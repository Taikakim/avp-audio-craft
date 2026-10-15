#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-15)
# run_latch_guide_anchor.sh -- wait for the GPU, render the guide_anchor test (146 clips, ~12 min), encode, score, release.
#   bash eval/run_latch_guide_anchor.sh        (run in background; exit = done; resumable)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu2/sa3_control_runs/latch_guide_anchor_20261015
STAGE=$HOME/evals_aac/latch_guide_anchor
export ROCR_VISIBLE_DEVICES=0
cd "$SAO" || exit 2

until KIND=batch NOTE="WINTERMUTE latch guide_anchor test (146 x 20 s renders + PQ), ~15 min" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
echo "$(date +%H:%M) GPU acquired"
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT

"$SAO/.venv/bin/python" eval/latch_guide_anchor_test.py
echo "$(date +%H:%M) render rc=$?"
echo "cells written: $(wc -l < "$OUT/cells.jsonl") / 146"

mkdir -p "$STAGE"
for w in "$OUT"/*.wav; do
    d="$STAGE/$(basename "$w" .wav).m4a"
    [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 128k "$1"'
/home/kim/Projects/mir/mir/bin/python control/sa3_control/clip_metrics.py --roots latch_guide_anchor --workers 12 2>&1 | tail -1
/home/kim/Projects/mir/mir/bin/python control/sa3_control/clip_metrics_audiobox.py --roots latch_guide_anchor 2>&1 | tail -1
echo "$(date +%H:%M) ALL DONE"
