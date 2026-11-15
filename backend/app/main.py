"""FastAPI app.

POST /analyze   musicxml + WAV + settings -> {results, expected_notes, sung_notes, pitch_track}  (stages 1-5)
POST /feedback  results                    -> feedback  (stage 6; always 200, falls back to rules)

Errors from /analyze use one shape (see docs/DECISIONS.md, "API"):
  {"error": {"code": "...", "message": "...", "stage": "..."}}
"""

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Literal

from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.errors import AnalysisError  # stages raise it; defined in app/errors.py to avoid a circular import
from app.stages.align import align
from app.stages.feedback import generate_feedback, rule_based_feedback
from app.stages.grade import grade
from app.stages.pitch import track_pitch
from app.stages.score import parse_score
from app.stages.segment import segment_notes

BACKEND_DIR = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = BACKEND_DIR.parent / "contracts"
TMP_DIR = BACKEND_DIR / "tmp"  # uploads live here only while a request runs (gitignored)

log = logging.getLogger("gensing")

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
    mode: Literal["strict", "free"] = Form("free"),  # free is the main mode (DECISIONS.md section 1)
    tempo_bpm: float | None = Form(None, gt=0),
    preset: Literal["default", "beginner", "advanced"] = Form("default"),
    countin_end_sec: float = Form(0.0, ge=0),
) -> dict:
    """Stages 1-5. The uploads are saved to backend/tmp/ for the length of the request."""
    TMP_DIR.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(dir=TMP_DIR))
    try:
        score_path, wav_path = work / "score", work / "audio.wav"  # stage 1 reads the score by content
        score_path.write_bytes(await musicxml.read())
        wav_path.write_bytes(await audio.read())
        # pitch tracking takes seconds: run it off the event loop so the server stays responsive
        return await run_in_threadpool(
            run_pipeline, score_path, wav_path, mode, tempo_bpm, preset, countin_end_sec
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_pipeline(
    score_path: Path, wav_path: Path, mode: str, tempo_bpm: float | None, preset: str, countin_end_sec: float
) -> dict:
    expected = _stage("score", parse_score, score_path, tempo_bpm)
    track = _stage("pitch", track_pitch, str(wav_path), countin_end_sec)
    sung = _stage("segment", segment_notes, track)
    aligned = _stage("align", align, expected, sung, mode)
    results = _stage("grade", grade, aligned, expected, sung, mode, preset)
    return {"results": results, "expected_notes": expected, "sung_notes": sung, "pitch_track": track}


def _stage(name: str, fn: Callable, *args):
    """Run one stage. AnalysisError passes through as is; any other exception is our bug: logged with
    its traceback and returned as a 500 internal_error that names the stage."""
    try:
        return fn(*args)
    except AnalysisError:
        raise
    except Exception as e:
        log.exception("stage %s crashed", name)
        raise AnalysisError("internal_error", f"Something went wrong while analyzing ({name}).", name, 500) from e


@app.post("/feedback")
async def feedback(results: dict = Body(...)) -> dict:
    """Stage 6. Body = the `results` object from /analyze.

    Always 200: Claude via generate_feedback, or rule_based_feedback on any failure.
    """
    try:
        return generate_feedback(results)
    except Exception:
        try:
            return rule_based_feedback(results)
        except Exception:
            return load_sample("feedback")
