#!/bin/bash
# subloss_tgate_modes.sbatch — R2(t)-GATE MODE A/B + seed pairs (burn-day, Kim 2026-08-21)
# (CONTINUITY 2026-08-06). Identical to subspace_loss_grid_mt.sbatch EXCEPT the subspace basis:
# melody_subspace15_selective_v3.npz instead of _v2. This is the A/B that Kim's melody
# machinery-audit motivated. The v2 basis (top-15 melody VARIANCE) had ~ZERO melody-vs-codec-noise
# selectivity on held-out data (SNR 1.0x) — so upweighting it boosts codec hiss as much as melody,
# the probable reason #59 came back weak. v3 (whitened CSP: signal=atlas interval deltas, noise=
# real codec deltas+timbre) is 5.1x melody-over-codec-noise on held-out. See
# eval/musicology/melody_selective_subspace_2026-08-06/VERDICT.md.
#
# ARMS (single-GCD, small-g): K in {2, 5, 12} — matched to the v2 grid so v3 arms compare
# directly against the already-run subloss_goa_k{2,5,12} (v2) + the shared lreq_goa_lr1e4 (K=1)
# baseline. RECIPE = lreq_goa_lr1e4 EXACTLY (nothing but the basis differs from the v2 grid).
# Diffs vs sa3.sif version: MTSIF + sa3_train_venv_mt overlay, PYTHONPATH append+first, no
# MIOPEN_FIND_MODE hack, PYTORCH_TUNABLEOP_ENABLED=0. PREREQ: build_train_venv_mt.sh GATE=PASS.
#
#SBATCH --account=project_465003186
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=4
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem-per-gpu=60G
#SBATCH --time=40:00:00
#SBATCH --job-name=subloss_tgate_modes
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
RUNROOT=${SCRATCH}/runs/subloss_tgate_modes
mkdir -p "${RUNROOT}" "${FLASH}"

[ -n "${SIF}" ] || { echo "[subloss-mt] FATAL: no lumi-multitorch-full under /appl/local/laifs/containers/ — pass MTSIF="; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[subloss-mt] FATAL: ${VENV} missing — run lumi/build_train_venv_mt.sh on uan18"; exit 1; }
grep -q -- "--subspace_loss_basis" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[subloss-mt] FATAL: train_lora.py missing --subspace_loss_basis (code refresh needed)"; exit 1; }
# arm 3 (added 2026-08-19): the R²(t)-GATED subspace term needs the tgate flag + module + measurement tool
grep -q -- "subspace_loss_tgate" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[subloss-mt] FATAL: train_lora.py missing --subspace-loss-tgate (rsync stable-audio-3 + eval/melody_r2_vs_t.py)"; exit 1; }
[ -f "${CODE}/stable-audio-3/stable_audio_3/training/tgate.py" ] || { echo "[subloss-mt] FATAL: tgate.py missing"; exit 1; }
[ -f "${CODE}/eval/melody_r2_vs_t.py" ] || { echo "[subloss-mt] FATAL: eval/melody_r2_vs_t.py missing"; exit 1; }
grep -q "subspace_basis" "${CODE}/stable-audio-3/stable_audio_3/training/diffusion.py" \
  || { echo "[subloss-mt] FATAL: training/diffusion.py missing subspace hook (code refresh needed)"; exit 1; }
[ -f "${CODE}/lumi/melody_subspace15_selective_v3.npz" ] \
  || { echo "[subloss-mt] FATAL: melody_subspace15_selective_v3.npz not shipped"; exit 1; }

if [ ! -d "${FLASH}/latents_sa3" ]; then
  mkdir -p "${FLASH}/latents_sa3"
  tar -xzf "${SCRATCH}/latents_sa3.tar.gz" -C "${FLASH}/latents_sa3" --strip-components=1
fi
echo "[subloss-mt] image=${SIF}"
echo "[subloss-mt] goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=4 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/subloss_tgate_modes
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

TGATE_ARGS=""
SEED=1
GMODE=r2
case ${ARM} in
  0) K=5; TGATE=1; GMODE=deficit; SEED=1 ;;   # the UNTESTED gate direction (B2 readout: r2 lost to flat)
  1) K=5; TGATE=1; GMODE=deficit; SEED=2 ;;
  2) K=5; TGATE=1; GMODE=r2;      SEED=2 ;;   # seed pair for the existing r2 arm
  3) K=5;                          SEED=2 ;;   # seed pair for the flat-K5 winner
  *) exit 0 ;;
esac
NAME=subloss_v3sel_k${K}_s${SEED}
if [ "${TGATE:-0}" = "1" ]; then
  NAME=subloss_v3sel_k${K}_tgate_${GMODE}_s${SEED}
  # Gate source: the measured R²(t) curve of the melody subspace under medium-base. Use the
  # committed reference if the code tree carries it; otherwise MEASURE IT HERE on this GCD first
  # (~5 min, 48 crops x 19 t) so the arm is self-contained. Mode r2 = weight where melody is
  # recoverable; the json also carries r2_rest and deficit for later modes.
  GATE=${CODE}/lumi/melody_r2_vs_t_medium-base.json
  if [ ! -f "${GATE}" ]; then
    GATE=${RUNROOT}/${NAME}/melody_r2_vs_t_medium-base.json
    mkdir -p "${RUNROOT}/${NAME}"
    [ -f "${GATE}" ] || python ${CODE}/eval/melody_r2_vs_t.py --latents ${FLASH}/latents_sa3 \
        --basis ${CODE}/lumi/melody_subspace15_selective_v3.npz --n-crops 48 --frames 1024 \
        --out "${GATE}" 2>&1 | tee ${RUNROOT}/${NAME}/r2_measure.log
  fi
  [ -f "${GATE}" ] || { echo "[arm ${ARM}] FATAL: no gate file"; exit 1; }
  TGATE_ARGS="--subspace-loss-tgate ${GATE} --subspace-loss-tgate-mode ${GMODE} --subspace-loss-tgate-floor 0.05"
  echo "[arm ${ARM}] t-gate: ${GATE}"
fi
RUN=${RUNROOT}/${NAME}
mkdir -p "${RUN}"

SIDECAR=${CODE}/lumi/goa_longform_sidecar.json
PROBS=0,0,1
BASIS=${CODE}/lumi/melody_subspace15_selective_v3.npz

cat > "${RUN}/run_meta.json" <<META
{
 "hypothesis": "Melody-SELECTIVE subspace A/B (C 2026-08-06). Same as the v2 subloss grid but the upweighted 15-dim subspace is now melody-SELECTIVE (whitened CSP: signal=atlas interval deltas, noise=real codec deltas+timbre) instead of top-15 melody-variance. The v2 basis had ~zero melody-vs-codec-noise selectivity on held-out data (SNR 1.0x) so upweighting it boosted codec hiss as much as melody (probable cause of the weak #59); v3 is 5.1x melody-over-codec-noise held-out. Prediction: v3 arms show more within-clip contour repetition (hook axis) at matched/cleaner texture than the v2 subloss_goa_k arms and the lreq K=1 baseline. Container: lumi-multitorch-full ROCm7 FA2.",
 "arm_K": ${K}, "subspace": "melody_subspace15_selective_v3.npz (whitened-CSP melody-selective, 15-dim, held-out SNR 5.1x; A/B vs subloss_goa_k${K} on v2 + lreq K=1)",
 "dataset": "goa (latents_sa3, full 5401)", "adapter": "dora-rows r128 a128",
 "optimizer": "adamw wd0.01", "precision": "bf16", "frames_T": 512, "batch_size": 4, "tgate": "${TGATE_ARGS:-none}",
 "lr": "1e-4", "epochs": 20, "ckpt_every": 4,
 "baseline": "runs/lr_equiv_grid_mt/lreq_goa_lr1e4 (K=1, byte-identical recipe)",
 "kim_feedback": null
}
META

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME_FLAG=""
[ -n "${FATCKPT}" ] && { echo "[arm ${ARM}] resuming from ${FATCKPT}"; RESUME_FLAG="--resume_ckpt ${FATCKPT}"; }

echo "[arm ${ARM}] TRAIN ${NAME}: K=${K}, lr 1e-4 -> 20 ep ROCm7+FA2"
if python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/latents_sa3 \
    --save_dir "${RUN}" \
    --adapter_type dora-rows --rank 128 --lora_alpha 128 \
    --optimizer adamw \
    --base_precision bf16 \
    --lr 1e-4 --batch_size 4 \
    --frames 512 --beat-aware-crop \
    --subspace-loss-basis ${BASIS} --subspace-loss-weight ${K} ${TGATE_ARGS} \
    ${RESUME_FLAG} \
    --epochs 20 --checkpoint_every_epochs 4 \
    --num_workers 6 --seed ${SEED} --no_demos --logger csv \
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
echo "[subloss-mt] arms finished:"; ls -la "${RUNROOT}"/*/ 2>/dev/null | head -20
NCK=$(ls "${RUNROOT}"/*/epoch=*.ckpt 2>/dev/null | grep -cv weights || true)
echo "[subloss-mt] total fat ckpts across arms: ${NCK} (target: 3 arms x 5 = 15)"
# SUCCESS = ckpt counts + train/subspace_loss present in each arm's csv logs. Never trust rc.
