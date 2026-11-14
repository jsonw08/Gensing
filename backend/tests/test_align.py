"""Stage 4 (alignment) tests. Part 3a: core table in strict mode + near_id."""

import json
from pathlib import Path

import pytest
from synth_sung import PIECES, load_take, score_path

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
    # every sung note exactly once (in a match or as an extra), in time order
    assert [s for p in result["pairs"] for s in p["sids"]] == [s["sid"] for s in sung_notes["notes"]]
    # shapes
    for p in result["pairs"]:
        assert set(p) == {"type", "id", "sids", "cost"} | ({"near_id"} if p["type"] == "extra" else set())
        assert len(p["sids"]) == {"match": 1, "skipped": 0, "extra": 1}[p["type"]]
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


def test_free_mode_not_available_yet():
    with pytest.raises(AnalysisError) as err:
        align(written("C4"), sung(("C4", 0.0)), mode="free")
    assert (err.value.code, err.value.stage, err.value.status) == ("invalid_input", "align", 422)


def test_nothing_sung_means_everything_skipped():
    result = align(written("C4", "D4"), {"notes": []})
    assert summary(result) == [("skipped", "m1-n0", []), ("skipped", "m1-n1", [])]
    assert result["total_cost"] == 6.0
