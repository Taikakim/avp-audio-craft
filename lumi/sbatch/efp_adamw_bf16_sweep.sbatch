#!/bin/bash
# efp_adamw_bf16_sweep.sbatch — AdamW / bf16 lr×batch sweep (Kim direct, 2026-07-24,
# prompted by Zach@StabilityAI: "worth an A/B with AdamW"). The AdamW counterpart to the
# FusionOpt runs — SAME adapter recipe (dora-rows r128/a128, T=512 beat-aware crops,
# medium-base), only the OPTIMIZER changes (fusion→adamw) and precision is bf16.
# One standard-g node, 8 GCDs, 8 single-GCD arms driven by SLURM_PROCID.
#
# WHY (Kim: "just test AdamW vs Fusion"): (1) is AdamW competitive with FusionOpt on the
# DoRA control recipe, and does it "drag less dataset sound" (Kim's obs — AdamW more benign,
# Fusion denser/more memorization)? (2) an AdamW lr sweep {½×,1×,2×} of the 1e-4 working
# point, both datasets, to find the AdamW operating lr. T=512 (compromise: long-T's universal
# benefit is unproven). The Fusion side of the A/B at T512/bf16 = the existing bf16_twin run
# (Fusion bf16 T512 bs8 lr1e-4); the nearest AdamW arm here is arm 0/1 (bs4 lr1e-4).
#
# ARMS (all: dora-rows r128 a128, T=512 beat-aware, AdamW wd=0.01 betas[0.9,0.95], bf16, 10 ep):
#   0: avp  bs4  lr 1e-4     (working point, avp)          4: avp  bs4  lr 2e-4   (2×, avp)
#   1: goa  bs4  lr 1e-4     (working point, goa)          5: goa  bs4  lr 2e-4   (2×, goa)
#   2: avp  bs1  lr 1e-4     (batch-1, avp)                6: avp  bs4  lr 5e-5   (½×, avp)
#   3: goa  bs1  lr 1e-4     (batch-1, goa)                7: goa  bs4  lr 5e-5   (½×, goa)
#   => 4× avp + 4× goa. lr sweep {5e-5,1e-4,2e-4} at bs4 + a bs1 point at 1e-4.
#
# MEMORY: T=512 bf16 is cheap (≈47.6 s crops) — bs4/bs1 fit trivially on 64 GB/GCD. No probe.
# bf16 uses NATIVE attention — no fp32 SDPA probe / SA3_SDPA_CAST_BF16 island needed.
#
# PREREQ: latents_avp.tar.gz + latents_sa3.tar.gz + SIF + models + code already on ${SCRATCH}
# (the fp32_compare/winning campaigns staged them). Code just needs train_lora.py present —
# adamw is the DEFAULT optimizer, no special patch required. Plan: chat 2026-07-24.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=47:00:00
#SBATCH --job-name=sa3_adamw_bf16_sweep
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/adamw_bf16_sweep
mkdir -p "${RUNROOT}" "${FLASH}"

# ── stage both datasets to NVMe once (idempotent) ──
for DS in latents_avp latents_sa3; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[adamw] avp latents: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/adamw_bf16_sweep

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor
# MIOPEN_DISABLE_CACHE=1: the MIOpen kernel-cache SQLite open fails on LUMI (proven smoke run
# 2026-07-16); kernels recompile per run. NOTE: single-quoted bash -c below -- no apostrophes/backticks.
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
rm -rf "${MIOPEN_USER_DB_PATH}"; mkdir -p "${MIOPEN_USER_DB_PATH}"

# ── arm table: DS BS LR ──
case ${ARM} in
  0) DS=latents_avp; BS=4; LR=1e-4 ;;
  1) DS=latents_sa3; BS=4; LR=1e-4 ;;
  2) DS=latents_avp; BS=1; LR=1e-4 ;;
  3) DS=latents_sa3; BS=1; LR=1e-4 ;;
  4) DS=latents_avp; BS=4; LR=2e-4 ;;
  5) DS=latents_sa3; BS=4; LR=2e-4 ;;
  6) DS=latents_avp; BS=4; LR=5e-5 ;;
  7) DS=latents_sa3; BS=4; LR=5e-5 ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
T=512
DSTAG=$([ "${DS}" = latents_avp ] && echo avp || echo goa)
LRTAG=$(echo ${LR} | tr -d ".-")
NAME=adamw_${DSTAG}_t${T}_bs${BS}_lr${LRTAG}
RUN=${RUNROOT}/${NAME}
mkdir -p "${RUN}"

# longform sidecar default (CAPTIONS=stored to disable; SIDECAR/PROBS override)
if [ "${CAPTIONS:-longform}" = "longform" ] && [ -z "${SIDECAR:-}" ]; then
  SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json
  PROBS=${PROBS:-0,0,1}
fi

# ── MANIFEST v2 provenance sidecar (write at creation, before training) ──
cat > "${RUN}/run_meta.json" <<META
{
 "hypothesis": "AdamW-vs-FusionOpt A/B on the DoRA control recipe (Zach@StabilityAI suggested it): is AdamW competitive, and does it drag less dataset sound than Fusion? Plus an AdamW lr sweep {5e-5,1e-4,2e-4} at bs4 to find the AdamW operating lr.",
 "arm": ${ARM}, "dataset": "${DSTAG}", "frames_T": ${T}, "beat_aware_crop": true, "batch_size": ${BS},
 "optimizer": "adamw", "adamw": "wd=0.01 betas[0.9,0.95]", "lr": "${LR}",
 "precision": "bf16", "adapter": "dora-rows r128 a128", "model": "medium-base", "epochs": 10,
 "compare_against": "runs/fp32_compare (FusionOpt fp32, same ds/bs/T arms)",
 "purpose_paths": {"sbatch": "code/lumi/sbatch/efp_adamw_bf16_sweep.sbatch", "plan": "chat 2026-07-24"}
}
META

train() {
  local sc_args=()
  if [ -n "${SIDECAR:-}" ]; then sc_args=(--caption_sidecar "${SIDECAR}" --caption_probs "${PROBS:-0.6,0.3,0.1}"); fi
  python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/${DS} \
    --save_dir "${RUN}" \
    --adapter_type dora-rows --rank 128 --lora_alpha 128 \
    --optimizer adamw \
    --base_precision bf16 \
    --lr ${LR} --batch_size ${BS} \
    --frames ${T} --beat-aware-crop \
    --epochs 10 --checkpoint_every_epochs 1 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name ${NAME} "${sc_args[@]}"
}

echo "[arm ${ARM}] TRAIN ${DSTAG} T=${T} BS=${BS} lr=${LR} adamw bf16 -> ${RUN}"
if train 2>&1 | tee ${RUN}/train.log; then
  echo "[arm ${ARM}] TRAIN DONE"
  # ── EVAL RENDER (STANDING DIRECTIVE): each run generates its own eval-prompt grid after
  # finishing (full 18-prompt × cfg{1,7,16} × strength{1,1.5,2} 20s grid), LAST + a MIDPOINT ckpt.
  SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
  ROUT=${SCRATCH}/renders/matrix_cells; mkdir -p "${ROUT}"
  mapfile -t CKS < <(ls ${RUN}/epoch=*.ckpt 2>/dev/null | sort -V)
  if [ ${#CKS[@]} -gt 0 ]; then
    SEL=("${CKS[$(( ${#CKS[@]} - 1 ))]}")
    [ ${#CKS[@]} -gt 3 ] && SEL+=("${CKS[$(( ${#CKS[@]} / 2 ))]}")
    for CK in "${SEL[@]}"; do
      EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
      echo "[arm ${ARM}] EVAL RENDER ${NAME} ep${EP}"
      python ${CODE}/lumi/render_matrix_cells.py --label ${NAME} --tag ep${EP} \
        --ckpt "${CK}" --prompts ${SNAP} --out ${ROUT} \
        || echo "[arm ${ARM}] eval render ep${EP} failed (non-fatal)"
    done
  fi
else
  echo "[arm ${ARM}] TRAIN FAILED — see ${RUN}/train.log (siblings unaffected)"
fi
'
echo "[adamw] all arms finished:" && ls -la "${RUNROOT}"
# SUCCESS = count ckpts per arm dir (NEVER the sbatch rc): each ${RUNROOT}/adamw_*/ should
# carry ~10 epoch ckpts + a run_meta.json + matrix_cells renders. A/B: arm 0/1 (AdamW bf16
# T512 bs4 lr1e-4) reads against runs/bf16_twin (Fusion bf16 T512 bs8 lr1e-4) — nearest single-
# variable optimizer comparison (bs 4 vs 8); the lr sweep (arms 0/4/6 avp, 1/5/7 goa) gives the AdamW curve.
