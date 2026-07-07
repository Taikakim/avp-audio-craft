#!/bin/bash
# latch_all_features.sbatch — Kim's campaign A: a LatCH head for EVERY feature, full trick
# stack (EMA 0.999 + grad-accum 2 + early-stop-by-epochs + standardize + save-best-only —
# the validated damping recipe, WORKLOG 2026-06-29 / MASTER §4 trajectory-stats note).
#
# Job ARRAY: one array task = one feature = one GCD. 20 features → fits 2.5 LUMI-G nodes;
# Slurm packs them. This is the whole point of LUMI: the local box does these serially.
#
#   sbatch --array=0-19 latch_all_features.sbatch
#   sbatch --array=0-19%8 latch_all_features.sbatch   # throttle to one node's worth
#
# Telemetry: full per-run wandb (offline) per the MASTER §4 comprehensive-logging rule —
# the cross-feature per-layer fingerprint (DiT-block × feature controllability map) is only
# reconstructable if every run logged everything. Sync after: `wandb sync` on a login node.
#
#SBATCH --account=project_465XXXXX
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=60G
#SBATCH --time=06:00:00
#SBATCH --job-name=latch-all
#SBATCH --output=%x-%A_%a.out

set -euo pipefail
source /project/${SA3_PROJECT:-project_465XXXXX}/lumi/env_lumi.sh

# The 20 whole-track timeseries fields (latents_sa3 *.TIMESERIES.npz, 2026-07 grid).
# relative_position_ts intentionally excluded — position ramp, not a controllable target.
# hpcp_ts is 12-channel; the trainer auto-detects out_channels.
FEATURES=(
  rms_energy_bass_ts rms_energy_body_ts rms_energy_mid_ts rms_energy_air_ts
  spectral_flatness_ts spectral_flux_ts spectral_skewness_ts spectral_kurtosis_ts
  onset_envelope_ts hpcp_ts beat_activation_ts downbeat_activation_ts
  onset_envelope_drums_ts rms_drums_ts
  onset_envelope_bass_ts rms_bass_ts
  onset_envelope_other_ts rms_other_ts
  onset_envelope_vocals_ts rms_vocals_ts
)
FEAT=${FEATURES[$SLURM_ARRAY_TASK_ID]}

CONTAINER=/project/${SA3_PROJECT}/sa3-train.sif
REPO=/project/${SA3_PROJECT}/stable-audio-3
TRAINER=${REPO}/scripts/latch/train_latch.py

srun singularity exec \
    -B /project/${SA3_PROJECT},/scratch/${SA3_PROJECT} \
    ${CONTAINER} \
    python ${TRAINER} \
      --feature ${FEAT%_ts} \
      --latent-dir ${SA3_DATA}/latents_sa3 \
      --target-source npz \
      --save-dir ${SA3_RUNS}/latch_all/${FEAT} \
      --optimizer adamw --lr 3e-4 --batch-size 32 \
      --ema 0.999 --grad-accum 2 \
      --epochs 20 --standardize --save-best-only \
      --seed 1 \
      --wandb --wandb-project latch-lumi --run-name all_${FEAT}
