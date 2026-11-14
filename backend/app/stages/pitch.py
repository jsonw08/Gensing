"""Stage 2: Pitch tracking (owner: B).

Recording -> pitch reading every 10 ms (no notes yet, just a curve).
Output shape: contracts/pitch_track.sample.json
"""


def track_pitch(audio_path: str, countin_end_sec: float = 0.0) -> dict:
    """Mono + resample + normalize, trim the count-in so 0.0 s = beat 1,
    then librosa.pyin + RMS per frame.
    """
    raise NotImplementedError
