#!/usr/bin/env bash
# Cut a raw capture down to a submission video.
#
# Record raw at whatever pace the software actually runs at - including slow real-model
# runs - then compress time here. Speeding up a segment is honest as long as nothing is
# reordered and nothing is faked; a 40 second Bedrock inference shown at 8x is still the
# real inference. What must never be sped up is a beat the viewer has to READ: the
# denial, the approval token, the UNKNOWN refusal.
#
#   ./captures/edit.sh raw.webm out.mp4
#
# Segments are declared below as: START END SPEED LABEL
# SPEED 1 = real time, 4 = four times faster. Times are in the RAW recording.
set -euo pipefail

RAW="${1:?usage: edit.sh <raw.webm> [out.mp4]}"
OUT="${2:-captures/cairn-demo.mp4}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Beats from docs/architecture/10-demo-video-plan.md. Read-critical beats stay at 1x.
SEGMENTS=(
  "0    26   2.0  problem: the quiet room"
  "26   56   2.0  correlation: five signals become one incident"
  "56   82   1.5  evidence: stale and conflicting, both surfaced"
  "82   110  1.5  three options that trade different things away"
  "110  136  1.0  DENIED - tier 4, no model call"
  "136  168  1.0  approval: scoped, expiring, single-use"
  "168  214  1.0  timeout -> UNKNOWN -> retry refused -> reconciled"
  "214  250  1.5  outcome and the audit chain"
  "250  260  2.0  reset and replay"
)

echo "cutting $RAW"
i=0
: > "$WORK/list.txt"
for seg in "${SEGMENTS[@]}"; do
  read -r start end speed label <<<"$seg"
  dur=$(echo "$end - $start" | bc)
  out="$WORK/seg$(printf '%02d' "$i").mp4"
  # setpts divides presentation timestamps, so 1/speed compresses the segment.
  ffmpeg -v error -y -ss "$start" -t "$dur" -i "$RAW" \
    -vf "setpts=PTS/${speed},scale=3840:-2:flags=lanczos" \
    -an -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -r 30 "$out"
  printf "file '%s'\n" "$out" >> "$WORK/list.txt"
  printf "  %-52s %5ss raw -> %5.1fs at %sx\n" "$label" "$dur" "$(echo "$dur / $speed" | bc -l)" "$speed"
  i=$((i + 1))
done

ffmpeg -v error -y -f concat -safe 0 -i "$WORK/list.txt" -c copy "$OUT"

total=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT")
secs=${total%.*}
printf '\n%s\n' "$OUT"
printf 'runtime: %d:%02d  (5:00 cap, %ds of headroom)\n' \
  "$((secs / 60))" "$((secs % 60))" "$((300 - secs))"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=nw=1 "$OUT"
ls -lh "$OUT" | awk '{print "size:", $5}'
