"""Stage 1: Score parsing (owner: C).

MusicXML -> ordered list of every note (and rest) the singer should sing.
Output shape: contracts/expected_notes.sample.json. ID rules: docs/DECISIONS.md section 3.

The frontend (OSMD) builds the same IDs independently, so the counting rules here must not drift:
  - bars numbered by position in the file, from 1 (printed numbers ignored: pickups print as 0)
  - index = position in the bar, from 0; rests count; grace notes are skipped entirely
  - chord -> top note, one index; first part, voice 1 only
  - tie -> every notehead takes an index, but only the first gets an entry; all go in render_ids
"""

from pathlib import Path

from music21 import converter, tempo

from app.errors import AnalysisError

DEFAULT_TEMPO_BPM = 80.0  # when the score has no metronome mark (same as tools/synth_take.py)
ROUND = 6  # decimals for beats/seconds: keeps triplets readable, avoids 0.7500000001


def parse_score(musicxml_path: str | Path, tempo_bpm: float | None = None) -> dict:
    """Parse the first part, voice 1, with music21. If tempo_bpm is None, use the score's marking."""
    score = _load(musicxml_path)
    parts = list(score.parts)
    if not parts:
        raise AnalysisError("invalid_musicxml", "The score has no parts.", "score", 400)
    part = parts[0]

    bpm = float(tempo_bpm) if tempo_bpm is not None else _score_tempo(score, part)
    sec_per_beat = 60.0 / bpm

    notes: list[dict] = []
    for measure_no, measure in enumerate(part.getElementsByClass("Measure"), start=1):
        container = _voice_one(measure)
        base = measure.offset + (container.offset if container is not measure else 0.0)
        index = 0
        for el in sorted(container.notesAndRests, key=lambda e: e.offset):
            if el.duration.isGrace:
                continue
            note_id = f"m{measure_no}-n{index}"
            index += 1
            onset = float(base + el.offset)
            beats = float(el.quarterLength)

            if el.isRest:
                notes.append(_entry(note_id, measure_no, index - 1, None, None, onset, beats, None))
                continue

            pitch = max(el.pitches, key=lambda p: p.ps) if el.isChord else el.pitch
            prev = notes[-1] if notes else None
            tie = el.tie.type if el.tie else None
            if tie in ("stop", "continue") and prev and prev["midi"] == pitch.midi:
                prev["duration_beats"] += beats
                prev["render_ids"].append(note_id)
                continue

            name = pitch.nameWithOctave.replace("-", "b")  # music21 writes flats as "B-4"
            notes.append(_entry(note_id, measure_no, index - 1, pitch.midi, name, onset, beats, _first_verse(el)))

    if not any(not n["is_rest"] for n in notes):
        raise AnalysisError("invalid_musicxml", "The score has no notes to sing.", "score", 400)

    for n in notes:  # seconds from beats once, after ties have summed their durations
        n["onset_beats"] = round(n["onset_beats"], ROUND)
        n["duration_beats"] = round(n["duration_beats"], ROUND)
        n["onset_sec"] = round(n["onset_beats"] * sec_per_beat, ROUND)
        n["duration_sec"] = round(n["duration_beats"] * sec_per_beat, ROUND)

    return {"title": _title(score, musicxml_path), "tempo_bpm": bpm, "beat_unit": "quarter", "notes": notes}


def _load(path: str | Path):
    try:
        # forceSource: never read music21's on-disk pickle cache (keyed by path + mtime);
        # uploads may reuse the same tmp path.
        return converter.parse(str(path), forceSource=True)
    except Exception as e:  # music21 raises many different types for bad files
        raise AnalysisError("invalid_musicxml", "This file couldn't be read as MusicXML.", "score", 400) from e


def _score_tempo(score, part) -> float:
    """First metronome mark, as quarter notes per minute (dotted-quarter = 60 -> 90).

    Look in the sung part first, then the whole score: the tempo applies to every part, and
    voice + piano files often put it only on the piano (e.g. OSMD's Mozart_DasVeilchen.xml).
    """
    for source in (part, score):
        for mark in source.recurse().getElementsByClass(tempo.MetronomeMark):
            bpm = mark.getQuarterBPM()
            if bpm and bpm > 0:
                return float(bpm)
    return DEFAULT_TEMPO_BPM


def _first_verse(el) -> str | None:
    """Verse 1 only. music21's el.lyric joins every verse with newlines ("Land\nHeiß\nMu")."""
    if not el.lyrics:
        return None
    lyric = next((ly for ly in el.lyrics if ly.number == 1), el.lyrics[0])
    return lyric.text or None


def _title(score, path) -> str | None:
    """<work-title>, else <movement-title>. music21 fills movementName with the file name when the
    file has none, so that case is ignored. Titles that only exist as page text (credits) -> null."""
    md = score.metadata
    if md is None:
        return None
    if md.title:
        return md.title
    movement = md.movementName
    if movement and movement != Path(path).name:
        return movement
    return None


def _voice_one(measure):
    """Voice "1" if the bar has voices (else the first voice); the bar itself if it has none."""
    voices = list(measure.voices)
    if not voices:
        return measure
    return next((v for v in voices if str(v.id) == "1"), voices[0])


def _entry(note_id, measure, index, midi, name, onset_beats, duration_beats, lyric) -> dict:
    return {
        "id": note_id,
        "measure": measure,
        "index": index,
        "is_rest": midi is None,
        "midi": midi,
        "name": name,
        "onset_beats": onset_beats,
        "duration_beats": duration_beats,
        "onset_sec": None,  # filled in once all ties are merged
        "duration_sec": None,
        "lyric": lyric,
        "render_ids": [note_id],
    }
