#!/usr/bin/env bash
# run_extend_and_retrain.sh -- Unified runner for:
# 1. Rendering extended guidance weights (0.5x g1024, 1.5x g3072) across 29 choice models
# 2. Rebuilding the interactive dashboard choice_clips_chroma.html
# 3. Retraining the best LatCH chroma head (C3 same_chroma d512 depth 8, lr 8e-4, batch 64, 40 ep, cosine decay)
set -u

SAO=/home/kim/Projects/SAO
cd "$SAO" || exit 1

LOG_RENDER="/home/kim/.gemini/antigravity/brain/62fc5213-e94b-4c13-86bf-69147f02f03c/scratch/extend_weights_render.log"

echo "$(date +%H:%M) [1/2] Acquiring GPU lock for extended weights render..."
until "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) Waiting for GPU lock..."
    sleep 15
done

echo "$(date +%H:%M) Starting extended weights rendering pass (0.5x g1024, 1.5x g3072)..."
$SAO/.venv/bin/python "$SAO/eval/render_choice_clips_chroma.py" > "$LOG_RENDER" 2>&1
rc_render=$?

"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1

if [ $rc_render -ne 0 ]; then
    echo "$(date +%H:%M) ERROR: Render failed with code $rc_render! See $LOG_RENDER"
    exit $rc_render
fi

echo "$(date +%H:%M) Render completed successfully. Rebuilding choice_clips_chroma.html..."
$SAO/.venv/bin/python "$SAO/eval/build_choice_clips_page.py"

echo "$(date +%H:%M) [2/2] Launching 40-epoch retrain of best chroma head..."
bash "$SAO/latch/run_best_chroma_retrain_40ep.sh"
rc_train=$?

echo "$(date +%H:%M) All tasks completed with return code $rc_train"
exit $rc_train
