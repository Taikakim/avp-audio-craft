#!/bin/bash
# preencode_bigset.sbatch — CONTINUITY 2026-08-13 (Kim direct): 8-GCD PARALLEL SAME-L pre-encode of
# the big goa set. Live-encode (#68 fullft_bigset --data_dir) is just a test; this writes T4096
# latents to $SCRATCH so Kim can pull them to his drive and future runs train on --encoded_dir.
#
# ONE standard-g node, 8 GCDs, ROCR-pinned (ROCR_VISIBLE_DEVICES=$SLURM_PROCID ALONE, never +HIP),
# one INDEPENDENT encode per GCD over the deterministic 1/8 slice pre_encode_dataset --shard I/8.
# Shard-prefixed latent ids -> all 8 write ONE collision-free dir. Multitorch image + sa3_train_venv_mt
# (the #68/#69 proven env; encode is SAME forward, no training backward, so the fp32-miopen issue N/A).
#
# SCOPE / CAVEATS (Kim, read before treating this as the canonical set):
#   * ONE T4096 window per track. Long goa tracks (>380s) yield only their first ~380s crop — LESS
#     coverage than the live-encode's per-epoch random crop or latents_sa3's beat-manifest ~2 crops/
#     track. Fine for a first latents-on-the-drive pass; MULTI-CROP is a v2 (needs a beat manifest).
#   * NO captions + NO .TIMESERIES.npz companions here. pre_encode_dataset writes latent + a bare .json;
#     captions (goa_caption_sidecar.json) + canonical sidecars (from goa_archive_features, via the
#     tested sa3_encode_from_manifest --companion-only) are a LOCAL post-step after Kim pulls — keeps
#     the whole-track store dependency off this GPU job.
#
# RUN:  SS + OUT overridable.  sbatch lumi/sbatch/preencode_bigset.sbatch
# then Kim:  rsync $SCRATCH/latents_goa_bigset (or the tar) to the drive.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=preencode_bigset
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code; MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
BIGSET=${BIGSET_DIR:-${SCRATCH}/goa_archive}
OUT=${OUT:-${SCRATCH}/latents_goa_bigset}
SS=${SAMPLE_SIZE:-16777216}          # 2^24 samples = 380.4 s = T4096 latent frames
mkdir -p "${OUT}"

[ -n "${SIF}" ] || { echo "[preenc] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[preenc] FATAL: ${VENV} missing"; exit 1; }
[ -d "${BIGSET}" ] || { echo "[preenc] FATAL: ${BIGSET} missing (big goa audio dir)"; exit 1; }
grep -q -- "--shard" "${CODE}/stable-audio-3/scripts/pre_encode_dataset.py" || { echo "[preenc] FATAL: pre_encode_dataset on LUMI lacks --shard (rsync it)"; exit 1; }
echo "[preenc] image=${SIF}  audio=${BIGSET}  out=${OUT}  SS=${SS} (T$((SS/4096)))"

srun --overlap --cpu-bind=none --mpi=none --nodes=1 --ntasks=8 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
export ROCR_VISIBLE_DEVICES=${ARM}
echo "[gpu-assign] shard=${ARM}/8 ROCR=${ROCR_VISIBLE_DEVICES}"
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
VENV='"${VENV}"'; source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-${ARM} /tmp/triton-${ARM}; mkdir -p /tmp/miopen-${ARM} /tmp/triton-${ARM}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || true
echo "[preenc shard ${ARM}] start $(date +%H:%M:%S)"
python ${CODE}/stable-audio-3/scripts/pre_encode_dataset.py \
    --model same-l --data_dir '"${BIGSET}"' \
    --shard ${ARM}/8 --sample_size '"${SS}"' --pad --batch_size 1 \
    --output_path '"${OUT}"' 2>&1 | tail -n +1 | sed "s/^/[shard ${ARM}] /"
echo "[preenc shard ${ARM}] done $(date +%H:%M:%S)"
'
set +e
NLAT=$(ls "${OUT}"/*.npy 2>/dev/null | grep -vc silence)
echo "[preenc] DONE — ${NLAT} latents in ${OUT} (verify vs $(cat ${BIGSET}/filelist.txt 2>/dev/null | wc -l) source files; per-shard counts differ)"
echo "[preenc] pull: rsync -av <this>:${OUT}/ ~/Projects/latents_goa_bigset/  then LOCAL: companion + caption merge"
