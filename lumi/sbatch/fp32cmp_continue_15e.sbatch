#!/bin/bash
# fp32cmp_continue_15e.sbatch — DRAFT (2026-07-23, unsubmitted, for Kim's review):
# resume all 8 efp_fp32_compare.sbatch arms from their terminal fat checkpoints and
# train each to the NEW 15-epoch default (docs/training-findings.md, Kim's 2026-07-23
# listening verdicts). Skeleton = efp_fp32_compare.sbatch verbatim (same srun/singularity
# deployment, MIOpen/HF env, fp32-SDPA probe); the only new thing is the resume plumbing.
#
# RESUME MECHANISM — VERIFIED, not assumed (task asked to check this before building):
# `scripts/train_lora.py` has TWO ckpt-continuation flags — `--resume_ckpt` (full Lightning
# .ckpt, `trainer.fit(..., ckpt_path=args.resume_ckpt)`, line ~442: restores optimizer state,
# LR-scheduler state, AND epoch/global_step counters — a real seamless resume, not a
# different experiment) vs `--warm_start_ckpt` (OLD-format ckpts only, weights+optimizer
# but epoch/step counters RESTART). **This job uses `--resume_ckpt`** — the true-resume
# path Kim wants. Confirmed via the flag's own help text: "--epochs is the total target,
# so resuming an ep-4 ckpt with --epochs 8 = 3 more" — exactly the semantics this job
# relies on (see the epoch arithmetic below). No open question here: true resume exists
# and this script uses it.
#
# GROUND TRUTH (Kim's live inventory, all 8 confirmed 1 fat .ckpt each, post-prune):
#   avp_t4096_bs1        ep7   avp_t4096_bs4        ep7   avp_t4096_bs4_lr5e5  ep7
#   avp_t512_bs8         ep7   goa_t4096_bs4        ep7   goa_t4096_bs4_lr5e5  ep7
#   goa_t512_bs8         ep7   goa_t4096_bs1_lr1e4  ep6   <- 47h-TIMEOUT casualty, job 19945290
# (BS values are the RESOLVED batch sizes the original probe settled on — arms 0/1/6/7
# were `BS=probe` in efp_fp32_compare.sbatch and all four resolved to BS=4; no re-probe
# here, the resolved value is now fixed history.)
#
# EPOCH ARITHMETIC (off-by-one here wastes node-days — worked through explicitly):
# checkpoint `epoch=N` is 0-indexed and means N+1 epochs have COMPLETED. So `epoch=7`
# = 8 epochs done, `epoch=6` = 7 epochs done. `--epochs` in train_lora.py is the Lightning
# `max_epochs` TOTAL target (not an increment — see the resume-flag help text above), so
# **every arm passes the SAME `--epochs 15`**: the 7 ep7 arms each run 15-8 = **7 more**
# epochs (finishing at epoch index 14 = 15 total); the ep6 arm (goa_t4096_bs1_lr1e4) runs
# 15-7 = **8 more** (also finishing at epoch index 14). One flag, correct for all 8 arms —
# do NOT compute a per-arm epoch count and pass different values, that's the off-by-one trap.
#
# WALLTIME: slowest arm is goa_t4096_bs1 (~99 min/epoch observed) x 8 remaining epochs =
# ~13.2h -> requesting 20:00:00 (headroom for the other 7 faster/shorter arms + startup).
# TIMEOUT LESSON (why per-epoch ckpts matter here): job 19945290 died AT the 47h wall
# mid-epoch on the original goa_t4096_bs1_lr1e4 arm — that's exactly why it's the ep6
# outlier. Per-epoch checkpointing means a timeout here costs only the partial epoch in
# flight; a re-submit of this same script just resumes again from whatever the new
# terminal fat is (glob picks it up automatically — no manual epoch bookkeeping needed).
#
# PREREQS / CODE REFRESH (lumi-ops rule: working tree, never `git archive`) — this job
# NEEDS the fp32 train_lora patch AND --resume_ckpt shipped; the preamble below grep-
# verifies both before spinning up the node (fails in seconds, not after allocation).
# Also needs: latents_avp.tar.gz + latents_sa3.tar.gz on ${SCRATCH} (already staged from
# the original campaign) and the fat .ckpt files still present under
# ${SCRATCH}/runs/fp32_compare/fp32cmp_*/ (i.e. prune_optimizer_states.py has NOT yet
# been run against this tree — a pruned-to-slim-only dir has no optimizer state to resume
# from; verify before submitting).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=20:00:00
#SBATCH --job-name=sa3_fp32cmp_cont15e
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/fp32_compare   # SAME tree as the original campaign — resuming IN PLACE
mkdir -p "${FLASH}"

# ── code-refresh verification (fails loud, before the node spins up) ──
grep -q -- "--resume_ckpt" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[fp32cmp-cont] FATAL: train_lora.py missing --resume_ckpt — working-tree code refresh needed (never git archive, lumi-ops rule)"; exit 1; }
grep -q "base_precision" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[fp32cmp-cont] FATAL: train_lora.py missing the fp32 base_precision patch"; exit 1; }

# ── stage both datasets to NVMe once (idempotent, done by task 0 before srun) ──
for DS in latents_avp latents_sa3; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[fp32cmp-cont] avp latents: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/fp32_compare

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

# ── arm table — SAME 8 arms/naming as efp_fp32_compare.sbatch, resolved-BS history baked in ──
case ${ARM} in
  0) DS=latents_avp; T=4096; BS=4; LR=1e-4; EP_DONE=7 ;;
  1) DS=latents_sa3; T=4096; BS=4; LR=1e-4; EP_DONE=7 ;;
  2) DS=latents_avp; T=4096; BS=1; LR=1e-4; EP_DONE=7 ;;
  3) DS=latents_sa3; T=4096; BS=1; LR=1e-4; EP_DONE=6 ;;   # 19945290 timeout casualty
  4) DS=latents_avp; T=512;  BS=8; LR=1e-4; EP_DONE=7 ;;
  5) DS=latents_sa3; T=512;  BS=8; LR=1e-4; EP_DONE=7 ;;
  6) DS=latents_avp; T=4096; BS=4; LR=5e-5; EP_DONE=7 ;;
  7) DS=latents_sa3; T=4096; BS=4; LR=5e-5; EP_DONE=7 ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
DSTAG=$([ "${DS}" = latents_avp ] && echo avp || echo goa)
LRTAG=$(echo ${LR} | tr -d ".-")
RUN=${RUNROOT}/fp32cmp_${DSTAG}_t${T}_bs${BS}_lr${LRTAG}
REMAINING=$((15 - (EP_DONE + 1)))
echo "[arm ${ARM}] ${DSTAG} t${T} bs${BS} lr${LR}: epoch=${EP_DONE} done ($((EP_DONE+1)) epochs) -> resume to 15 total (${REMAINING} more)"

[ -d "${RUN}" ] || { echo "[arm ${ARM}] FATAL: ${RUN} missing — was the original fp32_compare tree pruned/moved?"; exit 1; }

# ── glob the single fat (non-.weights) epoch=*.ckpt — the only one with optimizer state ──
FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
if [ -z "${FATCKPT}" ]; then
  echo "[arm ${ARM}] FATAL: no fat epoch=*.ckpt in ${RUN} (pruned to slim-only? resume needs optimizer state)"
  exit 1
fi
echo "[arm ${ARM}] resuming from ${FATCKPT}"

# longform sidecar default (CAPTIONS=stored to disable; SIDECAR/PROBS override) — SAME
# default as the original campaign, must match for a coherent resume.
if [ "${CAPTIONS:-longform}" = "longform" ] && [ -z "${SIDECAR:-}" ]; then
  SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json
  PROBS=${PROBS:-0,0,1}
fi

# ── fp32 SDPA capability probe (once per arm, cheap — identical to efp_fp32_compare.sbatch) ──
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

sc_args=()
if [ -n "${SIDECAR:-}" ]; then
  sc_args=(--caption_sidecar "${SIDECAR}" --caption_probs "${PROBS:-0.6,0.3,0.1}")
fi

echo "[arm ${ARM}] RESUME ${DSTAG} T=${T} BS=${BS} lr=${LR} fp32 -> ${RUN} (target: 15 total epochs)"
if python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/${DS} \
    --save_dir "${RUN}" \
    --adapter_type dora-rows --rank 128 --lora_alpha 128 \
    --optimizer fusion \
    --base_precision fp32 \
    --lr ${LR} --batch_size ${BS} \
    --frames ${T} $([ "${T}" = "512" ] && echo --beat-aware-crop) \
    --resume_ckpt "${FATCKPT}" \
    --epochs 15 --checkpoint_every_epochs 1 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name fp32cmp_${DSTAG}_t${T}_lr${LRTAG} \
    "${sc_args[@]}" 2>&1 | tee -a ${RUN}/train_continue15e.log; then
  echo "[arm ${ARM}] DONE"
else
  echo "[arm ${ARM}] TRAIN FAILED — see ${RUN}/train_continue15e.log (siblings unaffected)"
fi
'
echo "[fp32cmp-cont] all arms finished:" && ls -la "${RUNROOT}"
# SUCCESS: each arm prints its resumed-from fat + attention mode, loss lines tick,
# per-epoch ckpts continue past the pre-existing epoch=7 (or epoch=6) up through
# epoch=14. sbatch rc 0 proves nothing about individual arms — check each
# ${RUN}/train_continue15e.log tail + `ls ${RUN}/epoch=14*.ckpt` per arm.
