#!/bin/bash
# diag_dora_determinism.sbatch — GHOST-NOTE 2026-09-25, for CONTINUITY's TEST 2
# (docs/training-findings.md 13e: the live-DoRA render nondeterminism repro, run on
# LUMI's MI250X (gfx90a) to separate this card/driver from the desktop RX 9070 XT
# (gfx1201). Same test, one GCD, no training. PREPARED, NOT SUBMITTED — hand-review
# with CONTINUITY before this reaches the operator.
#
# WHAT THIS NEEDS STAGED FIRST (rsync commands are separate, see the DM handback):
#   ${PROJ}/code/stable-audio-3/scripts/diag_dora_render_determinism.py  (patched, --slim-adapter)
#   ${PROJ}/code/stable-audio-3/scripts/demo_cfg_sweep.py                (unchanged, imported by the above)
#   ${PROJ}/code/stable-audio-3/scripts/eval_demo_callback.py            (unchanged, imported by the above)
#   ${PROJ}/code/stable-audio-3/stable_audio_3/                          (the package itself)
#   ${SCRATCH}/diag_dora/slim_adapter_x_step3804.pt                      (667 MB -- see note below)
#   ${PROJ}/models/                                                      (medium-base weights, HF_HUB_OFFLINE=1 --
#                                                                          reuses whatever's already cached from
#                                                                          prior LUMI training runs; if this arm is
#                                                                          the first to ever load medium-base on
#                                                                          LUMI, HF_HUB_OFFLINE will fail loudly
#                                                                          and needs HF_HUB_OFFLINE=0 once to warm
#                                                                          the cache -- flag this to the operator)
#
# NOTE ON THE SLIM ADAPTER: C's estimate was "tens of MB" -- it's actually 667 MB (687 DoRA
# tensors at rank 128 across the whole DiT + conditioner). Still two orders of magnitude
# smaller than the 4 GB Lightning ckpt (which also isn't needed here -- no optimizer_states).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=00:30:00
#SBATCH --job-name=diag_dora_determinism
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
ADAPTER=${SCRATCH}/diag_dora/slim_adapter_x_step3804.pt

srun --nodes=1 --ntasks=1 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
ADAPTER=${SCRATCH}/diag_dora/slim_adapter_x_step3804.pt

export HF_HOME="'"${MODELS}"'" HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor
# Mandatory on gfx90a (lumi-ops): the MIOpen kernel-cache SQLite open fails on every LUMI
# filesystem without MIOPEN_DISABLE_CACHE=1; kernels recompile per run instead.
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export MIOPEN_USER_DB_PATH=/tmp/miopen-diag MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-diag
export TRITON_CACHE_DIR=/tmp/triton-diag
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
# No ROCR_VISIBLE_DEVICES here: Slurm assigns the one GCD, and the proven render sbatches
# (a13_render, a2a_bracket) do not override it.
export TMPDIR=/tmp

DIAG=${CODE}/stable-audio-3/scripts/diag_dora_render_determinism.py

echo "[diag] === 3x --mode live --sdpa ==="
for i in 1 2 3; do
  echo "[diag] --- live run ${i} ---"
  # the repro exits 1 on MISMATCH by design: capture it, or set -e ends the job after run 1
  rc=0; python "${DIAG}" --mode live --sdpa --slim-adapter --ckpt "${ADAPTER}" || rc=$?
  echo "[diag] run ${i} rc=${rc}"
done

echo "[diag] === control: 1x --mode merged --sdpa (must say DETERMINISTIC) ==="
rc=0; python "${DIAG}" --mode merged --sdpa --slim-adapter --ckpt "${ADAPTER}" || rc=$?
echo "[diag] control rc=${rc}"
'
# SUCCESS = readable per this repo:
#   - every "live fresh cfg1" std matches across the 3 live runs (baseline is sound here too)
#   - the final DETERMINISTIC/MISMATCH line per run
#   - the control run ends DETERMINISTIC (if not, the harness itself is broken on this stack --
#     do not trust the live-mode result)
# ON A CRASH: LUMI compute nodes have no user journalctl access. The HIP runtime prints
# "Memory access fault by GPU node-N ... Reason: ..." and the faulting kernel name directly to
# stderr, which this job's %x-%j.out already captures (no extra flag needed) -- grep it:
#   grep -A2 -B2 "Memory access fault" diag_dora_determinism-<jobid>.out
