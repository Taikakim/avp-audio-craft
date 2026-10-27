#!/bin/bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: WINTERMUTE (created 2026-10-21)
# run_unit_matched.sh -- one lr that means the same per-element step for every parameter group, plus guards
# (decided 2026-10-21 ~09:30, replacing the slow-lr / cosine arms):
#   units:  --mod-update-scale rms0.2 (matrix update RMS 0.2*lr, Adam-sized) + --mod-scalar-opt adam (1-D params AND the
#           256->1 output layer on element-wise Adam, no 1/sqrt(d) radius) + --mod-scalar-sf-beta 0.95 (SF-NorMuon paper)
#   guards: --lr-watchdog 2 (halve a group's lr when its weight RMS doubles within an epoch, after warmup),
#           --grad-clip 1.0, escape velocity OFF. Momentum, wd, warmup, radial brake as in each base recipe.
#   AIR_U3  air head, E6 O1 recipe (which cooked at every lr > 1e-2) at lr 3e-3, per-epoch ckpts for a listening sweep
#   ON_U1   onset head, E05 recipe, lr 1e-3, 20 ep        ON_U3  same at lr 3e-3      (reference B0: 0.1822)
#   setsid nohup bash eval/run_unit_matched.sh > <OUT>/run.log 2>&1 < /dev/null &
set -u
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
OUT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow/unit_matched_20261021
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
mkdir -p "$OUT"; cd "$SAO" || exit 2
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE unit-matched LatCH arms: air 3e-3, onset 1e-3 / 3e-3 (~4.5 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 60
done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"
UNITS="--optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95
  --lr-watchdog 2 --grad-clip 1.0 --log-opt-groups"
ONSET="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --epochs 20 --standardize --num-workers 16 --mod-warmup 500 --batch-size 16
  --mod-radial-brake 0.8 --depth 8 --log-grad-noise 50 --save-best-only"
AIR="--feature rms_energy_air --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0
  --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --max-steps 4000 --epochs 25 --save-every-epoch
  --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 --ema-halflife-epochs 2
  --cosine-epochs 17.5 25 --dim 256 --depth 8 --batch-size 16 --grad-accum 2"
ARMS=(
  "AIR_U3|$AIR --lr 3e-3"
  "ON_U1|$ONSET --lr 1e-3"
  "ON_U3|$ONSET --lr 3e-3"
)
for spec in "${ARMS[@]}"; do
  arm=${spec%%|*}; flags=${spec#*|}; d="$OUT/$arm"
  [ -f "$d/DONE" ] && { echo "$(date +%H:%M) $arm already done"; continue; }
  mkdir -p "$d"; echo "$(date +%H:%M) $arm"
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $UNITS $flags --save-dir "$d" > "$d/train.log" 2>&1 )
  rc=$?
  best=$(grep -oE 'val=[0-9.]+' "$d/train.log" | cut -d= -f2 | sort -g | head -1)
  echo "$(date +%H:%M) $arm rc=$rc; best val ${best:-NA}; watchdog cuts $(grep -c 'lr-watchdog\] step' "$d/train.log"); last: $(grep -E '^epoch|val=' "$d/train.log" | tail -2 | tr -s ' ' | paste -sd' ')"
  [ "$rc" -eq 0 ] && touch "$d/DONE"
done
echo "$(date +%H:%M) unit-matched runner done"
