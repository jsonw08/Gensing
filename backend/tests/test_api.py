"""API error shape: every failure from /analyze is {"error": {code, message, stage}} (DECISIONS.md section 5)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.errors import AnalysisError
from app.main import app

REPO = Path(__file__).resolve().parents[2]

client = TestClient(app)
FILES = {"musicxml": ("score.musicxml", b"<score/>"), "audio": ("take.wav", b"RIFF")}


def post(data=None, files=FILES):  # FILES: junk, fine for tests that fail validation before any stage runs
    return client.post("/analyze", data=data or {}, files=files)


def take_files(piece, take):
    d = REPO / "samples" / piece
    key = json.loads((d / "takes" / f"{take}.answer.json").read_text())
    files = {"musicxml": ("score.musicxml", (d / "score.musicxml").read_bytes()),
             "audio": ("take.wav", (d / "takes" / f"{take}.wav").read_bytes())}
    return files, key


def test_real_take_runs_the_whole_pipeline():
    files, key = take_files("c-major-scale", "mistakes")
    r = post({"mode": "free", "countin_end_sec": str(key["settings"]["countin_end_sec"])}, files)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"results", "expected_notes", "sung_notes", "pitch_track"}
    got = {n["id"]: (n["status"], n["timing"]) for n in body["results"]["notes"]}
    assert got == {i: (v["status"], v["timing"]) for i, v in key["notes"].items()}
    assert body["results"]["meta"]["mode"] == "free"
    json.dumps(body, allow_nan=False)


def test_settings_reach_the_stages():
    files, key = take_files("c-major-scale", "perfect")
    r = post({"mode": "strict", "preset": "advanced", "tempo_bpm": "100",
              "countin_end_sec": str(key["settings"]["countin_end_sec"])}, files)
    meta = r.json()["results"]["meta"]
    assert (meta["mode"], meta["preset"], meta["tempo_bpm"]) == ("strict", "advanced", 100)


def test_junk_score_is_invalid_musicxml():
    files, _ = take_files("c-major-scale", "perfect")
    r = post({"countin_end_sec": "3.0"}, {**files, "musicxml": ("score.musicxml", b"not a score")})
    assert r.status_code == 400
    assert (r.json()["error"]["code"], r.json()["error"]["stage"]) == ("invalid_musicxml", "score")


def test_junk_audio_is_invalid_audio():
    files, _ = take_files("c-major-scale", "perfect")
    r = post({}, {**files, "audio": ("take.wav", b"RIFF but not really")})
    assert r.status_code == 400
    assert (r.json()["error"]["code"], r.json()["error"]["stage"]) == ("invalid_audio", "pitch")


def test_a_crashing_stage_is_internal_error_naming_the_stage(monkeypatch):
    def broken(_track):
        raise RuntimeError("boom")
    monkeypatch.setattr(main, "segment_notes", broken)
    files, key = take_files("c-major-scale", "perfect")
    r = post({"countin_end_sec": str(key["settings"]["countin_end_sec"])}, files)
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal_error", "message": "Something went wrong while analyzing (segment).",
                                  "stage": "segment"}}


def test_uploads_are_deleted_after_the_request():
    before = set(main.TMP_DIR.iterdir()) if main.TMP_DIR.exists() else set()
    files, _ = take_files("c-major-scale", "perfect")
    post({"countin_end_sec": "3.0"}, files)
    post({}, {**files, "audio": ("take.wav", b"junk")})  # a failing request cleans up too
    assert set(main.TMP_DIR.iterdir()) == before


@pytest.mark.parametrize(
    "data,field",
    [
        ({"tempo_bpm": "0"}, "tempo_bpm"),
        ({"tempo_bpm": "-5"}, "tempo_bpm"),
        ({"tempo_bpm": "fast"}, "tempo_bpm"),
        ({"mode": "fast"}, "mode"),
        ({"preset": "expert"}, "preset"),
        ({"countin_end_sec": "-1"}, "countin_end_sec"),
    ],
)
def test_bad_field_is_invalid_input_in_our_shape(data, field):
    r = post(data)
    assert r.status_code == 400
    assert set(r.json()) == {"error"}
    err = r.json()["error"]
    assert (err["code"], err["stage"]) == ("invalid_input", "api")
    assert err["message"].startswith(f"{field}: ")


def test_missing_file_is_invalid_input():
    r = post(files={"musicxml": FILES["musicxml"]})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_input"
    assert r.json()["error"]["message"].startswith("audio: ")


def test_analysis_error_from_a_stage_keeps_its_own_code_and_status():
    @app.get("/_test_raise")
    def _raise():
        raise AnalysisError("no_voice_detected", "No singing found in the recording.", "pitch", 422)

    r = client.get("/_test_raise")
    assert r.status_code == 422
    assert r.json() == {"error": {"code": "no_voice_detected", "message": "No singing found in the recording.", "stage": "pitch"}}
