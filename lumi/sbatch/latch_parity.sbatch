#!/bin/bash
# latch_parity.sbatch — Phase-5 step 1: ONE LatCH head, 1 GCD, dev-g partition.
# Purpose: confirm the container + data + trainer produce a loss curve and a checkpoint
# that loads and steers like the local run before any GPU-hours go to the campaign.
# Local reference to beat: rms_energy_bass, EMA+ga2 recipe (WORKLOG 2026-06-29).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=60G
#SBATCH --time=02:00:00
#SBATCH --job-name=latch-parity
#SBATCH --output=%x-%j.out

set -euo pipefail
source /project/${SA3_PROJECT:-project_465003186}/lumi/env_lumi.sh

CONTAINER=/project/${SA3_PROJECT}/sa3-train.sif
REPO=/project/${SA3_PROJECT}/stable-audio-3          # git clone, code lives on /project
TRAINER=${REPO}/scripts/latch/train_latch.py         # the --ema/--grad-accum lineage

srun singularity exec \
    -B /project/${SA3_PROJECT},/scratch/${SA3_PROJECT} \
    ${CONTAINER} \
    python ${TRAINER} \
      --feature rms_energy_bass \
      --latent-dir ${SA3_DATA}/latents_sa3 \
      --target-source npz \
      --save-dir ${SA3_RUNS}/latch_parity \
      --optimizer adamw --lr 3e-4 --batch-size 32 \
      --ema 0.999 --grad-accum 2 \
      --epochs 20 --standardize --save-best-only \
      --seed 1 \
      --wandb --wandb-project latch-lumi --run-name parity_rms_bass
