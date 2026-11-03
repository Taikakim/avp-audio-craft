#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
A=/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_AdamW_lr7.5e-5_randomcrop_20ep
SA3PY=/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python
cd /home/kim/Projects/SAO/stable-audio-tools/avp_sa3
for ck in $(ls $A/riffer_step*.pt | sort -t_ -k2 -n); do
  step=$(basename $ck | grep -oE '[0-9]+'); ep=$((step/5400)); out=$A/onset_eval_adamw20_ep$ep
  [ -f $out/onset_eval.json ] && { echo "ep$ep cached"; continue; }
  echo "=== ep$ep (step$step) $(date +%H:%M) ==="
  timeout 600 env FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2 OMP_NUM_THREADS=4 \
    $SA3PY sa3_control/onset_eval.py $ck --prompt "aggressive upbeat goa trance" --gains "2,4,6" --densities "2,4,6,8,10" --seed 777 \
    --notes "AdamW 20ep onset_density lr7.5e-5 randomcrop — rich-matrix prerequisite: per-layer telemetry x control authority across training" \
    --out $out 2>&1 | grep -iE 'corr|wrote' | tail -2
done
echo ADAMW20_DONE
