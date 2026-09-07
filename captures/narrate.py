#!/usr/bin/env python3
"""Build a narration track from the cue sheet, placed on the video's own timeline.

Takes the words from the table in captures/narration.md and the timings from
captures/beats.json, which capture.mjs measured against the recording. The sheet's own
cue column is for the person holding it, not for this: hand-written times drift from the
take, which is exactly how the captions once landed twelve seconds off their own shots.
Each line is laid at its beat rather than concatenated, so a line that runs long overruns
only its own beat instead of pushing every later line out of sync with the picture.
Overruns are reported rather than silently trimmed, because the fix is to cut the
sentence, not to talk faster.

macOS `say` is the floor, not the plan: a synthesised track reads as a project that ran
out of time. Record a human take over the same cue sheet when there is any chance to.

    python3 captures/narrate.py [out.wav] [--voice 'Lee (Premium)'] [--rate 160]
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
ROW = re.compile(r"^\|\s*(\d+):(\d{2})\s*\|\s*(\d+)s\s*\|[^|]*\|\s*(.+?)\s*\|\s*$")


def cues(path: pathlib.Path) -> list[tuple[float, int, str]]:
    out = []
    for line in path.read_text().splitlines():
        m = ROW.match(line)
        if m:
            out.append((int(m[1]) * 60 + int(m[2]), int(m[3]), m[4]))
    return out


def duration(path: pathlib.Path) -> float:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(probe.stdout.strip())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="captures/narration.wav")
    ap.add_argument("--voice", default="Lee (Premium)")
    ap.add_argument("--rate", type=int, default=160)
    ap.add_argument("--script", default=str(HERE / "narration.md"))
    ap.add_argument("--beats", default=str(HERE / "beats.json"))
    args = ap.parse_args()

    sheet = cues(pathlib.Path(args.script))
    if not sheet:
        sys.exit(f"no cues parsed from {args.script}")

    beats = json.loads(pathlib.Path(args.beats).read_text())
    if len(beats) != len(sheet):
        sys.exit(f"{len(sheet)} lines in the cue sheet but {len(beats)} beats in the take; "
                 "they are written one to one, so re-sync the sheet before recording")

    # Beat times are relative to the first beat, which is where the cut starts.
    origin = beats[0]["at"]
    lines = [(b["at"] - origin, b["seconds"], text) for b, (_, _, text) in zip(beats, sheet)]
    worst = max(abs(a - s) for (a, _, _), (s, _, _) in zip(lines, sheet))
    print(f"{len(lines)} lines, worst cue-sheet drift {worst:.1f}s (timings taken from the take)\n")

    work = pathlib.Path(tempfile.mkdtemp())
    parts, overruns = [], []
    for i, (at, hold, text) in enumerate(lines):
        aiff, wav = work / f"{i:02d}.aiff", work / f"{i:02d}.wav"
        subprocess.run(["say", "-v", args.voice, "-r", str(args.rate), "-o", str(aiff), text],
                       check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff),
                        "-ar", "48000", "-ac", "1", str(wav)], check=True)
        spoken = duration(wav)
        mark = " "
        if spoken > hold:
            overruns.append((at, hold, spoken, text))
            mark = "!"
        print(f"{mark} {int(at) // 60}:{int(at) % 60:02d}  hold {hold:4.1f}s  spoken {spoken:5.1f}s")
        parts.append((wav, at))

    # Delay each line to its cue and mix. amix normalises by input count, so the gain is
    # restored afterwards; without that a track of eighteen inputs is inaudible.
    inputs, filters, labels = [], [], []
    for i, (wav, at) in enumerate(parts):
        inputs += ["-i", str(wav)]
        filters.append(f"[{i}:a]adelay={int(at * 1000)}:all=1[d{i}]")
        labels.append(f"[d{i}]")
    graph = ";".join(filters) + ";" + "".join(labels) + \
        f"amix=inputs={len(parts)}:normalize=0:dropout_transition=0[mixed]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph,
                    "-map", "[mixed]", "-ar", "48000", "-ac", "1", args.out], check=True)

    print(f"\n{args.out}  {duration(pathlib.Path(args.out)):.1f}s   voice: {args.voice} @ {args.rate} wpm")
    for at, hold, spoken, text in overruns:
        print(f"  OVERRUN {int(at) // 60}:{int(at) % 60:02d} by {spoken - hold:.1f}s - cut a sentence: {text[:70]}...")
    if not overruns:
        print("  every line fits its beat")


if __name__ == "__main__":
    main()
