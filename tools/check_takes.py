"""Run every test take through the real pipeline and compare with its answer key.

    npm run check:takes

Stages 1-4 today (score -> pitch track -> sung notes -> alignment), strict and free mode, for every
samples/<piece>/takes/<take>.wav. Checks the octave shift, the planted skip and extra (near_id), the
time offset and (free mode) the singer's speed. Add stage 5 verdicts here once grading exists.
Exit code 1 if anything is off. AGENTS.md rule 11: run after changing stages 2-5.
"""
import json, sys, time
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from app.stages.score import parse_score
from app.stages.pitch import track_pitch
from app.stages.segment import segment_notes
from app.stages.align import align

problems = runs = 0
for piece in sorted(p.name for p in (REPO / "samples").iterdir() if (p / "takes").is_dir()):
    for take in sorted(f.name.removesuffix(".answer.json") for f in (REPO / f"samples/{piece}/takes").glob("*.answer.json")):
        key = json.loads((REPO / f"samples/{piece}/takes/{take}.answer.json").read_text())
        st = key["settings"]
        expected = parse_score(REPO / f"samples/{piece}/score.musicxml", st["tempo_bpm"])
        t0 = time.time()
        sung = segment_notes(track_pitch(str(REPO / f"samples/{piece}/takes/{take}.wav"), st["countin_end_sec"]))
        n_written = sum(not n["is_rest"] for n in expected["notes"])
        for mode in ["strict", "free"]:
            al = align(expected, sung, mode)
            by_id = {p["id"]: p for p in al["pairs"] if p["id"]}
            issues = []
            if al["octave_shift"] != key["expect"]["octave_shift"]:
                issues.append(f"octave {al['octave_shift']} != {key['expect']['octave_shift']}")
            want_skip = sorted(i for i, v in key["notes"].items() if v["status"] == "skipped")
            got_skip = sorted(i for i, p in by_id.items() if p["type"] == "skipped")
            if got_skip != want_skip:
                issues.append(f"skipped {got_skip} != {want_skip}")
            want_extra = [e["near_id"] for e in key["extras"]]
            got_extra = [p["near_id"] for p in al["pairs"] if p["type"] == "extra"]
            if got_extra != want_extra:
                issues.append(f"extras near {got_extra} != {want_extra}")
            want_off = key["expect"].get("timing_offset_ms", 0) / 1000
            if abs(al["time_offset_sec"] - want_off) > 0.04:
                issues.append(f"offset {al['time_offset_sec']} vs ~{want_off}")
            if mode == "free" and abs(al["tempo_scale"] - 1) > 0.03:
                issues.append(f"tempo_scale {al['tempo_scale']}")
            merged = sum(len(p["sids"]) > 1 for p in al["pairs"])
            joined = sum(bool(p.get("joined")) for p in al["pairs"])
            problems += bool(issues)
            runs += 1
            print(f"{'OK  ' if not issues else 'FAIL'} {piece:<14}{take:<12}{mode:<7} written {n_written:>2}, sung {len(sung['notes']):>2}"
                  f" | shift {al['octave_shift']:>3} offset {al['time_offset_sec']:+.3f} scale {al['tempo_scale']:.3f}"
                  f" | merged {merged} joined {joined} ({time.time() - t0:.1f}s)")
            for i in issues:
                print("       ", i)
print(f"\n{problems} of {runs} runs with problems")
sys.exit(1 if problems else 0)
