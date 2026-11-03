#!/usr/bin/env bash
set -uo pipefail
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
PY=/home/kim/Projects/SAO/.venv/bin/python
cd /home/kim/Projects/SAO/control
BASE=/run/media/kim/Mantu/sa3_control_runs
# Round 2: only WELL-REPRESENTED genres (all >600 crops) so a null isn't just "model never saw it".
# Goa(0) Psy-Trance(1) Trance(2) Progressive Trance(4) Acid(7). Gain 6 (round-1 sweet spot), 2 seeds.
for V in A C; do
  echo "=== genre_eval_r2 fp$V START $(date +%H:%M:%S) ==="
  "$PY" -m sa3_control.genre_eval \
    --adapter "$BASE/style_fp${V}_adamw/riffer_final.pt" \
    --out-dir "$BASE/genre_eval_fp${V}_r2" \
    --genres 0,1,2,4,7 --gains 6 --seeds 1234,5678 --baseline \
    --duration 15 --steps 40 --cfg 7.0 --prompt "electronic music" \
    2>&1 | grep -E '\[genre_eval\]|Error|Traceback'
  echo "=== genre_eval_r2 fp$V DONE $(date +%H:%M:%S) ==="
done
echo "=== GENRE EVAL R2 COMPLETE $(date +%H:%M:%S) ==="
