#!/bin/bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: WINTERMUTE (created 2026-10-21)
# run_air_unit_lr1e2.sh -- does the unit-matched recipe widen the usable lr range, or only re-express it?
# AIR_U3 (lr 3e-3) moved the matrices 0.2 x 3e-3 = 6e-4 per weight, the same as the old recipe at lr 1e-2 (lr/16), so it
# showed the unit conversion works (CONTINUITY review, 2026-10-21). AIR_U10 = the same recipe at lr 1e-2: matrix step
# 2e-3 per weight = the old recipe at lr 3e-2, where the air head always diverged (O3/O4: NaN at ep15/ep26 at b64).
# Waits for run_unit_matched.sh (same GPU handle), runs AIR_U10, releases the lock, then starts the batch sweep.
#   setsid nohup bash eval/run_air_unit_lr1e2.sh > <OUT>/air_u10.log 2>&1 < /dev/null &
set -u
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
ROOT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
OUT=$ROOT/unit_matched_20261021
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
while pgrep -f '^bash eval/run_unit_matched\.sh' >/dev/null; do sleep 30; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE air head unit-matched lr 1e-2 (~45 min), then the batch sweep" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 60
done
d="$OUT/AIR_U10"
if [ ! -f "$d/DONE" ]; then
  mkdir -p "$d"; echo "$(date +%H:%M) AIR_U10"
  ( cd /tmp && "$LPY" "$TRAIN" --optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam \
      --mod-scalar-sf-beta 0.95 --lr-watchdog 2 --grad-clip 1.0 --log-opt-groups \
      --feature rms_energy_air --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0 \
      --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --max-steps 4000 --epochs 25 \
      --save-every-epoch --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 \
      --ema-halflife-epochs 2 --cosine-epochs 17.5 25 --dim 256 --depth 8 --batch-size 16 --grad-accum 2 --lr 1e-2 \
      --save-dir "$d" > "$d/train.log" 2>&1 )
  rc=$?
  best=$(grep -oE 'val=[0-9.]+' "$d/train.log" | cut -d= -f2 | sort -g | head -1)
  echo "$(date +%H:%M) AIR_U10 rc=$rc; best val ${best:-NA}; watchdog cuts $(grep -c 'lr-watchdog\] step' "$d/train.log"); last: $(grep -E '^epoch|val=|non-finite|cooked' "$d/train.log" | tail -2 | tr -s ' ' | paste -sd' ')"
  [ "$rc" -eq 0 ] && touch "$d/DONE"
fi
Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1
echo "$(date +%H:%M) starting the batch sweep"
setsid nohup bash eval/run_batch_sweep.sh > "$ROOT/batch_sweep_20261021/run.log" 2>&1 < /dev/null &
