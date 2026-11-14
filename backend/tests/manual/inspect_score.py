"""Look at a real MusicXML file next to what stage 1 (parse_score) makes of it.

Not a pytest test (pytest only collects test_*.py): run it yourself and read the output.

    npm run inspect:score                            # list the files you can use
    npm run inspect:score -- beethoven               # summary + bars 1-2: real XML, then our output
    npm run inspect:score -- beethoven --bars 3-5    # other bars
    npm run inspect:score -- edge-cases --bars 4-5   # our own samples (tie across a barline)
    npm run inspect:score -- all                     # one-line check of every file
    npm run inspect:score -- path/to/any.musicxml    # any file on disk
    npm run inspect:score -- beethoven --json        # full JSON entries instead of the table

For each file it also runs an independent checker that reads the raw XML (no music21), applies the
ID rules from docs/DECISIONS.md section 3 itself, and compares ids, pitches, onsets, durations and
render_ids. "0 mismatches" = two separate implementations agree.

Real-world files come from OSMD's own test data (same renderer as our frontend). They are downloaded
on first use into tests/manual/downloads/ (gitignored: several carry Recordare copyright notices).
"""

import argparse
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.stages.score import parse_score  # noqa: E402

OSMD_URL = "https://raw.githubusercontent.com/opensheetmusicdisplay/opensheetmusicdisplay/develop/test/data/"
DOWNLOADS = HERE / "downloads"

# short name -> local path (str) or OSMD file name (downloaded on demand)
FILES = {
    "c-major-scale": REPO / "samples/c-major-scale/score.musicxml",
    "edge-cases": REPO / "samples/edge-cases/score.musicxml",
    "beethoven": "Beethoven_AnDieFerneGeliebte.xml",
    "dichterliebe": "Dichterliebe01.xml",
    "land-der-berge": "Land_der_Berge.musicxml",
    "mozart": "Mozart_DasVeilchen.xml",
    "schubert": "Schubert_An_die_Musik.xml",
    "grace-notes": "OSMD_function_test_GraceNotes.xml",
    "rest-bars": HERE / "fixtures/rest-bars.musicxml",
}
NOTES = {
    "c-major-scale": "our sample: 8 quarter notes",
    "edge-cases": "our sample: pickup, rests, tie across bars 4-5, F#",
    "beethoven": "voice + piano, 3 flats, dotted rhythms, lyrics",
    "dichterliebe": "voice + piano, piano intro (voice rests), 2/4",
    "land-der-berge": "voice + piano, 3 lyric verses (we keep verse 1)",
    "mozart": "voice + piano, tempo only on the piano part",
    "schubert": "voice + piano, title only as page text (-> null)",
    "grace-notes": "OSMD's grace-note test (grace notes take no index)",
    "rest-bars": "voice only, 3 empty bars in a row (OSMD multi-bar rest)",
}


# --------------------------------------------------------------------------- files


def resolve(name: str) -> Path:
    if name in FILES:
        src = FILES[name]
        if isinstance(src, Path):
            return src
        DOWNLOADS.mkdir(exist_ok=True)
        path = DOWNLOADS / src
        if not path.exists():
            print(f"(downloading {src} from OSMD's test data...)", file=sys.stderr)
            urllib.request.urlretrieve(OSMD_URL + src, path)
        return path
    path = Path(name)
    if not path.exists():
        sys.exit(f"Unknown file or name: {name!r}. Run without arguments to list names.")
    return path


# --------------------------------------------------------------------------- raw XML (no music21)

LAYOUT_TAGS = {"print", "stem", "beam", "staff-layout", "system-layout", "measure-layout", "barline", "instrument"}
LAYOUT_ATTR = re.compile(r"(default|relative)-|font|color|width|justify|halign|valign|placement|osmd")
STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def first_part_measures(path: Path) -> list[ET.Element]:
    return ET.parse(path).getroot().find("part").findall("measure")


def pretty_measure(measure: ET.Element) -> str:
    """The measure's XML with display-only elements/attributes removed (musical content untouched)."""

    def prune(el):
        for child in list(el):
            if child.tag in LAYOUT_TAGS or (child.tag == "notations" and child.find("tied") is None):
                el.remove(child)
            else:
                prune(child)
        for attr in list(el.attrib):
            if LAYOUT_ATTR.match(attr):
                del el.attrib[attr]

    prune(measure)
    ET.indent(measure, "  ")
    return ET.tostring(measure, encoding="unicode").strip()


def midi_of(note_el: ET.Element) -> int:
    p = note_el.find("pitch")
    return (int(p.findtext("octave")) + 1) * 12 + STEPS[p.findtext("step")] + round(float(p.findtext("alter") or 0))


def raw_reference(path: Path) -> list[dict]:
    """The ID rules applied straight to the XML: part 1, voice 1, bars by file position, rests count,
    grace notes skipped, chord -> top note, ties merged into the first notehead."""
    divisions, measure_start, entries = 1, Fraction(0), []
    for m_no, measure in enumerate(first_part_measures(path), start=1):
        voices = [v.text.strip() for v in measure.iter("voice")]
        voice_one = "1" if "1" in voices or not voices else voices[0]
        pos, longest, index, last = Fraction(0), Fraction(0), 0, None
        for el in measure:
            if el.tag == "attributes" and el.find("divisions") is not None:
                divisions = int(el.findtext("divisions"))
            elif el.tag in ("backup", "forward"):
                step = Fraction(int(el.findtext("duration")), divisions)
                pos += step if el.tag == "forward" else -step
                longest = max(longest, pos)
            elif el.tag == "note" and el.find("grace") is None:
                voice = (el.findtext("voice") or "1").strip()
                if el.find("chord") is not None:  # extra chord tone: same onset, keep the top pitch
                    if voice == voice_one and last and not last["is_rest"]:
                        last["midi"] = max(last["midi"], midi_of(el))
                    continue
                onset, dur = pos, Fraction(int(el.findtext("duration") or 0), divisions)
                pos += dur
                longest = max(longest, pos)
                if voice != voice_one:
                    continue
                note_id, index = f"m{m_no}-n{index}", index + 1
                is_rest = el.find("rest") is not None
                prev = entries[-1] if entries else None
                tie_stop = "stop" in {t.get("type") for t in el.findall("tie")}
                if not is_rest and tie_stop and prev and not prev["is_rest"] and prev["midi"] == midi_of(el):
                    prev["render_ids"].append(note_id)
                    prev["duration_beats"] += dur
                    last = prev
                    continue
                last = {
                    "id": note_id, "is_rest": is_rest, "midi": None if is_rest else midi_of(el),
                    "onset_beats": measure_start + onset, "duration_beats": dur, "render_ids": [note_id],
                }
                entries.append(last)
        measure_start += longest
    return entries


def compare(ours: list[dict], ref: list[dict]) -> list[str]:
    def key(n):
        return (n["id"], n["is_rest"], n["midi"], n["render_ids"],
                round(float(n["onset_beats"]), 4), round(float(n["duration_beats"]), 4))

    problems = [f"entry count: ours {len(ours)}, raw XML {len(ref)}"] if len(ours) != len(ref) else []
    for a, b in zip(ours, ref):
        if key(a) != key(b):
            problems.append(f"ours {key(a)}\n      raw  {key(b)}")
    return problems


# --------------------------------------------------------------------------- printing


def summary(path: Path, expected: dict, problems: list[str]) -> str:
    notes = expected["notes"]
    sung = [n for n in notes if not n["is_rest"]]
    tied = sum(len(n["render_ids"]) > 1 for n in sung)
    if problems is None:
        verdict = "skipped (.mxl is zipped; unzip it to check)"
    else:
        verdict = "OK, 0 mismatches" if not problems else f"{len(problems)} MISMATCHES"
    return (
        f"title={expected['title']!r}  tempo={expected['tempo_bpm']:g} bpm  bars={notes[-1]['measure']}  "
        f"entries={len(notes)} (notes {len(sung)}, rests {len(notes) - len(sung)}, tied {tied}, "
        f"with lyric {sum(1 for n in sung if n['lyric'])})\n"
        f"independent raw-XML check: {len(notes)} entries -> {verdict}"
    )


def table(rows: list[dict]) -> str:
    head = f"{'id':<9}{'name':<6}{'midi':>5}{'onset_beats':>13}{'dur_beats':>11}{'onset_sec':>11}{'dur_sec':>9}  {'lyric':<10}render_ids"
    lines = [head, "-" * len(head)]
    for n in rows:
        lines.append(
            f"{n['id']:<9}{n['name'] or 'rest':<6}{n['midi'] if n['midi'] is not None else '-':>5}"
            f"{n['onset_beats']:>13g}{n['duration_beats']:>11g}{n['onset_sec']:>11g}{n['duration_sec']:>9g}  "
            f"{(n['lyric'] or '-'):<10}{n['render_ids']}"
        )
    return "\n".join(lines)


def show_bars(path: Path, expected: dict, first: int, last: int, as_json: bool) -> None:
    measures = first_part_measures(path)
    last = min(last, len(measures))
    for bar in range(first, last + 1):
        print(f"\n{'=' * 30} bar {bar} (file position; printed number=\"{measures[bar - 1].get('number')}\") {'=' * 30}")
        print("\n--- real XML, part 1 (layout removed) ---")
        print(pretty_measure(measures[bar - 1]))
        print("\n--- our expected_notes for this bar ---")
        rows = [n for n in expected["notes"] if n["measure"] == bar]
        if as_json:
            print("\n".join(json.dumps(n, ensure_ascii=False) for n in rows) or "(none)")
        else:
            print(table(rows) if rows else "(no entries start in this bar)")
        carried = [(rid, n["id"]) for n in expected["notes"] for rid in n["render_ids"][1:] if rid.startswith(f"m{bar}-")]
        for rid, owner in carried:
            print(f"   note: notehead {rid} is the tied continuation of {owner} (no entry of its own)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="a short name (see list), 'all', or a path to a MusicXML file")
    ap.add_argument("--bars", default="1-2", help="bar range by file position, e.g. 3-5 or 4 (default 1-2)")
    ap.add_argument("--tempo", type=float, help="tempo override, like the API's tempo_bpm")
    ap.add_argument("--json", action="store_true", help="print full JSON entries instead of the table")
    ap.add_argument("--names", action="store_true", help="(for tools) print the short names as JSON")
    ap.add_argument("--dump-json", action="store_true", help="(for tools) print {path, expected_notes} as JSON")
    args = ap.parse_args()

    if args.names:
        print(json.dumps(list(FILES)))
        return
    if args.dump_json:
        path = resolve(args.file)
        print(json.dumps({"path": str(path), "expected_notes": parse_score(path, args.tempo)}, ensure_ascii=False))
        return

    if not args.file:
        print("Files (use the short name):\n")
        for name, note in NOTES.items():
            print(f"  {name:<16}{note}")
        print("\nOr 'all', or a path to any .musicxml/.xml/.mxl file. --help for options.")
        return

    names = list(FILES) if args.file == "all" else [args.file]
    for name in names:
        path = resolve(name)
        expected = parse_score(path, args.tempo)
        problems = compare(expected["notes"], raw_reference(path)) if path.suffix != ".mxl" else None
        print(f"\n##### {name}  ({path.name})")
        print(summary(path, expected, problems))
        for p in (problems or [])[:10]:
            print("   ", p)
        if args.file != "all":
            first, _, last = args.bars.partition("-")
            show_bars(path, expected, int(first), int(last or first), args.json)


if __name__ == "__main__":
    main()
