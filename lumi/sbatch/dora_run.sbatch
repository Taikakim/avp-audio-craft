#!/bin/bash
# dora_run.sbatch — Kim's campaign B: DoRA finetunes on 1 GCD each.
# Parameterized via --export so one script serves the whole bracket, e.g.:
#
#   sbatch --export=ALL,ENC=latents_sa3,RANK=16,EPOCHS=8,NAME=dora16_goa dora_run.sbatch
#   # avp step-capped recipe (see LESSONS below) — EPOCHS=0 hands control to STEPS:
#   sbatch --export=ALL,ENC=latents_avp_aug10,RANK=128,LR=1e-4,EPOCHS=0,STEPS=3000,NAME=dora128_avp_aug10 dora_run.sbatch
#   sbatch --export=ALL,ENC=latents_avp_aug10,RANK=256,LR=7e-5,EPOCHS=0,STEPS=3000,NAME=dora256_avp_aug10 dora_run.sbatch
#
# LR/rank brackets = a one-line for-loop over sbatch calls; each lands on its own GCD.
#
# ── avp-DoRA LESSONS (local bracket, 2026-07-08 — bake these into every avp run) ──
#  * STEP CAP: the quality knee is ep4-6; runs collage/drift past it ("disjointed
#    pieces copied and pasted" = the 3x-lr signature). Cap at ~3000 steps, ckpt every
#    300, COMPARE EARLY CKPTS FIRST, extend only if earned. (EPOCHS=0 => STEPS governs;
#    the trainer sets max_steps=-1 whenever --epochs is truthy, so EPOCHS must be 0.)
#  * AUG POLICY: 10% random sample, NOT 88%. An aug-heavy corpus (each track held at 7
#    tempo/pitch variants under ONE caption) makes the trigger token condition a
#    TEMPO-MULTIMODAL distribution -> sampling mode-hops mid-clip = audible tempo
#    instability (goa-locked 100% > real-avp 80% > r16-adapter ~50% clip-stability;
#    Kim's ear + two independent meters agree). Fix: per-crop bpm captioning, or drop
#    tempo augs, or keep augs to a 10% tail. latents_avp_aug10 = 288 orig + 32 augs.
#  * NEVER novelty/familiarity-weighting on an aug-heavy corpus: it over-samples exactly
#    the stretch-artifact tail (r16_familiarity was the WORST arm, all glitchy+diffuse).
#  * RANK mitigates: r128/r256 tolerate the instability far better than r16 (r128adj 86%
#    clip-stable vs r16 ~50%) — higher rank is a partial workaround if augs can't be fixed.
#  * LAUNCH-ARG TRAP (cost hours locally 2026-07-08): train_lora --duration DEFAULTS TO
#    380s (T=4096) — omit it and you get 8x sequence => ~45s/step, indistinguishable from a
#    hung card. ALWAYS pass --duration 47 (wired below). Lesson: diff the FULL arg list
#    against a known-good reference run before launching; and kill process GROUPS, not the
#    main PID — orphaned dataloader workers hold KFD contexts through a GPU reset.
#  * BUG: train_lora.py --source_weights is a SILENT NO-OP (parsed into `weights` at
#    line ~134, no sampler consumes it). Do NOT rely on it for per-source mixing until
#    fixed; use corpus composition (latents_avp_aug10) instead.
# ──────────────────────────────────────────────────────────────────────────────────
#
# NOTE (air-gap): SA3 medium-base weights + T5-Gemma must be PRE-STAGED under
# ${SA3_MODELS} (HF_HOME points there, HF_HUB_OFFLINE=1) — first dry-run the model load
# on a login node (which has internet) to populate the cache, then it's frozen.
#
#SBATCH --account=project_465XXXXX
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=120G
#SBATCH --time=24:00:00
#SBATCH --job-name=dora
#SBATCH --output=%x-%j.out

set -euo pipefail
source /project/${SA3_PROJECT:-project_465XXXXX}/lumi/env_lumi.sh

ENC=${ENC:-latents_sa3}
RANK=${RANK:-16}
EPOCHS=${EPOCHS:-8}        # set EPOCHS=0 to hand the run length to STEPS (avp recipe)
STEPS=${STEPS:-3000}       # step cap; only active when EPOCHS=0 (trainer semantics)
CKPT_EVERY=${CKPT_EVERY:-300}  # step-based checkpoint cadence (compare-first workflow)
LR=${LR:-1e-4}
DUR=${DUR:-47}            # CRITICAL: train_lora --duration DEFAULTS TO 380s (T=4096) — 8x
                         # the intended 47s crop => ~65x attention in checkpointed backward
                         # => ~45s/step (looks like a hung card). ALWAYS pass 47. (2026-07-08)
CLIP=${CLIP:-1.0}        # gradient_clip_val (trainer default 0=off); DoRA stability
NAME=${NAME:-dora_r${RANK}_${ENC}}

CONTAINER=/project/${SA3_PROJECT}/sa3-train.sif
REPO=/project/${SA3_PROJECT}/stable-audio-3

srun singularity exec \
    -B /project/${SA3_PROJECT},/scratch/${SA3_PROJECT} \
    ${CONTAINER} \
    python ${REPO}/scripts/train_lora.py \
      --adapter_type dora \
      --model medium-base \
      --encoded_dir ${SA3_DATA}/${ENC} \
      --rank ${RANK} --lr ${LR} --epochs ${EPOCHS} --steps ${STEPS} \
      --checkpoint_every ${CKPT_EVERY} \
      --duration ${DUR} --gradient_clip_val ${CLIP} \
      --batch_size 32 --beat-aware-crop \
      --save_dir ${SA3_RUNS}/${NAME} \
      --name ${NAME} \
      --seed 1 --no_demos --logger wandb
