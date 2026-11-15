"""Stage 6: LLM feedback (owner: B).

Turn results into a short coaching note. The LLM only explains; it never analyzes.
Output shape: contracts/feedback.sample.json

Plan (see docs/DECISIONS.md, "Stage 6"):
- Claude API, model "claude-sonnet-5-5", low effort, structured output matching feedback.json.
- Key from ANTHROPIC_API_KEY (backend/.env, loaded in main.py).
- Send only: meta, score, counts, patterns, extras, and problem notes (max 30).
- Validate: every tips[].measures entry must be a real bar. Retry once, then fall back.
- Timeout ~15 s. On ANY failure return rule_based_feedback(results) with source="fallback".
"""

from __future__ import annotations

import json
import os
from typing import Any

MODEL = "claude-sonnet-5-5"
TIMEOUT_SEC = 15.0
MAX_PROBLEM_NOTES = 30

SYSTEM_PROMPT = """You are a supportive vocal coach for amateur singers.
Use ONLY the facts in the JSON the user provides. Never invent errors, scores, or numbers.
Write under 150 words total across summary, strengths, and tips.
Give at most 2 strengths and at most 3 tips, most important first.
Each tip needs: title, explanation, exercise, measures.
measures must be bar numbers from valid_measures only (or [] if the tip is not bar-specific).
Do not mention that you are an AI or that you were given JSON."""

# Structured output schema (feedback.json without source — we set source ourselves)
FEEDBACK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "strengths": {
            "type": "array",
            "items": {"type": "string"},
        },
        "tips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "explanation": {"type": "string"},
                    "exercise": {"type": "string"},
                    "measures": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["title", "explanation", "exercise", "measures"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "strengths", "tips"],
    "additionalProperties": False,
}


def generate_feedback(results: dict) -> dict:
    """Try Claude; on any failure (or invalid measures after one retry) use the rule fallback."""
    try:
        feedback = _claude_feedback(results)
        if feedback is not None:
            return feedback
    except Exception:
        pass
    return rule_based_feedback(results)


def _claude_feedback(results: dict) -> dict | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    payload = _llm_payload(results)
    valid_measures = set(payload["valid_measures"])
    user_content = (
        "Write coaching feedback from this singing-analysis JSON.\n\n"
        + json.dumps(payload, separators=(",", ":"))
    )

    raw = _call_claude(api_key, user_content)
    ok, feedback = _validate_feedback(raw, valid_measures)
    if ok and feedback is not None:
        return feedback

    # One retry with a short reminder about valid bars
    retry_content = (
        user_content
        + "\n\nYour previous reply had invalid measure numbers. "
        "Every tips[].measures entry MUST be in valid_measures "
        f"({sorted(valid_measures)}) or use an empty list."
    )
    raw = _call_claude(api_key, retry_content)
    ok, feedback = _validate_feedback(raw, valid_measures)
    if ok and feedback is not None:
        return feedback
    return None


def _call_claude(api_key: str, user_content: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SEC)
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        output_config={
            "effort": "low",
            "format": {
                "type": "json_schema",
                "schema": FEEDBACK_SCHEMA,
            },
        },
    )
    text = next(block.text for block in response.content if block.type == "text")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Claude returned non-object JSON")
    return data


def _llm_payload(results: dict) -> dict:
    notes = results.get("notes") or []
    problem_notes = [
        n
        for n in notes
        if not (n.get("status") == "in_tune" and n.get("timing") in (None, "on_time"))
    ][:MAX_PROBLEM_NOTES]

    valid_measures: set[int] = set()
    for n in notes:
        m = n.get("measure")
        if isinstance(m, int):
            valid_measures.add(m)
    for m in (results.get("patterns") or {}).get("worst_measures") or []:
        if isinstance(m, int):
            valid_measures.add(m)

    return {
        "meta": results.get("meta"),
        "score": results.get("score"),
        "counts": results.get("counts"),
        "patterns": results.get("patterns"),
        "extras": results.get("extras") or [],
        "problem_notes": problem_notes,
        "valid_measures": sorted(valid_measures),
    }


def _validate_feedback(
    raw: dict, valid_measures: set[int]
) -> tuple[bool, dict | None]:
    summary = raw.get("summary")
    strengths = raw.get("strengths")
    tips = raw.get("tips")
    if not isinstance(summary, str) or not summary.strip():
        return False, None
    if not isinstance(strengths, list) or not all(isinstance(s, str) for s in strengths):
        return False, None
    if not isinstance(tips, list):
        return False, None

    strengths = [s.strip() for s in strengths if s and s.strip()][:2]
    clean_tips: list[dict] = []
    for tip in tips[:3]:
        if not isinstance(tip, dict):
            return False, None
        title = tip.get("title")
        explanation = tip.get("explanation")
        exercise = tip.get("exercise")
        measures = tip.get("measures")
        if not all(isinstance(x, str) and x.strip() for x in (title, explanation, exercise)):
            return False, None
        if not isinstance(measures, list) or not all(isinstance(m, int) for m in measures):
            return False, None
        if any(m not in valid_measures for m in measures):
            return False, None
        clean_tips.append(
            {
                "title": title.strip(),
                "explanation": explanation.strip(),
                "exercise": exercise.strip(),
                "measures": list(measures),
            }
        )

    if not strengths:
        return False, None
    if not clean_tips:
        return False, None

    return True, {
        "source": "llm",
        "summary": summary.strip(),
        "strengths": strengths,
        "tips": clean_tips,
    }


def rule_based_feedback(results: dict) -> dict:
    """Fallback when the LLM is slow, down, or returns invalid output. Same shape, source="fallback"."""
    counts = results.get("counts") or {}
    notes = results.get("notes") or []
    extras = results.get("extras") or []
    patterns = results.get("patterns") or {}
    score = results.get("score") or {}

    n_notes = int(counts.get("notes") or len(notes) or 0)
    in_tune = int(counts.get("in_tune") or 0)
    # "Right pitch" ≈ in_tune + out_of_tune (wrong note / skipped are not)
    right_pitch = in_tune + int(counts.get("out_of_tune") or 0)

    summary = _summary(n_notes, right_pitch, in_tune, score)
    strengths = _strengths(notes, patterns, score)
    tips = _tips(notes, extras, counts, patterns)

    return {
        "source": "fallback",
        "summary": summary,
        "strengths": strengths[:2],
        "tips": tips[:3],
    }


def _summary(n_notes: int, right_pitch: int, in_tune: int, score: dict) -> str:
    total = score.get("total")
    if n_notes <= 0:
        return "No graded notes were available to coach from."
    if right_pitch == n_notes and in_tune == n_notes:
        base = f"Nice work: all {n_notes} notes landed in tune."
    elif right_pitch == n_notes:
        base = f"Solid pitch map: all {n_notes} notes were the right pitch, with some tuning to polish."
    else:
        base = f"Good start: {right_pitch} of {n_notes} notes landed on the right pitch."
    if isinstance(total, (int, float)):
        return f"{base} Overall score {int(total)}/100."
    return base


def _strengths(notes: list[dict], patterns: dict, score: dict) -> list[str]:
    strengths: list[str] = []

    clean = [
        n
        for n in notes
        if n.get("status") == "in_tune" and n.get("timing") in (None, "on_time") and not n.get("uncertain")
    ]
    if clean:
        names = [n["name"] for n in clean if n.get("name")]
        if len(names) == 1:
            strengths.append(f"{names[0]} was right in tune and on time")
        elif len(names) <= 4:
            strengths.append(f"{_join_names(names)} were right in tune and on time")
        else:
            strengths.append(f"{len(names)} notes were right in tune and on time")

    tendency = patterns.get("timing_tendency")
    if tendency == "steady" and int((score.get("rhythm") or 0)) >= 70:
        strengths.append("Your pulse stayed fairly steady overall")

    intonation = score.get("intonation")
    if isinstance(intonation, (int, float)) and intonation >= 85 and not strengths:
        strengths.append("Intonation was strong when you were on the right note")

    if not strengths:
        strengths.append("Keep going — focus on the tips below for the biggest gains")
    return strengths


def _tips(
    notes: list[dict],
    extras: list[dict],
    counts: dict,
    patterns: dict,
) -> list[dict[str, Any]]:
    tips: list[dict[str, Any]] = []
    used_measures: set[int] = set()

    wrong = [n for n in notes if n.get("status") == "wrong_note"]
    if wrong:
        n = wrong[0]
        measure = n.get("measure")
        sang = n.get("sang") or "a different pitch"
        name = n.get("name") or "the written note"
        tips.append(
            {
                "title": _bar_title(measure, f"{name} came out as {sang}"),
                "explanation": (
                    f"Where the score has {name}, you sang {sang}"
                    + (f" (about {abs(int(n['cents']))} cents off)." if isinstance(n.get("cents"), (int, float)) else ".")
                ),
                "exercise": (
                    f"Sing a slow approach into {name} on 'la' against a reference pitch, "
                    "then place it in the phrase."
                ),
                "measures": _measures(measure),
            }
        )
        if isinstance(measure, int):
            used_measures.add(measure)

    skipped = [n for n in notes if n.get("status") == "skipped"]
    if skipped and len(tips) < 3:
        n = skipped[0]
        measure = n.get("measure")
        name = n.get("name") or "a note"
        tips.append(
            {
                "title": _bar_title(measure, f"{name} was skipped"),
                "explanation": f"You didn't land {name} in this take, so the line lost a step in that bar.",
                "exercise": (
                    f"Isolate that bar: hum the rhythm first, then add {name} on a comfortable vowel "
                    "before singing the full phrase."
                ),
                "measures": _measures(measure),
            }
        )
        if isinstance(measure, int):
            used_measures.add(measure)

    flat_sharp = [n for n in notes if n.get("status") == "out_of_tune"]
    if flat_sharp and len(tips) < 3:
        n = flat_sharp[0]
        measure = n.get("measure")
        cents = n.get("cents")
        name = n.get("name") or "that note"
        direction = "flat" if isinstance(cents, (int, float)) and cents < 0 else "sharp"
        amount = abs(int(cents)) if isinstance(cents, (int, float)) else None
        tips.append(
            {
                "title": _bar_title(measure, f"{name} was {direction}"),
                "explanation": (
                    f"{name} was about {amount} cents {direction}."
                    if amount is not None
                    else f"{name} was slightly {direction}."
                ),
                "exercise": (
                    f"Hold {name} against a drone and slide until the beats disappear, "
                    "then sing the bar without the drone."
                ),
                "measures": _measures(measure),
            }
        )
        if isinstance(measure, int):
            used_measures.add(measure)

    early = [n for n in notes if n.get("timing") == "early"]
    late = [n for n in notes if n.get("timing") == "late"]
    if (early or late) and len(tips) < 3:
        # Prefer a worst_measures bar if it has timing issues
        worst = [m for m in (patterns.get("worst_measures") or []) if isinstance(m, int)]
        timing_notes = early + late
        pick = None
        for m in worst:
            cand = [n for n in timing_notes if n.get("measure") == m]
            if cand:
                pick = cand[0]
                break
        if pick is None:
            pick = timing_notes[0]
        measure = pick.get("measure")
        timing = pick.get("timing")
        ms = pick.get("timing_ms")
        name = pick.get("name") or "A note"
        when = "early" if timing == "early" else "late"
        ms_bit = f" by about {abs(int(ms))} ms" if isinstance(ms, (int, float)) else ""
        other = ""
        if early and late:
            other = " You also had both early and late attacks nearby — aim for a steadier pulse."
        tips.append(
            {
                "title": _bar_title(measure, "keep an even pulse"),
                "explanation": f"{name} came in {when}{ms_bit}.{other}",
                "exercise": (
                    "Clap the bar with a click first, then sing it under tempo before returning "
                    "to performance speed."
                ),
                "measures": _measures(measure),
            }
        )
        if isinstance(measure, int):
            used_measures.add(measure)

    if extras and len(tips) < 3:
        ex = extras[0]
        near = ex.get("near_id")
        measure = _measure_from_id(near)
        sang = ex.get("sang") or "an extra pitch"
        during_rest = bool(ex.get("during_rest"))
        where = "during a rest" if during_rest else f"near {near}" if near else "in the line"
        tips.append(
            {
                "title": _bar_title(measure, f"extra {sang}"),
                "explanation": f"There was an extra note ({sang}) {where}.",
                "exercise": (
                    "Mark rests and held notes in the score, then sing the phrase while "
                    "audibly counting silent beats."
                ),
                "measures": _measures(measure),
            }
        )

    if patterns.get("high_notes_flat") and len(tips) < 3:
        tips.append(
            {
                "title": "Support the higher notes",
                "explanation": "Higher notes tended to sit flat in this take.",
                "exercise": (
                    "On a gentle siren, slide up to the top notes and stay there for a full breath "
                    "before adding the melody."
                ),
                "measures": [],
            }
        )

    tendency = patterns.get("timing_tendency")
    if tendency in ("rushing", "dragging") and len(tips) < 3:
        word = "rushing" if tendency == "rushing" else "dragging"
        tips.append(
            {
                "title": f"Watch for {word}",
                "explanation": f"Across the take, timing tended toward {word}.",
                "exercise": (
                    "Sing with a metronome at a slower tempo, landing every attack exactly on the click."
                ),
                "measures": [
                    m
                    for m in (patterns.get("worst_measures") or [])
                    if isinstance(m, int)
                ][:2],
            }
        )

    # No concrete problems: encourage locking it in (or leave tips empty if already perfect)
    if not tips:
        n_notes = int(counts.get("notes") or 0)
        in_tune = int(counts.get("in_tune") or 0)
        if n_notes > 0 and in_tune == n_notes and not extras:
            tips.append(
                {
                    "title": "Lock this take in",
                    "explanation": "Pitch and timing look clean — the next step is repeating it consistently.",
                    "exercise": "Sing the phrase twice more at performance tempo, then once under tempo as a check.",
                    "measures": [],
                }
            )
        else:
            tips.append(
                {
                    "title": "Sing it again, slowly",
                    "explanation": "This take didn't surface a clear single issue — a slower pass will.",
                    "exercise": (
                        "Halve the tempo, aim for center pitch on every note, then build speed back up."
                    ),
                    "measures": [
                        m
                        for m in (patterns.get("worst_measures") or [])
                        if isinstance(m, int)
                    ][:2],
                }
            )

    return tips


def _bar_title(measure: Any, rest: str) -> str:
    if isinstance(measure, int):
        return f"Bar {measure}: {rest}"
    return rest[0].upper() + rest[1:] if rest else rest


def _measures(measure: Any) -> list[int]:
    return [measure] if isinstance(measure, int) else []


def _measure_from_id(note_id: Any) -> int | None:
    # ids look like m2-n3
    if not isinstance(note_id, str) or not note_id.startswith("m"):
        return None
    try:
        return int(note_id.split("-", 1)[0][1:])
    except ValueError:
        return None


def _join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"
