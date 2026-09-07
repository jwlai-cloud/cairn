#!/usr/bin/env bash
# Cut a raw capture down to a submission video.
#
#   ./captures/edit.sh raw.webm [out.mp4] [beats.json]
#
# There is no segment table and no speed ramp. The raw take already fits the five
# minute cap, and speeding a beat up costs the narration its room: captures/narration.md
# is written to these durations, and a beat compressed 2x has half the words. Speed is
# worth reintroducing for exactly one thing - a live model inference with nothing being
# said over it - and it should arrive then, per beat, not as a standing setting.
#
# The recording does not play back at the speed it was made. Playwright stamps frames at
# a nominal 25fps, but a page running a 3D scene renders slower than that, so a session
# that took 253 seconds comes out as 281 seconds of video playing eleven per cent slow -
# which is both visibly sluggish and enough to put the denial caption twelve seconds off
# its own toast. The ratio is uniform; it held to within a frame across beats forty
# seconds apart. So restore real time first, and then the wall clock times that
# capture.mjs measured into captures/beats.json are the output times, exactly. Nothing
# downstream is hand-timed or rescaled.
set -euo pipefail

RAW="${1:?usage: edit.sh <raw.webm> [out.mp4] [beats.json]}"
OUT="${2:-captures/cairn-demo.mp4}"
BEATS="${3:-captures/beats.json}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

VIDEO_SECS=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$RAW")

# SLOWDOWN is how much longer the video is than the session; START is the first beat, in
# video time, which trims the page load and reset preamble off the front.
read -r SLOWDOWN START < <(python3 - "$BEATS" "$VIDEO_SECS" <<'PY'
import json, sys
beats = json.load(open(sys.argv[1]))
slowdown = float(sys.argv[2]) / (beats[-1]["at"] + beats[-1]["seconds"])
print(f'{slowdown:.6f} {beats[0]["at"] * slowdown:.3f}')
PY
)

python3 captures/captions.py "$BEATS" > "$WORK/captions.ass"

# setpts restores real time, so captions can be burned at their measured wall times.
# They go on after the upscale, so the type is rendered at 4K rather than scaled up into
# it, and the .ass header declares that frame so libass sizes against it.
echo "cutting $RAW from ${START}s, correcting ${SLOWDOWN}x slowdown"
ffmpeg -v error -y -ss "$START" -i "$RAW" \
  -vf "setpts=PTS/${SLOWDOWN},scale=3840:-2:flags=lanczos,ass=filename='$WORK/captions.ass'" \
  -an -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -r 30 "$OUT"

total=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT")
secs=${total%.*}
printf '\n%s\n' "$OUT"
printf 'runtime: %d:%02d  (5:00 cap, %ds of headroom)\n' \
  "$((secs / 60))" "$((secs % 60))" "$((300 - secs))"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=nw=1 "$OUT"
ls -lh "$OUT" | awk '{print "size:", $5}'
