"""Stage 4: Alignment (owner: C).

Pair written notes with sung notes: match / skipped / extra. No judgments here (stage 5 judges).
Output shape: contracts/alignment.sample.json. Spec: docs/DECISIONS.md 4.4; walkthrough of the
table method: docs/ALIGNMENT_EXPLAINED.md.

Steps (later parts fill in the marked ones):
  1. drop rests (they never appear in pairs)
  2. first pass, pitch only: octave shift = the shift whose pairing costs least
  3. time offset from that pass's near-right matches / tempo scale [3e: 1.0 for now]
  4. fill the table (pitch + timing) and trace back
  5. split-note merge                               [3c: every match has one sid for now]
  6. near_id on extras
"""

from statistics import median

from app.errors import AnalysisError

# Costs (starting values from DECISIONS.md 4.4; tune on the test takes)
PITCH_CAP = 4.0  # semitones; past this every wrong note costs the same
BEAT_WEIGHT = 0.5  # cost per beat between the written onset and the sung start
SKIP_COST = 3.0  # written note not sung
EXTRA_COST = 3.0  # sung note not in the score
# On an exact tie, prefer the explanation with fewer claimed mistakes: "you sang it" over skip + extra.
# (Comparing (cost, "name") tuples would break ties alphabetically, so "extra" would beat "match".)
TIE_ORDER = {"match": 0, "skipped": 1, "extra": 2}

# Octave shift: a voice singing the line in another octave (baritone on a soprano line: -12; soprano on
# a bass line: +12 or +24). Listed in tie order: on an exact tie, the smallest shift wins.
OCTAVE_SHIFTS = (0, -12, 12, -24, 24)

# Time offset (DECISIONS.md section 3, "Time zero"): how far the singer's timeline is shifted from the
# score's (silence before singing in an upload, browser recording delay). Measured, then removed.
OFFSET_PITCH_TOL = 1.0  # semitones: only near-right pairs vote (a "wrong note" pair may be a wrong pairing)
MIN_OFFSET_PAIRS = 3  # fewer voting pairs than this -> too little to trust, offset 0


def align(expected_notes: dict, sung_notes: dict, mode: str = "strict") -> dict:
    """mode: "strict" (against the click) or "free" (against the singer's own tempo; not built yet)."""
    if mode != "strict":
        raise AnalysisError(
            "invalid_input", "Free tempo mode isn't available yet. Please use strict mode.", "align", 422
        )

    written = [n for n in expected_notes["notes"] if not n["is_rest"]]
    sung = sung_notes["notes"]
    beats_per_sec = expected_notes["tempo_bpm"] / 60.0

    octave_shift, first_pass = _choose_octave_shift(written, sung)
    tempo_scale = 1.0  # 3e (score time = sung time x tempo_scale)
    time_offset = _time_offset(written, sung, octave_shift, first_pass)
    sung_beats = [(s["start_sec"] - time_offset) * tempo_scale * beats_per_sec for s in sung]

    pairs, total = _fill_and_trace(written, sung, sung_beats, octave_shift)

    beat_of = {s["sid"]: b for s, b in zip(sung, sung_beats)}
    for pair in pairs:
        if pair["type"] == "extra":
            pair["near_id"] = _near_id(expected_notes["notes"], beat_of[pair["sids"][0]])

    return {
        "octave_shift": octave_shift,
        "tempo_scale": tempo_scale,
        "time_offset_sec": round(time_offset, 4),
        "total_cost": round(total, 4),
        "pairs": pairs,
    }


def pair_cost(
    written: dict, sung_midi: float, sung_beat: float, octave_shift: int = 0, beat_weight: float = BEAT_WEIGHT
) -> float:
    """Semitones apart (after the octave shift, capped) + a little for being apart in time."""
    semitones = min(abs(sung_midi - octave_shift - written["midi"]), PITCH_CAP)
    return semitones + beat_weight * abs(sung_beat - written["onset_beats"])


def _choose_octave_shift(written: list[dict], sung: list[dict]) -> tuple[int, list[dict]]:
    """First pass: pair by pitch only (timing off, so an unknown time offset can't mislead it), once per
    candidate shift. The right shift makes pairs cost ~0; an octave off makes them cost the cap, so the
    cheapest pairing is the "most common gap" measured on real pairs. Returns (shift, its pairs)."""
    best = None
    for rank, shift in enumerate(OCTAVE_SHIFTS):
        pairs, cost = _fill_and_trace(written, sung, [0.0] * len(sung), shift, beat_weight=0.0)
        key = (round(cost, 9), rank)
        if best is None or key < best[0]:
            best = (key, shift, pairs)
    return best[1], best[2]


def _time_offset(written: list[dict], sung: list[dict], octave_shift: int, first_pass: list[dict]) -> float:
    """Seconds to subtract from sung times so they line up with the score.

    Each near-right match from the pitch-only first pass votes with (sung start - written start); the
    median ignores a cough, a skipped note or a few wrong pairings. Works for uploads, scores that open
    with rests, and recording delay alike.
    """
    pairs = first_pass
    w_by_id = {w["id"]: w for w in written}
    s_by_id = {s["sid"]: s for s in sung}
    votes = []
    for p in pairs:
        if p["type"] != "match":
            continue
        w, s = w_by_id[p["id"]], s_by_id[p["sids"][0]]
        if abs(s["midi"] - octave_shift - w["midi"]) <= OFFSET_PITCH_TOL:
            votes.append(s["start_sec"] - w["onset_sec"])
    return median(votes) if len(votes) >= MIN_OFFSET_PAIRS else 0.0


def _fill_and_trace(
    written: list[dict],
    sung: list[dict],
    sung_beats: list[float],
    octave_shift: int,
    beat_weight: float = BEAT_WEIGHT,
):
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
                c = pair_cost(written[i - 1], sung[j - 1]["midi"], sung_beats[j - 1], octave_shift, beat_weight)
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
