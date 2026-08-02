#!/bin/bash
# run_local_length_variant.sh — local overnight leg of the 2026-08-02 length-variant eval run.
# Renders the LOCAL-queue terminal checkpoints (render_jobs_local.txt) on the ROCm 7.14 fast venv
# (native CK FA2), GPU-mutex held for the whole run, with a 1-cell smoke gate before the multi-hour
# commit. Resumable (model_matrix_gen skips existing cells). Native T512 = safe locally; the 5
# T4096 _repr auto-skip to their LUMI twins.
set -uo pipefail
cd /home/kim/Projects/SAO/eval

PY=/home/kim/Projects/SAO/.venv/bin/python                 # ROCm 7.14, native CK FA2
LOCK=/home/kim/Projects/SAO/.gpu.lock
FL=/home/kim/Projects/SAO/Misc/filelock.py
PROMPTS="kimlong,techno,kl_0,rb_bracket_0,rb_common_1,rb_common_2,rb_rare_7,rb_rare_8,goa_organic"
LOCAL=$(cut -f1 render_jobs_local.txt | paste -sd,)
SMOKE=$(cut -f1 render_jobs_local.txt | head -1)

# CK flash-attn + the SA3-medium-safe MIOpen/TunableOp env (MASTER §5). NB: do NOT set
# HF_HUB_OFFLINE -- the model weights stream from HF (stabilityai/stable-audio-3-medium[-base])
# and the local HF cache is currently empty; offline would hard-fail the load.
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8

echo "[local] restoring STAGING manifest from durable mirror (resume source)"
cp -u ~/evals_aac/model_matrix/manifest.jsonl ~/.cache/evals_aac/model_matrix/manifest.jsonl 2>/dev/null || true

echo "[local] pre-downloading model weights to HF cache (no lock; ~6GB x2, one-time)"
if ! $PY -c "
from huggingface_hub import hf_hub_download
for repo in ['stabilityai/stable-audio-3-medium-base','stabilityai/stable-audio-3-medium']:
    hf_hub_download(repo,'model_config.json'); hf_hub_download(repo,'model.safetensors')
print('[local] models cached')"; then
  echo '[local] !! model pre-download failed (gated/network?) -- aborting before the lock'; exit 1
fi

echo "[local] acquiring GPU lock"
python3 "$FL" acquire "$LOCK" --handle WINTERMUTE --pid-aware --pid $$ || { echo "[local] GPU busy, abort"; exit 1; }
trap 'python3 "$FL" release "$LOCK" --handle WINTERMUTE; echo "[local] GPU lock released"' EXIT

echo "[local] === SMOKE: 1 cell ($SMOKE x goa_organic cfg1 w1) on the 7.14 venv ==="
if ! $PY model_matrix_gen.py --prompts-from-manifest --only-prompts goa_organic \
      --terminal-only --require-file --only-labels "$SMOKE" --only-cfgs 1 --only-strengths 1.0; then
  echo "[local] !! SMOKE FAILED on the 7.14 venv -- aborting before the full run"; exit 1
fi
echo "[local] smoke OK"

echo "[local] === MEDIUM pass: native full-grid + goa_organic 20s @ terminal ($LOCAL) ==="
$PY model_matrix_gen.py --prompts-from-manifest --only-prompts "$PROMPTS" \
    --terminal-only --native-grid --require-file --only-labels "$LOCAL"

echo "[local] === PTM pass: post-trained base, cfg1/w1, 8-step, native @ terminal ==="
$PY model_matrix_gen.py --pt-medium --only-cfgs 1 --only-strengths 1.0 --steps 8 \
    --prompts-from-manifest --only-prompts "$PROMPTS" \
    --terminal-only --native-grid --require-file --only-labels "$LOCAL"

echo "[local] DONE (medium + ptm). Manifest appended; run the board rebuild + ingest next."
