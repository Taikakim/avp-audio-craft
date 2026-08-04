#!/bin/bash
# goa_sep.sbatch — BS-RoFormer stem separation over the FULL goa_archive on LUMI
# (CONTINUITY 2026-07-29, Kim direct: offload separation; stems as ~192k m4a).
# 8 GCD-pinned ranks, round-robin shards, resumable (.sep_done markers) — a wall
# timeout costs only in-flight tracks; RE-SUBMIT this same script to continue.
#
# PREREQS (fail-loud checks below):
#   1. archive rsync'd:            ${SCRATCH}/goa_archive/  (Kim's transfer)
#   2. offload venv built + GREEN: ${SCRATCH}/goa_offload_venv  (lumi/build_offload_venv.sh on uan18)
#   3. model staged:               ${PROJ}/models/bs-roformer/jarredou-BS-ROFO-SW-Fixed-drums/
#   4. mir src staged:             ${CODE}/mir-src/  (preprocessing/ + core/ + classification/)
#
# PROBE MODE (run FIRST — validates the port in minutes, not node-days):
#   sbatch --time=00:40:00 --export=ALL,PROBE=1 lumi/sbatch/goa_sep.sbatch
#   -> each rank separates 2 tracks then exits; check timings + that stems are .m4a not .flac
#      (a .flac fallback means ffmpeg is missing from PATH -> rerun build_offload_venv.sh).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=47:00:00
#SBATCH --job-name=sa3_goa_sep
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
VENV=${SCRATCH}/goa_offload_venv
ARCHIVE=${SCRATCH}/goa_archive
OUT=${SCRATCH}/goa_archive_stems
MODELD=${PROJ}/models/bs-roformer
mkdir -p "${OUT}/shards"

[ -d "${ARCHIVE}" ] || { echo "[goa-sep] FATAL: ${ARCHIVE} missing — archive not rsync'd yet"; exit 1; }
# NOTE: test bin/activate (regular file), NOT bin/python — the venv was created INSIDE the
# SIF, so bin/python symlinks to the container's conda python, which is a BROKEN link on the
# host where this prolog runs ([ -x ] follows it -> false-missing; probes 20422459/60).
[ -f "${VENV}/bin/activate" ] || { echo "[goa-sep] FATAL: ${VENV} missing — run lumi/build_offload_venv.sh on uan18"; exit 1; }
[ -d "${MODELD}/jarredou-BS-ROFO-SW-Fixed-drums" ] || { echo "[goa-sep] FATAL: BS-RoFormer model not staged under ${MODELD}"; exit 1; }
[ -d "${CODE}/mir-src/preprocessing" ] || { echo "[goa-sep] FATAL: ${CODE}/mir-src missing (rsync mir/src)"; exit 1; }

# ── enumerate + round-robin split into 8 shards (stable order; resumable via .sep_done) ──
LIST=${OUT}/shards/all_tracks.txt
find "${ARCHIVE}" -type f \( -iname '*.mp3' -o -iname '*.flac' -o -iname '*.m4a' \) | sort > "${LIST}"
N=$(wc -l < "${LIST}")
echo "[goa-sep] ${N} tracks; splitting round-robin into 8 shards"
for R in 0 1 2 3 4 5 6 7; do awk -v r=${R} 'NR % 8 == r' "${LIST}" > "${OUT}/shards/shard_${R}.txt"; done

LIMIT_ARG=""
[ "${PROBE:-0}" = "1" ] && LIMIT_ARG="--limit 2" && echo "[goa-sep] PROBE MODE: 2 tracks/rank"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
R=${SLURM_PROCID}
# NO ROCR export: pinning here comes from srun --gpus-per-task=1 (cgroup, 1 GPU renumbered to
# index 0 per task — the efp training-sbatch pattern). Adding ROCR_VISIBLE_DEVICES=$RANK on top
# indexes into the 1-GPU cgroup list -> ranks 1-7 see NO GPU (probe 20422524 rank-1 crash at
# model.to(device)). ROCR-alone is for the HQ pattern where tasks share the full allocation.
source '"${VENV}"'/bin/activate           # venv python + SIF torch (system-site) + static ffmpeg
export MIR_SRC='"${CODE}"'/mir-src
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
# home-inode safety — keep torch.compile + MIOpen user caches OFF $HOME (the ~/.triton quota
# death that stalled captions at 9%; separation ran at scale would refill the 100k limit too)
export TRITON_CACHE_DIR=/tmp/triton-${R}; rm -rf "${TRITON_CACHE_DIR}"; mkdir -p "${TRITON_CACHE_DIR}"
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
rm -rf "${MIOPEN_USER_DB_PATH}"; mkdir -p "${MIOPEN_USER_DB_PATH}"
python '"${CODE}"'/lumi/goa_sep_task.py \
  --shard '"${OUT}"'/shards/shard_${R}.txt \
  --archive '"${ARCHIVE}"' --out '"${OUT}"' \
  --model-dir '"${MODELD}"' '"${LIMIT_ARG}"' \
  2>&1 | sed "s/^/[rank ${R}] /"
'
NDONE=$(find "${OUT}" -name '.sep_done' 2>/dev/null | wc -l)
NM4A=$(find "${OUT}" -name '*.m4a' 2>/dev/null | wc -l)
NFLAC=$(find "${OUT}" -name '*.flac' 2>/dev/null | wc -l)
echo "[goa-sep] done-markers=${NDONE}/${N}  m4a=${NM4A}  flac-fallbacks=${NFLAC}"
if [ "${NFLAC}" -gt 0 ]; then echo "[goa-sep] WARNING: FLAC fallbacks present — ffmpeg missing? (size blowup; fix venv + re-run)"; fi
# NOT `[ cond ] && echo` — as the LAST command, a false cond returns rc=1 and the whole job
# reports FAILED on the SUCCESS path (probe 20422698: 72/72 m4a perfect, state FAILED).
# SUCCESS = done-markers count vs ${N}; re-submit to continue after a timeout. Never trust rc.
