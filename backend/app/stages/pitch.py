"""Stage 2: Pitch tracking (owner: B).

Recording -> pitch reading every 10 ms (no notes yet, just a curve).
Output shape: contracts/pitch_track.sample.json

Decided knobs (docs/DECISIONS.md §4.2, AGENTS.md §6):
  sr=16000, hop_length=160 (exactly 10 ms), fmin=65, fmax=1050.
"""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

SAMPLE_RATE = 16_000
HOP_LENGTH = 160  # 160 / 16000 = 0.01 s exactly
HOP_SEC = HOP_LENGTH / SAMPLE_RATE
FMIN = 65.0
FMAX = 1050.0


def _jsonable_float(x: float) -> float | None:
    """JSON has no NaN/Inf; contract requires null for missing pitch."""
    if x is None or not np.isfinite(x):
        return None
    return float(x)


def track_pitch(audio_path: str, countin_end_sec: float = 0.0) -> dict:
    """Mono + resample + normalize, trim the count-in so 0.0 s = beat 1,
    then librosa.pyin + RMS per frame.
    """
    path = Path(audio_path)
    if not path.is_file():
        from app.main import AnalysisError

        raise AnalysisError(
            "invalid_audio",
            f"Audio file not found: {audio_path}",
            stage="pitch",
            status=400,
        )

    try:
        y, _sr = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    except Exception as exc:  # librosa wraps soundfile / audioread errors
        from app.main import AnalysisError

        raise AnalysisError(
            "invalid_audio",
            f"Could not read audio: {exc}",
            stage="pitch",
            status=400,
        ) from exc

    if countin_end_sec < 0:
        countin_end_sec = 0.0

    trim_samples = int(round(countin_end_sec * SAMPLE_RATE))
    if trim_samples >= len(y):
        from app.main import AnalysisError

        raise AnalysisError(
            "invalid_audio",
            "Count-in trim leaves no audio to analyze",
            stage="pitch",
            status=400,
        )

    y = y[trim_samples:]
    audio_offset_sec = float(countin_end_sec)
    duration_sec = float(len(y) / SAMPLE_RATE)

    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak > 0.0:
        y = y / peak

    # pYIN: f0 in Hz (NaN when unvoiced), voiced flag, voiced probability
    f0_hz, voiced_flag, voiced_probs = librosa.pyin(
        y,
        fmin=FMIN,
        fmax=FMAX,
        sr=SAMPLE_RATE,
        hop_length=HOP_LENGTH,
    )

    # Loudness on the same hop grid. Match pYIN frame count (pad/trim).
    rms = librosa.feature.rms(y=y, hop_length=HOP_LENGTH)[0]
    n = len(f0_hz)
    if len(rms) < n:
        rms = np.pad(rms, (0, n - len(rms)))
    elif len(rms) > n:
        rms = rms[:n]

    # Contract sample uses t = i * hop_sec (first frame at 0.0 = beat 1).
    t = (np.arange(n, dtype=np.float64) * HOP_SEC).tolist()

    midi: list[float | None] = []
    for hz, is_voiced in zip(f0_hz, voiced_flag):
        if not is_voiced or not np.isfinite(hz):
            midi.append(None)
        else:
            midi.append(_jsonable_float(float(librosa.hz_to_midi(hz))))

    voiced = [bool(v) for v in voiced_flag]
    conf = [float(c) if np.isfinite(c) else 0.0 for c in voiced_probs]
    rms_out = [float(r) if np.isfinite(r) else 0.0 for r in rms]

    return {
        "sample_rate": SAMPLE_RATE,
        "hop_sec": HOP_SEC,
        "audio_offset_sec": audio_offset_sec,
        "duration_sec": duration_sec,
        "t": t,
        "midi": midi,
        "voiced": voiced,
        "conf": conf,
        "rms": rms_out,
    }
