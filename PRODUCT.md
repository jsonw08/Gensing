# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Singers practicing alone** (primary, durable). Students, choir members and amateur singers
  working through a piece with no teacher in the room. Their job: sing the piece through, then
  find out exactly which notes went wrong, how, and what to practice next.
- **Hackathon judges** (near-term, HackUMass XIV). They watch a short live demo on the team's
  laptop and have to understand the result immediately: a colored score with the error types,
  plus an overall score.

Not confirmed as audiences (don't design for them unless the team decides to): voice teachers
reviewing students, and beginners who can't yet read notation.

## Product Purpose

Gensing gives a solo singer the feedback a voice teacher would. You load a MusicXML score and
record yourself singing it, and you get the sheet music back with every note marked: in tune, out
of tune (flat/sharp, in cents), wrong note, early/late, skipped, or extra. You also get an overall
score and short coaching tips.

Success for the singer means knowing which bars and notes to work on, and why. Success for the
demo means the colored score, the error types and the overall score all show reliably. Those
three are never cut.

## Positioning

- **It marks up your real score.** Feedback lands on the actual notation, notehead by notehead,
  the way a teacher marks a student's copy. There's no scrolling pitch lane and no karaoke bar.
- **Coaching, not just a grade.** It names patterns ("flat on the high notes in bars 5–8") and
  doesn't stop at a percentage. The analysis computes every number and pattern; the AI only
  turns them into readable advice and never analyzes or invents trends itself.

Recording first and reviewing after, and following the singer's own tempo by default, are real
product facts, but they aren't the claim Gensing competes on.

## Operating Context

- **Flow:** Welcome → Practice → Evaluate.
  - **Practice:** load a MusicXML file, set the starting tempo, hear a one-bar count-in, then
    record (no click while singing). Or upload an existing recording. Takes collect in a list.
  - **Evaluate:** a take shows the colored score, a score card (total + pitch, intonation,
    rhythm, completeness), hover details per note, and a "Get feedback" button that asks for
    coaching on demand. Clicking a tip highlights its bars.
- **Setting:** one singing voice, no accompaniment, a microphone in a browser. The demo runs live
  on a laptop, possibly on unreliable Wi-Fi.
- **Timing modes:** free (the singer's own tempo, the default and main mode) and strict (against
  the score's tempo).

## Capabilities and Constraints

- **Input:** MusicXML only. The app grades the first part, voice 1. Grace notes are skipped, ties
  count as one sung note, and chords use the top note.
- **Feedback vocabulary** (use these words consistently):
  - Pitch status: `in_tune`, `out_of_tune`, `wrong_note`, `skipped`.
  - Timing, a separate verdict: `on_time`, `early`, `late`.
  - `extra`: a sung note that wasn't written.
  - `uncertain`: low confidence. Drawn faded and left out of the score.
  - A note can be out of tune *and* late at the same time.
- **Score:** 0–100 total, made up of pitch, intonation, rhythm and completeness.
- **Presets:** default / beginner / advanced thresholds exist in the API. The UI doesn't offer
  them yet.
- **No accounts, no saving.** No sign-in. Takes live in memory for the session and are lost on
  reload. This is intended.
- **Rendering:** the score is drawn in the browser (OpenSheetMusicDisplay). Colors attach to
  noteheads through note IDs shared with the backend.
- **Coaching** is optional. If the AI call fails, rule-based tips stand in, so it never errors.
- **Open (undecided):**
  - Phone / small-screen support.
  - Whether error types must be readable without color.
  - The demo pieces, and real recordings of them.
  - Choosing which part to sing.

## Brand Commitments

- **Name:** Gensing.
- No binding voice, tone or identity rules have been set. The current welcome line ("Your sheet
  music, marked up like a voice teacher would") is existing copy, not a confirmed commitment.

## Evidence on Hand

- **Sample pieces** in `samples/`: `c-major-scale`, `edge-cases`, `lantern-song` and
  `twinkle-twinkle`, each with generated test takes (perfect, mistakes, octave-down, delayed) and
  answer keys.
- **Contract samples** for every pipeline hand-off in `contracts/`, and frontend mocks in
  `frontend/src/mocks/` (lantern-song).
- **Absent, never to be fabricated:** real singer recordings, users, testimonials, accuracy
  benchmarks, and press.

## Product Principles

1. **The score is the interface.** Feedback belongs on the notation the singer already reads,
   not in a separate chart they have to translate back.
2. **Facts first, words second.** Every verdict, number and pattern is computed. Coaching only
   phrases those facts and never adds claims of its own.
3. **Specific beats general.** Point to the bar and the note, and say flat or sharp, early or
   late, by how much.
4. **The core path never breaks.** The colored score, the error types and the overall score
   always show. Optional parts (coaching, recording) fall back instead of failing.
5. **Session, not account.** Open it, sing, learn, leave. Nothing is stored, and nothing asks you
   to sign up.
