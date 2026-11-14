"""Generate fake "sung" recordings of a MusicXML score, plus an answer key for each.

Each take is a WAV that imitates an in-app recording (one bar of silent count-in, then
the melody), and an .answer.json saying exactly what /analyze should report. Mistakes are
planted on purpose, so we know the right answer for every note.

Takes:
  perfect      sung exactly as written                -> all in tune, all on time
  mistakes     one wrong note, one flat, one late,     -> each mistake caught, rest green
               one early, one skipped, one extra
  octave-down  perfect, but an octave lower            -> all green (tests octave detection)
  delayed      perfect, but everything 120 ms late     -> all on time (tests median-offset removal)

Usage (from the repo root):
  backend/.venv/bin/python tools/synth_take.py                 # every samples/*/score.musicxml
  backend/.venv/bin/python tools/synth_take.py samples/edge-cases/score.musicxml
  backend/.venv/bin/python tools/synth_take.py --clean          # pure tones, into takes-clean/

Output: samples/<piece>/takes/<take>.wav and <take>.answer.json

Note: the parser below follows the note-ID rules in the contracts, independently of stage 1.
That makes it a cross-check: stage 1's IDs should match the ones in these answer keys.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import soundfile as sf
from music21 import converter, tempo

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RATE = 22050
SEED = 7

# Voice-like sound settings
HARMONICS = 10
VIBRATO_RATE_HZ = 5.5
VIBRATO_DEPTH_SEMITONES = 0.30  # +/- 30 cents
VIBRATO_FADE_IN_SEC = 0.15
SCOOP_SEMITONES = 0.40  # notes start 40 cents low...
SCOOP_SEC = 0.06  # ...and slide up over 60 ms
ATTACK_SEC = 0.03
RELEASE_SEC = 0.04
BREATH_GAP_SEC = 0.06  # silence before the next note starts
NOISE_LEVEL = 0.005

# Planted mistakes
WRONG_NOTE_SEMITONES = (2, -2, 3, -3)  # first one that differs from both neighbours
FLAT_CENTS = -35
TIMING_SHIFT_SEC = 0.20
DELAY_SEC = 0.12
EXTRA_NOTE_SEC = 0.30

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_name(midi: int) -> str:
    return f"{SHARP_NAMES[midi % 12]}{midi // 12 - 1}"


# --------------------------------------------------------------------------- parsing


@dataclass
class WrittenNote:
    id: str
    measure: int
    is_rest: bool
    midi: int | None
    name: str | None
    onset_sec: float
    duration_sec: float
    render_ids: list[str] = field(default_factory=list)


@dataclass
class Score:
    title: str | None
    tempo_bpm: float
    beats_per_bar: float
    notes: list[WrittenNote]


def parse_score(path: Path) -> Score:
    """Follow the contract's note-ID rules: first part, voice 1, bars in file order from 1,
    rests counted, grace notes skipped, chords -> top note, ties merged into the first."""
    s = converter.parse(str(path))
    part = s.parts[0]

    marks = list(part.recurse().getElementsByClass(tempo.MetronomeMark))
    tempo_bpm = float(marks[0].getQuarterBPM()) if marks else 80.0
    sec_per_beat = 60.0 / tempo_bpm

    measures = list(part.getElementsByClass("Measure"))
    ts = measures[0].timeSignature or part.recurse().getElementsByClass("TimeSignature").first()
    beats_per_bar = float(ts.barDuration.quarterLength) if ts else 4.0

    notes: list[WrittenNote] = []
    for m_idx, m in enumerate(measures, start=1):
        container = m.voices[0] if m.voices else m
        index = 0
        for el in sorted(container.notesAndRests, key=lambda e: e.offset):
            if el.duration.isGrace:
                continue
            note_id = f"m{m_idx}-n{index}"
            index += 1
            onset = (m.offset + el.offset) * sec_per_beat
            dur = el.quarterLength * sec_per_beat

            if el.isRest:
                notes.append(WrittenNote(note_id, m_idx, True, None, None, onset, dur, [note_id]))
                continue

            pitch = max(el.pitches, key=lambda p: p.midi) if el.isChord else el.pitch
            tie = el.tie.type if el.tie else None
            if tie in ("stop", "continue") and notes and not notes[-1].is_rest:
                notes[-1].duration_sec += dur
                notes[-1].render_ids.append(note_id)
                continue
            notes.append(
                WrittenNote(note_id, m_idx, False, pitch.midi, pitch.nameWithOctave.replace("-", "b"), onset, dur, [note_id])
            )

    title = s.metadata.title if s.metadata else None
    return Score(title, tempo_bpm, beats_per_bar, notes)


# --------------------------------------------------------------------------- takes


@dataclass
class SungNote:
    midi: float  # may include a cents offset
    start: float  # seconds, 0 = beat 1
    end: float


@dataclass
class Take:
    name: str
    sung: list[SungNote]
    answer_notes: dict[str, dict]
    answer_extras: list[dict]
    expect: dict


def default_sung(n: WrittenNote) -> SungNote:
    end = n.onset_sec + n.duration_sec - BREATH_GAP_SEC
    return SungNote(float(n.midi), n.onset_sec, end)


def perfect_answers(score: Score) -> dict[str, dict]:
    return {n.id: {"status": "in_tune", "timing": "on_time"} for n in score.notes if not n.is_rest}


def take_perfect(score: Score) -> Take:
    sung = [default_sung(n) for n in score.notes if not n.is_rest]
    return Take("perfect", sung, perfect_answers(score), [], {"octave_shift": 0})


def take_octave_down(score: Score) -> Take:
    sung = [replace(default_sung(n), midi=n.midi - 12) for n in score.notes if not n.is_rest]
    return Take("octave-down", sung, perfect_answers(score), [], {"octave_shift": -12})


def take_delayed(score: Score) -> Take:
    sung = []
    for n in score.notes:
        if n.is_rest:
            continue
        s = default_sung(n)
        sung.append(SungNote(s.midi, s.start + DELAY_SEC, s.end + DELAY_SEC))
    return Take(
        "delayed", sung, perfect_answers(score), [], {"octave_shift": 0, "timing_offset_ms": round(DELAY_SEC * 1000)}
    )


def take_mistakes(score: Score) -> Take:
    """Plant one of each mistake on notes spread through the piece (never the first or last)."""
    pitched = [n for n in score.notes if not n.is_rest]
    if len(pitched) < 7:
        raise ValueError("need at least 7 sung notes to plant every mistake")

    def pick(frac: float) -> int:
        return min(max(1, round(frac * (len(pitched) - 1))), len(pitched) - 2)

    plan = {"wrong": pick(0.2), "flat": pick(0.35), "late": pick(0.5), "early": pick(0.65), "skip": pick(0.8)}
    if len(set(plan.values())) < len(plan):
        raise ValueError("piece too short to keep the planted mistakes apart")

    answers = perfect_answers(score)
    sung_by_idx: dict[int, SungNote] = {i: default_sung(n) for i, n in enumerate(pitched)}

    # Wrong note: a different note that isn't the same as either neighbour.
    i = plan["wrong"]
    neighbours = {pitched[i - 1].midi, pitched[i + 1].midi}
    for step in WRONG_NOTE_SEMITONES:
        if pitched[i].midi + step not in neighbours:
            break
    sung_by_idx[i].midi = pitched[i].midi + step
    answers[pitched[i].id] = {"status": "wrong_note", "sang": midi_to_name(pitched[i].midi + step), "timing": "on_time"}

    # Out of tune (flat).
    i = plan["flat"]
    sung_by_idx[i].midi = pitched[i].midi + FLAT_CENTS / 100
    answers[pitched[i].id] = {"status": "out_of_tune", "cents": FLAT_CENTS, "timing": "on_time"}

    # Late: start later, end where it would have.
    i = plan["late"]
    sung_by_idx[i].start += TIMING_SHIFT_SEC
    answers[pitched[i].id] = {"status": "in_tune", "timing": "late"}

    # Early: start earlier, and cut the previous note short so they don't overlap.
    i = plan["early"]
    sung_by_idx[i].start -= TIMING_SHIFT_SEC
    prev = sung_by_idx[i - 1]
    prev.end = min(prev.end, sung_by_idx[i].start - BREATH_GAP_SEC)
    answers[pitched[i].id] = {"status": "in_tune", "timing": "early"}

    # Skipped: just don't sing it.
    i = plan["skip"]
    del sung_by_idx[i]
    answers[pitched[i].id] = {"status": "skipped", "timing": None}

    sung = [sung_by_idx[k] for k in sorted(sung_by_idx)]

    # Extra: inside the first rest long enough to hold it; otherwise after the last note.
    extras = []
    rest = next((n for n in score.notes if n.is_rest and n.duration_sec >= EXTRA_NOTE_SEC + 0.3), None)
    if rest is not None:
        idx = score.notes.index(rest)
        before = next(n for n in reversed(score.notes[:idx]) if not n.is_rest)
        extra_midi = before.midi + 4
        mid = rest.onset_sec + rest.duration_sec / 2
        sung.append(SungNote(float(extra_midi), mid - EXTRA_NOTE_SEC / 2, mid + EXTRA_NOTE_SEC / 2))
        extras.append({"near_id": rest.id, "during_rest": True, "sang": midi_to_name(extra_midi)})
    else:
        last = pitched[-1]
        extra_midi = last.midi + 4
        start = last.onset_sec + last.duration_sec + 0.3
        sung.append(SungNote(float(extra_midi), start, start + EXTRA_NOTE_SEC))
        extras.append({"near_id": last.id, "during_rest": False, "sang": midi_to_name(extra_midi)})

    sung.sort(key=lambda s: s.start)
    return Take("mistakes", sung, answers, extras, {"octave_shift": 0})


# --------------------------------------------------------------------------- audio


def render(sung: list[SungNote], countin_sec: float, total_sec: float, clean: bool, rng: np.random.Generator) -> np.ndarray:
    n_samples = int((countin_sec + total_sec + 1.0) * SAMPLE_RATE)
    out = np.zeros(n_samples)

    for note in sung:
        start = countin_sec + note.start
        dur = note.end - note.start
        if dur <= 0:
            continue
        t = np.arange(int(dur * SAMPLE_RATE)) / SAMPLE_RATE

        midi = np.full_like(t, note.midi)
        if not clean:
            fade = np.clip(t / VIBRATO_FADE_IN_SEC, 0, 1)
            midi += VIBRATO_DEPTH_SEMITONES * fade * np.sin(2 * np.pi * VIBRATO_RATE_HZ * t)
            midi -= SCOOP_SEMITONES * np.clip(1 - t / SCOOP_SEC, 0, 1)
        freq = 440.0 * 2 ** ((midi - 69) / 12)
        phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE

        if clean:
            wave = np.sin(phase)
        else:
            wave = np.zeros_like(t)
            for k in range(1, HARMONICS + 1):
                if freq.max() * k >= SAMPLE_RATE / 2:
                    break
                wave += np.sin(k * phase) / k**1.2

        env = np.minimum(1.0, np.minimum(t / ATTACK_SEC, (dur - t) / RELEASE_SEC))
        wave *= np.clip(env, 0, 1)

        i0 = int(start * SAMPLE_RATE)
        out[i0 : i0 + len(wave)] += wave

    peak = np.abs(out).max()
    if peak > 0:
        out = 0.8 * out / peak
    if not clean:
        out += NOISE_LEVEL * rng.standard_normal(len(out))
    return out.astype(np.float32)


# --------------------------------------------------------------------------- main


def generate(score_path: Path, clean: bool) -> None:
    score = parse_score(score_path)
    piece = score_path.parent.name
    out_dir = score_path.parent / ("takes-clean" if clean else "takes")
    out_dir.mkdir(exist_ok=True)

    countin_sec = score.beats_per_bar * 60.0 / score.tempo_bpm  # one bar, silent (singer wears headphones)
    last = score.notes[-1]
    total_sec = last.onset_sec + last.duration_sec

    rng = np.random.default_rng(SEED)
    for take in (take_perfect(score), take_mistakes(score), take_octave_down(score), take_delayed(score)):
        audio = render(take.sung, countin_sec, total_sec, clean, rng)
        sf.write(out_dir / f"{take.name}.wav", audio, SAMPLE_RATE, subtype="PCM_16")

        answer = {
            "piece": piece,
            "take": take.name,
            "settings": {"mode": "strict", "tempo_bpm": score.tempo_bpm, "countin_end_sec": round(countin_sec, 3)},
            "expect": take.expect,
            "notes": take.answer_notes,
            "extras": take.answer_extras,
        }
        (out_dir / f"{take.name}.answer.json").write_text(json.dumps(answer, indent=2) + "\n")

    rel = out_dir.relative_to(REPO_ROOT)
    print(f"{piece}: {sum(not n.is_rest for n in score.notes)} notes, tempo {score.tempo_bpm:g} -> {rel}/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scores", nargs="*", type=Path, help="MusicXML files (default: samples/*/score.musicxml)")
    ap.add_argument("--clean", action="store_true", help="pure sine tones, no vibrato/scoop/noise")
    args = ap.parse_args()

    scores = [p.resolve() for p in args.scores] or sorted((REPO_ROOT / "samples").glob("*/score.musicxml"))
    if not scores:
        sys.exit("no scores found")
    for path in scores:
        generate(path, args.clean)


if __name__ == "__main__":
    main()
