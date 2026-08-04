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
OUT=$SCRATCH/muscriptor_full; mkdir -p "$OUT"
# stage latents once to /flash (throughput guide: stage once per node, not per task).
# Source is the tarball $SCRATCH/latents_sa3.tar.gz (top-level dir latents_sa3/), NOT an
# extracted dir — extract it like ctrl_matrix_hq.sbatch does (was: rsync from a dir that
# doesn't exist -> job aborted under set -e). C 2026-07-18 w/ W.
if [ ! -d "$FLASH/latents_sa3" ]; then
  mkdir -p "$FLASH/latents_sa3"
  tar -xzf "$SCRATCH/latents_sa3.tar.gz" -C "$FLASH/latents_sa3" --strip-components=1
fi
module use /appl/local/csc/modulefiles && module load hyperqueue
export HQ_SERVER_DIR=$SCRATCH/.hq-muscriptor; hq server start & sleep 5
srun --overlap bash -c '
  export ROCR_VISIBLE_DEVICES=$SLURM_PROCID
  hq worker start --cpus 7' & sleep 10
while read -r shard; do
  hq submit --cpus 7 -- singularity exec \
    --bind $PROJ,$SCRATCH,$FLASH,/tmp "$SIF" \
    bash -c "export HF_HUB_OFFLINE=1 HF_HOME=$PROJ/models PYTHONPATH=$CODE/stable-audio-3:$CODE/muscriptor \
             MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0; \
             python $CODE/lumi/muscriptor_decode_task.py --shard $shard \
               --latents $FLASH/latents_sa3 --out $OUT --profiles $CODE/lumi/muscriptor_ref_profiles.json"
done < "$CODE/lumi/muscriptor_shards.txt"
hq job wait all; hq server stop
echo "[muscriptor_full] done -> $OUT"
