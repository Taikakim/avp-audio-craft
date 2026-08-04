#!/bin/bash
# efp_fp32_winning.sbatch — the "winning fp32 run" (WINTERMUTE 2026-07-22, from the DoRA
# hyperparameter × metric analysis). Flagship = the top-CLAP recipe levers (α<rank "adj",
# augmentation, fp32) on the FULL corpus, + ablations that isolate each lever from the
# 320-crop small-set confound Kim caught. One standard-g node, 8 GCDs, 8 SLURM_PROCID arms.
# Adapted from efp_fp32_compare.sbatch (same SDPA-fp32 probe / MIOpen / staging plumbing).
# Plan: docs/superpowers/specs/2026-07-22-winning-fp32-run-plan.md
#
# ARMS (α = lora_alpha; rank 128, lr 1e-4, FusionOpt, medium-base, 20 epochs, ckpt/epoch):
#   0: avp-full   T512   α45  fp32   FLAGSHIP (winning recipe, avp)
#   1: goa        T512   α45  fp32   FLAGSHIP (winning recipe, goa)
#   2: avp-full   T512   α128 fp32   α control (isolates the adj benefit)
#   3: goa        T512   α128 fp32   α control (goa)
#   4: avp-aug10  T512   α45  fp32   small-set control (does fp32 alone rescue the 320-crop result?)
#   5: avp-full   T1024  α45  fp32   frames control (analysis: T1024 optimum)
#   6: avp-full   T512   α45  bf16   precision control (fp32 vs bf16 on the identical winning recipe)
#   7: goa        T512   α45  bf16   precision control (goa)
#
# PREREQ: latents_avp.tar.gz + latents_sa3.tar.gz + latents_avp_aug10.tar.gz on ${SCRATCH},
# SIF+models+code pre-staged (same as efp_fp32_compare). The aug10 tarball is the NEW prereq.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=47:00:00
#SBATCH --job-name=sa3_fp32_winning
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/fp32_winning
mkdir -p "${RUNROOT}" "${FLASH}"

# ── stage datasets to NVMe once (idempotent) ──
for DS in latents_avp latents_sa3 latents_avp_aug10; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[winning] avp: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)  aug10: $(ls ${FLASH}/latents_avp_aug10/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/fp32_winning

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

# ── arm table: DS T ALPHA PREC ──
case ${ARM} in
  0) DS=latents_avp;       T=512;  ALPHA=45;  PREC=fp32 ;;
  1) DS=latents_sa3;       T=512;  ALPHA=45;  PREC=fp32 ;;
  2) DS=latents_avp;       T=512;  ALPHA=128; PREC=fp32 ;;
  3) DS=latents_sa3;       T=512;  ALPHA=128; PREC=fp32 ;;
  4) DS=latents_avp_aug10; T=512;  ALPHA=45;  PREC=fp32 ;;
  5) DS=latents_avp;       T=1024; ALPHA=45;  PREC=fp32 ;;
  6) DS=latents_avp;       T=512;  ALPHA=45;  PREC=bf16 ;;
  7) DS=latents_sa3;       T=512;  ALPHA=45;  PREC=bf16 ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
case ${DS} in
  latents_avp)       DSTAG=avp ;;
  latents_sa3)       DSTAG=goa ;;
  latents_avp_aug10) DSTAG=avpaug10 ;;
esac

# longform sidecar default (CAPTIONS=stored to disable) -- goa/avp only; aug10 uses stored
if [ "${CAPTIONS:-longform}" = "longform" ] && [ -z "${SIDECAR:-}" ] && [ "${DSTAG}" != "avpaug10" ]; then
  SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json
  PROBS=${PROBS:-0,0,1}
fi

# ── fp32 SDPA capability probe (fp32 arms only; bf16 arms use native attention) ──
if [ "${PREC}" = "fp32" ]; then
  if python - <<PYEOF
import torch
from torch.nn.attention import sdpa_kernel, SDPBackend
q = torch.randn(1, 24, 2048, 64, device="cuda", dtype=torch.float32)
try:
    with sdpa_kernel([SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION]):
        torch.nn.functional.scaled_dot_product_attention(q, q, q)
    print("fp32 fused SDPA: OK")
except Exception as e:
    print(f"fp32 fused SDPA unavailable: {e}")
    raise SystemExit(1)
PYEOF
  then export SA3_SDPA_CAST_BF16=0; echo "[arm ${ARM}] attention: true fp32"
  else export SA3_SDPA_CAST_BF16=1; echo "[arm ${ARM}] attention: bf16 island"
  fi
fi

NAME=winning_${DSTAG}_t${T}_a${ALPHA}_${PREC}
RUN=${RUNROOT}/${NAME}
mkdir -p "${RUN}"

# BS: T512 fp32 -> BS8 fits (the fp32cmp T512 arms ran BS8); T1024 -> BS4; bf16 half-cost -> BS8.
if [ "${T}" = "1024" ]; then BS=4; else BS=8; fi

train() {
  local sc_args=()
  if [ -n "${SIDECAR:-}" ]; then sc_args=(--caption_sidecar "${SIDECAR}" --caption_probs "${PROBS:-0.6,0.3,0.1}"); fi
  python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/${DS} \
    --save_dir "${RUN}" \
    --adapter_type dora-rows --rank 128 --lora_alpha ${ALPHA} \
    --optimizer fusion \
    --base_precision ${PREC} \
    --lr 1e-4 --batch_size ${BS} \
    --frames ${T} $([ "${T}" = "512" ] || [ "${T}" = "1024" ] && echo --beat-aware-crop) \
    --epochs 20 --checkpoint_every_epochs 1 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name ${NAME} "${sc_args[@]}"
}

echo "[arm ${ARM}] TRAIN ${DSTAG} T=${T} BS=${BS} alpha=${ALPHA} ${PREC} -> ${RUN}"
if train 2>&1 | tee ${RUN}/train.log; then
  echo "[arm ${ARM}] TRAIN DONE"
  # ── EVAL RENDER (STANDING DIRECTIVE, Kim 2026-07-23): every LUMI training run generates its
  # own eval-prompt grid after finishing, per spec (model_matrix_gen: full 18-prompt x cfg{1,7,16}
  # x strength{1,1.5,2} 20s grid). Fixes the coverage gap that left native runs at 1 prompt.
  # Rendered at 20s (cheap) even for native-trained arms; LAST + a MIDPOINT checkpoint.
  SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
  ROUT=${SCRATCH}/renders/matrix_cells; mkdir -p "${ROUT}"
  mapfile -t CKS < <(ls ${RUN}/epoch=*.ckpt 2>/dev/null | sort -V)
  if [ ${#CKS[@]} -gt 0 ]; then
    SEL=("${CKS[$(( ${#CKS[@]} - 1 ))]}")                                  # last
    [ ${#CKS[@]} -gt 3 ] && SEL+=("${CKS[$(( ${#CKS[@]} / 2 ))]}")         # + midpoint
    for CK in "${SEL[@]}"; do
      EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
      echo "[arm ${ARM}] EVAL RENDER ${NAME} ep${EP} (full 18-prompt grid)"
      python ${CODE}/lumi/render_matrix_cells.py --label ${NAME} --tag ep${EP} \
        --ckpt "${CK}" --prompts ${SNAP} --out ${ROUT} \
        || echo "[arm ${ARM}] eval render ep${EP} failed (non-fatal)"
    done
  fi
else
  echo "[arm ${ARM}] TRAIN FAILED — see ${RUN}/train.log (siblings unaffected)"
fi
'
echo "[winning] all arms finished:" && ls -la "${RUNROOT}"
# SUCCESS = each arm dir has epoch checkpoints; VERIFY by counting ckpts, never the sbatch rc.
