"""Plot a stage-2 pitch track (and stage-3 sung notes) for debugging.

Usage (from the repo root):
  backend/.venv/bin/python tools/plot_pitch.py samples/c-major-scale/takes/perfect.wav
  backend/.venv/bin/python tools/plot_pitch.py samples/c-major-scale/takes/perfect.wav \\
      --countin 3.0 --out backend/tmp/perfect_pitch.png
  backend/.venv/bin/python tools/plot_pitch.py samples/edge-cases/takes/perfect.wav --no-notes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.stages.pitch import track_pitch  # noqa: E402
from app.stages.segment import segment_notes  # noqa: E402

NOTE_COLOR = "#c45c26"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot stage-2 pitch_track (optionally with stage-3 note overlay)"
    )
    parser.add_argument("wav", type=Path, help="Path to a WAV file")
    parser.add_argument(
        "--countin",
        type=float,
        default=None,
        help="Count-in end in seconds (default: read from sibling .answer.json if present, else 0)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Save PNG here (default: <wav_stem>_pitch.png next to the WAV)",
    )
    parser.add_argument(
        "--dump-json",
        type=Path,
        default=None,
        help="Also write the full pitch_track JSON to this path",
    )
    parser.add_argument(
        "--no-notes",
        action="store_true",
        help="Skip stage-3 overlay (pitch curve + RMS only)",
    )
    args = parser.parse_args()

    wav = args.wav if args.wav.is_absolute() else REPO_ROOT / args.wav
    if not wav.is_file():
        sys.exit(f"WAV not found: {wav}")

    countin = args.countin
    if countin is None:
        answer = wav.with_suffix(".answer.json")
        if answer.is_file():
            countin = float(json.loads(answer.read_text())["settings"]["countin_end_sec"])
        else:
            countin = 0.0

    track = track_pitch(str(wav), countin_end_sec=countin)
    sung = None if args.no_notes else segment_notes(track)

    if args.dump_json is not None:
        out_json = args.dump_json if args.dump_json.is_absolute() else REPO_ROOT / args.dump_json
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(track))
        print(f"wrote {out_json}")

    t = np.asarray(track["t"], dtype=float)
    midi = np.asarray(
        [np.nan if m is None else m for m in track["midi"]],
        dtype=float,
    )
    rms = np.asarray(track["rms"], dtype=float)

    out = args.out
    if out is None:
        out = wav.with_name(f"{wav.stem}_pitch.png")
    elif not out.is_absolute():
        out = REPO_ROOT / out

    fig, (ax_pitch, ax_rms) = plt.subplots(
        2, 1, figsize=(12, 6), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    ax_pitch.plot(t, midi, color="#1f4e79", linewidth=1.0, label="pitch track")

    if sung is not None:
        for i, note in enumerate(sung["notes"]):
            ax_pitch.hlines(
                note["midi"],
                note["start_sec"],
                note["end_sec"],
                colors=NOTE_COLOR,
                linewidth=2.5,
                alpha=0.9,
                label="sung note" if i == 0 else None,
            )
            ax_pitch.axvspan(
                note["start_sec"],
                note["end_sec"],
                color=NOTE_COLOR,
                alpha=0.08,
            )
            ax_pitch.text(
                (note["start_sec"] + note["end_sec"]) / 2,
                note["midi"],
                note["sid"],
                ha="center",
                va="bottom",
                fontsize=8,
                color=NOTE_COLOR,
            )
            # Mark note spans on the RMS panel too (helps see dip-splits)
            ax_rms.axvline(note["start_sec"], color=NOTE_COLOR, linewidth=0.6, alpha=0.5)
            ax_rms.axvline(note["end_sec"], color=NOTE_COLOR, linewidth=0.6, alpha=0.5)

        n_notes = len(sung["notes"])
        title_extra = f"  |  {n_notes} sung notes"
    else:
        title_extra = ""

    ax_pitch.set_ylabel("MIDI")
    ax_pitch.set_title(
        f"{wav.name}  |  countin={countin:.3f}s  |  "
        f"duration={track['duration_sec']:.2f}s  |  hop={track['hop_sec']}s"
        f"{title_extra}"
    )
    ax_pitch.grid(True, alpha=0.3)
    if sung is not None:
        ax_pitch.legend(loc="upper left", fontsize=8)

    ax_rms.plot(t, rms, color="#5b7c99", linewidth=0.8)
    ax_rms.set_ylabel("RMS")
    ax_rms.set_xlabel("t (sec after count-in)")
    ax_rms.grid(True, alpha=0.3)

    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
