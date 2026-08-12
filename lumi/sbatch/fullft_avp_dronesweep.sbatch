#!/bin/bash
# fullft_avp_dronesweep.sbatch — CONTINUITY 2026-08-12 (Kim direct: the clean AVP fp32 full-FT
# drone-recipe A/B). Settles the drone fix + optimizer for deliverable-1 (great AVP model) BEFORE
# the goa-big-set production run gets the winner. T=1024 (Kim: 2x epochs/GPU-hour vs T4096).
#
# ENV = the PROVEN fullft_avp_aug/#68 multitorch recipe VERBATIM (lumi-multitorch-full image +
# sa3_train_venv_mt venv + expandable_segments + fp32-SDPA probe). v1 wrongly used sa3.sif -> every
# arm died miopenStatusInternalError in the backward conv (smoke 21060331). Fixed here.
#
# LAYOUT = 4 recipes x 2 seeds = 8 GCDs, 1 INDEPENDENT full-FT per GCD (NOT DDP): srun --overlap
# --ntasks=8 + ROCR_VISIBLE_DEVICES=$SLURM_PROCID (the morph/#52 independent-arm pin; NOT
# --gpus-per-task=1 which collides all arms on GCD0). Full-FT fp32/T1024/bs4 fits 1 GCD (mem_probe).
# 2 seeds = the synthesis's sweep->replicate in one job. GATE on ears + disintegration DSP, not z0-std.
#
# RECIPES (WD 0.1 = drone fix, NOT the 0.01 default; EMA 0.9999; grad-clip 1.0; CFG-dropout 0.1
#   inherited from the training wrapper = SA1 10%; no tag-shuffle = correct for T5-Gemma):
#   plain        FusionOpt(all-on)+wd0.1              (bounded-runaway baseline)
#   force_scalar +Muon-OFF on output-proj+AdaLN       (SA3-base's OWN recipe; the clean cure)
#   adamw_fair   AdamW lr 2e-4                         (strategic null: no runaway, ~1.1x gap)
#   bf16_plain   plain but bf16                        (settle fp32-vs-bf16 COST axis, matched)
#
# RUN: SMOKE=1 sbatch ...  (steps-capped ~15min; verify [gpu-assign] ROCR 0..7 distinct + no crash + ckpts)
#      then sbatch ...      (full)
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=48:00:00
#SBATCH --job-name=fullft_avp_dronesweep
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code; MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
SAVE_ROOT=${SCRATCH}/runs/avp_dronesweep; mkdir -p "${SAVE_ROOT}" "${FLASH}"
SMOKE=${SMOKE:-}
BS=${BS:-4}; FRAMES=${FRAMES:-1024}; EPOCHS=${EPOCHS:-20}; CKEVERY=${CKEVERY:-2}; WD=${WD:-0.1}
FSRE='project_out|postprocess_conv|to_scale_shift_gate'   # output-proj + AdaLN (SA3-base recipe)

[ -n "${SIF}" ] || { echo "[sweep] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[sweep] FATAL: ${VENV} missing"; exit 1; }
grep -q -- "--force-scalar" "${CODE}/stable-audio-3/scripts/train_lora.py" || { echo "[sweep] FATAL: train_lora on LUMI missing --force-scalar (rsync it)"; exit 1; }
if [ ! -d "${FLASH}/latents_avp" ]; then
  [ -f "${SCRATCH}/latents_avp.tar.gz" ] || { echo "[sweep] FATAL: ${SCRATCH}/latents_avp.tar.gz missing"; exit 1; }
  mkdir -p "${FLASH}/latents_avp"; tar -xzf "${SCRATCH}/latents_avp.tar.gz" -C "${FLASH}/latents_avp" --strip-components=1
fi
echo "[sweep] image=${SIF}  crops=$(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  FRAMES=${FRAMES} BS=${BS} EPOCHS=${EPOCHS} WD=${WD} SMOKE=${SMOKE:-0}"

srun --overlap --cpu-bind=none --mpi=none --nodes=1 --ntasks=8 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
export ROCR_VISIBLE_DEVICES=${ARM}                        # pin THIS task to GCD=ARM (ROCR ALONE, never +HIP)
echo "[gpu-assign] arm=${ARM} ROCR=${ROCR_VISIBLE_DEVICES:-} STEP_GPUS=${SLURM_STEP_GPUS:-}"
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186; CODE=${PROJ}/code
VENV='"${VENV}"'; source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-${ARM} /tmp/triton-${ARM}; mkdir -p /tmp/miopen-${ARM} /tmp/triton-${ARM}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true
SAVE_ROOT='"${SAVE_ROOT}"'; FRAMES='"${FRAMES}"'; BS='"${BS}"'; EPOCHS='"${EPOCHS}"'; CKEVERY='"${CKEVERY}"'; WD='"${WD}"'; FSRE='"'"${FSRE}"'"'
case ${ARM} in
  0) R=plain;        SEED=1; OPT="--optimizer fusion --weight_decay ${WD}"; PREC=fp32 ;;
  1) R=force_scalar; SEED=1; OPT="--optimizer fusion --weight_decay ${WD} --force-scalar ${FSRE}"; PREC=fp32 ;;
  2) R=adamw_fair;   SEED=1; OPT="--optimizer adamw --lr 2e-4"; PREC=fp32 ;;
  3) R=bf16_plain;   SEED=1; OPT="--optimizer fusion --weight_decay ${WD}"; PREC=bf16 ;;
  4) R=plain;        SEED=2; OPT="--optimizer fusion --weight_decay ${WD}"; PREC=fp32 ;;
  5) R=force_scalar; SEED=2; OPT="--optimizer fusion --weight_decay ${WD} --force-scalar ${FSRE}"; PREC=fp32 ;;
  6) R=adamw_fair;   SEED=2; OPT="--optimizer adamw --lr 2e-4"; PREC=fp32 ;;
  7) R=bf16_plain;   SEED=2; OPT="--optimizer fusion --weight_decay ${WD}"; PREC=bf16 ;;
  *) echo "[sweep] arm ${ARM} unassigned"; exit 0 ;;
esac
LR_DEF="--lr 8e-5"; case "${OPT}" in *"--lr "*) LR_DEF="";; esac
# fp32 fused-SDPA probe (native fp32 attn if available, else cast bf16 for SDPA only)
if [ "${PREC}" = "fp32" ]; then
  if python - <<PYEOF
import torch
from torch.nn.attention import sdpa_kernel, SDPBackend
q = torch.randn(1, 24, 4096, 64, device="cuda", dtype=torch.float32)
try:
    with sdpa_kernel([SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION]):
        torch.nn.functional.scaled_dot_product_attention(q, q, q)
    raise SystemExit(0)
except SystemExit:
    raise
except Exception:
    raise SystemExit(1)
PYEOF
  then export SA3_SDPA_CAST_BF16=0; else export SA3_SDPA_CAST_BF16=1; fi
  echo "[rank ${ARM}] fp32 SDPA cast_bf16=${SA3_SDPA_CAST_BF16}"
fi
if [ -n "'"${SMOKE:-}"'" ]; then EPOCHARG="--steps 120 --checkpoint_every 60"; else EPOCHARG="--epochs ${EPOCHS} --checkpoint_every_epochs ${CKEVERY}"; fi
RUN="${SAVE_ROOT}/${R}_s${SEED}"; mkdir -p "${RUN}"
echo "[sweep] arm ${ARM} -> ${R} seed${SEED}: prec=${PREC} opt=[${OPT}] -> ${RUN}"
if python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base --full-finetune \
    --encoded_dir ${FLASH}/latents_avp --save_dir "${RUN}" \
    ${OPT} ${LR_DEF} --use-ema --ema-beta 0.9999 \
    --base_precision ${PREC} --gradient_clip_val 1.0 \
    --batch_size ${BS} --frames ${FRAMES} --beat-aware-crop \
    ${EPOCHARG} --num_workers 6 --seed ${SEED} --no_demos --logger csv \
    --name avp_dronesweep_${R}_s${SEED} 2>&1 | tee -a "${RUN}"/train_rank${ARM}.log; then
  echo "[sweep] arm ${ARM} (${R} s${SEED}) DONE"
else
  echo "[sweep] arm ${ARM} (${R} s${SEED}) FAILED — see ${RUN}/train_rank${ARM}.log (siblings unaffected)"
fi
'
set +e
echo "[sweep] ===== per-arm ckpt count ====="
for d in "${SAVE_ROOT}"/*/; do n=$(ls "${d}"epoch=*.ckpt 2>/dev/null | grep -cv weights); echo "  $(basename "${d}"): ${n} ckpts"; done
