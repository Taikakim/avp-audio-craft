#!/bin/bash
# Owner: ANTIGRAVITY (created 2026-10-29)
# run_chroma_avp_matrix.sh -- Orchestrates rendering and dashboard generation
# for the AVP retrained chroma head comparative evaluation matrix.
set -u
SAO=/home/kim/Projects/SAO
cd "$SAO" || exit 1

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4

LOG=/home/kim/sao_runs/chroma_avp_matrix_$(date +%Y%m%d).log
mkdir -p /home/kim/sao_runs
exec >>"$LOG" 2>&1

echo "$(date +%H:%M) Waiting for training runner to finish..."
while pgrep -f "latch/run_chroma_avp_retrain.sh" >/dev/null; do
    sleep 30
done
echo "$(date +%H:%M) Training runner completed. Checking GPU lock..."

until Misc/gpu_guard.sh acquire ANTIGRAVITY $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) Waiting for GPU lock..."
    sleep 30
done
trap 'Misc/gpu_guard.sh release ANTIGRAVITY >/dev/null 2>&1' EXIT

echo "$(date +%H:%M) GPU acquired. Starting chroma AVP matrix render..."
.venv/bin/python eval/chroma_avp_matrix_render.py
rc=$?
if [ $rc -ne 0 ]; then
    echo "$(date +%H:%M) Render failed with rc=$rc"
    exit $rc
fi

echo "$(date +%H:%M) Building listening dashboard..."
.venv/bin/python Misc/build_chroma_avp_matrix_page.py

echo "$(date +%H:%M) Running leak check on generated HTML..."
LEAKS=$(grep -rnoE '/home/|/run/media|password|token=|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' ~/evals_aac/chroma_avp_matrix.html ~/evals_aac/chroma_avp_matrix/index.html || true)
if [ -n "$LEAKS" ]; then
    echo "$(date +%H:%M) WARNING: Potential leak detected:"
    echo "$LEAKS"
    exit 1
fi

echo "$(date +%H:%M) ALL DONE. Matrix rendered, staged, and clean."
