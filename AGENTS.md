# AGENTS.md: instructions for AI assistants working on Gensing

This file is for any AI model (Claude, GPT, Gemini, Copilot, Cursor, ...) helping on this repo.
It explains what the project is, what has been built, every decision made so far **and why**, and
what is expected next. Read it fully before changing anything.

Last updated: 2026-11-14 (roles assigned, pytest added; before any real pipeline code).

---

## 0. Read these first

1. **This file**: context, reasoning, rules.
2. **[`docs/DECISIONS.md`](docs/DECISIONS.md)**: the spec. Exact JSON fields, API, conventions, note ID rules. **The source of truth.** If this file and DECISIONS.md disagree, DECISIONS.md wins.
3. **[`contracts/`](contracts/)**: one sample JSON per hand-off file, all consistent with each other.
4. **[`docs/gensing.pdf`](docs/gensing.pdf)**: the original design notes (17 pages): pipeline, stages, scope, risks, nice-to-haves.
5. **[`docs/Alignment Explained Costs, Dynamic Programming, and DTW.pdf`](docs/)**: stage 4 in depth (penalties, DP table, reference code, DTW as fallback).
6. **[`docs/NICE_TO_HAVE.md`](docs/NICE_TO_HAVE.md)**: the live nice-to-have list (the PDF's 10, plus new ideas). Add new ideas there, not to the PDF.

The PDFs are the original plan. DECISIONS.md refines them; where they differ, DECISIONS.md is newer
and was agreed deliberately (each difference and its reason is listed in section 4 below).

---

## 1. The project in one paragraph

**Gensing** is a singing-feedback web app built for HackUMass XIV (team of 3, 24 hours). A singer
uploads a MusicXML score, records themselves singing it (record first, analyze after; no live
feedback), and gets the sheet music back with every note colored: in tune, out of tune, wrong
note, early/late, skipped, or extra. They also get an overall score (total + pitch, intonation,
rhythm, completeness) and short AI coaching tips. One singing voice, no instruments, MusicXML
input only. Two timing modes: **strict** (against a click track, build first) and **free**
(against the singer's own tempo).

**The demo must show:** a colored score with the error types, plus the overall score. Everything
else is secondary.

---

## 2. Architecture

```
MusicXML ──► [1 score parse] ──► expected_notes ─┐
                                                  ├─► [4 align] ─► alignment ─► [5 grade] ─► results ─► [6 LLM] ─► feedback
WAV ──► [2 pitch track] ──► pitch_track ──► [3 segment] ──► sung_notes ─┘                         │                    │
                                                                                                  ▼                    ▼
MusicXML (drawn separately in the browser by OSMD) ─────────────────────────────────────► [7 frontend: colored score + score card + coach]
```

- Each arrow is a JSON file with a locked format (`contracts/`). **The JSON files are the only
  connections between people**, so each person can work against a sample until the real
  upstream stage exists.
- Stages 1 and 2–3 are independent; they meet at stage 4.
- The frontend draws the MusicXML itself (OSMD → SVG) and colors noteheads using IDs from the
  backend. **Both sides must build note IDs identically** (see section 5); this is the
  single most important integration point.
- The LLM (stage 6) never analyzes anything. Stage 5 computes all numbers and patterns; the LLM
  only turns them into readable coaching. LLMs are bad at arithmetic and may invent trends.

### Owners

| Role | Person | Stages | Owns |
|---|---|---|---|
| A: Frontend | Jason | 7 + in-app recording | `frontend/` |
| B: Audio + server | Jonathan | 2, 3, 6 + API | `pitch.py`, `segment.py`, `feedback.py`, `main.py` |
| C: Music logic | Mehul | 1, 4, 5 | `score.py`, `align.py`, `grade.py` |

When you work on a stage, stay inside its files
unless the task requires otherwise, and say so when you touch someone else's.

---

## 3. Repo map and commands

```
AGENTS.md            this file
CLAUDE.md            points Claude Code at this file
README.md            human quickstart
package.json         root scripts: setup / dev / synth (uses `concurrently`)
backend/
  requirements.txt   pinned: fastapi, uvicorn, python-multipart, music21, librosa, numpy, anthropic, python-dotenv, pytest
  pytest.ini         test config: tests/ folder; backend/ and tools/ on the import path
  tests/             pytest unit tests (run with `npm test`)
  tests/synth_sung.py  load_take(piece, take): perfect sung_notes + answer key per take (tests stages 4-5 without 2-3)
  tests/manual/      inspect_score.py (look at stage 1 by eye) + fixtures/; downloads/ is gitignored
  .env.example       ANTHROPIC_API_KEY= (copy to backend/.env, which is gitignored)
  app/main.py        FastAPI: /health, /analyze, /feedback, AnalysisError handler
  app/errors.py      AnalysisError (stages import it from here, not from main)
  app/stages/        score.py pitch.py segment.py align.py grade.py feedback.py (stubs)
frontend/            React + Vite + TS; src/App.tsx (dev page), src/components/ScoreView.tsx (OSMD), src/lib/api.ts
contracts/           *.sample.json for all six hand-offs + README
samples/<piece>/     score.musicxml + takes/ (generated WAVs + answer keys)
tools/synth_take.py  generates the test recordings
tools/check_osmd_ids.mjs  proves stage 1 IDs match OSMD's (collectNoteIds() = the frontend's counting recipe)
docs/                DECISIONS.md, NICE_TO_HAVE.md, the two design PDFs
```

| Command (repo root) | Does |
|---|---|
| `npm run setup` | once: root deps, `backend/.venv` + pip install, frontend npm install |
| `npm run dev` | backend (:8000, reload) + frontend (:5173) in one terminal, logs prefixed `[api]` / `[web]` |
| `npm run dev:backend` / `npm run dev:frontend` | one side only |
| `npm run setup:backend` | re-run after `requirements.txt` changes |
| `npm test` | run the backend unit tests (pytest; extra args: `npm test -- -k score`) |
| `npm run check:osmd-ids [-- <name>]` | proves stage 1 IDs == OSMD's IDs and every ID has a drawn notehead (real OSMD in Node via jsdom). `--osmd-defaults` shows the multi-rest problem. |
| `npm run inspect:score -- <name> [--bars 3-5]` | stage 1 by eye: real MusicXML bars next to `parse_score` output, plus an independent raw-XML check (no args lists names; `all` checks every file). Not a pytest test. |
| `npm run synth` | regenerate all test takes (`-- --clean` for pure tones into `takes-clean/`) |
| `cd frontend && npm run build && npm run lint` | type-check, build, lint (oxlint) |

API docs while running: http://localhost:8000/docs. The frontend calls `/api/*`; Vite proxies
that to `localhost:8000` (strips `/api`). Backend Python is run as `backend/.venv/bin/python`.

---

## 4. Everything decided so far, and why

### 4.1 Setup

| Decision | Why |
|---|---|
| Monorepo: `backend/`, `frontend/`, `contracts/`, `samples/`, `tools/`, `docs/` | One place for the contracts both sides depend on |
| Frontend: React + Vite + TypeScript | Fast dev server, types help with the JSON contracts, OSMD works with any framework |
| Backend: FastAPI | Simple, auto API docs, handles multipart uploads |
| Python env: plain `venv` + `requirements.txt` (not uv/poetry) | Familiar to everyone; team chose it |
| Pinned versions in `requirements.txt` | Everyone gets identical behavior; no "works on my machine" mid-hackathon |
| One command `npm run dev` (via `concurrently`) | Nobody has to juggle two terminals; if one server crashes on startup the other stops too (`--kill-others-on-fail`) |
| macOS-only scripts (`.venv/bin/...`) | Whole team is on Mac; no Windows shims needed |
| Vite proxy `/api` → `:8000` + CORS for `localhost:5173` | No CORS issues in dev; the frontend code never hardcodes the backend URL |
| Endpoints and stages are **stubs** | `/analyze` and `/feedback` return the contract samples so the frontend can be built on day one. Each stage function has its real signature and raises `NotImplementedError` until its owner fills it in. Separate files per stage avoid merge conflicts. |
| `.gitignore`: venvs, node_modules, dist, caches, `.env*` (except `.env.example`), logs, `.DS_Store`, editors, `backend/tmp/`, `samples/*/takes-clean/` | Keep the repo to source only; never commit secrets |

### 4.2 Contracts (full field tables in DECISIONS.md section 4)

| Decision | Why |
|---|---|
| **Note IDs:** `m{measure}-n{index}`, bars counted by **file position from 1** (ignore printed numbers) | Pickup bars are printed as 0 or 1 depending on the tool; file order is the one count both music21 and OSMD can reproduce exactly |
| Rests take an index | They're kept anyway (to detect singing during a rest), and OSMD draws them too |
| Ties: one entry with the first ID; all notehead IDs in `render_ids` | The singer sings one note; both noteheads must still be colored |
| Grace notes: skipped, no index | Ornamental; we don't grade them. OSMD draws them, so the frontend must skip them when counting. |
| Chords: top note, one index | Shouldn't occur in one vocal line; deterministic if it does |
| First part, voice 1 only | One singer |
| `expected_notes`: added `title`, `beat_unit` ("quarter"), `index`, `duration_beats`; rest fields null | Title for feedback; fixed beat unit avoids 6/8 confusion; beats needed for alignment's timing term |
| `pitch_track`: **16 kHz**, hop exactly 10 ms | At 22,050 Hz a 10 ms hop = 220.5 samples → rounds to 220 → ~70 ms drift over 30 s (notes look late). 16 kHz is also CREPE's rate. |
| `pitch_track`: columns (`t`, `midi`, `voiced`, `conf`, `rms` arrays), not objects | Half the size, maps to numpy and charts directly |
| Unvoiced pitch = `null`, never `NaN` | pYIN returns NaN; Python's `json` writes `NaN`, which isn't valid JSON and crashes `JSON.parse` in the browser |
| `pitch_track.audio_offset_sec` | The browser keeps the untrimmed recording; click-to-hear needs to map back to it |
| `sung_notes`: `sid` from `s0`; pitch = median of middle 60%; `stability_cents` = std dev; optional `params` | Consistent 0-based numbering; scoops ignored; stage 5 needs an exact definition for "shaky"; params make tuning runs comparable |
| `alignment`: `sid` → **`sids` list** on every pair | Split-note merge (stage 3 cut one note in two) needs several sung notes per match; one uniform shape |
| `alignment`: `near_id` always set on extras, may be a **rest** | Frontend needs a place for the `+`; extra-during-rest is then just "near_id is a rest" |
| `alignment`: rests never in `pairs`; `cost`/`total_cost` for debugging | Matches the alignment PDF's code; costs help tuning |
| `results.notes`: **every** written note, not just problems | Frontend must color green notes too |
| `results`: pitch `status` and `timing` are separate fields | A note can be flat *and* late |
| `results`: dropped `direction` | Sign of `cents` already says flat/sharp; redundant fields drift apart |
| `results`: added `measure`, `name`, `lyric`, `sung_start_sec/end_sec`, `uncertain`, `meta`, `counts`, more `patterns` | Results is self-contained for hover text and stage 6; click-to-hear; score card needs no math |
| `feedback`: added `source` (`llm`/`fallback`); `measures` may be empty | Debugging and optional UI label; not every tip is about specific bars |

### 4.3 API (DECISIONS.md section 5)

| Decision | Why |
|---|---|
| Two endpoints: `/analyze` (stages 1–5) and `/feedback` (stage 6) | The colored score shows immediately; AI feedback loads after |
| `/analyze` returns `{results, expected_notes, sung_notes, pitch_track}` | Pitch view needs them; one request shows every stage when debugging (~150 KB) |
| Frontend **always sends WAV** | Browsers record WebM/MP4; librosa needs ffmpeg for those. Converting in the browser (Web Audio API) means one format and no ffmpeg on anyone's laptop. |
| Error shape `{"error": {code, message, stage}}`; 400 / 422 / 500 | One shape to handle; `stage` tells you whose code failed. Raise `AnalysisError` from `app.errors` (own module: `main` imports the stages, so importing from `main` would be circular). |
| `/feedback` always returns 200, falls back to rules | The demo survives Wi-Fi or API failure |
| Claude API, model `claude-sonnet-5-5`, low effort, structured output | The team chose Claude. Structured output guarantees the feedback JSON shape, so only the "bars exist" check remains. Switched from Opus to Sonnet for lower latency/cost on this short task. |
| Key in `backend/.env` (`ANTHROPIC_API_KEY`), loaded by `python-dotenv` in `main.py` | Never committed; `.env.example` documents it |

### 4.4 Test recordings (`tools/synth_take.py`, DECISIONS.md section 7)

| Decision | Why |
|---|---|
| Generate fake "sung" WAVs from MusicXML with **answer keys** | Guaranteed ground truth for stages 2–5 before anyone records real audio |
| Voice-like by default (10 harmonics, vibrato ±30 cents @ 5.5 Hz, 40-cent scoop over 60 ms, 30 ms attack, 40 ms release, 60 ms breath gap, light noise); `--clean` for pure sine | Pure tones are too easy and would hide stage 3 bugs; clean mode helps debugging |
| Takes: `perfect`, `mistakes`, `octave-down`, `delayed` | Cover: everything green; each mistake type; octave detection; recording-latency (median offset) removal |
| Mistakes picked automatically, spread through the piece, never first/last; wrong note picks a pitch different from both neighbours (+2, −2, +3, −3 semitones); extra goes in the first rest long enough to hold it, else after the last note | Works on any piece (including the future demo piece) without hand-editing |
| One silent bar of count-in in every take | Mimics an in-app recording; tests count-in trimming (`countin_end_sec` in the answer key) |
| Fixed seed; WAVs committed (~0.5–0.9 MB each) | Identical files for everyone; no regeneration needed |
| Its own small parser following the ID rules | Independent cross-check: stage 1's IDs must match the answer keys |
| `samples/edge-cases/score.musicxml` | Exercises every ID edge case: pickup (printed 0 → `m1`), rests, tie across a barline (`m4-n2` with `render_ids` `["m4-n2","m5-n0"]`), repeated G4s, 7-semitone leap, F# from the key signature |

Verified with pYIN (16 kHz, hop 160): every note reads within ~1 cent of its target; the planted
flat note measures about −31 cents (vibrato pulls it from −35; still inside the 25–50 band);
the wrong note, extra and skip appear where planted. Known quirk: in `octave-down`, pYIN marks a
few rest frames as voiced (conf ≈ 0.01, ~1% loudness). Stage 3's confidence cutoff must drop them.

### 4.5 Team workflow

- Nobody pushes to `main`. Work on a branch, open a PR. No further formal rules were adopted.
- Checkpoints/timeline were deliberately **not** planned in detail.

### 4.6 Still open (don't decide these on your own)

- Who makes the call on cuts.
- Demo pieces (one teammate is working on it). Criteria: slow, no repeats, few repeated same-pitch notes.
- Real recordings of the demo piece (sung well + with deliberate mistakes).

---

## 5. Rules for AI assistants on this repo

**Contracts and conventions**

1. **Never change a contract silently.** A field rename/removal/type change must update the sample in `contracts/`, `docs/DECISIONS.md`, and every producer/consumer in the same change, and should be flagged to the user. Adding an optional field is lower-risk but still goes in DECISIONS.md.
2. **Note IDs follow DECISIONS.md section 3 exactly**, in both `score.py` and the frontend. Don't "fix" the scheme locally on one side.
3. Units: MIDI for pitch, cents for deviations, seconds for times, ms for timing errors, quarter-note beats. Time zero = first beat after the count-in.
4. **No `NaN`/`Infinity` in JSON.** Convert to `null` before returning.
5. The LLM only explains facts computed by stage 5. Never move analysis into the prompt.

**Code**

6. Stay in your stage's file(s). Shared files (`main.py`, `requirements.txt`, `package.json`, `vite.config.ts`) get small, explained edits.
7. Keep stage functions pure-ish: dict in, dict out (contract-shaped). File I/O and HTTP stay in `main.py`.
8. Raise `AnalysisError(code, message, stage, status)` (`from app.errors import AnalysisError`) for user-facing failures in `/analyze`. `/feedback` must never error; it falls back.
9. Adding a Python dependency: pin it in `backend/requirements.txt` and tell the user to re-run `npm run setup:backend`.
10. Keep it simple; this is a 24-hour hackathon. Prefer the straightforward version that works over the general one.

**Verification**

11. After changing stages 2–5, run every take in `samples/*/takes/` through the pipeline and compare against its `.answer.json`: `perfect` must stay all green, every planted mistake must still be caught. (A `tools/check_takes.py` script to automate this is planned but not written yet; it's a good thing to build once stages are real.)
12. Plot before tuning: the pitch curve (stage 2) and detected notes over it (stage 3) are the main debugging tools.
13. Frontend: run `npm run build` and `npm run lint` in `frontend/`. Check note coloring against `contracts/` samples (real IDs from `c-major-scale`).

**Git and secrets**

14. Never commit to or push to `main`. Use a branch; the humans open/merge PRs. Don't commit or push unless asked.
15. Never commit `backend/.env` or any API key.

**Working with the team**

16. The user prefers to **discuss a plan before large changes** and to go one step at a time. For anything beyond a small, clearly scoped edit, propose first.
17. If you make or change a decision, record it in DECISIONS.md (the what) and, if it changes the reasoning, here (the why).

---

## 6. What's expected next, per stage

Each stage's "done" means: real output matching its contract, and the test takes behave as their answer keys say.

**Stage 1, score parsing (C)**: `parse_score(musicxml_path, tempo_bpm=None) -> expected_notes`.
music21: `converter.parse`, `parts[0]`, `getElementsByClass("Measure")` in file order, `voices[0]` if present,
`notesAndRests`; skip `duration.isGrace`; merge ties (`el.tie.type` in `stop`/`continue`). Onset = (measure.offset +
element.offset) beats. Verified: music21 gives the pickup bar offset 0 and the next bar offset 1.0 in
`edge-cases`. `tools/synth_take.py: parse_score` is a working reference for the ID rules. **First joint
test with A:** color every notehead from a real `expected_notes` for both sample pieces.

**Stage 2, pitch tracking (B)**: `track_pitch(wav_path, countin_end_sec) -> pitch_track`. Load mono at 16 kHz,
normalize, trim the count-in, `librosa.pyin(y, sr=16000, fmin=65, fmax=1050, hop_length=160)`, `hz_to_midi`, RMS with the
same hop. NaN → null. Switch to CREPE (torchcrepe tiny) only if curves are messy. Watch for octave jumps and noise frames.

**Stage 3, segmentation (B)**: `segment_notes(pitch_track) -> sung_notes`. Starting knobs: conf cutoff 0.5,
new note on a >0.5 semitone change held ≥50 ms, ~50 ms median filter, split repeats on loudness dips/onsets,
drop notes <80 ms, merge same-pitch neighbors with no real break. The most fragile stage; plot notes over the curve.

**Stage 4, alignment (C)**: `align(expected_notes, sung_notes, mode) -> alignment`. Filter out rests; detect octave
shift (most common sung−written gap rounded to −12/0/+12); free mode: scale times to the score's length;
edit-distance DP (reference code in the alignment PDF); split-note merge; set `near_id` on extras. First unit test:
written C D E vs sung C E → match, skipped, match.

**Stage 5, grading (C)**: `grade(alignment, expected_notes, sung_notes, mode, preset) -> results`. Subtract the
median timing offset, apply verdict rules and score weights (DECISIONS.md 4.5), compute patterns. Tune thresholds
on the test takes.

**Stage 6, feedback (B)**: `generate_feedback(results) -> feedback` with Claude (see 4.3) and `rule_based_feedback(results)`
(a few if-rules over `patterns`, ~20 minutes of work; build it first). Load the `claude-api` skill or official
Anthropic SDK docs before writing the API call; don't guess SDK signatures.

**Stage 7, frontend (A)**: Setup screen (upload MusicXML, mode/tempo/preset, or upload a recording), Record screen
(one-bar count-in, click via Web Audio API, MediaRecorder for the mic, headphones; send the exact `countin_end_sec`),
Results screen (colored score, score card, coach panel with clickable tips → highlight bars, optional pitch view).
Convert all audio to WAV before upload. Note IDs: copy `collectNoteIds()` from `tools/check_osmd_ids.mjs`
(already verified against stage 1; see DECISIONS.md section 3). **First task before any audio exists:** color every note from
`contracts/results.sample.json` (loaded with `samples/c-major-scale/score.musicxml`) and check each color and marker
lands on the right notehead. `api.ts` currently types responses as `any`; tighten to the contract shapes when convenient.

**Wiring (B)**: replace the stub bodies in `main.py` with the real calls (the TODO lists the order), saving
uploads to `backend/tmp/` (gitignored).

### Nice-to-haves (only after the core works end to end)

Full list with details and owners: [`docs/NICE_TO_HAVE.md`](docs/NICE_TO_HAVE.md). In priority order:
click a note to hear it → pitch view → beginner/advanced presets → repeats → playback highlight →
"ask the coach" → retry a bar → any-key transposition → lyrics/tone/breath analysis → OMR for
PDFs/photos. Not yet ranked: choosing which part to sing (today: first part only).

**If behind, cut in this order:** retry-a-bar, ask-the-coach, playback highlight → pitch view →
free tempo mode → the LLM call (fallback covers it) → in-app recording (upload only).
**Never cut:** the colored score, the error types, the overall score.

---

## 7. Gotchas already found

- **pYIN NaN → invalid JSON.** Always convert.
- **22,050 Hz hop drift.** Use 16 kHz / hop 160.
- **Browser audio isn't WAV.** Convert in the frontend.
- **Pickup bars are printed as 0** in MusicXML (`number="0" implicit="yes"`). Count by file position.
- **OSMD draws grace notes**; the frontend's ID counter must skip them.
- **OSMD merges empty bars into one multi-bar rest by default**, leaving those rests without a notehead. Set
  `autoGenerateMultipleRestMeasuresFromRestMeasures: false`. Counting recipe: DECISIONS.md section 3, "How the frontend counts".
- **Recording latency** (50–150 ms) makes everything look late in strict mode; stage 5 subtracts the median offset. The `delayed` take tests this.
- **Vibrato shifts measured pitch slightly** (planted −35 cents reads ≈ −31). Thresholds shouldn't sit right at a planted value.
- **Noise frames can be marked voiced** with near-zero confidence (see `octave-down`). Filter by `conf`.
- **Frontend bundle > 500 kB warning** comes from OSMD. Harmless.
- Local Python is 3.12; code should run on 3.11+.
