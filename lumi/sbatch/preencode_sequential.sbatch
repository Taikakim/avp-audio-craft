#!/bin/bash
# preencode_sequential.sbatch — GHOST-NOTE 2026-08-17 (Kim direct): SAME-L pre-encode, same node
# + same 8-way shard split as preencode_bigset.sbatch, but the 8 shards run ONE AT A TIME
# (sequential srun steps) instead of all 8 concurrently. preencode_bigset's concurrent
# --ntasks=8 approach has OOM'd repeatedly on the goa bigset (kernel oom_kill from 8 GCD-pinned
# shards' CPU-side audio decode piling up RAM at once, even at --num_workers 1 each) --
# CONTINUITY's fixes there (decode-duration cap, RSS instrumentation, leak scan) are still
# UNRESOLVED as of this writing. Running sequentially sidesteps the pileup entirely (only one
# shard's decode workers are ever alive), independent of whatever the root cause turns out to
# be -- slower wall-clock (no cross-shard overlap), but the whole node's CPUs are free for the
# one active shard, so --num_workers can go a bit higher than the parallel job's forced 1.
#
# GENERIC over dataset: BIGSET_DIR / OUT / SAMPLE_SIZE all overridable, same convention as
# preencode_bigset.sbatch and the goa_sep/goa_caption/goa_granite Suomisoundi parameterization.
#
# RUN:  sbatch --export=ALL,BIGSET_DIR=/scratch/project_465003186/suomisoundi_archive,OUT=/scratch/project_465003186/suomisoundi_latents lumi/sbatch/preencode_sequential.sbatch
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=preencode_sequential
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code; MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
BIGSET=${BIGSET_DIR:-${SCRATCH}/goa_archive}
OUT=${OUT:-${SCRATCH}/latents_goa_bigset}
SS=${SAMPLE_SIZE:-16777216}          # 2^24 samples = 380.4 s = T4096 latent frames
NW=${PREENC_NUM_WORKERS:-2}          # safe to raise a bit vs the parallel job's forced 1 -- only
                                      # one shard's workers are ever alive at once here
mkdir -p "${OUT}"

[ -n "${SIF}" ] || { echo "[preenc] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[preenc] FATAL: ${VENV} missing"; exit 1; }
[ -d "${BIGSET}" ] || { echo "[preenc] FATAL: ${BIGSET} missing"; exit 1; }
grep -q -- "--shard" "${CODE}/stable-audio-3/scripts/pre_encode_dataset.py" || { echo "[preenc] FATAL: pre_encode_dataset on LUMI lacks --shard (rsync it)"; exit 1; }
echo "[preenc] image=${SIF}  audio=${BIGSET}  out=${OUT}  SS=${SS} (T$((SS/4096)))  num_workers=${NW}  MODE=sequential"

for ARM in 0 1 2 3 4 5 6 7; do
  echo "[preenc] === shard ${ARM}/8 starting $(date +%H:%M:%S) ==="
  srun --overlap --cpu-bind=none --mpi=none --nodes=1 --ntasks=1 --gpus-per-task=1 --cpus-per-task=56 \
    singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
  set -euo pipefail
  ARM='"${ARM}"'
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
  python -u ${CODE}/stable-audio-3/scripts/pre_encode_dataset.py \
      --model same-l --data_dir '"${BIGSET}"' \
      --shard ${ARM}/8 --sample_size '"${SS}"' --pad --batch_size 1 --num_workers '"${NW}"' \
      --output_path '"${OUT}"' 2>&1 | sed "s/^/[shard ${ARM}] /"
  '
  echo "[preenc] === shard ${ARM}/8 done $(date +%H:%M:%S) ==="
done

set +e
NLAT=$(ls "${OUT}"/*.npy 2>/dev/null | grep -vc silence)
echo "[preenc] DONE — ${NLAT} latents in ${OUT} (verify vs $(cat ${BIGSET}/filelist.txt 2>/dev/null | wc -l) source files; per-shard counts differ)"
echo "[preenc] pull: rsync -av <this>:${OUT}/ ~/Projects/<dataset>_latents/"
