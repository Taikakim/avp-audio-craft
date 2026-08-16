#!/bin/bash
# diag_venv_probe.sbatch — CONTINUITY 2026-08-17: ckpt_dup_delta.sbatch failed twice with
# ModuleNotFoundError: No module named 'torch' -- once on the bare login node (expected, no
# container), but ALSO once inside the exact srun+singularity pattern every other script this
# session has used successfully (render jobs included). Rather than guess a third time, print
# every layer: which SIF/VENV resolved, whether the venv's own python3 exists, sys.executable/
# sys.path as actually seen inside the container, and whether torch import works from the venv's
# OWN interpreter directly (bypassing `source activate` + bare `python3` entirely) vs the
# activated-PATH route. This isolates whether the bug is in SIF/VENV resolution, in `source
# activate` not doing what we think, or in something else entirely.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=00:10:00
#SBATCH --job-name=sa3_venv_probe
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
echo "[probe] SIF=${SIF}"
echo "[probe] VENV=${VENV}"
ls -la "${VENV}/bin/python"* 2>&1 || echo "[probe] no python* in ${VENV}/bin"

srun --nodes=1 --ntasks=1 --gpus=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
echo "[in-container] whoami=$(whoami) hostname=$(hostname)"
echo "[in-container] which python3 (before activate) = $(which python3 2>&1)"
echo "[in-container] ls '"${VENV}"'/bin/python* :"
ls -la '"${VENV}"'/bin/python* 2>&1
source '"${VENV}"'/bin/activate
echo "[in-container] which python3 (after activate) = $(which python3 2>&1)"
echo "[in-container] sys.executable / sys.path:"
python3 -c "import sys; print(sys.executable); [print(p) for p in sys.path]"
echo "[in-container] direct venv interpreter torch import:"
'"${VENV}"'/bin/python3 -c "import torch; print(torch.__version__)" 2>&1
echo "[in-container] activated bare python3 torch import:"
python3 -c "import torch; print(torch.__version__)" 2>&1
'
