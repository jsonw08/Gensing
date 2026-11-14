"""Stage 6: LLM feedback (owner: B).

Turn results into a short coaching note. The LLM only explains; it never analyzes.
Output shape: contracts/feedback.sample.json

Plan (see docs/DECISIONS.md, "Stage 6"):
- Claude API, model "claude-opus-5-5", low effort, structured output matching feedback.json.
- Key from ANTHROPIC_API_KEY (backend/.env, loaded in main.py).
- Send only: meta, score, counts, patterns, extras, and problem notes (max 30).
- Validate: every tips[].measures entry must be a real bar. Retry once, then fall back.
- Timeout ~15 s. On ANY failure return rule_based_feedback(results) with source="fallback".
"""


def generate_feedback(results: dict) -> dict:
    raise NotImplementedError


def rule_based_feedback(results: dict) -> dict:
    """Fallback when the LLM is slow, down, or returns invalid output. Same shape, source="fallback"."""
    raise NotImplementedError
