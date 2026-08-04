#!/bin/bash
# lr_equiv_grid_mt.sbatch — LR × epoch × weight EQUIVALENCE GRID on the LUMI MULTITORCH
# image (ROCm 7 + gfx90a FA2). Multitorch migration of lr_equiv_grid.sbatch (CONTINUITY
# 2026-08-03) off sa3.sif (ROCm 6.2 MIOpen gfx90a find-fallback HANG). Arm 1 (lr1e-4) is the
# shared K=1 baseline for the whole melody-wall campaign (subspace / x0-equiv / combined).
# Diffs vs sa3.sif version: MTSIF + sa3_train_venv_mt overlay, PYTHONPATH append+first,
# no MIOPEN_FIND_MODE hack (ROCm7 has no hang), PYTORCH_TUNABLEOP_ENABLED=0. See lumi-ops
# "Containers". PREREQ: build_train_venv_mt.sh COMPAT GATE = PASS.
#
#SBATCH --account=project_465003186
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=3
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem-per-gpu=60G
#SBATCH --time=68:00:00
#SBATCH --job-name=sa3_lreq_mt
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
RUNROOT=${SCRATCH}/runs/lr_equiv_grid_mt
mkdir -p "${RUNROOT}" "${FLASH}"

[ -n "${SIF}" ] || { echo "[lreq-mt] FATAL: no lumi-multitorch-full under /appl/local/laifs/containers/ — pass MTSIF="; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[lreq-mt] FATAL: ${VENV} missing — run lumi/build_train_venv_mt.sh on uan18"; exit 1; }
grep -q -- "--resume_ckpt" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[lreq-mt] FATAL: train_lora.py missing --resume_ckpt (code refresh needed)"; exit 1; }

# goa latents to NVMe (idempotent)
if [ ! -d "${FLASH}/latents_sa3" ]; then
  mkdir -p "${FLASH}/latents_sa3"
  tar -xzf "${SCRATCH}/latents_sa3.tar.gz" -C "${FLASH}/latents_sa3" --strip-components=1
fi
echo "[lreq-mt] image=${SIF}"
echo "[lreq-mt] goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=3 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/lr_equiv_grid_mt
VENV='"${VENV}"'

source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
# APPEND container $PYTHONPATH (/opt/venv has torch+FA2); overlay+code FIRST so our pins win
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export PYTORCH_TUNABLEOP_ENABLED=0
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
# NO ROCR export: --gpus-per-task=1 cgroup pins (pattern A)

case ${ARM} in
  0) LR=2e-4; EPOCHS=14; CKEVERY=2 ;;
  1) LR=1e-4; EPOCHS=20; CKEVERY=4 ;;
  2) LR=5e-5; EPOCHS=40; CKEVERY=4 ;;
  *) exit 0 ;;
esac
LRTAG=$(echo ${LR} | tr -d ".-")
NAME=lreq_goa_lr${LRTAG}
RUN=${RUNROOT}/${NAME}
mkdir -p "${RUN}"

SIDECAR=${CODE}/lumi/goa_longform_sidecar.json
PROBS=0,0,1

cat > "${RUN}/run_meta.json" <<META
{
 "hypothesis": "LR x steps x inference-weight equivalence: magnitude invariant holds in param space (dW ~ LR, DONE); this arm supplies the DIRECTION-MATURITY curve (cos(dW@ep_k, dW@final)) + matched-cumulative perceptual points. All 3 arms end at cumulative LRxep = 2e-3. Container: lumi-multitorch-full ROCm7 FA2 (migrated off sa3.sif).",
 "arm_lr": "${LR}", "target_epochs": ${EPOCHS}, "ckpt_every": ${CKEVERY},
 "dataset": "goa (latents_sa3, full 5401)", "adapter": "dora-rows r128 a128",
 "optimizer": "adamw wd0.01", "precision": "bf16", "frames_T": 512, "batch_size": 4,
 "matched_points": "2e-4@ep10 == 1e-4@ep20 == 5e-5@ep40",
 "spec": "docs/superpowers/specs/2026-07-30-lr-steps-weight-equivalence-grid.md",
 "kim_feedback": null
}
META

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME_FLAG=""
[ -n "${FATCKPT}" ] && { echo "[arm ${ARM}] resuming from ${FATCKPT}"; RESUME_FLAG="--resume_ckpt ${FATCKPT}"; }

echo "[arm ${ARM}] TRAIN ${NAME}: lr=${LR} -> ${EPOCHS} ep (ckpt every ${CKEVERY}) ROCm7+FA2"
if python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/latents_sa3 \
    --save_dir "${RUN}" \
    --adapter_type dora-rows --rank 128 --lora_alpha 128 \
    --optimizer adamw \
    --base_precision bf16 \
    --lr ${LR} --batch_size 4 \
    --frames 512 --beat-aware-crop \
    ${RESUME_FLAG} \
    --epochs ${EPOCHS} --checkpoint_every_epochs ${CKEVERY} \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --caption_sidecar "${SIDECAR}" --caption_probs "${PROBS}" \
    --name ${NAME} 2>&1 | tee -a ${RUN}/train.log; then
  echo "[arm ${ARM}] TRAIN DONE — render tail (cfg7, weights 1/1.5/2/3, all saved ckpts)"
  SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
  ROUT=${SCRATCH}/renders/matrix_cells; mkdir -p "${ROUT}"
  for CK in $(ls ${RUN}/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V); do
    EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
    python ${CODE}/lumi/render_matrix_cells.py --label ${NAME} --tag ep${EP} \
      --ckpt "${CK}" --prompts ${SNAP} --out ${ROUT} \
      --only-cfgs 7 --strengths 1.0,1.5,2.0,3.0 \
      || echo "[arm ${ARM}] render ep${EP} failed (non-fatal)"
  done
else
  echo "[arm ${ARM}] TRAIN FAILED/TIMEOUT — re-submit to auto-resume (siblings unaffected)"
fi
'
echo "[lreq-mt] arms finished:"; ls -la "${RUNROOT}"/*/ 2>/dev/null | head -30
NCK=$(ls "${RUNROOT}"/*/epoch=*.ckpt 2>/dev/null | grep -cv weights || true)
echo "[lreq-mt] total fat ckpts across arms: ${NCK} (target: 7 + 5 + 10 = 22)"
# SUCCESS = per-arm ckpt counts + matched-point epochs present (idx 9/19/39). Never trust rc.
