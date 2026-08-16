#!/bin/bash
# fullft_mixed_wdfix_render.sbatch — CONTINUITY 2026-08-17: render job 21161065's finished run
# (fullft_mixed_avp_goa_t4096.sbatch, RUNTAG=wdfix, RUN=fullft_mixed_avp_latents_sa3_t4096_wdfix).
# All 8 epochs completed (log: "Epoch 7/7"), BUT this run shipped WITHOUT --devices -> its 8 srun
# ranks were 8 UNCOORDINATED single-GPU trainers writing to the same checkpoint names, not one
# real DDP job (see train_lora.py --devices help text, precedent job 20413874; confirmed via the
# -v1..-v4 duplicate ckpts, being cross-checked by ckpt_dup_delta.py/job 21243996). So whichever
# epoch=7-*.ckpt currently sorts last (highest -vN) is an ARBITRARY pick among up to 8
# independently-diverged trajectories, not a deliberate result -- render it anyway to have
# something to listen to, label clearly flags the provenance caveat. NOT --use-ema (this run
# never passed --use-ema, unlike the continue8 fullft arms).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --job-name=sa3_mixedwdfix_render
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
LABEL=fullft_mixed_wdfix_ddpbug   # flagged in the name -- uncertain provenance, see header
NLAST=${NLAST:-1}

[ -n "${SIF}" ] || { echo "[mixedwdfix-render] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[mixedwdfix-render] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[mixedwdfix-render] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }
mapfile -t CKPTS < <(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -n "${NLAST}")
[ "${#CKPTS[@]}" -gt 0 ] || { echo "[mixedwdfix-render] FATAL: no fat ckpt in ${RUN}"; exit 1; }
mkdir -p "${ROUT}"
echo "[mixedwdfix-render] rendering ${#CKPTS[@]} ckpt(s) as label=${LABEL}: ${CKPTS[*]}"

srun --exclusive -N1 -n1 --gpus=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
source '"${VENV}"'/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-mwr MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-mwr
export TRITON_CACHE_DIR=/tmp/triton-mwr PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-mwr /tmp/triton-mwr; mkdir -p /tmp/miopen-mwr /tmp/triton-mwr
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
for CK in '"${CKPTS[*]}"'; do
  EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
  echo "[mixedwdfix-render] ep${EP} <- ${CK}"
  python ${CODE}/lumi/render_matrix_cells.py \
      --label '"${LABEL}"' --tag ep${EP} \
      --ckpt "${CK}" --fullft \
      --prompts '"${SNAP}"' --out '"${ROUT}"' \
      --only-cfgs 7 --strengths 1.0 \
    || echo "[mixedwdfix-render] ep${EP} render FAILED (non-fatal)"
done
'
echo "[mixedwdfix-render] done. cells:"; ls "${ROUT}"/${LABEL}__* 2>/dev/null | wc -l
