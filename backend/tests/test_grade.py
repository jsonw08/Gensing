"""Stage 5 (grading) tests. Part 1: per-note verdicts (pitch, timing), extras, meta, counts."""

import json
from pathlib import Path

import pytest
from synth_sung import PIECES, TAKES, load_take, score_path, synth_notes

from app.errors import AnalysisError
from app.stages.align import align
from app.stages.grade import grade, midi_name
from app.stages.score import parse_score

REPO = Path(__file__).resolve().parents[2]
NAMES = {"B3": 59, "C4": 60, "D4": 62, "E4": 64, "F4": 65, "G4": 67, "A4": 69, "B4": 71, "C5": 72}


# --------------------------------------------------------------------------- tiny builders


def written(*notes, bpm=60.0, fermata_at=None):
    """written("C4", None, "E4"): one beat each, None = rest; ids m1-n0, m1-n1, ... (all bar 1)."""
    beat = 60.0 / bpm
    out = []
    for i, name in enumerate(notes):
        out.append({
            "id": f"m1-n{i}", "measure": 1, "index": i, "is_rest": name is None,
            "midi": None if name is None else NAMES[name], "name": name,
            "onset_beats": float(i), "duration_beats": 1.0, "onset_sec": i * beat, "duration_sec": beat,
            "lyric": None, "render_ids": [f"m1-n{i}"],
        })
        if i == fermata_at:
            out[-1]["fermata"] = True
    return {"title": "Test", "tempo_bpm": bpm, "beat_unit": "quarter", "notes": out}


def sung(*notes, conf=0.9):
    """sung((midi, start_sec), ...): each lasts 0.8 s (or (midi, start, end))."""
    out = []
    for k, n in enumerate(notes):
        midi, start = n[0], n[1]
        end = n[2] if len(n) > 2 else start + 0.8
        out.append({"sid": f"s{k}", "start_sec": start, "end_sec": end, "midi": float(midi),
                    "stability_cents": 20.0, "conf": conf})
    return {"notes": out}


def pitches(*names, cents=(), late=None, spacing=1.0):
    """Sung notes for written(*names): note k at k x spacing, `cents` added per note, `late` = {k: sec}."""
    late = late or {}
    out = []
    for k, name in enumerate(names):
        c = cents[k] if k < len(cents) else 0
        out.append((NAMES[name] + c / 100, k * spacing + late.get(k, 0.0)))
    return sung(*out)


def run(expected, sung_notes, mode="strict", preset="default"):
    return grade(align(expected, sung_notes, mode), expected, sung_notes, mode, preset)


def by_id(results):
    return {n["id"]: n for n in results["notes"]}


def alignment(pairs, shift=0, offset=0.0, scale=1.0):
    """A hand-made alignment (stage 4's shape), to test stage 5 without stage 4's choices."""
    return {"octave_shift": shift, "tempo_scale": scale, "time_offset_sec": offset, "total_cost": 0.0,
            "pairs": pairs}


# --------------------------------------------------------------------------- the test takes vs answer keys


def check_against_key(results, key):
    """Every written note's status/timing (and planted sang/cents) and every extra, as the answer key says."""
    notes = by_id(results)
    assert set(notes) == set(key["notes"])
    for nid, want in key["notes"].items():
        got = notes[nid]
        assert (nid, got["status"], got["timing"]) == (nid, want["status"], want["timing"])
        if "sang" in want:
            assert got["sang"] == want["sang"], nid
        if "cents" in want:
            assert abs(got["cents"] - want["cents"]) <= 2, nid
    got_x = [(x["near_id"], x["during_rest"], x["sang"]) for x in results["extras"]]
    assert got_x == [(x["near_id"], x["during_rest"], x["sang"]) for x in key["extras"]]


def graded_take(piece, take, mode, **kw):
    sung_notes, key = load_take(piece, take, **kw)
    expected = parse_score(score_path(piece), key["settings"]["tempo_bpm"])
    return grade(align(expected, sung_notes, mode), expected, sung_notes, mode), key


@pytest.mark.parametrize("mode", ["strict", "free"])
@pytest.mark.parametrize("take", TAKES)
@pytest.mark.parametrize("piece", PIECES)
def test_take_matches_answer_key(piece, take, mode):
    results, key = graded_take(piece, take, mode)
    check_against_key(results, key)
    assert results["meta"]["octave_shift"] == key["expect"]["octave_shift"]
    assert abs(results["meta"]["timing_offset_ms"] - key["expect"].get("timing_offset_ms", 0)) <= 5


@pytest.mark.parametrize("mode", ["strict", "free"])
@pytest.mark.parametrize("take", TAKES)
@pytest.mark.parametrize("piece", PIECES)
def test_take_with_jittered_note_edges(piece, take, mode):
    # stage 3 never finds edges exactly; +/-20 ms must not change any verdict
    results, key = graded_take(piece, take, mode, jitter_ms=20, seed=3)
    check_against_key(results, key)


@pytest.mark.parametrize("mode", ["strict", "free"])
@pytest.mark.parametrize("take", ["perfect", "octave-down", "delayed"])
@pytest.mark.parametrize("piece", PIECES)
def test_take_with_every_note_split(piece, take, mode):
    # stage 4 merges the halves; the merged note is graded as one (still green, still on time).
    # (Mistakes takes: stage 4's merge can go wrong when the split lands next to a planted mistake.)
    for i in range(len(synth_notes(piece, take))):
        results, key = graded_take(piece, take, mode, split=[i])
        check_against_key(results, key)


def test_perfect_take_cents_are_near_zero():
    results, _ = graded_take("edge-cases", "perfect", "strict")
    assert all(abs(n["cents"]) <= 1 for n in results["notes"])
    assert all(abs(n["timing_ms"]) <= 1 for n in results["notes"])


# --------------------------------------------------------------------------- pitch verdicts


def test_pitch_thresholds_and_sang():
    exp = written("C4", "D4", "E4", "F4", "G4", "A4")
    r = by_id(run(exp, pitches("C4", "D4", "E4", "F4", "G4", "A4", cents=(0, 24, -26, 50, -51, 140))))
    got = [(n["status"], n["cents"], n["sang"]) for n in r.values()]
    assert got == [
        ("in_tune", 0, "C4"),
        ("in_tune", 24, "D4"),
        ("out_of_tune", -26, "E4"),  # negative = flat
        ("out_of_tune", 50, "F4"),  # exactly 50: still the written note
        ("wrong_note", -51, "F#4"),  # closer to F#4 than to G4; sung names use sharps
        ("wrong_note", 140, "A#4"),
    ]


def test_presets_move_the_in_tune_line():
    exp = written("C4", "D4", "E4", "F4")
    s = pitches("C4", "D4", "E4", "F4", cents=(30, 20, 0, 0))
    status = lambda preset: [n["status"] for n in run(exp, s, preset=preset)["notes"][:2]]
    assert status("default") == ["out_of_tune", "in_tune"]
    assert status("beginner") == ["in_tune", "in_tune"]  # +/-35
    assert status("advanced") == ["out_of_tune", "out_of_tune"]  # +/-15


def test_wrong_note_line_is_the_same_in_every_preset():
    exp = written("C4", "D4", "E4", "F4")
    s = pitches("C4", "D4", "E4", "F4", cents=(60, 0, 0, 0))
    assert all(run(exp, s, preset=p)["notes"][0]["status"] == "wrong_note" for p in ("default", "beginner", "advanced"))


def test_octave_shift_is_removed_from_cents_and_sang():
    exp = written("C4", "D4", "E4", "F4")
    s = sung((48.3, 0.0), (50.0, 1.0), (52.0, 2.0), (59.0, 3.0))  # an octave down; F4 sung as B3 (B4 - 12)
    res = run(exp, s)
    assert res["meta"]["octave_shift"] == -12
    assert [(n["status"], n["cents"], n["sang"]) for n in res["notes"]] == [
        ("out_of_tune", 30, "C4"), ("in_tune", 0, "D4"), ("in_tune", 0, "E4"), ("wrong_note", 600, "B4")]


def test_split_note_uses_merged_span_and_weighted_pitch():
    exp = written("C4", "D4")
    s = sung((60.0, 0.0, 0.3), (60.4, 0.32, 0.92), (62.0, 1.0))  # C4: 0.3 s at 0 cents + 0.6 s at +40
    res = grade(alignment([
        {"type": "match", "id": "m1-n0", "sids": ["s0", "s1"]},
        {"type": "match", "id": "m1-n1", "sids": ["s2"]},
    ]), exp, s, "strict")
    c4 = res["notes"][0]
    assert (c4["sung_start_sec"], c4["sung_end_sec"]) == (0.0, 0.92)
    assert c4["cents"] == round((0.3 * 0 + 0.6 * 40) / 0.9)  # 27: weighted, not the plain mean (20)
    assert c4["status"] == "out_of_tune"
    assert c4["timing_ms"] == 0  # timed from the first piece


def test_skipped_note_has_no_numbers():
    exp = written("C4", "D4", "E4", "F4")
    res = by_id(run(exp, sung((60, 0.0), (64, 2.0), (65, 3.0))))
    assert res["m1-n1"] == {
        "id": "m1-n1", "measure": 1, "name": "D4", "lyric": None, "status": "skipped", "cents": None,
        "sang": None, "timing": None, "timing_ms": None, "sung_start_sec": None, "sung_end_sec": None,
        "uncertain": False,
    }


def test_joined_note_gets_pitch_but_no_timing():
    exp = written("C4", "G4", "G4", "A4")
    s = sung((60, 0.0), (67.1, 1.0, 2.9), (69, 3.0))
    res = by_id(grade(alignment([
        {"type": "match", "id": "m1-n0", "sids": ["s0"]},
        {"type": "match", "id": "m1-n1", "sids": ["s1"]},
        {"type": "match", "id": "m1-n2", "sids": ["s1"], "joined": True},
        {"type": "match", "id": "m1-n3", "sids": ["s2"]},
    ]), exp, s, "strict"))
    assert (res["m1-n2"]["status"], res["m1-n2"]["cents"]) == ("in_tune", 10)
    assert (res["m1-n2"]["timing"], res["m1-n2"]["timing_ms"]) == (None, None)
    assert res["m1-n1"]["timing"] == "on_time"


def test_low_confidence_is_uncertain_but_still_judged():
    exp = written("C4", "D4", "E4")
    s = pitches("C4", "D4", "E4", cents=(40, 0, 0))
    s["notes"][0]["conf"] = 0.3
    n = run(exp, s)["notes"][0]
    assert (n["status"], n["uncertain"]) == ("out_of_tune", True)
    assert run(exp, pitches("C4", "D4", "E4"))["notes"][0]["uncertain"] is False


# --------------------------------------------------------------------------- timing verdicts


def test_strict_window_is_an_eighth_of_a_beat():
    exp = written("C4", "D4", "E4", "F4", "G4")  # 60 BPM: 1/8 beat = 125 ms
    r = run(exp, pitches("C4", "D4", "E4", "F4", "G4", late={1: 0.12, 2: 0.13, 3: -0.13}))
    assert [(n["timing"], n["timing_ms"]) for n in r["notes"]] == [
        ("on_time", 0), ("on_time", 120), ("late", 130), ("early", -130), ("on_time", 0)]


def test_strict_window_never_below_80_ms():
    exp = written("C4", "D4", "E4", "F4", "G4", bpm=240)  # 1/8 beat = 31 ms -> the 80 ms floor
    s = pitches("C4", "D4", "E4", "F4", "G4", spacing=0.25, late={1: 0.07, 2: 0.09})
    assert [n["timing"] for n in run(exp, s)["notes"]] == ["on_time", "on_time", "late", "on_time", "on_time"]


def test_presets_move_the_timing_window():
    exp = written("C4", "D4", "E4", "F4", "G4")  # 60 BPM
    s = pitches("C4", "D4", "E4", "F4", "G4", late={1: 0.2, 2: 0.07})
    timing = lambda preset: [n["timing"] for n in run(exp, s, preset=preset)["notes"][1:3]]
    assert timing("default") == ["late", "on_time"]
    assert timing("beginner") == ["on_time", "on_time"]  # 1/4 beat = 250 ms
    assert timing("advanced") == ["late", "late"]  # 1/16 beat = 62.5 ms (floor 50 ms)


def test_median_offset_is_removed():
    exp = written("C4", "D4", "E4", "F4", "G4")
    s = pitches("C4", "D4", "E4", "F4", "G4", late={k: 0.3 for k in range(5)} | {2: 0.5})
    res = run(exp, s)
    assert res["meta"]["timing_offset_ms"] == 300
    assert [(n["timing"], n["timing_ms"]) for n in res["notes"]][1:4] == [("on_time", 0), ("late", 200), ("on_time", 0)]


def slowing_take(n=14, bump=None):
    """A singer who slows down steadily (each gap 2% longer than the last: ~30% slower by the end);
    `bump` = (k, sec) moves one note. (Much stronger bends, e.g. 4% per note, aren't followed: see
    DECISIONS.md section 9.)"""
    names = ["C4", "D4", "E4", "F4", "G4", "A4", "B4"] * 2
    t, starts = 0.0, []
    for k in range(n):
        starts.append(t)
        t += 1.0 * 1.02 ** k
    if bump:
        starts[bump[0]] += bump[1]
    return written(*names[:n]), sung(*[(NAMES[names[k]], s, s + 0.5) for k, s in enumerate(starts)])


def test_free_mode_follows_gradual_slowing():
    exp, s = slowing_take()
    assert {n["timing"] for n in run(exp, s, "free")["notes"]} == {"on_time"}
    assert "late" in {n["timing"] for n in run(exp, s, "strict")["notes"]}  # against the score: late by the end


@pytest.mark.parametrize("k, sec, verdict", [(7, 0.25, "late"), (7, -0.25, "early"), (12, 0.25, "late")])
def test_free_mode_still_catches_one_note_while_slowing(k, sec, verdict):
    exp, s = slowing_take(bump=(k, sec))
    timing = [n["timing"] for n in run(exp, s, "free")["notes"]]
    assert timing[k] == verdict
    assert timing.count("on_time") == len(timing) - 1


def test_free_mode_two_neighbouring_mistakes_near_the_end():
    # The last note has only neighbours before it, two of them planted +/-200 ms: still on time.
    exp = written("C4", "D4", "E4", "F4", "G4", "A4")
    s = pitches("C4", "D4", "E4", "F4", "G4", "A4", late={3: 0.2, 4: -0.2})
    assert [n["timing"] for n in run(exp, s, "free")["notes"]] == ["on_time"] * 3 + ["late", "early", "on_time"]


def test_fermata_section_uses_the_pairs_own_offset():
    exp = written("C4", "D4", "E4", "F4", "G4", "A4", fermata_at=2)
    s = sung((60, 0.0), (62, 1.0), (64, 2.0), (65, 5.0), (67, 6.0), (69, 7.15))  # held E4 2 s longer
    al = alignment([{"type": "match", "id": f"m1-n{k}", "sids": [f"s{k}"],
                     "time_offset_sec": 0.0 if k < 3 else 2.0} for k in range(6)])
    for mode in ("strict", "free"):
        assert [n["timing"] for n in grade(al, exp, s, mode)["notes"]] == ["on_time"] * 5 + ["late"]


def test_fermata_through_stage_4():
    exp = written("C4", "D4", "E4", "F4", "G4", "A4", fermata_at=2)
    s = sung((60, 0.0), (62, 1.0), (64, 2.0, 4.8), (65, 5.0), (67, 6.0), (69, 7.0))
    for mode in ("strict", "free"):
        assert {n["timing"] for n in run(exp, s, mode)["notes"]} == {"on_time"}


# --------------------------------------------------------------------------- extras, meta, counts, shape


def test_extras_near_notes_and_rests():
    exp = written("C4", "D4", None, "E4", "F4")
    s = sung((60, 0.0), (62, 1.0), (71, 2.1, 2.6), (64, 3.0), (65, 4.0), (72, 4.5, 4.9))
    res = run(exp, s)
    assert [(x["sid"], x["near_id"], x["sang"], x["during_rest"]) for x in res["extras"]] == [
        ("s2", "m1-n2", "B4", True), ("s5", "m1-n4", "C5", False)]
    assert (res["extras"][0]["start_sec"], res["extras"][0]["end_sec"]) == (2.1, 2.6)


def test_extra_sang_after_octave_shift():
    exp = written("C4", "D4", "E4", "F4")
    s = sung((48, 0.0), (50, 1.0), (52, 2.0), (59, 2.5, 2.8), (53, 3.0))
    assert run(exp, s)["extras"][0]["sang"] == "B4"


def test_rests_are_not_in_notes_and_order_is_the_scores():
    exp = written("C4", None, "D4", None, "E4")
    res = run(exp, sung((60, 0.0), (62, 2.0), (64, 4.0)))
    assert [n["id"] for n in res["notes"]] == ["m1-n0", "m1-n2", "m1-n4"]


def test_meta_and_counts():
    exp = written("C4", "D4", "E4", "F4", "G4", "A4")
    # C4 30 cents sharp (in tune for beginner), D4 sung as E4, E4 fine, F4 skipped, G4 low confidence,
    # A4 0.3 s late (beginner window: 250 ms), one extra
    s = sung((60.3, 0.0), (64, 1.0), (64, 2.0), (67, 4.0), (69, 5.3), (72, 5.6, 5.8))
    s["notes"][3]["conf"] = 0.2
    al = alignment([
        {"type": "match", "id": "m1-n0", "sids": ["s0"]},
        {"type": "match", "id": "m1-n1", "sids": ["s1"]},
        {"type": "match", "id": "m1-n2", "sids": ["s2"]},
        {"type": "skipped", "id": "m1-n3", "sids": []},
        {"type": "match", "id": "m1-n4", "sids": ["s3"]},
        {"type": "match", "id": "m1-n5", "sids": ["s4"]},
        {"type": "extra", "id": None, "sids": ["s5"], "near_id": "m1-n5"},
    ], offset=0.012)
    res = grade(al, exp, s, "strict", "beginner")
    assert res["meta"] == {"title": "Test", "mode": "strict", "preset": "beginner", "tempo_bpm": 60.0,
                           "octave_shift": 0, "timing_offset_ms": 12}
    assert res["counts"] == {"notes": 6, "in_tune": 4, "out_of_tune": 0, "wrong_note": 1, "skipped": 1,
                             "extra": 1, "early": 0, "late": 1, "uncertain": 1}


def test_shape_matches_the_contract_sample():
    sample = json.loads((REPO / "contracts/results.sample.json").read_text())
    results, _ = graded_take("c-major-scale", "mistakes", "strict")
    assert set(results) == set(sample)
    assert set(results["meta"]) == set(sample["meta"])
    assert set(results["counts"]) == set(sample["counts"])
    assert all(set(n) == set(sample["notes"][0]) for n in results["notes"])
    assert all(set(x) == set(sample["extras"][0]) for x in results["extras"])
    json.dumps(results, allow_nan=False)  # no NaN / Infinity


def test_reproduces_the_contract_sample_verdicts():
    # contracts/ samples are what /analyze returns for c-major-scale/mistakes (strict)
    sample = json.loads((REPO / "contracts/results.sample.json").read_text())
    results, _ = graded_take("c-major-scale", "mistakes", "strict")
    fields = ("id", "measure", "name", "status", "sang", "timing")
    assert [[n[f] for f in fields] for n in results["notes"]] == [[n[f] for f in fields] for n in sample["notes"]]
    assert results["counts"] == sample["counts"]
    assert [x["near_id"] for x in results["extras"]] == [x["near_id"] for x in sample["extras"]]


def test_unknown_mode_or_preset():
    exp = written("C4", "D4", "E4")
    s = pitches("C4", "D4", "E4")
    al = align(exp, s)
    for mode, preset in (("loose", "default"), ("strict", "expert")):
        with pytest.raises(AnalysisError) as e:
            grade(al, exp, s, mode, preset)
        assert (e.value.code, e.value.status) == ("invalid_input", 400)


def test_midi_name():
    assert [midi_name(m) for m in (60, 61.4, 70.6, 59.5, 83)] == ["C4", "C#4", "B4", "C4", "B5"]


# --------------------------------------------------------------------------- part 2: the score


def scored(notes, n_extras=0):
    """Score from hand-made results.notes entries: ("in_tune"|..., cents, timing, uncertain)."""
    from app.stages.grade import _score
    return _score([{"status": s, "cents": c, "timing": t, "uncertain": u} for s, c, t, u in notes], n_extras)


@pytest.mark.parametrize("take", ["perfect", "octave-down", "delayed"])
@pytest.mark.parametrize("piece", PIECES)
def test_clean_takes_score_100(piece, take):
    for mode in ("strict", "free"):
        results, _ = graded_take(piece, take, mode)
        assert results["score"] == {"total": 100, "pitch": 100, "intonation": 100, "rhythm": 100, "completeness": 100}


def test_mistakes_take_matches_the_contract_sample_parts():
    # pitch 6/8, rhythm 5/7 matched notes on time, completeness 7/8 - 5 for the extra: as in the sample
    sample = json.loads((REPO / "contracts/results.sample.json").read_text())["score"]
    score = graded_take("c-major-scale", "mistakes", "strict")[0]["score"]
    assert (score["pitch"], score["rhythm"], score["completeness"]) == (sample["pitch"], sample["rhythm"], sample["completeness"])
    assert score["intonation"] == 88  # |cents| 0,0,35,0,0,0 on the 6 right notes -> 100 - 2 x 5.83


def test_score_formulas():
    s = scored([
        ("in_tune", 10, "on_time", False),
        ("out_of_tune", -30, "late", False),
        ("wrong_note", 200, "on_time", False),
        ("skipped", None, None, False),
    ], n_extras=1)
    # pitch 2/4 = 50; intonation 100 - 2 x 20 = 60; rhythm 2/3 = 66.7; completeness 3/4 - 5 = 70
    # total 0.5 x 50 + 0.25 x 60 + 0.15 x 66.67 + 0.1 x 70 = 57
    assert s == {"total": 57, "pitch": 50, "intonation": 60, "rhythm": 67, "completeness": 70}


def test_joined_notes_count_for_pitch_but_not_rhythm():
    s = scored([("in_tune", 0, "on_time", False), ("in_tune", 0, None, False), ("in_tune", 0, "late", False)])
    assert (s["pitch"], s["rhythm"]) == (100, 50)


def test_uncertain_notes_are_left_out_of_the_score():
    sure = [("in_tune", 0, "on_time", False)] * 3
    assert scored(sure + [("wrong_note", 300, "late", True), ("skipped", None, None, True)]) == scored(sure)


def test_low_confidence_extra_costs_nothing():
    exp = written("C4", "D4", "E4", "F4")
    s = sung((60, 0.0), (62, 1.0), (71, 1.5, 1.8), (64, 2.0), (65, 3.0))
    assert run(exp, s)["score"]["completeness"] == 95
    s["notes"][2]["conf"] = 0.2
    res = run(exp, s)
    assert res["score"]["completeness"] == 100 and res["counts"]["extra"] == 1  # still shown, just not penalized


def test_scores_stay_within_0_and_100():
    s = scored([("skipped", None, None, False), ("in_tune", 0, "on_time", False)], n_extras=40)
    assert s["completeness"] == 0
    s = scored([("out_of_tune", 50, "on_time", False)])
    assert s["intonation"] == 0
    assert all(isinstance(v, int) and 0 <= v <= 100 for v in s.values())


def test_nothing_to_judge_scores_zero():
    zero = {"total": 0, "pitch": 0, "intonation": 0, "rhythm": 0, "completeness": 0}
    assert scored([]) == zero
    assert scored([("in_tune", 0, "on_time", True)]) == zero
    assert scored([("skipped", None, None, False)]) == zero


def test_rounding_is_half_up():
    # completeness 7/8 - 5 = 82.5 -> 83 (Python's round() would give 82)
    s = scored([("in_tune", 0, "on_time", False)] * 7 + [("skipped", None, None, False)], n_extras=1)
    assert s["completeness"] == 83


def test_weights_sum_to_one():
    from app.stages.grade import WEIGHTS
    assert abs(sum(WEIGHTS.values()) - 1) < 1e-9


# --------------------------------------------------------------------------- part 3: patterns


def in_bars(expected, per_bar):
    """Spread written() notes over bars of `per_bar` notes (ids m1-n0.., m2-n0..)."""
    for k, n in enumerate(expected["notes"]):
        n["measure"], n["index"] = k // per_bar + 1, k % per_bar
        n["id"] = f"m{n['measure']}-n{n['index']}"
        n["render_ids"] = [n["id"]]
    return expected


def patterns(expected, sung_notes, mode="strict"):
    return run(expected, sung_notes, mode)["patterns"]


SCALE = ("C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5", "D4")


def test_clean_take_patterns_are_empty():
    results, _ = graded_take("edge-cases", "perfect", "strict")
    assert results["patterns"] == {
        "worst_measures": [], "drift_cents": {"first_third": 0, "last_third": 0}, "high_notes_flat": False,
        "timing_tendency": "steady", "shaky_long_notes": [], "errors_after_leaps": []}


def test_patterns_match_the_contract_sample_fields():
    sample = json.loads((REPO / "contracts/results.sample.json").read_text())["patterns"]
    got = graded_take("c-major-scale", "mistakes", "strict")[0]["patterns"]
    assert set(got) == set(sample) and set(got["drift_cents"]) == set(sample["drift_cents"])
    assert got["worst_measures"] == sample["worst_measures"] == [2, 1]
    json.dumps(got, allow_nan=False)


def test_worst_measures_most_problems_first_earlier_bar_on_ties_at_most_3():
    exp = in_bars(written("C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"), per_bar=2)
    # bar 1: C4 flat (1); bar 2: F4 wrong + late (2); bar 3: nothing; bar 4: C5 flat (1) + an extra (1)
    s = sung((59.6, 0.0), (62, 1.0), (64, 2.0), (66, 3.3), (67, 4.0), (69, 5.0), (71, 6.0), (72.3, 7.0),
             (76, 7.5, 7.8))
    assert patterns(exp, s)["worst_measures"] == [2, 4, 1]
    exp5 = in_bars(written("C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"), per_bar=1)
    s5 = sung(*[(m + 0.4, k) for k, m in enumerate((60, 62, 64, 65, 67, 69, 71, 72))])  # all 40 c sharp
    assert patterns(exp5, s5)["worst_measures"] == [1, 2, 3]  # ties: earlier bars, only 3


def test_worst_measures_ignore_uncertain_notes():
    exp = in_bars(written("C4", "D4", "E4", "F4"), per_bar=2)
    s = sung((60, 0.0), (62, 1.0), (64, 2.0), (68, 3.0))
    s["notes"][3]["conf"] = 0.2
    assert patterns(exp, s)["worst_measures"] == []


def test_drift_first_third_vs_last_third():
    exp = written(*SCALE)
    s = pitches(*SCALE, cents=(5, 0, 1, 0, 0, -20, -30, -40, -20))
    assert patterns(exp, s)["drift_cents"] == {"first_third": 2, "last_third": -30}


def test_drift_ignores_wrong_notes_and_is_null_without_right_notes():
    exp = written(*SCALE)
    s = pitches(*SCALE, cents=(300, 300, 300, 0, 0, 0, 0, -10, 0))
    assert patterns(exp, s)["drift_cents"] == {"first_third": None, "last_third": -3}
    assert patterns(written("C4", "D4"), pitches("C4", "D4"))["drift_cents"] == {"first_third": None, "last_third": None}


def test_high_notes_flat():
    exp = written(*SCALE)  # median written pitch F4/G4 split: C4 D4 E4 D4 low, A4 B4 C5 high
    flat_top = (0, 0, 0, 0, 0, -25, -30, -35, 0)
    assert patterns(exp, pitches(*SCALE, cents=flat_top))["high_notes_flat"] is True
    small_gap = (0, 0, 0, 0, 0, -8, -10, -12, 0)  # flat, but less than 10 cents: not a pattern
    assert patterns(exp, pitches(*SCALE, cents=small_gap))["high_notes_flat"] is False
    flat_everywhere = (-30,) * 9  # no difference between high and low
    assert patterns(exp, pitches(*SCALE, cents=flat_everywhere))["high_notes_flat"] is False
    few = written("C4", "D4", "A4", "B4")  # fewer than 3 notes a side
    assert patterns(few, pitches("C4", "D4", "A4", "B4", cents=(0, 0, -40, -40)))["high_notes_flat"] is False


def steady_take(n, sec_per_beat, names=SCALE * 2):
    exp = written(*names[:n])
    return exp, sung(*[(NAMES[names[k]], k * sec_per_beat, k * sec_per_beat + 0.5 * sec_per_beat) for k in range(n)])


def test_timing_tendency_strict_against_the_scores_tempo():
    exp, faster = steady_take(12, 0.85)  # 15% faster than written all the way through
    assert patterns(exp, faster, "strict")["timing_tendency"] == "rushing"
    exp, slower = steady_take(12, 1.15)
    assert patterns(exp, slower, "strict")["timing_tendency"] == "dragging"
    exp, close = steady_take(12, 1.05)  # within 8%
    assert patterns(exp, close, "strict")["timing_tendency"] == "steady"


def test_timing_tendency_free_mode_only_the_change_within_the_take():
    exp, faster = steady_take(12, 0.85)  # a steady tempo of their own is fine in free mode
    assert patterns(exp, faster, "free")["timing_tendency"] == "steady"
    exp, slowing = slowing_take()  # each gap 2% longer: the last third ~20% slower than the first
    assert patterns(exp, slowing, "free")["timing_tendency"] == "dragging"
    s = {"notes": [dict(n) for n in slowing["notes"]]}
    end = s["notes"][-1]["start_sec"]
    for n in s["notes"]:  # the same take mirrored in time: speeding up
        n["start_sec"], n["end_sec"] = round(end - n["start_sec"], 6), round(end - n["start_sec"] + 0.5, 6)
    s["notes"].reverse()
    for k, n in enumerate(s["notes"]):
        n["sid"], n["midi"] = f"s{k}", float(exp["notes"][k]["midi"])
    assert patterns(exp, s, "free")["timing_tendency"] == "rushing"


def test_timing_tendency_needs_enough_notes():
    exp, faster = steady_take(6, 0.8)
    assert patterns(exp, faster, "free")["timing_tendency"] == "steady"


def test_shaky_long_notes():
    exp = written("C4", "D4", "E4", "F4", "G4")
    exp["notes"][1]["duration_beats"], exp["notes"][1]["duration_sec"] = 0.5, 0.5  # D4: short
    s = pitches("C4", "D4", "E4", "F4", "G4", cents=(0, 0, 0, 300, 0))
    for k, cents in enumerate((50, 50, 30, 60, 41)):
        s["notes"][k]["stability_cents"] = cents
    # C4 long + shaky; D4 short; E4 steady enough; F4 wrong note (not a "right note sung shakily"); G4 just over
    assert patterns(exp, s)["shaky_long_notes"] == ["m1-n0", "m1-n4"]


def test_errors_after_leaps():
    exp = written("C4", "A4", "B4", "E4", "F4", "C5", "C4")
    # A4 flat after a 9-semitone leap: yes; B4 flat after a step: no; E4 in tune after a leap: no;
    # C5 wrong after a 7-semitone leap: yes; C4 skipped after a leap: no (not a pitch error)
    s = sung((60, 0.0), (68.7, 1.0), (70.7, 2.0), (64, 3.0), (65, 4.0), (74, 5.0))
    assert patterns(exp, s)["errors_after_leaps"] == ["m1-n1", "m1-n5"]


def test_grading_the_contract_samples_gives_the_results_sample():
    # contracts/ is one consistent run: stage 5 on the expected_notes, sung_notes and alignment samples
    # must give exactly results.sample.json (so the samples can't drift apart)
    load = lambda name: json.loads((REPO / f"contracts/{name}.sample.json").read_text())
    want = load("results")
    got = grade(load("alignment"), load("expected_notes"), load("sung_notes"), want["meta"]["mode"], want["meta"]["preset"])
    assert got == want
