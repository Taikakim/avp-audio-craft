#!/bin/bash
# preencode_bigset_finegrained.sbatch — CONTINUITY 2026-08-17 (Kim direct: "divide the set to
# eight parts... run as separate tasks"). The 8-way split ALREADY EXISTS (preencode_bigset.sbatch,
# --shard I/8) -- and it's exactly what preencode_bigset_smoke.sbatch tested in ISOLATION (shard
# 0/8 alone, one GPU, no other shards competing) and STILL watched RSS climb toward 300+GB. So an
# 8-way split alone doesn't dodge the leak -- it scales with FILE COUNT PROCESSED by one
# long-lived process, not multiprocessing/decode-length (both already ruled out this session), and
# 8 such leaks running in parallel on one node would exhaust node RAM faster than any one alone.
#
# ROOT CAUSE STILL UNKNOWN (unresolved after ~7 layers of isolation testing) -- this works AROUND
# it rather than fixing it: shard MUCH finer (96-way instead of 8-way, ~130 files/sub-shard vs
# ~1565) and RESTART the python process between sub-shards. A fresh process has clean RSS
# regardless of what leaked in the previous one -- process exit reclaims everything the OS gave
# it, leak or not. Each GPU rank loops sequentially through its 12 assigned sub-shard indices
# (0..95 strided by 8), one `python pre_encode_dataset.py --shard I/96` subprocess at a time.
# Overhead: ~12 model reloads/rank (~20s each) = a few minutes total, negligible against encode
# time. shard_i is 2-digit-formatted in latent_id (pre_encode_dataset.py:155) -- FINE must stay
# <=99 or the id format silently grows past 2 digits (still unique, just breaks the fixed-width
# convention downstream code may assume -- keep FINE<=99).
#
# RUN:  [FINE=96] sbatch lumi/sbatch/preencode_bigset_finegrained.sbatch
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
#SBATCH --job-name=preencode_bigset_fine
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code; MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
BIGSET=${BIGSET_DIR:-${SCRATCH}/goa_archive}
OUT=${OUT:-${SCRATCH}/latents_goa_bigset}
SS=${SAMPLE_SIZE:-16777216}          # 2^24 samples = 380.4 s = T4096 latent frames
FINE=${FINE:-96}                     # fine-grained shard count, MUST be <=99 (2-digit shard_i)
mkdir -p "${OUT}"

[ -n "${SIF}" ] || { echo "[preenc-fine] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[preenc-fine] FATAL: ${VENV} missing"; exit 1; }
[ -d "${BIGSET}" ] || { echo "[preenc-fine] FATAL: ${BIGSET} missing (big goa audio dir)"; exit 1; }
[ "${FINE}" -le 99 ] || { echo "[preenc-fine] FATAL: FINE=${FINE} > 99 breaks the 2-digit shard_i id format"; exit 1; }
grep -q -- "--shard" "${CODE}/stable-audio-3/scripts/pre_encode_dataset.py" || { echo "[preenc-fine] FATAL: pre_encode_dataset on LUMI lacks --shard (rsync it)"; exit 1; }
echo "[preenc-fine] image=${SIF}  audio=${BIGSET}  out=${OUT}  SS=${SS} (T$((SS/4096)))  FINE=${FINE}"

srun --overlap --cpu-bind=none --mpi=none --nodes=1 --ntasks=8 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
export ROCR_VISIBLE_DEVICES=${ARM}
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
FINE='"${FINE}"'
echo "[gpu-assign ${ARM}] ROCR=${ROCR_VISIBLE_DEVICES} FINE=${FINE}"
FIDX=${ARM}
while [ "${FIDX}" -lt "${FINE}" ]; do
  echo "[preenc-fine shard ${FIDX}/${FINE}] start $(date +%H:%M:%S)"
  python -u ${CODE}/stable-audio-3/scripts/pre_encode_dataset.py \
      --model same-l --data_dir '"${BIGSET}"' \
      --shard ${FIDX}/${FINE} --sample_size '"${SS}"' --pad --batch_size 1 --num_workers 1 \
      --output_path '"${OUT}"' 2>&1 | sed "s/^/[shard ${FIDX}\/${FINE}] /" \
    || echo "[preenc-fine shard ${FIDX}/${FINE}] FAILED (non-fatal, continuing to next sub-shard)"
  echo "[preenc-fine shard ${FIDX}/${FINE}] done $(date +%H:%M:%S)"
  FIDX=$((FIDX + 8))
done
echo "[preenc-fine ${ARM}] all assigned sub-shards done"
'
set +e
NLAT=$(ls "${OUT}"/*.npy 2>/dev/null | grep -vc silence)
echo "[preenc-fine] DONE — ${NLAT} latents in ${OUT} (verify vs $(cat ${BIGSET}/filelist.txt 2>/dev/null | wc -l) source files)"
echo "[preenc-fine] pull: rsync -av <this>:${OUT}/ ~/Projects/latents_goa_bigset/  then LOCAL: companion + caption merge"
