#!/usr/bin/env bash
# run_ep10_vs_ep40_eval.sh -- executes GPU renders for ep40 and ep40_ema0.25 heads,
# builds the interactive page, and links it in index.html.
set -euo pipefail

SAO=/home/kim/Projects/SAO
PY=$SAO/.venv-rocm10-amd/bin/python

until "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) Waiting for GPU lock..."
    sleep 20
done
trap '"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1' EXIT

echo "$(date +%H:%M) GPU acquired. Running ep10 vs ep40 render..."
$PY "$SAO/eval/render_ep10_vs_ep40_eval.py"

echo "$(date +%H:%M) Renders finished. Rebuilding HTML..."
python3 "$SAO/eval/build_ep10_vs_ep40_page.py"

echo "$(date +%H:%M) All eval tasks complete!"
