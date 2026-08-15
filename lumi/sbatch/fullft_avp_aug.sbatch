#!/bin/bash
# fullft_avp_aug.sbatch — CONTINUITY 2026-08-09 (Kim direct: "stage an AVP aug set x8
# with the same recipe, 60eps"). Full-finetune of medium-base on the AVP ×8 set, 60
# epochs, mirroring #68's fullft_bigset recipe (full-FT, FusionOpt, EMA) on PRE-ENCODED
# latents.
#
# ── latents_avp IS ALREADY THE ×8 SET (verified 2026-08-09) ───────────────────────────
# No separate encode stage is needed: latents_avp = 2394 crops = 289 base + 2105 bungee-
# augmented, across exactly the 8 variants (pitch±1/±2, tempo±5/±10). The AVP corpus was
# augmented via mir/src/tools/augment_tracks.py, then base+variants were all cropped and
# SAME-encoded into latents_avp. So this trains directly on:
#   --encoded_dir latents_avp        (the base + ×8 augmentation, all in one dir)
# (An earlier draft assumed the aug set had to be built like goa's latents_goa_aug8 — it
# doesn't; avp was pre-augmented. Kim caught the redundant source upload.)
#
# ── WHY PRE-ENCODED x8, not live --augment ────────────────────────────────────────────
# #68 uses --data_dir + --augment (LIGHT live aug: gain/stereo; pitch/time only under
# --aug-heavy, which routes to torchaudio — FORBIDDEN by the bungee-only rule). The "x8"
# Kim wants is the STRUCTURAL 8-variant bungee pitch/tempo set, which only exists
# pre-encoded. So: pre-encoded base+aug8 latents (the x8 data) + #68's model recipe.
#
# ── DDP: Pattern 2 (--gpus-per-task=1, NO --devices) — IDENTICAL to #68's proven
#    multitorch launch. On this image Pattern 1 (all GPUs visible + --devices 8) OOMs:
#    load_model's model.to("cuda") runs BEFORE Lightning assigns per-rank devices, so all
#    8 ranks pile onto GPU 0 (job 20869819 died this way). cgroup-pinning each rank to 1
#    GCD is what fixes it. See the srun block below + lumi-ops SKILL. ───────────────────
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=48:00:00
#SBATCH --job-name=sa3_fullft_avp_aug
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
# CAPTIONS: --encoded_dir sources the prompt from each crop's OWN .json (base latents_avp
# carry prompts; encode_aug_task.py writes the inherited parent prompt into every aug
# crop's .json — line 112). So NO sidecar: both base + aug crops are captioned by
# construction, and a stem-keyed sidecar would MISS the __variant aug crops. (If richer
# tiered captions are wanted later, that's a follow-up needing a __variant-aware key_fn.)
BS=${BS:-4}; FRAMES=${FRAMES:-2048}; PREC=${PREC:-fp32}; LR=${LR:-8e-5}; EPOCHS=${EPOCHS:-60}; CKEVERY=${CKEVERY:-5}
# GA (2026-08-15, post-mortem on job 21148122's OOM): --use-ema is hardcoded ON below, and
# EMA's second full-precision model copy is fixed overhead the ORIGINAL bs4/fp32/T2048
# default absorbed (proven: WORKLOG "full-FT + fp32 + T2048 + bs4 + FusionOpt + EMA FITS on
# one 64GB GCD") but an override to BS=8 at bf16/T1024 did NOT, despite looking cheaper on
# paper (shorter T, half-precision) -- OOM'd in practice, mechanism not fully understood.
# Default GA=1 (unchanged behavior for anyone not touching BS). When raising the EFFECTIVE
# batch, prefer BS=2 + GA=<effective/2> over a larger raw BS -- that's the one pattern
# that's actually survived tonight (the T4096 mixed run, BS=2 GA=2).
GA=${GA:-1}
# WARMUP_FRAC / GRAD_CLIP_MODE (2026-08-15, Kim direct): both empty by default -> byte-
# identical to the original recipe (--warmup-steps stays 0, --grad-clip-mode stays "norm"
# with --gradient_clip_val unset -> disabled). Set WARMUP_FRAC=0.05 GRAD_CLIP_MODE=agc for
# the EMA+warmup+AGC stabilization recipe (replaces the earlier wd0.1+global-norm-clip
# combo -- AGC is "the gentler alternative to broad weight decay", train_lora.py's own
# --grad-clip-mode help).
WARMUP_FRAC=${WARMUP_FRAC:-}
GRAD_CLIP_MODE=${GRAD_CLIP_MODE:-}
RUNTAG=${RUNTAG:-}
NAME=fullft_avp_aug${RUNTAG:+_${RUNTAG}}
RUN=${SCRATCH}/runs/${NAME}
mkdir -p "${RUN}" "${FLASH}"

[ -n "${SIF}" ] || { echo "[avp-aug] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[avp-aug] FATAL: ${VENV} missing"; exit 1; }

# ── stage the ×8 latents (already base+aug) to node-local NVMe once ──
if [ ! -d "${FLASH}/latents_avp" ]; then
  [ -f "${SCRATCH}/latents_avp.tar.gz" ] || { echo "[avp-aug] FATAL: ${SCRATCH}/latents_avp.tar.gz missing — upload it (it already contains base + ×8 aug crops)"; exit 1; }
  mkdir -p "${FLASH}/latents_avp"
  tar -xzf "${SCRATCH}/latents_avp.tar.gz" -C "${FLASH}/latents_avp" --strip-components=1
fi
NCROP=$(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)
echo "[avp-aug] latents_avp (base+×8): ${NCROP} crops (expect ~2394)  image=${SIF}"
echo "[avp-aug] BS=${BS} GA=${GA} (eff batch $((BS*GA))) FRAMES=${FRAMES} PREC=${PREC} LR=${LR} EPOCHS=${EPOCHS} CKEVERY=${CKEVERY} WARMUP_FRAC=${WARMUP_FRAC:-off} GRAD_CLIP_MODE=${GRAD_CLIP_MODE:-off} RUNTAG=${RUNTAG:-none} NAME=${NAME}"

# ── DDP: Pattern 2 (--gpus-per-task=1) — IDENTICAL to #68's proven multitorch launch.
#    Each rank is cgroup-pinned to ONE GCD, so model.to("cuda") at load_model (line 130,
#    BEFORE Lightning assigns devices) lands on that rank's own GPU. Pattern 1 (all GPUs
#    visible, --devices 8) OOMs here: all 8 ranks load onto GPU 0 (job 20869819). NO
#    --devices flag — Lightning's SLURMEnvironment forms the world_size=8 group from
#    SLURM_NTASKS (proven by #68, which trains fine with no -vN ckpts). ────────────────
srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUN='"${RUN}"'
VENV='"${VENV}"'
source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${SLURM_PROCID} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${SLURM_PROCID}
export TRITON_CACHE_DIR=/tmp/triton-${SLURM_PROCID} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-${SLURM_PROCID} /tmp/triton-${SLURM_PROCID}; mkdir -p /tmp/miopen-${SLURM_PROCID} /tmp/triton-${SLURM_PROCID}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

# fp32 fused-SDPA probe (same as the aug8/#68 recipe): use native fp32 attention if the
# fused kernel is available, else cast bf16 for the SDPA only.
if [ "'"${PREC}"'" = "fp32" ]; then
  if python - <<PYEOF
import torch
from torch.nn.attention import sdpa_kernel, SDPBackend
q = torch.randn(1, 24, 4096, 64, device="cuda", dtype=torch.float32)
try:
    with sdpa_kernel([SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION]):
        torch.nn.functional.scaled_dot_product_attention(q, q, q)
    raise SystemExit(0)
except SystemExit as e:
    raise
except Exception:
    raise SystemExit(1)
PYEOF
  then export SA3_SDPA_CAST_BF16=0; else export SA3_SDPA_CAST_BF16=1; fi
  echo "[rank ${SLURM_PROCID}] fp32 SDPA cast_bf16=${SA3_SDPA_CAST_BF16}"
fi

# auto-resume from a prior fat ckpt in THIS run dir
FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME=""; [ -n "${FATCKPT}" ] && { RESUME="--resume_ckpt ${FATCKPT}"; echo "[avp-aug] resuming from ${FATCKPT}"; }

EXTRA_FLAGS=""
[ -n "'"${WARMUP_FRAC}"'" ] && EXTRA_FLAGS="${EXTRA_FLAGS} --warmup-frac '"${WARMUP_FRAC}"'"
[ -n "'"${GRAD_CLIP_MODE}"'" ] && EXTRA_FLAGS="${EXTRA_FLAGS} --grad-clip-mode '"${GRAD_CLIP_MODE}"'"
[ -n "${EXTRA_FLAGS}" ] && echo "[avp-aug] extra flags:${EXTRA_FLAGS}"

echo "[rank ${SLURM_PROCID}/${SLURM_NTASKS}] node=$(hostname) local=${SLURM_LOCALID} TRAIN fullft_avp_aug"
python ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --full-finetune \
  --encoded_dir ${FLASH}/latents_avp \
  --save_dir "'"${RUN}"'" \
  --optimizer fusion \
  --use-ema --ema-beta 0.9999 \
  --base_precision '"${PREC}"' \
  --lr '"${LR}"' --batch_size '"${BS}"' --accumulate_grad_batches '"${GA}"' \
  --frames '"${FRAMES}"' --beat-aware-crop \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  ${RESUME} ${EXTRA_FLAGS} \
  --num_workers 6 --seed 1 --no_demos --logger csv \
  --name '"${NAME}"' 2>&1 | tee -a '"${RUN}"'/train_rank${SLURM_PROCID}.log
'
echo "[avp-aug] DONE — verify (read log, not rc):"
echo "  world_size=8 one group:  grep -h 'initializing distributed\\|MEMBER:' ${RUN}/train_rank0.log | head"
echo "  NO -vN ckpts (dup writers): ls ${RUN}/epoch=*-v[0-9]*.ckpt 2>/dev/null && echo BAD || echo ok"
ls -la "${RUN}" 2>/dev/null | grep -E "epoch=|train_rank0" | head
# RENDER after ckpts land: reuse fullft_bigset_render.sbatch pattern pointed at this RUN
# (render_matrix_cells --fullft --use-ema). EMA weights ride as diffusion_ema.ema_model.*
