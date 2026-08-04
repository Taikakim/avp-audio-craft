#!/bin/bash
# fullft_mem_probe.sbatch — MEMORY GATE for the #68 big-set full finetune (CONTINUITY 2026-08-04).
# Does Kim's target config FIT on one MI250X GCD (64 GB)? Runs ~20 real steps of:
#   full-FT (all 1.4B DiT) + fp32 + T2048 + bs4 + FusionOpt(all-on, NO shampoo) + EMA
# on the READY pre-encoded latents_sa3 (isolates DiT training memory — the dominant cost — without
# waiting on the big-set live-encode). Gradient checkpointing is ON by default (transformer.py:1235).
#
# READ THE RESULT:
#   - completes 20 steps + writes metrics.csv  -> the config FITS at bs4/T2048/fp32; scale to 40ep/8-GCD.
#   - HIP OOM in the first steps                -> step down IN THIS ORDER and re-probe: (1) --batch_size 2,
#       (2) --frames 1024, (3) --base_precision bf16. NB: the LIVE-ENCODE run adds the SAME encoder (~852M)
#       + raw audio to VRAM, so leave headroom — if this is >~55 GB peak, live-encode wants bf16 or bs2.
#   - the KL-SHAMPOO parallel arm (--fusion-shampoo) is HEAVIER (two-sided preconditioners) -> probe separately.
#
# 1 GCD on purpose: full-FT is DDP-replicate, so per-GCD memory == what one GCD holds == what OOMs.
# Multitorch image (ROCm7 + FA2) + the sa3_train_venv_mt overlay + the mandatory GPU env (lumi-ops skill).
#
#SBATCH --account=project_465003186
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem-per-gpu=60G
#SBATCH --time=00:40:00
#SBATCH --job-name=sa3_fullft_memprobe
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
RUN=${SCRATCH}/runs/fullft_mem_probe
mkdir -p "${RUN}" "${FLASH}"

[ -n "${SIF}" ] || { echo "[memprobe] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[memprobe] FATAL: ${VENV} missing — run build_train_venv_mt.sh"; exit 1; }
grep -q -- "--use-ema" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[memprobe] FATAL: train_lora.py missing --use-ema (code refresh needed)"; exit 1; }
grep -q -- "--full-finetune" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[memprobe] FATAL: train_lora.py missing --full-finetune"; exit 1; }

if [ ! -d "${FLASH}/latents_sa3" ]; then
  mkdir -p "${FLASH}/latents_sa3"
  tar -xzf "${SCRATCH}/latents_sa3.tar.gz" -C "${FLASH}/latents_sa3" --strip-components=1
fi
echo "[memprobe] image=${SIF}"
echo "[memprobe] goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=1 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUN=${SCRATCH}/runs/fullft_mem_probe
VENV='"${VENV}"'

source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
# MANDATORY GPU env (lumi-ops skill): MIOpen read-only-db fix + home-inode + tunableop off
export MIOPEN_USER_DB_PATH=/tmp/miopen-mp MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-mp
export TRITON_CACHE_DIR=/tmp/triton-mp PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-mp /tmp/triton-mp; mkdir -p /tmp/miopen-mp /tmp/triton-mp
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True   # reduce fragmentation OOMs at big T

SIDECAR=${CODE}/lumi/goa_longform_sidecar.json

echo "[memprobe] full-FT fp32 T2048 bs4 Fusion(no-shampoo) EMA, ~20 steps"
python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --full-finetune \
    --encoded_dir ${FLASH}/latents_sa3 \
    --save_dir "${RUN}" \
    --optimizer fusion \
    --use-ema --ema-beta 0.9999 \
    --base_precision fp32 \
    --lr 8e-5 --batch_size 4 \
    --frames 2048 --beat-aware-crop \
    --steps 20 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --caption_sidecar "${SIDECAR}" --caption_probs 0,0,1 \
    --name fullft_memprobe 2>&1 | tee ${RUN}/probe.log
echo "[memprobe] python rc=$? (0 = ran; look for a metrics.csv + no HIP OOM in probe.log)"
'
echo "[memprobe] ckpt/metrics written?"; ls -la "${RUN}"/ 2>/dev/null | head
echo "[memprobe] VERDICT: grep the .out/probe.log for 'out of memory' / 'HIP' — absent + metrics.csv present = FITS."
