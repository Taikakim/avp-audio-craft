#!/bin/bash
# goa_granite.sbatch — Granite caption-REVISION over the big-set Music Flamingo captions
# (CONTINUITY 2026-08-03, Kim direct). 8 GCD-pinned ranks, round-robin shards, resumable
# (skips tracks whose granite json exists). LARGER Granite instruct via transformers on the
# multitorch image (ROCm 7 — VRAM the local GGUF path lacked). Genre-corrected T2 variant pools.
#
# PREREQ: Granite model pre-staged to $MODELS (compute nodes are air-gapped). On a LOGIN node
# (NOTE the --bind: without it singularity mounts /project READ-ONLY and the download fails):
#   singularity exec --bind /project/project_465003186,/scratch/project_465003186 <MTSIF> \
#     bash -c 'export HF_HOME=/project/project_465003186/models; hf download ibm-granite/granite-3.3-8b-instruct'
#   (swap the id via --export=ALL,GRANITE_MODEL=<id> for a bigger variant; stage that id first.)
#
# INPUT:  ${SCRATCH}/goa_archive_captions/json/*.json   (from goa_caption.sbatch)
# OUTPUT: ${SCRATCH}/goa_archive_captions/granite/*.json (per-track {short_*:[variants], medium_review})
#
# PROBE (run FIRST): sbatch --time=00:25:00 --export=ALL,PROBE=1 lumi/sbatch/goa_granite.sbatch
#   -> 3 tracks/rank; check variants look sane + genre-corrected + per-track wall.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=sa3_goa_granite
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${GRANITE_SIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
GRANITE_MODEL=${GRANITE_MODEL:-ibm-granite/granite-3.3-8b-instruct}
CAPJSON=${SCRATCH}/goa_archive_captions/json
OUT=${SCRATCH}/goa_archive_captions/granite
mkdir -p "${OUT}/shards"

[ -n "${SIF}" ] || { echo "[granite] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -d "${CAPJSON}" ] || { echo "[granite] FATAL: ${CAPJSON} missing — run goa_caption.sbatch first"; exit 1; }
MODELDIR="models--$(echo "${GRANITE_MODEL}" | sed 's|/|--|g')"   # HF cache uses '--' for '/', not '-'
ls "${MODELS}"/hub/${MODELDIR}/snapshots/*/ >/dev/null 2>&1 \
  || { echo "[granite] FATAL: ${GRANITE_MODEL} not staged in ${MODELS} — run the login-node snapshot_download (header)"; exit 1; }

LIST=${OUT}/shards/all_caps.txt
find "${CAPJSON}" -type f -name '*.json' | sort > "${LIST}"
N=$(wc -l < "${LIST}")
echo "[granite] ${N} MF captions; model=${GRANITE_MODEL}"
for R in 0 1 2 3 4 5 6 7; do awk -v r=${R} 'NR % 8 == r' "${LIST}" > "${OUT}/shards/shard_${R}.txt"; done

LIMIT_ARG=""
[ "${PROBE:-0}" = "1" ] && LIMIT_ARG="--limit 3" && echo "[granite] PROBE MODE: 3 tracks/rank"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
R=${SLURM_PROCID}
CODE=/project/project_465003186/code
# NO ROCR export — srun --gpus-per-task=1 cgroup pins (pattern A)
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
# MANDATORY GPU env (lumi-ops skill): MIOpen read-only-db fix + home-inode + tunableop off
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export TRITON_CACHE_DIR=/tmp/triton-${R} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-${R} /tmp/triton-${R}; mkdir -p /tmp/miopen-${R} /tmp/triton-${R}
export GRANITE_MODEL='"${GRANITE_MODEL}"'
python '"${CODE}"'/lumi/goa_granite_task.py \
  --shard '"${OUT}"'/shards/shard_${R}.txt --out '"${OUT}"' '"${LIMIT_ARG}"' \
  2>&1 | sed "s/^/[rank ${R}] /"
'
NG=$(ls "${OUT}"/*.json 2>/dev/null | wc -l)
echo "[granite] revised=${NG}/${N} -> ${OUT}"
# SUCCESS = json count vs ${N}; resumable — re-submit to continue. Never trust rc alone.
