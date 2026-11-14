# Gensing

Singing feedback app (HackUMass XIV). Upload a MusicXML score, record yourself singing it,
and get the sheet music back with every note marked: in tune, out of tune, wrong, early/late,
skipped or extra, plus an overall score and short AI coaching tips.

- **Start here:** [`docs/DECISIONS.md`](docs/DECISIONS.md): formats, API, conventions agreed before building.
- Original design: [`docs/PIPELINE_NOTES.md`](docs/PIPELINE_NOTES.md); stage 4 in depth: [`docs/ALIGNMENT_EXPLAINED.md`](docs/ALIGNMENT_EXPLAINED.md).
- AI assistants: [`AGENTS.md`](AGENTS.md) explains everything done so far and why.

## Repo layout

```
backend/     FastAPI + the analysis pipeline (Python)
  app/main.py          /health, /analyze, /feedback
  app/stages/          one module per pipeline stage (owner in each docstring)
frontend/    React + Vite + TypeScript, OpenSheetMusicDisplay for the score
contracts/   sample JSON for every hand-off between stages
samples/     test pieces: <piece>/score.musicxml + generated takes/
tools/       dev scripts (synth_take.py generates test recordings)
docs/        design notes
```

## Run locally

Prereqs: Python 3.11+ and Node 20+.

From the repo root:

```bash
npm run setup   # once: root tools, backend venv + pip install, frontend npm install
npm run dev     # starts backend and frontend together; Ctrl+C stops both
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000 (interactive API docs at http://localhost:8000/docs)

Logs from both are shown in one terminal, prefixed `[api]` and `[web]`.
To run just one side: `npm run dev:backend` or `npm run dev:frontend`.
After someone adds a Python package to `backend/requirements.txt`, re-run `npm run setup:backend`.

The frontend calls `/api/*`, and Vite proxies it to the backend on port 8000.
Load `samples/c-major-scale/score.musicxml` to check that the score renders.

## Test recordings

`npm run synth` regenerates fake "sung" recordings for every `samples/*/score.musicxml`,
each with an answer key of what `/analyze` should report:

| Take | What's in it | Expected result |
|---|---|---|
| `perfect` | sung exactly as written | all in tune, all on time |
| `mistakes` | one wrong note, one flat, one late, one early, one skipped, one extra | each mistake caught, everything else green |
| `octave-down` | perfect, an octave lower | all green (octave shift −12) |
| `delayed` | perfect, everything 120 ms late | all on time (median offset ≈ 120 ms) |

Every take starts with one silent bar of count-in (`countin_end_sec` is in its answer key).
The audio is voice-like (vibrato, scoops, breath gaps, light noise); `npm run synth -- --clean`
writes pure-tone versions to `takes-clean/` for debugging.

Pieces: `c-major-scale` (simplest case) and `edge-cases` (pickup bar, rests, a tie across a
barline, repeated notes, a big leap). Add the real demo piece as `samples/<name>/score.musicxml`
and run `npm run synth` again.

## Claude API key

Stage 6 calls Claude. Copy `backend/.env.example` to `backend/.env` and set `ANTHROPIC_API_KEY`.
Without it, `/feedback` uses the rule-based fallback.

## Status

`/analyze` and `/feedback` are **stubs**: they return the sample JSON in `contracts/`
so the frontend can be built before the real pipeline exists. Each stage in
`backend/app/stages/` raises `NotImplementedError` until its owner fills it in.
