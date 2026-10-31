#!/usr/bin/env bash
# run_choice_clips_mood_eval.sh -- executes GPU renders for 56-dim Mood LatCH head (ep40 and ep40_ema0.25),
# builds the interactive page, and links it in index.html.
set -euo pipefail

SAO=/home/kim/Projects/SAO
PY=$SAO/stable-audio-3/.venv/bin/python

until "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) Waiting for GPU lock..."
    sleep 20
done
trap '"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1' EXIT

echo "$(date +%H:%M) GPU acquired. Running mood choice clips render across representative models..."
$PY "$SAO/eval/render_choice_clips_mood.py" --rows 2,5,7,11,22,28 --heads ep40,ep40_ema0.25

echo "$(date +%H:%M) Renders finished. Rebuilding HTML dashboard..."
$PY "$SAO/eval/build_mood_eval_page.py"

echo "$(date +%H:%M) All mood eval tasks complete!"
