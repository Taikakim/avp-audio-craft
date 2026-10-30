#!/usr/bin/env bash
# run_best_chroma_retrain_40ep.sh -- Retrain our winning E13 SAME-chroma conditioning head
# (same_chroma, 384-ch other-stem, cosine loss, dim 512, depth 8) with:
#   - 0.8x LR: 8e-4 (0.0008)
#   - Effective batch size: 64 (batch size 8, grad accum 8)
#   - 2x longer: 40 epochs
#   - 1 epoch buildup, then cosine decay from epoch 1 to epoch 40
#   - ModularOptimizer (Shampoo whitening, Muon on 2D weights, radial brake 0.8, grad clip 1.0)
#   - Held-out validation by source relpath (5%) with t-binned evaluation
#
# Usage:
#   bash latch/run_best_chroma_retrain_40ep.sh
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/chroma_retrain_best_40ep_20261030
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 WANDB_MODE=offline WANDB_DIR=$OUT

COMMON="--feature same_chroma --target-source chroma --chroma-key other \
  --chroma-dir /run/media/kim/Kosmos/latents/latents_sa3_stem_chroma \
  --latent-dir /run/media/kim/Kosmos/latents/latents_sa3 \
  --val-frac 0.05 --val-seed 0 --val-group-by relpath --seed 0 --num-workers 8 \
  --loss cosine --save-every-epoch --save-online --optimizer modular --allow-uniform-lr \
  --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 \
  --mod-radial-brake 0.8 --grad-clip 1.0 --ema-halflife-epochs 1 --ema-extra-halflife-epochs 0.25 \
  --epochs 40 --depth 8 --dim 512 --batch-size 8 --grad-accum 8 --lr 8e-4 \
  --cosine-epochs 1 40 --cosine-min-frac 0.0 --val-t-bins 10 \
  --wandb --wandb-project sa3-latch-chroma --log-every 20 --layer-every 100"

ARM_NAME="C3_best_lr8e-4_b64_cos40"

mkdir -p "$OUT/$ARM_NAME"
touch "$OUT/SUMMARY.tsv"
cd /tmp || exit 1

until "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) Waiting for GPU lock..."
    sleep 30
done
trap '"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1' EXIT

echo "$(date +%H:%M) GPU acquired; launching 40-epoch retrain of best chroma head ($ARM_NAME)..."
t0=$(date +%s)
# shellcheck disable=SC2086
$PY "$TRAIN" $COMMON --save-dir "$OUT/$ARM_NAME" --run-name "$ARM_NAME" > "$OUT/$ARM_NAME/train.log" 2>&1
rc=$?
t1=$(date +%s)

last=$(grep -oE "val=[0-9.na]+" "$OUT/$ARM_NAME/train.log" | tail -1 | cut -d= -f2)
best=$(grep -oE "val=[0-9.]+" "$OUT/$ARM_NAME/train.log" | cut -d= -f2 | sort -g | head -1)
printf '%s\t%s\t%s\t%s\trc=%s\n' "$ARM_NAME" "$((t1 - t0))" "${best:-NA}" "${last:-NA}" "$rc" >> "$OUT/SUMMARY.tsv"
echo "$(date +%H:%M) $ARM_NAME finished rc=$rc (time: $((t1 - t0))s, best val: ${best:-NA})"
exit $rc
