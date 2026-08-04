#!/bin/bash
# efp_alpha_campaign.sbatch — alpha sweep + frames + optimizer-ablation campaign
# (CONTINUITY 2026-07-24, from Kim's ear-A/B: winning α45 beat α128 on stereo+punch).
# Adapted verbatim from efp_fp32_winning.sbatch (SDPA-fp32 probe / MIOpen / staging /
# per-arm eval-render tail unchanged). One standard-g node, 8 GCDs, 8 SLURM_PROCID arms.
# Base recipe (all arms): medium-base, dora-rows rank 128, --optimizer fusion, fp32,
# lr 1e-4, 20 epochs, ckpt/epoch, beat-aware-crop.
#
# ARMS:
#   0: avp  T512  α16  fp32   alpha-low   (does the α45>α128 trend continue even gentler?)
#   1: goa  T512  α16  fp32   alpha-low (goa)
#   2: avp  T512  α86  fp32   alpha-mid   (halfway 45->128, fills the sweep)
#   3: goa  T512  α86  fp32   alpha-mid (goa)
#   4: avp  T512  α45  fp32   QKV-SPLIT   (Zach: split fused to_qkv before NS5) -- needs --fusion-split-qkv
#   5: avp  T1024 α45  fp32   frames-1024 (20ep, avp)
#   6: goa  T1024 α45  fp32   frames-1024 (20ep, goa)
#   7: avp  T512  α45  fp32   KL-SHAMPOO on, BS4 -- needs --fusion-shampoo (was off ONLY for local 16GB VRAM;
#                                                    fits on a 64GB GCD)
#
# ⚠️ CODE PREREQ (W's lane, DM'd 2026-07-24): arms 4 and 7 pass flags train_lora.py does NOT
# yet accept — --fusion-split-qkv (fused-qkv split in build_fusion_param_groups before NS5)
# and --fusion-shampoo (append "shampoo" to the FusionOpt components list). DO NOT SUBMIT
# until BOTH parse on the SHIPPED code (grep -c 'fusion-split-qkv' / 'fusion-shampoo' in
# train_lora.py on LUMI, or a --help parse-test) — else arms 4/7 argparse-fail in seconds
# and burn their GCDs (lumi-ops: verify-shipped-flag-before-submit). Arms 0-3,5,6 are
# config-only and run regardless.
#
# PREREQ DATA: latents_avp.tar.gz + latents_sa3.tar.gz on ${SCRATCH} (already staged).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=47:00:00
#SBATCH --job-name=sa3_alpha_campaign
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/alpha_campaign
mkdir -p "${RUNROOT}" "${FLASH}"

# ── stage datasets to NVMe once (idempotent) ──
for DS in latents_avp latents_sa3; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[alpha] avp: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/alpha_campaign

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor  # +control: render_matrix_cells imports sa3_control (job 20190736 tail crash)
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

# ── arm table: DS T ALPHA EXTRA TAG ── (all fp32)
case ${ARM} in
  0) DS=latents_avp; T=512;  ALPHA=16;  EXTRA="";                   TAG="" ;;
  1) DS=latents_sa3; T=512;  ALPHA=16;  EXTRA="";                   TAG="" ;;
  2) DS=latents_avp; T=512;  ALPHA=86;  EXTRA="";                   TAG="" ;;
  3) DS=latents_sa3; T=512;  ALPHA=86;  EXTRA="";                   TAG="" ;;
  4) DS=latents_avp; T=512;  ALPHA=45;  EXTRA="--fusion-split-qkv"; TAG="_qkvsplit" ;;
  5) DS=latents_avp; T=1024; ALPHA=45;  EXTRA="";                   TAG="" ;;
  6) DS=latents_sa3; T=1024; ALPHA=45;  EXTRA="";                   TAG="" ;;
  7) DS=latents_avp; T=512;  ALPHA=45;  EXTRA="--fusion-shampoo";   TAG="_shampoo" ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
PREC=fp32
case ${DS} in
  latents_avp) DSTAG=avp ;;
  latents_sa3) DSTAG=goa ;;
esac

# longform sidecar default (CAPTIONS=stored to disable)
if [ "${CAPTIONS:-longform}" = "longform" ] && [ -z "${SIDECAR:-}" ]; then
  SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json
  PROBS=${PROBS:-0,0,1}
fi

# ── fp32 SDPA capability probe (all arms fp32) ──
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

NAME=winning_${DSTAG}_t${T}_a${ALPHA}_${PREC}${TAG}
RUN=${RUNROOT}/${NAME}
mkdir -p "${RUN}"

# BS: T1024 -> 4; shampoo arm -> 4 (Kim); else 8.
if [ "${T}" = "1024" ] || [ "${ARM}" = "7" ]; then BS=4; else BS=8; fi

train() {
  local sc_args=()
  if [ -n "${SIDECAR:-}" ]; then sc_args=(--caption_sidecar "${SIDECAR}" --caption_probs "${PROBS:-0.6,0.3,0.1}"); fi
  python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/${DS} \
    --save_dir "${RUN}" \
    --adapter_type dora-rows --rank 128 --lora_alpha ${ALPHA} \
    --optimizer fusion ${EXTRA} \
    --base_precision ${PREC} \
    --lr 1e-4 --batch_size ${BS} \
    --frames ${T} $([ "${T}" = "512" ] || [ "${T}" = "1024" ] && echo --beat-aware-crop) \
    --epochs 20 --checkpoint_every_epochs 1 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name ${NAME} "${sc_args[@]}"
}

echo "[arm ${ARM}] TRAIN ${DSTAG} T=${T} BS=${BS} alpha=${ALPHA} ${PREC} ${EXTRA} -> ${RUN}"
if train 2>&1 | tee ${RUN}/train.log; then
  echo "[arm ${ARM}] TRAIN DONE"
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
echo "[alpha] all arms finished:" && ls -la "${RUNROOT}"
# SUCCESS = each arm dir has epoch checkpoints; VERIFY by counting ckpts, never the sbatch rc.
