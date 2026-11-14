# Gensing: Decisions Before We Start

Everything the team agreed on before building, in one place. Read this before starting your part.
Background and the full pipeline design are in [`gensing.pdf`](gensing.pdf); stage 4 is explained
in depth in [`Alignment Explained Costs, Dynamic Programming, and DTW.pdf`](Alignment%20Explained%20Costs,%20Dynamic%20Programming,%20and%20DTW.pdf).

**Change these deliberately, not by drift.** If something here needs to change, change this doc
and `contracts/` in the same PR, and tell whoever reads the affected file.

---

## 1. What we're building

A singer uploads a MusicXML score, records themselves singing it, and gets the sheet music back
with every note marked: in tune, out of tune, wrong note, early/late, skipped, or extra. Plus an
overall score and short AI coaching tips. HackUMass XIV, team of 3, 24 hours.

**Must work in the demo:** a colored score showing the error types, plus the overall score.

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

B also owns the API endpoints (`backend/app/main.py`). Who is A, B and C is still open.

---

## 2. Stack and repo

| Part | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, music21, librosa, numpy; `venv` + `requirements.txt` |
| Frontend | React + Vite + TypeScript, OpenSheetMusicDisplay (OSMD) |
| LLM | Claude API (`anthropic` Python SDK) |
| Run | `npm run setup` once, then `npm run dev` from the repo root (both servers, one terminal) |
| Test audio | `npm run synth` (generated recordings + answer keys, see section 7) |

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
| Time zero | 0.0 s = the first beat after the count-in, in every file. For uploaded recordings, the first sung note is beat 1. |
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

---

## 4. Contracts (JSON hand-offs)

Samples for every file are in [`contracts/`](../contracts/). They're consistent with each other:
together they are what `/analyze` should return for `samples/c-major-scale/takes/mistakes.wav`.
Build against the samples until the real stage exists.

### 4.1 `expected_notes.json` (stage 1 → 4, 5, 6, 7)

Top level: `title` (string|null), `tempo_bpm` (number, the one actually used), `beat_unit`
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
| `onset_sec`, `duration_sec` | float | Same in seconds. Single tempo assumed. |
| `lyric` | string\|null | |
| `render_ids` | string[] | Noteheads to color: `[id]`, or several for ties |

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
| `octave_shift` | int | −12, 0 or +12. Stage 5 subtracts it from sung pitch. |
| `tempo_scale` | float | score time = sung time × `tempo_scale`. 1.0 in strict mode. |
| `total_cost` | float | Debug only |
| `pairs` | array | Score order; extras placed where they happened. **Rests never appear.** |

Each pair:

| Field | Type | Meaning |
|---|---|---|
| `type` | `match` \| `skipped` \| `extra` | |
| `id` | string\|null | Written note; null for extras |
| `sids` | string[] | `match`: 1+ (more than one = split-note merge), `skipped`: empty, `extra`: exactly 1 |
| `cost` | float | Optional, debug |
| `near_id` | string | Extras only: the note **or rest** whose time span contains the extra's start, else the nearest onset |

**Split-note merge:** if stage 3 cut one sung note in two, stage 4 pairs both pieces with one
written note (`"sids": ["s1", "s2"]`). Stage 5 then uses start of the first piece, end of the
last, and the duration-weighted average pitch.

**Costs (starting values, tune on test takes):** pair = semitones apart (capped at 4) + 0.5 ×
beats apart; skip = extra = 3. A 1–2 semitone error must cost less than skip + extra (6), so a
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
| `timing` | `on_time` \| `early` \| `late` \| null | **Timing** verdict, separate from pitch. null if skipped. |
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

Strict mode measures timing against the click (stage 1 onsets). Free mode measures against a
line fit through ~4 neighbors on each side. Both subtract the singer's median offset first
(browser recording delay of 50–150 ms + consonant-before-vowel).

**Score weights (first guess):** pitch 40% (% of notes on the right note), intonation 20% (avg
cents off on right notes: 0 → 100, 50 → 0), rhythm 25% (% of matched notes on time),
completeness 15% (% not skipped, minus a small penalty per extra).

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
| `musicxml` | file | `.musicxml`, `.xml`, `.mxl` |
| `audio` | file | **Always WAV.** Browsers record WebM (Chrome) or MP4 (Safari); librosa can't read those without ffmpeg. The frontend converts any recording or upload to WAV with the Web Audio API first. |
| `mode` | `strict` \| `free` | default `strict` |
| `tempo_bpm` | number, optional | missing = the score's marking |
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

Codes: `invalid_musicxml`, `invalid_audio`, `no_voice_detected`, `internal_error`.
`stage` says whose code failed. `message` can be shown to the user. In code: raise
`AnalysisError(code, message, stage, status)` from `app.main`.

### Claude API (stage 6)

- Model **`claude-opus-5-5`** at low effort (short task). Switch to a faster model only if latency is a problem.
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

- **Roles:** who is A, B, C.
- **Decision maker** for cuts when time runs short.
- **Demo pieces:** 1–2 real pieces (slow, no repeats, few repeated same-pitch notes) + real recordings of them sung well and with deliberate mistakes.

### If behind schedule, cut in this order

retry-a-bar, "ask the coach", playback highlight → pitch view → free tempo mode (keep strict) →
the LLM call (fallback covers it) → in-app recording (upload only).
**Never cut:** the colored score, the error types, the overall score.
