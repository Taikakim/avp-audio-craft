#!/bin/bash
# run_ckpt_dup_delta.sh -- login-node wrapper for ckpt_dup_delta.py (Kim direct 2026-08-17).
# No srun/sbatch needed (CPU/mmap-only). Runs INSIDE the multitorch container since the
# overlay venv's own python only resolves there (SKILL.md: "AIF/multitorch images ship their
# own /opt/venv" -- venv python is not on PATH on the bare login node).
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
SIF=$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)
VENV=${SCRATCH}/sa3_train_venv_mt
RUN=${RUN:-${SCRATCH}/runs/fullft_mixed_avp_latents_sa3_t4096_wdfix}

singularity exec --bind ${PROJ},${SCRATCH} "${SIF}" bash -c "source ${VENV}/bin/activate && export PYTHONPATH=${VENV}/lib/python3.12/site-packages && python3 ${CODE}/lumi/ckpt_dup_delta.py --run ${RUN}"
