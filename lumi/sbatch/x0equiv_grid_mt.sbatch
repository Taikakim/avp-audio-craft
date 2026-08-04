#!/bin/bash
# x0equiv_grid_mt.sbatch — E1a on the LUMI MULTITORCH image (ROCm 7 + gfx90a FA2).
# Multitorch migration of x0equiv_grid.sbatch (CONTINUITY 2026-08-02, Kim "let's try this
# with the multitorch image"). Moves off sa3.sif (ROCm 6.2) whose MIOpen gfx90a FindDb-gap
# → FAST-mode AI-fallback → first-backward HANG (see lumi-ops skill "Containers" + mode #5).
#
# DIFFS vs x0equiv_grid.sbatch:
#   - SIF  = lumi-multitorch-full (ROCm 7); VENV overlay = sa3_train_venv_mt (build_train_venv_mt.sh)
#   - PYTHONPATH prepends the venv site-packages FIRST (image /opt/venv shadows it otherwise)
#   - MIOPEN find-mode HACKS DROPPED (newer MIOpen has no gfx90a find-fallback hang) — no
#     FIND_MODE=1 / DISABLE_CACHE; keep only the /tmp redirects (home 100k-inode safety) + FA2
#   - flash-attn is present in the image → sa3 auto-uses FA2 (no flag; sa3 probes `import flash_attn`)
#
# PREREQ: run lumi/build_train_venv_mt.sh on uan18 and confirm its "COMPAT GATE: PASS" first.
# SMOKE (run FIRST): sbatch --export=ALL,SMOKE=1 lumi/sbatch/x0equiv_grid_mt.sbatch
#   -> EPOCHS=1, ckpt+render after 1 epoch: proves sa3 trains on ROCm-7 torch + the render path,
#      no MIOpen hang, before the 40h grid.
#
#SBATCH --account=project_465003186
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=2
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem-per-gpu=60G
#SBATCH --time=40:00:00
#SBATCH --job-name=sa3_x0eq_mt
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
# multitorch image (readable path; NOT the easybuild-sif-images symlinks) + train venv overlay
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
RUNROOT=${SCRATCH}/runs/x0equiv_grid_mt
mkdir -p "${RUNROOT}" "${FLASH}"

[ -n "${SIF}" ] || { echo "[x0eq-mt] FATAL: no lumi-multitorch-full under /appl/local/laifs/containers/ — pass MTSIF="; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[x0eq-mt] FATAL: ${VENV} missing — run lumi/build_train_venv_mt.sh on uan18"; exit 1; }
grep -q -- "--x0_equiv_loss" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[x0eq-mt] FATAL: train_lora.py missing --x0_equiv_loss (code refresh needed)"; exit 1; }
grep -q "x0_equiv_loss" "${CODE}/stable-audio-3/stable_audio_3/training/diffusion.py" \
  || { echo "[x0eq-mt] FATAL: training/diffusion.py missing x0 hook (code refresh needed)"; exit 1; }
grep -q "subspace_basis" "${CODE}/stable-audio-3/stable_audio_3/training/diffusion.py" \
  || { echo "[x0eq-mt] FATAL: training/diffusion.py missing subspace hook (code refresh needed)"; exit 1; }
[ -f "${CODE}/lumi/melody_subspace15_v2.npz" ] \
  || { echo "[x0eq-mt] FATAL: melody_subspace15_v2.npz not shipped"; exit 1; }

if [ ! -d "${FLASH}/latents_sa3" ]; then
  mkdir -p "${FLASH}/latents_sa3"
  tar -xzf "${SCRATCH}/latents_sa3.tar.gz" -C "${FLASH}/latents_sa3" --strip-components=1
fi
echo "[x0eq-mt] image=${SIF}"
echo "[x0eq-mt] goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=2 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/x0equiv_grid_mt
VENV='"${VENV}"'

source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
# APPEND to the container $PYTHONPATH (do NOT clobber — /opt/venv there holds torch+flash-attn).
# Overlay + code dirs FIRST so our pins win; container /opt/venv stays on path (caption-run lesson).
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
# multitorch image enables TunableOp by default + points it at a bogus /home/kim csv (spams
# "could not open ... realtime append failed", adds per-GEMM search cost). We use FA2/CK — off.
export PYTORCH_TUNABLEOP_ENABLED=0
# home-inode safety (NOT the 6.2 MIOpen find-mode hack — ROCm 7 MIOpen has no gfx90a find-fallback hang)
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
# NO ROCR export: --gpus-per-task=1 cgroup pins (pattern A)

EPOCHS=20; CKEVERY=4
if [ "'"${SMOKE:-0}"'" = "1" ]; then EPOCHS=1; CKEVERY=1; echo "[arm ${ARM}] SMOKE: 1 epoch"; fi

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
 "hypothesis": "E1a JLT port on MULTITORCH (ROCm7+FA2): sigma^2-weighted v-loss (== x0-space MSE for a v-output head) removes the isotropic floor swamping the 188/256 sub-unit eigendirections. Arm 1 adds subspace-K5. Baseline = lreq_goa_lr1e4. Container migrated off sa3.sif (6.2 MIOpen hang).",
 "arm": "${NAME}", "dataset": "goa (latents_sa3, full 5401)", "adapter": "dora-rows r128 a128",
 "optimizer": "adamw wd0.01", "precision": "bf16", "frames_T": 512, "batch_size": 4,
 "lr": "1e-4", "epochs": ${EPOCHS}, "ckpt_every": ${CKEVERY}, "container": "lumi-multitorch-full ROCm7 FA2",
 "baseline": "runs/lr_equiv_grid/lreq_goa_lr1e4 (K=1, byte-identical recipe on sa3.sif — watch for container-shift)",
 "kim_feedback": null
}
META

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME_FLAG=""
[ -n "${FATCKPT}" ] && { echo "[arm ${ARM}] resuming from ${FATCKPT}"; RESUME_FLAG="--resume_ckpt ${FATCKPT}"; }

echo "[arm ${ARM}] TRAIN ${NAME}: ${EXTRA} lr 1e-4 -> ${EPOCHS} ep (ROCm7+FA2)"
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
echo "[x0eq-mt] arms finished:"; ls -la "${RUNROOT}"/*/ 2>/dev/null | head -20
NCK=$(ls "${RUNROOT}"/*/epoch=*.ckpt 2>/dev/null | grep -cv weights || true)
echo "[x0eq-mt] total fat ckpts across arms: ${NCK}"
# SUCCESS = ckpt counts + train_loss present in each arm's csv logs. Never trust rc.
