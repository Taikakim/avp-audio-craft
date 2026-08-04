#!/bin/bash
# efp_fp32_winning_continue40.sbatch — resume all 8 efp_fp32_winning.sbatch arms from their
# terminal fat checkpoints and train 40 MORE epochs (20 done -> 60 total). Kim direct
# 2026-07-29 ("40 more epochs for the winning models trained 20 so far"). Skeleton mirrors
# fp32cmp_continue_15e.sbatch (the verified continuation precedent) + efp_fp32_winning.sbatch's
# arm table/recipe. Motivation: the winning arms may still be under-trained at ep20 (cf. the
# Head-B melody head still improving at step9240) — 60 epochs surfaces whether more training
# helps or drifts; per-epoch ckpts keep every point auditable so we pick the best post-hoc.
#
# RESUME MECHANISM — VERIFIED (same as fp32cmp_continue_15e): train_lora.py `--resume_ckpt`
# = full Lightning .ckpt via trainer.fit(ckpt_path=...), restores optimizer + LR-scheduler +
# epoch/global_step (a TRUE seamless resume, incl. FusionOpt state). `--epochs` is the TOTAL
# Lightning max_epochs target, NOT an increment (flag help: "resuming an ep-4 ckpt with
# --epochs 8 = 3 more"). The fp32_winning ckpts are FAT/unpruned (W's inventory), so they
# carry optimizer state -> resume_ckpt (not warm_start).
#
# EPOCH ARITHMETIC: checkpoint `epoch=N` is 0-indexed = N+1 epochs COMPLETED. All 8 winning
# arms reached epoch=19 (= 20 epochs done). One uniform flag **--epochs 60** => every arm runs
# 60-20 = 40 more, finishing at epoch index 59. Do NOT pass per-arm counts (off-by-one trap).
#
# WALLTIME / RE-SUBMIT: 40 epochs is large. The original 20 epochs used most of the 47h node
# wall for the slower arms, so 40 more will very likely NOT fit one 47h job — esp. arm 5
# (T1024) and the goa/aug10 arms. THAT IS FINE: per-epoch checkpointing + the FATCKPT glob
# below (picks the LATEST epoch=*.ckpt) mean a re-submit of THIS SAME script auto-resumes from
# wherever it timed out and continues toward 60. Expect ~1-2 re-submits for the full 40; a
# timeout costs only the partial epoch in flight. Requesting the 47h max.
#
# PREREQS (verify before submit): (1) train_lora.py has --resume_ckpt + base_precision on the
#   SHIPPED code (grep below fails loud). (2) fat epoch=*.ckpt still present under
#   ${SCRATCH}/runs/fp32_winning/winning_*/ — NOT pruned to slim-only (a .weights-only dir has
#   no optimizer state to resume). (3) latents_avp/latents_sa3/latents_avp_aug10 tarballs on
#   ${SCRATCH} (already staged from the original winning campaign).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=47:00:00
#SBATCH --job-name=sa3_winning_cont40
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/fp32_winning   # SAME tree — resuming IN PLACE (continuous ep20..59)
mkdir -p "${FLASH}"

# ── code-refresh verification (fails loud, before the node spins up) ──
grep -q -- "--resume_ckpt" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[winning-cont] FATAL: train_lora.py missing --resume_ckpt — working-tree code refresh needed (lumi-ops: never git archive)"; exit 1; }
grep -q "base_precision" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[winning-cont] FATAL: train_lora.py missing base_precision"; exit 1; }

# ── stage datasets to NVMe once (idempotent) ──
for DS in latents_avp latents_sa3 latents_avp_aug10; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[winning-cont] avp: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)  aug10: $(ls ${FLASH}/latents_avp_aug10/*.npy 2>/dev/null | wc -l)"

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
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor  # +control: eval-render tail imports sa3_control
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

# ── arm table — SAME 8 arms/naming as efp_fp32_winning.sbatch ──
case ${ARM} in
  0) DS=latents_avp;       T=512;  ALPHA=45;  PREC=fp32 ;;   # FLAGSHIP avp
  1) DS=latents_sa3;       T=512;  ALPHA=45;  PREC=fp32 ;;   # FLAGSHIP goa
  2) DS=latents_avp;       T=512;  ALPHA=128; PREC=fp32 ;;   # alpha control
  3) DS=latents_sa3;       T=512;  ALPHA=128; PREC=fp32 ;;
  4) DS=latents_avp_aug10; T=512;  ALPHA=45;  PREC=fp32 ;;   # aug10
  5) DS=latents_avp;       T=1024; ALPHA=45;  PREC=fp32 ;;   # frames (slow arm)
  6) DS=latents_avp;       T=512;  ALPHA=45;  PREC=bf16 ;;   # precision control
  7) DS=latents_sa3;       T=512;  ALPHA=45;  PREC=bf16 ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
case ${DS} in
  latents_avp)       DSTAG=avp ;;
  latents_sa3)       DSTAG=goa ;;
  latents_avp_aug10) DSTAG=avpaug10 ;;
esac
NAME=winning_${DSTAG}_t${T}_a${ALPHA}_${PREC}
RUN=${RUNROOT}/${NAME}
if [ "${T}" = "1024" ]; then BS=4; else BS=8; fi

[ -d "${RUN}" ] || { echo "[arm ${ARM}] FATAL: ${RUN} missing — fp32_winning tree moved/pruned?"; exit 1; }

# ── glob the LATEST fat epoch=*.ckpt (excludes .weights slims); auto-resumes across re-submits ──
FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
if [ -z "${FATCKPT}" ]; then
  echo "[arm ${ARM}] FATAL: no fat epoch=*.ckpt in ${RUN} (pruned to slim-only? resume needs optimizer state)"; exit 1
fi
EP_AT=$(basename "${FATCKPT}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
echo "[arm ${ARM}] ${NAME}: resuming from ${FATCKPT} (epoch=${EP_AT} = $((EP_AT+1)) done) -> --epochs 60 ($((59 - EP_AT)) more)"

# longform sidecar default (goa/avp only; aug10 uses stored) — MUST match the original run
if [ "${CAPTIONS:-longform}" = "longform" ] && [ -z "${SIDECAR:-}" ] && [ "${DSTAG}" != "avpaug10" ]; then
  SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json
  PROBS=${PROBS:-0,0,1}
fi

# ── fp32 SDPA capability probe (fp32 arms only; bf16 uses native attention) ──
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

sc_args=()
if [ -n "${SIDECAR:-}" ]; then sc_args=(--caption_sidecar "${SIDECAR}" --caption_probs "${PROBS:-0.6,0.3,0.1}"); fi

echo "[arm ${ARM}] RESUME ${NAME} T=${T} BS=${BS} alpha=${ALPHA} ${PREC} -> ${RUN} (target 60 epochs)"
if python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/${DS} \
    --save_dir "${RUN}" \
    --adapter_type dora-rows --rank 128 --lora_alpha ${ALPHA} \
    --optimizer fusion \
    --base_precision ${PREC} \
    --lr 1e-4 --batch_size ${BS} \
    --frames ${T} $([ "${T}" = "512" ] || [ "${T}" = "1024" ] && echo --beat-aware-crop) \
    --resume_ckpt "${FATCKPT}" \
    --epochs 60 --checkpoint_every_epochs 1 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name ${NAME} "${sc_args[@]}" 2>&1 | tee -a ${RUN}/train_continue40.log; then
  echo "[arm ${ARM}] TRAIN DONE (reached 60)"
  # ── eval-render tail (standing directive): render the NEW terminal + a midpoint of the extension ──
  SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
  ROUT=${SCRATCH}/renders/matrix_cells; mkdir -p "${ROUT}"
  mapfile -t CKS < <(ls ${RUN}/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V)
  if [ ${#CKS[@]} -gt 0 ]; then
    SEL=("${CKS[$(( ${#CKS[@]} - 1 ))]}")                              # new terminal (ep59)
    [ ${#CKS[@]} -gt 3 ] && SEL+=("${CKS[$(( (${#CKS[@]} + 40) / 2 ))]}")   # ~ep40 midpoint of the extension
    for CK in "${SEL[@]}"; do
      EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
      echo "[arm ${ARM}] EVAL RENDER ${NAME} ep${EP} (full 18-prompt grid)"
      python ${CODE}/lumi/render_matrix_cells.py --label ${NAME} --tag ep${EP} \
        --ckpt "${CK}" --prompts ${SNAP} --out ${ROUT} \
        || echo "[arm ${ARM}] eval render ep${EP} failed (non-fatal)"
    done
  fi
else
  echo "[arm ${ARM}] TRAIN FAILED/TIMEOUT — see ${RUN}/train_continue40.log; RE-SUBMIT this script to auto-resume from the new terminal fat (siblings unaffected)"
fi
'
echo "[winning-cont] all arms finished:" && ls -la "${RUNROOT}"
# SUCCESS = per-arm: ${RUN}/train_continue40.log tail shows resume + loss ticking, and
# `ls ${RUN}/epoch=59*.ckpt` exists (or the latest epoch climbs past 19 toward 59). If any arm
# timed out short of 59, RE-SUBMIT this same script — the FATCKPT glob resumes it automatically.
# NEVER trust the sbatch rc; verify per-arm ckpt epochs.
