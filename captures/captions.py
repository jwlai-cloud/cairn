#!/usr/bin/env python3
"""Emit burned-in captions for the demo cut.

The video carries no narration track, so the captions are the argument. Each one
states what the beat *proves*, not what is on screen - a judge watching muted, or at
360p on a phone, has to be able to follow the claim without the voiceover.

Timings come from captures/beats.json, the wall clock times capture.mjs measured. They
are also the output times, because edit.sh restores real time before burning these in:
the raw recording plays about eleven per cent slow, and captions cut to the raw timeline
miss their own shots by up to twelve seconds. Captions key off the beat label rather
than a time, so a re-record re-times them with no edit here.

ASS rather than SRT, purely so the header can declare the frame it was written for.
libass assumes 288 lines for a plain subtitle file, so a size chosen for a 2400-line
frame gets scaled up by eight and fills the screen.

    python3 captures/captions.py [beats.json] > captions.ass
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent

# Keyed by the beat labels in capture.mjs. Two lines maximum - a third does not fit the
# safe area. A beat with no entry here plays without a caption.
CAPTIONS = {
    "Normal shift: 16 900 t of 28 000 t, eight trucks, no alerts":
        "Eight hours into a twelve-hour shift.\n"
        "Four systems, each about to be exactly right - and useless.",
    "Five signals from four systems land on the timeline":
        "Five signals. Four source systems.\n"
        "Not one of them knows they are the same incident.",
    "Four specialists in parallel; spine fills with measured durations":
        "Four specialists run in parallel in a bounded Strands graph.\n"
        "The edges carry typed findings, not just execution order.",
    "STALE telemetry and a 13-minute source CONFLICT, both surfaced":
        "Bad evidence is surfaced, not smoothed over.\n"
        "Telemetry stale by 15 min. Two forecasts disagree - both kept.",
    "Agent cards: tool chips, evidence counts, confidence, durations":
        "Every claim carries an evidence id, a confidence,\n"
        "and a measured duration.",
    "Protect safety: +4 900 t, LOW risk":
        "Protect safety: stand down early. +4 900 t.",
    "Preserve equipment: +6 100 t, crusher capped":
        "Preserve equipment: cap the crusher. +6 100 t.",
    "Recover tonnes: +7 600 t, recommended, reason shown":
        "Recover tonnes: reroute, draw the stockpile. +7 600 t.\n"
        "All three respect the ramp closure. None may trade it away.",
    "DENIED: rule T4-PROHIBITED-INTERLOCK, tier 4, no model call":
        "DENIED. Tier 4, rule T4-PROHIBITED-INTERLOCK.\n"
        "Decided by deterministic policy - with no model call at all.",
    "Policy escalates to a named role":
        "Even a permitted action does not just happen.\n"
        "Policy escalates it to a named, accountable role.",
    "Scoped approval: token bound to plan version and evidence hash":
        "The approval is scoped to those assets, bound to the plan version\n"
        "and the evidence hash, expiring, and good exactly once.",
    "Dispatch times out AFTER the call may have applied -> UNKNOWN":
        "Dispatch times out AFTER the call may already have applied.\n"
        "The outcome is held as UNKNOWN.",
    "Blind retry REFUSED: RECONCILIATION_REQUIRED":
        "A blind retry is REFUSED: RECONCILIATION_REQUIRED.\n"
        "It cannot prove the first call did not land.",
    "Reconciled: UNKNOWN -> RECONCILING -> SUCCEEDED":
        "Only an authoritative source closes it.\n"
        "UNKNOWN, then RECONCILING, then SUCCEEDED.",
    "Outcome verified: truck still down, residual risks still open":
        "Simulation only. The truck is still down and the residual\n"
        "risks are still open - the outcome is not flattered.",
    "Audit: event -> evidence -> findings -> policy -> approval -> action -> outcome":
        "The whole decision reconstructs: event, evidence, findings,\n"
        "policy, approval, action, outcome.",
    "Scroll the full chain":
        "An append-only ledger. Every stage writes to it,\n"
        "and nothing can rewrite it.",
    "Reset: the same fixtures replay to the same decision":
        "The same fixtures replay to the same decision, exactly.",
}

# Written for the 4K cut. Sizes are in these units, so they survive any output scale.
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


def main() -> None:
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "beats.json"
    beats = json.loads(path.read_text())

    unknown = {b["label"] for b in beats} - set(CAPTIONS)
    if unknown:
        # A renamed beat would otherwise silently lose its caption.
        print(f"beat with no caption: {sorted(unknown)[0]!r}", file=sys.stderr)
        raise SystemExit(1)

    # The cut starts at the first beat, so drop the load and reset preamble with it.
    origin = beats[0]["at"]
    print(HEADER)
    for b in beats:
        text = CAPTIONS[b["label"]]
        if not text:
            continue
        start, end = b["at"] - origin, b["at"] + b["seconds"] - origin
        print(f"Dialogue: 0,{stamp(start)},{stamp(end)},Cue,,0,0,0,,"
              f"{text.replace(chr(10), r'\N')}")


if __name__ == "__main__":
    main()
