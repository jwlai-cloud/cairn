#!/usr/bin/env python3
"""Burn-in captions for the assembled cut.

These are not subtitles. The narration carries the story; a caption states the claim the
beat proves, so a judge watching muted, or at 360p on a phone, can still follow it. They
are deliberately shorter than what is spoken.

The six slide frames get none - three architecture, three method. They carry their own
text, and a caption over a slide is two captions arguing.

Timings come from captures/narration.md. That file is the plan and edit.sh assembles the
output to match it, so its times are the output times.

Captions are keyed by cue position, not by timecode. Timecodes move every time the holds
are recalibrated - which happens after any wording change - and keying on them meant
re-keying this table twice for edits that changed no caption at all. Position is stable
under re-timing. It is not stable under inserting or removing a cue, so the count is
asserted: an inserted cue fails loudly rather than shifting every caption by one.

ASS rather than SRT, so the header can declare the frame it was written for. libass
assumes 288 lines for a plain subtitle file, and a size chosen for a 2400-line frame gets
scaled up by eight and fills the screen.

    python3 captures/captions.py --assembled > captions.ass
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
SHEET = HERE / "narration.md"
CUE = re.compile(r"^\|\s*(\d+):(\d{2})\s*\|\s*(\d+)s\s*\|")

# One entry per cue, in sheet order. None means no caption: the six slide frames carry
# their own text, and a caption over a slide is two captions arguing.
CAPTIONS: list[str | None] = [
    "A decision layer for a mine shift.\nIt recommends. It never authorises.",
    "Synthetic scenario. Four systems, each correct.\nNone of them sees the combined decision.",
    "The decision loop. Agents interpret evidence.\nPolicy, approval and execution stay deterministic.",
    "A bounded Strands graph.\nFour specialists in parallel, not a chain of handovers.",
    "Each specialist returns a structured finding.\nEvidence and uncertainty travel with it.",
    "Fifteen minutes stale, and marked stale.\nTwo forecasts disagree, and both are kept.",
    "Three options, each giving up something different.\nA visible trade-off, with evidence behind it.",
    "DENIED by a deterministic policy service.\nNo model call. Nothing to talk past.",
    "Approval bound to a named role and this plan version.\nExpiring, and good exactly once.",
    "Timed out after the call may have applied.\nHeld UNKNOWN. A blind retry is refused.",
    None, None, None,          # architecture frames
    None, None, None,          # method frames
    "Event, evidence, findings, policy,\napproval, action, outcome.",
    "It recommends. It does not authorise.",
]

WIDTH, HEIGHT = 3840, 2400

HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cue,Helvetica Neue,64,&H00F6EDE6,&H00F6EDE6,&H14140B08,&H14140B08,0,0,0,0,100,100,0,0,3,22,0,2,240,240,24,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""


def stamp(seconds: float) -> str:
    cs = round(seconds * 100)
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6_000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def cues() -> list[tuple[float, int]]:
    out = []
    for line in SHEET.read_text().splitlines():
        m = CUE.match(line)
        if m:
            out.append((int(m[1]) * 60 + int(m[2]), int(m[3])))
    return out


def main() -> None:
    if "--assembled" not in sys.argv:
        sys.exit("only --assembled is supported; the cut is assembled from two sources")

    sheet = cues()
    if len(sheet) != len(CAPTIONS):
        sys.exit(f"the sheet has {len(sheet)} cues but this table has {len(CAPTIONS)} entries; "
                 "a cue was added or removed, so add or remove its entry rather than "
                 "letting every caption shift by one")

    print(HEADER)
    for (at, hold), text in zip(sheet, CAPTIONS):
        if not text:
            continue
        print(f"Dialogue: 0,{stamp(at)},{stamp(at + hold)},Cue,,0,0,0,,"
              f"{text.replace(chr(10), r'\N')}")


if __name__ == "__main__":
    main()
