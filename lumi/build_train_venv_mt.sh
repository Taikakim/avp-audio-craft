#!/bin/bash
# build_train_venv_mt.sh — SA3 TRAINING venv overlay on the LUMI multitorch image
# (ROCm 7 + prebuilt gfx90a flash-attn). Migrates train_lora off the legacy sa3.sif
# (ROCm 6.2 — MIOpen gfx90a FindDb-gap → FAST-mode AI-fallback → first-backward hang;
# see lumi-ops skill "Containers"). RUN ON uan18. Idempotent. Mirrors build_offload_venv_mt.sh.
#
# torch / torchaudio / flash-attn come FROM the image (--system-site-packages) — NOT reinstalled.
# The COMPAT GATE is step [3]: it imports stable_audio_3 + train_lora deps against the image's
# ROCm-7 torch. If that passes, training on multitorch is viable; if it fails, we see the exact
# torch/API mismatch before spending a GPU node.
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
# readable path is laifs/containers (easybuild-sif-images symlinks are non-world-readable)
MTSIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
[ -n "${MTSIF}" ] || { echo "FATAL: no lumi-multitorch-full under /appl/local/laifs/containers/ — ls that dir and pass MTSIF=<path>"; exit 1; }
VENV=${SCRATCH}/sa3_train_venv_mt
echo "== base image: ${MTSIF} =="

echo "== [1/3] venv (system-site-packages: reuse image torch+flash-attn) =="
[ -d "${VENV}" ] || singularity exec --bind "${SCRATCH}" "${MTSIF}" python3 -m venv --system-site-packages "${VENV}"

echo "== [2/3] training deps (NO torch/torchaudio — those are the image's) =="
singularity exec --bind "${SCRATCH}" "${MTSIF}" bash -c "
  source ${VENV}/bin/activate
  pip install --no-cache-dir --upgrade pip -q
  pip install --no-cache-dir 'pytorch-lightning>=2.4,<3' dill matplotlib pillow 'numpy<2.4' \
    einops safetensors soundfile tqdm tensorboard 'transformers>=4.44' sentencepiece \
    accelerate huggingface_hub librosa pyloudnorm pedalboard wandb
"

echo "== [3/3] COMPAT GATE: sa3 stack imports on the image's ROCm-7 torch =="
singularity exec --bind "${PROJ}","${SCRATCH}" "${MTSIF}" bash -c "
  source ${VENV}/bin/activate
  # APPEND to the container's \$PYTHONPATH (do NOT clobber) — the image sets it to /opt/venv/...
  # where torch/flash-attn LIVE. \$ ESCAPED so this expands INSIDE the container (where PYTHONPATH is
  # set), not in the outer login shell (unset + set -u -> unbound-var crash, and would append nothing).
  export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor\${PYTHONPATH:+:\${PYTHONPATH}}
  export HF_HOME=${MODELS} HF_HUB_OFFLINE=1
  python - <<'PYEOF'
ok=True
import torch; print('torch', torch.__version__, '| hip', getattr(torch.version,'hip',None), '| cuda-avail', torch.cuda.is_available())
try:
    import flash_attn; print('flash_attn', flash_attn.__version__)
except Exception as e: print('flash_attn MISSING (FA2 will be off):', e)
import pytorch_lightning as pl; print('lightning', pl.__version__)
try:
    import stable_audio_3
    from stable_audio_3.models.lora.model import LoRAParametrization
    print('stable_audio_3 import OK | phm_n arg present:', 'phm_n' in LoRAParametrization.__init__.__code__.co_varnames)
except Exception as e:
    ok=False; print('stable_audio_3 IMPORT FAILED:', repr(e))
print('COMPAT GATE:', 'PASS' if ok else 'FAIL')
PYEOF
"
echo "== done. If COMPAT GATE: PASS -> ping CONTINUITY to wire the multitorch training sbatch. =="
