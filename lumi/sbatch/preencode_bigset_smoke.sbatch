#!/bin/bash
# preencode_bigset_smoke.sbatch — CONTINUITY 2026-08-15 (Kim direct): SINGLE-GPU, SINGLE-SHARD
# diagnostic for the still-unresolved preencode_bigset OOM (3 failed attempts in a row:
# 21073662 / 21148858 / 21149732, two rounds of blind fixes, real mechanism never confirmed).
#
# WHY SOLO, NOT 8-WAY: isolates whether the OOM needs 8-way node contention (the working
# theory so far) or happens even alone (would mean a per-shard leak/accumulation, a different
# bug entirely). Runs the EXACT same shard workload production shard 0 would do (--shard 0/8,
# same 1/8 slice, same --num_workers 1) with NO siblings competing for node RAM — directly
# comparable to a real shard's behavior, just isolated.
#
# INSTRUMENTATION (new this run, both in pre_encode_dataset.py and dataset.py::_ffmpeg_load):
# periodic main-process RSS every 20 batches + per-file WORKER-process RSS before/after every
# ffmpeg decode (tagged with filename + decoded byte count) — logs to this job's own .out, no
# extra flags needed. If a single file's decode causes a RSS jump, or RSS climbs unbounded
# across many files without dropping, that's caught here in the log BEFORE any OOM kill,
# instead of losing the evidence to block-buffered stdout again.
#
# ALSO: track-length cap tightened 1800s -> 720s (12 min) this run (Kim direct) — cuts off
# more of any DJ-mix/compilation-length outlier while the RSS instrumentation runs, independent
# of whether that theory turns out to be the real mechanism.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=06:00:00
#SBATCH --job-name=preencode_smoke
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code; MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
BIGSET=${BIGSET_DIR:-${SCRATCH}/goa_archive}
OUT=${OUT:-${SCRATCH}/latents_goa_bigset_smoke}
SS=${SAMPLE_SIZE:-16777216}          # 2^24 samples = 380.4 s = T4096 latent frames
SHARD=${SHARD:-0/8}                  # same slice production shard 0 would take
WORKERS=${WORKERS:-1}                # 0 = in-process, no DataLoader worker subprocess/queue/
                                      # file_system-sharing-strategy at all -- the isolating test
                                      # for whether the leak (confirmed worker-only, job 21154320:
                                      # RSS pid=worker 316GB/62.7%mem vs main pid 2.18GB) needs the
                                      # multiprocessing path or lives in _ffmpeg_load itself
mkdir -p "${OUT}"

[ -n "${SIF}" ] || { echo "[preenc-smoke] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[preenc-smoke] FATAL: ${VENV} missing"; exit 1; }
[ -d "${BIGSET}" ] || { echo "[preenc-smoke] FATAL: ${BIGSET} missing (big goa audio dir)"; exit 1; }
grep -q -- "--shard" "${CODE}/stable-audio-3/scripts/pre_encode_dataset.py" || { echo "[preenc-smoke] FATAL: pre_encode_dataset on LUMI lacks --shard (rsync it)"; exit 1; }
grep -q -- "_log_rss" "${CODE}/stable-audio-3/scripts/pre_encode_dataset.py" \
  || { echo "[preenc-smoke] FATAL: pre_encode_dataset on LUMI lacks the RSS instrumentation (code refresh needed)"; exit 1; }
grep -q -- "_log_rss" "${CODE}/stable-audio-3/stable_audio_3/data/dataset.py" \
  || { echo "[preenc-smoke] FATAL: dataset.py on LUMI lacks the RSS instrumentation (code refresh needed)"; exit 1; }
echo "[preenc-smoke] image=${SIF}  audio=${BIGSET}  out=${OUT}  SS=${SS} (T$((SS/4096)))  SHARD=${SHARD}  WORKERS=${WORKERS}"

srun --overlap --cpu-bind=none --mpi=none --nodes=1 --ntasks=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
export ROCR_VISIBLE_DEVICES=0
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
VENV='"${VENV}"'; source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-smoke MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-smoke
export TRITON_CACHE_DIR=/tmp/triton-smoke PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-smoke /tmp/triton-smoke; mkdir -p /tmp/miopen-smoke /tmp/triton-smoke
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || true
echo "[preenc-smoke] start $(date +%H:%M:%S)"
python -u ${CODE}/stable-audio-3/scripts/pre_encode_dataset.py \
    --model same-l --data_dir '"${BIGSET}"' \
    --shard '"${SHARD}"' --sample_size '"${SS}"' --pad --batch_size 1 --num_workers '"${WORKERS}"' \
    --output_path '"${OUT}"'
echo "[preenc-smoke] done $(date +%H:%M:%S)"
'
set +e
NLAT=$(ls "${OUT}"/*.npy 2>/dev/null | grep -vc silence)
echo "[preenc-smoke] DONE — ${NLAT} latents in ${OUT}"
echo "[preenc-smoke] RSS trend: grep '\[rss' <this>.out | less   (watch for unbounded growth or a jump tied to one file)"
