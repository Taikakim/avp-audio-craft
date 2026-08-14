#!/bin/bash
# fullft_avp_aug_mn2.sbatch — CONTINUITY 2026-08-14 (Kim direct: "verify the multi-node
# setup with 2x8 GPUs. Warmup, EMA, Adagc, lr 1e-4, bf16, t1024 for speed avp aug set").
#
# TWO PURPOSES IN ONE JOB, deliberately: (1) verify 2-node (16 GCD) DDP actually forms
# ONE coordinated world_size=16 group over LUMI's Slingshot fabric — UNVERIFIED as of
# 2026-08-09 (multinode_ddp_smoke.sbatch proved the LAUNCH PATTERN at 4 nodes/32 GCDs
# exists and is documented, but its own header notes the smoke had not yet been run to
# a PASS/HANG verdict). (2) if it forms, the run itself is real signal: a NEW candidate
# stabilization recipe (warmup + AGC, replacing the earlier wd0.1+global-norm-clip
# combo — AGC is "the gentler alternative to broad weight decay for the FusionOpt
# full-FT latent-scale runaway", train_lora.py's own --grad-clip-mode help) tested on
# the AVP aug set at T1024 (chosen for speed/iteration, not T2048/T4096).
#
# ── RECIPE, vs fullft_avp_aug.sbatch (the single-node ancestor of this file) ──────────
#   frames  2048 -> 1024   (speed, Kim direct)
#   precision fp32 -> bf16 (speed, Kim direct — the fp32-SDPA probe block is DROPPED,
#                            it only matters for the fp32 path)
#   lr      8e-5 -> 1e-4   (Kim direct)
#   NEW: --warmup-frac (FusionOpt warmup, added to train_lora.py THIS SESSION,
#        2026-08-14 — every prior Fusion run had warmup_steps=0). Default 0.05 = one
#        epoch's worth of optimizer steps at ANY epoch count (Kim: "aim for 5% at
#        least of the intended length").
#   NEW: --grad-clip-mode agc (Adaptive Gradient Clipping, NFNets/Brock — per-unit
#        grad-norm-relative-to-weight-norm clip, INSTEAD of the earlier
#        --weight_decay 0.1 + --gradient_clip_val 1.0 combo from the #68/#69 drone fix).
#        --weight_decay left UNSET (defaults to 0.0 for fusion) — AGC is meant to
#        replace broad weight decay, not stack with it (see the flag's own docstring).
#   unchanged: --full-finetune --optimizer fusion --use-ema --ema-beta 0.9999,
#              --encoded_dir latents_avp (the AVP aug×8 set — base+2105 bungee variants,
#              289+2105=2394 crops, verified 2026-08-09, no separate encode needed).
#
# ── DDP LAUNCH: Pattern 2 extended across nodes (multinode_ddp_smoke.sbatch's proven
#    plumbing, copied verbatim — do NOT improvise the fabric env, it was hard-won) ──
#    --ntasks-per-node=8 --gpus-per-task=1 (cgroup-pins each rank to one GCD; Pattern 1
#    with --devices OOMs on multitorch, job 20869819 — model.to("cuda") in load_model
#    runs before Lightning assigns per-rank devices). NO --devices/--num_nodes flag to
#    train_lora.py — Lightning's SLURMEnvironment derives world_size = SLURM_NTASKS
#    (nodes*8) and MASTER_ADDR from node 0 automatically.
#
# ── VERIFY (read the log, sbatch rc proves nothing — MASTER §5 rule) ──────────────────
#   world_size=16 one group:  grep -h 'initializing distributed\|MEMBER:\|Number of nodes' ${RUN}/train_rank0.log
#   fabric path (perf only):  grep -h 'NET/OFI\|NET/Socket\|Selected Provider' ${RUN}/train_rank0.log | head
#   ONE coordinated writer:   ls ${RUN}/epoch=*-v[0-9]*.ckpt 2>/dev/null && echo BAD-dup-writers || echo ok
#   HANG (>5min stuck at "initializing distributed") -> NCCL_SOCKET_IFNAME mismatch is
#   the prime suspect; see multinode_ddp_smoke.sbatch's header for the fix order.
#
# RUN: [SMOKE=1] (few steps only, verify DDP forms one group before committing GPU-h)
#      [BS=] [FRAMES=1024] [LR=1e-4] [EPOCHS=20] [CKEVERY=2] [WARMUP_FRAC=0.05]
#      sbatch lumi/sbatch/fullft_avp_aug_mn2.sbatch
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=2
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=sa3_fullft_avp_aug_mn2
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
BS=${BS:-4}; FRAMES=${FRAMES:-1024}; LR=${LR:-1e-4}; EPOCHS=${EPOCHS:-20}; CKEVERY=${CKEVERY:-2}
WARMUP_FRAC=${WARMUP_FRAC:-0.05}
NAME=fullft_avp_aug_mn2
RUN=${SCRATCH}/runs/${NAME}
mkdir -p "${RUN}" "${FLASH}"

if [ "${SMOKE:-0}" = "1" ]; then
  STEPS_FLAG="--steps 40"
  EPOCHS_FLAG=""
  echo "[mn2] SMOKE MODE: 40 steps, ignores EPOCHS — verify DDP forms one group before the real run"
else
  STEPS_FLAG=""
  EPOCHS_FLAG="--epochs ${EPOCHS} --checkpoint_every_epochs ${CKEVERY}"
fi

[ -n "${SIF}" ] || { echo "[mn2] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[mn2] FATAL: ${VENV} missing"; exit 1; }
grep -q -- "--warmup-frac" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[mn2] FATAL: train_lora.py missing --warmup-frac (code refresh needed — added 2026-08-14)"; exit 1; }

# ── stage latents_avp (base+×8 aug, 2394 crops) to node-local NVMe on EVERY node ──
srun --ntasks-per-node=1 --ntasks=${SLURM_NNODES} bash -c '
  FLASH=/flash/project_465003186; SCRATCH=/scratch/project_465003186
  if [ ! -d "${FLASH}/latents_avp" ]; then
    [ -f "${SCRATCH}/latents_avp.tar.gz" ] || { echo "[mn2] FATAL on $(hostname): latents_avp.tar.gz missing"; exit 1; }
    mkdir -p "${FLASH}/latents_avp"
    tar -xzf "${SCRATCH}/latents_avp.tar.gz" -C "${FLASH}/latents_avp" --strip-components=1
  fi
  echo "[mn2] $(hostname) latents_avp: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l) crops (expect ~2394)"'

export MASTER_ADDR=$(scontrol show hostnames "${SLURM_JOB_NODELIST}" | head -n1)
export MASTER_PORT=29500
echo "[mn2] nodes=${SLURM_NNODES} MASTER_ADDR=${MASTER_ADDR} image=${SIF}"
echo "[mn2] BS=${BS} FRAMES=${FRAMES} LR=${LR} EPOCHS=${EPOCHS} CKEVERY=${CKEVERY} WARMUP_FRAC=${WARMUP_FRAC} SMOKE=${SMOKE:-0}"

srun --nodes=${SLURM_NNODES} --ntasks-per-node=8 --gpus-per-task=1 --cpus-per-task=7 \
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
export MASTER_ADDR='"${MASTER_ADDR}"' MASTER_PORT='"${MASTER_PORT}"'

# ── LUMI Slingshot / RCCL inter-node fabric — copied VERBATIM from
#    multinode_ddp_smoke.sbatch (2026-08-09). Do not improvise these. ──
export NCCL_SOCKET_IFNAME=hsn0,hsn1,hsn2,hsn3
export NCCL_NET_GDR_LEVEL=PHB
export MPICH_GPU_SUPPORT_ENABLED=1
export CXI_FORK_SAFE=1 CXI_FORK_SAFE_HP=1 FI_CXI_DISABLE_CQ_HUGETLB=1
export FI_MR_CACHE_MONITOR=userfaultfd
export NCCL_DEBUG=INFO   # verification run: prints the transport/provider; drop once confirmed

ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME=""; [ -n "${FATCKPT}" ] && { RESUME="--resume_ckpt ${FATCKPT}"; echo "[mn2] resuming from ${FATCKPT}"; }

echo "[rank ${SLURM_PROCID}/${SLURM_NTASKS}] node=$(hostname) local=${SLURM_LOCALID} MASTER=${MASTER_ADDR}:${MASTER_PORT}"
python ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --full-finetune \
  --encoded_dir ${FLASH}/latents_avp \
  --save_dir "'"${RUN}"'" \
  --devices 8 --num_nodes ${SLURM_NNODES} \
  --optimizer fusion \
  --use-ema --ema-beta 0.9999 \
  --warmup-frac '"${WARMUP_FRAC}"' \
  --grad-clip-mode agc \
  --base_precision bf16 \
  --lr '"${LR}"' --batch_size '"${BS}"' \
  --frames '"${FRAMES}"' --beat-aware-crop \
  '"${STEPS_FLAG}"' '"${EPOCHS_FLAG}"' \
  ${RESUME} \
  --num_workers 6 --seed 1 --no_demos --logger csv \
  --name '"${NAME}"' 2>&1 | tee -a '"${RUN}"'/train_rank${SLURM_PROCID}.log
'
echo "[mn2] DONE — READ THE LOG, not the rc:"
echo "  world size:   grep -h 'initializing distributed\\|MEMBER\\|Number of nodes' ${RUN}/train_rank0.log"
echo "  fabric path:  grep -h 'NET/OFI\\|NET/Socket\\|Selected Provider' ${RUN}/train_rank0.log | head"
echo "  one-group?:   ls ${RUN}/epoch=*-v[0-9]*.ckpt 2>/dev/null && echo BAD-dup-writers || echo ok"
ls -la "${RUN}" 2>/dev/null | grep -E "epoch=|train_rank0" | head
