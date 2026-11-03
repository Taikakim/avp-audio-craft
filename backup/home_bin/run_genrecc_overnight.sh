#!/usr/bin/env bash
# Overnight: fpC (the eval winner) + CONTINUITY's genre-consistency loss (meter-in-the-gradient).
# Long run — patient early-stop, not the ep5 benchmark cap — so it keeps learning if the fp signal
# moves. Supervise Goa/Psy/Trance/Prog (strong probe r); monitor the rest for probe-hacking.
set -uo pipefail
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
PY=/home/kim/Projects/SAO/.venv/bin/python
cd /home/kim/Projects/SAO/control
SAVE=/run/media/kim/Mantu/sa3_control_runs/style_fpC_genrecc
echo "=== genre-cc overnight START $(date '+%F %T') ==="
"$PY" -m sa3_control.train \
  --encoded_dir /home/kim/Projects/latents_sa3 --model medium-base --precision bf16 \
  --control-mode fingerprint --fp-variant C --genre-vocab sa3_control/genre_vocab.json \
  --fp-probe /run/media/kim/Mantu/sa3_control_runs/cc_probe_genre.pt \
  --lambda-fp 0.1 --fp-t-max 0.5 --fp-supervise 0,1,2,4 \
  --crop-frames 512 --random-crop --batch 4 --lr 1e-4 --optimizer adamw \
  --control-dim 768 --n-tokens 256 --cfg-dropout 0.1 --num-workers 4 --ema 0.999 --grad-accum 2 \
  --max-epochs 22 --early-stop-patience 12 --val-frac 0.05 --save-every 2700 \
  --run-name style_fpC_genrecc --save-dir "$SAVE" --no-export-onnx-on-finish \
  2>&1 | grep -vE 'it/s\]$|Loading weights|WeightNorm|UserWarning|FutureWarning' \
       | grep -E '\[fp\]|\[control\]|\[step|\[epoch|\[early|val_rf|DONE|done|Error|Traceback'
echo "=== genre-cc overnight DONE $(date '+%F %T') ==="
