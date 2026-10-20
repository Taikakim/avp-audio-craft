#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-21)
# run_kuang_plan_p1_mid.sh -- P1 spectral probe on P0's mid-run checkpoints (ep10, then ep5), after the B runner exits.
# Why: on the final ep20 checkpoint every probe raised held-out loss (the run had overshot along its leading momentum
# directions); the open question is whether the bulk tolerates a bigger step while the loss is still moving.
# Each probe ~25 min; one starts only if it can finish before DEADLINE.
set -u
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
POUT=/run/media/kim/Mantu/latch_sweep/kuang_plan_P_20261017
DEADLINE=${DEADLINE:-$(date -d '06:45' +%s)}; [ "$DEADLINE" -lt "$(date +%s)" ] && DEADLINE=$((DEADLINE + 86400))
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
# same handle as the B runner, which releases the lock on exit: wait for it to be gone first
while pgrep -f '^bash eval/run_kuang_plan_b\.sh' >/dev/null; do sleep 30; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE test plan P1 on mid-run checkpoints, ~25 min each" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    [ "$(date +%s)" -gt "$DEADLINE" ] && { echo "$(date +%H:%M) deadline passed while waiting"; exit 0; }
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 60
done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
for ep in 10 5; do
  out="$POUT/P1_probe_y_ep$ep"
  [ -f "$out" ] && continue
  if [ $(( $(date +%s) + 1800 )) -gt "$DEADLINE" ]; then echo "$(date +%H:%M) ep$ep not started: deadline"; break; fi
  echo "$(date +%H:%M) P1 ep$ep"
  ( cd /tmp && "$LPY" "$SAO/stable-audio-3/scripts/latch/spectral_probe.py" --ckpt "$POUT/P0_E05_anchor/latch_sa3_onset_per_beat_ts_ep$ep.pt" \
      --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --feature onset_per_beat_ts --val-frac 0.05 --val-seed 0 \
      --val-group-by relpath --lr 1e-2 --point y --repeats 3 --out "$out" > "$out.log" 2>&1 )
  rc=$?
  echo "$(date +%H:%M) P1 ep$ep rc=$rc"
done
echo "$(date +%H:%M) P1 mid done"
