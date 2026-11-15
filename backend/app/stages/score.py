"""Stage 1: Score parsing (owner: C).

MusicXML -> ordered list of every note (and rest) the singer should sing.
Output shape: contracts/expected_notes.sample.json. ID rules: docs/DECISIONS.md section 3.

The frontend (OSMD) builds the same IDs independently, so the counting rules here must not drift:
  - bars numbered by position in the file, from 1 (printed numbers ignored: pickups print as 0)
  - index = position in the bar, from 0; rests count; grace notes are skipped entirely
  - chord -> top note, one index; first part, voice 1 only
  - tie -> every notehead takes an index, but only the first gets an entry; all go in render_ids
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from music21 import converter, tempo

from app.errors import AnalysisError

DEFAULT_TEMPO_BPM = 80.0  # when the score has no metronome mark (same as tools/synth_take.py)
ROUND = 6  # decimals for beats/seconds: keeps triplets readable, avoids 0.7500000001


def parse_score(musicxml_path: str | Path, tempo_bpm: float | None = None) -> dict:
    """Parse the first part, voice 1, with music21.

    Tempo: every metronome mark in the score is followed (seconds are added up piece by piece). If
    tempo_bpm is given, every mark is scaled by the same factor so the first one becomes tempo_bpm.
    """
    score = _load(musicxml_path)
    parts = list(score.parts)
    if not parts:
        raise AnalysisError("invalid_musicxml", "The score has no parts.", "score", 400)
    part = parts[0]

    tempo_map = _tempo_map(parts, tempo_bpm)

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
        start = _seconds_at(n["onset_beats"], tempo_map)
        n["onset_sec"] = round(start, ROUND)
        n["duration_sec"] = round(_seconds_at(n["onset_beats"] + n["duration_beats"], tempo_map) - start, ROUND)

    first_bpm = tempo_map[0][1]
    return {"title": _title(score, musicxml_path), "tempo_bpm": first_bpm, "beat_unit": "quarter", "notes": notes}


def _load(path: str | Path):
    """Read by content, not by file name: music21 picks its reader from the extension, so an upload
    saved without one (or a zipped .mxl saved as .musicxml) would be rejected. Zip -> .mxl."""
    try:
        if zipfile.is_zipfile(path):
            return converter.parseData(_mxl_score_xml(path), format="musicxml")
        # forceSource: never read music21's on-disk pickle cache (keyed by path + mtime);
        # uploads may reuse the same tmp path.
        return converter.parse(str(path), format="musicxml", forceSource=True)
    except Exception as e:  # music21 raises many different types for bad files
        raise AnalysisError("invalid_musicxml", "This file couldn't be read as MusicXML.", "score", 400) from e


def _mxl_score_xml(path: str | Path) -> str:
    """The score inside a compressed .mxl: the file META-INF/container.xml points to, else the first
    .xml/.musicxml outside META-INF."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        root = None
        if "META-INF/container.xml" in names:
            rootfile = ET.fromstring(z.read("META-INF/container.xml")).find(".//{*}rootfile")
            root = rootfile.get("full-path") if rootfile is not None else None
        if root not in names:
            root = next(n for n in names if n.endswith((".xml", ".musicxml")) and not n.startswith("META-INF/"))
        return z.read(root).decode("utf-8-sig")


def _tempo_map(parts, override: float | None) -> list[tuple[float, float]]:
    """[(beat, quarter-note bpm), ...] sorted, first at beat 0 (dotted-quarter = 60 -> 90).

    Marks from every part count: the tempo applies to the whole score, and voice + piano files often
    put it only on the piano (e.g. OSMD's Mozart_DasVeilchen.xml). Two marks on the same beat: the sung
    part (part 1) wins, then the earlier part. No marks: DEFAULT_TEMPO_BPM throughout. The first mark
    applies from the start even if it sits a little later. An override scales every mark by one factor.
    """
    found: dict[float, tuple[int, float]] = {}
    for rank, part in enumerate(parts):
        for mark in part.recurse().getElementsByClass(tempo.MetronomeMark):
            bpm = mark.getQuarterBPM()
            if not bpm or bpm <= 0:
                continue
            try:
                beat = round(float(mark.getOffsetInHierarchy(part)), ROUND)
            except Exception:  # mark not reachable from the part (shouldn't happen); skip it
                continue
            if beat not in found or rank < found[beat][0]:
                found[beat] = (rank, float(bpm))
    marks = [(beat, bpm) for beat, (_, bpm) in sorted(found.items())] or [(0.0, DEFAULT_TEMPO_BPM)]
    marks[0] = (0.0, marks[0][1])
    marks = [m for k, m in enumerate(marks) if k == 0 or m[1] != marks[k - 1][1]]  # drop repeats of same tempo
    if override is not None:
        factor = float(override) / marks[0][1]
        marks = [(beat, bpm * factor) for beat, bpm in marks]
    return marks


def _seconds_at(beat: float, tempo_map: list[tuple[float, float]]) -> float:
    """Seconds from beat 0 to `beat`, adding up each stretch at its own tempo."""
    seconds = 0.0
    for k, (start, bpm) in enumerate(tempo_map):
        if beat <= start:
            break
        end = tempo_map[k + 1][0] if k + 1 < len(tempo_map) else beat
        seconds += (min(beat, end) - start) * 60.0 / bpm
    return seconds


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
