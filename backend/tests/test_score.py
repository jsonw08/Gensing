"""Stage 1 (score parsing) tests."""

import json
from pathlib import Path

import pytest
import synth_take

from app.errors import AnalysisError
from app.stages.score import DEFAULT_TEMPO_BPM, parse_score

REPO = Path(__file__).resolve().parents[2]
PIECES = ["c-major-scale", "edge-cases"]


def score_path(piece: str) -> Path:
    return REPO / "samples" / piece / "score.musicxml"


def by_id(expected: dict) -> dict[str, dict]:
    return {n["id"]: n for n in expected["notes"]}


# --------------------------------------------------------------------------- sample pieces


def test_c_major_matches_contract_sample():
    contract = json.loads((REPO / "contracts" / "expected_notes.sample.json").read_text())
    assert parse_score(score_path("c-major-scale")) == contract


@pytest.mark.parametrize("piece", PIECES)
def test_note_ids_match_answer_keys(piece):
    answer = json.loads((REPO / "samples" / piece / "takes" / "perfect.answer.json").read_text())
    sung_ids = [n["id"] for n in parse_score(score_path(piece))["notes"] if not n["is_rest"]]
    assert sung_ids == list(answer["notes"])


@pytest.mark.parametrize("piece", PIECES)
def test_matches_synth_reference_parser(piece):
    ours = parse_score(score_path(piece))
    ref = synth_take.parse_score(score_path(piece))
    assert ours["tempo_bpm"] == ref.tempo_bpm
    assert len(ours["notes"]) == len(ref.notes)
    for a, b in zip(ours["notes"], ref.notes):
        assert (a["id"], a["measure"], a["is_rest"], a["midi"], a["name"], a["render_ids"]) == (
            b.id, b.measure, b.is_rest, b.midi, b.name, b.render_ids,
        )
        assert a["onset_sec"] == pytest.approx(b.onset_sec)
        assert a["duration_sec"] == pytest.approx(b.duration_sec)


def test_edge_cases_details():
    exp = parse_score(score_path("edge-cases"))
    notes = by_id(exp)
    assert exp["title"] == "Edge Cases (test)"

    # Pickup bar (printed as 0) is m1, and bar 2 starts after its single beat
    assert notes["m1-n0"]["measure"] == 1 and notes["m1-n0"]["onset_beats"] == 0.0
    assert notes["m2-n0"]["onset_beats"] == 1.0

    # Tie across the barline: one entry, both noteheads, summed duration; next note is n1
    tied = notes["m4-n2"]
    assert tied["render_ids"] == ["m4-n2", "m5-n0"]
    assert tied["duration_beats"] == 2.0 and tied["duration_sec"] == pytest.approx(1.5)
    assert "m5-n0" not in notes
    assert notes["m5-n1"]["onset_beats"] == tied["onset_beats"] + 2.0

    # Rests take an index and have null pitch fields
    rest = notes["m3-n2"]
    assert rest["is_rest"] and rest["midi"] is None and rest["name"] is None and rest["lyric"] is None
    assert notes["m3-n3"]["index"] == 3

    # F# from the key signature, repeated G4s kept separate, lyrics carried
    assert notes["m5-n2"]["name"] == "F#4" and notes["m5-n2"]["midi"] == 66
    assert notes["m2-n0"]["midi"] == notes["m2-n1"]["midi"] == 67
    assert notes["m1-n0"]["lyric"] == "Oh"


@pytest.mark.parametrize("piece", PIECES)
def test_notes_in_time_order_and_contiguous(piece):
    notes = parse_score(score_path(piece))["notes"]
    for a, b in zip(notes, notes[1:]):
        assert b["onset_beats"] == pytest.approx(a["onset_beats"] + a["duration_beats"])


@pytest.mark.parametrize("piece", PIECES)
def test_output_is_strict_json(piece):
    def reject(name):
        raise ValueError(name)

    json.loads(json.dumps(parse_score(score_path(piece))), parse_constant=reject)


# --------------------------------------------------------------------------- tempo


def test_tempo_override_changes_seconds_not_beats():
    base = parse_score(score_path("c-major-scale"))
    fast = parse_score(score_path("c-major-scale"), tempo_bpm=120)
    assert fast["tempo_bpm"] == 120
    for a, b in zip(base["notes"], fast["notes"]):
        assert a["onset_beats"] == b["onset_beats"]
        assert b["onset_sec"] == pytest.approx(b["onset_beats"] * 0.5)


def test_no_tempo_mark_uses_default(tmp_path):
    exp = parse_score(write_xml(tmp_path, [[note("C", 4)] * 4]))
    assert exp["tempo_bpm"] == DEFAULT_TEMPO_BPM


def test_dotted_quarter_tempo_converted_to_quarter_bpm(tmp_path):
    mark = (
        "<direction><direction-type><metronome><beat-unit>quarter</beat-unit><beat-unit-dot/>"
        "<per-minute>60</per-minute></metronome></direction-type></direction>"
    )
    exp = parse_score(write_xml(tmp_path, [[mark] + [note("C", 4)] * 4]))
    assert exp["tempo_bpm"] == 90


def test_tempo_only_in_another_part_is_found(tmp_path):
    # Found in the wild: OSMD's Mozart_DasVeilchen.xml puts <sound tempo="60"/> on the piano part only
    piano = [['<direction><sound tempo="60"/></direction>'] + [note("C", 3)] * 4]
    exp = parse_score(write_xml(tmp_path, [[note("C", 5)] * 4], extra_parts=[piano]))
    assert exp["tempo_bpm"] == 60


# --------------------------------------------------------------------------- built edge cases


def test_lyrics_take_verse_one_only(tmp_path):
    # Found in the wild: Land_der_Berge.musicxml has 3 verses; music21's el.lyric joins them with newlines
    first = note("C", 4, lyrics=["Land", "Heiß", "Mu"])
    exp = parse_score(write_xml(tmp_path, [[first, note("D", 4, lyrics=["der"]), note("E", 4), note("F", 4)]]))
    assert [n["lyric"] for n in exp["notes"]] == ["Land", "der", None, None]


def test_movement_title_used_when_no_work_title(tmp_path):
    exp = parse_score(write_xml(tmp_path, [[note("C", 4)] * 4], header="<movement-title>Im Mai</movement-title>"))
    assert exp["title"] == "Im Mai"


def test_grace_notes_take_no_index(tmp_path):
    exp = parse_score(write_xml(tmp_path, [[note("C", 4), note("D", 4, grace=True), note("E", 4), note("F", 4), note("G", 4)]]))
    assert [(n["id"], n["name"]) for n in exp["notes"]] == [
        ("m1-n0", "C4"), ("m1-n1", "E4"), ("m1-n2", "F4"), ("m1-n3", "G4"),
    ]


def test_chord_gives_top_note_and_one_index(tmp_path):
    chord = [note("C", 4), note("G", 4, chord=True), note("E", 4, chord=True)]
    exp = parse_score(write_xml(tmp_path, [chord + [note("D", 4)] * 3]))
    assert [(n["id"], n["name"]) for n in exp["notes"]] == [
        ("m1-n0", "G4"), ("m1-n1", "D4"), ("m1-n2", "D4"), ("m1-n3", "D4"),
    ]


def test_only_first_part_and_voice_one(tmp_path):
    voice1 = [note("C", 5)] * 4
    voice2 = ["<backup><duration>4</duration></backup>"] + [note("C", 3, voice=2)] * 4
    second_part = [[note("A", 2)] * 4]
    exp = parse_score(write_xml(tmp_path, [voice1 + voice2], extra_parts=[second_part]))
    assert [n["name"] for n in exp["notes"]] == ["C5"] * 4


def test_flats_spelled_with_b_and_title_missing_is_null(tmp_path):
    exp = parse_score(write_xml(tmp_path, [[note("B", 4, alter=-1)] + [note("C", 4)] * 3]))
    assert exp["notes"][0]["name"] == "Bb4" and exp["notes"][0]["midi"] == 70
    assert exp["title"] is None


# --------------------------------------------------------------------------- errors


def test_garbage_file_is_invalid_musicxml(tmp_path):
    bad = tmp_path / "bad.musicxml"
    bad.write_text("this is not a score")
    with pytest.raises(AnalysisError) as err:
        parse_score(bad)
    assert (err.value.code, err.value.stage, err.value.status) == ("invalid_musicxml", "score", 400)


def test_only_rests_is_invalid_musicxml(tmp_path):
    with pytest.raises(AnalysisError) as err:
        parse_score(write_xml(tmp_path, [["<note><rest/><duration>4</duration><voice>1</voice><type>whole</type></note>"]]))
    assert err.value.code == "invalid_musicxml"


# --------------------------------------------------------------------------- MusicXML builder


def note(step, octave, *, alter=0, grace=False, chord=False, voice=1, lyrics=()) -> str:
    pitch = f"<step>{step}</step>" + (f"<alter>{alter}</alter>" if alter else "") + f"<octave>{octave}</octave>"
    if grace:
        return f"<note><grace/><pitch>{pitch}</pitch><voice>{voice}</voice><type>eighth</type></note>"
    return (
        f"<note>{'<chord/>' if chord else ''}<pitch>{pitch}</pitch>"
        f"<duration>1</duration><voice>{voice}</voice><type>quarter</type>"
        + "".join(f'<lyric number="{i}"><syllabic>single</syllabic><text>{t}</text></lyric>' for i, t in enumerate(lyrics, 1))
        + "</note>"
    )


ATTRS = (
    "<attributes><divisions>1</divisions><key><fifths>0</fifths></key>"
    "<time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>"
)


def write_xml(tmp_path: Path, measures: list[list[str]], extra_parts: list[list[list[str]]] = (), header: str = "") -> Path:
    """Minimal 4/4 MusicXML: one part per list of measures, each measure a list of XML snippets."""

    def part(pid: str, ms: list[list[str]]) -> str:
        body = "".join(
            f'<measure number="{i}">{ATTRS if i == 1 else ""}{"".join(m)}</measure>' for i, m in enumerate(ms, 1)
        )
        return f'<part id="{pid}">{body}</part>'

    all_parts = [measures, *extra_parts]
    ids = [f"P{i}" for i in range(1, len(all_parts) + 1)]
    part_list = "".join(f'<score-part id="{p}"><part-name>{p}</part-name></score-part>' for p in ids)
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0">{header}'
        f"<part-list>{part_list}</part-list>{''.join(part(p, ms) for p, ms in zip(ids, all_parts))}</score-partwise>"
    )
    path = tmp_path / "built.musicxml"
    path.write_text(xml)
    return path


# --------------------------------------------------------------------------- more rhythm / file formats


def test_triplets_get_exact_third_beats(tmp_path):
    def trip(step):
        return (
            f"<note><pitch><step>{step}</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice>"
            "<type>eighth</type><time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes>"
            "</time-modification></note>"
        )

    def quarter(step):
        return f"<note><pitch><step>{step}</step><octave>4</octave></pitch><duration>3</duration><voice>1</voice><type>quarter</type></note>"

    path = write_xml(tmp_path, [[trip("C"), trip("D"), trip("E"), quarter("F"), quarter("G"), quarter("A")]])
    path.write_text(path.read_text().replace("<divisions>1</divisions>", "<divisions>3</divisions>"))
    notes = parse_score(path)["notes"]
    assert [n["onset_beats"] for n in notes[:4]] == [0.0, 0.333333, 0.666667, 1.0]
    assert notes[0]["duration_beats"] == 0.333333
    assert notes[3]["onset_sec"] == 0.75  # 1 beat at 80 bpm


def test_time_signature_changes_shift_bar_starts(tmp_path):
    def time(beats):
        return f"<attributes><time><beats>{beats}</beats><beat-type>4</beat-type></time></attributes>"

    bars = [[note("C", 4)] * 4, [time(3)] + [note("D", 4)] * 3, [time(2)] + [note("E", 4)] * 2, [note("F", 4)] * 2]
    firsts = [(n["id"], n["onset_beats"]) for n in parse_score(write_xml(tmp_path, bars))["notes"] if n["index"] == 0]
    assert firsts == [("m1-n0", 0.0), ("m2-n0", 4.0), ("m3-n0", 7.0), ("m4-n0", 9.0)]


def make_mxl(dest: Path, with_container: bool = True) -> Path:
    import zipfile

    with zipfile.ZipFile(dest, "w") as z:
        if with_container:
            z.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?><container><rootfiles><rootfile full-path="score.musicxml"/></rootfiles></container>',
            )
        z.write(score_path("edge-cases"), "score.musicxml")
    return dest


@pytest.mark.parametrize("zipped", [False, True], ids=["plain", "zipped"])
@pytest.mark.parametrize("name", ["score.musicxml", "score.xml", "score.mxl", "upload", "upload.tmp"])
def test_file_read_by_content_not_name(tmp_path, zipped, name):
    # /analyze saves uploads under a name it picks; a plain or zipped (.mxl) score must parse either way
    path = tmp_path / name
    if zipped:
        make_mxl(path)
    else:
        path.write_bytes(score_path("edge-cases").read_bytes())
    assert parse_score(path)["notes"] == parse_score(score_path("edge-cases"))["notes"]


def test_mxl_without_container_file(tmp_path):
    mxl = make_mxl(tmp_path / "bare.mxl", with_container=False)
    assert parse_score(mxl)["notes"] == parse_score(score_path("edge-cases"))["notes"]



# --------------------------------------------------------------------------- tempo changes


def metronome(bpm, dotted=False):
    dot = "<beat-unit-dot/>" if dotted else ""
    return (f"<direction><direction-type><metronome><beat-unit>quarter</beat-unit>{dot}<per-minute>{bpm}</per-minute>"
            f"</metronome></direction-type><sound tempo=\"{bpm * (1.5 if dotted else 1)}\"/></direction>")


def test_tempo_change_at_a_barline(tmp_path):
    # 60 bpm for bar 1 (1 s per beat), 120 bpm from bar 2 (0.5 s per beat)
    exp = parse_score(write_xml(tmp_path, [[metronome(60)] + [note("C", 4)] * 4, [metronome(120)] + [note("D", 4)] * 4]))
    assert exp["tempo_bpm"] == 60
    assert [n["onset_sec"] for n in exp["notes"]] == [0, 1, 2, 3, 4, 4.5, 5, 5.5]
    assert [n["duration_sec"] for n in exp["notes"]] == [1] * 4 + [0.5] * 4
    assert [n["onset_beats"] for n in exp["notes"]] == list(range(8))  # beats never change


def test_tempo_change_in_the_middle_of_a_bar_and_a_note_across_it(tmp_path):
    # 60 bpm; a half note on beats 0-2 of bar 2, then 120 bpm from beat 2 of bar 2
    half = "<note><pitch><step>E</step><octave>4</octave></pitch><duration>2</duration><voice>1</voice><type>half</type></note>"
    bars = [[metronome(60)] + [note("C", 4)] * 4, [half, metronome(120), note("F", 4), note("G", 4)]]
    exp = parse_score(write_xml(tmp_path, bars))
    assert [n["onset_sec"] for n in exp["notes"]] == [0, 1, 2, 3, 4, 6, 6.5]
    assert exp["notes"][4]["duration_sec"] == 2  # the half note is all at 60 bpm


def test_override_scales_every_tempo_mark(tmp_path):
    exp = parse_score(write_xml(tmp_path, [[metronome(60)] + [note("C", 4)] * 4, [metronome(120)] + [note("D", 4)] * 4]),
                      tempo_bpm=120)
    assert exp["tempo_bpm"] == 120
    assert [n["onset_sec"] for n in exp["notes"]] == [0, 0.5, 1, 1.5, 2, 2.25, 2.5, 2.75]  # 120 then 240


def test_tempo_change_on_the_piano_part_counts(tmp_path):
    piano = [[metronome(60)] + [note("C", 3)] * 4, [metronome(120)] + [note("C", 3)] * 4]
    exp = parse_score(write_xml(tmp_path, [[note("C", 5)] * 4, [note("D", 5)] * 4], extra_parts=[piano]))
    assert [n["onset_sec"] for n in exp["notes"]] == [0, 1, 2, 3, 4, 4.5, 5, 5.5]


def test_same_beat_marks_on_two_parts_sung_part_wins(tmp_path):
    piano = [[metronome(100)] + [note("C", 3)] * 4]
    exp = parse_score(write_xml(tmp_path, [[metronome(60)] + [note("C", 5)] * 4], extra_parts=[piano]))
    assert exp["tempo_bpm"] == 60 and exp["notes"][1]["onset_sec"] == 1


def test_dotted_quarter_tempo_change(tmp_path):
    # Dotted-quarter = 40 means 60 quarter notes per minute
    exp = parse_score(write_xml(tmp_path, [[metronome(120)] + [note("C", 4)] * 4, [metronome(40, dotted=True)] + [note("D", 4)] * 2]))
    assert [n["onset_sec"] for n in exp["notes"]] == [0, 0.5, 1, 1.5, 2, 3]


# --------------------------------------------------------------------------- fermatas


FERMATA = '<notations><fermata type="upright"/></notations>'


def held(snippet: str) -> str:
    """Put a fermata on a <note> snippet."""
    return snippet.replace("</note>", FERMATA + "</note>", 1)


def flagged(exp):
    return [n["id"] for n in exp["notes"] if n.get("fermata")]


def test_fermata_on_a_note_flags_only_that_entry(tmp_path):
    exp = parse_score(write_xml(tmp_path, [[note("C", 4), note("D", 4), held(note("E", 4)), note("F", 4)]]))
    assert flagged(exp) == ["m1-n2"]
    assert all("fermata" not in n for n in exp["notes"] if n["id"] != "m1-n2")  # only fermata entries get the key
    assert exp["notes"][2]["fermata"] is True


def test_fermata_on_a_rest(tmp_path):
    rest = "<note><rest/><duration>1</duration><voice>1</voice><type>quarter</type></note>"
    exp = parse_score(write_xml(tmp_path, [[note("C", 4), note("D", 4), held(rest), note("F", 4)]]))
    assert flagged(exp) == ["m1-n2"]


def test_fermata_on_the_second_half_of_a_tied_note(tmp_path):
    tie_start = ('<note><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration><tie type="start"/>'
                 '<voice>1</voice><type>quarter</type><notations><tied type="start"/></notations></note>')
    tie_stop = ('<note><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration><tie type="stop"/>'
                '<voice>1</voice><type>quarter</type><notations><tied type="stop"/><fermata type="upright"/></notations></note>')
    exp = parse_score(write_xml(tmp_path, [[note("C", 4), note("D", 4), note("E", 4), tie_start], [tie_stop] + [note("A", 4)] * 3]))
    assert flagged(exp) == ["m1-n3"]  # the merged tied entry, whose render_ids include m2-n0


def test_piano_fermata_while_the_voice_rests(tmp_path):
    rest = "<note><rest/><duration>1</duration><voice>1</voice><type>quarter</type></note>"
    piano = [[note("C", 3), note("C", 3), held(note("C", 3)), note("C", 3)]]
    exp = parse_score(write_xml(tmp_path, [[note("C", 5), note("D", 5), rest, note("E", 5)]], extra_parts=[piano]))
    assert flagged(exp) == ["m1-n2"]  # the singer waits for the pianist


def test_long_piano_fermata_flags_the_voice_entry_where_it_ends(tmp_path):
    half = "<note><pitch><step>C</step><octave>3</octave></pitch><duration>2</duration><voice>1</voice><type>half</type></note>"
    piano = [[note("C", 3), note("C", 3), held(half)]]  # held from beat 2 to beat 4
    exp = parse_score(write_xml(tmp_path, [[note("C", 5), note("D", 5), note("E", 5), note("F", 5)]], extra_parts=[piano]))
    assert flagged(exp) == ["m1-n3"]  # the pause comes at the end of the held chord
