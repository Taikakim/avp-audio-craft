#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-21)
# run_kuang_plan_b_day2.sh -- test plan section B, second leg (docs/modular-opt-test-plan-2026-10-17.md), as decided 2026-10-21 08:xx:
#   AIRS = the air head at the lr that always diverged (E6 O1: lr 5e-2, NaN in epoch 3-4) with the sign group capped at 2e-3:
#          does a cooler scalar group stop that blow-up too? (B3 localised the onset-head divergence to the sign group.)
#   B4   = SF-NorMuon recipe (rms0.2, Adam scalars, mu 0.8, wd 0.05, warmup 1500), lr 1e-2.   B5 dropped.
#   B7   = NorMuon off, nothing else changed.
#   BEST = the best B arm, 40 epochs (2x), seed 1. An arm counts as better only if it beats B0 (0.1822) by more than the
#          0.004 run-to-run noise on file (EXPERIMENTS E5 audit 2026-10-07); otherwise BEST = the B0 recipe. Schedule-Free with
#          no decay, so its epoch-20 val is also a seed-1 repeat of the chosen arm.
#   setsid nohup bash eval/run_kuang_plan_b_day2.sh > <BOUT>/day2.log 2>&1 < /dev/null &
set -u
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
BOUT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow/kuang_plan_B_20261021
B0_VAL=0.1822; NOISE=0.004
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE test plan B day 2: air sign-cap, B4, B7, best arm x2 (~7.5 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 60
done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"

ONSET="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --standardize --num-workers 16 --optimizer modular --mod-whitening shampoo
  --mod-warmup 500 --batch-size 16 --mod-radial-brake 0.8 --mod-escape-velocity --depth 8
  --log-grad-noise 50 --log-opt-groups --save-best-only"
# E6 O1 verbatim (latch/run_air_overnight.sh) + the sign cap
AIR="--feature rms_energy_air --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0
  --val-group-by relpath --seed 0 --standardize --num-workers 8 --loss smooth_l1 --max-steps 4000 --epochs 25 --save-every-epoch
  --optimizer modular --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8
  --ema-halflife-epochs 2 --cosine-epochs 17.5 25 --mod-late-from-epochs 2 --grad-clip 1.0 --lr 5e-2 --dim 256 --depth 8
  --batch-size 16 --grad-accum 2 --log-opt-groups"
declare -A FLAGS=(
  [B0]="--lr 1e-2"
  [B1]="--lr 1e-2 --mod-sign-lr 2e-3"
  [B2]="--lr 3e-2 --mod-sign-lr 2e-3"
  [B4]="--lr 1e-2 --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95 --mod-momentum 0.8 --mod-wd 0.05 --mod-warmup 1500"
  [B7]="--lr 1e-2 --no-mod-normuon"
)

run() {   # name, flags...
  local name=$1; shift; local d="$BOUT/$name"
  [ -f "$d/DONE" ] && { echo "$(date +%H:%M) $name already done"; return; }
  mkdir -p "$d"; echo "$(date +%H:%M) $name: $*"
  ( cd /tmp && "$LPY" "$TRAIN" "$@" --save-dir "$d" > "$d/train.log" 2>&1 )
  local rc=$?
  echo "$(date +%H:%M) $name rc=$rc; best val $(best_val "$name"); last: $(grep -E '^epoch|val=' "$d/train.log" | tail -2 | tr -s ' ' | paste -sd' ')"
  [ "$rc" -eq 0 ] && touch "$d/DONE"
}
best_val() { grep -oE 'val=[0-9.]+' "$BOUT/$1/train.log" 2>/dev/null | cut -d= -f2 | sort -g | head -1; }

# shellcheck disable=SC2086
run AIRS_O1_signcap $AIR --mod-sign-lr 2e-3
# shellcheck disable=SC2086
run B4 $ONSET --seed 0 --epochs 20 ${FLAGS[B4]}
# shellcheck disable=SC2086
run B7 $ONSET --seed 0 --epochs 20 ${FLAGS[B7]}

pick=B0; pv=$B0_VAL
for a in B1 B2 B4 B7; do
  v=$(best_val "$a"); [ -z "$v" ] && continue
  if awk -v v="$v" -v p="$pv" -v b="$B0_VAL" -v n="$NOISE" 'BEGIN{exit !(v < p && v < b - n)}'; then pick=$a; pv=$v; fi
done
echo "$(date +%H:%M) best arm: $pick ($pv; must beat B0 $B0_VAL by > $NOISE)"
# shellcheck disable=SC2086
run "BEST_${pick}_ep40_seed1" $ONSET --seed 1 --epochs 40 ${FLAGS[$pick]}
echo "$(date +%H:%M) day 2 done"
