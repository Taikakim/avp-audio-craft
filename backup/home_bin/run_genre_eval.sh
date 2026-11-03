#!/usr/bin/env bash
set -uo pipefail
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
PY=/home/kim/Projects/SAO/.venv/bin/python
cd /home/kim/Projects/SAO/control
BASE=/run/media/kim/Mantu/sa3_control_runs
for V in A C; do
  echo "=== genre_eval fp$V START $(date +%H:%M:%S) ==="
  "$PY" -m sa3_control.genre_eval \
    --adapter "$BASE/style_fp${V}_adamw/riffer_final.pt" \
    --out-dir "$BASE/genre_eval_fp${V}" \
    --genres 0,3,5,8 --gains 6,12 --seeds 1234 --baseline \
    --duration 15 --steps 40 --cfg 7.0 --prompt "electronic music" \
    2>&1 | grep -E '\[genre_eval\]|Error|Traceback|core'
  echo "=== genre_eval fp$V DONE $(date +%H:%M:%S) ==="
done
echo "=== GENRE EVAL COMPLETE $(date +%H:%M:%S) ==="
