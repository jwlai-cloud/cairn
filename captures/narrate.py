#!/usr/bin/env python3
"""Build a narration track from the cue sheet, placed on the video's own timeline.

Words and timings both come from the table in captures/narration.md, because that sheet
is now the output timeline. edit.sh assembles the cut to match it: each source is
corrected for its own recording slowdown and then trimmed to the durations declared here,
which was verified at 288.1 seconds against the sheet's 4:48.

An earlier version read timings from captures/beats.json instead, to avoid hand-written
times drifting from the take. That was right when the video was one continuous recording.
It stopped being right once the three TOGAF frames were spliced in: they have no app
beats, so the sheet has fifteen cues where the app take has twelve.

Each line is laid at its cue rather than concatenated, so a line that runs long overruns
only its own beat instead of pushing every later line out of sync with the picture.
Overruns are reported rather than silently trimmed, because the fix is to cut the
sentence, not to talk faster.

Two synthesis providers, neither required.

`say` is macOS built-in: no network, no key, no account, and it sounds like it. It stays
the default so the pipeline runs anywhere.

`gcloud` uses Google Cloud Text-to-Speech, which is markedly better. It needs application
default credentials and the texttospeech API enabled on a project, and it bills that
project - fractions of a cent for this script, but not free. Studio voices are built for
long-form narration and honour speakingRate; the Chirp3-HD family sounds excellent and
only partly honours it. Either is fine, because holds are measured rather than assumed.

A human take still beats both. The cue sheet is the same either way.

    python3 captures/narrate.py                                   # macOS say
    python3 captures/narrate.py --provider gcloud                  # Cloud TTS
    python3 captures/narrate.py --provider gcloud --calibrate      # re-time for it
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
# A cue row opens with a timecode and a hold; the spoken line is always the last cell,
# so the columns in between (screen action, highlight target) can change freely.
CUE = re.compile(r"^\s*(\d+):(\d{2})\s*$")
HOLD = re.compile(r"^\s*(\d+)s\s*$")


def cues(path: pathlib.Path) -> list[tuple[float, int, str]]:
    out = []
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = line.split("|")[1:-1]
        if len(cells) < 3:
            continue
        at, hold = CUE.match(cells[0]), HOLD.match(cells[1])
        if at and hold:
            out.append((int(at[1]) * 60 + int(at[2]), int(hold[1]), cells[-1].strip()))
    return out


def duration(path: pathlib.Path) -> float:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(probe.stdout.strip())


def _say_speaker(args):
    """macOS `say`, resampled to the rate the mix uses."""
    def speak(text: str, wav: pathlib.Path) -> None:
        aiff = wav.with_suffix(".aiff")
        subprocess.run(["say", "-v", args.voice, "-r", str(args.rate), "-o", str(aiff), text],
                       check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff),
                        "-ar", "48000", "-ac", "1", str(wav)], check=True)
    return speak


def _gcloud_speaker(args):
    """Google Cloud Text-to-Speech over REST, authorised by application default credentials.

    REST and the gcloud CLI rather than a client library, so this adds no dependency to a
    project whose evaluation gate must run on a clean checkout with no account. If the
    credentials are missing the error says so instead of producing silence.
    """
    import base64
    import json as _json
    import urllib.error
    import urllib.request

    def _sh(*cmd: str) -> str:
        out = subprocess.run(cmd, capture_output=True, text=True)
        return out.stdout.strip()

    token = _sh("gcloud", "auth", "application-default", "print-access-token")
    if not token:
        sys.exit("no application default credentials: run `gcloud auth application-default login`")
    project = args.gcloud_project or _sh("gcloud", "config", "get-value", "project")
    if not project:
        sys.exit("no billing project: pass --gcloud-project or set one with `gcloud config set project`")

    def speak(text: str, wav: pathlib.Path) -> None:
        body = _json.dumps({
            "input": {"text": text},
            "voice": {"languageCode": "en-US", "name": args.gcloud_voice},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 48000,
                            "speakingRate": args.gcloud_rate},
        }).encode()
        req = urllib.request.Request(
            "https://texttospeech.googleapis.com/v1/text:synthesize", data=body,
            headers={"Authorization": f"Bearer {token}",
                     "x-goog-user-project": project,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                payload = _json.load(res)
        except urllib.error.HTTPError as exc:
            sys.exit(f"text-to-speech refused the request: {exc.read().decode()[:300]}")
        raw = wav.with_suffix(".raw.wav")
        raw.write_bytes(base64.b64decode(payload["audioContent"]))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw),
                        "-ar", "48000", "-ac", "1", str(wav)], check=True)
    return speak


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="captures/narration.wav")
    ap.add_argument("--provider", choices=("say", "gcloud"), default="say")
    ap.add_argument("--voice", default="Samantha", help="`say` voice name")
    ap.add_argument("--rate", type=int, default=220, help="`say` rate")
    ap.add_argument("--gcloud-voice", default="en-US-Studio-O")
    ap.add_argument("--gcloud-rate", type=float, default=1.2)
    ap.add_argument("--gcloud-project", default=None,
                    help="billing project; defaults to the active gcloud config")
    ap.add_argument("--script", default=str(HERE / "narration.md"))
    ap.add_argument("--beats", default=str(HERE / "beats.json"))
    ap.add_argument("--calibrate", action="store_true",
                    help="print the hold each cue needs, measured, and write nothing else")
    args = ap.parse_args()

    sheet = cues(pathlib.Path(args.script))
    if not sheet:
        sys.exit(f"no cues parsed from {args.script}")

    lines = sheet
    span = sheet[-1][0] + sheet[-1][1]
    print(f"{len(lines)} lines over {int(span)//60}:{int(span)%60:02d} "
          f"({300 - span:.0f}s under the cap)\n")

    speak = _gcloud_speaker(args) if args.provider == "gcloud" else _say_speaker(args)
    work = pathlib.Path(tempfile.mkdtemp())
    parts, overruns = [], []
    for i, (at, hold, text) in enumerate(lines):
        wav = work / f"{i:02d}.wav"
        speak(text, wav)
        spoken = duration(wav)
        mark = " "
        if spoken > hold:
            overruns.append((at, hold, spoken, text))
            mark = "!"
        print(f"{mark} {int(at) // 60}:{int(at) % 60:02d}  hold {hold:4.1f}s  spoken {spoken:5.1f}s")
        parts.append((wav, at))

    if args.calibrate:
        # A word-count model cannot predict per-line pauses, and it guessed wrong twice.
        # These are the measured durations plus a fixed gap, which is what the holds
        # should be. Feed them back into the sheet rather than modelling the rate.
        gap = 1.5
        import math
        print("\nmeasured holds (spoken + %.1fs):" % gap)
        for (at, _, _), (wav, _) in zip(lines, parts):
            print(f"  {int(at) // 60}:{int(at) % 60:02d}\t{int(math.ceil(duration(wav) + gap))}")
        return

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

    label = (f"{args.gcloud_voice} @ rate {args.gcloud_rate}" if args.provider == "gcloud"
             else f"say {args.voice} @ {args.rate}")
    print(f"\n{args.out}  {duration(pathlib.Path(args.out)):.1f}s   voice: {label}")
    for at, hold, spoken, text in overruns:
        print(f"  OVERRUN {int(at) // 60}:{int(at) % 60:02d} by {spoken - hold:.1f}s - cut a sentence: {text[:70]}...")
    if not overruns:
        print("  every line fits its beat")


if __name__ == "__main__":
    main()
