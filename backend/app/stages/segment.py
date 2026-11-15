"""Stage 3: Note segmentation (owner: B).

Pitch curve -> list of sung notes (start, end, one pitch). Does not look at the score.
Output shape: contracts/sung_notes.sample.json

Pass 1: conf cutoff, ~50 ms median filter, split on pitch jumps held ≥50 ms,
drop notes shorter than 80 ms.
Pass 2: merge same-pitch neighbors with no real break, then split same-pitch runs on RMS dips
(in that order, so a re-sung repeated note isn't merged back).
"""

from __future__ import annotations

import numpy as np

from app.errors import AnalysisError

# Starting knobs (AGENTS.md §6 / contracts/sung_notes.sample.json params)
CONF_CUTOFF = 0.5
MIN_PITCH_CHANGE = 0.5  # semitones
MIN_HOLD_MS = 50
MIN_NOTE_MS = 80
MEDIAN_FILTER_MS = 50

# Pass 2 starting knobs (not locked in DECISIONS.md — tune on takes)
# Synth breath gaps are 60 ms; merge must stay stricter so real breaths stay split.
RMS_DIP_RATIO = 0.5  # dip if rms < this × median rms of the span
RMS_DIP_MIN_MS = 30  # dip must last at least this long
RMS_DIP_EDGE_MS = 40  # ignore attack/release at span edges
MERGE_MAX_GAP_MS = 30  # merge same-pitch neighbors if gap ≤ this
MERGE_PITCH_TOL = 0.5  # semitones


def segment_notes(pitch_track: dict) -> dict:
    hop_sec = float(pitch_track["hop_sec"])
    t = np.asarray(pitch_track["t"], dtype=float)
    n = len(t)
    if n == 0:
        raise AnalysisError(
            "no_voice_detected",
            "The recording is empty.",
            stage="segment",
            status=422,
        )

    midi_raw = np.array(
        [np.nan if m is None else float(m) for m in pitch_track["midi"]],
        dtype=float,
    )
    voiced = np.asarray(pitch_track["voiced"], dtype=bool)
    conf = np.asarray(pitch_track["conf"], dtype=float)
    rms = np.asarray(pitch_track["rms"], dtype=float)

    # Usable pitch: voiced, above conf cutoff, finite midi
    usable = voiced & (conf >= CONF_CUTOFF) & np.isfinite(midi_raw)
    midi_usable = np.where(usable, midi_raw, np.nan)

    filter_frames = max(1, int(round(MEDIAN_FILTER_MS / (hop_sec * 1000.0))))
    if filter_frames % 2 == 0:
        filter_frames += 1
    midi_f = _nan_median_filter(midi_usable, filter_frames)

    hold_frames = max(1, int(round(MIN_HOLD_MS / (hop_sec * 1000.0))))
    min_note_frames = max(1, int(round(MIN_NOTE_MS / (hop_sec * 1000.0))))
    dip_min_frames = max(1, int(round(RMS_DIP_MIN_MS / (hop_sec * 1000.0))))
    dip_edge_frames = max(0, int(round(RMS_DIP_EDGE_MS / (hop_sec * 1000.0))))
    merge_gap_frames = max(0, int(round(MERGE_MAX_GAP_MS / (hop_sec * 1000.0))))

    spans = _split_notes(midi_f, hold_frames=hold_frames, min_change=MIN_PITCH_CHANGE)
    # Merge pitch-jitter fragments first, THEN split on loudness dips: merging after the dip split glued a
    # re-sung repeated note (dip ~30 ms at low pitches, where pYIN's long window smears the gap) back together.
    spans = _merge_same_pitch(
        spans,
        midi_f,
        pitch_tol=MERGE_PITCH_TOL,
        max_gap_frames=merge_gap_frames,
    )
    spans = _split_on_rms_dips(
        spans,
        rms,
        dip_ratio=RMS_DIP_RATIO,
        dip_min_frames=dip_min_frames,
        edge_frames=dip_edge_frames,
    )
    spans = [(a, b) for a, b in spans if (b - a) >= min_note_frames]

    notes: list[dict] = []
    for start_i, end_i in spans:
        # end_i is exclusive
        sl = slice(start_i, end_i)
        note_midi = midi_f[sl]
        note_conf = conf[sl]
        finite = np.isfinite(note_midi)
        if not np.any(finite):
            continue

        # Middle ~60% of the note (ignore scoops at the edges)
        idxs = np.nonzero(finite)[0]
        lo = idxs[int(len(idxs) * 0.20)]
        hi = idxs[int(len(idxs) * 0.80)]
        if hi < lo:
            hi = lo
        mid = note_midi[lo : hi + 1]
        mid = mid[np.isfinite(mid)]
        if mid.size == 0:
            continue

        midi_med = float(np.median(mid))
        stability = float(np.std(mid) * 100.0)  # midi std → cents
        conf_mean = float(np.mean(note_conf))

        notes.append(
            {
                "sid": f"s{len(notes)}",
                "start_sec": float(t[start_i]),
                "end_sec": float(t[end_i - 1]),
                "midi": midi_med,
                "stability_cents": stability,
                "conf": conf_mean,
            }
        )

    if not notes:
        raise AnalysisError(
            "no_voice_detected",
            "No singing found in the recording. Check the microphone and try again.",
            stage="segment",
            status=422,
        )

    return {
        "notes": notes,
        "params": {
            "conf_cutoff": CONF_CUTOFF,
            "min_pitch_change": MIN_PITCH_CHANGE,
            "min_hold_ms": MIN_HOLD_MS,
            "min_note_ms": MIN_NOTE_MS,
            # Pass 2 knobs (extra vs sample; for tuning comparability)
            "rms_dip_ratio": RMS_DIP_RATIO,
            "rms_dip_min_ms": RMS_DIP_MIN_MS,
            "merge_max_gap_ms": MERGE_MAX_GAP_MS,
            "merge_pitch_tol": MERGE_PITCH_TOL,
        },
    }


def _nan_median_filter(x: np.ndarray, size: int) -> np.ndarray:
    """Centered median filter that ignores NaNs; all-NaN windows stay NaN."""
    if size <= 1:
        return x.copy()
    half = size // 2
    out = np.full_like(x, np.nan)
    n = len(x)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        window = x[lo:hi]
        finite = window[np.isfinite(window)]
        if finite.size:
            out[i] = float(np.median(finite))
    return out


def _split_notes(
    midi_f: np.ndarray,
    *,
    hold_frames: int,
    min_change: float,
) -> list[tuple[int, int]]:
    """Return half-open [start, end) frame spans for candidate notes.

    A note ends on an unvoiced gap, or when pitch moves by > min_change semitones
    and the new pitch is held for hold_frames.
    """
    n = len(midi_f)
    spans: list[tuple[int, int]] = []
    i = 0
    while i < n:
        while i < n and not np.isfinite(midi_f[i]):
            i += 1
        if i >= n:
            break

        start = i
        # Reference pitch = first frame of this note (after median filter)
        ref = float(midi_f[i])
        i += 1
        change_run = 0

        while i < n and np.isfinite(midi_f[i]):
            pitch = float(midi_f[i])
            if abs(pitch - ref) > min_change:
                change_run += 1
                if change_run >= hold_frames:
                    # Split before the sustained new pitch began
                    split_at = i - change_run + 1
                    if split_at > start:
                        spans.append((start, split_at))
                    start = split_at
                    ref = float(midi_f[start])
                    i = start + 1
                    change_run = 0
                    continue
            else:
                change_run = 0
            i += 1

        if i > start:
            spans.append((start, i))

    return spans


def _split_on_rms_dips(
    spans: list[tuple[int, int]],
    rms: np.ndarray,
    *,
    dip_ratio: float,
    dip_min_frames: int,
    edge_frames: int,
) -> list[tuple[int, int]]:
    """Split a span where loudness dips (re-articulated same pitch).

    Dip frames are excluded from both sides. Edge frames are ignored so attack
    and release don't count as dips.
    """
    out: list[tuple[int, int]] = []
    for start, end in spans:
        length = end - start
        if length < dip_min_frames + 2 * edge_frames + 1:
            out.append((start, end))
            continue

        seg = rms[start:end]
        finite = seg[np.isfinite(seg)]
        if finite.size == 0:
            out.append((start, end))
            continue

        thresh = float(np.median(finite)) * dip_ratio
        # Search only the interior of the span
        lo = start + edge_frames
        hi = end - edge_frames
        dip_runs: list[tuple[int, int]] = []
        i = lo
        while i < hi:
            if np.isfinite(rms[i]) and rms[i] < thresh:
                run_start = i
                while i < hi and np.isfinite(rms[i]) and rms[i] < thresh:
                    i += 1
                if i - run_start >= dip_min_frames:
                    dip_runs.append((run_start, i))
            else:
                i += 1

        if not dip_runs:
            out.append((start, end))
            continue

        cursor = start
        for dip_a, dip_b in dip_runs:
            if dip_a > cursor:
                out.append((cursor, dip_a))
            cursor = dip_b
        if cursor < end:
            out.append((cursor, end))

    return out


def _merge_same_pitch(
    spans: list[tuple[int, int]],
    midi_f: np.ndarray,
    *,
    pitch_tol: float,
    max_gap_frames: int,
) -> list[tuple[int, int]]:
    """Merge neighbors with similar pitch and only a tiny gap (conf flicker, not a breath)."""
    if not spans:
        return []

    def span_midi(a: int, b: int) -> float | None:
        vals = midi_f[a:b]
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            return None
        return float(np.median(vals))

    merged: list[tuple[int, int]] = [spans[0]]
    for start, end in spans[1:]:
        prev_a, prev_b = merged[-1]
        gap = start - prev_b
        p0 = span_midi(prev_a, prev_b)
        p1 = span_midi(start, end)
        if (
            p0 is not None
            and p1 is not None
            and gap >= 0
            and gap <= max_gap_frames
            and abs(p0 - p1) <= pitch_tol
        ):
            merged[-1] = (prev_a, end)
        else:
            merged.append((start, end))
    return merged
