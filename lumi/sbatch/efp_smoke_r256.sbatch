#!/bin/bash
# efp_smoke_r256.sbatch — FIRST LUMI SMOKE RUN (Kim, 2026-07-13), paste-ready for the
# EFP Workflows web UI (workflows.my-eurohpc.eu -> Data Management -> Job Scripts).
#
# Purpose: prove the training loop runs on LUMI at all. Small on purpose:
#   r256, lr 1e-4, batch 8, alpha 256 (=rank, s=1 per the 2026-07-12 alpha audit),
#   --frames 512 (multiples-of-256 rule), 300 steps, ckpt every 100.
# Dataset: Kim's upload /scratch/project_465003186/latents_avp_originals.tar.gz (288 crops).
#
# PREREQS (one SSH session on a login node BEFORE this job — compute nodes have no internet):
#   1. code:    tar of SAO/stable-audio-3 at ${CODE}/stable-audio-3  (pack_data.sh helps)
#   2. SIF:     module load LUMI cotainr && cotainr build ${SIF} \
#                 --base-image=/appl/local/containers/sif-images/lumi-rocm-rocm-6.2.4.sif \
#                 --conda-env=${CODE}/SAO/lumi/sa3-env.yml
#   3. models:  HF_HOME=${MODELS} python -c "from stable_audio_3 import StableAudioModel; StableAudioModel.from_pretrained('medium-base', device='cpu')"
#               (login node has internet; after this HF_HUB_OFFLINE=1 works on compute)
#
#SBATCH --account=project_465003186
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=60G
#SBATCH --time=01:30:00
#SBATCH --job-name=sa3_smoke_r256

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models            # HF cache pre-staged (see prereq 3)
RUN=${SCRATCH}/runs/smoke_r256_a256_lr1e4_f512_bs8
DATA=${FLASH}/latents_avp_originals

mkdir -p "${RUN}" "${FLASH}"
# stage dataset to NVMe once (idempotent)
if [ ! -d "${DATA}" ]; then
  mkdir -p "${DATA}"
  tar -xzf "${SCRATCH}/latents_avp_originals.tar.gz" -C "${DATA}" --strip-components=1
fi
echo "[smoke] dataset files: $(ls ${DATA}/*.npy 2>/dev/null | wc -l)"

# --nodes/--ntasks pinned HERE because the EFP workflow form controls the job
# allocation (its fields override the #SBATCH header and expose no node count).
# NO gpu flag on srun: requesting gres at step level errors ('Invalid generic
# resource') when the allocation carries none/other-format — the step inherits
# whatever GPUs the allocation has; the probe line below tells us the truth.
echo "[smoke] allocation: nodes=${SLURM_NNODES:-?} tasks=${SLURM_NTASKS:-?} gpus-on-node=${SLURM_GPUS_ON_NODE:-unset} job-gpus=${SLURM_JOB_GPUS:-unset}"
# NOTE the extra ',/tmp' bind: without it, /tmp inside the container is the SIF's
# baked-in 'nodev' overlay (see build warning), NOT the compute node's RAM tmpfs.
# MIOpen's perf-db needs a real tmpfs (WAL shared-memory locking), so we MUST bind
# the host node /tmp through.
srun --nodes=1 --ntasks=1 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c "
  set -euo pipefail
  export HF_HOME=${MODELS} HF_HUB_OFFLINE=1
  export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor   # package runs from source, not installed
  # MIOpen's failing file gfx90a6e.UKDB = the user KERNEL-CACHE (compiled-kernel
  # SQLite store). RELOCATING it failed on every filesystem we tried (/scratch, /flash,
  # host-bound /tmp) even though plain rollback-journal SQLite opens fine at those paths
  # -> the problem is MIOpen's own SQLite open, not the FS. So we DISABLE the kernel
  # cache instead of moving it: MIOpen then never opens the .ukdb. Cost = kernels
  # recompile each run (one-time few-min on the first step); acceptable for training.
  export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
  # Still point the DB/cache dirs at bound host /tmp (job-scoped, wiped) as a belt-and-
  # -suspenders in case any residual MIOpen path is consulted despite DISABLE_CACHE.
  export MIOPEN_USER_DB_PATH=/tmp/miopen-\${SLURM_JOB_ID:-0} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-\${SLURM_JOB_ID:-0}
  rm -rf \${MIOPEN_USER_DB_PATH}; mkdir -p \${MIOPEN_USER_DB_PATH}
  export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
  # --- non-fatal diagnostics IN THE REAL compute-node container (login-node tests
  #     can't reproduce the failure): what /tmp actually is, whether the gfx90a system
  #     perf-db ships, and rollback-vs-WAL at both /tmp and /flash to pin the mechanism.
  set +e
  echo '[smoke] /tmp mount:'; mount | grep ' /tmp ' || echo '  (no explicit /tmp mount line — using default)'
  echo '[smoke] gfx90a system perf-db shipped in container?'; find /opt -path '*miopen*' -name 'gfx90a*' 2>/dev/null | head -5
  export MIO_PROBE_FLASH=${FLASH}/miotest; mkdir -p \${MIO_PROBE_FLASH}
  python - <<'PY'
import sqlite3, os
for d in (os.environ['MIOPEN_USER_DB_PATH'], os.environ['MIO_PROBE_FLASH']):
    for mode in ('DELETE', 'WAL'):
        p = os.path.join(d, f'probe_{mode}.db')
        try:
            c = sqlite3.connect(p); got = c.execute(f'PRAGMA journal_mode={mode}').fetchone()[0]
            c.execute('create table if not exists t(x)'); c.execute('insert into t values (1)'); c.commit(); c.close()
            print(f'[smoke] sqlite {mode:6s} at {d}: OK (mode={got})')
        except Exception as e:
            print(f'[smoke] sqlite {mode:6s} at {d}: FAIL {e!r}')
PY
  set -e
  python -c 'import torch; print(\"[smoke] GPU visible:\", torch.cuda.is_available(), \"count:\", torch.cuda.device_count())'
  cd ${CODE}/stable-audio-3
  python scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${DATA} \
    --save_dir ${RUN} \
    --rank 256 --lora_alpha 256 \
    --lr 1e-4 --batch_size 8 \
    --frames 512 --beat-aware-crop \
    --optimizer fusion \
    --steps 300 \
    --checkpoint_every 100 \
    2>&1 | tee ${RUN}/train.log
"
echo '[smoke] DONE — checkpoints:' && ls -la "${RUN}"
# SUCCESS CRITERIA: loss lines printing, ~similar s/step to local r256 x8 batch scaled,
# 3 checkpoints on disk, no NaN. Then the real campaigns (arc_*, longctx_*) are go.
# NOTE alpha: 256 (=rank) per the audit convention — Kim floated 128 (s=0.5); use 256
# so the smoke matches the convention all new runs use. NOTE partition: small-g bills
# per GCD (~1.5 GCD-h for this smoke); standard-g allocates whole nodes (8 GCDs) —
# only use it when packing full 8-GCD campaign jobs. dev-g ok for <3h debug runs.
