#!/bin/bash
# continue_8runs_openended.sbatch — CONTINUITY 2026-08-15 (Kim direct): resume 8 specific
# named runs on ONE node (8 GCDs, one arm each), open-ended (NO --epochs cap — Kim: "maybe
# it's interesting to go on past 60, for style transfers overtrained models can be very
# good... continue from last epoch of each"). Combines THREE previously-separate campaigns
# that share one deployment (sa3.sif, same MIOpen/env pattern, same latents_avp/latents_sa3):
#   arms 0-3: fp32cmp DoRA arms      (precedent: fp32cmp_continue_15e.sbatch, DRAFT/unconfirmed-run)
#   arms 4-5: winning DoRA arms      (precedent: efp_fp32_winning_continue40.sbatch)
#   arms 6-7: fullft_t256 full-FT    (precedent: efp_fullft_short.sbatch; NEW this run: EMA+AGC)
#
# ── OPEN-ENDED, NOT A FIXED TARGET (Kim direct) ── train_lora.py: `--epochs` defaults to
# None -> Lightning max_epochs=None -> trains until walltime/manual stop, no capped target.
# Omitted here on purpose for ALL 8 arms. Re-submit this same script to keep extending past
# a walltime timeout (FATCKPT glob below auto-picks up wherever each arm left off — same
# auto-resume pattern as every other continue script this session).
#
# ── EMA + AGC now added to arms 6-7 ONLY (fullft_t256, Kim direct 2026-08-15) — NOT arms
# 0-5: EMA is full-finetune ONLY, train_lora.py force-disables it for DoRA/LoRA regardless
# of the flag (see its own printed note), so passing --use-ema on arms 0-5 would be a no-op;
# left OFF there to match the arm's actual recipe, not to withhold a working feature.
#   - CRASH SAFETY (verified in code, not assumed): train_lora.py sets
#     training_wrapper.strict_loading = False on any --resume_ckpt specifically to tolerate
#     key-set mismatches (comment: "DoRA fats strip the frozen base... a partial restore is
#     CORRECT"). Newly turning on --use-ema on a checkpoint trained WITHOUT it means the
#     resumed ckpt has no diffusion_ema.* keys at all -- strict_loading=False means this is
#     a normal missing-keys skip, not a crash.
#   - STALENESS SAFETY (verified in code): SimpleEMA.update_after_step (bound to
#     --ema-warmup-steps, default 100) HARD-COPIES the online model into the EMA shadow for
#     the first 100 steps (ep.copy_(mp.detach())), not the slow 0.9999 lerp -- so EMA catches
#     up to wherever the resumed model currently is almost immediately, not after thousands
#     of steps decaying from a stale pretrained-base copy. Default warmup is fine, no override.
#   - OOM SAFETY: tonight's two EMA+full-FT OOMs (jobs 21148122/21148584, see
#     fullft_avp_aug.sbatch's post-mortem comment) were BOTH at T=1024 with a raw
#     --batch_size (8, then 4) and no grad-accum. T=256 is 4x shorter (quadratic attention ->
#     ~16x less activation memory) so BS=4 direct is very likely fine, but per that same
#     post-mortem's own lesson ("a config that 'looks small enough' is not evidence until
#     it's actually run") this job still uses the ONE proven-safe pattern instead of trusting
#     the shorter-T argument alone: --batch_size 2 --accumulate_grad_batches 2 (effective 4,
#     matching the ORIGINAL fullft_t256 recipe's batch=4 exactly -- same optimizer-step
#     semantics, just split across 2 micro-batches instead of one).
#
# ── DEPLOYMENT: sa3.sif (NOT multitorch) -- matches ALL THREE original campaigns' own
# choice, kept as-is rather than switching containers mid-run (a Lightning ckpt is
# container-agnostic, but the DiT/MIOpen shape-cache behavior differs across images and
# these arms already proved their shapes hang-free on sa3.sif across their original epochs
# -- MIOPEN_FIND_MODE=2's known hang-on-a-cache-gap risk (SKILL.md Containers section) is
# a per-SHAPE risk, and these exact shapes already have FindDb entries from the original
# run, so the gap that causes the hang shouldn't exist here. Inherited choice, not
# re-litigated.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=47:00:00
#SBATCH --job-name=sa3_continue8
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
mkdir -p "${FLASH}"

# ── code-refresh verification (fails loud, before the node spins up) ──
for FLAG in "--resume_ckpt" "base_precision" "use-ema" "grad-clip-mode"; do
  grep -q -- "${FLAG}" "${CODE}/stable-audio-3/scripts/train_lora.py" \
    || { echo "[continue8] FATAL: train_lora.py missing '${FLAG}' — working-tree code refresh needed (never git archive)"; exit 1; }
done

# ── stage both datasets to NVMe once (idempotent, done by task 0 before srun) ──
for DS in latents_avp latents_sa3; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[continue8] avp latents: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True

# ── arm table — the 8 EXACT named runs Kim asked for ──
case ${ARM} in
  0) FAMILY=fp32cmp; DS=latents_avp; T=4096; BS=4; LR=1e-4; RUNROOT=${SCRATCH}/runs/fp32_compare ;;
  1) FAMILY=fp32cmp; DS=latents_sa3; T=4096; BS=4; LR=1e-4; RUNROOT=${SCRATCH}/runs/fp32_compare ;;
  2) FAMILY=fp32cmp; DS=latents_avp; T=4096; BS=1; LR=1e-4; RUNROOT=${SCRATCH}/runs/fp32_compare ;;
  3) FAMILY=fp32cmp; DS=latents_sa3; T=4096; BS=1; LR=1e-4; RUNROOT=${SCRATCH}/runs/fp32_compare ;;
  4) FAMILY=winning; DS=latents_avp; T=512;  ALPHA=128; RUNROOT=${SCRATCH}/runs/fp32_winning ;;
  5) FAMILY=winning; DS=latents_sa3; T=512;  ALPHA=128; RUNROOT=${SCRATCH}/runs/fp32_winning ;;
  6) FAMILY=fullft;  DS=latents_avp; T=256;  RUNROOT=${SCRATCH}/runs/fullft ;;
  7) FAMILY=fullft;  DS=latents_sa3; T=256;  RUNROOT=${SCRATCH}/runs/fullft ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
DSTAG=$([ "${DS}" = latents_avp ] && echo avp || echo goa)

case ${FAMILY} in
  fp32cmp) LRTAG=$(echo ${LR} | tr -d ".-"); NAME=fp32cmp_${DSTAG}_t${T}_bs${BS}_lr${LRTAG} ;;
  winning) NAME=winning_${DSTAG}_t${T}_a${ALPHA}_fp32 ;;
  fullft)  NAME=fullft_${DSTAG}_t${T} ;;
esac
RUN=${RUNROOT}/${NAME}
[ -d "${RUN}" ] || { echo "[arm ${ARM}] FATAL: ${RUN} missing — run tree moved/pruned?"; exit 1; }

# ── glob the LATEST fat epoch=*.ckpt (excludes .weights slims) — auto-resumes across re-submits ──
FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
[ -n "${FATCKPT}" ] || { echo "[arm ${ARM}] FATAL: no fat epoch=*.ckpt in ${RUN} (pruned to slim-only? resume needs optimizer state)"; exit 1; }
EP_AT=$(basename "${FATCKPT}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
echo "[arm ${ARM}] ${NAME}: resuming from ${FATCKPT} (epoch=${EP_AT} = $((EP_AT+1)) done) -> OPEN-ENDED (no --epochs cap)"

# longform sidecar default (CAPTIONS=stored to disable; SIDECAR/PROBS override) — MUST match
# each arms original recipe for a coherent resume.
if [ "${CAPTIONS:-longform}" = "longform" ] && [ -z "${SIDECAR:-}" ]; then
  SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json
  PROBS=${PROBS:-0,0,1}
fi
sc_args=()
[ -n "${SIDECAR:-}" ] && sc_args=(--caption_sidecar "${SIDECAR}" --caption_probs "${PROBS:-0.6,0.3,0.1}")

# ── fp32 SDPA capability probe (fp32cmp/winning arms only — both fp32; fullft is bf16, skip) ──
if [ "${FAMILY}" != "fullft" ]; then
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

case ${FAMILY} in
  fp32cmp)
    echo "[arm ${ARM}] RESUME ${NAME} DoRA T=${T} BS=${BS} lr=${LR} fp32 -> ${RUN} (open-ended)"
    python ${CODE}/stable-audio-3/scripts/train_lora.py \
      --model medium-base --encoded_dir ${FLASH}/${DS} --save_dir "${RUN}" \
      --adapter_type dora-rows --rank 128 --lora_alpha 128 \
      --optimizer fusion --base_precision fp32 \
      --lr ${LR} --batch_size ${BS} --frames ${T} \
      --resume_ckpt "${FATCKPT}" --checkpoint_every_epochs 1 \
      --num_workers 6 --seed 1 --no_demos --logger csv --name ${NAME} \
      "${sc_args[@]}" 2>&1 | tee -a ${RUN}/train_continue_openended.log
    ;;
  winning)
    echo "[arm ${ARM}] RESUME ${NAME} DoRA T=${T} BS=8 alpha=${ALPHA} fp32 -> ${RUN} (open-ended)"
    python ${CODE}/stable-audio-3/scripts/train_lora.py \
      --model medium-base --encoded_dir ${FLASH}/${DS} --save_dir "${RUN}" \
      --adapter_type dora-rows --rank 128 --lora_alpha ${ALPHA} \
      --optimizer fusion --base_precision fp32 \
      --lr 1e-4 --batch_size 8 --frames ${T} --beat-aware-crop \
      --resume_ckpt "${FATCKPT}" --checkpoint_every_epochs 1 \
      --num_workers 6 --seed 1 --no_demos --logger csv --name ${NAME} \
      "${sc_args[@]}" 2>&1 | tee -a ${RUN}/train_continue_openended.log
    ;;
  fullft)
    echo "[arm ${ARM}] RESUME ${NAME} full-FT T=${T} BS=2 GA=2 (eff 4) bf16 +EMA+AGC -> ${RUN} (open-ended)"
    python ${CODE}/stable-audio-3/scripts/train_lora.py \
      --model medium-base --encoded_dir ${FLASH}/${DS} --save_dir "${RUN}" \
      --full-finetune --optimizer fusion \
      --use-ema --ema-beta 0.9999 --grad-clip-mode agc \
      --lr 1e-4 --batch_size 2 --accumulate_grad_batches 2 --frames ${T} --beat-aware-crop \
      --resume_ckpt "${FATCKPT}" --checkpoint_every_epochs 1 \
      --num_workers 6 --seed 1 --no_demos --logger csv --name ${NAME} \
      "${sc_args[@]}" 2>&1 | tee -a ${RUN}/train_continue_openended.log
    ;;
esac
echo "[arm ${ARM}] arm finished (or timed out — re-submit this SAME script to auto-resume from the new terminal fat)"
'
echo "[continue8] all arms finished:" && ls -la "${SCRATCH}/runs/fp32_compare" "${SCRATCH}/runs/fp32_winning" "${SCRATCH}/runs/fullft" 2>/dev/null
# SUCCESS = per-arm: ${RUN}/train_continue_openended.log tail shows "[resume] strict_loading=False"
# + loss ticking past the pre-existing terminal epoch. NEVER trust sbatch rc — check each log +
# `ls ${RUN}/epoch=*.ckpt | sort -V | tail -1` per arm. Re-submit this SAME script on timeout;
# it auto-resumes every arm from wherever it currently is (no epoch bookkeeping needed).
