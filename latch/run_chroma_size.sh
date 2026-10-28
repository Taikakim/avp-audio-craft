#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-28)
# EXPERIMENTS E13b: same_chroma head, (1) the onset-head recipe (E5 Phase E winner) and (2) bigger / deeper heads on the chroma recipe
# that steered best in E13 (C3, lr 1e-3). Every arm logs gradient noise per flow-time bin and per model part (--log-grad-noise-t),
# plus the pooled meter, per-step / per-layer telemetry and held-out loss by t. 12 epochs (E13 steering peaked at epoch 10), every
# epoch saved. Trainer: the worktree branch wintermute/latch-gn-by-t (stable-audio-3), until it is merged.
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/chroma_size_2026-10-28
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=/home/kim/Projects/SAO-worktrees/sa3-latch-gn/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 WANDB_MODE=offline WANDB_DIR=$OUT
DATA="--feature same_chroma --target-source chroma --chroma-dir /run/media/kim/Kosmos/latents/latents_sa3_stem_chroma --chroma-key other --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --num-workers 8 --loss cosine"
LOGS="--save-every-epoch --save-online --ema-halflife-epochs 1 --ema-extra-halflife-epochs 0.25 --epochs 12 --wandb --wandb-project sa3-latch-chroma --log-every 20 --layer-every 100 --step-log --layer-log 50 --log-grad-noise 100 --log-grad-noise-t 100 --grad-noise-t-bins 5 --val-t-bins 10"
# the E13 C3 recipe (latch/run_chroma_retrain.sh) at lr 1e-3
C3="--optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 --grad-clip 1.0 --batch-size 8 --grad-accum 4 --lr 1e-3"
# the onset-head recipe (EXPERIMENTS E5 Phase A-E): modular lr 1e-2, 500-step warmup, batch 16, depth 8 (Phase E's only win), d256
ONSET="--optimizer modular --allow-uniform-lr --lr 1e-2 --mod-warmup 500 --batch-size 16 --grad-accum 1 --dim 256 --depth 8"
ARMS=(
"S0_onset_recipe_d256_L8|$ONSET"
"S1_c3_d512_L12|$C3 --dim 512 --depth 12 --batch-size 4 --grad-accum 8"
"S2_c3_d768_L8|$C3 --dim 768 --depth 8 --batch-size 4 --grad-accum 8"
)
mkdir -p "$OUT"; touch "$OUT/SUMMARY.tsv"; cd /tmp || exit 1
until "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 120; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date '+%F %T') GPU acquired; smoke (20 steps, noise-by-t every 5)"
# shellcheck disable=SC2086
$PY "$TRAIN" $DATA ${LOGS/--log-grad-noise-t 100/--log-grad-noise-t 5} $C3 --dim 768 --depth 8 --batch-size 4 --grad-accum 8 --max-steps 20 --save-dir "$OUT/_smoke" --run-name chroma_size_smoke > "$OUT/smoke.log" 2>&1
rc=$?
if [ $rc -ne 0 ] || [ ! -s "$OUT/_smoke/grad_noise_by_t.jsonl" ]; then echo "$(date '+%F %T') SMOKE FAILED rc=$rc, see $OUT/smoke.log"; exit 1; fi
echo "$(date '+%F %T') smoke ok"
for a in "${ARMS[@]}"; do
  name=${a%%|*}; rest=${a#*|}
  grep -q "^${name}	" "$OUT/SUMMARY.tsv" && continue
  if [ "$(df --output=avail -BG "$OUT" | tail -1 | tr -dc 0-9)" -lt 20 ]; then echo "$(date '+%F %T') under 20 GB free, stopping"; exit 1; fi
  mkdir -p "$OUT/$name"; t0=$(date +%s)
  # shellcheck disable=SC2086
  $PY "$TRAIN" $DATA $LOGS $rest --save-dir "$OUT/$name" --run-name "$name" > "$OUT/$name/train.log" 2>&1
  rc=$?; t1=$(date +%s)
  best=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | cut -d= -f2 | sort -g | head -1)
  last=$(grep -oE "val=[0-9.na]+" "$OUT/$name/train.log" | tail -1 | cut -d= -f2)
  printf '%s\t%s\t%s\t%s\trc=%s\n' "$name" "$((t1 - t0))" "${best:-NA}" "${last:-NA}" "$rc" >> "$OUT/SUMMARY.tsv"
  echo "$(date '+%F %T') $name rc=$rc best=${best:-NA}"
done
echo "$(date '+%F %T') ALL DONE"
