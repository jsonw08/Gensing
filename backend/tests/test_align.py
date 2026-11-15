"""Stage 4 (alignment) tests. Part 3a: core table in strict mode + near_id."""

import json
from pathlib import Path

import pytest
from synth_sung import PIECES, load_take, score_path, synth_notes

from app.errors import AnalysisError
from app.stages.align import align
from app.stages.score import parse_score

REPO = Path(__file__).resolve().parents[2]
NAMES = {"C4": 60, "C#4": 61, "D4": 62, "D#4": 63, "E4": 64, "F4": 65, "G4": 67, "A4": 69, "C6": 84}


# --------------------------------------------------------------------------- tiny builders (60 BPM: 1 beat = 1 s)


def written(*notes):
    """written("C4", "D4", None, "E4"): one beat each, None = rest. All in bar 1, ids m1-n0, m1-n1, ..."""
    out = []
    for i, name in enumerate(notes):
        out.append({
            "id": f"m1-n{i}", "measure": 1, "index": i, "is_rest": name is None,
            "midi": None if name is None else NAMES[name], "name": name,
            "onset_beats": float(i), "duration_beats": 1.0, "onset_sec": float(i), "duration_sec": 1.0,
            "lyric": None, "render_ids": [f"m1-n{i}"],
        })
    return {"title": None, "tempo_bpm": 60.0, "beat_unit": "quarter", "notes": out}


def sung(*notes):
    """sung(("C4", 0.0), ("E4", 2.0)): (name or midi, start_sec); each lasts 0.8 s."""
    out = []
    for k, (pitch, start) in enumerate(notes):
        midi = NAMES[pitch] if isinstance(pitch, str) else pitch
        out.append({"sid": f"s{k}", "start_sec": start, "end_sec": start + 0.8, "midi": float(midi),
                    "stability_cents": 20.0, "conf": 0.9})
    return {"notes": out}


def summary(alignment):
    return [(p["type"], p["id"], p["sids"]) for p in alignment["pairs"]]


# --------------------------------------------------------------------------- the method


def test_worked_example_c_d_e_vs_c_e():
    # docs/ALIGNMENT_EXPLAINED.md: written C D E, sung C E -> match, skipped, match, total 3
    result = align(written("C4", "D4", "E4"), sung(("C4", 0.0), ("E4", 2.0)))
    assert summary(result) == [("match", "m1-n0", ["s0"]), ("skipped", "m1-n1", []), ("match", "m1-n2", ["s1"])]
    assert result["total_cost"] == 3.0
    assert (result["octave_shift"], result["tempo_scale"]) == (0, 1.0)


def test_wrong_note_is_a_match_not_skip_plus_extra():
    result = align(written("C4", "D4", "E4"), sung(("C4", 0.0), ("D#4", 1.0), ("E4", 2.0)))
    assert summary(result)[1] == ("match", "m1-n1", ["s1"])
    assert result["pairs"][1]["cost"] == 1.0  # 1 semitone, on time


def test_cents_count_as_fractional_semitones():
    result = align(written("C4"), sung((60.35, 0.0)))
    assert result["pairs"][0]["cost"] == pytest.approx(0.35)


def test_exact_tie_prefers_match():
    # Pitch capped at 4 + 0.5 x 4 beats late = 6 = skip + extra. A tie: "you sang it, badly" wins.
    result = align(written("C4"), sung(("E4", 4.0)))
    assert summary(result) == [("match", "m1-n0", ["s0"])]


@pytest.mark.parametrize("sung_at,skipped,matched", [(0.0, "m1-n1", "m1-n0"), (1.0, "m1-n0", "m1-n1")])
def test_timing_picks_the_right_one_of_two_identical_notes(sung_at, skipped, matched):
    # Written G G A, one G sung: pitch can't tell which G it was, timing must (both directions,
    # so the tie rule alone can't make this pass)
    result = align(written("G4", "G4", "A4"), sung(("G4", sung_at), ("A4", 2.0)))
    by_id = {p["id"]: p["type"] for p in result["pairs"]}
    assert (by_id[skipped], by_id[matched], by_id["m1-n2"]) == ("skipped", "match", "match")


# --------------------------------------------------------------------------- extras and near_id


def test_extra_inside_a_note_points_at_that_note():
    result = align(written("C4", "D4", "E4"), sung(("C4", 0.0), ("C6", 1.4), ("D4", 1.0), ("E4", 2.0)))
    extras = [p for p in result["pairs"] if p["type"] == "extra"]
    assert [(p["sids"], p["near_id"]) for p in extras] == [(["s1"], "m1-n1")]


def test_extra_during_a_rest_points_at_the_rest():
    result = align(written("C4", None, "E4"), sung(("C4", 0.0), ("G4", 1.3), ("E4", 2.0)))
    assert summary(result) == [("match", "m1-n0", ["s0"]), ("extra", None, ["s1"]), ("match", "m1-n2", ["s2"])]
    assert result["pairs"][1]["near_id"] == "m1-n1"  # the rest


def test_extra_after_the_last_note_points_at_nearest_onset():
    result = align(written("C4", "D4"), sung(("C4", 0.0), ("D4", 1.0), ("G4", 3.5)))
    assert result["pairs"][-1]["type"] == "extra"
    assert result["pairs"][-1]["near_id"] == "m1-n1"


def test_only_extras_have_near_id():
    result = align(written("C4", "D4"), sung(("C4", 0.0), ("G4", 0.5), ("D4", 1.0)))
    for p in result["pairs"]:
        assert ("near_id" in p) == (p["type"] == "extra")


# --------------------------------------------------------------------------- invariants and contract


def check_invariants(expected, sung_notes, result):
    written_ids = [n["id"] for n in expected["notes"] if not n["is_rest"]]
    rest_ids = {n["id"] for n in expected["notes"] if n["is_rest"]}
    # every written note exactly once (match or skipped), in score order; rests never
    assert [p["id"] for p in result["pairs"] if p["type"] != "extra"] == written_ids
    assert not rest_ids & {p["id"] for p in result["pairs"]}
    # every sung note exactly once (in a match or as an extra), in time order; a joined pair shares
    # its neighbour's sung note, so it isn't counted again
    assert [s for p in result["pairs"] if not p.get("joined") for s in p["sids"]] == [s["sid"] for s in sung_notes["notes"]]
    for p in result["pairs"]:
        if p.get("joined"):
            assert p["type"] == "match" and len(p["sids"]) == 1
    # shapes
    for p in result["pairs"]:
        optional = ({"near_id"} if p["type"] == "extra" else set()) | ({"joined"} if p.get("joined") else set())
        assert set(p) == {"type", "id", "sids", "cost"} | optional
        assert len(p["sids"]) >= 1 if p["type"] == "match" else len(p["sids"]) == {"skipped": 0, "extra": 1}[p["type"]]
    assert result["total_cost"] == pytest.approx(sum(p["cost"] for p in result["pairs"]), abs=1e-3)
    json.loads(json.dumps(result), parse_constant=lambda c: pytest.fail(c))


def test_contract_samples():
    expected = json.loads((REPO / "contracts/expected_notes.sample.json").read_text())
    sung_notes = json.loads((REPO / "contracts/sung_notes.sample.json").read_text())
    sample = json.loads((REPO / "contracts/alignment.sample.json").read_text())
    result = align(expected, sung_notes)
    check_invariants(expected, sung_notes, result)

    def strip(pairs):  # costs aside: the sample predates the timing term's exact numbers
        return [(p["type"], p["id"], p["sids"], p.get("near_id")) for p in pairs]

    assert strip(result["pairs"]) == strip(sample["pairs"])
    assert set(result) == set(sample)


# --------------------------------------------------------------------------- synth takes


@pytest.mark.parametrize("piece", PIECES)
@pytest.mark.parametrize("take", ["perfect", "delayed"])
def test_clean_takes_are_all_matches(piece, take):
    expected = parse_score(score_path(piece))
    sung_notes, _ = load_take(piece, take)
    result = align(expected, sung_notes)
    check_invariants(expected, sung_notes, result)
    assert {p["type"] for p in result["pairs"]} == {"match"}


@pytest.mark.parametrize("piece", PIECES)
def test_mistakes_take_finds_the_planted_skip_and_extra(piece):
    expected = parse_score(score_path(piece))
    sung_notes, answer = load_take(piece, "mistakes")
    result = align(expected, sung_notes)
    check_invariants(expected, sung_notes, result)

    skipped = [p["id"] for p in result["pairs"] if p["type"] == "skipped"]
    assert skipped == [i for i, v in answer["notes"].items() if v["status"] == "skipped"]
    extras = [p["near_id"] for p in result["pairs"] if p["type"] == "extra"]
    assert extras == [e["near_id"] for e in answer["extras"]]
    wrong = next(i for i, v in answer["notes"].items() if v["status"] == "wrong_note")
    assert next(p for p in result["pairs"] if p["id"] == wrong)["type"] == "match"


@pytest.mark.parametrize("piece", PIECES)
def test_timing_jitter_changes_nothing(piece):
    expected = parse_score(score_path(piece))
    sung_notes, _ = load_take(piece, "perfect", jitter_ms=20, seed=3)
    assert {p["type"] for p in align(expected, sung_notes)["pairs"]} == {"match"}


# --------------------------------------------------------------------------- modes and edge cases


def test_unknown_mode_is_rejected():
    with pytest.raises(AnalysisError) as err:
        align(written("C4"), sung(("C4", 0.0)), mode="fast")
    assert (err.value.code, err.value.stage, err.value.status) == ("invalid_input", "align", 400)


def test_nothing_sung_means_everything_skipped():
    result = align(written("C4", "D4"), {"notes": []})
    assert summary(result) == [("skipped", "m1-n0", []), ("skipped", "m1-n1", [])]
    assert result["total_cost"] == 6.0


# --------------------------------------------------------------------------- time offset (uploads, recording delay)


def shifted(sung_notes, sec, cough_at=None):
    """Move every sung note by `sec` (an upload's lead-in silence); optionally add a cough first."""
    notes = [dict(n, start_sec=n["start_sec"] + sec, end_sec=n["end_sec"] + sec) for n in sung_notes["notes"]]
    if cough_at is not None:
        notes.insert(0, {"start_sec": cough_at, "end_sec": cough_at + 0.15, "midi": 50.3,
                         "stability_cents": 80.0, "conf": 0.6})
    return {"notes": [dict(n, sid=f"s{k}") for k, n in enumerate(notes)]}


@pytest.mark.parametrize("piece", PIECES)
def test_upload_with_silence_before_singing(piece):
    expected = parse_score(score_path(piece))
    sung_notes = shifted(load_take(piece, "perfect")[0], 1.5)
    result = align(expected, sung_notes)
    check_invariants(expected, sung_notes, result)
    assert result["time_offset_sec"] == pytest.approx(1.5, abs=0.001)
    assert {p["type"] for p in result["pairs"]} == {"match"}
    assert max(p["cost"] for p in result["pairs"]) < 0.01  # timing lines up after the shift


@pytest.mark.parametrize("piece", PIECES)
def test_cough_before_singing_is_an_extra_and_does_not_move_the_offset(piece):
    expected = parse_score(score_path(piece))
    sung_notes = shifted(load_take(piece, "perfect")[0], 1.5, cough_at=0.4)
    result = align(expected, sung_notes)
    check_invariants(expected, sung_notes, result)
    assert result["time_offset_sec"] == pytest.approx(1.5, abs=0.001)
    assert summary(result)[0] == ("extra", None, ["s0"])
    assert [p["type"] for p in result["pairs"][1:]] == ["match"] * (len(result["pairs"]) - 1)


@pytest.mark.parametrize("piece", PIECES)
def test_shifted_mistakes_take_aligns_like_the_unshifted_one(piece):
    expected = parse_score(score_path(piece))
    plain, _ = load_take(piece, "mistakes")
    a, b = align(expected, plain), align(expected, shifted(plain, 1.5))
    assert summary(a) == summary(b)
    assert [p.get("near_id") for p in a["pairs"]] == [p.get("near_id") for p in b["pairs"]]
    assert b["time_offset_sec"] == pytest.approx(a["time_offset_sec"] + 1.5, abs=0.001)


def test_score_that_opens_with_rests():
    # Schubert-like: 8 beats of piano intro (voice rests), singer's file starts singing at 0.8 s.
    # The old "first sung note = beat 1" rule would have lined them up with the intro.
    expected = written(*[None] * 8, "C4", "D4", "E4", "F4")
    sung_notes = sung(("C4", 0.8), ("D4", 1.8), ("E4", 2.8), ("F4", 3.8))
    result = align(expected, sung_notes)
    assert result["time_offset_sec"] == pytest.approx(0.8 - 8.0)
    assert [p["type"] for p in result["pairs"]] == ["match"] * 4
    assert max(p["cost"] for p in result["pairs"]) < 1e-6


@pytest.mark.parametrize("piece", PIECES)
def test_recording_delay_is_measured(piece):
    expected = parse_score(score_path(piece))
    sung_notes, answer = load_take(piece, "delayed")
    result = align(expected, sung_notes)
    assert result["time_offset_sec"] * 1000 == pytest.approx(answer["expect"]["timing_offset_ms"], abs=1)


def test_too_few_pairs_to_trust_means_no_offset():
    result = align(written("C4", "D4"), sung(("C4", 5.0), ("D4", 6.0)))
    assert result["time_offset_sec"] == 0.0
    assert [p["type"] for p in result["pairs"]] == ["match", "match"]  # still paired, just not shifted


def test_wrong_notes_do_not_vote():
    # Three near-right notes 1.0 s late, four wrong notes (3 semitones off) 3.0 s late. If the wrong
    # ones voted they'd be the majority and the median would be 3.0; only near-right pairs count.
    expected = written("C4", "D4", "E4", "F4", "G4", "A4", "C6")
    sung_notes = sung(("C4", 1.0), ("D4", 2.0), ("E4", 3.0), (68, 6.0), (70, 7.0), (72, 8.0), (87, 9.0))
    # (How the deliberately odd wrong notes get paired in the final pass isn't the point here.)
    assert align(expected, sung_notes)["time_offset_sec"] == pytest.approx(1.0)


# --------------------------------------------------------------------------- octave shift (3b)


def transposed(sung_notes, semitones):
    return {"notes": [dict(n, midi=n["midi"] + semitones) for n in sung_notes["notes"]]}


@pytest.mark.parametrize("piece", PIECES)
def test_octave_down_take(piece):
    expected = parse_score(score_path(piece))
    sung_notes, answer = load_take(piece, "octave-down")
    result = align(expected, sung_notes)
    check_invariants(expected, sung_notes, result)
    assert result["octave_shift"] == answer["expect"]["octave_shift"] == -12
    assert {p["type"] for p in result["pairs"]} == {"match"}
    assert max(p["cost"] for p in result["pairs"]) < 0.01


@pytest.mark.parametrize("piece", PIECES)
@pytest.mark.parametrize("take", ["perfect", "mistakes", "delayed"])
def test_same_octave_takes_have_no_shift(piece, take):
    result = align(parse_score(score_path(piece)), load_take(piece, take)[0])
    assert result["octave_shift"] == 0


@pytest.mark.parametrize("piece", PIECES)
@pytest.mark.parametrize("shift", [-24, -12, 12, 24])
def test_mistakes_take_in_another_octave_aligns_the_same(piece, shift):
    expected = parse_score(score_path(piece))
    plain, _ = load_take(piece, "mistakes")
    a, b = align(expected, plain), align(expected, transposed(plain, shift))
    assert b["octave_shift"] == shift
    assert summary(a) == summary(b)
    assert [p.get("near_id") for p in a["pairs"]] == [p.get("near_id") for p in b["pairs"]]
    assert [p["cost"] for p in a["pairs"]] == pytest.approx([p["cost"] for p in b["pairs"]])


@pytest.mark.parametrize("piece", PIECES)
def test_octave_down_and_upload_silence_together(piece):
    expected = parse_score(score_path(piece))
    sung_notes = shifted(load_take(piece, "octave-down")[0], 1.5)
    result = align(expected, sung_notes)
    assert (result["octave_shift"], result["time_offset_sec"]) == (-12, pytest.approx(1.5, abs=0.001))
    assert {p["type"] for p in result["pairs"]} == {"match"}


def test_tie_between_shifts_picks_the_smallest():
    # Everything a tritone (6 semitones) low: 0 and -12 fit equally badly -> no shift claimed
    expected = written("C4", "D4", "E4", "F4")
    sung_notes = sung((54, 0.0), (56, 1.0), (58, 2.0), (59, 3.0))
    assert align(expected, sung_notes)["octave_shift"] == 0


def test_nothing_sung_has_no_shift():
    assert align(written("C4", "D4"), {"notes": []})["octave_shift"] == 0


# --------------------------------------------------------------------------- split-note merge (3c)


def notes_at(*notes):
    """notes_at((midi, start, end), ...): sung notes with explicit ends (pieces of split notes)."""
    return {"notes": [{"sid": f"s{k}", "start_sec": a, "end_sec": b, "midi": float(m), "stability_cents": 20.0,
                       "conf": 0.9} for k, (m, a, b) in enumerate(notes)]}


def by_id(result):
    return {p["id"]: p for p in result["pairs"] if p["id"]}


@pytest.mark.parametrize("piece", PIECES)
def test_split_note_merges_back_into_one_match(piece):
    expected = parse_score(score_path(piece))
    sung_notes, _ = load_take(piece, "perfect", split=[3])
    result = align(expected, sung_notes)
    check_invariants(expected, sung_notes, result)
    assert {p["type"] for p in result["pairs"]} == {"match"}
    assert [p["sids"] for p in result["pairs"] if len(p["sids"]) > 1] == [["s3", "s4"]]


def test_note_cut_into_three_pieces():
    sung_notes = notes_at((60, 0.0, 0.3), (60, 0.32, 0.6), (60, 0.62, 0.9), (62, 1.0, 1.8), (64, 2.0, 2.8))
    result = align(written("C4", "D4", "E4"), sung_notes)
    assert summary(result) == [("match", "m1-n0", ["s0", "s1", "s2"]), ("match", "m1-n1", ["s3"]),
                               ("match", "m1-n2", ["s4"])]


def test_vibrato_halves_merge():
    # Two short pieces of one vibrato note, one caught high (+45 c) and one low (-45 c): 0.9 semitone apart
    sung_notes = notes_at((60.45, 0.0, 0.35), (59.55, 0.37, 0.8), (62, 1.0, 1.8), (64, 2.0, 2.8))
    result = align(written("C4", "D4", "E4"), sung_notes)
    assert by_id(result)["m1-n0"]["sids"] == ["s0", "s1"] and len(result["pairs"]) == 3


def test_scoop_into_a_note_merges():
    sung_notes = notes_at((59.2, 0.0, 0.1), (60, 0.12, 0.8), (62, 1.0, 1.8), (64, 2.0, 2.8))
    result = align(written("C4", "D4", "E4"), sung_notes)
    assert by_id(result)["m1-n0"]["sids"] == ["s0", "s1"] and len(result["pairs"]) == 3


def test_piece_joins_the_note_it_is_closest_to():
    # Written C4 C#4 D4. A piece at 60.9 right after the C is within 1 semitone of it, but it's really
    # the start of the C#: it joins the C#, not the C.
    sung_notes = notes_at((60, 0.0, 0.6), (60.9, 0.62, 0.8), (61, 1.0, 1.6), (62, 2.0, 2.6))
    result = align(written("C4", "C#4", "D4"), sung_notes)
    assert by_id(result)["m1-n0"]["sids"] == ["s0"]
    assert by_id(result)["m1-n1"]["sids"] == ["s1", "s2"]


def test_piece_closer_to_the_next_note_but_too_far_from_it_stays_extra():
    # Same, but the C# comes 0.3 s after the piece: too big a gap to join the C#, and the guard keeps it
    # out of the C (it's closer to C# than to C)
    sung_notes = notes_at((60, 0.0, 0.6), (60.9, 0.62, 0.8), (61, 1.1, 1.6), (62, 2.0, 2.6))
    result = align(written("C4", "C#4", "D4"), sung_notes)
    assert [p["type"] for p in result["pairs"]] == ["match", "extra", "match", "match"]


def test_same_note_sung_again_after_a_real_gap_stays_extra():
    sung_notes = notes_at((60, 0.0, 0.4), (60, 0.9, 1.3), (64, 2.0, 2.8))
    result = align(written("C4", None, "E4"), sung_notes)
    assert summary(result) == [("match", "m1-n0", ["s0"]), ("extra", None, ["s1"]), ("match", "m1-n2", ["s2"])]


def test_different_pitch_next_to_a_note_stays_extra():
    sung_notes = notes_at((60, 0.0, 0.5), (64, 0.52, 0.8), (62, 1.0, 1.8))
    result = align(written("C4", "D4"), sung_notes)
    assert [p["type"] for p in result["pairs"]] == ["match", "extra", "match"]


@pytest.mark.parametrize("piece", PIECES)
def test_split_flat_note_in_mistakes_take(piece):
    # The planted -35 cent note, split in two: merges; the planted extra (other pitch) stays an extra
    expected = parse_score(score_path(piece))
    raw = synth_notes(piece, "mistakes")
    flat = next(i for i, n in enumerate(raw) if abs(n.midi - round(n.midi) + 0.35) < 1e-6)
    sung_notes, answer = load_take(piece, "mistakes", split=[flat])
    result = align(expected, sung_notes)
    check_invariants(expected, sung_notes, result)
    flat_id = next(i for i, v in answer["notes"].items() if v["status"] == "out_of_tune")
    assert len(by_id(result)[flat_id]["sids"]) == 2
    assert [p["near_id"] for p in result["pairs"] if p["type"] == "extra"] == [e["near_id"] for e in answer["extras"]]


@pytest.mark.parametrize("piece", PIECES)
def test_split_with_octave_down_upload_silence_and_jitter(piece):
    expected = parse_score(score_path(piece))
    sung_notes, _ = load_take(piece, "octave-down", split=[2, 5], jitter_ms=15, seed=4)
    sung_notes = shifted(sung_notes, 1.5)
    result = align(expected, sung_notes)
    check_invariants(expected, sung_notes, result)
    assert result["octave_shift"] == -12
    assert {p["type"] for p in result["pairs"]} == {"match"}
    assert sum(len(p["sids"]) == 2 for p in result["pairs"]) == 2



# --------------------------------------------------------------------------- tempo changes


def written_tempo_change():
    """C D at 60 bpm (1 s per beat), then E F G at 120 bpm (0.5 s per beat), then a rest, then A."""
    spec = [("C4", 0, 1), ("D4", 1, 1), ("E4", 2, 0.5), ("F4", 2.5, 0.5), ("G4", 3, 0.5), (None, 3.5, 0.5), ("A4", 4, 0.5)]
    notes = [{"id": f"m1-n{i}", "measure": 1, "index": i, "is_rest": n is None, "midi": None if n is None else NAMES[n],
              "name": n, "onset_beats": float(i), "duration_beats": 1.0, "onset_sec": float(t), "duration_sec": float(d),
              "lyric": None, "render_ids": [f"m1-n{i}"]} for i, (n, t, d) in enumerate(spec)]
    return {"title": None, "tempo_bpm": 60.0, "beat_unit": "quarter", "notes": notes}


def test_tempo_change_sung_exactly_costs_nothing():
    sung_notes = sung(("C4", 0.0), ("D4", 1.0), ("E4", 2.0), ("F4", 2.5), ("G4", 3.0), ("A4", 4.0))
    result = align(written_tempo_change(), sung_notes)
    assert [p["type"] for p in result["pairs"]] == ["match"] * 6
    assert max(p["cost"] for p in result["pairs"]) == 0
    assert result["time_offset_sec"] == 0


def test_timing_term_uses_the_local_tempo():
    # 0.25 s late is half a beat at 120 bpm (cost 0.25), a quarter beat at 60 bpm (cost 0.125)
    sung_notes = sung(("C4", 0.25), ("D4", 1.0), ("E4", 2.0), ("F4", 2.75), ("G4", 3.0), ("A4", 4.0))
    costs = {p["id"]: p["cost"] for p in align(written_tempo_change(), sung_notes)["pairs"]}
    assert costs["m1-n0"] == pytest.approx(0.125)
    assert costs["m1-n3"] == pytest.approx(0.25)


def test_near_id_after_a_tempo_change():
    # An extra at 3.6 s falls in the rest (3.5-4.0 s); with one tempo (60 bpm) it would land on beat 3.6
    sung_notes = sung(("C4", 0.0), ("D4", 1.0), ("E4", 2.0), ("F4", 2.5), ("G4", 3.0), ("C6", 3.6), ("A4", 4.0))
    extra = next(p for p in align(written_tempo_change(), sung_notes)["pairs"] if p["type"] == "extra")
    assert extra["near_id"] == "m1-n5"



# --------------------------------------------------------------------------- free mode (3e)


def at_speed(sung_notes, speed, lead_in=0.0):
    """The same performance sung at `speed` x the score's tempo (0.75 = slower), starting `lead_in` s later."""
    k = 1.0 / speed
    return {"notes": [dict(n, start_sec=n["start_sec"] * k + lead_in, end_sec=n["end_sec"] * k + lead_in)
                      for n in sung_notes["notes"]]}


@pytest.mark.parametrize("piece", PIECES)
@pytest.mark.parametrize("speed", [0.75, 1.0, 1.3])
def test_free_mode_follows_the_singers_speed(piece, speed):
    expected = parse_score(score_path(piece))
    sung_notes = at_speed(load_take(piece, "perfect")[0], speed)
    result = align(expected, sung_notes, mode="free")
    check_invariants(expected, sung_notes, result)
    assert result["tempo_scale"] == pytest.approx(speed, abs=0.001)
    assert result["time_offset_sec"] == pytest.approx(0.0, abs=0.001)
    assert {p["type"] for p in result["pairs"]} == {"match"}
    assert max(p["cost"] for p in result["pairs"]) < 0.01


@pytest.mark.parametrize("piece", PIECES)
def test_free_mode_mistakes_take_slowed_aligns_the_same(piece):
    expected = parse_score(score_path(piece))
    plain, answer = load_take(piece, "mistakes")
    a = align(expected, plain, mode="free")
    b = align(expected, at_speed(plain, 0.8), mode="free")
    assert summary(a) == summary(b)
    assert [p.get("near_id") for p in b["pairs"] if p["type"] == "extra"] == [e["near_id"] for e in answer["extras"]]
    assert b["tempo_scale"] == pytest.approx(0.8, abs=0.01)


@pytest.mark.parametrize("piece", PIECES)
def test_free_mode_gradual_ritardando(piece):
    # Getting slower and slower: by the end each beat takes ~40% longer. A straight line is only an
    # approximation, but pitch keeps the pairs right.
    expected = parse_score(score_path(piece))
    perfect, _ = load_take(piece, "perfect")
    end = perfect["notes"][-1]["end_sec"]
    warp = lambda t: t + 0.2 * t * t / end  # noqa: E731
    sung_notes = {"notes": [dict(n, start_sec=warp(n["start_sec"]), end_sec=warp(n["end_sec"])) for n in perfect["notes"]]}
    result = align(expected, sung_notes, mode="free")
    check_invariants(expected, sung_notes, result)
    assert {p["type"] for p in result["pairs"]} == {"match"}


@pytest.mark.parametrize("piece", PIECES)
def test_free_mode_everything_at_once(piece):
    # Slower, an octave down, two split notes, a little jitter and 1.5 s of silence before singing
    expected = parse_score(score_path(piece))
    sung_notes, _ = load_take(piece, "octave-down", split=[2, 5], jitter_ms=15, seed=7)
    sung_notes = at_speed(sung_notes, 0.8, lead_in=1.5)
    result = align(expected, sung_notes, mode="free")
    check_invariants(expected, sung_notes, result)
    assert result["octave_shift"] == -12
    assert result["tempo_scale"] == pytest.approx(0.8, abs=0.02)
    assert result["time_offset_sec"] == pytest.approx(1.5, abs=0.05)
    assert {p["type"] for p in result["pairs"]} == {"match"}
    assert sum(len(p["sids"]) == 2 for p in result["pairs"]) == 2


def test_free_mode_with_too_few_notes_keeps_speed_one():
    result = align(written("C4", "D4"), sung(("C4", 0.0), ("D4", 2.0)), mode="free")
    assert (result["tempo_scale"], result["time_offset_sec"]) == (1.0, 0.0)


def test_free_mode_absurd_speed_falls_back():
    # Four times slower than written is outside 0.4x-2.5x: treated as a broken fit, speed 1
    expected = written("C4", "D4", "E4", "F4")
    result = align(expected, sung(("C4", 0.0), ("D4", 4.0), ("E4", 8.0), ("F4", 12.0)), mode="free")
    assert result["tempo_scale"] == 1.0


def test_free_mode_outliers_do_not_tilt_the_line():
    # Six notes exactly on a 0.5x line, two badly rushed: the median-of-slopes fit ignores them
    expected = written("C4", "D4", "E4", "F4", "G4", "A4", "C4", "D4")
    times = [0, 2, 4, 6, 8, 10, 11.0, 14]  # note 7 rushed by 1 s
    times[3] = 5.0  # note 4 rushed by 1 s
    names = ["C4", "D4", "E4", "F4", "G4", "A4", "C4", "D4"]
    result = align(expected, sung(*zip(names, times)), mode="free")
    assert result["tempo_scale"] == pytest.approx(0.5)


def test_strict_mode_never_changes_speed():
    expected = parse_score(score_path("c-major-scale"))
    result = align(expected, at_speed(load_take("c-major-scale", "perfect")[0], 0.75), mode="strict")
    assert result["tempo_scale"] == 1.0



# --------------------------------------------------------------------------- joined notes


def test_repeated_note_sung_legato_is_joined_not_skipped():
    # Written G G A; the two G's sung as one long G (stage 3 sees one note)
    expected = written("G4", "G4", "A4")
    sung_notes = notes_at((67, 0.0, 1.95), (69, 2.0, 2.8))
    result = align(expected, sung_notes)
    check_invariants(expected, sung_notes, result)
    assert summary(result) == [("match", "m1-n0", ["s0"]), ("match", "m1-n1", ["s0"]), ("match", "m1-n2", ["s1"])]
    assert result["pairs"][1]["joined"] is True and "joined" not in result["pairs"][0]


@pytest.mark.parametrize("end,joined", [(0.9, False), (1.4, False), (1.6, True)])
def test_join_needs_the_sung_note_to_last_through_half_the_next(end, joined):
    # The second G spans 1.0-2.0 s: covering 0 or 0.4 s of it isn't enough, 0.6 s is
    result = align(written("G4", "G4", "A4"), notes_at((67, 0.0, end), (69, 2.0, 2.8)))
    assert by_id(result)["m1-n1"]["type"] == ("match" if joined else "skipped")


def test_three_repeated_notes_in_one_breath():
    result = align(written("G4", "G4", "G4", "A4"), notes_at((67, 0.0, 2.9), (69, 3.0, 3.8)))
    assert [p["type"] for p in result["pairs"]] == ["match"] * 4
    assert [bool(p.get("joined")) for p in result["pairs"]] == [False, True, True, False]
    assert {tuple(p["sids"]) for p in result["pairs"][:3]} == {("s0",)}


def test_different_written_pitches_never_join():
    # Written G A, one long G: the A really was skipped (the G was just held too long)
    result = align(written("G4", "A4", "C6"), notes_at((67, 0.0, 1.9), (84, 2.0, 2.8)))
    assert by_id(result)["m1-n1"]["type"] == "skipped"


def test_out_of_tune_long_note_does_not_join():
    # One long note a semitone sharp (G#): wrong for both G's, so the second stays skipped
    result = align(written("G4", "G4", "A4"), notes_at((68, 0.0, 1.95), (69, 2.0, 2.8)))
    assert by_id(result)["m1-n1"]["type"] == "skipped"


def test_joined_works_an_octave_down_and_in_free_mode():
    expected = written("C4", "D4", "G4", "G4", "A4", "C4")
    # an octave down, at 0.8x speed (each written second takes 1.25 s), the two G's as one note
    k = 1.25
    sung_notes = notes_at((48, 0, 0.9 * k), (50, 1 * k, 1.9 * k), (55, 2 * k, 3.95 * k), (57, 4 * k, 4.9 * k), (48, 5 * k, 5.9 * k))
    result = align(expected, sung_notes, mode="free")
    check_invariants(expected, sung_notes, result)
    assert (result["octave_shift"], result["tempo_scale"]) == (-12, pytest.approx(0.8, abs=0.01))
    assert by_id(result)["m1-n3"] == {"type": "match", "id": "m1-n3", "sids": ["s2"], "cost": 0.0, "joined": True}



def test_slow_singer_who_stops_early_is_not_joined():
    # Free mode, singer at half speed. Their long G (4.0-6.6 s) is score time 2.0-3.3 s: it covers only
    # 0.3 of the second G (3-4 s) -> skipped.
    expected = written("C4", "D4", "G4", "G4", "A4", "C4")
    sung_notes = notes_at((60, 0, 1.8), (62, 2, 3.8), (67, 4, 6.6), (69, 8, 9.8), (60, 10, 11.8))
    result = align(expected, sung_notes, mode="free")
    assert result["tempo_scale"] == pytest.approx(0.5)
    assert by_id(result)["m1-n3"]["type"] == "skipped"



def test_join_coverage_uses_the_score_clock_for_a_fast_singer():
    # Free mode at 1.5x speed. The long G is 1.333-2.4 s on the singer's clock = 2.0-3.6 s on the score's:
    # it covers 0.6 of the second G (3-4 s) -> joined. Measured on the singer's clock it covers nothing.
    expected = written("C4", "D4", "G4", "G4", "A4", "C4")
    k = 1 / 1.5
    sung_notes = notes_at((60, 0, 0.9 * k), (62, 1 * k, 1.9 * k), (67, 2 * k, 2.4), (69, 4 * k, 4.8 * k), (60, 5 * k, 5.8 * k))
    result = align(expected, sung_notes, mode="free")
    assert result["tempo_scale"] == pytest.approx(1.5)
    assert by_id(result)["m1-n3"].get("joined") is True
