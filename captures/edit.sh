#!/usr/bin/env bash
# Assemble the submission video from the app recording and the slide recording.
#
#   ./captures/edit.sh                      # uses the newest raw takes
#   ./captures/edit.sh app.webm slides.webm out.mp4
#
# Three sources in order: the app up to the reconcile beat, the three TOGAF frames, then
# the app's audit and close beats. capture.mjs tags its beats pre and post, so the split
# point is read rather than hand-written.
#
# Neither recording plays back at the speed it was made. Playwright stamps frames at a
# nominal rate while a page running a 3D scene renders slower, so a session comes out
# around eleven per cent long and fractionally slow. Each source is corrected by its own
# measured ratio before anything is cut, after which the cue sheet's times are the output
# times and captions need no rescaling.
#
# There is no speed ramp. The cut already fits the cap, and compressing a beat costs the
# narration its room.
set -euo pipefail

cd "$(dirname "$0")/.."
APP="${1:-$(ls -t captures/raw-app*.webm 2>/dev/null | head -1)}"
SLIDES="${2:-$(ls -t captures/raw-slides*.webm 2>/dev/null | head -1)}"
OUT="${3:-captures/cairn-silent.mp4}"
BEATS=captures/beats.json
: "${APP:?no app recording found: run node captures/capture.mjs}"
: "${SLIDES:?no slide recording found: run node captures/capture-slides.mjs --video}"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
probe() { ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$1"; }
APP_SECS=$(probe "$APP"); SLIDE_SECS=$(probe "$SLIDES")

read -r K PRE_START PRE_DUR POST_START < <(python3 - "$BEATS" "$APP_SECS" <<'PY'
import json, sys
beats = json.load(open(sys.argv[1]))
video = float(sys.argv[2])
# The recording is longer than the session by a uniform ratio.
k = video / (beats[-1]["at"] + beats[-1]["seconds"])
pre = [b for b in beats if b["section"] == "pre"]
post = [b for b in beats if b["section"] == "post"]
start = beats[0]["at"] * k                      # trims the load and reset preamble
pre_end = (pre[-1]["at"] + pre[-1]["seconds"]) * k
print(f'{k:.6f} {start:.3f} {pre_end - start:.3f} {post[0]["at"] * k:.3f}')
PY
)

echo "app $APP_SECS s, slowdown ${K}x"
echo "  pre    ${PRE_START}s for ${PRE_DUR}s"
echo "  slides $SLIDE_SECS s"
echo "  post   from ${POST_START}s"

# Every source is normalised to the same size, rate and pixel format so concat can copy.
cut() { # cut <in> <ss> <t|-> <slowdown> <out>
  # A plain string, not an array: macOS ships bash 3.2, where expanding an empty array
  # under `set -u` is an unbound-variable error. The value is a bare number, so leaving
  # it unquoted to word-split is safe here.
  local span=""
  [ "$3" != "-" ] && span="-t $3"
  ffmpeg -v error -y -ss "$2" $span -i "$1" \
    -vf "setpts=PTS/${4},scale=3840:2400:force_original_aspect_ratio=decrease,pad=3840:2400:-1:-1:color=0xDEDACF,setsar=1" \
    -an -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -r 30 "$5"
}

# The slide section's declared length comes from the sheet, not a constant. It was 63
# seconds when there were three frames and is 104 with the architecture frames added.
SLIDE_PLAN=$(python3 - <<'PY'
import re
rows = [m for m in (re.match(r'^\|\s*\d+:\d\d\s*\|\s*(\d+)s\s*\|\s*slide\s*\|', l)
                    for l in open('captures/narration.md')) if m]
print(sum(int(m[1]) for m in rows))
PY
)
SLIDE_K=$(python3 -c "print(f'{float('$SLIDE_SECS')/float('$SLIDE_PLAN'):.6f}')")
cut "$APP"    "$PRE_START"  "$PRE_DUR" "$K"       "$WORK/1-pre.mp4"
cut "$SLIDES" 0             -          "$SLIDE_K" "$WORK/2-slides.mp4"
cut "$APP"    "$POST_START" -          "$K"       "$WORK/3-post.mp4"

for f in "$WORK"/[123]-*.mp4; do printf "file '%s'\n" "$f" >> "$WORK/list.txt"; done
ffmpeg -v error -y -f concat -safe 0 -i "$WORK/list.txt" -c copy "$WORK/joined.mp4"

# Captions ride the assembled timeline, which is the cue sheet's timeline.
python3 captures/captions.py --assembled > "$WORK/captions.ass"
ffmpeg -v error -y -i "$WORK/joined.mp4" -vf "ass=filename='$WORK/captions.ass'" \
  -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -r 30 "$OUT"

total=$(probe "$OUT"); secs=${total%.*}
printf '\n%s\n' "$OUT"
printf 'runtime: %d:%02d  (5:00 cap, %ds of headroom)\n' "$((secs/60))" "$((secs%60))" "$((300-secs))"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=nw=1 "$OUT"
ls -lh "$OUT" | awk '{print "size:", $5}'
