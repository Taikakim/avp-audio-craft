#!/bin/bash
# build_offload_venv_mt.sh — SECOND venv overlay, against the LUMI MULTITORCH image
# (flash-attn prebuilt for gfx90a) — the FA2 caption experiment (Kim direct 2026-07-30).
# RUN ON uan18. Idempotent. Caption-stack only (no audio-separator — sep stays on sa3.sif).
#
# Why: MF's audio tower materializes a full-sequence attention matrix (quadratic; 600s
# audio = one 23.66 GiB alloc, probe 20423145). attn_implementation="sdpa" was ignored,
# but flash_attention_2 is a SEPARATE explicit branch in transformers attention code —
# NVIDIA trained MF with FA, so the fork may implement it. The multitorch image ships
# flash-attn for gfx90a => no build. If FA2 engages: linear memory, full tracks captionable.
#
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
MODELS=${PROJ}/models
# READABLE images live under /appl/local/laifs/containers/ (LAIF docs) — the
# easybuild-sif-images entries are symlinks into another project's scratch, NOT world-
# readable (hit 2026-07-30). Default = newest multitorch-FULL (torch + flash-attn +
# bitsandbytes + vLLM); override with MTSIF=... .
MTSIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
[ -n "${MTSIF}" ] || { echo "FATAL: no lumi-multitorch-full image found under /appl/local/laifs/containers/ — ls that dir and pass MTSIF=<path>"; exit 1; }
VENV=${SCRATCH}/goa_offload_venv_mt
OLDVENV=${SCRATCH}/goa_offload_venv

echo "== [1/3] venv + pip deps (multitorch python) =="
[ -f "${MTSIF}" ] || { echo "FATAL: multitorch SIF not found at ${MTSIF}"; exit 1; }
[ -d "${VENV}" ] || singularity exec --bind "${SCRATCH}" "${MTSIF}" python3 -m venv --system-site-packages "${VENV}"
singularity exec --bind "${SCRATCH}" "${MTSIF}" bash -c "
  source ${VENV}/bin/activate
  pip install --no-cache-dir --upgrade pip -q
  pip install --no-cache-dir librosa soundfile pydub resampy tqdm pyyaml
  # OFFICIAL transformers, not the lashahub fork — MF is mainline as
  # AudioFlamingo3ForConditionalGeneration (NVIDIA README, music_flamingo branch).
  pip install --no-cache-dir --upgrade 'git+https://github.com/huggingface/transformers' accelerate
"

echo "== [2/3] ffmpeg (reuse the static build from the sa3 venv) =="
if [ -x "${VENV}/bin/ffmpeg" ]; then echo "already staged"
elif [ -x "${OLDVENV}/bin/ffmpeg" ]; then cp "${OLDVENV}/bin/ffmpeg" "${OLDVENV}/bin/ffprobe" "${VENV}/bin/"; echo "copied from ${OLDVENV}"
else echo "WARN: no static ffmpeg found — audioread mp3 fallback may fail; run build_offload_venv.sh step 2 logic if needed"
fi

echo "== [3/3] verification: torch + gfx90a flash-attn + MF class (CPU-safe) =="
# PYTHONPATH prepend is LOAD-BEARING: the multitorch image ships its own /opt/venv and its
# env shadows our venv on sys.path — without this, imports resolve to the CONTAINER's
# transformers 4.57.6 (predates AudioFlamingo3) instead of our 5.x (hit 2026-07-30).
singularity exec --bind "${PROJ}","${SCRATCH}" "${MTSIF}" bash -c "
  source ${VENV}/bin/activate
  export PYTHONPATH=${VENV}/lib/python3.12/site-packages\${PYTHONPATH:+:\${PYTHONPATH}}
  export HF_HOME=${MODELS} HF_HUB_OFFLINE=1
  python - <<'PYEOF'
import sys
fails = []
for what, stmt in [
    ('torch (multitorch image)', 'import torch; assert torch.version.hip, \"not a ROCm torch\"; print(\"    torch\", torch.__version__)'),
    ('flash_attn import', 'import flash_attn; print(\"    flash_attn\", flash_attn.__version__)'),
    ('OUR transformers wins sys.path',
     'import transformers; print(\"    transformers\", transformers.__version__, transformers.__file__); '
     'assert not transformers.__file__.startswith(\"/opt/venv\"), \"container transformers shadowing the venv\"'),
    ('mainline MF class (AudioFlamingo3)', 'from transformers import AudioFlamingo3ForConditionalGeneration, AutoProcessor'),
    ('librosa', 'import librosa'),
    ('pydub', 'import pydub'),
]:
    try:
        exec(stmt)
        print(f'  OK   {what}')
    except Exception as e:
        fails.append(what)
        print(f'  FAIL {what}: {type(e).__name__}: {e}')
# NOTE: is_flash_attn_2_available() is NOT checked here — it requires torch.cuda.is_available(),
# always False on the GPU-less login node. The GPU probe is the real FA2-engagement test.
sys.exit(1 if fails else 0)
PYEOF
"
echo "== build_offload_venv_mt: ALL GREEN =="
echo "Probe with: sbatch --time=00:40:00 --export=ALL,PROBE=1,CAPTION_SIF=${MTSIF},CAPTION_VENV=${VENV},MF_USE_FA2=1,CAPTION_MAX_SEC=1200 lumi/sbatch/goa_caption.sbatch"
