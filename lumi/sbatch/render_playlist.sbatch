#!/bin/bash
# render_playlist.sbatch — Kim direct 2026-08-15: the 24h T4096 YouTube playlist
# (Dadabots-metal-GAN homage) + matched-pair follow-ups, all off ONE manifest
# (eval/build_playlist_manifest.py, 128 entries: random T4096 checkpoint from BOTH avp
# and goa runs x random Music-Flamingo/Granite goa prompt x per-clip DoRA weight
# 0.8-1.2 (1.0 for the 2 full-FT labels) x unique seed).
#
# ONE node, 8 GPUs, 8-way sharded (render_playlist_manifest.py --shard I/8), same launch
# pattern as every other single-node multitorch job (--gpus-per-task=1, cgroup-pinned).
#
# STAGES (Kim's own ordering) — set STAGE=A/B256/B1024/C/D, or override the underlying
# FRAMES/CFG_OVERRIDE/DIST_SHIFT_RATE/PT_MEDIUM/SUBSET vars directly:
#   A     : the playlist itself.        frames=4096 cfg=manifest(7) n=128
#   B256  : length/HF matched pair.     frames=256  cfg=manifest(7) n=128
#   B1024 : length/HF matched pair.     frames=1024 cfg=manifest(7) n=128
#   C     : length-adaptive schedule ON (inference-time only, no retrain — model ships
#           with LogSNRShift(rate=0) hardcoded; rate=1.0 is the CLASS's own default,
#           confirmed via model.generate(dist_shift=...) 2026-08-15).
#           frames=4096 cfg=manifest(7) dist_shift_rate=1.0 subset=64 (first 64 by idx)
#   D     : post-trained model, cfg=1, same weights. full-FT-sourced slots have no
#           adapter to carry over -> render as PLAIN post-trained medium instead
#           (flagged per-clip in the output mmline.json, not silently merged).
#           frames=4096 cfg_override=1 pt_medium=1 n=128
#
# RUN (build the manifest ONCE, reuse across every stage/resubmit):
#   python3 eval/build_playlist_manifest.py   # writes eval/playlist_manifest_128.json
#   STAGE=A    sbatch lumi/sbatch/render_playlist.sbatch
#   STAGE=B256 sbatch lumi/sbatch/render_playlist.sbatch
#   STAGE=B1024 sbatch lumi/sbatch/render_playlist.sbatch
#   STAGE=C    sbatch lumi/sbatch/render_playlist.sbatch
#   STAGE=D    sbatch lumi/sbatch/render_playlist.sbatch
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=08:00:00
#SBATCH --job-name=sa3_playlist
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
MANIFEST=${CODE}/eval/playlist_manifest_128.json
ROUT=${SCRATCH}/renders/playlist

STAGE=${STAGE:-A}
case "${STAGE}" in
  A)     FRAMES=4096 CFG_OVERRIDE= DIST_SHIFT_RATE= PT_MEDIUM=0 SUBSET= ;;
  B256)  FRAMES=256  CFG_OVERRIDE= DIST_SHIFT_RATE= PT_MEDIUM=0 SUBSET= ;;
  B1024) FRAMES=1024 CFG_OVERRIDE= DIST_SHIFT_RATE= PT_MEDIUM=0 SUBSET= ;;
  C)     FRAMES=4096 CFG_OVERRIDE= DIST_SHIFT_RATE=1.0 PT_MEDIUM=0 SUBSET=64 ;;
  D)     FRAMES=4096 CFG_OVERRIDE=1 DIST_SHIFT_RATE= PT_MEDIUM=1 SUBSET= ;;
  *) echo "[playlist] FATAL: unknown STAGE=${STAGE} (want A/B256/B1024/C/D)"; exit 1 ;;
esac
# explicit env override always wins over the STAGE preset
FRAMES=${FRAMES_OVERRIDE:-${FRAMES}}

[ -n "${SIF}" ] || { echo "[playlist] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[playlist] FATAL: ${VENV} missing"; exit 1; }
[ -f "${MANIFEST}" ] || { echo "[playlist] FATAL: ${MANIFEST} missing — run eval/build_playlist_manifest.py first"; exit 1; }
mkdir -p "${ROUT}"
echo "[playlist] STAGE=${STAGE} FRAMES=${FRAMES} CFG_OVERRIDE=${CFG_OVERRIDE:-manifest} DIST_SHIFT_RATE=${DIST_SHIFT_RATE:-off} PT_MEDIUM=${PT_MEDIUM} SUBSET=${SUBSET:-all}"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
VENV='"${VENV}"'; source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${SLURM_PROCID} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${SLURM_PROCID}
export TRITON_CACHE_DIR=/tmp/triton-${SLURM_PROCID} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-${SLURM_PROCID} /tmp/triton-${SLURM_PROCID}; mkdir -p /tmp/miopen-${SLURM_PROCID} /tmp/triton-${SLURM_PROCID}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True

ARGS="--manifest '"${MANIFEST}"' --shard ${SLURM_PROCID}/8 --out '"${ROUT}"'/stage'"${STAGE}"' --frames '"${FRAMES}"' --stage '"${STAGE}"'"
[ -n "'"${CFG_OVERRIDE:-}"'" ] && ARGS="${ARGS} --cfg-override '"${CFG_OVERRIDE:-}"'"
[ -n "'"${DIST_SHIFT_RATE:-}"'" ] && ARGS="${ARGS} --dist-shift-rate '"${DIST_SHIFT_RATE:-}"'"
[ "'"${PT_MEDIUM}"'" = "1" ] && ARGS="${ARGS} --pt-medium"
[ -n "'"${SUBSET:-}"'" ] && ARGS="${ARGS} --subset '"${SUBSET:-}"'"

echo "[rank ${SLURM_PROCID}/8] node=$(hostname) STAGE='"${STAGE}"' args: ${ARGS}"
python ${CODE}/lumi/render_playlist_manifest.py ${ARGS} \
  || echo "[rank ${SLURM_PROCID}] render FAILED (non-fatal, other ranks continue)"
'
echo "[playlist] STAGE=${STAGE} done. cells: $(ls ${ROUT}/stage${STAGE}/*.wav 2>/dev/null | wc -l)"
