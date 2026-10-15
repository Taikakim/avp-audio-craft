#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-15)
# run_latch_early_budget.sh -- wait for the GPU, then render + score the LatCH early-budget bracket.
# Polls Misc/gpu_guard.sh every 5 min (it checks rocm-smi ground truth AND both lockfiles), holds the
# lock for render + Audiobox PQ, releases it, and exits. Resumable: re-running skips finished cells.
#   bash eval/run_latch_early_budget.sh            (run in background; exit = done)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu2/sa3_control_runs/latch_early_budget_20261015
STAGE=$HOME/evals_aac/latch_early_budget
export ROCR_VISIBLE_DEVICES=0
cd "$SAO" || exit 2

until KIND=batch NOTE="WINTERMUTE latch early-budget bracket (250 x 20 s renders + PQ), ~1-2 h" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 300
done
echo "$(date +%H:%M) GPU acquired"
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT

"$SAO/.venv/bin/python" eval/latch_early_budget_bracket.py --legs A,B,C,D
rc=$?
echo "$(date +%H:%M) render rc=$rc"

mkdir -p "$STAGE"
for w in "$OUT"/*/*.wav; do
    leg=$(basename "$(dirname "$w")"); mkdir -p "$STAGE/$leg"
    d="$STAGE/$leg/$(basename "$w" .wav).m4a"
    [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 128k "$1"'
/home/kim/Projects/mir/mir/bin/python control/sa3_control/clip_metrics.py --roots latch_early_budget --workers 12 2>&1 | tail -1
/home/kim/Projects/mir/mir/bin/python control/sa3_control/clip_metrics_audiobox.py --roots latch_early_budget 2>&1 | tail -1
echo "$(date +%H:%M) ALL DONE (render rc=$rc)"
exit $rc
