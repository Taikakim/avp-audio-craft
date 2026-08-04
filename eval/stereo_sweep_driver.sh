#!/bin/bash
# stereo_sweep_driver.sh — T=512 stereo-loss DoRA sweep, run DETACHED via setsid so the
# harness can't reap it (the 2026-07-16 SIGTERM that killed the first attempt at ~1h).
# Waits for a free GPU before each arm (coexists politely with W's render poll-driver),
# then trains w = 0.0 / 0.1 / 0.3 back to back. Fresh start (old w=0.0 partial removed).
set -uo pipefail
cd /home/kim/Projects/SAO/stable-audio-3
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
OUT=/run/media/kim/Mantu/sa3_lora_runs
PY=/home/kim/Projects/SAO/stable-audio-3/.venv/bin/python

wait_gpu() {  # block until VRAM used < 3 GB (i.e. no one else training/rendering), max ~2h
  for _ in $(seq 1 2400); do
    used=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -oiP "used memory \(b\): \K[0-9]+" | head -1)
    if [ -n "${used:-}" ] && [ "$used" -lt 3000000000 ]; then return 0; fi
    sleep 30
  done
}

rm -rf ${OUT}/stereo_sweep_w0.0 ${OUT}/stereo_sweep_w0.1 ${OUT}/stereo_sweep_w0.3
for W in 0.0 0.1 0.3; do
  echo "[sweep] waiting for free GPU before w=${W} ($(date +%H:%M))"
  wait_gpu
  echo "[sweep] arm w=${W} START $(date +%H:%M)"
  ${PY} scripts/train_lora.py \
    --model medium-base --encoded_dir /home/kim/Projects/latents_sa3 \
    --frames 512 --beat-aware-crop --batch_size 2 \
    --adapter_type dora-rows --rank 128 --lora_alpha 128 \
    --optimizer fusion --lr 1e-4 --steps 4000 \
    --save_dir ${OUT}/stereo_sweep_w${W} \
    --stereo_loss_weight ${W} --stereo_loss_tmax 0.3 --stereo_loss_subbatch 1 \
    --num_workers 4 --seed 1 --no_demos --logger csv > ${OUT}/stereo_sweep_w${W}.log 2>&1
  echo "[sweep] arm w=${W} DONE $(date +%H:%M) rc=$?"
done
echo "[sweep] ALL DONE $(date +%H:%M)"
