#!/bin/bash
# lr5e5_allsets.sbatch — Kim direct 2026-08-22, after auditioning
# renders/length_variant/adamw_goa_t512_bs4_lr5e5__ep9__cfg16__w100__*: "the 5e-5 clips sound
# better than 1e-4, 2e-4 shows degradation, and where 1e-4/2e-4 MELT at cfg16/w2 the 5e-5 can
# take that push and still sound musical — which speaks to some deeper very healthy structure."
# => REPLICATE THAT RUN'S RECIPE IN FULL, across every sound set we have, to ep48.
#
# THE RUN BEING REPLICATED: runs/adamw_bf16_sweep/adamw_goa_t512_bs4_lr5e5 (arm 7 of
# efp_adamw_bf16_sweep.sbatch, 2026-07-24). Its ACTUAL settings, read off run_meta + sbatch:
#   dora-rows r128 ALPHA 128 (not 45), AdamW wd0.01 betas[0.9,0.95], lr 5e-5 CONSTANT (no
#   schedule), bf16, T=512 beat-aware, goa longform sidecar at caption tiers 0,0,1 (t3 ONLY),
#   NO warmup flag, seed 1 -- and batch 4 on ONE GCD, i.e. EFFECTIVE BATCH 4. That sweep ran
#   8 independent single-GCD arms off SLURM_PROCID; it was never DDP.
# TWO DELIBERATE DEVIATIONS, both forced, both recorded so nobody reads this as a pure replicate:
#   1. EFFECTIVE BATCH 8, not 4. Single-GCD at eff-4 puts a ~21.6k-crop mix at ~110 min/epoch =
#      88 h to ep48, which does not fit the allocation. 8-way DDP at BS=1 is the closest
#      reachable regime (eff 8 = 2x, vs eff 32 if we kept BS=4 across 8 ranks = 8x and a
#      different experiment). lr stays 5e-5 -- the variable Kim isolated.
#   2. MIXED CORPUS, not goa alone (that is the point of the run).
# NOT A DEVIATION, deliberately kept: alpha 128, constant lr, T512, beat-aware, t3-only goa
# captions. The dorlor lane uses alpha 45 / WSD / T256 / 0.6,0.3,0.1 -- copying it here would
# have changed four things at once and thrown away what Kim actually heard.
#
# CORPUS MIX (--encoded_dir order; per-source sidecars + per-source caption tiers):
#   goa     latents_sa3          5400   w 1.00   goa_longform_sidecar          0,0,1
#   bigset  latents_goa_bigset  12524   w 0.18   goa_bigset_hinted_bylatent    0,0,1
#   avpaug  latents_avp          ~2400  w 1.00   avp_captions_tiered           0,0.9,0.1
#   suomi   suomisoundi_latents   1261   w 1.00   suomisoundi_caption_sidecar   0.25,0.45,0.30
# BIGSET WEIGHT: Kim asked for "maybe 20% chance because it's got mp3 sources more than the
# others". Natural proportion would be 58%; w=0.18 lands it at ~20% of draws. It also rides
# tiers 0,0,1 because its granite tier measured NOT GROUNDED (folder-name derived, rare-term
# recall 1.24x vs chance) -- per-source probs exist precisely so that cannot poison the mix.
#
# AUG=1: appends latents_goa_aug8 (3941 bungee-augmented goa crops) as a 5th source, sharing
# the goa sidecar -- the same clean+aug pairing aug8_train_ddp.sbatch used. NOTE: train_lora's
# --augment is live-encode ONLY ("No effect on --encoded_dir"), so there is no on-the-fly
# augmentation available on the pre-encoded latent path. Pre-augmented dirs are the only route.
#
# WARM=<ckpt|liked>: CONTINUE FROM the model Kim actually liked instead of re-learning it.
# WARM=liked resolves to adamw_bf16_sweep/adamw_goa_t512_bs4_lr5e5/epoch=9-step=13500.ckpt.
# It is a clean Lightning 2.6.5 save (epoch 9, step 13500, 687 dora-rows tensors, 1 optimizer
# state, lr_schedulers []) so --resume_ckpt would ALSO load -- but we deliberately use
# --warm_start_ckpt, because --resume_ckpt restores the LOOP state too, and those counters were
# written against a 1350-step goa-only epoch. This run has ~2700 steps/epoch over a different
# corpus, so a true resume would fast-forward a dataloader that no longer exists at that index.
# warm-start keeps what we want (adapter weights + AdamW moments via OptimizerWarmStart) and
# drops only the epoch/shuffle counters. CONSEQUENCE: --epochs is the ADDITIONAL count, so
# EPOCHS=48 means 48 more on top of the original 10, not 48 total.
# Adapter geometry must match the ckpt and does: dora-rows r128 a128.
#
# RUN:  sbatch lumi/sbatch/lr5e5_allsets.sbatch                 (clean mix, fresh)
#       AUG=1 sbatch lumi/sbatch/lr5e5_allsets.sbatch           (+ augmented goa)
#       WARM=liked sbatch lumi/sbatch/lr5e5_allsets.sbatch      (continue the liked model)
#       SCHED=wsd sbatch lumi/sbatch/lr5e5_allsets.sbatch        (+ decay: the constant-LR hedge)
#
# SCHED=wsd (Kim 2026-08-22, "I hope the constant LR does not become an issue"): linear warmup ->
# flat to --lr_knee_epoch (default EPOCHS/4) -> cosine to 10% of lr by the end. The replicated run
# was constant-LR, but it only ever ran 10 epochs that way; constant 5e-5 held for 48 is
# unexplored, not proven. Running BOTH makes the schedule an AXIS instead of an assumption --
# same corpus, same seed, same everything else. Warmup is 0.78% of steps (the ratified value) on
# wsd arms only; the constant arms take no warmup, as replicated.
# VERIFY within minutes: LOCAL_RANK 0..7 once each (NOT eight rank-0s -- the silent-DDP bug);
#       "[captions] source i" one line per source; "[q5] steps/epoch" plausible vs the banner.
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=20:00:00
#SBATCH --job-name=lr5e5_allsets
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

AUG=${AUG:-0}
BS=${BS:-1}
GA=${GA:-1}
RANK=${RANK:-128}
ALPHA=${ALPHA:-128}
LR=${LR:-5e-5}
SEED=${SEED:-1}
EPOCHS=${EPOCHS:-48}
CKEVERY=${CKEVERY:-2}
BIGW=${BIGW:-0.18}
SCHED=${SCHED:-none}
WARM=${WARM:-}
LIKED=${SCRATCH}/runs/adamw_bf16_sweep/adamw_goa_t512_bs4_lr5e5/epoch=9-step=13500.ckpt
[ "${WARM}" = "liked" ] && WARM=${LIKED}
SCHEDARG=""
if [ "${SCHED}" = "wsd" ]; then
  KNEE=${KNEE:-$(python3 -c "print(${EPOCHS}/4)")}
  SCHEDARG="--lr_schedule wsd --lr_knee_epoch ${KNEE} --warmup-frac ${WARMUP_FRAC:-0.0078}"
  echo "[q5] SCHED=wsd knee=ep${KNEE} -> cosine to 10% of lr by ep${EPOCHS}"
elif [ "${SCHED}" != "none" ]; then
  echo "[q5] FATAL: SCHED must be none|wsd (got ${SCHED})"; exit 1
fi
WARMARG=""
if [ -n "${WARM}" ]; then
  [ -f "${WARM}" ] || { echo "[q5] FATAL: warm-start ckpt not found: ${WARM}"; exit 1; }
  WARMARG="--warm_start_ckpt ${WARM}"
  echo "[q5] WARM-START from ${WARM} (adapter weights + AdamW moments; epoch counter restarts, so EPOCHS=${EPOCHS} is ADDITIONAL)"
fi

NAME=lr5e5mix$([ "${AUG}" = "1" ] && echo aug)$([ -n "${WARM}" ] && echo warm)$([ "${SCHED}" != "none" ] && echo ${SCHED})_r${RANK}a${ALPHA}_t512_bf16_bs$((BS*GA*8))_s${SEED}
RUN=${SCRATCH}/runs/lr5e5_allsets/${NAME}

[ -n "${SIF}" ] || { echo "[q5] FATAL: no multitorch image"; exit 1; }
[ -d "${VENV}" ] || { echo "[q5] FATAL: no train venv at ${VENV}"; exit 1; }

# ── staging: flash dirs, from a .tar.gz when scratch holds only the tarball (latents_sa3 and
# latents_avp are tarballs -- scratch lost their loose npy to the Jul-14 tar), else cp the npy.
# LOCKED: the clean and AUG jobs share 3 of 4 sources and would otherwise stampede the copy.
stage() {
  local D=$1
  if [ "$(ls ${FLASH}/${D}/*.npy 2>/dev/null | wc -l)" -gt 0 ]; then return 0; fi
  local L=${FLASH}/.stage_${D}.lock
  if mkdir "${L}" 2>/dev/null; then
    echo "[q5] staging ${D} -> flash (lock held)"
    mkdir -p "${FLASH}/${D}"
    if [ -f "${SCRATCH}/${D}.tar.gz" ]; then
      tar -xzf "${SCRATCH}/${D}.tar.gz" -C "${FLASH}/${D}" --strip-components=1
    else
      cp ${SCRATCH}/${D}/*.npy "${FLASH}/${D}/" 2>/dev/null
    fi
    cp ${SCRATCH}/${D}/*.json "${FLASH}/${D}/" 2>/dev/null || true
    rmdir "${L}"
  else
    echo "[q5] another job is staging ${D}; waiting"
    while [ -d "${L}" ]; do sleep 20; done
  fi
}

SRCD=(latents_sa3 latents_goa_bigset latents_avp suomisoundi_latents)
SRCW=(1.0 ${BIGW} 1.0 1.0)
SRCS=(${CODE}/lumi/goa_longform_sidecar.json ${CODE}/lumi/goa_bigset_hinted_bylatent.json ${CODE}/lumi/avp_captions_tiered.json ${CODE}/lumi/suomisoundi_caption_sidecar.json)
SRCP=("0,0,1" "0,0,1" "0,0.9,0.1" "0.25,0.45,0.30")
if [ "${AUG}" = "1" ]; then
  SRCD+=(latents_goa_aug8); SRCW+=(1.0); SRCS+=(${CODE}/lumi/goa_longform_sidecar.json); SRCP+=("0,0,1")
fi

TOT=0
DIRS=""; WTS=""; SIDES=""; PROBS=""
for i in "${!SRCD[@]}"; do
  stage "${SRCD[$i]}"
  N=$(ls ${FLASH}/${SRCD[$i]}/*.npy 2>/dev/null | wc -l)
  [ "${N}" -gt 0 ] || { echo "[q5] FATAL: ${SRCD[$i]} staged empty"; exit 1; }
  NJ=$(ls ${FLASH}/${SRCD[$i]}/*.json 2>/dev/null | wc -l)
  [ "${NJ}" -gt 0 ] || { echo "[q5] FATAL: no .json metas for ${SRCD[$i]} (train_lora requires them)"; exit 1; }
  [ -f "${SRCS[$i]}" ] || { echo "[q5] FATAL: sidecar missing ${SRCS[$i]}"; exit 1; }
  TOT=$((TOT+N))
  DIRS="${DIRS}${DIRS:+,}${FLASH}/${SRCD[$i]}"
  WTS="${WTS}${WTS:+,}${SRCW[$i]}"
  SIDES="${SIDES}${SIDES:+,}${SRCS[$i]}"
  PROBS="${PROBS}${PROBS:+;}${SRCP[$i]}"
  echo "[q5] source ${i}: ${SRCD[$i]} ${N} npy / ${NJ} json  w=${SRCW[$i]}  tiers=${SRCP[$i]}"
done
SPE=$((TOT/(BS*GA*8)))
echo "[q5] NAME=${NAME} sources=${#SRCD[@]} crops=${TOT} eff_batch=$((BS*GA*8)) steps/epoch~${SPE} epochs=${EPOCHS} (~$((SPE*EPOCHS)) steps) lr=${LR} alpha=${ALPHA}"

mkdir -p "${RUN}"
cat > "${RUN}/run_meta.json" <<META
{"run": "${NAME}", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "Kim direct 2026-08-22 after auditioning adamw_goa_t512_bs4_lr5e5 ep9: 5e-5 beat 1e-4/2e-4 and stayed musical at cfg16/w2 where the others melted. Replicate that recipe across every corpus to ep48.",
 "replicates": "runs/adamw_bf16_sweep/adamw_goa_t512_bs4_lr5e5 (efp_adamw_bf16_sweep arm 7, 2026-07-24)",
 "recipe": {"adapter": "dora-rows", "rank": ${RANK}, "alpha": ${ALPHA}, "optimizer": "adamw wd0.01 betas[0.9,0.95]",
            "lr": "${LR}", "lr_schedule": "CONSTANT (as replicated; no warmup flag)",
            "precision": "bf16", "frames": 512, "beat_aware_crop": true,
            "batch_per_rank": ${BS}, "grad_accum": ${GA}, "gpus": 8, "ddp": "torchrun --standalone (verified pattern)",
            "effective_batch": $((BS*GA*8)), "epochs": ${EPOCHS}, "seed": ${SEED},
            "warm_start_ckpt": "${WARM:-null}",
            "warm_start_note": "--warm_start_ckpt not --resume_ckpt: the ckpt loop state was written against a 1350-step goa-only epoch and this run has a different corpus/length; EPOCHS is ADDITIONAL when warm-started"},
 "deviations_from_replicated_run": ["effective batch 8 vs 4 (single-GCD eff-4 = 88h to ep48, does not fit allocation)",
                                    "mixed corpus vs goa alone (the point of the run)"],
 "dataset": {"sources": "${DIRS}", "weights": "${WTS}", "caption_probs": "${PROBS}", "crops": ${TOT},
             "bigset_weight_rationale": "Kim: ~20% of draws because bigset is mp3-heavier; natural share would be 58%",
             "bigset_tiers": "0,0,1 -- its granite tier measured NOT GROUNDED (folder-name derived)"},
 "script": "lumi/sbatch/lr5e5_allsets.sbatch", "result": null, "kim_feedback": null}
META

srun --nodes=1 --ntasks=1 --cpus-per-task=56 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/stable-audio-tools:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-q5 MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-q5
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2
export TRITON_CACHE_DIR=/tmp/triton-q5 PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-q5 /tmp/triton-q5; mkdir -p /tmp/miopen-q5 /tmp/triton-q5
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536
torchrun --standalone --nnodes=1 --nproc-per-node=8 \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --base_precision bf16 \
  --adapter_type dora-rows --rank '"${RANK}"' --lora_alpha '"${ALPHA}"' \
  --optimizer adamw --lr '"${LR}"' \
  --encoded_dir "'"${DIRS}"'" --caption_sidecar "'"${SIDES}"'" \
  --caption_probs "'"${PROBS}"'" --source_weights "'"${WTS}"'" \
  --frames 512 --beat-aware-crop \
  --batch_size '"${BS}"' --accumulate_grad_batches '"${GA}"' \
  --num_workers 6 --seed '"${SEED}"' \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  '"${WARMARG}"' '"${SCHEDARG}"' \
  --no_demos --logger csv --name '"${NAME}"' \
  --save_dir '"${RUN}"' \
  2>&1
'
rc=$?
echo "[q5] srun rc=${rc}; ckpts: $(ls ${RUN}/*.ckpt 2>/dev/null | wc -l)"
grep -h "LOCAL_RANK" ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out 2>/dev/null | sort | uniq -c | head -10
exit ${rc}
