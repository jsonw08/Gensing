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
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.errors import AnalysisError  # stages raise it; defined in app/errors.py to avoid a circular import
from app.stages.feedback import generate_feedback, rule_based_feedback

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


@app.exception_handler(AnalysisError)
async def analysis_error_handler(_: Request, exc: AnalysisError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message, "stage": exc.stage}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Bad form fields (tempo_bpm=0, mode="fast", missing file) are rejected by FastAPI before our
    endpoint runs; without this they'd come back as FastAPI's own {"detail": [...]} 422."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = first.get("loc", ("request",))[-1]
    message = f"{field}: {first.get('msg', 'invalid request')}"
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "invalid_input", "message": message, "stage": "api"}},
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
    tempo_bpm: float | None = Form(None, gt=0),
    preset: Literal["default", "beginner", "advanced"] = Form("default"),
    countin_end_sec: float = Form(0.0, ge=0),
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
    """Stage 6. Body = results object (until stage 5 is live, POST contracts/results.sample.json).

    Always 200: Claude via generate_feedback, or rule_based_feedback on any failure.
    """
    try:
        return generate_feedback(results)
    except Exception:
        try:
            return rule_based_feedback(results)
        except Exception:
            return load_sample("feedback")
