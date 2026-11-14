"""FastAPI app. Endpoints return sample JSON from /contracts until the stages are real.

POST /analyze   musicxml + WAV + settings -> {results, expected_notes, sung_notes, pitch_track}  (stages 1-5)
POST /feedback  results                    -> feedback  (stage 6; always 200, falls back to rules)

Errors from /analyze use one shape (see docs/DECISIONS.md, "API"):
  {"error": {"code": "...", "message": "...", "stage": "..."}}
"""

import json
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

BACKEND_DIR = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = BACKEND_DIR.parent / "contracts"

load_dotenv(BACKEND_DIR / ".env")  # ANTHROPIC_API_KEY for stage 6

app = FastAPI(title="Gensing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisError(Exception):
    """Raise from any stage to return a clean error to the frontend.

    code:   invalid_musicxml | invalid_audio | no_voice_detected | internal_error
    stage:  score | pitch | segment | align | grade | feedback
    status: 400 bad input, 422 input fine but can't analyze, 500 our bug
    """

    def __init__(self, code: str, message: str, stage: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.stage, self.status = code, message, stage, status


@app.exception_handler(AnalysisError)
async def analysis_error_handler(_: Request, exc: AnalysisError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message, "stage": exc.stage}},
    )


def load_sample(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / f"{name}.sample.json").read_text())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(
    musicxml: UploadFile = File(...),
    audio: UploadFile = File(...),  # always WAV: the frontend converts recordings/uploads first
    mode: Literal["strict", "free"] = Form("strict"),
    tempo_bpm: float | None = Form(None),
    preset: Literal["default", "beginner", "advanced"] = Form("default"),
    countin_end_sec: float = Form(0.0),
) -> dict:
    # TODO: replace with the real pipeline:
    #   expected = score.parse_score(musicxml_path, tempo_bpm)
    #   track    = pitch.track_pitch(wav_path, countin_end_sec)
    #   sung     = segment.segment_notes(track)
    #   aligned  = align.align(expected, sung, mode)
    #   results  = grade.grade(aligned, expected, sung, mode, preset)
    return {
        "results": load_sample("results"),
        "expected_notes": load_sample("expected_notes"),
        "sung_notes": load_sample("sung_notes"),
        "pitch_track": load_sample("pitch_track"),
    }


@app.post("/feedback")
async def feedback(results: dict = Body(...)) -> dict:
    # TODO: replace with feedback.generate_feedback(results), which falls back to
    # feedback.rule_based_feedback(results) on any failure. Never return an error here.
    return load_sample("feedback")
