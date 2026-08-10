#!/bin/bash
# melody_wall_v3sel.sbatch — whitened-chroma melody-recurrence A/B for the v3sel A/B
# (CONTINUITY 2026-08-07). Runs eval/melody_wall_analysis.py ON LUMI over the cells already in
# scratch renders/matrix_cells (no cell pull needed), comparing:
#   ARMS   = subloss_v3sel_k{2,5,12}  (NEW melody-SELECTIVE subspace, held-out SNR 5.1x)
#          + subloss_goa_k{2,5,12}    (OLD melody-VARIANCE subspace, the weak #59, SNR 1.0x)
#   BASELINE = lreq_goa_lr1e4         (K=1, subspace-loss OFF)
# Q: does the selective subspace lift within-clip melodic recurrence MORE than the variance one?
#
# NB the v2 subloss_goa_* + lreq cells were rendered 08-04 — if scratch was cleaned they may be
# GONE (only v3sel is fresh). The job PRINTS per-arm cell counts first; if v2/lreq show ~0, the
# comparison can't run on LUMI — pull the fresh v3sel cells local and run melody_wall_analysis.py
# there instead (defaults + mir venv have all arms). Output is tiny (VERDICT.md + summary.json).
#
#SBATCH --account=project_465003186
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem-per-gpu=60G
#SBATCH --time=03:00:00
#SBATCH --job-name=sa3_melodywall_v3sel
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
CELLS=${SCRATCH}/renders/matrix_cells
OUTDIR=${SCRATCH}/analysis/melody_wall_v3sel
BASELINE=lreq_goa_lr1e4
ARMS=subloss_v3sel_k2,subloss_v3sel_k5,subloss_v3sel_k12,subloss_goa_k2,subloss_goa_k5,subloss_goa_k12

[ -n "${SIF}" ] || { echo "[mw] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[mw] FATAL: ${VENV} missing"; exit 1; }
mkdir -p "${OUTDIR}"

echo "[mw] per-arm cell counts in ${CELLS}:"
for lbl in ${BASELINE} ${ARMS//,/ }; do
  n=$(ls "${CELLS}/${lbl}__"*.wav 2>/dev/null | wc -l)
  printf "  %-22s %s\n" "${lbl}" "${n}"
done

srun --exclusive -N1 -n1 --gpus=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
CODE=/project/project_465003186/code
source '"${VENV}"'/bin/activate
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
python -c "import librosa, soundfile, numpy" 2>/dev/null \
  || { echo "[mw] FATAL: librosa/soundfile not in the venv — pip install librosa soundfile on uan18 into '"${VENV}"' then resubmit"; exit 3; }
export MW_RENDERS='"${CELLS}"' MW_OUTDIR='"${OUTDIR}"' MW_BASELINE='"${BASELINE}"' MW_ARMS='"${ARMS}"'
python ${CODE}/eval/melody_wall_analysis.py
'
echo "[mw] done -> ${OUTDIR}/{VERDICT.md,summary.json,per_clip.jsonl}"
head -40 "${OUTDIR}/VERDICT.md" 2>/dev/null || true
