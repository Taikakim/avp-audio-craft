#!/bin/bash
# dronesweep_render.sbatch — CONTINUITY 2026-08-13: audition the AVP drone-recipe sweep
# (fullft_avp_dronesweep, job 21063704). Renders the NEWEST fat ckpt of each arm dir under
# $SCRATCH/runs/avp_dronesweep/<recipe>_s<seed>/ with a per-arm label (dronesweep_<arm>) so the 4
# recipes x 2 seeds land side-by-side on the board = the deliverable-1 "gate the winner on ears"
# comparison. EMA-trained fullft -> --use-ema --fullft. FORCE=1 re-renders over existing clips.
#
# The drone sweep is PRE-ENCODED (--encoded_dir latents_avp) -> NO gain-clip bug (that's the big-goa
# live-encode --augment path only). These ckpts are clean.
#
# RUN:  [ARMS='plain_s1 force_scalar_s1'] [NLAST=1] [FORCE=1] sbatch lumi/sbatch/dronesweep_render.sbatch
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=03:00:00
#SBATCH --job-name=dronesweep_render
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code; MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
SWEEP=${SCRATCH}/runs/avp_dronesweep
SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
ROUT=${SCRATCH}/renders/matrix_cells
CFGS=${CFGS:-1,7,16}
NLAST=${NLAST:-1}
FORCE=${FORCE:-}
# default = all 8 arms; override ARMS to render a subset
ARMS=${ARMS:-$(ls -d "${SWEEP}"/*/ 2>/dev/null | xargs -n1 basename | tr '\n' ' ')}

[ -n "${SIF}" ] || { echo "[ds-render] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[ds-render] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[ds-render] FATAL: prompt snapshot missing"; exit 1; }
[ -d "${SWEEP}" ] || { echo "[ds-render] FATAL: ${SWEEP} missing (no drone sweep run dir)"; exit 1; }
[ -n "${ARMS// }" ] || { echo "[ds-render] FATAL: no arm dirs under ${SWEEP}"; exit 1; }
mkdir -p "${ROUT}"
echo "[ds-render] arms: ${ARMS}"

# one GCD-pinned task per arm (8 arms -> 8 GCDs), each renders its arm's newest ckpt
read -r -a ARM_ARR <<< "${ARMS}"
srun --overlap --cpu-bind=none --mpi=none --nodes=1 --ntasks=8 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM_IDX=${SLURM_PROCID}
ARMS_STR="'"${ARMS}"'"; read -r -a A <<< "${ARMS_STR}"
ARM="${A[${ARM_IDX}]:-}"
[ -n "${ARM}" ] || { echo "[ds-render] task ${ARM_IDX}: no arm assigned, idle"; exit 0; }
export ROCR_VISIBLE_DEVICES=${ARM_IDX}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
SWEEP=${SCRATCH}/runs/avp_dronesweep
VENV='"${VENV}"'; source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM_IDX} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM_IDX}
export TRITON_CACHE_DIR=/tmp/triton-${ARM_IDX} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-${ARM_IDX} /tmp/triton-${ARM_IDX}; mkdir -p /tmp/miopen-${ARM_IDX} /tmp/triton-${ARM_IDX}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
mapfile -t CKPTS < <(ls "${SWEEP}/${ARM}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -n '"${NLAST}"')
[ "${#CKPTS[@]}" -gt 0 ] || { echo "[ds-render] ${ARM}: no fat ckpt, skip (arm ${ARM_IDX} ROCR ${ROCR_VISIBLE_DEVICES})"; exit 0; }
for CK in "${CKPTS[@]}"; do
  EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
  echo "[ds-render] ${ARM} ep${EP} (EMA) ROCR=${ROCR_VISIBLE_DEVICES} <- ${CK}"
  python ${CODE}/lumi/render_matrix_cells.py \
      --label dronesweep_${ARM} --tag ep${EP} \
      --ckpt "${CK}" --fullft --use-ema '"${FORCE:+--force}"' \
      --prompts '"${SNAP}"' --out '"${ROUT}"' \
      --only-cfgs '"${CFGS}"' --strengths 1.0 \
    || echo "[ds-render] ${ARM} ep${EP} render FAILED (non-fatal)"
done
'
set +e
echo "[ds-render] done. cells per arm:"
for ARM in ${ARMS}; do echo "  ${ARM}: $(ls "${ROUT}"/dronesweep_${ARM}__* 2>/dev/null | wc -l)"; done
