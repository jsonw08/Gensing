"""Stage 5: Grading and scoring (owner: C).

Judge every pair, compute the overall score, find patterns for feedback.
Output shape: contracts/results.sample.json. Spec: docs/DECISIONS.md 4.5.

Steps (later parts fill in the marked ones):
  1. per-note verdicts: pitch (cents -> in tune / out of tune / wrong note) and timing (early / on time /
     late), judged separately; extras; meta and counts
  2. the overall score: pitch, intonation, rhythm, completeness -> weighted total
  3. patterns for the coach: worst bars, drift, high notes flat, rushing/dragging, shaky long notes,
     errors after leaps. Computed here so the LLM (stage 6) never does math.

Pitch and timing never mix: a note can be flat and late. The notehead color is the pitch verdict.
"""

from statistics import median

from app.errors import AnalysisError
from app.stages.align import _sections  # fermata sections, same split as stage 4

# Thresholds per preset (DECISIONS.md 4.5). A note is in tune within `in_tune_cents`; on time within
# +/-max(window_beats of its own beat, min_window_ms). Advanced has a lower floor than 80 ms: 1/16 beat
# is 47 ms at 80 BPM, so an 80 ms floor would make its timing no stricter than default's.
PRESETS = {
    "default": {"in_tune_cents": 25, "window_beats": 1 / 8, "min_window_ms": 80},
    "beginner": {"in_tune_cents": 35, "window_beats": 1 / 4, "min_window_ms": 80},
    "advanced": {"in_tune_cents": 15, "window_beats": 1 / 16, "min_window_ms": 50},
}
# Past this the singer is closer to another note than to the written one: wrong note, every preset.
WRONG_NOTE_CENTS = 50
# Stage 3's mean voicing confidence below this -> "uncertain": still judged, drawn faded, left out of
# the score. Same value as stage 3's frame cutoff; the test takes sit at 0.83-0.93.
UNCERTAIN_CONF = 0.5

# Free mode: each note's timing is judged against its neighbours (up to this many timed notes on each
# side, same fermata section, not the note itself), so gradual slowing or speeding up is fine and only a
# note that sticks out is early/late. Fewer points than MIN_LOCAL_POINTS: stage 4's whole-take clock.
LOCAL_NEIGHBOURS = 4
MIN_LOCAL_POINTS = 3

# Overall score (DECISIONS.md 4.5): pitch counts most. Every part is 0-100; `uncertain` notes (and
# low-confidence extras) are left out of all of them.
WEIGHTS = {"pitch": 0.50, "intonation": 0.25, "rhythm": 0.15, "completeness": 0.10}
INTONATION_CENTS_PER_POINT = 0.5  # intonation = 100 - 2 x average |cents| on right notes (50 cents -> 0)
EXTRA_PENALTY = 5  # completeness points per extra note

# Patterns (DECISIONS.md 4.5). `uncertain` notes and low-confidence extras are left out of all of them.
WORST_MEASURES = 3  # at most this many bars, most problems first
HIGH_FLAT_GAP_CENTS = 15  # high notes flat: the upper half averages this much flatter than the lower half
HIGH_FLAT_MAX_CENTS = -10  # ...and is itself at least this flat
MIN_HALF_NOTES = 3  # each half needs this many right notes
TEMPO_CHANGE = 0.08  # rushing / dragging: the singer's speed changes by more than 8% (last third vs first;
#                      strict mode also: the whole take vs the score's tempo)
MIN_THIRD_POINTS = 3  # timed notes needed in a third to measure its speed
SHAKY_MIN_BEATS = 1.0  # long note: written >= 1 beat
SHAKY_CENTS = 40  # shaky: pitch std dev over the note's middle (stage 3's stability_cents) above this.
#                   A +/-30 cent vibrato is ~21; stage 3 reads the test takes at 8-14. Tune on real voices.
LEAP_SEMITONES = 4  # errors after leaps: a pitch error right after a written jump of >= 4 semitones

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def grade(
    alignment: dict,
    expected_notes: dict,
    sung_notes: dict,
    mode: str = "free",
    preset: str = "default",
) -> dict:
    """mode: "free" (the main mode) or "strict"; preset: "default", "beginner" or "advanced"."""
    if mode not in ("free", "strict"):
        raise AnalysisError("invalid_input", f"Unknown mode {mode!r}: use free or strict.", "grade", 400)
    if preset not in PRESETS:
        raise AnalysisError("invalid_input", f"Unknown preset {preset!r}: use {', '.join(PRESETS)}.", "grade", 400)
    th = PRESETS[preset]

    all_notes = expected_notes["notes"]
    written = [n for n in all_notes if not n["is_rest"]]
    sung_by_sid = {s["sid"]: s for s in sung_notes["notes"]}
    pair_of = {p["id"]: p for p in alignment["pairs"] if p["type"] != "extra"}
    shift = alignment["octave_shift"]

    notes = [_judge_pitch(w, pair_of[w["id"]], sung_by_sid, shift, th) for w in written]
    _judge_timing(notes, written, pair_of, sung_by_sid, alignment, mode, th, _sections(all_notes))
    extras = _extras(alignment, sung_by_sid, all_notes, shift)
    sure_extras = [x for x in extras if sung_by_sid[x["sid"]]["conf"] >= UNCERTAIN_CONF]

    return {
        "meta": {
            "title": expected_notes.get("title"),
            "mode": mode,
            "preset": preset,
            "tempo_bpm": expected_notes["tempo_bpm"],
            "octave_shift": shift,
            "timing_offset_ms": round(alignment["time_offset_sec"] * 1000),
        },
        "score": _score(notes, len(sure_extras)),
        "counts": _counts(notes, extras),
        "notes": notes,
        "extras": extras,
        "patterns": _patterns(notes, written, all_notes, pair_of, sung_by_sid, sure_extras, alignment, mode,
                              _sections(all_notes)),
    }


def midi_name(midi: float) -> str:
    """Nearest note name, sharps (DECISIONS.md section 3: sung notes are spelled with sharps)."""
    m = round(midi)
    return f"{SHARP_NAMES[m % 12]}{m // 12 - 1}"


def _sung_piece(pair: dict, sung_by_sid: dict) -> dict:
    """What was sung for a match, as one note. Split notes (several sids): start of the first piece,
    end of the last, duration-weighted pitch and confidence."""
    pieces = [sung_by_sid[sid] for sid in pair["sids"]]
    weights = [max(p["end_sec"] - p["start_sec"], 1e-6) for p in pieces]
    total = sum(weights)
    return {
        "start_sec": pieces[0]["start_sec"],
        "end_sec": pieces[-1]["end_sec"],
        **{k: sum(p[k] * w for p, w in zip(pieces, weights)) / total for k in ("midi", "conf", "stability_cents")},
    }


def _judge_pitch(w: dict, pair: dict, sung_by_sid: dict, shift: int, th: dict) -> dict:
    """One results.notes entry with the pitch verdict; timing is filled in by _judge_timing."""
    entry = {
        "id": w["id"], "measure": w["measure"], "name": w["name"], "lyric": w["lyric"],
        "status": "skipped", "cents": None, "sang": None,
        "timing": None, "timing_ms": None,
        "sung_start_sec": None, "sung_end_sec": None,
        "uncertain": False,
    }
    if pair["type"] != "match":
        return entry
    s = _sung_piece(pair, sung_by_sid)
    cents = (s["midi"] - shift - w["midi"]) * 100
    right_note = abs(cents) <= WRONG_NOTE_CENTS
    entry.update({
        "status": "in_tune" if abs(cents) <= th["in_tune_cents"] else "out_of_tune" if right_note else "wrong_note",
        "cents": round(cents),
        # the written note (sharp spelling) unless it's a wrong note, so exactly 50 cents doesn't say
        # "sang F#4" on an out-of-tune F4
        "sang": midi_name(w["midi"] if right_note else s["midi"] - shift),
        "sung_start_sec": round(s["start_sec"], 3),
        "sung_end_sec": round(s["end_sec"], 3),
        "uncertain": s["conf"] < UNCERTAIN_CONF,
    })
    return entry


def _judge_timing(notes, written, pair_of, sung_by_sid, alignment, mode, th, section_of) -> None:
    """Fill timing / timing_ms on every match that has its own start (not skipped, not joined).

    Expected sung start of a written note, starting from stage 4's clock (sung = onset_sec / tempo_scale
    + offset; the pair's own time_offset_sec in fermata scores, so after a hold the singer is judged from
    where they came back in):
      strict: exactly that (tempo_scale is 1: the score's tempo);
      free:   that, corrected by its neighbours' leftovers (sung start - clock), so the reference
              follows the singer's own slowing down / speeding up. Two readings of the neighbours:
              steady (their median leftover) and steadily changing (a line through their leftovers,
              Theil-Sen). The note is early/late only if it sticks out from both; timing_ms is the
              smaller deviation. Why both: the median is hard to fool (two planted mistakes among a
              last note's 4 neighbours don't move it) but lags in a big ritardando when every neighbour
              is on one side; the line follows the ritardando but two bad neighbours can tilt it.
    Window: +/-max(window_beats of the note's own beat in sung seconds, min_window_ms).
    """
    scale = alignment["tempo_scale"]
    timed = []  # (index into notes, written onset_sec, leftover = sung start - clock, section)
    for k, w in enumerate(written):
        pair = pair_of[w["id"]]
        if pair["type"] == "match" and not pair.get("joined"):
            start = sung_by_sid[pair["sids"][0]]["start_sec"]
            offset = pair.get("time_offset_sec", alignment["time_offset_sec"])
            timed.append((k, w["onset_sec"], start - (w["onset_sec"] / scale + offset), section_of[w["id"]]))

    for t, (k, onset, leftover, section) in enumerate(timed):
        dev = leftover
        if mode == "free":
            dev = min((leftover - c for c in _local_corrections(timed, t, section, notes)), key=abs, default=dev)
        w = written[k]
        beat_sec = w["duration_sec"] / w["duration_beats"] / scale  # the note's own beat, in sung seconds
        window = max(th["window_beats"] * beat_sec, th["min_window_ms"] / 1000)
        notes[k]["timing_ms"] = round(dev * 1000)
        notes[k]["timing"] = "on_time" if abs(dev) <= window else ("late" if dev > 0 else "early")


def _local_corrections(timed, t, section, notes) -> list[float]:
    """Where the neighbours say timed[t]'s leftover should be: [median, line at its onset]. Neighbours =
    up to LOCAL_NEIGHBOURS timed notes on each side (same fermata section, not uncertain, not itself).
    [] if fewer than MIN_LOCAL_POINTS (the whole-take clock alone)."""
    same = [i for i, x in enumerate(timed) if x[3] == section and i != t and not notes[x[0]]["uncertain"]]
    near = [i for i in same if i < t][-LOCAL_NEIGHBOURS:] + [i for i in same if i > t][:LOCAL_NEIGHBOURS]
    if len(near) < MIN_LOCAL_POINTS:
        return []
    pts = [(timed[i][1], timed[i][2]) for i in near]
    out = [median(r for _, r in pts)]
    slopes = [(r2 - r1) / (w2 - w1) for i, (w1, r1) in enumerate(pts) for (w2, r2) in pts[i + 1:] if w2 - w1 > 1e-9]
    if slopes:
        b = median(slopes)
        out.append(median(r - b * w for w, r in pts) + b * timed[t][1])
    return out


def _extras(alignment, sung_by_sid, all_notes, shift) -> list[dict]:
    rest_ids = {n["id"] for n in all_notes if n["is_rest"]}
    out = []
    for p in alignment["pairs"]:
        if p["type"] != "extra":
            continue
        s = sung_by_sid[p["sids"][0]]
        out.append({
            "sid": s["sid"],
            "near_id": p["near_id"],
            "sang": midi_name(s["midi"] - shift),
            "during_rest": p["near_id"] in rest_ids,
            "start_sec": round(s["start_sec"], 3),
            "end_sec": round(s["end_sec"], 3),
        })
    return out


def _score(notes: list[dict], n_extras: int) -> dict:
    """The score card (ints 0-100), from the notes that aren't uncertain.
      pitch:        % of written notes sung on the right note (in tune or out of tune). A skipped note
                    counts against it too (and against completeness): not singing a note costs more
                    than singing the wrong one.
      intonation:   100 - 2 x average |cents| over the right notes (0 cents -> 100, 50 -> 0)
      rhythm:       % of the notes with a timing verdict that are on time (not skipped, not joined)
      completeness: % of written notes not skipped, minus EXTRA_PENALTY per extra
    Nothing to judge (no notes, or all uncertain): 0."""
    graded = [n for n in notes if not n["uncertain"]]
    right = [n for n in graded if n["status"] in ("in_tune", "out_of_tune")]
    timed = [n for n in graded if n["timing"] is not None]
    parts = {"pitch": 0.0, "intonation": 0.0, "rhythm": 0.0, "completeness": 0.0}
    if graded:
        parts["pitch"] = 100 * len(right) / len(graded)
        parts["completeness"] = 100 * sum(n["status"] != "skipped" for n in graded) / len(graded) - EXTRA_PENALTY * n_extras
    if right:
        parts["intonation"] = 100 - sum(abs(n["cents"]) for n in right) / len(right) / INTONATION_CENTS_PER_POINT
    if timed:
        parts["rhythm"] = 100 * sum(n["timing"] == "on_time" for n in timed) / len(timed)
    parts = {k: min(max(v, 0.0), 100.0) for k, v in parts.items()}
    total = sum(WEIGHTS[k] * v for k, v in parts.items())  # from the unrounded parts
    return {"total": _round(total), **{k: _round(v) for k, v in parts.items()}}


def _round(x: float) -> int:
    """Half up (82.5 -> 83), not Python's round-half-to-even (82.5 -> 82)."""
    return int(x + 0.5)


def _patterns(notes, written, all_notes, pair_of, sung_by_sid, extras, alignment, mode, section_of) -> dict:
    """The facts stage 6 turns into coaching (field names fixed by DECISIONS.md 4.5)."""
    sure = [(n, w) for n, w in zip(notes, written) if not n["uncertain"]]
    right = [(n, w) for n, w in sure if n["status"] in ("in_tune", "out_of_tune")]

    # worst_measures: bars with the most problems (a pitch problem, a timing problem, an extra near it:
    # one each); ties -> the earlier bar. Only bars with at least one problem.
    measure_of = {e["id"]: e["measure"] for e in all_notes}
    problems: dict[int, int] = {}
    for n, _ in sure:
        k = (n["status"] != "in_tune") + (n["timing"] in ("early", "late"))
        if k:
            problems[n["measure"]] = problems.get(n["measure"], 0) + k
    for x in extras:
        m = measure_of[x["near_id"]]
        problems[m] = problems.get(m, 0) + 1
    worst = sorted(problems, key=lambda m: (-problems[m], m))[:WORST_MEASURES]

    # drift_cents: average cents of the right notes in the first and last third of the written notes
    # (null if that third has none)
    third = len(written) // 3
    def avg_cents(ids):
        cents = [n["cents"] for n, w in right if w["id"] in ids]
        return round(sum(cents) / len(cents)) if cents else None
    first_ids = {w["id"] for w in written[:third]} if third else set()
    last_ids = {w["id"] for w in written[-third:]} if third else set()

    # high_notes_flat: right notes above vs below the median written pitch (notes on it left out)
    high_flat = False
    if right:
        mid = median(w["midi"] for _, w in right)
        high = [n["cents"] for n, w in right if w["midi"] > mid]
        low = [n["cents"] for n, w in right if w["midi"] < mid]
        if len(high) >= MIN_HALF_NOTES and len(low) >= MIN_HALF_NOTES:
            h, lo = sum(high) / len(high), sum(low) / len(low)
            high_flat = h <= lo - HIGH_FLAT_GAP_CENTS and h <= HIGH_FLAT_MAX_CENTS

    # shaky_long_notes: right notes written >= 1 beat whose sung pitch wobbles more than SHAKY_CENTS
    shaky = [n["id"] for n, w in right if w["duration_beats"] >= SHAKY_MIN_BEATS
             and _sung_piece(pair_of[w["id"]], sung_by_sid)["stability_cents"] > SHAKY_CENTS]

    # errors_after_leaps: pitch errors right after a written jump of >= LEAP_SEMITONES (rests ignored)
    after_leaps = [n["id"] for k, (n, w) in enumerate(zip(notes, written))
                   if k > 0 and not n["uncertain"] and n["status"] in ("out_of_tune", "wrong_note")
                   and abs(w["midi"] - written[k - 1]["midi"]) >= LEAP_SEMITONES]

    return {
        "worst_measures": worst,
        "drift_cents": {"first_third": avg_cents(first_ids), "last_third": avg_cents(last_ids)},
        "high_notes_flat": high_flat,
        "timing_tendency": _timing_tendency(notes, written, pair_of, sung_by_sid, mode, section_of),
        "shaky_long_notes": shaky,
        "errors_after_leaps": after_leaps,
    }


def _timing_tendency(notes, written, pair_of, sung_by_sid, mode, section_of) -> str:
    """rushing / dragging / steady, from the singer's speed (sung seconds per score second, Theil-Sen
    over notes with their own start; slopes only between notes of the same fermata section).
    Both modes: the last third of those notes vs the first third (getting faster / slower).
    Strict mode, if that's steady: the whole take vs the score's tempo (1.0)."""
    pts = [(w["onset_sec"], sung_by_sid[pair_of[w["id"]]["sids"][0]]["start_sec"], section_of[w["id"]])
           for n, w in zip(notes, written) if n["timing"] is not None and not n["uncertain"]]

    def speed(points):
        slopes = [(s2 - s1) / (w2 - w1) for i, (w1, s1, k1) in enumerate(points) for (w2, s2, k2) in points[i + 1:]
                  if k1 == k2 and w2 - w1 > 1e-9]
        return median(slopes) if slopes else None

    def verdict(ratio):  # ratio = sung seconds per score second, relative: > 1 slower, < 1 faster
        if ratio is None or ratio <= 0:
            return "steady"
        return "dragging" if ratio > 1 + TEMPO_CHANGE else "rushing" if ratio < 1 / (1 + TEMPO_CHANGE) else "steady"

    third = len(pts) // 3
    trend = "steady"
    if third >= MIN_THIRD_POINTS:
        first, last = speed(pts[:third]), speed(pts[-third:])
        trend = verdict(last / first if first and last else None)
    if trend == "steady" and mode == "strict":
        return verdict(speed(pts))
    return trend


def _counts(notes: list[dict], extras: list[dict]) -> dict:
    status = [n["status"] for n in notes]
    timing = [n["timing"] for n in notes]
    return {
        "notes": len(notes),
        "in_tune": status.count("in_tune"),
        "out_of_tune": status.count("out_of_tune"),
        "wrong_note": status.count("wrong_note"),
        "skipped": status.count("skipped"),
        "extra": len(extras),
        "early": timing.count("early"),
        "late": timing.count("late"),
        "uncertain": sum(n["uncertain"] for n in notes),
    }
