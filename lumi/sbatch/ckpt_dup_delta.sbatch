#!/bin/bash
# ckpt_dup_delta.sbatch — CONTINUITY 2026-08-17: run ckpt_dup_delta.py as a real sbatch job
# instead of a bare login-node singularity call. The login-node attempt (run_ckpt_dup_delta.sh)
# hit `ModuleNotFoundError: No module named 'torch'` even inside `singularity exec` -- torch
# was missing entirely (not just shadowed by the container's own /opt/venv, which is a
# DIFFERENT documented gotcha -- SKILL.md's shadow-venv note is about wrong VERSIONS winning,
# not modules being absent altogether). Most likely cause: /appl/local/laifs/containers/ isn't
# mounted the same way outside a SLURM allocation. Every OTHER singularity invocation this
# session has gone through srun inside an sbatch job and worked reliably -- use that proven
# path instead of debugging login-node-specific mount/namespace quirks. No GPU actually needed
# for this diff (pure CPU + mmap), but keeping --gpus-per-node=1 for parity with every other
# proven job template (this project's allocation is GPU-partition only).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=00:30:00
#SBATCH --job-name=sa3_ckpt_delta
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
RUN=${RUN:-${SCRATCH}/runs/fullft_mixed_avp_latents_sa3_t4096_wdfix}

[ -n "${SIF}" ] || { echo "[ckpt-delta] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[ckpt-delta] FATAL: ${VENV} missing"; exit 1; }

srun --nodes=1 --ntasks=1 --gpus=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH} "${SIF}" bash -c '
set -euo pipefail
CODE='"${CODE}"'
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages
python3 ${CODE}/lumi/ckpt_dup_delta.py --run '"${RUN}"'
'
