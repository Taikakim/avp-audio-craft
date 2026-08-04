#!/bin/bash
# arc_rollout.sbatch — ARC-Forcing rollout DATASET build (task #46 part 1, the GPU step).
# Runs eval/arc_rollout_dataset.py over latents_sa3 (goa) to synthesize the exposure-bias
# training corpus: per sample, re-render a Tctx=512 context through the model (latent-domain
# SDEdit reanchor at --rollout-nl) so the stored context is the model's OWN drifted output;
# save the TRUE T=1024 window as target + a clamp mask. Output is consumed by arc_train.sbatch.
#
# HYPOTHESIS: training on the model's own drifted continuations (not ground truth) closes the
# exposure-bias gap that makes long a2a/continuation wander — the model learns to recover from
# its own imperfect context instead of only ever seeing clean teacher-forced frames.
#
# ── run knobs (override via --export=ALL,KEY=VAL) ────────────────────────────────
#   OUT        where the .npz dataset + manifest.json land (default: scratch runs dir)
#   N          --n-samples (default 2000)
#   TCTX       context frames re-rendered per sample (default 512; free region = 1024-TCTX)
#   NL         --rollout-nl SDEdit reanchor noise level (default 0.5)
#   STEPS      diffusion steps for the reanchor (default 24)
#   CFG        --cfg-scale (default 6.0)
#   LORA_CKPT  adapter whose drift is captured (default: none = base medium-base drift).
#              Its id lands in every sample's meta + the manifest — PRE-STAGE it under /project.
#   SEED       --seed (default 42; per-sample seeds derive from it → resumable & reproducible)
# e.g.  sbatch --export=ALL,N=2000,LORA_CKPT=/project/project_465003186/models/adapters/dora128_goa.safetensors arc_rollout.sbatch
#
# RESUMABLE: the builder skips existing {idx:06d}.npz, so a re-submit after a timeout/purge
# continues where it stopped — point OUT at the same dir. (Scratch auto-purges: keep the
# rollout + arc_train inside one scratch-retention window, or copy OUT to /project after.)
#
# STAGING NOTE: OUT is written to /scratch (large, scratch-tier). arc_train.sbatch reads it
# from the SAME path — set both to the same OUT, or copy to /project/.../data/arc_rollout_ds
# if it must outlive scratch.
#
# WALLCLOCK ESTIMATE: ~1–2 h for 2000 samples (24-step SDEdit reanchor at T=512 ≈ 1–2 s/sample
# on 1 GCD) + ~3 min model load. --time 04:00:00 leaves headroom for a cold MIOpen compile.
#
# NOTE (air-gap): SA3 medium-base weights + T5-Gemma must be PRE-STAGED under ${SA3_MODELS}
# (HF_HOME points there, HF_HUB_OFFLINE=1) — dry-run the model load on a login node first.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=60G
#SBATCH --time=04:00:00
#SBATCH --job-name=arc-rollout
#SBATCH --output=%x-%j.out

set -euo pipefail
source /project/${SA3_PROJECT:-project_465003186}/lumi/env_lumi.sh

OUT=${OUT:-${SA3_RUNS}/arc_rollout_ds}
N=${N:-2000}
TCTX=${TCTX:-512}
NL=${NL:-0.5}
STEPS=${STEPS:-24}
CFG=${CFG:-6.0}
SEED=${SEED:-42}
LORA_CKPT=${LORA_CKPT:-}

CONTAINER=/project/${SA3_PROJECT}/sa3-train.sif
MASTER_REPO=/project/${SA3_PROJECT}          # SAO master repo root (eval/ lives here)
SA3_REPO=/project/${SA3_PROJECT}/stable-audio-3   # SDEditReanchor import path
ROLLOUT=${MASTER_REPO}/eval/arc_rollout_dataset.py

srun singularity exec \
    -B /project/${SA3_PROJECT},/scratch/${SA3_PROJECT} \
    --env PYTHONPATH=${SA3_REPO} \
    ${CONTAINER} \
    python ${ROLLOUT} \
      --out ${OUT} \
      --latents-dir ${SA3_DATA}/latents_sa3 \
      --n-samples ${N} \
      --tctx ${TCTX} --rollout-nl ${NL} \
      --steps ${STEPS} --cfg-scale ${CFG} \
      --model medium-base \
      --device cuda --seed ${SEED} \
      ${LORA_CKPT:+--lora-ckpt ${LORA_CKPT}}
