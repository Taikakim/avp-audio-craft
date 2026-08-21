#!/bin/bash
# genre_fusion_probe.sbatch — LUMI generalization probe (GHOST-NOTE 2026-08-21, Kim direct).
#
# WHY: local scoping (Mantu/sa3_lora_runs/genre_fusion_2026-08-21/) found our best DoRA soup
# holds onto trance/electronic character under an out-of-distribution "thrash metal" prompt,
# while the plain post-trained base model goes fully literal-metal with no electronic character
# at all. This job checks whether that generalization-vs-collapse signal is systematic across
# checkpoints: render the same fusion prompts at the MID and LAST (or best-PQ, for goa runs --
# see genre_fusion_checkpoints.txt) epoch of every "passable" run (WINTERMUTE's lean top-12/20
# checkpoint cut from this morning's rating stats), then score TWO CLAP numbers per clip, not
# one PQ number -- WINTERMUTE's methodology catch: "collapsed into training genre" and "renders
# the odd prompt badly" are different failures that PQ alone cannot distinguish. clap_score.py
# already scores every clip against every prompt in the pool for free, so the fusion-prompt
# self-cosine (did it follow the prompt) and the gf_ref-cosine (does it still sound like our
# corpus) come out of ONE scoring pass, no new tooling needed.
#
# PREREQ (run on a LOGIN node first):
#   python3 lumi/genre_fusion_shards.py --checkpoints lumi/genre_fusion_checkpoints.txt \
#       --scratch-runs /scratch/project_465003186/runs \
#       --out /scratch/project_465003186/genre_fusion_probe/shards --shards 8
#
# RUN:  sbatch lumi/sbatch/genre_fusion_probe.sbatch
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=03:00:00
#SBATCH --job-name=sa3_genre_fusion_probe
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
OUT=${OUT:-${SCRATCH}/genre_fusion_probe/renders}
SDIR=${SDIR:-${SCRATCH}/genre_fusion_probe/shards}
PROMPTS=${PROMPTS:-${CODE}/lumi/genre_fusion_prompts_lumi.json}
mkdir -p "${OUT}"

[ -n "${SIF}" ] || { echo "[gf-probe] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${PROMPTS}" ] || { echo "[gf-probe] FATAL: ${PROMPTS} missing — rsync lumi/genre_fusion_prompts_lumi.json"; exit 1; }
for R in 0 1 2 3 4 5 6 7; do
  [ -f "${SDIR}/shard_00${R}.txt" ] || { echo "[gf-probe] FATAL: ${SDIR}/shard_00${R}.txt missing — run genre_fusion_shards.py first"; exit 1; }
done
TODO=$(cat "${SDIR}"/shard_*.txt | grep -c . || true)
echo "[gf-probe] image=${SIF}  out=${OUT}  ${TODO} render_matrix_cells.py invocations across 8 ranks"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
R=${SLURM_PROCID}
CODE=/project/project_465003186/code
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export TRITON_CACHE_DIR=/tmp/triton-${R} PYTORCH_TUNABLEOP_ENABLED=0
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
rm -rf /tmp/miopen-${R} /tmp/triton-${R}; mkdir -p /tmp/miopen-${R} /tmp/triton-${R}
SHARD='"${SDIR}"'/shard_$(printf %03d ${R}).txt
n=0
while read -r LABEL TAG CKPT FRAMES EXTRA; do
  [ -z "${LABEL:-}" ] && continue
  n=$((n+1))
  echo "[rank ${R}] [${n}] ${LABEL} ${TAG} frames=${FRAMES}"
  python '"${CODE}"'/lumi/render_matrix_cells.py \
    --label "${LABEL}" --tag "${TAG}" --ckpt "${CKPT}" \
    --prompts '"${PROMPTS}"' --out '"${OUT}"' --frames "${FRAMES}" ${EXTRA} \
    2>&1 | sed "s/^/[rank ${R}] /"
done < "${SHARD}"
echo "[rank ${R}] done, ${n} invocations"
'
NC=$(find "${OUT}" -name "*.wav" 2>/dev/null | wc -l)
echo "[gf-probe] DONE — ${NC} clips in ${OUT}"
echo "[gf-probe] next: pull to Mantu, then clap_score.py against the full prompt pool"
echo "[gf-probe]   (each fusion clip x gf_ref cosine = corpus-retention; matched-prompt cosine = adherence)"
