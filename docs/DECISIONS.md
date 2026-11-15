# Gensing: Decisions Before We Start

Everything the team agreed on before building, in one place. Read this before starting your part.
Background and the full pipeline design are in [`PIPELINE_NOTES.md`](PIPELINE_NOTES.md); stage 4 is explained
in depth in [`ALIGNMENT_EXPLAINED.md`](ALIGNMENT_EXPLAINED.md).

**Change these deliberately, not by drift.** If something here needs to change, change this doc
and `contracts/` in the same PR, and tell whoever reads the affected file.

---

## 1. What we're building

A singer uploads a MusicXML score, records themselves singing it, and gets the sheet music back
with every note marked: in tune, out of tune, wrong note, early/late, skipped, or extra. Plus an
overall score and short AI coaching tips. HackUMass XIV, team of 3, 24 hours.

**Must work in the demo:** a colored score showing the error types, plus the overall score.

**Timing modes (decided 2026-11-14):**

- **Free (main mode, the default):** the singer records at their own speed. Rhythm is judged against
  their own pulse, not the score's tempo marking.
- **Strict (secondary):** graded against the score's tempo. The app plays **only a one-bar count-in**
  at the starting tempo, then no click while singing: the singer keeps time on their own. (No
  continuous click, so the frontend has nothing to keep in sync with tempo changes, and headphones are
  optional: the count-in is cut off before analysis.)
- Keep the frontend's work small.

### Pipeline and owners

Each arrow is a JSON file. Stages 1 and 2–3 don't depend on each other; they meet at stage 4.

| # | Stage | Input → Output | Owner | Code |
|---|---|---|---|---|
| 1 | Score parsing (music21) | MusicXML → `expected_notes` | C | `backend/app/stages/score.py` |
| 2 | Pitch tracking (librosa pYIN) | WAV → `pitch_track` | B | `backend/app/stages/pitch.py` |
| 3 | Note segmentation | `pitch_track` → `sung_notes` | B | `backend/app/stages/segment.py` |
| 4 | Alignment (edit-distance DP) | `expected_notes` + `sung_notes` → `alignment` | C | `backend/app/stages/align.py` |
| 5 | Grading, score, patterns | `alignment` + notes → `results` | C | `backend/app/stages/grade.py` |
| 6 | LLM feedback + fallback | `results` → `feedback` | B | `backend/app/stages/feedback.py` |
| 7 | Frontend: record, draw, color | everything → the app | A | `frontend/` |

B also owns the API endpoints (`backend/app/main.py`).

**Who:** A = Jason, B = Jonathan, C = Mehul.

---

## 2. Stack and repo

| Part | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, music21, librosa, numpy; `venv` + `requirements.txt` |
| Frontend | React + Vite + TypeScript, OpenSheetMusicDisplay (OSMD) |
| LLM | Claude API (`anthropic` Python SDK) |
| Run | `npm run setup` once, then `npm run dev` from the repo root (both servers, one terminal) |
| Test audio | `npm run synth` (generated recordings + answer keys, see section 7) |
| Tests | pytest in `backend/tests/`; run `npm test` from the repo root |

Everyone is on macOS. Frontend calls `/api/*`; Vite proxies to the backend on port 8000.

**Working together:** nobody pushes to `main`. Work on a branch, open a PR.

---

## 3. Conventions (everyone, every file)

| Thing | Rule |
|---|---|
| Pitch | MIDI number; C4 = 60. Decimal for sung pitch (60.22 = C4, 22 cents sharp). |
| Pitch deviations | cents (100 cents = 1 semitone); negative = flat |
| Times | seconds |
| Timing errors | milliseconds; positive = late |
| Beats | one beat = one quarter note, always (so 6/8 can't cause confusion) |
| Time zero | 0.0 s = the first beat after the count-in, in every file. Recordings without a count-in (uploads) start wherever the file starts; stage 4 measures how far the sung timeline is shifted from the score's (`time_offset_sec`, median of the matched notes) and removes it. Nothing earlier shifts times. (Was "the first sung note is beat 1": breaks on songs that open with rests, or a cough before the first note.) |
| Missing values | JSON `null`. Never `NaN`: Python's `json` writes it but the browser's `JSON.parse` crashes on it. |
| Note names | Written notes: spelled as in the score (`"F#4"`, `"Bb4"`). Sung notes (`sang`): sharps. |

### Note ID scheme

Every written note and rest gets an ID `m{measure}-n{index}`, e.g. `m3-n2` = bar 3, note #2.
The backend (stage 1, music21) and the frontend (OSMD) build these **independently**, so both
must count identically, or colors land on the wrong noteheads.

| Case | Rule |
|---|---|
| Bars | Numbered by **position in the file**, starting at 1. Ignore printed bar numbers (pickups are often printed as 0). |
| Index | Position within the bar in time order, starting at 0 |
| Rests | **Count.** They take an index (C, rest, E → E is `n2`). |
| Ties | One sung note. Both noteheads take an index, but there's **one entry**, with the first notehead's `id`. Every notehead's ID goes in `render_ids`. |
| Grace notes | **Skipped entirely**, take no index. OSMD still draws them, so the frontend must skip them when counting. |
| Chords | Top note only; the chord takes one index. |
| Parts / voices | First part, voice 1 only. |

Example (`samples/edge-cases`): the pickup bar is `m1`; a B4 tied from bar 4 into bar 5 is one
entry `m4-n2` with `render_ids: ["m4-n2", "m5-n0"]`, and the next note in bar 5 is `m5-n1`.

### How the frontend counts (OSMD)

The same rules, expressed in OSMD's data model. Reference implementation: `collectNoteIds()` in
[`tools/check_osmd_ids.mjs`](../tools/check_osmd_ids.mjs), written to be copied into the frontend.

| Rule | OSMD |
|---|---|
| Bars | `osmd.Sheet.SourceMeasures`, **index + 1**. Not `MeasureNumber` (that's the printed number: a pickup prints as 0). |
| Part / voice | `container.StaffEntries[0]` for each `measure.VerticalSourceStaffEntryContainers` (first staff of the first instrument), then `VoiceEntries` whose `ParentVoice.VoiceId === 1` (if the bar has no voice 1: the first voice in it) |
| Index | One per voice entry, in container order (time order), from 0 |
| Grace notes | Skip voice entries with `IsGrace` |
| Rests | `note.isRest()`; they take an index |
| Chords | One voice entry with several `Notes`: one index; top note = highest `Pitch.getHalfTone()` |
| Ties | Top note's `NoteTie` exists and `NoteTie.StartNote !== note` → continuation: takes an index, its ID goes in the previous entry's `render_ids`, no entry of its own |
| Pitch / time (only for checking) | MIDI = `Pitch.getHalfTone() + 12`; onset beats = `(measure.AbsoluteTimestamp + container.Timestamp).RealValue × 4` (OSMD counts in whole notes) |
| Noteheads to color | `osmd.EngravingRules.GNote(note)` → `GraphicalNote`; `getSVGGElement()` is its SVG |

**Required option:** `autoGenerateMultipleRestMeasuresFromRestMeasures: false`. OSMD's default draws
several empty bars in a row as one multi-bar rest, and those rests then have no notehead (an extra
sung during them would have nowhere to show its `+`).

**Verified** with `npm run check:osmd-ids`: real OSMD (2.3.1, in Node) on both samples, six
real-world files and `rest-bars`. IDs identical to stage 1 and every ID has a drawn notehead. Re-run
it after upgrading OSMD or changing either side's counting.

---

## 4. Contracts (JSON hand-offs)

Samples for every file are in [`contracts/`](../contracts/). They're consistent with each other:
together they are what `/analyze` should return for `samples/c-major-scale/takes/mistakes.wav`.
Build against the samples until the real stage exists.

### 4.1 `expected_notes.json` (stage 1 → 4, 5, 6, 7)

Top level: `title` (string|null), `tempo_bpm` (number: the first tempo, after any override; later tempo marks are followed in `onset_sec`), `beat_unit`
(always `"quarter"`), `notes` (every note **and rest**, in time order).

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `m{measure}-n{index}` |
| `measure` | int | Bar number in file order, from 1 |
| `index` | int | Position in the bar, from 0 |
| `is_rest` | bool | |
| `midi` | int\|null | null for rests |
| `name` | string\|null | As written (`"F#4"`); null for rests |
| `onset_beats`, `duration_beats` | float | From the start of the piece |
| `onset_sec`, `duration_sec` | float | Same in seconds. Every tempo mark in the score is followed (any part; on the same beat the sung part wins): seconds are added up stretch by stretch. |
| `lyric` | string\|null | |
| `render_ids` | string[] | Noteheads to color: `[id]`, or several for ties |
| `fermata` | `true` | Optional, only on fermata entries (notes **or rests**). A fermata in **any** part counts (if the piano holds while the voice rests, the singer waits too); the entry containing the end of the held note is flagged. Stage 4 starts a new timing section after it. |

### 4.2 `pitch_track.json` (stage 2 → 3, 7)

Columns, not a list of objects (half the size, maps straight to numpy and to charts).
All arrays have the same length.

| Field | Type | Meaning |
|---|---|---|
| `sample_rate` | int | 16000 |
| `hop_sec` | float | 0.01 |
| `audio_offset_sec` | float | Seconds cut from the start of the original recording (count-in). Original time = `t + audio_offset_sec`. |
| `duration_sec` | float | Length after trimming |
| `t` | float[] | Frame center times; 0.0 = beat 1 |
| `midi` | (float\|null)[] | Raw pitch (no octave shift). null when unvoiced. |
| `voiced` | bool[] | pYIN voiced flag |
| `conf` | float[] | 0–1 (pYIN voiced probability) |
| `rms` | float[] | Loudness of the normalized audio |

**Why 16 kHz, not 22,050 Hz:** at 22,050 Hz a 10 ms hop is 220.5 samples, which rounds to 220
(9.98 ms). Over 30 s that drifts ~70 ms from the score, enough to make notes look late. At
16 kHz, 10 ms is exactly 160 samples; it's also CREPE's native rate.

### 4.3 `sung_notes.json` (stage 3 → 4, 5, 7)

`notes` in time order, never overlapping; optional `params` (the tuning knobs used, for debugging).

| Field | Type | Meaning |
|---|---|---|
| `sid` | string | `s0`, `s1`, … from 0 |
| `start_sec`, `end_sec` | float | First/last frame of the note. Same timeline as `pitch_track.t`. Start = first voiced frame; no adjustment for consonants (stage 5 handles that). |
| `midi` | float | Median of the middle ~60% (ignores scoops). Raw, no octave shift. |
| `stability_cents` | float | Std dev of pitch over that middle 60% |
| `conf` | float | Mean `conf` over the note's frames |

### 4.4 `alignment.json` (stage 4 → 5)

| Field | Type | Meaning |
|---|---|---|
| `octave_shift` | int | −24, −12, 0, +12 or +24 (±24: e.g. a soprano singing a bass line). Chosen by a pitch-only first pass run once per shift: the shift whose pairing costs least; on a tie the smallest shift. Stage 5 subtracts it from sung pitch. Non-octave shifts (another key) are not detected: that's nice-to-have "any-key transposition". |
| `tempo_scale` | float | The singer's speed: score time = (sung time − `time_offset_sec`) × `tempo_scale` (0.75 = sang at ¾ of the written tempo). Always 1.0 in strict mode. Free mode: a line sung = offset + slope × written fitted through the same near-right pairs as the offset, outlier-resistant (slope = median of the slopes between every two points; offset = median of the leftovers); `tempo_scale` = 1 / slope. Fewer than 3 pairs, or a speed outside 0.4–2.5: falls back to the strict clock (1.0, median offset). One straight line for the whole take: gradual slowing is left to stage 5's local check. |
| `time_offset_sec` | float | Subtracted from sung times before aligning: median of (sung start − written start) over near-right matches (within 0.5 semitone, i.e. not wrong notes) from a pitch-only first pass; 0 if fewer than 3. Covers upload lead-in silence and recording delay. `sung_notes` itself is not changed. **Fermatas:** the singer's clock jumps by the hold, so the score is cut into sections after each `fermata` entry and each section gets its own offset (fewer than 3 near-right pairs in a section: it borrows the previous section's). This top-level value is the first section's; then every `match` also carries its own `time_offset_sec`. In free mode the speed is shared, fitted only from pairs within the same section. Scores without fermatas: one section, no per-match field. |
| `total_cost` | float | Debug only |
| `pairs` | array | Score order; extras placed where they happened. **Rests never appear.** |

Each pair:

| Field | Type | Meaning |
|---|---|---|
| `type` | `match` \| `skipped` \| `extra` | |
| `id` | string\|null | Written note; null for extras |
| `sids` | string[] | `match`: 1+ (more than one = split-note merge), `skipped`: empty, `extra`: exactly 1. Every sung note appears in exactly one pair, except that a `joined` pair reuses its neighbour's sid. |
| `cost` | float | Optional, debug |
| `near_id` | string | Extras only: the note **or rest** whose time span contains the extra's start, else the nearest onset |
| `joined` | `true` | Optional, matches only: this written note had no sung note of its own. Its neighbour, the **same written pitch**, was sung as one long note that stays in tune (within 0.5 semitone) and lasts through at least half of this note (on the score's clock): e.g. written G G sung legato. `sids` = that neighbour's sung note. Stage 5 grades its pitch; its timing is `null` (no separate start to measure). |

**Split-note merge:** if stage 3 cut one sung note in two, stage 4 pairs both pieces with one
written note (`"sids": ["s1", "s2"]`). Stage 5 then uses start of the first piece, end of the
last, and the duration-weighted average pitch.

Rule (starting values, constants in `align.py`): an extra joins the match right before or after it
when it is within **1 semitone** of that match's nearest sung piece (short pieces of one vibrato note
can land ~1 semitone apart), with at most **0.2 s** of silence between them, and is no closer in pitch
to the written notes either side than to this one (so a note sliding toward the next written note
stays with that note). Repeats until nothing changes (3+ pieces → one match). Inside the table, a sung
note that looks like a piece of its sung neighbour costs **0.5** as an extra instead of 3; otherwise the
table would rather shift every later pairing by one note than pay for it. Not merged: grace notes and
ornaments sung correctly (stage 1 skips grace notes, so they show as extras), and the opposite stage 3
error (two written notes joined into one sung note) is handled separately: see `joined` above.

**Costs (starting values, tune on test takes):** pair = semitones apart (capped at 4) + 0.5 ×
beats apart (seconds apart × that written note's own beats per second, so tempo changes are
respected); skip = extra = 3. A 1–2 semitone error must cost less than skip + extra (6), so a
wrong-but-present note is reported as "wrong note", not skip + extra.

**DTW fallback:** only if stage 3 proves unreliable. DTW would also output its own
`sung_notes`-shaped list plus this same `alignment.json`, so stages 5–7 don't change.

### 4.5 `results.json` (stage 5 → 6, 7; returned by `/analyze`)

| Field | Meaning |
|---|---|
| `meta` | `title`, `mode`, `preset`, `tempo_bpm`, `octave_shift`, `timing_offset_ms` (the median offset that was subtracted) |
| `score` | `total`, `pitch`, `intonation`, `rhythm`, `completeness`: ints 0–100 |
| `counts` | `notes`, `in_tune`, `out_of_tune`, `wrong_note`, `skipped`, `extra`, `early`, `late`, `uncertain` |
| `notes` | **One entry per written note (not rests)**, in score order. Fields below. |
| `extras` | `sid`, `near_id`, `sang`, `during_rest` (= `near_id` is a rest), `start_sec`, `end_sec` |
| `patterns` | `worst_measures` (int[]), `drift_cents` {`first_third`, `last_third`}, `high_notes_flat` (bool), `timing_tendency` (`rushing`\|`dragging`\|`steady`), `shaky_long_notes` (ids), `errors_after_leaps` (ids). C owns the exact rules; field names are fixed. |

Each entry in `notes`:

| Field | Type | Meaning |
|---|---|---|
| `id`, `measure`, `name`, `lyric` | | Copied from `expected_notes`, so hover text and stage 6 need no second file |
| `status` | `in_tune` \| `out_of_tune` \| `wrong_note` \| `skipped` | **Pitch** verdict; decides the notehead color |
| `cents` | float\|null | (sung − octave_shift − written) × 100. Negative = flat. null if skipped. |
| `sang` | string\|null | Nearest note name actually sung (after octave shift) |
| `timing` | `on_time` \| `early` \| `late` \| null | **Timing** verdict, separate from pitch. null if skipped or `joined` (no separate start). |
| `timing_ms` | int\|null | After subtracting the median offset; positive = late |
| `sung_start_sec`, `sung_end_sec` | float\|null | Where it is in the recording (for click-to-hear). Merged span for split notes. |
| `uncertain` | bool | Low confidence: still gets a status, excluded from the score, drawn faded |

**Verdict rules (starting values):**

| Check | Rule | Verdict |
|---|---|---|
| Pitch | within ±25 cents | `in_tune` |
| Pitch | 25–50 cents | `out_of_tune` |
| Pitch | over 50 cents | `wrong_note` (+ `sang`) |
| Timing | within ±max(⅛ beat, 80 ms) | `on_time` (±94 ms at 80 BPM) |
| Timing | outside | `early` / `late` |

Strict mode measures timing against the score's tempo (stage 1 onsets; the singer heard it only in the
count-in). Free mode measures against a
line fit through ~4 neighbors on each side. Both subtract the singer's median offset first
(browser recording delay of 50–150 ms + consonant-before-vowel, or an upload's lead-in silence):
that offset is `alignment.time_offset_sec` (or the pair's own `time_offset_sec` when present, in
scores with fermatas), so stage 4 and 5 use the same number. After a fermata the next notes are judged
from where the singer came back in (like a conductor's new downbeat), not from the original timeline.

**Score weights (first guess):** pitch 40% (% of notes on the right note), intonation 20% (avg
cents off on right notes: 0 → 100, 50 → 0), rhythm 25% (% of matched notes on time),
completeness 15% (% not skipped, minus a small penalty per extra).
**Pitch should count more** (decided 2026-11-14): e.g. pitch 50 / intonation 25 / rhythm 15 /
completeness 10. Exact numbers are set when stage 5 is built.

Optional presets: beginner ±35 cents / ±¼ beat; advanced ±15 cents / ±1/16 beat.

### 4.6 `feedback.json` (stage 6 → 7; returned by `/feedback`)

| Field | Type | Meaning |
|---|---|---|
| `source` | `llm` \| `fallback` | Who wrote it |
| `summary` | string | One sentence |
| `strengths` | string[] | 1–2 |
| `tips` | array, max 3 | Most important first: `title`, `explanation`, `exercise`, `measures` (int[], may be empty; clicking a tip highlights these bars) |

Under 150 words total. Every `measures` entry must be a real bar. The fallback returns the same shape.

---

## 5. API

### `POST /analyze` (stages 1–5)

Multipart form:

| Field | Type | Notes |
|---|---|---|
| `musicxml` | file | `.musicxml`, `.xml`, `.mxl`. Any saved file name works: stage 1 reads by content (a zip = compressed `.mxl`). |
| `audio` | file | **Always WAV.** Browsers record WebM (Chrome) or MP4 (Safari); librosa can't read those without ffmpeg. The frontend converts any recording or upload to WAV with the Web Audio API first. |
| `mode` | `strict` \| `free` | default `free` (the main mode) |
| `tempo_bpm` | number, optional | missing = the score's marking. Given: every tempo mark is scaled by the same factor so the first one becomes this (80 → 120 later becomes 120 → 180). Must be > 0 (validate in the endpoint: `Form(None, gt=0)`). |
| `preset` | `default` \| `beginner` \| `advanced` | default `default` |
| `countin_end_sec` | number | where beat 1 is in the recording; 0 for uploads |

Response: `{"results": …, "expected_notes": …, "sung_notes": …, "pitch_track": …}`. The pitch
view needs the last three, and it makes debugging easy. `alignment` isn't returned; everything
the UI needs from it is in `results`.

### `POST /feedback` (stage 6)

Body: the `results` object. Response: `feedback.json`. **Always 200.** On any failure (no key,
timeout ~15 s, bad output) it returns the rule-based fallback with `"source": "fallback"`.
It's a separate call so the colored score appears before the AI feedback is ready.

### Errors (`/analyze`)

```json
{"error": {"code": "no_voice_detected", "message": "No singing found in the recording.", "stage": "pitch"}}
```

| Status | When |
|---|---|
| 400 | bad input |
| 422 | input fine, but analysis can't proceed |
| 500 | our bug |

Codes: `invalid_musicxml`, `invalid_audio`, `no_voice_detected`, `invalid_input`, `internal_error`.

`invalid_input` (400, `stage: "api"`) = a form field failed validation before any stage ran: missing
file, `mode`/`preset` not one of the allowed values, `tempo_bpm` ≤ 0 or not a number, `countin_end_sec` < 0.
`message` names the field (`"tempo_bpm: Input should be greater than 0"`). FastAPI would otherwise answer
these with its own `{"detail": [...]}` 422; `main.py` converts them so there is only one error shape.

`stage` says whose code failed. `message` can be shown to the user. In code: raise
`AnalysisError(code, message, stage, status)` from `app.errors` (its own module, so stages
can import it without a circular import through `app.main`).

### Claude API (stage 6)

- Model **`claude-sonnet-5-5`** at low effort (short task). Switched from Opus for lower latency/cost on this short coaching task.
- Structured output with the `feedback.json` schema, so the reply is always valid JSON in the right shape.
- System prompt: supportive vocal coach, use ONLY the given facts, never invent errors or numbers, max 3 tips, under 150 words.
- Send only: `meta`, `score`, `counts`, `patterns`, `extras`, and problem notes (not `in_tune`+`on_time`), max 30.
- Key: `ANTHROPIC_API_KEY` in `backend/.env` (gitignored; template in `backend/.env.example`).

---

## 6. How results show on the score

| Result | Display |
|---|---|
| In tune | green notehead |
| Out of tune | yellow + ↑/↓ arrow |
| Wrong note | red + "sang C#4" label |
| Early / late | small marker above the note (color stays with pitch) |
| Skipped | grey or hollow notehead + ✕ |
| Extra | small red + next to `near_id` (over the rest if it was during a rest) |
| Uncertain | its status color, faded |

Hover: exact numbers ("D5 · 38 cents flat · 140 ms late"). Color every ID in `render_ids`.

---

## 7. Test recordings

`npm run synth` generates, for every `samples/*/score.musicxml`, four takes in
`samples/<piece>/takes/` (WAV + `.answer.json`):

| Take | What's in it | Expected |
|---|---|---|
| `perfect` | sung exactly as written | all `in_tune`, all `on_time` |
| `mistakes` | one wrong note, one flat (−35 cents), one late (+200 ms), one early (−200 ms), one skipped, one extra | each caught, rest green |
| `octave-down` | perfect, an octave lower | all green; `octave_shift` −12 |
| `delayed` | perfect, everything 120 ms late | all `on_time`; `timing_offset_ms` ≈ 120 |

The audio is voice-like (harmonics, vibrato ±30 cents at 5.5 Hz, 40-cent scoop into each note,
breath gaps, light noise). Every take starts with one silent bar of count-in; `countin_end_sec`
is in the answer key. `--clean` writes pure-tone versions to `takes-clean/` (not committed).

Answer key format: `settings` (what to send to `/analyze`), `expect` (`octave_shift`,
`timing_offset_ms`), `notes` (id → `status`, `timing`, plus `sang`/`cents` where planted),
`extras` (`near_id`, `during_rest`, `sang`).

Pieces: `c-major-scale` (simplest), `edge-cases` (pickup bar, rests, tie across a barline,
repeated notes, 7-semitone leap). **After any change to stages 2–5, run every take:** `perfect`
stays green and every planted mistake is still caught. (`tools/check_takes.py` to automate this
is planned once the real pipeline exists.)

Known quirk: in `octave-down`, pYIN marks a few noise frames during rests as voiced (conf ≈ 0.01,
~1% of singing loudness). Stage 3's confidence cutoff must drop them.

---

## 8. Still open

- **Decision maker** for cuts when time runs short.
- **Demo pieces:** 1–2 real pieces (slow, no repeats, few repeated same-pitch notes) + real recordings of them sung well and with deliberate mistakes.

### Nice-to-haves

The list (with details and owners) lives in [`NICE_TO_HAVE.md`](NICE_TO_HAVE.md). New ideas go there.

### If behind schedule, cut in this order

retry-a-bar, "ask the coach", playback highlight → pitch view → strict mode (keep free, the main mode) →
the LLM call (fallback covers it) → in-app recording (upload only).
**Never cut:** the colored score, the error types, the overall score.

---

## 9. Known limitations

What the pipeline gets wrong or doesn't check today. Pick demo pieces and recordings around these;
update this list when one is fixed.

| Case | What happens | Workaround / plan |
|---|---|---|
| **Fermatas** (handled) | Each section between fermatas gets its own clock. A section with < 3 near-right notes borrows the previous section's offset, so a hold just before the last 1–2 notes still makes them look late. Coming back in late after a fermata isn't flagged (by design). | Fermatas on a barline (rare) aren't read |
| **"rit." / "accel." text** (amount not written) | Strict mode marks the slowed/sped notes late/early | Use free mode for such pieces (it follows the singer's local pulse) |
| **Fast runs, melismas** (notes under ~150 ms) | Stage 3 needs a pitch held ≥ 50 ms and drops pieces < 80 ms → notes blur: skips, odd pitches | Slow demo pieces; stage 3 tuning |
| **Grace notes, trills, turns sung correctly** | Stage 1 skips grace notes (no ID) → the sung ornament shows as **extra** | Avoid in demo pieces |
| **Slides between notes** (portamento) | May become a short in-between extra, or make the next note look early | Split-note merge covers part of it |
| **Note length / releases** | Only note **starts** are graded; cutting a note short or holding into a rest isn't caught | Possible stage 5 addition |
| **Repeats, endings, D.C.** | Not unfolded: the second pass shows as extras | Nice-to-have #4; demo pieces without repeats |
| **Other parts / divisi** | First part, voice 1, top note only | Nice-to-have "choose which part to sing" |
| **Singing in another key** (not an octave) | Every note "wrong": only octave shifts (±12, ±24) are detected | Nice-to-have #11 (play the starting pitch); #8 any-key transposition |
| **Switching octave mid-piece** | One shift for the whole recording → the other-octave notes are "wrong note, sang X" | Accepted (it is what they sang) |
| **Coming in a whole bar late, then staying in time** (strict) | The median offset removes it, so everything looks on time | Stage 5 decision (could report the offset) |
| **Notes outside C2–C6** (65–1050 Hz) | Not heard → skipped | Rare outside opera |
| **Lyrics / diction, tone, breathing** | Not checked at all | Nice-to-have #9 |
