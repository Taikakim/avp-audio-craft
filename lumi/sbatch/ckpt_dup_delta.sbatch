#!/bin/bash
# ckpt_dup_delta.sbatch — CONTINUITY 2026-08-17: run ckpt_dup_delta.py as a real sbatch job
# instead of a bare login-node singularity call (that first attempt, run_ckpt_dup_delta.sh, hit
# the same ModuleNotFoundError for an unrelated reason -- no SLURM allocation at all outside
# srun; moot now, see below).
#
# ROOT CAUSE OF THE ModuleNotFoundError (confirmed via diag_venv_probe.sbatch, 2026-08-17):
# this script's own `export PYTHONPATH=${VENV}/lib/python3.12/site-packages` REPLACED PYTHONPATH
# outright instead of appending to it. The multitorch container ships its OWN /opt/venv with
# torch already on a baseline PYTHONPATH (confirmed: sys.path shows /opt/venv/lib/python3.12/
# site-packages present WITHOUT ever setting PYTHONPATH manually) -- the overlay venv relies on
# that system-site-packages inheritance for torch, it's not reinstalled into the venv's own
# site-packages. Overwriting PYTHONPATH dropped /opt/venv entirely, leaving only the (torch-less)
# overlay site-packages. FIX: append, don't replace --
# `export PYTHONPATH=${VENV}/lib/python3.12/site-packages${PYTHONPATH:+:${PYTHONPATH}}` (the
# exact form SKILL.md's shadow-venv note prescribes -- I quoted the rule in an earlier commit
# message but didn't actually write the append syntax; now fixed AND added as its own explicit
# SKILL.md bullet so it isn't just implied by the shadow-venv paragraph next time).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --job-name=sa3_ckpt_delta
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
RUN=${RUN:-${SCRATCH}/runs/fullft_mixed_avp_latents_sa3_t4096_wdfix}
# scoped to the one group that was actually rendered (epoch=7-step=15584, -v4 was the file
# render_matrix_cells.py picked) -- job 21243996/21244385 both timed out at 30min scanning
# every duplicate group in the run; one group is cheap, all ~8 groups apparently isn't.
ONLY_KEY=${ONLY_KEY:-epoch=7-step=15584}

[ -n "${SIF}" ] || { echo "[ckpt-delta] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[ckpt-delta] FATAL: ${VENV} missing"; exit 1; }

srun --nodes=1 --ntasks=1 --gpus=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH} "${SIF}" bash -c '
set -euo pipefail
CODE='"${CODE}"'
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages${PYTHONPATH:+:${PYTHONPATH}}
python3 ${CODE}/lumi/ckpt_dup_delta.py --run '"${RUN}"' --only-key '"${ONLY_KEY}"'
'
