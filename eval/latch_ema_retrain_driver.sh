#!/bin/bash
# latch_ema_retrain_driver.sh — Kim ask 2026-07-19: "for all models that seem medium or
# dead, train them longer (2x epochs) and try that." The EVIDENCE-BASED version:
#
# WORKLOG 2026-06-29 already showed raw "more epochs" is the WRONG lever — heads that look
# "architecture-limited" are DAMPING-limited: they find the control direction then DRIFT,
# and >40ep lets late drift leak in and HURTS. What REVERSED a dead head (spectral_skewness,
# ~3x control) was EMA(0.999)+grad-accum2+early-stop — but ONLY skewness ever got it. Every
# other medium/dead head still has no averaged_state_dict.
#
# So this retrains the medium/dead heads with the PROVEN ema_ga2 recipe, in two arms:
#   ema20 = EMA + ga2 + 20ep  (the sweet spot: best skew head moved LEAST from init)
#   ema40 = EMA + ga2 + 40ep  (Kim's "2x epochs", WITH the damping fix — the safe upper bound;
#                              >40 drifts). Directly tests "does 2x epochs help, done right".
# Each replicates the head's ORIGINAL recipe (smooth_l1 + standardize) + EMA, so EMA/epochs
# are the ONLY changed variables vs the shipped head.
#
# same_chroma (384-d) is EXCLUDED: its per-crop SAME-chroma target corpus isn't packed
# (chroma384 spec §6) — that's a prerequisite CPU pass, not this run.
#
# GPU-polite (waits for a free card), sequential (each run uses the whole GPU), resumable
# (skips a run whose final-epoch head already exists). Eval — does EMA help — is a separate
# pass (re-render the chroma pilot with EMA-hpcp; latch gain-sweep + MERT-Δ for the rest).
# Launch: setsid bash eval/latch_ema_retrain_driver.sh >/tmp/latch_ema_retrain.log 2>&1 &
set -uo pipefail
cd /home/kim/Projects/SAO
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2 \
       OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
PY=/home/kim/Projects/SAO/.venv/bin/python
OUT=/run/media/kim/Mantu/sa3_control_runs/latch_ema_retrain_20260719
TRAIN=stable-audio-3/scripts/latch/train_latch.py

# medium/dead heads (MASTER §5): dead activation/spectral + hpcp (chroma), medium energies.
# spectral_skewness EXCLUDED (already EMA'd); the strong bass/mid energies EXCLUDED.
HEADS="hpcp spectral_kurtosis beat_activation downbeat_activation onset_envelope rms_energy_body rms_energy_air"

wait_gpu() {  # block until VRAM used < 3 GB, max ~10h
  for _ in $(seq 1 1200); do
    used=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -oiP "used memory \(b\): \K[0-9]+" | head -1)
    if [ -n "${used:-}" ] && [ "$used" -lt 3000000000 ]; then return 0; fi
    sleep 30
  done
  echo "[ema-retrain] wait_gpu timed out (~10h) — GPU stayed busy."; return 1
}

run_one() {  # $1=feature $2=arm $3=epochs
  local h=$1 arm=$2 ep=$3 dir="$OUT/${1}_${2}"
  if ls "$dir"/latch_sa3_${h}_ep${ep}.pt >/dev/null 2>&1; then
    echo "[ema-retrain] SKIP ${h}/${arm} (ep${ep} exists)"; return 0
  fi
  wait_gpu || return 1
  echo "[ema-retrain] $(date +%H:%M) START ${h}/${arm} (${ep}ep, smooth_l1+std+EMA0.999+ga2)"
  ${PY} ${TRAIN} --feature "$h" --target-source npz --loss smooth_l1 --standardize \
    --ema 0.999 --grad-accum 2 --epochs "$ep" --lr 3e-4 --batch-size 32 --precision bf16 \
    --save-dir "$dir" && echo "[ema-retrain] $(date +%H:%M) DONE ${h}/${arm}" \
    || echo "[ema-retrain] $(date +%H:%M) FAIL ${h}/${arm}"
}

echo "[ema-retrain] $(date +%H:%M) start — ${HEADS} x {ema20, ema40}"
for h in $HEADS; do run_one "$h" ema20 20; done
for h in $HEADS; do run_one "$h" ema40 40; done
echo "[ema-retrain] $(date +%H:%M) ALL DONE -> $OUT"
echo "[ema-retrain] NEXT (eval pass, does EMA help): re-render chroma pilot with EMA-hpcp;"
echo "[ema-retrain] latch gain-sweep + MERT-Δ vs the shipped heads for the rest."
