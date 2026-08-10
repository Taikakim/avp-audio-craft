#!/bin/bash
# multinode_ddp_smoke.sbatch — CONTINUITY 2026-08-09, for Kim's multi-node scale-up
# (aug8 + slow-long-run acceleration). PURPOSE: prove ONE thing cheaply before we bet
# the remaining GPU hours on multi-node — does an 8-GCD-per-node Lightning DDP group
# EXTEND ACROSS NODES (RCCL rendezvous over Slingshot forms a single world_size=32
# group)? Single-node 8-GCD DDP is a VERIFIED recipe (lumi-ops SKILL, smoke 20422454
# COMPLETED) = "Pattern 1": srun --ntasks-per-node=8 --gpus-per-node=8 (NO
# --gpus-per-task, NO ROCR — every rank sees all 8 GCDs, Lightning binds via
# SLURM_LOCALID) + train_lora.py --devices 8. This smoke extends THAT proven recipe to
# 4 nodes via the --num_nodes hook (added to train_lora 2026-08-09). So it's a
# ONE-VARIABLE test: single-node DDP works → does adding nodes + the inter-node fabric
# env keep it one coordinated world_size=32 group, or hang at rendezvous / split per-node?
#
# ⚠️ NOTE (2026-08-09): #68 fullft_bigset uses the OTHER launch ("Pattern 2":
# --gpus-per-task=1, no --devices) which the SKILL warns can silently fall back to N
# UNCOORDINATED trainers (tell: epoch=..-vN ckpts, no "initializing distributed" line).
# Whether #68 actually formed one group on the multitorch image is being verified
# separately. This smoke deliberately uses the VERIFIED Pattern 1 — it fails LOUDLY on
# a mis-launch instead of silently splitting.
#
# ── WHY THIS IS LOW-RISK / CHEAP ──────────────────────────────────────────────────
# - Uses PRE-ENCODED latents (--encoded_dir), NOT live-encode (--data_dir): isolates
#   the DDP-rendezvous variable from the torchaudio/torchcodec live-encode path (which
#   is a SEPARATE known multitorch gotcha, lumi-ops SKILL §live-encode). One test, one
#   variable.
# - --steps 40 (not epochs): a few minutes of a 4-node alloc = ~ a few GPU-hours, the
#   cost of de-risking a multi-day multi-node campaign.
# - dora-bf16 (light, fast, low OOM headroom needed) — the MODEL output is irrelevant;
#   we only read the DDP/rendezvous telemetry.
#
# ── SUCCESS CRITERIA (read the .out — sbatch rc 0 proves NOTHING) ──────────────────
#   PASS  = rank-0 log shows ONE trainer reporting:
#             "initializing distributed: GLOBAL_RANK: 0, MEMBER: 1/32"  (world = 32)
#           and Lightning prints "Number of nodes: 4", "GPU available ... 8", strategy
#           DDP; loss ticks ONCE per global step; ONE set of ckpts (NOT epoch=..-v1..-v31
#           versioned files = N uncoordinated writers = FAIL).
#   FABRIC-OK check: grep the .out for RCCL using the OFI/CXI plugin, e.g.
#             "NET/OFI" / "Selected Provider is cxi"  (if you see "NET/Socket" only,
#           RCCL fell back to TCP over hsn — still may WORK for the smoke but is the
#           slow path; note it, it's a perf fix not a correctness blocker).
#   HANG (no progress past "initializing distributed" for >5 min) = inter-node fabric
#           env wrong → the thing this smoke exists to catch. First fixes to try, in
#           order: (1) confirm NCCL_SOCKET_IFNAME matches the node's Slingshot NICs
#           (`ip -o link | grep hsn` on a compute node); (2) drop NCCL_NET_GDR_LEVEL;
#           (3) add MASTER_PORT collision avoidance; (4) fall back to the torchrun-c10d
#           launcher (CSC docs pattern) — noted at the bottom of this file.
#
# ── AFTER THIS PASSES ──────────────────────────────────────────────────────────────
# The real runs reuse this EXACT launch + env, swapping the smoke train call for:
#   - WEAK scaling (large-batch scale test, aug8 flagship): per-GCD BS kept, global
#     batch = 32 x per-GCD, lr scaled by the SQRT rule (~1e-4*sqrt(32) ~= 5.5e-4) +
#     longer warmup. Validates large-batch training preserves quality → unlocks fresh
#     long runs (#50 long-context) finishing in the 2 weeks left.
#   - STRONG scaling (accelerate a slow run, no LR risk): matched global batch across
#     32 GCDs (per-GCD BS = single-node/4), SAME lr — identical optimization, faster
#     wall-clock. The no-risk way to speed a mid-run resume like #68.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=4
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=00:30:00
#SBATCH --job-name=sa3_mn_ddp_smoke
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
RUN=${SCRATCH}/runs/multinode_ddp_smoke
mkdir -p "${RUN}"

[ -n "${SIF}" ] || { echo "[mn-smoke] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[mn-smoke] FATAL: ${VENV} missing"; exit 1; }

# ── stage the existing goa latents to node-local NVMe once (data-independent smoke —
#    reuses the proven latents_sa3 corpus; NOTE: /flash is node-local, so on a 4-node
#    job each node must have it. srun below runs the stage on every node first.) ──
srun --ntasks-per-node=1 --ntasks=${SLURM_NNODES} bash -c '
  FLASH=/flash/project_465003186; SCRATCH=/scratch/project_465003186
  if [ ! -d "${FLASH}/latents_sa3" ]; then
    mkdir -p "${FLASH}/latents_sa3"
    tar -xzf "${SCRATCH}/latents_sa3.tar.gz" -C "${FLASH}/latents_sa3" --strip-components=1
  fi
  echo "[mn-smoke] $(hostname) latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"'

# ── inter-node rendezvous (Lightning SLURMEnvironment also derives these, but set them
#    explicitly so a mis-launch is loud, and so RCCL agrees on the endpoint) ──
export MASTER_ADDR=$(scontrol show hostnames "${SLURM_JOB_NODELIST}" | head -n1)
export MASTER_PORT=29500
echo "[mn-smoke] nodes=${SLURM_NNODES} MASTER_ADDR=${MASTER_ADDR} image=${SIF}"

# ── the 32-rank DDP smoke: Pattern 2 (the multitorch recipe) — --ntasks-per-node=8
#    --gpus-per-task=1, per-GCD cgroup pinning. NO --devices: Lightning's SLURMEnvironment
#    derives world_size from SLURM_NTASKS (= nodes*8) and MASTER_ADDR from node 0.
#    (Pattern 1 — all GPUs visible + --devices N — OOMs on multitorch: every rank's
#    load_model model.to("cuda") piles onto GPU 0. Confirmed by job 20869819. See the
#    lumi-ops SKILL "DDP CORRECTION" bullet.)
#    ALT LAUNCH (CSC docs.csc.fi/support/tutorials/ml-multi, if Pattern 2 misbehaves):
#    `srun --ntasks-per-node=1 singularity run $SIF torchrun --nnodes=$SLURM_NNODES
#    --nproc_per_node=8 --rdzv_backend=c10d --rdzv_endpoint=$MASTER_ADDR:$MASTER_PORT ...`
#    (1 task/node, torchrun forks 8). CSC also wires the fabric via
#    `module load lumi-aif-singularity-bindings` INSTEAD of the manual NCCL/CXI env below —
#    try that if the OFI provider isn't picked up (see the fabric note). ─────
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

# ── LUMI Slingshot / RCCL inter-node fabric (THE new-vs-single-node part) ──
# The aws-ofi-rccl plugin ships INSIDE lumi-multitorch-full → RCCL uses libfabric/CXI
# over Slingshot. These exports point RCCL at the 4 high-speed NICs and keep libfabric
# fork-safe with the dataloader workers. VERIFY on the first run (see header): if RCCL
# logs NET/Socket instead of NET/OFI, the plugin/provider is not being picked up (perf,
# not correctness); if it HANGS at "initializing distributed", NCCL_SOCKET_IFNAME is the
# prime suspect (confirm the hsn interface names on a compute node).
export NCCL_SOCKET_IFNAME=hsn0,hsn1,hsn2,hsn3
export NCCL_NET_GDR_LEVEL=PHB
export MPICH_GPU_SUPPORT_ENABLED=1
export CXI_FORK_SAFE=1 CXI_FORK_SAFE_HP=1 FI_CXI_DISABLE_CQ_HUGETLB=1
export FI_MR_CACHE_MONITOR=userfaultfd
export NCCL_DEBUG=INFO   # SMOKE ONLY: prints the transport/provider so we can read the fabric path; drop for real runs

ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

echo "[rank ${SLURM_PROCID}/${SLURM_NTASKS}] node=$(hostname) local=${SLURM_LOCALID} MASTER=${MASTER_ADDR}:${MASTER_PORT}"

# Pattern 2: no --devices/--num_nodes — SLURMEnvironment derives world_size=nodes*8=32
# from SLURM_NTASKS. dora-bf16, tiny, 40 steps. Success = DDP telemetry (world_size=32,
# one group), not the model.
python ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base \
  --adapter_type dora-rows --rank 128 --lora_alpha 128 \
  --encoded_dir ${FLASH}/latents_sa3 \
  --save_dir "'"${RUN}"'" \
  --optimizer fusion \
  --lr 1e-4 --batch_size 1 \
  --frames 512 --beat-aware-crop \
  --steps 40 \
  --num_workers 4 --seed 1 --no_demos --logger csv \
  --name mn_ddp_smoke 2>&1 | tee -a '"${RUN}"'/train_rank${SLURM_PROCID}.log
'
echo "[mn-smoke] DONE — READ THE LOG, not the rc:"
echo "  world size:   grep -h 'initializing distributed\\|MEMBER\\|Number of nodes' ${RUN}/train_rank0.log"
echo "  fabric path:  grep -h 'NET/OFI\\|NET/Socket\\|Selected Provider' ${RUN}/train_rank0.log | head"
echo "  one-group?:   ls ${RUN}/*.ckpt   (versioned -vN files = FAIL: uncoordinated writers)"
ls -la "${RUN}" || true

# ── FALLBACK launcher (only if Pattern 2 multi-node rendezvous fails) — the CSC-docs
#    torchrun/c10d pattern (docs.csc.fi/support/tutorials/ml-multi). Would need
#    --ntasks-per-node=1 + `srun torchrun --nnodes=${SLURM_NNODES} --nproc_per_node=8
#    --rdzv_backend=c10d --rdzv_endpoint=${MASTER_ADDR}:${MASTER_PORT} train_lora.py
#    --devices 8 --num_nodes ${SLURM_NNODES}` (uses the --num_nodes hook added to
#    train_lora 2026-08-09). Kept as a documented plan B; Pattern 2 is tried first
#    because it's a zero-diff extension of the proven #68 launch.
