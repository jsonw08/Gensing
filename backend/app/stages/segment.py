"""Stage 3: Note segmentation (owner: B).

Pitch curve -> list of sung notes (start, end, one pitch). Does not look at the score.
Output shape: contracts/sung_notes.sample.json
"""


def segment_notes(pitch_track: dict) -> dict:
    raise NotImplementedError
