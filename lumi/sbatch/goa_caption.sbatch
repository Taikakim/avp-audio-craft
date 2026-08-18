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

# ── SHARDS ARE PRE-MADE, NOT COMPUTED HERE (2026-08-18) ─────────────────────────────────────────
# Kim's design: pre-distribute one file list per GPU with lumi/make_caption_shards.py, THEN submit
# many small jobs. Small jobs backfill far better than one huge allocation, but they cannot each
# compute their own sharding -- every job would derive the SAME shards and caption the same tracks
# in parallel. Making the assignment once, up front, is race-free by construction and inspectable:
# read shard_007.txt and you know exactly what that GPU will do.
#   python3 lumi/make_caption_shards.py --archive ${SCRATCH}/goa_archive \
#       --out ${OUT} --shards 64
#   for O in 0 8 16 24 32 40 48 56; do SHARD_OFFSET=$O sbatch --nodes=1 --time=03:00:00 \
#       lumi/sbatch/goa_caption.sbatch; done
# Each job owns shards [SHARD_OFFSET, SHARD_OFFSET + ntasks). Rank r reads shard_$((OFFSET+r)).txt.
SHARD_OFFSET=${SHARD_OFFSET:-0}
NTASKS=$(( ${SLURM_NNODES:-1} * 8 ))
SDIR=${OUT}/shards
for R in $(seq 0 $(( NTASKS - 1 ))); do
  G=$(( SHARD_OFFSET + R ))
  F=$(printf "%s/shard_%03d.txt" "${SDIR}" "${G}")
  [ -f "${F}" ] || { echo "[goa-cap] FATAL: ${F} missing — run lumi/make_caption_shards.py first (shards are PRE-MADE, this script no longer generates them)"; exit 1; }
done
TODO=$(cat $(for R in $(seq 0 $(( NTASKS - 1 ))); do printf "%s/shard_%03d.txt " "${SDIR}" "$(( SHARD_OFFSET + R ))"; done) | wc -l)
echo "[goa-cap] shards ${SHARD_OFFSET}..$(( SHARD_OFFSET + NTASKS - 1 )) (${NTASKS} GPUs), ${TODO} tracks this job; prompts=${PROMPT_TYPES:-full}"
echo "[goa-cap] hint file: ${GENRE_HINT_FILE:-<none>} -> '${GENRE_HINT}'"

LIMIT_ARG=""
[ "${PROBE:-0}" = "1" ] && LIMIT_ARG="--limit 2" && echo "[goa-cap] PROBE MODE: 2 tracks/rank"

# NOT a DDP job -- these are NTASKS INDEPENDENT single-GPU captioners with no rendezvous and
# nothing crossing a node boundary, so the "multi-node is unsolved" warning in lumi-ops does NOT
# apply here (that is about forming ONE coordinated gradient group). Scaling out is just more
# shards. Same reasoning W used to run the suomisoundi bracket as separate single-node jobs.
srun --nodes=${SLURM_NNODES:-1} --ntasks=${NTASKS} --gpus-per-task=1 --cpus-per-task=7 \
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
  --shard $(printf '"${OUT}"'/shards/shard_%03d.txt $(( '"${SHARD_OFFSET}"' + R ))) \
  --archive '"${ARCHIVE}"' --out '"${OUT}"' '"${LIMIT_ARG}"' \
  2>&1 | sed "s/^/[rank ${R}] /"
'
NJSON=$(ls "${OUT}/json" 2>/dev/null | wc -l)
echo "[goa-cap] captions now ${NJSON} total in ${OUT}/json (this job was assigned ${TODO})"
echo "[goa-cap] remaining across the corpus: re-run lumi/make_caption_shards.py to see, or just"
echo "[goa-cap]   re-shard + resubmit — it is resume-aware and re-balances only what is left."
# SUCCESS = the json COUNT rising by ~${TODO}, never the exit code. Resumable: re-shard and
# re-submit to continue, and the width may change between runs.
