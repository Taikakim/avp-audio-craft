#!/bin/bash
# efp_fp32_frames.sbatch — fp32 FRAME-LENGTH sweep (Kim direct 2026-07-21).
# "Does fp32 help with longer trains / longer context?" Runs the rank-128 fp32 DoRA
# at bs1 AND bs4 across four frame lengths {512,1024,2048,4096}, for BOTH corpora,
# 10 epochs each, all FRESH from scratch (we never had t1024/t2048 fp32 to resume, and
# redoing t512/t4096 fresh keeps the frame comparison apples-to-apples).
#
# 16 arms = 2 corpora x {bs1,bs4} x {512,1024,2048,4096}. A node has 8 GCDs, so 16 arms
# = 2 nodes, one corpus per node, the proven efp_fp32_compare single-GCD-per-arm packing
# (NOT 8 separate nodes — that would idle 7 GCDs/node for no speedup). Paste-ready for
# the EFP Workflows UI.
#
#   node 0 (PROCID 0-7)  = goa (latents_sa3):  t512/1024/2048/4096 x {bs1,bs4}
#   node 1 (PROCID 8-15) = avp (latents_avp):  same grid
#   within a corpus: LOCAL=PROCID%8 -> frame=FRAMES[LOCAL/2], bs = (LOCAL even? 1 : 4)
#
# DESIGN (matches efp_fp32_compare so results compose): dora-rows r128 a128, optimizer
# fusion, base_precision fp32, lr 1e-4, longform-sidecar captions (PROBS 0,0,1). fp32
# attention via the SDPA capability probe (true-fp32 if the fused backend accepts it,
# else the bf16-island fallback SA3_SDPA_CAST_BF16=1 — same convention as the FA path).
#
# CROP: t4096 = the full ~380 s track (T=4096 @ 10.767 Hz), no crop. t512/1024/2048 are
# sub-full crops -> --beat-aware-crop (musically aligned window), applied to every T<4096.
#
# BATCH: bs is FIXED per Kim (bs1, bs4) — no max-probe. The memory-tightest arm is
# bs4 x t4096 fp32 (~63-71 GB on the 64 GB GCD; the efp_fp32_compare probe DID land bs4
# there, so it fits, but it is the coin-flip arm). If it OOMs it dies ALONE (|| keeps
# siblings up); every other arm (bs1-any, bs4 at t<=2048) is comfortably within budget.
#
# EPOCHS/WALLTIME: 10 epochs, ckpt every epoch. Heaviest arms (bs4 t4096; bs1 t4096 =
# most steps) may brush the 47 h wall at 10 epochs fp32 — per-epoch checkpoints make
# partial completion useful. BILLING: 2 nodes x walltime ~= 2 x 8 x 47 = 752 GCD-h of
# the 5000 budget.
#
# PREREQS: code+SIF+models pre-staged; latents_avp.tar.gz AND latents_sa3.tar.gz on
# ${SCRATCH} (Kim's rsync); code tarball has the fp32 train_lora patch + the
# transformer.py SA3_SDPA_CAST_BF16 island (same as efp_fp32_compare).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=2
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=47:00:00
#SBATCH --job-name=sa3_fp32_frames
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/fp32_frames
mkdir -p "${RUNROOT}"

# ── stage BOTH datasets to node-local NVMe on EVERY node (once per node) ──
# 2 nodes -> the sbatch body runs only on node 0, so staging must be an srun that
# fans one task to each node. Idempotent (skips if already extracted).
srun --nodes=2 --ntasks=2 --ntasks-per-node=1 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
FLASH=/flash/project_465003186; SCRATCH=/scratch/project_465003186
for DS in latents_avp latents_sa3; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[stage $(hostname)] avp=$(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l) goa=$(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"
'

# ── 16 training arms, one per GCD across 2 nodes, driven by SLURM_PROCID ──
srun --nodes=2 --ntasks=16 --ntasks-per-node=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/fp32_frames

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

# ── arm table (arithmetic): PROCID 0-7 = goa, 8-15 = avp; LOCAL picks frame + bs ──
FRAMES=(512 1024 2048 4096)
LOCAL=$((ARM % 8))
if [ ${ARM} -lt 8 ]; then DS=latents_sa3; else DS=latents_avp; fi
T=${FRAMES[$((LOCAL / 2))]}
if [ $((LOCAL % 2)) -eq 0 ]; then BS=1; else BS=4; fi
LR=1e-4; LRTAG=1e4
DSTAG=$([ "${DS}" = latents_avp ] && echo avp || echo goa)

# longform-sidecar captions (pure-longform PROBS=0,0,1), same as efp_fp32_compare
SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json
PROBS=0,0,1

# ── fp32 SDPA capability probe (cheap; picks true-fp32 vs bf16-island) ──
if python - <<PYEOF
import torch
from torch.nn.attention import sdpa_kernel, SDPBackend
q = torch.randn(1, 24, 4096, 64, device="cuda", dtype=torch.float32)
try:
    with sdpa_kernel([SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION]):
        torch.nn.functional.scaled_dot_product_attention(q, q, q)
    print("fp32 fused SDPA: OK")
except Exception as e:
    print(f"fp32 fused SDPA unavailable: {e}")
    raise SystemExit(1)
PYEOF
then
  export SA3_SDPA_CAST_BF16=0
  echo "[arm ${ARM}] attention: true fp32"
else
  export SA3_SDPA_CAST_BF16=1
  echo "[arm ${ARM}] attention: bf16 island (fused fp32 unsupported)"
fi

RUN=${RUNROOT}/fp32frames_${DSTAG}_t${T}_bs${BS}_lr${LRTAG}
mkdir -p "${RUN}"
echo "[arm ${ARM}] TRAIN ${DSTAG} T=${T} BS=${BS} lr=${LR} fp32 10ep -> ${RUN}"

# crop only sub-full frame counts (t4096 = full track)
CROP=$([ "${T}" != "4096" ] && echo --beat-aware-crop || true)

if python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/${DS} \
    --save_dir "${RUN}" \
    --adapter_type dora-rows --rank 128 --lora_alpha 128 \
    --optimizer fusion \
    --base_precision fp32 \
    --lr ${LR} --batch_size ${BS} \
    --frames ${T} ${CROP} \
    --epochs 10 --checkpoint_every_epochs 1 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name fp32frames_${DSTAG}_t${T}_bs${BS}_lr${LRTAG} \
    --caption_sidecar "${SIDECAR}" --caption_probs "${PROBS}" \
    2>&1 | tee ${RUN}/train.log; then
  echo "[arm ${ARM}] DONE"
else
  echo "[arm ${ARM}] TRAIN FAILED — see ${RUN}/train.log (siblings unaffected)"
fi
'
echo "[fp32frames] all arms finished:" && ls -la "${RUNROOT}"
# SUCCESS: 16 dirs fp32frames_{goa,avp}_t{512,1024,2048,4096}_bs{1,4}_lr1e4, one ckpt per
# epoch each. Compare across the frame axis (does longer context/train help under fp32?)
# and against the bf16/T=512 local runs + the efp_fp32_compare T=4096 baseline.
