"""Stage 5: Grading and scoring (owner: C).

Judge every pair, compute the overall score, find patterns for feedback.
Output shape: contracts/results.sample.json
"""


def grade(
    alignment: dict,
    expected_notes: dict,
    sung_notes: dict,
    mode: str = "strict",
    preset: str = "default",
) -> dict:
    raise NotImplementedError
