#!/bin/bash
# goa_caption.sbatch — Music Flamingo (transformers bf16) captions over the FULL
# goa_archive on LUMI (CONTINUITY 2026-07-29; GGUF dropped per Kim — 64GB GCDs fit
# the full bf16 model, better quality). 8 GCD-pinned ranks, resumable per-track json.
#
# BUDGET: 'full' prompt ~28s/track local-GPU => 23232 x ~30s / 8 GCDs ≈ 24h -> 30h wall.
# Each EXTRA prompt type ≈ +24h; add via --export=ALL,PROMPT_TYPES=full,genre_mood
# (then expect a resubmit to finish — resumable, so it just continues).
#
# PREREQS: archive + venv + mir-src (same as goa_sep.sbatch) + MF weights in ${MODELS}
# (build_offload_venv.sh step 3 downloads them; compute nodes run HF_HUB_OFFLINE).
#
# PROBE MODE (run FIRST): sbatch --time=00:40:00 --export=ALL,PROBE=1 lumi/sbatch/goa_caption.sbatch
#   -> 2 tracks/rank; check captions look sane + per-track wall_s (sizes the full run).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=30:00:00
#SBATCH --job-name=sa3_goa_caption
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
# SIF/VENV overridable: the FA2 experiment runs the LUMI multitorch image (flash-attn
# prebuilt for gfx90a) + its own venv (build_offload_venv_mt.sh) via
#   --export=ALL,CAPTION_SIF=<multitorch.sif>,CAPTION_VENV=$SCRATCH/goa_offload_venv_mt,MF_USE_FA2=1
SIF=${CAPTION_SIF:-${PROJ}/containers/sa3.sif}
MODELS=${PROJ}/models
VENV=${CAPTION_VENV:-${SCRATCH}/goa_offload_venv}
ARCHIVE=${ARCHIVE:-${SCRATCH}/goa_archive}
OUT=${OUT:-${SCRATCH}/goa_archive_captions}
GENRE_HINT_FILE=${GENRE_HINT_FILE:-}
GENRE_HINT=""
[ -n "${GENRE_HINT_FILE}" ] && [ -f "${GENRE_HINT_FILE}" ] && GENRE_HINT=$(cat "${GENRE_HINT_FILE}")
mkdir -p "${OUT}/shards" "${OUT}/json"

[ -d "${ARCHIVE}" ] || { echo "[goa-cap] FATAL: ${ARCHIVE} missing — archive not rsync'd yet"; exit 1; }
# bin/activate not bin/python — container-made venv's python is a broken symlink host-side (see goa_sep.sbatch)
[ -f "${VENV}/bin/activate" ] || { echo "[goa-cap] FATAL: ${VENV} missing — run lumi/build_offload_venv.sh on uan18"; exit 1; }
[ -d "${CODE}/mir-src/classification" ] || { echo "[goa-cap] FATAL: ${CODE}/mir-src missing (rsync mir/src)"; exit 1; }
ls "${MODELS}"/hub/models--nvidia--music-flamingo-hf/snapshots/*/ >/dev/null 2>&1 \
  || { echo "[goa-cap] FATAL: MF weights not in ${MODELS} — run build_offload_venv.sh step 3"; exit 1; }

LIST=${OUT}/shards/all_tracks.txt
find "${ARCHIVE}" -type f \( -iname '*.mp3' -o -iname '*.flac' -o -iname '*.m4a' \) | sort > "${LIST}"
N=$(wc -l < "${LIST}")
echo "[goa-cap] ${N} tracks; prompts=${PROMPT_TYPES:-full}"
for R in 0 1 2 3 4 5 6 7; do awk -v r=${R} 'NR % 8 == r' "${LIST}" > "${OUT}/shards/shard_${R}.txt"; done

LIMIT_ARG=""
[ "${PROBE:-0}" = "1" ] && LIMIT_ARG="--limit 2" && echo "[goa-cap] PROBE MODE: 2 tracks/rank"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
R=${SLURM_PROCID}
# NO ROCR export — srun --gpus-per-task=1 cgroup already pins (see goa_sep.sbatch note)
source '"${VENV}"'/bin/activate
# venv site-packages FIRST on PYTHONPATH — the multitorch image ships /opt/venv and its env
# shadows an overlay venv (container transformers 4.57.6 would win over our 5.x; 2026-07-30).
# Harmless no-op under the sa3 SIF.
export PYTHONPATH='"${VENV}"'/lib/python3.12/site-packages${PYTHONPATH:+:${PYTHONPATH}}
export MIR_SRC='"${CODE}"'/mir-src
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True   # long-audio attn allocs fragment (probe 20423099: 24GiB reserved-unallocated after first OOM)
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export TRITON_CACHE_DIR=/tmp/triton-${R}; rm -rf "${TRITON_CACHE_DIR}"; mkdir -p "${TRITON_CACHE_DIR}"   # keep torch.compile cache OFF ~/.triton (killed this run at 9% via home inode quota)
export PROMPT_TYPES='"${PROMPT_TYPES:-full}"'
export MF_USE_FA2='"${MF_USE_FA2:-0}"' CAPTION_MAX_SEC='"${CAPTION_MAX_SEC:-300}"'
export GENRE_HINT="'"${GENRE_HINT}"'"
python '"${CODE}"'/lumi/goa_caption_task.py \
  --shard '"${OUT}"'/shards/shard_${R}.txt \
  --archive '"${ARCHIVE}"' --out '"${OUT}"' '"${LIMIT_ARG}"' \
  2>&1 | sed "s/^/[rank ${R}] /"
'
NJSON=$(ls "${OUT}/json" 2>/dev/null | wc -l)
echo "[goa-cap] captions=${NJSON}/${N} -> ${OUT}/json"
# SUCCESS = json count vs ${N}; resumable — re-submit to continue. Never trust rc alone.
