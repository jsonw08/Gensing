"""Tests for the synth_sung helper (perfect sung_notes for stages 4-5)."""

import json

import pytest
import synth_take
from synth_sung import PIECES, TAKES, answer_key, load_take, score_path

from app.stages.score import parse_score

ALL = [(p, t) for p in PIECES for t in TAKES]
CONTRACT_KEYS = set(json.loads(open(score_path("c-major-scale").parents[2] / "contracts/sung_notes.sample.json").read())["notes"][0])


def sung_written(piece):
    return [n for n in parse_score(score_path(piece))["notes"] if not n["is_rest"]]


@pytest.mark.parametrize("piece,take", ALL)
def test_contract_shape_order_and_strict_json(piece, take):
    sung, _ = load_take(piece, take)
    notes = sung["notes"]
    assert [n["sid"] for n in notes] == [f"s{i}" for i in range(len(notes))]
    assert all(set(n) == CONTRACT_KEYS for n in notes)
    for a, b in zip(notes, notes[1:]):
        assert a["start_sec"] < a["end_sec"] <= b["start_sec"]  # time order, never overlapping
    json.loads(json.dumps(sung), parse_constant=lambda c: pytest.fail(c))


@pytest.mark.parametrize("piece,take", ALL)
def test_helper_matches_committed_answer_keys(piece, take):
    # If synth_take changes without regenerating the takes, the helper and the WAVs/keys drift apart.
    score = synth_take.parse_score(score_path(piece))
    maker = {"perfect": synth_take.take_perfect, "mistakes": synth_take.take_mistakes,
             "octave-down": synth_take.take_octave_down, "delayed": synth_take.take_delayed}[take]
    generated = maker(score)
    key = answer_key(piece, take)
    assert generated.answer_notes == key["notes"]
    assert generated.answer_extras == key["extras"]


@pytest.mark.parametrize("piece", PIECES)
def test_perfect_is_the_score(piece):
    sung, _ = load_take(piece, "perfect")
    written = sung_written(piece)
    assert len(sung["notes"]) == len(written)
    for s, w in zip(sung["notes"], written):
        assert s["midi"] == w["midi"]
        assert s["start_sec"] == pytest.approx(w["onset_sec"])


@pytest.mark.parametrize("piece", PIECES)
def test_octave_down_and_delayed(piece):
    written = sung_written(piece)
    low, _ = load_take(piece, "octave-down")
    late, answer = load_take(piece, "delayed")
    assert [s["midi"] for s in low["notes"]] == [w["midi"] - 12 for w in written]
    delay = answer["expect"]["timing_offset_ms"] / 1000
    assert [s["start_sec"] for s in late["notes"]] == pytest.approx([w["onset_sec"] + delay for w in written])


@pytest.mark.parametrize("piece", PIECES)
def test_mistakes_take(piece):
    sung, answer = load_take(piece, "mistakes")
    written = sung_written(piece)
    skipped = sum(v["status"] == "skipped" for v in answer["notes"].values())
    assert len(sung["notes"]) == len(written) - skipped + len(answer["extras"])
    midis = [s["midi"] for s in sung["notes"]]
    assert any(abs(m - round(m) + 0.35) < 1e-6 for m in midis)  # the -35 cent flat note


def test_split_cuts_one_note_in_two():
    plain, _ = load_take("c-major-scale", "perfect")
    split, _ = load_take("c-major-scale", "perfect", split=[3])
    assert len(split["notes"]) == len(plain["notes"]) + 1
    original, a, b = plain["notes"][3], split["notes"][3], split["notes"][4]
    assert a["midi"] == b["midi"] == original["midi"]
    assert a["start_sec"] == original["start_sec"] and b["end_sec"] == original["end_sec"]
    assert a["end_sec"] < b["start_sec"]
    assert split["notes"][5]["midi"] == plain["notes"][4]["midi"]  # later notes just shift by one sid


def test_jitter_is_bounded_and_repeatable():
    plain, _ = load_take("edge-cases", "perfect")
    j1, _ = load_take("edge-cases", "perfect", jitter_ms=20, seed=1)
    j2, _ = load_take("edge-cases", "perfect", jitter_ms=20, seed=1)
    assert j1 == j2
    starts = [(p["start_sec"], j["start_sec"]) for p, j in zip(plain["notes"], j1["notes"])]
    assert all(abs(p - j) <= 0.0201 for p, j in starts)
    assert any(p != j for p, j in starts)
