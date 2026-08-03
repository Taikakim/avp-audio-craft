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

echo "[local] pre-downloading medium-base (required for medium/native pass; public)"
if ! $PY -c "
from huggingface_hub import hf_hub_download
hf_hub_download('stabilityai/stable-audio-3-medium-base','model_config.json')
hf_hub_download('stabilityai/stable-audio-3-medium-base','model.safetensors')
print('[local] medium-base cached')"; then
  echo '[local] !! medium-base download failed -- aborting before the lock'; exit 1
fi
# medium (ptm base + the SHARED t5gemma conditioner both passes need). Retry-with-timeout:
# hf_hub_download RESUMES the .incomplete blob, and HF_HUB_DOWNLOAD_TIMEOUT bounds a dead socket
# (a silent stall hung the pull at 2.8/6GB with no timeout, 2026-08-03).
PTM_OK=0
export HF_HUB_DOWNLOAD_TIMEOUT=30
for attempt in 1 2 3 4 5 6 7 8; do
  echo "[local] pre-downloading medium (attempt ${attempt}) ..."
  if $PY -c "
from huggingface_hub import hf_hub_download
for f in ('model_config.json','model.safetensors','t5gemma-b-b-ul2/config.json','t5gemma-b-b-ul2/tokenizer_config.json'):
    hf_hub_download('stabilityai/stable-audio-3-medium', f)
print('[local] medium cached')"; then
    PTM_OK=1; break
  fi
  echo "[local] medium download attempt ${attempt} stalled/failed -- resuming in 5s"
  sleep 5
done
if [ "$PTM_OK" != "1" ]; then
  echo '[local] !! medium unavailable after 8 attempts. Both passes need its t5gemma conditioner,'
  echo '[local]    so the render CANNOT proceed. Check HF auth (huggingface-cli login) + network, then re-run.'
  exit 1
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
    --terminal-only --native-grid --require-file --only-labels "$LOCAL" \
    --native-frames-file render_jobs_local.txt

if [ "$PTM_OK" = "1" ]; then
  echo "[local] === PTM pass: post-trained base, cfg1/w1, 8-step, native @ terminal ==="
  $PY model_matrix_gen.py --pt-medium --only-cfgs 1 --only-strengths 1.0 --steps 8 \
      --prompts-from-manifest --only-prompts "$PROMPTS" \
      --terminal-only --native-grid --require-file --only-labels "$LOCAL" \
      --native-frames-file render_jobs_local.txt
  echo "[local] DONE (medium + ptm)."
else
  echo "[local] PTM pass SKIPPED (medium model not authenticated). Medium/native pass complete;"
  echo "[local] re-run this script after 'huggingface-cli login' to fill the ptm cells (resumable)."
fi
echo "[local] Manifest appended; run the board rebuild + ingest next."
