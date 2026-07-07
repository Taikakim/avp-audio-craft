#!/bin/bash
# dora_run.sbatch — Kim's campaign B: DoRA finetunes on 1 GCD each.
# Parameterized via --export so one script serves the whole bracket, e.g.:
#
#   sbatch --export=ALL,ENC=latents_sa3,RANK=16,EPOCHS=8,NAME=dora16_goa dora_run.sbatch
#   sbatch --export=ALL,ENC=latents_avp,RANK=16,EPOCHS=8,NAME=dora16_avp dora_run.sbatch
#   sbatch --export=ALL,ENC=latents_avp,RANK=128,LR=5e-5,NAME=dora128_avp dora_run.sbatch
#
# LR/rank brackets = a one-line for-loop over sbatch calls; each lands on its own GCD.
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
EPOCHS=${EPOCHS:-8}
LR=${LR:-1e-4}
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
      --rank ${RANK} --lr ${LR} --epochs ${EPOCHS} \
      --batch_size 32 --beat-aware-crop \
      --save_dir ${SA3_RUNS}/${NAME} \
      --name ${NAME} \
      --seed 1 --no_demos --logger wandb
