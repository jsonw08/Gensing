"""API error shape: every failure from /analyze is {"error": {code, message, stage}} (DECISIONS.md section 5)."""

import pytest
from fastapi.testclient import TestClient

from app.errors import AnalysisError
from app.main import app

client = TestClient(app)
FILES = {"musicxml": ("score.musicxml", b"<score/>"), "audio": ("take.wav", b"RIFF")}


def post(data=None, files=FILES):
    return client.post("/analyze", data=data or {}, files=files)


def test_valid_request_passes_validation():
    r = post({"mode": "free", "tempo_bpm": "90", "preset": "beginner", "countin_end_sec": "3.0"})
    assert r.status_code == 200


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
