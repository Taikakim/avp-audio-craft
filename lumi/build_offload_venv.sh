#!/bin/bash
# build_offload_venv.sh — one-time setup for the goa-archive offload jobs (sep + caption).
# RUN ON uan18 (login node — has internet; compute nodes are offline). Idempotent.
# (CONTINUITY 2026-07-29. Pattern = the bungee_venv precedent: venv on scratch with
# --system-site-packages so torch/ROCm comes from the SIF's conda env.)
#
# Does four things:
#  1. venv at $SCRATCH/goa_offload_venv (SIF python) + pip deps:
#     - audio-separator --no-deps  (mir's bs_roformer_sep imports the model class from
#       audio_separator.separator.uvr_lib_v5.roformer — NOT lucidrains' BS-RoFormer pkg)
#       + the roformer-path deps: einops beartype rotary-embedding-torch librosa pydub resampy
#     - the lashahub transformers fork (MusicFlamingoForConditionalGeneration lives there —
#       music_flamingo_transformers.py line ~37) + accelerate
#  2. static ffmpeg into the venv bin IF the SIF lacks one (pydub m4a export + audioread
#     mp3 fallback both shell out to ffmpeg; without it stems fall back to FLAC = huge)
#  3. downloads nvidia/music-flamingo-hf into $MODELS (HF cache) for offline compute use
#  4. VERIFIES both import paths inside SIF+venv (CPU) — fails loud per item
#
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
VENV=${SCRATCH}/goa_offload_venv

echo "== [1/4] venv + pip deps =="
[ -d "${VENV}" ] || singularity exec --bind "${SCRATCH}" "${SIF}" python3 -m venv --system-site-packages "${VENV}"
singularity exec --bind "${SCRATCH}" "${SIF}" bash -c "
  source ${VENV}/bin/activate
  pip install --no-cache-dir --upgrade pip -q
  pip install --no-cache-dir --no-deps audio-separator
  pip install --no-cache-dir einops beartype rotary-embedding-torch librosa pydub resampy tqdm pyyaml soundfile
  # import-time deps of audio_separator's package __init__ chain (we use none of them at
  # runtime, but the roformer import walks the package): onnxruntime was the 2026-07-30
  # verification FAIL; ml_collections/julius are the same class of lazy-to-eager risk.
  # NO diffq: it's a C extension, the SIF has no gcc, and it's demucs-arch-only — its build
  # failure aborts the whole pip call (2026-07-30).
  pip install --no-cache-dir onnxruntime ml_collections julius
  pip install --no-cache-dir 'git+https://github.com/lashahub/transformers' accelerate
"

echo "== [2/4] ffmpeg =="
if singularity exec "${SIF}" which ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg present in SIF"
elif [ -x "${VENV}/bin/ffmpeg" ]; then
  echo "static ffmpeg already staged in venv"
else
  echo "SIF lacks ffmpeg — staging a static build into ${VENV}/bin"
  T=$(mktemp -d)
  curl -sL -o "${T}/ff.tar.xz" https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
  tar -xJf "${T}/ff.tar.xz" -C "${T}"
  cp "${T}"/ffmpeg-*-static/ffmpeg "${T}"/ffmpeg-*-static/ffprobe "${VENV}/bin/"
  rm -rf "${T}"
  "${VENV}/bin/ffmpeg" -version | head -1
fi

echo "== [3/4] Music Flamingo weights -> ${MODELS} =="
singularity exec --bind "${PROJ}","${SCRATCH}" "${SIF}" bash -c "
  source ${VENV}/bin/activate
  HF_HOME=${MODELS} python -c \"
from huggingface_hub import snapshot_download
p = snapshot_download('nvidia/music-flamingo-hf')
print('MF weights at:', p)\"
"

echo "== [4/4] import verification (CPU, fail-loud per item) =="
singularity exec --bind "${PROJ}","${SCRATCH}" "${SIF}" bash -c "
  source ${VENV}/bin/activate
  export HF_HOME=${MODELS} HF_HUB_OFFLINE=1
  python - <<'PYEOF'
import importlib, sys
fails = []
for what, stmt in [
    ('torch (SIF via system-site)', 'import torch; assert torch.version.hip'),
    ('BS-RoFormer model class',
     'from audio_separator.separator.uvr_lib_v5.roformer.bs_roformer import BSRoformer'),
    ('MF transformers class',
     'from transformers import MusicFlamingoForConditionalGeneration, AutoProcessor'),
    ('pydub', 'import pydub'),
    ('librosa', 'import librosa'),
]:
    try:
        exec(stmt)
        print(f'  OK   {what}')
    except Exception as e:
        fails.append(what)
        print(f'  FAIL {what}: {type(e).__name__}: {e}')
import shutil, os
ff = shutil.which('ffmpeg')
print(f'  {\"OK  \" if ff else \"FAIL\"} ffmpeg on PATH: {ff}')
if not ff: fails.append('ffmpeg')
sys.exit(1 if fails else 0)
PYEOF
"
echo "== build_offload_venv: ALL GREEN =="
