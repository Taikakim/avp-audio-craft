#!/usr/bin/env bash
# run_mood_finegrained_eval.sh -- executes GPU renders for the fine-grained weight matrix
# and model combinations on rb_bracket_0, then rebuilds mood_finegrained.html.
set -euo pipefail

SAO=/home/kim/Projects/SAO
PY=$SAO/stable-audio-3/.venv/bin/python

until "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) Waiting for GPU lock..."
    sleep 15
done
trap '"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1' EXIT

echo "$(date +%H:%M) GPU acquired. Running fine-grained weight matrix & model combinations render..."
$PY "$SAO/eval/render_mood_finegrained_matrix.py"

echo "$(date +%H:%M) Renders finished. Rebuilding HTML dashboard..."
$PY "$SAO/eval/build_mood_finegrained_page.py"

echo "$(date +%H:%M) All fine-grained mood eval tasks complete!"
