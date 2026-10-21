#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-21)
# run_kuang_plan_slow.sh -- "are we going too fast?" (decided 2026-10-21 ~08:45, replaces B4/B7/B6 of run_kuang_plan_b_day2.sh).
# Evidence for the question: P1 probes at ep5/10/20 show the leading momentum directions oscillating (too much step), the air head
# blows up in its weight matrices at any lr > 1e-2, and E5 Phase D found lr 3e-3..1e-2 flat on held-out loss.
# Four arms on the B0/E05 onset-head recipe, 40 epochs, seed 0 (B0 = lr 1e-2 SF on, 20 ep, best val 0.1822):
#   S_on  lr 5e-4 (1/20 of B0), Schedule-Free on          S_off  same, Schedule-Free off
#   C_on  lr 5e-3 (10x the slow arm), cosine 0->40 ep, SF on    C_off  same, SF off
# Weights stay fp32 here (--precision bf16 is autocast only), so a small lr is not lost to bf16 rounding.
#   setsid nohup bash eval/run_kuang_plan_slow.sh > <OUT>/slow.log 2>&1 < /dev/null &
set -u
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
OUT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow/kuang_plan_slow_20261021
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
mkdir -p "$OUT"; cd "$SAO" || exit 2
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE slow-lr / cosine x SF on-off, 4 x 40-epoch LatCH arms (~13 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 60
done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"
COMMON="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --epochs 40 --standardize --num-workers 16 --optimizer modular --mod-whitening shampoo
  --mod-warmup 500 --batch-size 16 --mod-radial-brake 0.8 --mod-escape-velocity --depth 8
  --log-grad-noise 50 --log-opt-groups --save-best-only"
ARMS=(
  "S_on|--lr 5e-4"
  "S_off|--lr 5e-4 --no-mod-sf"
  "C_on|--lr 5e-3 --cosine-epochs 0 40"
  "C_off|--lr 5e-3 --cosine-epochs 0 40 --no-mod-sf"
)
for spec in "${ARMS[@]}"; do
  arm=${spec%%|*}; flags=${spec#*|}; d="$OUT/$arm"
  [ -f "$d/DONE" ] && { echo "$(date +%H:%M) $arm already done"; continue; }
  mkdir -p "$d"; echo "$(date +%H:%M) $arm: $flags"
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $COMMON $flags --save-dir "$d" > "$d/train.log" 2>&1 )
  rc=$?
  best=$(grep -oE 'val=[0-9.]+' "$d/train.log" | cut -d= -f2 | sort -g | head -1)
  echo "$(date +%H:%M) $arm rc=$rc; best val ${best:-NA}; last: $(grep -E '^epoch|val=' "$d/train.log" | tail -2 | tr -s ' ' | paste -sd' ')"
  [ "$rc" -eq 0 ] && touch "$d/DONE"
done
echo "$(date +%H:%M) slow runner done"
