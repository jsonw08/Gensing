# Contracts

Sample JSON for every hand-off between stages. **These formats are locked**: field-by-field
definitions and the reasoning are in [`docs/DECISIONS.md`](../docs/DECISIONS.md), section 4.

All six samples describe one run: `samples/c-major-scale/takes/mistakes.wav` analyzed against
`samples/c-major-scale/score.musicxml`. The note IDs are real, so the frontend can test coloring
against them directly. (`pitch_track` is truncated to 8 frames.)

| File | Produced by | Consumed by |
|---|---|---|
| `expected_notes.sample.json` | Stage 1 (C) | 4, 5, 6, 7 |
| `pitch_track.sample.json` | Stage 2 (B) | 3, 7 (pitch view) |
| `sung_notes.sample.json` | Stage 3 (B) | 4, 5, 7 |
| `alignment.sample.json` | Stage 4 (C) | 5 |
| `results.sample.json` | Stage 5 (C) | 6, 7 |
| `feedback.sample.json` | Stage 6 (B) | 7 |

`POST /analyze` returns `{results, expected_notes, sung_notes, pitch_track}`.
`POST /feedback` takes `results` and returns `feedback`.

Changing a field? Update the sample, `docs/DECISIONS.md`, and tell whoever consumes the file,
all in the same PR.
