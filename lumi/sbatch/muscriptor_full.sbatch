#!/bin/bash
# muscriptor_full.sbatch — full-corpus MuScriptor transcription over SAME-decoded latents
# (spec docs/superpowers/specs/2026-07-17-muscriptor-lumi-batch.md; gate GREEN 2026-07-17).
# PATTERN: ctrl_matrix_hq.sbatch (HQ fan-out, 8 GCD workers) + efp_fp32_compare.sbatch
# (container/bind/env). Task list from gen_muscriptor_shards.sh -> lumi/muscriptor_tasks.txt.
# ~5401 crops / 50-crop shards = 109 tasks x ~75 min on one GCD => ~17 h wall on 1 node.
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=muscriptor_full
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${CODE:-$PROJ/code}; SIF=${SIF:-$PROJ/containers/sa3.sif}   # aligned to /code (has stable-audio-3) — was sa3-code, C 2026-07-18 w/ W
# ── PARAMETERISED BY LATENT SET (2026-08-18) ────────────────────────────────────────────────────
# Was hardcoded to latents_sa3. Kim wants the big-goa and suomisoundi sets transcribed too, and with
# WALL CLOCK the binding constraint (4 days of compute left, ~500-600 GPU-h/day available vs the 192
# one node spends) the answer is to run WIDE, not to queue three corpora behind each other:
#   SET=latents_goa_bigset  sbatch --nodes=8 --time=08:00:00 lumi/sbatch/muscriptor_full.sbatch
#   SET=suomisoundi_latents sbatch --nodes=2 --time=04:00:00 lumi/sbatch/muscriptor_full.sbatch
# Shard lists are per-set (lumi/muscriptor_shards_<SET>.txt) so two corpora cannot clobber each
# other's work list. Generate with: bash lumi/gen_muscriptor_shards.sh <latents-dir> <prefix> <SET>
SET=${SET:-latents_sa3}
OUT=${OUT:-$SCRATCH/muscriptor_$SET}; mkdir -p "$OUT"
SHARDS=${SHARDS:-$CODE/lumi/muscriptor_shards_$SET.txt}
[ -f "$SHARDS" ] || { echo "[muscriptor] FATAL: shard list $SHARDS missing — run lumi/gen_muscriptor_shards.sh for SET=$SET first"; exit 1; }
NSHARD=$(wc -l < "$SHARDS")
echo "[muscriptor] SET=$SET nodes=${SLURM_NNODES:-1} GCDs=$(( ${SLURM_NNODES:-1} * 8 )) shards=$NSHARD -> $OUT"
echo "[muscriptor] at ~1.5 GCD-min/crop and 50 crops/shard this is ~$(( NSHARD * 75 / 60 )) GCD-hours"
echo "[muscriptor]   -> ~$(( NSHARD * 75 / 60 / ( ${SLURM_NNODES:-1} * 8 ) )) h wall at this width"
# stage latents once to /flash (throughput guide: stage once per node, not per task).
# Source is the tarball $SCRATCH/latents_sa3.tar.gz (top-level dir latents_sa3/), NOT an
# extracted dir — extract it like ctrl_matrix_hq.sbatch does (was: rsync from a dir that
# doesn't exist -> job aborted under set -e). C 2026-07-18 w/ W.
# stage once per node. Accept EITHER an extracted dir on scratch or a tarball — latents_sa3 ships as
# a tarball, latents_goa_bigset and suomisoundi_latents are plain dirs, and assuming one form is what
# aborted this job under set -e once before (C 2026-07-18).
if [ ! -d "$FLASH/$SET" ]; then
  if [ -d "$SCRATCH/$SET" ]; then
    echo "[muscriptor] staging $SET from scratch dir ($(ls -1 $SCRATCH/$SET | wc -l) entries) ..."
    mkdir -p "$FLASH/$SET"; cp "$SCRATCH/$SET"/*.npy "$SCRATCH/$SET"/*.json "$FLASH/$SET/" 2>/dev/null || true
  elif [ -f "$SCRATCH/$SET.tar.gz" ]; then
    echo "[muscriptor] extracting $SET.tar.gz ..."
    mkdir -p "$FLASH/$SET"; tar -xzf "$SCRATCH/$SET.tar.gz" -C "$FLASH/$SET" --strip-components=1
  else
    echo "[muscriptor] FATAL: neither $SCRATCH/$SET/ nor $SCRATCH/$SET.tar.gz exists"; exit 1
  fi
fi
echo "[muscriptor] staged: $(ls -1 $FLASH/$SET/*.npy 2>/dev/null | wc -l) crops on /flash"
module use /appl/local/csc/modulefiles && module load hyperqueue
# per-SET server dir: two muscriptor jobs sharing $SCRATCH/.hq-muscriptor would join ONE HQ server
# and steal each other's tasks.
export HQ_SERVER_DIR=$SCRATCH/.hq-muscriptor-$SET; hq server start & sleep 5
# 🔴 $SLURM_LOCALID, NOT $SLURM_PROCID. On ONE node they are equal, which is why the original worked;
# across N nodes PROCID runs 0..(8N-1) while each node still has only GCDs 0-7, so every rank past
# the first node would index off the end -> "No HIP GPUs are available". LOCALID is per-node.
srun --overlap --ntasks=$(( ${SLURM_NNODES:-1} * 8 )) bash -c '
  export ROCR_VISIBLE_DEVICES=$SLURM_LOCALID
  hq worker start --cpus 7' & sleep 15
while read -r shard; do
  hq submit --cpus 7 -- singularity exec \
    --bind $PROJ,$SCRATCH,$FLASH,/tmp "$SIF" \
    bash -c "export HF_HUB_OFFLINE=1 HF_HOME=$PROJ/models PYTHONPATH=$CODE/stable-audio-3:$CODE/muscriptor \
             MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0; \
             python $CODE/lumi/muscriptor_decode_task.py --shard $shard \
               --latents $FLASH/$SET --out $OUT --profiles $CODE/lumi/muscriptor_ref_profiles.json"
done < "$SHARDS"
hq job wait all; hq server stop
echo "[muscriptor] $SET done -> $OUT ($(ls -1 $OUT 2>/dev/null | wc -l) outputs, $NSHARD shards submitted)"
echo "[muscriptor] VERIFY by artifact count, never rc: hq task failures do NOT propagate to the sbatch."
