#!/usr/bin/env bash
# Task 5 — the 3-variant style-adapter benchmark: V-A (style+groove), V-B (maximal),
# V-C (style-only), ~5 epochs each at the good settings, held constant (AdamW lr 1e-4,
# EMA 0.999, grad-accum 2, batch 4). Sequential so they don't contend for the GPU.
# Winner gets the detailed bracket afterward. Runs in background; zero LLM tokens.
set -uo pipefail
PY=/home/kim/Projects/SAO/.venv/bin/python
cd /home/kim/Projects/SAO/control
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
VOCAB=sa3_control/genre_vocab.json
SAVE=/run/media/kim/Mantu/sa3_control_runs
for V in A B C; do
  echo "=== [style-benchmark] fp-variant $V START $(date +%H:%M) ==="
  "$PY" sa3_control/train.py \
    --encoded_dir /home/kim/Projects/latents_sa3 --model medium-base --precision bf16 \
    --control-mode fingerprint --fp-variant "$V" --genre-vocab "$VOCAB" \
    --crop-frames 512 --random-crop --batch 4 --lr 1e-4 --optimizer adamw \
    --control-dim 768 --n-tokens 256 --cfg-dropout 0.1 --num-workers 4 \
    --ema 0.999 --grad-accum 2 --max-epochs 5 --early-stop-patience 3 \
    --run-name "style_fp${V}_adamw" --save-dir "$SAVE/style_fp${V}_adamw" --save-every 5400 \
    2>&1 | tail -50
  echo "=== [style-benchmark] fp-variant $V DONE $(date +%H:%M) ==="
done
echo "=== 3-VARIANT STYLE BENCHMARK COMPLETE $(date +%H:%M) ==="
