#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-22)
# Fallback for eval/run_adamw_cosine_20261022.sh: waits for that queue to exit, then for every arm that STARTED but has no DONE
# marker (a failed run; arms skipped by the time guard have no directory and are left alone) re-runs a short smoke test of the same
# arguments at the same effective batch 64 with smaller micro-batches: 32x2, 16x4, 8x8. Separates "out of memory / kernel failure at
# micro-batch 32" from "the optimizer itself breaks". 300 optimizer steps each, under $OUT/smoke/<arm>_<micro>x<accum>/.
# RUN: setsid nohup bash eval/run_smoke_fallback_20261022.sh <queue pid> &
QPID=${1:?queue pid}
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
OUT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow/adamw_cosine_20261022
LOG=/home/kim/sao_runs/adamw_cosine_20261022.log
STEPS=300
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
while kill -0 "$QPID" 2>/dev/null; do sleep 60; done

ONSET="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --depth 8
  --grad-clip 1.0 --lr-watchdog 2 --log-grad-noise 10 --save-best-only --optimizer adamw"

failed=""
for d in "$OUT"/*/; do
  n=$(basename "$d"); [ "$n" = smoke ] && continue
  [ -f "$d/DONE" ] || failed="$failed $n"
done
[ -n "$failed" ] || { echo "$(date +%H:%M) smoke fallback: every started arm finished, nothing to test"; exit 0; }
echo "$(date +%H:%M) smoke fallback for:$failed"

vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE smoke tests of failed optimizer arms, short" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT

for n in $failed; do
  args=$("$LPY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["train_args"])' "$OUT/$n/run_meta.json") || continue
  echo "$(date +%H:%M) $n failed run: $(tail -3 "$OUT/$n/train.log" | tr '\n' ' ' | cut -c1-300)"
  for mb in 32x2 16x4 8x8; do
    s="$OUT/smoke/${n}_$mb"; mkdir -p "$s"
    # shellcheck disable=SC2086
    ( cd /tmp && "$LPY" "$TRAIN" $ONSET $args --batch-size "${mb%x*}" --grad-accum "${mb#*x}" --max-steps $STEPS \
        --save-dir "$s" > "$s/train.log" 2>&1 )
    rc=$?
    echo "$(date +%H:%M) smoke $n $mb rc=$rc; last loss $(grep -oE 'loss=[0-9.naif]+' "$s/train.log" | tail -1); $(grep -m1 -oiE 'out of memory|nan|error[^ ]*' "$s/train.log")"
  done
done
echo "$(date +%H:%M) smoke fallback done"
