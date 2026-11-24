#!/usr/bin/env bash
# Records docs/demo.tape into a GIF without hogging RAM. Usage: docs/record.sh [OUT.gif]   (default docs/demo.gif)
#
# - vhs only writes an MP4 (streamed). Its own GIF step buffers every frame for the palette, which takes GBs.
# - The GIF is then made in two light ffmpeg passes.
# - Everything runs niced; with systemd it runs in a memory-capped scope (MEM, default 2G), and a watchdog
#   stops the recording if free RAM drops below MIN_FREE megabytes (default 1500).
set -euo pipefail
cd "$(dirname "$0")/.."
out=${1:-docs/demo.gif}
tmp=$(mktemp -d); unit="aware-rec-$$"; wd=""
have_sd=0; command -v systemd-run >/dev/null && systemd-run --user --scope -q true 2>/dev/null && have_sd=1

stop_all() {   # kills everything the recording started (vhs, chrome, ttyd, the demo's tmux server and claude)
  if [ $have_sd = 1 ]; then systemctl --user kill --signal=SIGKILL "$unit.scope" 2>/dev/null || true
  else pkill -TERM -P $$ 2>/dev/null || true; fi
}
cleanup() { [ -n "$wd" ] && kill "$wd" 2>/dev/null; stop_all; rm -rf "$tmp"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

capped() {   # capped NAME cmd...
  local name=$1; shift
  if [ $have_sd = 1 ]; then systemd-run --user --scope -q --unit="$name" -p "MemoryMax=${MEM:-2G}" -p MemorySwapMax=0 nice -n 10 "$@"
  else nice -n 10 "$@"; fi
}

( while sleep 3; do
    free_mb=$(awk '/MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)
    if [ "$free_mb" -lt "${MIN_FREE:-1500}" ]; then echo "record.sh: only ${free_mb}MB free, stopping" >&2; stop_all; exit; fi
  done ) & wd=$!

capped "$unit" vhs docs/demo.tape -o "$tmp/raw.mp4"
kill "$wd" 2>/dev/null; wd=""
vf="fps=${FPS:-10},scale=${WIDTH:-1200}:-1:flags=lanczos"
capped "aware-enc-$$" ffmpeg -loglevel error -threads 2 -i "$tmp/raw.mp4" -vf "$vf,palettegen=stats_mode=diff" -y "$tmp/palette.png"
capped "aware-enc2-$$" ffmpeg -loglevel error -threads 2 -i "$tmp/raw.mp4" -i "$tmp/palette.png" \
  -lavfi "$vf[x];[x][1:v]paletteuse=dither=none:diff_mode=rectangle" -y "$out"
echo "wrote $out ($(du -h "$out" | cut -f1))"
