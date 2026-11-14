"""Test helper: perfect `sung_notes` for every generated take, so stages 4-5 can be tested without
stages 2-3 (Jonathan's audio side).

tools/synth_take.py builds the exact list of notes it "sings" (pitch, start, end) before rendering each
WAV, then throws it away. This turns that list into the sung_notes contract (DECISIONS.md 4.3) and
pairs it with the take's committed answer key. Same timeline as the real pipeline: 0.0 s = beat 1
(the count-in is not included).

    sung, answer = load_take("c-major-scale", "mistakes")
    sung, answer = load_take("edge-cases", "perfect", split=[3], jitter_ms=20)

It's "perfect segmentation": real stage 3 output will be messier. The knobs fake the two most common
segmentation errors on purpose: `split` (one note cut in two -> stage 4's split-note merge) and
`jitter_ms` (note edges a little off).
"""

import json
from pathlib import Path

import numpy as np
import synth_take

REPO = Path(__file__).resolve().parents[2]
PIECES = ["c-major-scale", "edge-cases"]
TAKES = ["perfect", "mistakes", "octave-down", "delayed"]

# Not in synth's data; fixed, realistic values. Vibrato of +/-30 cents (a sine) has a std dev of ~21 cents.
STABILITY_CENTS = 21.0
CONF = 0.9
SPLIT_GAP_SEC = 0.02  # silence between the two halves of a split note
MIN_GAP_SEC = 0.01  # jitter never makes notes touch or overlap


def score_path(piece: str) -> Path:
    return REPO / "samples" / piece / "score.musicxml"


def answer_key(piece: str, take: str) -> dict:
    return json.loads((REPO / "samples" / piece / "takes" / f"{take}.answer.json").read_text())


def synth_notes(piece: str, take: str) -> list[synth_take.SungNote]:
    """The notes synth_take sang for this take (raw: midi, start, end), in time order."""
    score = synth_take.parse_score(score_path(piece))
    makers = {
        "perfect": synth_take.take_perfect,
        "mistakes": synth_take.take_mistakes,
        "octave-down": synth_take.take_octave_down,
        "delayed": synth_take.take_delayed,
    }
    return sorted(makers[take](score).sung, key=lambda s: s.start)


def load_take(
    piece: str,
    take: str,
    *,
    split: list[int] = (),
    jitter_ms: float = 0.0,
    seed: int = 0,
) -> tuple[dict, dict]:
    """Return (sung_notes, answer_key) for one take.

    split:     indices (into the unsplit, time-ordered notes) of notes to cut in two halves, same pitch
    jitter_ms: move every start/end by a random amount in [-jitter_ms, +jitter_ms] (seeded)
    """
    raw = [(s.midi, s.start, s.end) for s in synth_notes(piece, take)]

    notes = []
    for i, (midi, start, end) in enumerate(raw):
        if i in split:
            mid = (start + end) / 2
            notes += [(midi, start, mid - SPLIT_GAP_SEC / 2), (midi, mid + SPLIT_GAP_SEC / 2, end)]
        else:
            notes.append((midi, start, end))

    if jitter_ms:
        rng = np.random.default_rng(seed)
        j = jitter_ms / 1000
        jittered, prev_end = [], -1.0
        for midi, start, end in notes:
            start = max(start + rng.uniform(-j, j), prev_end + MIN_GAP_SEC, 0.0)
            end = max(end + rng.uniform(-j, j), start + MIN_GAP_SEC)
            jittered.append((midi, start, end))
            prev_end = end
        notes = jittered

    sung = {
        "notes": [
            {
                "sid": f"s{i}",
                "start_sec": round(start, 4),
                "end_sec": round(end, 4),
                "midi": round(float(midi), 4),  # synth stores wrong notes as int
                "stability_cents": STABILITY_CENTS,
                "conf": CONF,
            }
            for i, (midi, start, end) in enumerate(notes)
        ],
        "params": {"source": "synth_take", "piece": piece, "take": take, "split": list(split), "jitter_ms": jitter_ms},
    }
    return sung, answer_key(piece, take)
