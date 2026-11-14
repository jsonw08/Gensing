"""Stage 4: Alignment (owner: C).

Pair written notes with sung notes: match / skipped / extra. No judgments here (stage 5 judges).
Output shape: contracts/alignment.sample.json. Spec: docs/DECISIONS.md 4.4; walkthrough of the
table method: docs/ALIGNMENT_EXPLAINED.md.

Steps (later parts fill in the marked ones):
  1. drop rests (they never appear in pairs)
  2. octave shift                                   [3b: detected; 0 for now]
  3. time offset / tempo scale from matched pairs   [offset step + 3e: 0 s and 1.0 for now]
  4. fill the table and trace back                  (this part)
  5. split-note merge                               [3c: every match has one sid for now]
  6. near_id on extras                              (this part)
"""

from app.errors import AnalysisError

# Costs (starting values from DECISIONS.md 4.4; tune on the test takes)
PITCH_CAP = 4.0  # semitones; past this every wrong note costs the same
BEAT_WEIGHT = 0.5  # cost per beat between the written onset and the sung start
SKIP_COST = 3.0  # written note not sung
EXTRA_COST = 3.0  # sung note not in the score
# On an exact tie, prefer the explanation with fewer claimed mistakes: "you sang it" over skip + extra.
# (Comparing (cost, "name") tuples would break ties alphabetically, so "extra" would beat "match".)
TIE_ORDER = {"match": 0, "skipped": 1, "extra": 2}


def align(expected_notes: dict, sung_notes: dict, mode: str = "strict") -> dict:
    """mode: "strict" (against the click) or "free" (against the singer's own tempo; not built yet)."""
    if mode != "strict":
        raise AnalysisError(
            "invalid_input", "Free tempo mode isn't available yet. Please use strict mode.", "align", 422
        )

    written = [n for n in expected_notes["notes"] if not n["is_rest"]]
    sung = sung_notes["notes"]
    beats_per_sec = expected_notes["tempo_bpm"] / 60.0

    octave_shift = 0  # 3b
    tempo_scale = 1.0  # 3e (score time = sung time x tempo_scale)
    sung_beats = [s["start_sec"] * tempo_scale * beats_per_sec for s in sung]

    pairs, total = _fill_and_trace(written, sung, sung_beats, octave_shift)

    beat_of = {s["sid"]: b for s, b in zip(sung, sung_beats)}
    for pair in pairs:
        if pair["type"] == "extra":
            pair["near_id"] = _near_id(expected_notes["notes"], beat_of[pair["sids"][0]])

    return {
        "octave_shift": octave_shift,
        "tempo_scale": tempo_scale,
        "total_cost": round(total, 4),
        "pairs": pairs,
    }


def pair_cost(written: dict, sung_midi: float, sung_beat: float, octave_shift: int = 0) -> float:
    """Semitones apart (after the octave shift, capped) + a little for being apart in time."""
    semitones = min(abs(sung_midi - octave_shift - written["midi"]), PITCH_CAP)
    return semitones + BEAT_WEIGHT * abs(sung_beat - written["onset_beats"])


def _fill_and_trace(written: list[dict], sung: list[dict], sung_beats: list[float], octave_shift: int):
    """Edit-distance table: cell (i, j) = cheapest way to handle the first i written and j sung notes."""
    n, m = len(written), len(sung)
    table = [[0.0] * (m + 1) for _ in range(n + 1)]
    move = [[None] * (m + 1) for _ in range(n + 1)]
    step = [[0.0] * (m + 1) for _ in range(n + 1)]  # cost of the winning move itself (per-pair debug cost)

    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            options = []
            if i > 0 and j > 0:  # pair written i-1 with sung j-1 (diagonal)
                c = pair_cost(written[i - 1], sung[j - 1]["midi"], sung_beats[j - 1], octave_shift)
                options.append((table[i - 1][j - 1] + c, "match", c))
            if i > 0:  # written i-1 skipped (from above)
                options.append((table[i - 1][j] + SKIP_COST, "skipped", SKIP_COST))
            if j > 0:  # sung j-1 extra (from the left)
                options.append((table[i][j - 1] + EXTRA_COST, "extra", EXTRA_COST))
            best = min(options, key=lambda o: (round(o[0], 9), TIE_ORDER[o[1]]))  # round: float noise
            table[i][j], move[i][j], step[i][j] = best

    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        kind, cost = move[i][j], round(step[i][j], 4)
        if kind == "match":
            pairs.append({"type": "match", "id": written[i - 1]["id"], "sids": [sung[j - 1]["sid"]], "cost": cost})
            i, j = i - 1, j - 1
        elif kind == "skipped":
            pairs.append({"type": "skipped", "id": written[i - 1]["id"], "sids": [], "cost": cost})
            i -= 1
        else:
            pairs.append({"type": "extra", "id": None, "sids": [sung[j - 1]["sid"]], "cost": cost})
            j -= 1
    return pairs[::-1], table[n][m]


def _near_id(all_notes: list[dict], beat: float) -> str:
    """The written note or rest whose span contains `beat`, else the one with the nearest onset."""
    for n in all_notes:
        if n["onset_beats"] <= beat < n["onset_beats"] + n["duration_beats"]:
            return n["id"]
    return min(all_notes, key=lambda n: abs(n["onset_beats"] - beat))["id"]
