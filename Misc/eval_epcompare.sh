#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
F=/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_Fusion_opb_lr1.5e-4_30ep
SA3PY=/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python
cd /home/kim/Projects/SAO/stable-audio-tools/avp_sa3
for pair in 5:27000 10:54000 14:75600 15:81000; do
  EP=${pair%:*}; STEP=${pair#*:}
  echo "=== ep$EP (step$STEP) $(date +%H:%M) ==="
  timeout 240 env FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2 OMP_NUM_THREADS=4 \
    "$SA3PY" sa3_control/multi_eval.py "$F/riffer_step$STEP.pt" \
    --prompts "aggressive upbeat goa trance" --seeds 777 --gains "2,4,6" --densities "2,4,6,8" \
    --out "$F/eval_epcompare/ep$EP"
done
echo EPCOMPARE_DONE
