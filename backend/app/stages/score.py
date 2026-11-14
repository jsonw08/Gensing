"""Stage 1: Score parsing (owner: C).

MusicXML -> ordered list of every note the singer should sing.
Output shape: contracts/expected_notes.sample.json
"""


def parse_score(musicxml_path: str, tempo_bpm: float | None = None) -> dict:
    """Parse the first part, top line only, with music21.

    Note IDs must be "m{measure}-n{index}" and match the frontend's renderer.
    If tempo_bpm is None, use the score's tempo marking.
    """
    raise NotImplementedError
