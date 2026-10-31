#!/usr/bin/env bash
# run_full_eval_and_mood_train.sh -- End-to-end pipeline:
# 1. Renders ep40 & ep40_ema0.25 eval clips and generates ep10_vs_ep40_chroma.html
# 2. Trains the 56-dim Mood LatCH conditioning head for 40 epochs
set -euo pipefail

SAO=/home/kim/Projects/SAO
LOG="/home/kim/.gemini/antigravity/brain/62fc5213-e94b-4c13-86bf-69147f02f03c/scratch/full_execution.log"

echo "$(date +%H:%M) [1/2] Starting Phase 1: Chroma Head-to-Head Evaluation (ep10 vs ep40 vs ep40_ema0.25)..." | tee -a "$LOG"
bash "$SAO/eval/run_ep10_vs_ep40_eval.sh" | tee -a "$LOG"

echo "$(date +%H:%M) [2/2] Starting Phase 2: 40-Epoch Mood LatCH Head Training (C3_mood_lr8e-4_b64_cos40)..." | tee -a "$LOG"
bash "$SAO/latch/run_best_mood_train_40ep.sh" | tee -a "$LOG"

echo "$(date +%H:%M) All tasks successfully finished!" | tee -a "$LOG"
