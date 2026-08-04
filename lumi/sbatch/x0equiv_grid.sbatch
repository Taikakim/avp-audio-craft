#!/bin/bash
# x0equiv_grid.sbatch — E1a: x0-EQUIVALENT LOSS arms (CONTINUITY 2026-07-31, Kim
# "go on with the tests"). JLT port (arXiv 2605.27102): sigma^2-weighted v-loss ==
# x0-space MSE for a v-output head — removes the isotropic covariance floor that swamps
# low-variance eigendirections. PRE-TEST MEASURED the mechanism live: the v-trained base
# recovers low-lambda eigendirections 2-8x worse per unit signal (worst at sigma 0.2).
#
# ARMS (single-GCD, small-g):
#   0: --x0-equiv-loss alone            (the parameterization lever solo)
#   1: --x0-equiv-loss + subspace K=5   (combined: rebalance-all x upweight-melody)
# RECIPE = lreq_goa_lr1e4 EXACTLY => shared baseline with the lr-equiv + subloss grids;
# the three melody-wall attacks (subspace / x0 / combined) compare on one axis system.
#
# READOUT (post-pull): board cells + hook-decile contour repetition + per-eigendirection
# ERROR SPECTRUM of the trained model (rerun eval/e1_pretest_error_spectrum.py against
# the arm ckpt — does the sub-floor region's relative error actually drop vs base?).
#
# PREREQ: code refresh must carry BOTH new flags (train_lora.py + training/diffusion.py,
# 2026-07-31) + lumi/melody_subspace15_v2.npz — fail-loud checks below.
#
#SBATCH --account=project_465003186
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=2
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem-per-gpu=60G
#SBATCH --time=40:00:00
#SBATCH --job-name=sa3_x0eq
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/x0equiv_grid
mkdir -p "${RUNROOT}" "${FLASH}"

grep -q -- "--x0_equiv_loss" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[x0eq] FATAL: train_lora.py missing --x0_equiv_loss (code refresh needed)"; exit 1; }
grep -q "x0_equiv_loss" "${CODE}/stable-audio-3/stable_audio_3/training/diffusion.py" \
  || { echo "[x0eq] FATAL: training/diffusion.py missing x0 hook (code refresh needed)"; exit 1; }
grep -q "subspace_basis" "${CODE}/stable-audio-3/stable_audio_3/training/diffusion.py" \
  || { echo "[subloss] FATAL: training/diffusion.py missing subspace hook (code refresh needed)"; exit 1; }
[ -f "${CODE}/lumi/melody_subspace15_v2.npz" ] \
  || { echo "[subloss] FATAL: melody_subspace15_v2.npz not shipped"; exit 1; }

if [ ! -d "${FLASH}/latents_sa3" ]; then
  mkdir -p "${FLASH}/latents_sa3"
  tar -xzf "${SCRATCH}/latents_sa3.tar.gz" -C "${FLASH}/latents_sa3" --strip-components=1
fi
echo "[subloss] goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=2 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/x0equiv_grid

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=1 PYTORCH_TUNABLEOP_ENABLED=0
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
# NO ROCR export: --gpus-per-task=1 cgroup pins (pattern A)

case ${ARM} in
  0) EXTRA="--x0-equiv-loss";                                              NAME=x0eq_goa ;;
  1) EXTRA="--x0-equiv-loss --subspace-loss-basis ${CODE}/lumi/melody_subspace15_v2.npz --subspace-loss-weight 5"; NAME=x0eq_sub5_goa ;;
  *) exit 0 ;;
esac
RUN=${RUNROOT}/${NAME}
mkdir -p "${RUN}"

SIDECAR=${CODE}/lumi/goa_longform_sidecar.json
PROBS=0,0,1

cat > "${RUN}/run_meta.json" <<META
{
 "hypothesis": "E1a JLT port (arXiv 2605.27102): sigma^2-weighted v-loss (== x0-space MSE for a v-output head) removes the isotropic floor that swamps the 188/256 sub-unit eigendirections (pre-test: base recovers them 2-8x worse per unit signal, worst at low sigma). Arm 1 combines with subspace-K5 (rebalance-all x upweight-melody). Baseline = lreq_goa_lr1e4.",
 "arm": "${NAME}", "dataset": "goa (latents_sa3, full 5401)", "adapter": "dora-rows r128 a128",
 "optimizer": "adamw wd0.01", "precision": "bf16", "frames_T": 512, "batch_size": 4,
 "lr": "1e-4", "epochs": 20, "ckpt_every": 4,
 "baseline": "runs/lr_equiv_grid/lreq_goa_lr1e4 (K=1, byte-identical recipe)",
 "kim_feedback": null
}
META

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME_FLAG=""
[ -n "${FATCKPT}" ] && { echo "[arm ${ARM}] resuming from ${FATCKPT}"; RESUME_FLAG="--resume_ckpt ${FATCKPT}"; }

echo "[arm ${ARM}] TRAIN ${NAME}: ${EXTRA} lr 1e-4 -> 20 ep"
if python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/latents_sa3 \
    --save_dir "${RUN}" \
    --adapter_type dora-rows --rank 128 --lora_alpha 128 \
    --optimizer adamw \
    --base_precision bf16 \
    --lr 1e-4 --batch_size 4 \
    --frames 512 --beat-aware-crop \
    ${EXTRA} \
    ${RESUME_FLAG} \
    --epochs 20 --checkpoint_every_epochs 4 \
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
echo "[subloss] arms finished:"; ls -la "${RUNROOT}"/*/ 2>/dev/null | head -20
NCK=$(ls "${RUNROOT}"/*/epoch=*.ckpt 2>/dev/null | grep -cv weights || true)
echo "[subloss] total fat ckpts across arms: ${NCK} (target: 3 arms x 5 = 15)"
# SUCCESS = ckpt counts + train/subspace_loss present in each arm's csv logs. Never trust rc.
