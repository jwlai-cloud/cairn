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
# Trim points and caption timings both come from captures/beats.json, which capture.mjs
# measures against the video clock. Nothing here is hand-timed.
set -euo pipefail

RAW="${1:?usage: edit.sh <raw.webm> [out.mp4] [beats.json]}"
OUT="${2:-captures/cairn-demo.mp4}"
BEATS="${3:-captures/beats.json}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Start at the first beat, which drops the page load and reset preamble; end at the last.
read -r START DUR < <(python3 - "$BEATS" <<'PY'
import json, sys
beats = json.load(open(sys.argv[1]))
start = beats[0]["at"]
print(f'{start:.3f} {beats[-1]["at"] + beats[-1]["seconds"] - start:.3f}')
PY
)

python3 captures/captions.py "$BEATS" > "$WORK/captions.ass"

# Captions are burned after the upscale so the type is rendered at 4K rather than
# scaled up into it, and the .ass header declares that frame so libass sizes against it.
echo "cutting $RAW from ${START}s for ${DUR}s"
ffmpeg -v error -y -ss "$START" -t "$DUR" -i "$RAW" \
  -vf "scale=3840:-2:flags=lanczos,ass=filename='$WORK/captions.ass'" \
  -an -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -r 30 "$OUT"

total=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT")
secs=${total%.*}
printf '\n%s\n' "$OUT"
printf 'runtime: %d:%02d  (5:00 cap, %ds of headroom)\n' \
  "$((secs / 60))" "$((secs % 60))" "$((300 - secs))"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=nw=1 "$OUT"
ls -lh "$OUT" | awk '{print "size:", $5}'
