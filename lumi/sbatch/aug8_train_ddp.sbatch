#!/bin/bash
# aug8_train_ddp.sbatch — EXPERIMENTAL DRAFT (2026-07-23, unsubmitted, for Kim's
# review): "we should try that out" — instead of 8 independent one-arm-per-GCD runs
# (aug8_train.sbatch), train the aug8 arms ONE AT A TIME using all 8 GCDs as a single
# Lightning DDP group, cutting per-arm wall-clock ~8x. Arms run SERIALLY in one job
# (ARMS list below); first submission should be the single-arm SMOKE TEST
# (default ARMS=fullft_goa_aug8_fp32) — do not expand to more arms until Kim confirms
# DDP actually scales on this stack (untested combination: Lightning DDP + ROCm +
# Singularity + LUMI SLURM).
#
# ── WHAT train_lora.py / LIGHTNING ACTUALLY SUPPORT (verified by reading the code,
# not assumed) ──────────────────────────────────────────────────────────────────────
# `pl.Trainer(devices="auto", accelerator="auto", strategy="auto", ...)` — HARDCODED,
# no CLI flag exists in train_lora.py for devices/strategy/num_nodes (grepped: zero
# hits for --devices/--strategy/--num_nodes in the argparse block). So DDP is NOT
# something you request with a flag — Lightning's "auto" resolution derives it purely
# from how many GPUs are VISIBLE to the process and how many processes are launched:
#   - devices="auto" -> count of GPUs visible to THIS process (via ROCR_VISIBLE_DEVICES
#     / CUDA_VISIBLE_DEVICES, or all of them if unset).
#   - strategy="auto" -> SingleDeviceStrategy if devices resolves to 1, DDPStrategy if
#     devices>1 (or if Lightning detects a multi-process SLURM launch).
#   - Under `srun --ntasks=8`, Lightning auto-detects the SLURM cluster environment
#     (checks SLURM_NTASKS>1) and reads SLURM_PROCID (global rank) / SLURM_LOCALID
#     (local rank -> which of the node's GPUs this process binds) / SLURM_NTASKS
#     (world size) to form the DDP process group — no MASTER_ADDR/MASTER_PORT export
#     needed in the normal case (Lightning's SLURMEnvironment derives them from the
#     job); left unset here deliberately, add them only if the smoke run's rendezvous
#     fails.
#
# ── DELIBERATE EXCEPTION to the lumi-ops ROCR-only single-GCD-pinning rule ─────────
# The standing rule (`export ROCR_VISIBLE_DEVICES=$SLURM_PROCID` ALONE, every other
# sbatch in this tree) exists for the ONE-ARM-PER-GCD pattern: masking each of the 8
# ranks to a different single GPU is what keeps 8 INDEPENDENT training runs from
# colliding on the same device. DDP is the opposite goal — all 8 ranks must be part of
# ONE coordinated process group, so EVERY rank needs the SAME device visible (each
# rank then binds its own GCD via `torch.cuda.set_device(LOCAL_RANK)`, driven by
# Lightning/SLURM, not by us masking visibility per-rank). **This script deliberately
# does NOT export ROCR_VISIBLE_DEVICES=$SLURM_PROCID — that would break DDP outright
# (each rank would see exactly 1 GPU, devices="auto" resolves to 1, Lightning falls
# back to SingleDeviceStrategy, and you get 8 uncoordinated single-GPU trainers
# instead of one 8-way DDP group).** If a future reviewer reflexively "fixes" this
# back to match the other sbatch files, they will silently undo the entire point of
# this experiment — this paragraph is that warning.
# CAVEAT (unverified): SLURM's own `--gpus-per-task=1` binding MAY ALSO restrict
# device visibility per task at the cgroup level regardless of our env exports — if
# the smoke run's per-rank log shows only 1 GPU visible despite the above, the fix is
# `--ntasks=1 --gpus-per-node=8` instead (a single process, letting Lightning spawn
# its own 8 subprocesses via its internal subprocess launcher) — NOT implemented here,
# flagged for the smoke run to reveal which pattern this stack actually needs.
#
# ── EFFECTIVE BATCH SCALING (the choice + a flag, per the ask) ─────────────────────
# DDP_BATCH_MODE=divide (DEFAULT) — per-GCD batch = the arm's proven single-GCD batch
#   DIVIDED by 8 (floor at 1), so GLOBAL batch (per-GCD x 8 GCDs) stays EQUAL to the
#   original single-GCD arm's batch. Same gradient-estimate variance, same optimizer
#   trajectory as the existing aug8_train.sbatch / fp32cmp results — a clean apples-
#   to-apples wall-clock-only comparison. (Division isn't always exact — e.g. a proven
#   BS=4 arm floors to per-GCD BS=1, global=8, NOT 4 — noted per-arm below.)
# DDP_BATCH_MODE=keep — per-GCD batch = the SAME as the single-GCD arm (e.g. DoRA's
#   proven BS=8/GCD x 8 GCDs = global batch 64). Trains MORE data per step (fewer
#   steps/epoch, faster wall-clock on top of the DDP speedup) but is a DIFFERENT
#   experiment from the single-GCD baselines — the effective LR is now under-scaled
#   relative to the 8x larger batch (linear-scaling rule would want ~8x lr); no LR
#   auto-scaling is implemented here, so `keep` mode's results are NOT directly
#   comparable to the aug8_train.sbatch arms without accounting for that.
# fullft-**fp32** arms have NO proven single-GCD batch (aug8_train.sbatch probes them
# too) — DDP_BATCH_MODE is moot for those; they get the SAME 30-step probe ladder,
# just run per-GCD inside the DDP group (each GCD's memory footprint under DDP is the
# same as standalone — no cross-GPU memory sharing — so the probe transfers directly).
#
# ── SEQUENCE / WALLTIME ─────────────────────────────────────────────────────────────
# ARMS (env override, comma-separated, default = smoke test ONE arm):
#   ARMS=${ARMS:-ddp_smoke}
# Arms run SERIALLY, each as its own `srun --ntasks=8` DDP training, inside this one
# allocation. Per-arm wall-clock is expected to drop ~8x vs the single-GCD estimate in
# aug8_train.sbatch (data-parallel, not a re-derivation — same assumption caveats
# apply). Per-epoch checkpoints + auto-resume (globs for an existing fat epoch=*.ckpt
# per arm and passes --resume_ckpt if found, same mechanism as
# fp32cmp_continue_15e.sbatch) mean a timeout here costs only the in-flight epoch — a
# re-submit continues the SAME ARMS list from wherever each one left off.
#
# PREREQS: same as aug8_train.sbatch (latents_sa3.tar.gz, latents_avp.tar.gz,
# latents_goa_aug8.tar.gz on ${SCRATCH}; code tarball refreshed from the WORKING TREE).
# This lane is gated on the SAME open item as aug8_encode.sbatch: bungee_python inside
# sa3.sif is still UNVERIFIED — no real aug8 latents exist to smoke-test against until
# that's resolved (see docs/superpowers/specs/2026-07-23-aug8-15ep-campaign.md).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=sa3_aug8_train_ddp
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/aug8_train_ddp
mkdir -p "${RUNROOT}" "${FLASH}"

ARMS=${ARMS:-ddp_smoke_dora}   # comma-separated; default = DoRA-bf16-T512 smoke (data-independent, fits a 64GB GCD — the fullft-fp32 'ddp_smoke' OOM'd job 20176284; corrected CONTINUITY 2026-07-29)
DDP_BATCH_MODE=${DDP_BATCH_MODE:-divide}   # divide (default) | keep — see header

# ── stage datasets to NVMe once ──
NEED_AUG8=1; [[ "${ARMS}" == ddp_smoke* ]] && NEED_AUG8=0
NEED_AVP=1; [[ "${ARMS}" == ddp_smoke* ]] && NEED_AVP=0
for DS in $([ "${NEED_AVP}" = "1" ] && echo latents_avp) latents_sa3 $([ "${NEED_AUG8}" = "1" ] && echo latents_goa_aug8); do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[aug8-ddp] avp: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)  goa_aug8: $(ls ${FLASH}/latents_goa_aug8/*.npy 2>/dev/null | wc -l)"
echo "[aug8-ddp] ARMS=${ARMS} DDP_BATCH_MODE=${DDP_BATCH_MODE}"

IFS=',' read -ra ARM_LIST <<< "${ARMS}"
for ARMNAME in "${ARM_LIST[@]}"; do
  echo "[aug8-ddp] ==== starting arm: ${ARMNAME} ===="

  # ── arm registry: DSTAG/DS/MODE/PREC/PROVEN_BS (single-GCD reference; "probe" if none) ──
  case ${ARMNAME} in
    ddp_smoke)            DSTAG=goa; DS_SUFFIX=smoke; MODE=fullft; PREC=fp32; PROVEN_BS=4;    ;;
    ddp_smoke_dora)       DSTAG=goa; DS_SUFFIX=smoke; MODE=dora;   PREC=bf16; PROVEN_BS=8;    ;;
    dora_goa_aug8_fp32)   DSTAG=goa; DS_SUFFIX=goa;  MODE=dora;   PREC=fp32; PROVEN_BS=8;     ;;
    dora_goa_aug8_bf16)   DSTAG=goa; DS_SUFFIX=goa;  MODE=dora;   PREC=bf16; PROVEN_BS=8;     ;;
    fullft_goa_aug8_fp32) DSTAG=goa; DS_SUFFIX=goa;  MODE=fullft; PREC=fp32; PROVEN_BS=probe; ;;
    fullft_goa_aug8_bf16) DSTAG=goa; DS_SUFFIX=goa;  MODE=fullft; PREC=bf16; PROVEN_BS=4;     ;;
    dora_avp_fp32)        DSTAG=avp; DS_SUFFIX=avp;  MODE=dora;   PREC=fp32; PROVEN_BS=8;     ;;
    dora_avp_bf16)        DSTAG=avp; DS_SUFFIX=avp;  MODE=dora;   PREC=bf16; PROVEN_BS=8;     ;;
    fullft_avp_fp32)      DSTAG=avp; DS_SUFFIX=avp;  MODE=fullft; PREC=fp32; PROVEN_BS=probe; ;;
    fullft_avp_bf16)      DSTAG=avp; DS_SUFFIX=avp;  MODE=fullft; PREC=bf16; PROVEN_BS=4;     ;;
    *) echo "[aug8-ddp] FATAL: unknown arm name '${ARMNAME}'"; exit 1 ;;
  esac
  if [ "${DS_SUFFIX}" = "smoke" ]; then
    DS="${FLASH}/latents_sa3"          # DATA-INDEPENDENT: existing goa latents, no aug8 needed
  elif [ "${DS_SUFFIX}" = "goa" ]; then
    DS="${FLASH}/latents_sa3,${FLASH}/latents_goa_aug8"
  else
    DS="${FLASH}/latents_avp"
  fi
  LR=1e-4
  T=512
  EPOCHS_ARM=15
  # smoke = mechanics only: 8 ranks form one DDP group, loss steps, one ckpt written.
  [[ "${ARMNAME}" == ddp_smoke* ]] && EPOCHS_ARM=2
  # MUST be exported: the inner srun/singularity bash references ${EPOCHS_ARM} in a command
  # substitution; un-exported + set -u the substitution dies SILENTLY EMPTY -> train runs with
  # NO --epochs cap (job 20413874: 2-epoch smoke ran open-ended for 3h+).
  export EPOCHS_ARM
  RUN=${RUNROOT}/aug8ddp_${ARMNAME}
  mkdir -p "${RUN}"

  # ── auto-resume: if this arm already has a fat epoch=*.ckpt (a prior partial run
  # in THIS RUNROOT), resume it instead of starting over (same mechanism as
  # fp32cmp_continue_15e.sbatch — --resume_ckpt is a TRUE Lightning resume). Passed
  # as a plain string (not a bash array) so it survives the quote boundary into the
  # nested srun/singularity bash -c string cleanly — fine as long as ${RUN} has no
  # spaces, true for every $SCRATCH path in this repo's convention.
  FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
  RESUME_FLAG=""
  if [ -n "${FATCKPT}" ]; then
    echo "[aug8-ddp] ${ARMNAME}: resuming from ${FATCKPT}"
    RESUME_FLAG="--resume_ckpt ${FATCKPT}"
  fi
  export RESUME_FLAG   # picked up unquoted (word-split) inside the srun/singularity
                        # bash -c script below — NOT string-interpolated across the
                        # quote boundary, so a 0-or-2-word value both work correctly

  # ── per-GCD batch: divide/keep for proven-BS arms, probe ladder for fullft-fp32 ──
  if [ "${PROVEN_BS}" = "probe" ]; then
    BS_MODE=probe
  elif [ "${DDP_BATCH_MODE}" = "divide" ]; then
    BS=$(( PROVEN_BS / 8 )); [ "${BS}" -lt 1 ] && BS=1
    echo "[aug8-ddp] ${ARMNAME}: DDP_BATCH_MODE=divide, proven single-GCD BS=${PROVEN_BS} -> per-GCD BS=${BS} (global=$((BS*8)))"
  else
    BS=${PROVEN_BS}
    echo "[aug8-ddp] ${ARMNAME}: DDP_BATCH_MODE=keep, per-GCD BS=${BS} (global=$((BS*8)), 8x the single-GCD baseline's batch — NOT lr-scaled)"
  fi

  # NO --gpus-per-task=1 here (unlike every one-arm-per-GCD sbatch): SMOKE 20413874 PROVED it
  # cgroup-isolates each task to 1 GPU -> Lightning devices="auto" resolves to 1 -> falls back
  # to SingleDeviceStrategy -> 8 UNCOORDINATED duplicate trainers (tell: epoch=...-v1..-v7
  # versioned ckpts = N writers; no "Initializing distributed"/world-size lines). DDP needs all
  # tasks to share node-level GPU visibility; Lightning's SLURMEnvironment reads
  # SLURM_PROCID/LOCALID to bind each rank to its GCD.
  srun --nodes=1 --ntasks=8 --gpus-per-node=8 --cpus-per-task=7 \
    singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
# DELIBERATE: no ROCR_VISIBLE_DEVICES pinning here — see the header comment. Every
# rank must see all 8 GCDs for Lightning/SLURM to form one DDP group.
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
# per-rank MIOpen /tmp dir keyed on SLURM_LOCALID (the local GCD index under DDP,
# not SLURM_PROCID which is the same across ranks on one node here — actually
# equal to SLURM_PROCID for a single-node job; kept for clarity/consistency)
export MIOPEN_USER_DB_PATH=/tmp/miopen-${SLURM_PROCID} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${SLURM_PROCID}
rm -rf "${MIOPEN_USER_DB_PATH}"; mkdir -p "${MIOPEN_USER_DB_PATH}"

if [ "'"${PREC}"'" = "fp32" ]; then
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
  else
    export SA3_SDPA_CAST_BF16=1
  fi
  echo "[rank ${SLURM_PROCID}] attention: SA3_SDPA_CAST_BF16=${SA3_SDPA_CAST_BF16}"
fi

if [ "${CAPTIONS:-longform}" = "longform" ] && [ -z "${SIDECAR:-}" ]; then
  SIDECAR=${CODE}/lumi/'"${DSTAG}"'_longform_sidecar.json
  PROBS=${PROBS:-0,0,1}
fi
sc_args=()
[ -n "${SIDECAR:-}" ] && sc_args=(--caption_sidecar "${SIDECAR}" --caption_probs "${PROBS:-0.6,0.3,0.1}")
mode_args=()
if [ "'"${MODE}"'" = "fullft" ]; then
  mode_args=(--full-finetune)
else
  mode_args=(--adapter_type dora-rows --rank 128 --lora_alpha 128)
fi
prec_args=()
[ "'"${PREC}"'" = "fp32" ] && prec_args=(--base_precision fp32)

train_ddp() {  # train_ddp <batch> <steps-or-empty> [extra args...]
  local B=$1 STEPS=$2; shift 2
  python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --devices 8 \
    --encoded_dir '"${DS}"' \
    --save_dir "'"${RUN}"'" \
    "${mode_args[@]}" \
    --optimizer fusion \
    "${prec_args[@]}" \
    --lr '"${LR}"' --batch_size ${B} \
    --frames '"${T}"' --beat-aware-crop \
    ${STEPS:+--steps ${STEPS}} \
    $([ -z "${STEPS}" ] && echo "--epochs ${EPOCHS_ARM} --checkpoint_every_epochs 1") \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name aug8ddp_'"${ARMNAME}"' \
    "${sc_args[@]}" "$@"
}

if [ "'"${BS_MODE:-}"'" = "probe" ]; then
  for CAND in 4 3 2 1; do
    echo "[rank ${SLURM_PROCID}] probing per-GCD BS=${CAND} (30 steps, DDP)"
    if train_ddp ${CAND} 30 --save_dir "'"${RUN}"'_probe${CAND}" 2>&1 | tee /tmp/probe_${SLURM_PROCID}_${CAND}.log; then
      BS=${CAND}; echo "[rank ${SLURM_PROCID}] probe OK at BS=${BS}"; break
    fi
  done
  [ -z "${BS:-}" ] && { echo "[rank ${SLURM_PROCID}] FAILED: even BS=1 OOMs under DDP"; exit 0; }
else
  BS='"${BS:-1}"'
fi

echo "[rank ${SLURM_PROCID}] TRAIN DDP '"${ARMNAME}"' BS(per-GCD)=${BS} -> '"${RUN}"'"
# RESUME_FLAG is inherited from the outer script'"'"'s export (0 or 2 words: empty,
# or "--resume_ckpt <path>") — unquoted here so it word-splits correctly either way.
train_ddp ${BS} "" ${RESUME_FLAG:-} 2>&1 | tee -a '"${RUN}"'/train_rank${SLURM_PROCID}.log
'
  echo "[aug8-ddp] ==== arm ${ARMNAME} done (or failed — check ${RUN}/train_rank*.log) ===="
done

echo "[aug8-ddp] ALL ARMS FINISHED (${ARMS}):" && ls -la "${RUNROOT}"
# SUCCESS: rank-0's log should show ONE trainer with world_size=8 (not 8 separate
# world_size=1 trainers — that would mean DDP didn't actually form, see the
# CAVEAT above), loss lines tick once per GLOBAL step (not once per rank), one set
# of per-epoch ckpts per arm (not 8). sbatch rc 0 proves nothing — read the logs.
