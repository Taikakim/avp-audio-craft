#!/bin/bash
# efp_bf16_twin.sbatch — MATCHED BF16 CONTROL for the fp32 campaign (Kim, 2026-07-16).
# De-confounds the precision axis: the fp32 campaign's T=512 arms (PROCID 4/5) had no
# matched bf16 control INSIDE the campaign -- only historical local runs, which differ in
# data version / step count / env. These 2 arms replicate fp32 arms 4/5 EXACTLY (same data,
# steps, crop, batch, lr, longform sidecar) and differ ONLY in precision: default bf16-mixed,
# no --base_precision fp32. So fp32-arm4/5 vs bf16-arm0/1 = a clean fp32-vs-bf16 comparison.
# small-g, 2 GCDs. (The SDPA fp32 probe below is a harmless no-op under bf16-mixed.)
#   PROCID 0: avp  T=512  BS=8  lr 1e-4  bf16   (bf16 twin of fp32 arm 4)
#   PROCID 1: goa  T=512  BS=8  lr 1e-4  bf16   (bf16 twin of fp32 arm 5)
#
# BATCH ARITHMETIC (why probe 4->3->2): 64 GB/GCD. Fixed costs fp32: DiT 1.4B = 5.6 GB
# + conditioner ~2 GB + dora-r128 params/grads/Adam ~1.5 GB + ROCm workspace ~2 GB.
# Activations (no grad ckpt in train_lora) ~13-15 GB per sample at T=4096 fp32 with
# fused-attention memory. BS4 ~= 63-71 GB (coin flip), BS3 ~= 50-56 GB, BS2 safe.
# The probe settles it empirically: 30-step dry run per candidate, largest survivor wins.
#
# ATTENTION/PRECISION (Kim's FA2-vs-SDPA question, short version): FA2 kernels are
# fp16/bf16-ONLY — there is no fp32 flash attention anywhere, and our repo's FA path
# already silently casts fp32->fp16 (transformer.py ~line 680). On this container
# (no flash-attn, SDPA path) the prolog PROBES whether ROCm's fused SDPA backends
# accept fp32 at T=4096: if yes, attention runs true-fp32 (memory-safe, O(T));
# if not, SA3_SDPA_CAST_BF16=1 runs the attention kernel in bf16 and keeps
# everything else fp32 (same convention as the FA path; the alternative — math
# backend — saves the T x T softmax per layer for backward, ~50 GB at T=4096 bs1).
#
# CAPTIONS (Kim direct 2026-07-14): DEFAULT = the definitive longform sidecars
# (G's build, SAO 2131a36 — MF/Granite own prompts first-class, same-cluster
# borrow for uncaptioned tracks via merged_clusters_k48): goa 5400/5400 t3,
# avp 2236/2393 (93.4%; 157 unfillable fall back to stored t1). PROBS=0,0,1
# trains pure-longform; provenance maps ride beside the sidecars for eval pages.
# Caveat (G): only 163/273 flamingo-budget tracks were actually MF-captioned.
# To train on the datasets' stored prompts instead (caption-confound-free twin
# of the local runs), submit with CAPTIONS=stored.
#
# EPOCHS/WALLTIME: 8 epochs, ckpt every epoch. goa T=4096 BS1 = 5400 steps/epoch is
# the slow arm (~2-4 s/step fp32) and may hit the 48 h wall around epoch 5-8 —
# per-epoch checkpoints make partial completion useful. BILLING: whole node x
# walltime (max ~8 x 47 = 376 GCD-h of the 5000 budget); arms that finish early
# idle their GCD — acceptable for one flagship comparison.
#
# PREREQS: same as efp_smoke_r256.sbatch (code+SIF+models pre-staged) PLUS
# latents_avp.tar.gz and latents_sa3.tar.gz on ${SCRATCH} (Kim's rsync) and the
# code tarball refreshed so scripts/train_lora.py has the fp32 patch and
# stable_audio_3/models/transformer.py has the SA3_SDPA_CAST_BF16 island.
#
#SBATCH --account=project_465003186
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=2
#SBATCH --ntasks-per-node=2
#SBATCH --cpus-per-task=7
#SBATCH --mem=120G
#SBATCH --time=10:00:00
#SBATCH --job-name=sa3_bf16_twin
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/bf16_twin
mkdir -p "${RUNROOT}" "${FLASH}"

# ── stage both datasets to NVMe once (idempotent, done by task 0 before srun) ──
for DS in latents_avp latents_sa3; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[bf16cmp] avp latents: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

# per-arm launcher: everything below runs once per task inside the container.
# --nodes pinned: the EFP form controls the allocation and can oversize it;
# all 8 arms must land on ONE node's 8 GCDs.
srun --nodes=1 --ntasks=2 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/bf16_twin

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor   # source pkg + vendored FusionOpt shim
# MIOPEN_DISABLE_CACHE=1: the MIOpen user kernel-cache gfx90a6e.ukdb is a SQLite file whose
# open fails on LUMI on every filesystem -- proven on the smoke run 2026-07-16. Disabling the
# cache is the fix; kernels recompile per run. /tmp is bound above as host tmpfs. See smoke.
# NOTE: this arm script runs inside a single-quoted bash -c -- no apostrophes or backticks below.
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

# ── arm table ────────────────────────────────────────────────────────────────
case ${ARM} in
  0) DS=latents_avp; T=512; BS=8; LR=1e-4 ;;   # bf16 twin of fp32 arm 4
  1) DS=latents_sa3; T=512; BS=8; LR=1e-4 ;;   # bf16 twin of fp32 arm 5
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
DSTAG=$([ "${DS}" = latents_avp ] && echo avp || echo goa)
LRTAG=$(echo ${LR} | tr -d ".-")

# longform sidecar default (CAPTIONS=stored to disable; SIDECAR/PROBS override)
if [ "${CAPTIONS:-longform}" = "longform" ] && [ -z "${SIDECAR:-}" ]; then
  SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json
  PROBS=${PROBS:-0,0,1}
fi

# ── fp32 SDPA capability probe (once per arm, cheap) ─────────────────────────
# True-fp32 fused attention if the backend allows; bf16 attention island if not.
if python - <<PYEOF
import torch
from torch.nn.attention import sdpa_kernel, SDPBackend
q = torch.randn(1, 24, 4096, 64, device="cuda", dtype=torch.float32)
try:
    with sdpa_kernel([SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION]):
        torch.nn.functional.scaled_dot_product_attention(q, q, q)
    print("fp32 fused SDPA: OK")
except Exception as e:
    print(f"fp32 fused SDPA unavailable: {e}")
    raise SystemExit(1)
PYEOF
then
  export SA3_SDPA_CAST_BF16=0
  echo "[arm ${ARM}] attention: true fp32 (fused backend accepts fp32)"
else
  export SA3_SDPA_CAST_BF16=1
  echo "[arm ${ARM}] attention: bf16 island (fused fp32 unsupported; math would OOM)"
fi

train() {  # train <batch> <steps-or-empty> <savedir> [extra args...]
  local B=$1 STEPS=$2 SAVE=$3; shift 3
  local sc_args=()
  if [ -n "${SIDECAR:-}" ]; then
    sc_args=(--caption_sidecar "${SIDECAR}" --caption_probs "${PROBS:-0.6,0.3,0.1}")
  fi
  python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/${DS} \
    --save_dir "${SAVE}" \
    --adapter_type dora-rows --rank 128 --lora_alpha 128 \
    --optimizer fusion \
    --lr ${LR} --batch_size ${B} \
    --frames ${T} $([ "${T}" = "512" ] && echo --beat-aware-crop) \
    ${STEPS:+--steps ${STEPS}} \
    $([ -z "${STEPS}" ] && echo "--epochs 8 --checkpoint_every_epochs 1") \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name bf16cmp_${DSTAG}_t${T}_lr${LRTAG} \
    "${sc_args[@]}" "$@"
}

# ── batch probe (max-batch arms): 30-step dry run, largest survivor wins ─────
if [ "${BS}" = "probe" ]; then
  for CAND in 4 3 2; do
    PROBE_DIR=${RUNROOT}/probe_arm${ARM}_bs${CAND}
    echo "[arm ${ARM}] probing BS=${CAND} (30 steps)"
    if train ${CAND} 30 "${PROBE_DIR}" > ${RUNROOT}/probe_arm${ARM}_bs${CAND}.log 2>&1; then
      BS=${CAND}
      echo "[arm ${ARM}] probe OK at BS=${BS}"
      rm -rf "${PROBE_DIR}"
      break
    fi
    echo "[arm ${ARM}] BS=${CAND} failed (see probe log) — backing off"
    rm -rf "${PROBE_DIR}"
  done
  # exit 0 on give-up: a nonzero task exit can take the sibling arms down with it
  if [ "${BS}" = "probe" ]; then echo "[arm ${ARM}] FAILED: even BS=2 OOMs — arm abandoned"; exit 0; fi
fi

RUN=${RUNROOT}/bf16cmp_${DSTAG}_t${T}_bs${BS}_lr${LRTAG}
mkdir -p "${RUN}"
echo "[arm ${ARM}] TRAIN ${DSTAG} T=${T} BS=${BS} lr=${LR} fp32 -> ${RUN}"
if train ${BS} "" "${RUN}" 2>&1 | tee ${RUN}/train.log; then
  echo "[arm ${ARM}] DONE"
else
  echo "[arm ${ARM}] TRAIN FAILED — see ${RUN}/train.log (siblings unaffected)"
fi
'
echo "[bf16cmp] all arms finished:" && ls -la "${RUNROOT}"
# SUCCESS: each arm prints its attention mode + resolved BS, loss lines tick, one
# ckpt per epoch lands under ${RUNROOT}/bf16cmp_*/. Compare vs local bf16 T=512 runs:
# precision (arm 4/5 vs local), context length (0/1 vs 4/5), batch (0/1 vs 2/3),
# lr (6/7 vs 0/1). a2a auditions render with the longform (kimlong) prompts per
# the model_matrix convention.
