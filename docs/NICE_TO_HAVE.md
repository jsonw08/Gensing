# Gensing: Nice-to-haves

Things to build **only after the core works end to end** (colored score + error types + overall
score, on real recordings). This file is the live list: the original 10 come from
[`gensing.pdf`](gensing.pdf) ("Nice-to-haves and what to cut", p. 13–14), which can't be edited, so
new ideas go here instead.

Rules:

- Items 1–10 are in the team's agreed priority order. New items go under **Not yet ranked** until
  the team places them.
- If an item changes a contract (a JSON field, an API field), it still follows the normal rule:
  update `contracts/`, `docs/DECISIONS.md`, and every producer/consumer in the same PR.
- The cut order (what to drop first if behind) is in [`DECISIONS.md`](DECISIONS.md) section 8 and
  doesn't change here.

Owner letters: A = Jason (frontend), B = Jonathan (audio + server), C = Mehul (music logic).

---

## Ranked (from gensing.pdf)

| # | Idea | What it is | Touches |
|---|---|---|---|
| 1 | **Click a note to hear it** | Plays the recording from that note, so the singer hears exactly what went wrong and where. Uses `sung_start_sec` / `sung_end_sec` from `results` (+ `audio_offset_sec` to map back to the untrimmed recording). About an hour; very convincing for judges. | A |
| 2 | **Pitch view** | Expected notes as bars, the singer's voice as a line over them; flat notes visibly sit under their bars. Data is already in the `/analyze` response (`pitch_track`, `sung_notes`, `expected_notes`). | A |
| 3 | **Beginner / Advanced presets** | Looser or tighter thresholds. Beginner ±35 cents / ±¼ beat; advanced ±15 cents / ±1/16 beat (DECISIONS.md 4.5). The `preset` field already exists in the API. | C (stage 5), A (setting) |
| 4 | **Repeats** | On upload, unfold repeats with music21 `expandRepeats()` and save a new MusicXML that both stage 1 and the frontend use, so each pass is drawn and colored separately. Store the original bar and pass (`"orig_measure": 3, "pass": 2`) so feedback can say "bar 3, second time". Show the unfolded score while recording too. Check early that the exported file renders correctly and each pass has the right verse's lyrics. | C (stage 1), A, B (feedback wording) |
| 5 | **Playback highlight** | Play the recording back with a moving highlight across the score. | A |
| 6 | **"Ask the coach"** | Follow-up questions to the LLM, with `results.json` as context. | B, A |
| 7 | **Retry a bar** | Re-record only the worst bars. | A, B, C |
| 8 | **Any-key transposition** | Sing in any key, not just the written one or an octave off. Stage 4 would detect any semitone shift instead of only −12 / 0 / +12. | C (stage 4) |
| 9 | **Lyrics, tone and breath** | Diction (were the right syllables sung), tone quality, whether breaths land in sensible places. Each needs new analysis beyond pitch and timing. | B, C |
| 10 | **Scan any sheet music (OMR)** | Accept a PDF or photo and convert it to MusicXML (Audiveris or oemer) before stage 1. Risky: OMR mistakes look like singer mistakes. | B |

## Not yet ranked

| Idea | What it is | Touches |
|---|---|---|
| **Choose which part to sing** | Today we always grade the **first part, voice 1** (DECISIONS.md section 3). Fine for voice + piano songs, where the voice is almost always part 1. But in a SATB score an alto, tenor or bass can't pick their line, and a file that lists the piano first would grade the piano. Plan: list the parts (and voices) after upload, let the singer pick one, send `part_index` (+ `voice`) to `/analyze`, have stage 1 read that part, and have the frontend color noteheads in **that** part's staff (`m3-n2` alone doesn't say which part, so OSMD must count within the chosen part). Stage 1 change is small; the API field and the frontend part picker + per-staff coloring are the real work. | C (stage 1), B (API field), A (picker + coloring) |
