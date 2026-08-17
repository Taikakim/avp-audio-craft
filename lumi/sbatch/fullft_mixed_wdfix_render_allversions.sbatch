#!/bin/bash
# fullft_mixed_wdfix_render_allversions.sbatch — CONTINUITY 2026-08-17 (Kim direct: "can we
# ... render the clips for all of them?"). ckpt_dup_delta.py confirmed epoch=7-step=15584's 5
# copies (base + -v1..-v4) genuinely diverged (521/522 tensors differ, max_abs_diff ~0.25-0.27)
# -- renders ALL 5 so Kim can actually hear the difference, not just the one -v4 that happened
# to sort last (fullft_mixed_wdfix_render.sbatch only rendered that one). Same label
# (fullft_mixed_wdfix_ddpbug) so they group together on the board, distinct tags (ep7v0..ep7v4)
# so they don't collide. One version per GPU, 5 GPUs used of the 8 available (parallel, fast).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=5
#SBATCH --ntasks-per-node=5
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --job-name=sa3_mixedwdfix_allver
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
RUN=${SCRATCH}/runs/fullft_mixed_avp_latents_sa3_t4096_wdfix
SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
ROUT=${SCRATCH}/renders/matrix_cells
LABEL=fullft_mixed_wdfix_ddpbug
KEY=${KEY:-epoch=7-step=15584}

[ -n "${SIF}" ] || { echo "[allver-render] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[allver-render] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[allver-render] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }
mkdir -p "${ROUT}"

mapfile -t CKPTS < <(ls "${RUN}/${KEY}.ckpt" "${RUN}/${KEY}-v"*.ckpt 2>/dev/null | sort -V)
[ "${#CKPTS[@]}" -gt 0 ] || { echo "[allver-render] FATAL: no ckpts matching ${KEY}* in ${RUN}"; exit 1; }
echo "[allver-render] ${#CKPTS[@]} version(s) of ${KEY}: ${CKPTS[*]}"

srun --nodes=1 --ntasks=${#CKPTS[@]} --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
VENV='"${VENV}"'; source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-av${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-av${ARM}
export TRITON_CACHE_DIR=/tmp/triton-av${ARM} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-av${ARM} /tmp/triton-av${ARM}; mkdir -p /tmp/miopen-av${ARM} /tmp/triton-av${ARM}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True

CKPTS=('"${CKPTS[*]}"')
CK=${CKPTS[${ARM}]}
VTAG=$(basename "${CK}" .ckpt | grep -oE -- "-v[0-9]+$" | tr -d "-" || echo "v0")
echo "[allver-render arm ${ARM}] ${VTAG} <- ${CK}"
python ${CODE}/lumi/render_matrix_cells.py \
    --label '"${LABEL}"' --tag ep7${VTAG} \
    --ckpt "${CK}" --fullft \
    --prompts '"${SNAP}"' --out '"${ROUT}"' \
    --only-cfgs 7 --strengths 1.0 \
  || echo "[allver-render arm ${ARM}] ${VTAG} render FAILED (non-fatal)"
'
echo "[allver-render] done. cells:"; ls "${ROUT}"/${LABEL}__ep7v* 2>/dev/null | wc -l
