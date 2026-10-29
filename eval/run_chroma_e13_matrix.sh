#!/usr/bin/env bash
# Owner: ANTIGRAVITY (created 2026-10-29)
# EXPERIMENTS E13 follow-up: Parameter exploration matrix for the E13 modular retrained head
# (latch_sa3_same_chroma_ep10.pt) on curated Goa DoRA checkpoint (subloss_k24 biggoa t512 ep63).
# Sweeps:
#   - Checkpoint: medium-base vs subloss_k24 DoRA
#   - Guidance Weight: 0, 512, 1024, 2048, 4096
#   - CFG scale: 3.0, 5.0, 7.0
#   - Sampling steps: 25, 40, 50
#   - Guidance schedule: alpha vs flat
#   - Weak seed s5678 vs control seed s1234
#
# Usage:
#   bash eval/run_chroma_e13_matrix.sh
set -euo pipefail
SAO=/home/kim/Projects/SAO
cd "$SAO"

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export ROCR_VISIBLE_DEVICES=0
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4

LOG=/home/kim/sao_runs/chroma_e13_matrix_render.log
mkdir -p /home/kim/sao_runs
exec >> "$LOG" 2>&1

echo "[$(date +%H:%M:%S)] Waiting for GPU lock..."
until Misc/gpu_guard.sh acquire ANTIGRAVITY $$; do
    sleep 30
done
trap 'Misc/gpu_guard.sh release ANTIGRAVITY' EXIT

echo "[$(date +%H:%M:%S)] GPU lock acquired by ANTIGRAVITY ($$)"
.venv/bin/python eval/chroma_e13_matrix_render.py
echo "[$(date +%H:%M:%S)] Render complete. Building dashboard..."
.venv/bin/python Misc/build_chroma_e13_matrix_page.py
echo "[$(date +%H:%M:%S)] ALL DONE."
