"""Stage 4: Alignment (owner: C).

Pair written notes with sung notes: match / skipped / extra. No judgments here.
Output shape: contracts/alignment.sample.json
"""


def align(expected_notes: dict, sung_notes: dict, mode: str = "strict") -> dict:
    """mode: "strict" (against the click) or "free" (against the singer's own tempo)."""
    raise NotImplementedError
