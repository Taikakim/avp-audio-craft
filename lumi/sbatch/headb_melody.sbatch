#!/bin/bash
# headb_melody.sbatch — Head B melody-contour CONDITIONING adapter, full LUMI run.
# Spec: docs/superpowers/specs/2026-07-22-melodic-latch-film.md §2/§8. This is the
# "condition it in the model" path (Kim 2026-07-23: lightweight readout is out, feed
# melody IN via sa3_control FiLM). Ships to LUMI because the LOCAL RDNA4/ROCm 7.15 pilot
# died with native heap corruption (free(): chunks in smallbin corrupted, rc=134) in the
# GPU smoke — the melody_contour forward is CPU-test-green (5/5) and class streams are
# clean 0..7, so the crash is env-specific, not a code bug; sa3.sif is the known-good env.
#
# SINGLE GCD (one training process, no HQ fan-out). Env boilerplate lifted verbatim from
# the proven muscriptor_full.sbatch (SIF/bind/HF/MIOpen). r128 dora-rows + Embedding(9,768)
# per-frame melody FiLM, T=512, full melody set (2649/5400 crops carry a .melody8.npy
# stream), 15 epochs (Kim's new default; models click ep5-7), per-epoch saves.
#
# PREREQS (verify before submit):
#   1. $SCRATCH/latents_sa3.tar.gz          (already staged; extracted to $FLASH here)
#   2. $SCRATCH/latents_sa3_melody/         (2649 <id>.melody8.npy sidecars — ~10 MB, ship
#      from local /home/kim/Projects/latents_sa3_melody, see the campaign note)
#   3. $CODE/control/sa3_control/           (in the working-tree code refresh; NOT git archive)
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=60G
#SBATCH --time=08:00:00
#SBATCH --job-name=sa3_headb_melody
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${CODE:-$PROJ/code}; SIF=${SIF:-$PROJ/containers/sa3.sif}
MELODY=$SCRATCH/latents_sa3_melody
SAVE=$SCRATCH/runs/headb_melody; mkdir -p "$SAVE"

# --- fail loud on missing prereqs (a bad path here otherwise trains on 0 melody crops) ---
[ -f "$SCRATCH/latents_sa3.tar.gz" ] || { echo "[headb] FATAL: latents_sa3.tar.gz missing"; exit 1; }
[ -d "$MELODY" ] || { echo "[headb] FATAL: $MELODY missing — ship latents_sa3_melody sidecars first (prereq 2)"; exit 1; }
NMEL=$(ls "$MELODY"/*.melody8.npy 2>/dev/null | wc -l)
[ "$NMEL" -ge 2000 ] || { echo "[headb] FATAL: only $NMEL melody sidecars (<2000) — bad/partial ship"; exit 1; }
[ -f "$CODE/control/sa3_control/train.py" ] || { echo "[headb] FATAL: control/sa3_control not in code refresh (git-archive drop?)"; exit 1; }
echo "[headb] prereqs OK: $NMEL melody sidecars"

# --- stage latents once to /flash (extract from tarball, top-level dir latents_sa3/) ---
if [ ! -d "$FLASH/latents_sa3" ]; then
  mkdir -p "$FLASH/latents_sa3"
  tar -xzf "$SCRATCH/latents_sa3.tar.gz" -C "$FLASH/latents_sa3" --strip-components=1
fi

# --- single GCD: SLURM gives 1 GPU, no ROCR pinning needed; MIOpen user-db to /tmp
#     (read-only SIF), flash-attn CK path, TunableOp off (matches pilot + lumi-ops). ---
srun singularity exec --bind "$PROJ","$SCRATCH","$FLASH",/tmp "$SIF" bash -c '
  export HF_HUB_OFFLINE=1 HF_HOME='"$PROJ"'/models
  export PYTHONPATH='"$CODE"'/stable-audio-3:'"$CODE"'/control
  export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
  export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
  export MIOPEN_USER_DB_PATH=/tmp/miopen-headb-$$ MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-headb-$$
  mkdir -p "$MIOPEN_USER_DB_PATH"
  python '"$CODE"'/control/sa3_control/train.py \
    --encoded_dir '"$FLASH"'/latents_sa3 --model medium-base --precision bf16 \
    --control-mode melody_contour --melody-dir '"$MELODY"' \
    --control-dim 768 --dora-rank 128 --melody-dropout 0.1 --cfg-dropout 0.1 \
    --crop-frames 512 --batch 4 --grad-accum 1 --lr 1e-4 --optimizer adamw \
    --warmup-steps 100 --steps 15000 --max-epochs 15 --save-every 660 \
    --num-workers 7 --seed 42 --no-export-onnx-on-finish \
    --save-dir '"$SAVE"'
'
# --- verification: count epoch ckpts (never trust rc — but here rc matters too) ---
NCK=$(ls "$SAVE"/riffer_step*.pt 2>/dev/null | wc -l)
FINAL=$([ -f "$SAVE/riffer_final.pt" ] && echo yes || echo no)
echo "[headb] done -> $SAVE : $NCK epoch ckpts, final=$FINAL (expect >=12 ckpts for 15 epochs)"
[ "$NCK" -ge 10 ] && [ "$FINAL" = yes ] || { echo "[headb] SUCCESS-CHECK FAILED"; exit 1; }
