#!/bin/bash
set -uo pipefail
cd /home/kim/Projects/SAO
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
PY=/home/kim/Projects/SAO/.venv/bin/python
echo "[chain $(date +%H:%M)] waiting for Gate B to finish"
while pgrep -f gate_b_seed_fan.py >/dev/null 2>&1; do sleep 20; done
echo "[chain $(date +%H:%M)] Gate B done -> EMA-help render"
${PY} eval/ema_help_eval.py
echo "[chain $(date +%H:%M)] EMA-help renders done; measuring (mir venv)"
/home/kim/Projects/mir/mir/bin/python eval/latch_sa3_sweep_measure.py --root ema_help_20260719 2>&1 | tail -5 || echo "[chain] measure needs manual args-check"
echo "[chain $(date +%H:%M)] DONE"
