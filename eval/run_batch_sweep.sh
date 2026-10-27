#!/bin/bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: WINTERMUTE (created 2026-10-21)
# run_batch_sweep.sh -- effective batch 64 / 128 / 256 on the unit-matched onset recipe (decided 2026-10-21 ~09:45).
# Why: Muon sets every singular value of the step to 1, so at batch 16 the noise directions get a full-size step;
# SAMuon's gain grows with batch; batch 16 was never tested against bigger batches at a fixed budget (E5 batch arms were
# step-count artefacts, TRAINING F3/D14). Budget: 40 EPOCHS per arm (equal compute; the GPU is the bottleneck, 96-100%
# busy), warmup scaled in epochs (B0: 500 of 740 steps = 0.68 ep). Real micro-batch 32 + accumulation 2 / 4 / 8; the
# grad-noise meter reads the two accumulation halves (no extra passes).
# Step 0, a timing probe: 300 steps at batch 32 with Newton-Schulz in fp32 vs bf16 (section T: 323 -> 101 ms on FiLM);
# bf16 is used if it is >= 10% faster. If batch 32 does not fit, the sweep falls back to micro-batch 16 (accum x2).
# lr = the better of ON_U1 (1e-3) / ON_U3 (3e-3) from run_unit_matched.sh (waits for that runner to finish).
#   setsid nohup bash eval/run_batch_sweep.sh > <OUT>/run.log 2>&1 < /dev/null &
set -u
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
ROOT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
UNIT=$ROOT/unit_matched_20261021
OUT=$ROOT/batch_sweep_20261021
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
mkdir -p "$OUT"; cd "$SAO" || exit 2
while pgrep -f '^bash eval/run_unit_matched\.sh' >/dev/null; do sleep 60; done   # same handle: its exit releases the lock
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE batch sweep 64/128/256 on LatCH onset head (~10.5 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 60
done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"
best_val() { grep -oE 'val=[0-9.]+' "$1/train.log" 2>/dev/null | cut -d= -f2 | sort -g | head -1; }
v1=$(best_val "$UNIT/ON_U1"); v3=$(best_val "$UNIT/ON_U3")
LR=1e-3
[ -n "$v3" ] && { [ -z "$v1" ] || awk -v a="$v3" -v b="$v1" 'BEGIN{exit !(a < b)}'; } && LR=3e-3
echo "$(date +%H:%M) lr $LR (ON_U1 ${v1:-NA}, ON_U3 ${v3:-NA})"

UNITS="--optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95
  --lr-watchdog 2 --grad-clip 1.0 --log-opt-groups --lr $LR"
ONSET="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --mod-warmup-epochs 0.68
  --mod-radial-brake 0.8 --depth 8"

# --- timing probe ---
NS=fp32; MB=32
probe() {   # name, micro-batch, ns dtype -> prints seconds (or FAIL)
  local d="$OUT/probe_$1"; mkdir -p "$d"; local t0; t0=$(date +%s)
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $UNITS $ONSET --batch-size "$2" --mod-ns-dtype "$3" --max-steps 300 --epochs 1 \
      --save-dir "$d" > "$d/train.log" 2>&1 ) && echo $(( $(date +%s) - t0 )) || echo FAIL
}
p32=$(probe b32_fp32 32 fp32); echo "$(date +%H:%M) probe b32 ns fp32: ${p32}s"
if [ "$p32" = FAIL ]; then
  MB=16; echo "$(date +%H:%M) batch 32 failed (see probe_b32_fp32/train.log): micro-batch 16"
  pb=$(probe b16_bf16 16 bf16); pf=$(probe b16_fp32 16 fp32)
else
  pf=$p32; pb=$(probe b32_bf16 32 bf16)
fi
echo "$(date +%H:%M) probe ns fp32 ${pf}s vs bf16 ${pb}s (300 steps + one val pass each)"
if [ "$pb" != FAIL ] && [ "$pf" != FAIL ] && awk -v b="$pb" -v f="$pf" 'BEGIN{exit !(b < 0.9 * f)}'; then NS=bf16; fi
echo "$(date +%H:%M) using micro-batch $MB, Newton-Schulz $NS"

for EB in 64 128 256; do
  ACC=$(( EB / MB )); arm="EB${EB}"; d="$OUT/$arm"
  [ -f "$d/DONE" ] && { echo "$(date +%H:%M) $arm already done"; continue; }
  mkdir -p "$d"; echo "$(date +%H:%M) $arm: micro-batch $MB x accum $ACC"
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $UNITS $ONSET --batch-size "$MB" --grad-accum "$ACC" --epochs 40 --mod-ns-dtype "$NS" \
      --log-grad-noise 10 --save-best-only --save-dir "$d" > "$d/train.log" 2>&1 )
  rc=$?
  echo "$(date +%H:%M) $arm rc=$rc; best val $(best_val "$d"); watchdog cuts $(grep -c 'lr-watchdog\] step' "$d/train.log"); last: $(grep -E '^epoch|val=' "$d/train.log" | tail -2 | tr -s ' ' | paste -sd' ')"
  [ "$rc" -eq 0 ] && touch "$d/DONE"
done
echo "$(date +%H:%M) batch sweep done"
