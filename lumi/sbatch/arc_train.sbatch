#!/bin/bash
# arc_train.sbatch — ARC-Forcing TRAIN (task #46 part 2). Fine-tunes medium-base on the
# rollout dataset built by arc_rollout.sbatch: the drifted rollout context is CLAMPED via the
# inpaint conditioning keys (inpaint_mask + inpaint_masked_input, the model's local_add_cond),
# loss on the free (mask==0) region only. Samples are fixed-length T=1024 (shared data
# contract, multiple-of-256) — so NO --frames/--duration here; the .npz sets T.
#
# HYPOTHESIS: with the context frames the model must condition on being its OWN drifted output
# (not ground truth), the adapter learns error-recovery, not just clean teacher continuation —
# the exposure-bias fix for long-form drift. Compare against a plain continuation LoRA of equal
# rank/steps to isolate the rollout effect.
#
# RECIPE (Kim): standard train_lora, --arc-data, rank 128, alpha 128 (s=1), lr 1e-4.
#
# ── run knobs (override via --export=ALL,KEY=VAL) ────────────────────────────────
#   ARC_DS   rollout dataset dir (MUST match arc_rollout.sbatch OUT). default: scratch runs dir
#   RANK     LoRA rank (default 128)
#   ALPHA    lora_alpha (default 128 = rank → s=1)
#   LR       learning rate (default 1e-4)
#   EPOCHS   epochs (default 8; ckpt every epoch → compare across the run, don't take the last)
#   BS       batch size (default 16; T=1024 is 2× the T=512 seq, so half the T512 batch of 32)
#   ADAPTER  adapter_type (default lora; dora/bora available)
#   NAME     run name / save subdir (default arc_r${RANK})
# e.g.  sbatch --export=ALL,ARC_DS=/scratch/project_465003186/runs/arc_rollout_ds,RANK=128 arc_train.sbatch
#
# RESUME: --resume_ckpt <full .ckpt> restores optimizer/scheduler/epoch; --epochs is the TOTAL
# target (resuming an ep4 ckpt with EPOCHS=8 = 4 more). See train_lora.py header.
#
# WALLCLOCK ESTIMATE: 2000 samples / BS 16 ≈ 125 steps/epoch × 8 ≈ 1000 steps at T=1024
# (~1.5–2 s/step w/ r128 backward on 1 GCD) ≈ 30–60 min + model load. --time 08:00:00 is
# deliberately generous (first-step MIOpen compile can take several minutes with no log line —
# do NOT kill it; MASTER §5).
#
# NOTE (air-gap): medium-base + T5-Gemma PRE-STAGED under ${SA3_MODELS} (HF_HUB_OFFLINE=1).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=120G
#SBATCH --time=08:00:00
#SBATCH --job-name=arc-train
#SBATCH --output=%x-%j.out

set -euo pipefail
source /project/${SA3_PROJECT:-project_465003186}/lumi/env_lumi.sh

ARC_DS=${ARC_DS:-${SA3_RUNS}/arc_rollout_ds}
RANK=${RANK:-128}
ALPHA=${ALPHA:-128}
LR=${LR:-1e-4}
EPOCHS=${EPOCHS:-8}
BS=${BS:-16}
ADAPTER=${ADAPTER:-lora}
NAME=${NAME:-arc_r${RANK}}

CONTAINER=/project/${SA3_PROJECT}/sa3-train.sif
REPO=/project/${SA3_PROJECT}/stable-audio-3

srun singularity exec \
    -B /project/${SA3_PROJECT},/scratch/${SA3_PROJECT} \
    ${CONTAINER} \
    python ${REPO}/scripts/train_lora.py \
      --adapter_type ${ADAPTER} \
      --model medium-base \
      --arc-data ${ARC_DS} \
      --rank ${RANK} --lora_alpha ${ALPHA} --lr ${LR} \
      --epochs ${EPOCHS} --checkpoint_every_epochs 1 \
      --batch_size ${BS} \
      --save_dir ${SA3_RUNS}/${NAME} \
      --name ${NAME} \
      --seed 1 --no_demos --logger wandb
