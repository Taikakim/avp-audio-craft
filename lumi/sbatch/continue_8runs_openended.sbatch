#!/bin/bash
# continue_8runs_openended.sbatch — CONTINUITY 2026-08-15 (Kim direct): resume 8 specific
# named runs on ONE node (8 GCDs, one arm each), open-ended (NO --epochs cap — Kim: "maybe
# it's interesting to go on past 60, for style transfers overtrained models can be very
# good... continue from last epoch of each"). Combines THREE previously-separate campaigns
# that share one deployment (lumi-multitorch-full — MIGRATED from sa3.sif, see below —
# same latents_avp/latents_sa3):
#   arms 0-3: fp32cmp DoRA arms      (precedent: fp32cmp_continue_15e.sbatch, DRAFT/unconfirmed-run)
#   arms 4-5: winning DoRA arms      (precedent: efp_fp32_winning_continue40.sbatch)
#   arms 6-7: fullft_t256 full-FT    (precedent: efp_fullft_short.sbatch; NEW this run: EMA+AGC)
#
# ── OPEN-ENDED, NOT A FIXED TARGET (Kim direct) ── CORRECTED 2026-08-16 after job 21161063
# proved the first version wrong: omitting --epochs does NOT give unlimited training.
# train_lora.py's Trainer construction is `max_steps=(-1 if args.epochs else args.steps)` --
# an omitted --epochs falls through to max_steps=args.steps, and --steps DEFAULTS TO 10000.
# So the first submit capped every arm at step 10000 regardless of epoch progress, and since
# arms RESUME from wherever they left off, 6 of 8 arms had already passed step 10000 and did
# ZERO additional training for the full 2h40m job (only fp32cmp_avp_t4096_bs4_lr1e4 and
# fullft_avp_t256, both resumed below 10000, made real progress before also hitting the cap).
# FIX: pass an explicit huge --epochs instead of omitting it -- makes args.epochs truthy
# (-> max_steps=-1, no step cap) AND gives Lightning a concrete max_epochs instead of None
# (sidesteps Lightning's OWN separate "both max_epochs and max_steps unset -> defaults to
# 1000" fallback, which omitting --epochs would otherwise land on ambiguously).
# --epochs 100000 is effectively unlimited for any realistic run while being unambiguous in
# both places. Re-submit this same script to keep extending past a walltime timeout
# (FATCKPT glob below auto-picks up wherever each arm left off — same auto-resume pattern
# as every other continue script this session).
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
# ── DEPLOYMENT: MIGRATED to lumi-multitorch-full (2026-08-15, Kim direct) -- these three
# campaigns were the last ones still on legacy sa3.sif, purely by inherited precedent, not
# because sa3.sif is actually better for them. sa3.sif's flash-attn wheel targets gfx1201
# (the desktop RDNA4 card) and CANNOT run on LUMI's gfx90a (MI250X) -- architecturally
# incompatible, not a missing pip install (docs/lumi-transition-plan.md flagged this exact
# gap before tonight). lumi-multitorch-full ships a REAL prebuilt gfx90a flash-attn,
# already proven in production (the caption pipeline, WORKLOG 2026-07-30) and already the
# deployment every OTHER script this session uses (fullft_avp_aug.sbatch,
# subloss_goa_k20_fullft.sbatch, fullft_mixed_avp_goa_t4096.sbatch). Verified BEFORE
# migrating, not assumed: varlen kernels (flash_attn_varlen_func) confirmed importable in
# sa3_train_venv_mt on LUMI (Kim ran the check, printed 1) -- so this gets both plain FA2 AND
# varlen for free, no from-scratch CK compile needed (that was the OTHER option in the
# transition plan, GPU_ARCHS=gfx90a rebuild -- not required since LUMI's own image already
# has it; and note a GPU_ARCHS=gfx90a rebuild of OUR wheel was never possible anyway -- our CK
# recipe is on the RDNA-only rdna_fmha_gfx1100_gfx1201 branch, no CDNA kernels to compile).
#
# BACKEND + VERSION, corrected 2026-08-17 (F, scanned inside the container): the backend IS CK
# -- 9044 gfx90a + 42721 gfx950 code objects, 205k ck_tile strings -- with the Triton path
# bundled ALONGSIDE it, which is why FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE is load-bearing:
# both are present and the env var picks. BUT this block used to say "flash-attn 2.8.4" and
# that is now WRONG: the newest image (20260807) carries 2.8.3+lumi_aif_gfx90a_b664ea0. It WAS
# 2.8.4 in the Mar-May builds and moved BACKWARDS on 2026-07-31, while the `sort | tail -1`
# resolver below silently follows whatever LUMI ships newest -- so a campaign straddling that
# date changed attention backend mid-flight with no diff and no log line. Do not restate a
# version here without re-reading the image's dist-info. Full table: lumi-ops SKILL.md.
#
# RESIDUAL UNVERIFIED RISK: no script this session has yet run --adapter_type dora-rows on
# multitorch (every prior multitorch script here was --full-finetune) -- arms 0-5 (DoRA) are
# the first test of that combo. Should just work (stable-audio-3's LoRA/DoRA code is pure
# PyTorch, no extra deps beyond what full-FT already needs, and PYTHONPATH points at the same
# ${CODE}/stable-audio-3 regardless of container) but WATCH the first "LoRA config: rank=..."
# print + first successful step on arms 0-5 rather than assuming zero risk.
#
# MIOpen env DROPPED vs the sa3.sif version: MIOPEN_FIND_MODE=2 (the FAST-mode hang-on-a-
# cache-gap bug is a sa3.sif/ROCm-6.2 MIOpen defect -- multitorch's newer MIOpen doesn't have
# it, confirmed by every multitorch script tonight running clean without it) and
# MIOPEN_DISABLE_CACHE=1 (multitorch scripts redirect MIOPEN_USER_DB_PATH/
# MIOPEN_CUSTOM_CACHE_DIR to a real bound /tmp instead, which avoids the Lustre-SQLite-open
# failure without disabling caching outright -- same pattern as every other multitorch
# script). FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ADDED (must be set before `import torch`/
# `flash_attn` or the wrapper silently routes to the slow Triton-AMD fallback instead of CK).
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
EPOCHS_TARGET=${EPOCHS_TARGET:-100000}
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
MODELS=${PROJ}/models
mkdir -p "${FLASH}"

# ── code-refresh verification (fails loud, before the node spins up) ──
[ -n "${SIF}" ] || { echo "[continue8] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[continue8] FATAL: ${VENV} missing"; exit 1; }
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

VENV='"${VENV}"'; source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

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
echo "[arm ${ARM}] ${NAME}: resuming from ${FATCKPT} (epoch=${EP_AT} = $((EP_AT+1)) done) -> target '"${EPOCHS_TARGET}"' epochs (effectively open-ended)"

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
      --resume_ckpt "${FATCKPT}" --epochs '"${EPOCHS_TARGET}"' --checkpoint_every_epochs 1 \
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
      --resume_ckpt "${FATCKPT}" --epochs '"${EPOCHS_TARGET}"' --checkpoint_every_epochs 1 \
      --num_workers 6 --seed 1 --no_demos --logger csv --name ${NAME} \
      "${sc_args[@]}" 2>&1 | tee -a ${RUN}/train_continue_openended.log
    ;;
  fullft)
    # --weight_decay 0.1 added post-submit (2026-08-15, Kim direct) -- the FIRST version of
    # this arm shipped without it, defaulting FusionOpt spectral_wd to 0.01 (too weak for
    # a full-FT run per the 2026-08-10 drone-runaway incident). --grad-clip-mode agc is a
    # separate, orthogonal mechanism (per-step grad clip) and does nothing to counteract
    # multi-epoch weight-norm creep -- confirmed via the sibling fullft_mixed_avp_goa_t4096
    # run pulled ep0 z0.npy renders (literal numerical inf at cfg7/16, same CFG-amplified
    # instability shape as the confirmed-corrupted precision_ladder_t256_bf16mixed
    # dronesweep). This arm own progress from job 21155599 first (unfixed) submit should
    # be checked before trusting its ckpts -- see if it shows the same signature.
    echo "[arm ${ARM}] RESUME ${NAME} full-FT T=${T} BS=2 GA=2 (eff 4) bf16 +EMA+AGC+WD0.1 -> ${RUN} (open-ended)"
    python ${CODE}/stable-audio-3/scripts/train_lora.py \
      --model medium-base --encoded_dir ${FLASH}/${DS} --save_dir "${RUN}" \
      --full-finetune --optimizer fusion \
      --use-ema --ema-beta 0.9999 --grad-clip-mode agc --weight_decay 0.1 \
      --lr 1e-4 --batch_size 2 --accumulate_grad_batches 2 --frames ${T} --beat-aware-crop \
      --resume_ckpt "${FATCKPT}" --epochs '"${EPOCHS_TARGET}"' --checkpoint_every_epochs 1 \
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
