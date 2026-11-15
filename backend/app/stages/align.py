"""Stage 4: Alignment (owner: C).

Pair written notes with sung notes: match / skipped / extra. No judgments here (stage 5 judges).
Output shape: contracts/alignment.sample.json. Spec: docs/DECISIONS.md 4.4; walkthrough of the
table method: docs/ALIGNMENT_EXPLAINED.md.

Steps (later parts fill in the marked ones):
  1. drop rests (they never appear in pairs)
  2. first pass, pitch only: octave shift = the shift whose pairing costs least
  3. the singer's clock from that pass's near-right matches: offset (strict), or offset + speed (free)
  4. fill the table (pitch + timing) and trace back
  5. split-note merge: an extra that is really a piece of its neighbouring match joins it
  6. joined notes: a skipped repeated note that its neighbour's long sung note covers is a match too
  7. near_id on extras
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
OFFSET_PITCH_TOL = 0.5  # semitones: only in-tune / out-of-tune pairs vote; a wrong-note pair (> 50 cents,
#                         stage 5's line) may be a wrong pairing from the timing-free first pass
MIN_OFFSET_PAIRS = 3  # fewer voting pairs than this -> too little to trust, offset 0
# Free mode also measures the singer's speed (tempo_scale = score seconds per sung second). Outside this
# range the fit is treated as broken and we fall back to the strict-mode clock (speed 1, median offset).
MIN_TEMPO_SCALE = 0.4
MAX_TEMPO_SCALE = 2.5

# Split-note merge (DECISIONS.md 4.4): stage 3 sometimes cuts one sung note in two (vibrato, a dip in
# loudness, a scoop into the note). The extra piece joins its neighbouring match when it is:
MERGE_PITCH_TOL = 1.0  # within 1 semitone of the neighbouring piece (short pieces of a vibrato note
#                        can land ~1 semitone apart: one catches the top of the wobble, one the bottom)
MERGE_MAX_GAP_SEC = 0.2  # at most this much silence between the pieces (a deliberate re-sing has more)
# ...and no closer in pitch to the written notes either side than to this one (so a note sliding
# toward the next written note isn't swallowed by the previous one).
# The table must know such a piece is cheap: priced as a full extra (3), it would rather shift every
# later pairing by one note than pay for a wrong note + a piece. Merged afterwards, so it costs nothing.
PIECE_EXTRA_COST = 0.5  # extra cost for a sung note that looks like a piece of its sung neighbour

# Joined notes: the opposite stage 3 error. Written G G sung smoothly is one long sung G; the second G
# would show as skipped. It is matched to the same sung note ("joined": true) when its neighbour is the
# same written pitch, the sung note is in tune for it, and lasts through at least this share of it:
JOIN_MIN_COVER = 0.5


def align(expected_notes: dict, sung_notes: dict, mode: str = "strict") -> dict:
    """mode: "free" (the singer's own tempo; the main mode) or "strict" (the score's tempo)."""
    if mode not in ("free", "strict"):
        raise AnalysisError("invalid_input", f"Unknown mode {mode!r}: use free or strict.", "align", 400)

    written = [n for n in expected_notes["notes"] if not n["is_rest"]]
    sung = sung_notes["notes"]

    octave_shift, first_pass = _choose_octave_shift(written, sung)
    time_offset, tempo_scale = _singer_clock(written, sung, octave_shift, first_pass, mode)
    # Sung starts on the score's clock, in seconds: score time = (sung time - offset) x tempo_scale.
    # Seconds (not beats) because the score may change tempo: onset_sec already follows every mark.
    sung_secs = [(s["start_sec"] - time_offset) * tempo_scale for s in sung]

    pairs, _ = _fill_and_trace(written, sung, sung_secs, octave_shift)
    pairs = _merge_split_notes(pairs, written, sung, octave_shift)
    pairs = _join_repeated_notes(pairs, written, sung, octave_shift, time_offset, tempo_scale)
    total = sum(p["cost"] for p in pairs)

    sec_of = {s["sid"]: t for s, t in zip(sung, sung_secs)}
    for pair in pairs:
        if pair["type"] == "extra":
            pair["near_id"] = _near_id(expected_notes["notes"], sec_of[pair["sids"][0]])

    return {
        "octave_shift": octave_shift,
        "tempo_scale": round(tempo_scale, 4),
        "time_offset_sec": round(time_offset, 4),
        "total_cost": round(total, 4),
        "pairs": pairs,
    }


def pair_cost(
    written: dict, sung_midi: float, sung_sec: float, octave_shift: int = 0, beat_weight: float = BEAT_WEIGHT
) -> float:
    """Semitones apart (after the octave shift, capped) + a little for being apart in time.
    Time is measured in beats at this written note's own tempo (the score may change tempo)."""
    semitones = min(abs(sung_midi - octave_shift - written["midi"]), PITCH_CAP)
    beats_per_sec = written["duration_beats"] / written["duration_sec"] if written["duration_sec"] > 0 else 0.0
    beats_apart = abs(sung_sec - written["onset_sec"]) * beats_per_sec
    return semitones + beat_weight * beats_apart


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


def _singer_clock(
    written: list[dict], sung: list[dict], octave_shift: int, first_pass: list[dict], mode: str
) -> tuple[float, float]:
    """(time_offset_sec, tempo_scale) so that score time = (sung time - offset) x tempo_scale.

    Each near-right match from the pitch-only first pass gives a point (written start, sung start).
    Strict: speed is the score's (scale 1); offset = median of (sung - written), which ignores a cough,
    a skipped note or a few wrong pairings. Works for uploads, scores that open with rests, and
    recording delay alike.
    Free: fit a line sung = offset + slope x written through the points, outlier-resistant (Theil-Sen:
    slope = median of the slopes between every two points, offset = median of the leftovers); the
    singer's speed is tempo_scale = 1 / slope. Too few points or an absurd speed -> the strict clock.
    """
    points = _clock_points(written, sung, octave_shift, first_pass)
    if len(points) < MIN_OFFSET_PAIRS:
        return 0.0, 1.0
    strict_clock = (median(s - w for w, s in points), 1.0)
    if mode == "strict":
        return strict_clock
    slopes = [(s2 - s1) / (w2 - w1) for i, (w1, s1) in enumerate(points) for (w2, s2) in points[i + 1:] if w2 - w1 > 1e-9]
    if not slopes:
        return strict_clock
    slope = median(slopes)
    if not slope > 0 or not MIN_TEMPO_SCALE <= 1.0 / slope <= MAX_TEMPO_SCALE:
        return strict_clock
    offset = median(s - slope * w for w, s in points)
    return offset, 1.0 / slope


def _clock_points(written, sung, octave_shift, first_pass) -> list[tuple[float, float]]:
    """(written onset_sec, sung start_sec) for each first-pass match within OFFSET_PITCH_TOL, in score order."""
    w_by_id = {w["id"]: w for w in written}
    s_by_id = {s["sid"]: s for s in sung}
    points = []
    for p in first_pass:
        if p["type"] != "match":
            continue
        w, s = w_by_id[p["id"]], s_by_id[p["sids"][0]]
        if abs(s["midi"] - octave_shift - w["midi"]) <= OFFSET_PITCH_TOL:
            points.append((w["onset_sec"], s["start_sec"]))
    return points


def _fill_and_trace(
    written: list[dict],
    sung: list[dict],
    sung_secs: list[float],
    octave_shift: int,
    beat_weight: float = BEAT_WEIGHT,
):
    """Edit-distance table: cell (i, j) = cheapest way to handle the first i written and j sung notes."""
    n, m = len(written), len(sung)
    extra_cost = [PIECE_EXTRA_COST if _looks_like_piece(sung, j) else EXTRA_COST for j in range(m)]
    table = [[0.0] * (m + 1) for _ in range(n + 1)]
    move = [[None] * (m + 1) for _ in range(n + 1)]
    step = [[0.0] * (m + 1) for _ in range(n + 1)]  # cost of the winning move itself (per-pair debug cost)

    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            options = []
            if i > 0 and j > 0:  # pair written i-1 with sung j-1 (diagonal)
                c = pair_cost(written[i - 1], sung[j - 1]["midi"], sung_secs[j - 1], octave_shift, beat_weight)
                options.append((table[i - 1][j - 1] + c, "match", c))
            if i > 0:  # written i-1 skipped (from above)
                options.append((table[i - 1][j] + SKIP_COST, "skipped", SKIP_COST))
            if j > 0:  # sung j-1 extra (from the left)
                options.append((table[i][j - 1] + extra_cost[j - 1], "extra", extra_cost[j - 1]))
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


def _near_id(all_notes: list[dict], sec: float) -> str:
    """The written note or rest whose span (seconds) contains `sec`, else the one with the nearest onset."""
    for n in all_notes:
        if n["onset_sec"] <= sec < n["onset_sec"] + n["duration_sec"]:
            return n["id"]
    return min(all_notes, key=lambda n: abs(n["onset_sec"] - sec))["id"]


def _looks_like_piece(sung: list[dict], j: int) -> bool:
    """Sung note j is within 1 semitone of a sung neighbour with at most a short gap between them."""
    for k in (j - 1, j + 1):
        if 0 <= k < len(sung):
            a, b = (sung[k], sung[j]) if k < j else (sung[j], sung[k])
            if b["start_sec"] - a["end_sec"] <= MERGE_MAX_GAP_SEC and abs(a["midi"] - b["midi"]) <= MERGE_PITCH_TOL:
                return True
    return False


def _merge_split_notes(pairs: list[dict], written: list[dict], sung: list[dict], octave_shift: int) -> list[dict]:
    """Fold extras that are really pieces of a neighbouring match into it (sids in time order).
    Repeats until nothing changes, so a note cut into 3+ pieces ends up as one match."""
    sung_by_sid = {s["sid"]: s for s in sung}
    index_of = {w["id"]: k for k, w in enumerate(written)}
    merged = True
    while merged:
        merged = False
        for k, pair in enumerate(pairs):
            if pair["type"] != "extra":
                continue
            for nb in (k - 1, k + 1):
                if 0 <= nb < len(pairs) and pairs[nb]["type"] == "match":
                    match = pairs[nb]
                    if _is_piece_of(sung_by_sid[pair["sids"][0]], match, sung_by_sid, written, index_of, octave_shift):
                        match["sids"] = sorted(match["sids"] + pair["sids"], key=lambda sid: sung_by_sid[sid]["start_sec"])
                        del pairs[k]
                        merged = True
                        break
            if merged:
                break
    return pairs


def _is_piece_of(extra: dict, match: dict, sung_by_sid, written, index_of, octave_shift) -> bool:
    pieces = [sung_by_sid[sid] for sid in match["sids"]]
    if extra["start_sec"] < pieces[0]["start_sec"]:  # extra comes first: compare with the first piece
        neighbour, gap = pieces[0], pieces[0]["start_sec"] - extra["end_sec"]
    else:  # extra comes after: compare with the last piece
        neighbour, gap = pieces[-1], extra["start_sec"] - pieces[-1]["end_sec"]
    if gap > MERGE_MAX_GAP_SEC or abs(extra["midi"] - neighbour["midi"]) > MERGE_PITCH_TOL:
        return False
    k = index_of[match["id"]]
    pitch = extra["midi"] - octave_shift
    here = abs(pitch - written[k]["midi"])
    sides = [written[i]["midi"] for i in (k - 1, k + 1) if 0 <= i < len(written)]
    return all(here <= abs(pitch - m) for m in sides)


def _join_repeated_notes(pairs, written, sung, octave_shift, time_offset, tempo_scale) -> list[dict]:
    """Turn a skipped note into a match sharing its neighbour's sung note when that one sung note
    really covers both written notes (same written pitch, in tune, lasts through >= JOIN_MIN_COVER of
    the skipped note on the score's clock). Left to right, so G G G sung as one note joins twice."""
    sung_by_sid = {s["sid"]: s for s in sung}
    index_of = {w["id"]: k for k, w in enumerate(written)}
    for k, pair in enumerate(pairs):
        if pair["type"] != "skipped":
            continue
        i = index_of[pair["id"]]
        for nb in (k - 1, k + 1):
            if not (0 <= nb < len(pairs) and pairs[nb]["type"] == "match"):
                continue
            j = index_of[pairs[nb]["id"]]
            # Same written pitch: the rule as agreed. (Today the in-tune check below already implies it,
            # since neighbouring written notes a semitone or more apart can't both be within 0.5.)
            if abs(i - j) != 1 or written[j]["midi"] != written[i]["midi"]:
                continue
            piece = sung_by_sid[pairs[nb]["sids"][-1 if nb < k else 0]]  # the piece nearest the skipped note
            if abs(piece["midi"] - octave_shift - written[i]["midi"]) > OFFSET_PITCH_TOL:
                continue
            start = (piece["start_sec"] - time_offset) * tempo_scale
            end = (piece["end_sec"] - time_offset) * tempo_scale
            w0, w1 = written[i]["onset_sec"], written[i]["onset_sec"] + written[i]["duration_sec"]
            if min(end, w1) - max(start, w0) >= JOIN_MIN_COVER * written[i]["duration_sec"]:
                cost = round(min(abs(piece["midi"] - octave_shift - written[i]["midi"]), PITCH_CAP), 4)
                pairs[k] = {"type": "match", "id": pair["id"], "sids": [piece["sid"]], "cost": cost, "joined": True}
                break
    return pairs
