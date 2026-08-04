#!/bin/bash
# aug8_train.sbatch — DRAFT (2026-07-23, unsubmitted, for Kim's review): stage 2 of
# the aug8 campaign (docs/superpowers/specs/2026-07-23-aug8-15ep-campaign.md; renamed
# from aug10 -> aug8 per Kim's ruling — variant set now matches
# mir/src/tools/augment_tracks.py exactly, 8 not 10 variants/crop).
# One standard-g node, 8 GCDs, 8 independent single-GCD arms driven by SLURM_PROCID
# (the ONE-ARM-PER-GCD lane — see the sibling aug8_train_ddp.sbatch for the
# EXPERIMENTAL 8-way-DDP-per-arm alternative Kim asked to try for the walltime risk).
# Skeleton = efp_fp32_compare.sbatch (proven multi-arm one-task-per-GCD pattern);
# fullft flag/behavior = efp_fullft_short.sbatch / efp_fullft_t4096.sbatch. Read those
# three for the deployment rationale this file doesn't re-explain.
#
# DESIGN (Kim's 2026-07-23 listening verdicts, docs/training-findings.md): fp32 +
# full-finetune sound better than bf16 / adapter-only; rank helps; augmentation SEEMS
# to help; 15 EPOCHS is the new default target (models "start to sound fine after ep5,
# often ep7 is first really good" — prior 8-ep runs were stopping at the threshold of
# good). This campaign crosses the aug8 augmented GOA corpus (+ the EXISTING avp aug
# set, see DATASET PATHS — RESOLVED below) against the two axes Kim's verdict just
# settled (precision, full-ft-vs-adapter), all at 15 epochs, so the next listening pass
# can read off aug's effect ALONGSIDE the precision/rank effect rather than re-deriving
# it separately. GOA-aug8 x AVP(existing aug) x {DoRA-r128, fullft} x {fp32, bf16} =
# 8 arms, all --frames 512 (T=512, Kim's T-frames convention, MASTER.md §5) with
# --beat-aware-crop.
#
# Arms:
#   PROCID 0: goa-aug8  DoRA-r128  fp32  T=512  BS=8            lr=1e-4
#   PROCID 1: goa-aug8  DoRA-r128  bf16  T=512  BS=8            lr=1e-4
#   PROCID 2: goa-aug8  fullft     fp32  T=512  BS=probe(4->1)  lr=1e-4
#   PROCID 3: goa-aug8  fullft     bf16  T=512  BS=4            lr=1e-4
#   PROCID 4: avp       DoRA-r128  fp32  T=512  BS=8            lr=1e-4
#   PROCID 5: avp       DoRA-r128  bf16  T=512  BS=8            lr=1e-4
#   PROCID 6: avp       fullft     fp32  T=512  BS=probe(4->1)  lr=1e-4
#   PROCID 7: avp       fullft     bf16  T=512  BS=4            lr=1e-4
#
# LR / RANK / ALPHA convention (grepped from efp_fp32_compare.sbatch, efp_bf16_twin.sbatch,
# efp_fullft_short/t4096.sbatch — all four agree): lr **1e-4** for every arm (DoRA and
# fullft alike; no family here trains at 5e-5); DoRA = `--adapter_type dora-rows --rank
# 128 --lora_alpha 128` (alpha=rank, s=1, MASTER §5 convention); fullft = `--full-finetune`
# (unfreezes the whole 1.4B DiT, injects NO adapter, mutually exclusive with the rank/
# adapter flags). `--optimizer fusion` throughout (established default across all four
# reference sbatches).
#
# BATCH SIZE: DoRA-r128 T=512 BS=8 is PROVEN (efp_fp32_compare arms 4/5, efp_bf16_twin
# arms 0/1 — same T, same rank, both precisions, no probe needed). fullft bf16 T=512
# BS=4 is PROVEN (efp_fullft_short.sbatch arm 2/3: "batch 4 fits T=256/512/1024/2048
# with headroom", no probe). fullft **fp32** T=512 has NO direct precedent (fp32
# fullft was only ever run at T=4096 BS=2 ga=2, a different context length) — fp32
# roughly doubles the full-model param+grad+optimizer-state footprint vs bf16, so
# arms 2/6 get the proven 30-step batch PROBE (efp_fp32_compare's 4->3->2->1 ladder,
# extended down to 1 since a whole-DiT fp32 optimizer state is heavier than a DoRA
# adapter's) rather than assuming BS=4 blindly.
#
# EPOCH-TIME ESTIMATE — ASSUMPTION, NOT MEASURED (10-min grep of WORKLOG/journals
# found no per-epoch T=512/aug8 timing; the one hard number available is
# docs/training-findings.md's "~2.4 s/step" for SA3 DoRA at T~512 BS1, and
# efp_fp32_compare's own note that its T=4096 BS1 goa arm — 5400 steps/epoch, ~2-4
# s/step — "may hit the 48h wall around epoch 5-8"). Reasoning chain: GOA-aug8 is
# ~5400 orig + up to 5400x8=43200 aug crops (BPM-cap dedup likely trims the average
# below 8/crop slightly) ≈ **~43-48k crops**. At BS=8, T=512 (8x shorter context than
# the T=4096 arm above, so materially cheaper per step despite ~8x more crops and 8x
# the batch — steps/epoch ≈ 45000/8 ≈ 5600, roughly the SAME step COUNT as the
# T=4096/BS1 arm's 5400, but each step should be substantially cheaper at T=512):
# **DoRA arms: order ~1-2h/epoch -> 15-30h for 15 epochs (fits the 47h wall).**
# fullft arms do more work per step (whole-DiT backward + bigger optimizer) at a
# SMALLER batch (4 or probed-down), i.e. MORE steps/epoch than DoRA -> **fullft bf16:
# order ~2-4h/epoch -> 30-60h; fullft fp32 (smallest probed batch): likely the
# arm(s) that DON'T finish 15 epochs in one 47h job.** Per-epoch checkpoints (below)
# make partial completion useful regardless — re-submit with --resume_ckpt to
# continue past a wall-clock cutoff, OR see aug8_train_ddp.sbatch (Kim's requested
# DDP experiment: same 8 GCDs applied to ONE arm at a time instead of 8 arms in
# parallel, ~8x less wall-clock per arm). AVP arms (2393 base crops, ~10-20x smaller
# than GOA-aug8's) will finish 15 epochs comfortably early and idle their GCD —
# acceptable, matches the fp32cmp/fullft campaigns' own convention.
#
# DATASET PATHS — RESOLVED (Kim's ruling, 2026-07-23):
#   GOA-aug8 = original goa crops + the aug8 output from aug8_encode.sbatch, as TWO
#   comma-separated --encoded_dir sources (train_lora.py supports multi-source
#   --encoded_dir/--caption_sidecar natively):
#     ${FLASH}/latents_sa3,${FLASH}/latents_goa_aug8
#   AVP: reuse the EXISTING latents_avp aug set AS-IS — no new avp augmentation is
#   generated for this campaign. (This also makes the earlier open question — the
#   `latents_avp_aug10` naming collision with the 320-crop small-set control from
#   docs/superpowers/specs/2026-07-22-winning-fp32-run-plan.md — MOOT: nothing here
#   writes to or reads that path.)
#
# CAPTIONS: inherited default (longform sidecars, PROBS=0,0,1) — same override knobs
# as efp_fp32_compare.sbatch (CAPTIONS=stored, SIDECAR=, PROBS=). Augmented crops carry
# their PARENT crop's inherited prompt (see encode_aug_task.py) so the sidecar's
# per-source-track lookup still resolves for them.
#
# CAVEAT — beat-aware crop on augmented latents: --beat-aware-crop falls back to
# uniform-random sub-cropping for any latent lacking a sibling .TIMESERIES.npz
# (dataset.py, confirmed) — the aug8 latents from encode_aug_task.py do NOT carry
# one (not built in this draft). So the original 5400 goa crops (and existing avp
# crops) get true beat-aligned T=512 sub-crops; the aug8 variants get uniform-random
# ones. Flagged as an open question in the campaign spec, not fixed here.
#
# PREREQS: code+SIF+models pre-staged; latents_sa3.tar.gz + latents_avp.tar.gz (existing)
# AND latents_goa_aug8.tar.gz (aug8_encode.sbatch output) on ${SCRATCH}; code tarball
# refreshed from the WORKING TREE (never `git archive` — lumi-ops rule) so
# scripts/train_lora.py carries --full-finetune and --frames.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=47:00:00
#SBATCH --job-name=sa3_aug8_train
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/aug8_train
mkdir -p "${RUNROOT}" "${FLASH}"

# ── stage datasets to NVMe once (idempotent, done by task 0 before srun) ──
for DS in latents_avp latents_sa3 latents_goa_aug8; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[aug8-train] avp: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)  goa_aug8: $(ls ${FLASH}/latents_goa_aug8/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/aug8_train

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

# ── dataset paths (see the DATASET PATHS - RESOLVED header comment) ──
DS_GOA=${FLASH}/latents_sa3,${FLASH}/latents_goa_aug8
DS_AVP=${FLASH}/latents_avp

# ── arm table ────────────────────────────────────────────────────────────────
case ${ARM} in
  0) DSTAG=goa; DS=${DS_GOA}; MODE=dora;   PREC=fp32; BS=8;     ;;
  1) DSTAG=goa; DS=${DS_GOA}; MODE=dora;   PREC=bf16; BS=8;     ;;
  2) DSTAG=goa; DS=${DS_GOA}; MODE=fullft; PREC=fp32; BS=probe; ;;
  3) DSTAG=goa; DS=${DS_GOA}; MODE=fullft; PREC=bf16; BS=4;     ;;
  4) DSTAG=avp; DS=${DS_AVP}; MODE=dora;   PREC=fp32; BS=8;     ;;
  5) DSTAG=avp; DS=${DS_AVP}; MODE=dora;   PREC=bf16; BS=8;     ;;
  6) DSTAG=avp; DS=${DS_AVP}; MODE=fullft; PREC=fp32; BS=probe; ;;
  7) DSTAG=avp; DS=${DS_AVP}; MODE=fullft; PREC=bf16; BS=4;     ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
LR=1e-4
LRTAG=$(echo ${LR} | tr -d ".-")
T=512

# longform sidecar default (CAPTIONS=stored to disable; SIDECAR/PROBS override)
if [ "${CAPTIONS:-longform}" = "longform" ] && [ -z "${SIDECAR:-}" ]; then
  SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json
  PROBS=${PROBS:-0,0,1}
fi

# ── fp32 SDPA capability probe (fp32 arms only — 0,2,4,6; cheap, once per arm) ──
if [ "${PREC}" = "fp32" ]; then
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
    echo "[arm ${ARM}] attention: bf16 island (fused fp32 unsupported)"
  fi
fi

train() {  # train <batch> <steps-or-empty> <savedir> [extra args...]
  local B=$1 STEPS=$2 SAVE=$3; shift 3
  local sc_args=()
  if [ -n "${SIDECAR:-}" ]; then
    sc_args=(--caption_sidecar "${SIDECAR}" --caption_probs "${PROBS:-0.6,0.3,0.1}")
  fi
  local prec_args=()
  [ "${PREC}" = "fp32" ] && prec_args=(--base_precision fp32)
  local mode_args=()
  if [ "${MODE}" = "fullft" ]; then
    mode_args=(--full-finetune)
  else
    mode_args=(--adapter_type dora-rows --rank 128 --lora_alpha 128)
  fi
  python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${DS} \
    --save_dir "${SAVE}" \
    "${mode_args[@]}" \
    --optimizer fusion \
    "${prec_args[@]}" \
    --lr ${LR} --batch_size ${B} \
    --frames ${T} --beat-aware-crop \
    ${STEPS:+--steps ${STEPS}} \
    $([ -z "${STEPS}" ] && echo "--epochs 15 --checkpoint_every_epochs 1") \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name aug8_${DSTAG}_${MODE}_${PREC}_t${T}_lr${LRTAG} \
    "${sc_args[@]}" "$@"
}

# ── batch probe (fullft fp32 arms only): 30-step dry run, largest survivor wins ──
if [ "${BS}" = "probe" ]; then
  for CAND in 4 3 2 1; do
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
  if [ "${BS}" = "probe" ]; then echo "[arm ${ARM}] FAILED: even BS=1 OOMs — arm abandoned"; exit 0; fi
fi

RUN=${RUNROOT}/aug8_${DSTAG}_${MODE}_${PREC}_t${T}_bs${BS}
mkdir -p "${RUN}"
echo "[arm ${ARM}] TRAIN ${DSTAG} ${MODE} ${PREC} T=${T} BS=${BS} lr=${LR} 15ep -> ${RUN}"
if train ${BS} "" "${RUN}" 2>&1 | tee ${RUN}/train.log; then
  echo "[arm ${ARM}] DONE"
else
  echo "[arm ${ARM}] TRAIN FAILED — see ${RUN}/train.log (siblings unaffected)"
fi
'
echo "[aug8-train] all arms finished:" && ls -la "${RUNROOT}"
# SUCCESS: each arm prints its resolved MODE/PREC/BS, loss lines tick, per-epoch ckpts
# land under ${RUNROOT}/aug8_*/. sbatch rc 0 proves nothing about individual arms —
# check each RUN/train.log tail + ckpt count vs 15.
