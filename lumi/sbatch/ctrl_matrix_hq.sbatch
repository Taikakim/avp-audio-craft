#!/bin/bash
# ctrl_matrix_hq.sbatch — control-matrix campaign fan-out on ONE standard-g node (8 GCDs) via
# HyperQueue. 60 short single-GCD training runs (20 features x 3 variants: LatCH head / FiLM
# lone scalar / FiLM+BPM dual scalar) packed across the node's 8 GCDs, HQ draining the queue as
# workers free up. This is CSC's textbook >20-short-single-node-tasks case (throughput guide §1).
#
# PATTERN SOURCES (reuse, not reinvent):
#   - docs/lumi-throughput-workflow-guide.md §1  — hq server + 8 workers (one per GCD via
#     SLURM_PROCID/ROCR_VISIBLE_DEVICES), hq submit, stage-once-to-/flash.
#   - lumi/sbatch/efp_fp32_compare.sbatch        — PROVEN container/MIOpen/bind deployment:
#     cotainr sa3.sif, /code tree, PYTHONPATH, MIOPEN_DISABLE_CACHE=1 + FIND_MODE=2 +
#     TUNABLEOP=0, --bind PROJ,SCRATCH,FLASH,/tmp, HF_HUB_OFFLINE=1, stage latents to /flash.
#
# TASK LIST: generated separately and reproducibly by lumi/gen_ctrl_matrix_tasks.sh into
#   ${CODE}/lumi/ctrl_matrix_tasks.txt  (one full train invocation per line, with its save-dir).
# To trim the campaign, edit / head that file before submitting — the sbatch just fans out
# whatever lines are present.
#
# HQ ON LUMI: CSC ships HyperQueue as a module (docs.csc.fi/apps/hyperqueue/, LUMI build 0.18.0):
#   module use /appl/local/csc/modulefiles && module load hyperqueue
# If the module is ever unavailable, drop a downloaded static hq binary at ${CODE}/lumi/bin/hq
# (github.com/It4innovations/hyperqueue releases, musl x86_64) and set HQ_BIN to it — the script
# honours an HQ_BIN override. See the FALLBACK note at the bottom for a module-free path.
#
# GCD PINNING: srun launches 8 tasks (one per GCD); each exports ROCR_VISIBLE_DEVICES=$SLURM_PROCID
# before `hq worker start`, so every worker (and the train subprocess it runs) sees exactly one
# distinct GCD. This is our own inference per the guide's §1 flag — smoke-test with an 8-task
# rocm-smi echo before trusting it for a real campaign.
#
# BILLING/WALLTIME: whole node x walltime. 36 h generous headroom for ~60 short runs over 8 GCDs
# (each LatCH head is minutes; FiLM runs are the longer ones). Arms that finish early free their
# worker for the next queued task — that is the whole point.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=36:00:00
#SBATCH --job-name=sa3_ctrl_matrix_hq
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/ctrl_matrix
TASKLIST=${CODE}/lumi/ctrl_matrix_tasks.txt
LOGDIR=${RUNROOT}/hq_logs
mkdir -p "${RUNROOT}" "${LOGDIR}" "${FLASH}"

# ── HyperQueue binary: prefer the CSC module, honour an HQ_BIN override, else fail loud ──────
if [ -n "${HQ_BIN:-}" ]; then
  echo "[ctrlmx] using HQ_BIN override: ${HQ_BIN}"
else
  module use /appl/local/csc/modulefiles || true
  module load hyperqueue || true
  HQ_BIN=$(command -v hq || true)
fi
if [ -z "${HQ_BIN:-}" ]; then
  echo "[ctrlmx] FATAL: no hq binary (module load hyperqueue failed and HQ_BIN unset)." 1>&2
  echo "[ctrlmx] drop a static hq at ${CODE}/lumi/bin/hq and re-run with HQ_BIN=that path." 1>&2
  exit 1
fi
echo "[ctrlmx] hq: ${HQ_BIN} ($(${HQ_BIN} --version 2>/dev/null || echo version-unknown))"

# ── generate the task list if missing (idempotent; reproducible from the generator) ─────────
if [ ! -s "${TASKLIST}" ]; then
  echo "[ctrlmx] task list absent -> generating ${TASKLIST}"
  bash "${CODE}/lumi/gen_ctrl_matrix_tasks.sh" > "${TASKLIST}"
fi
NTASKS=$(grep -cve '^[[:space:]]*$' "${TASKLIST}")
echo "[ctrlmx] ${NTASKS} tasks in ${TASKLIST}"

# ── stage BOTH corpora to NVMe once (idempotent; guide §3 stage-once-per-node) ──────────────
for DS in latents_sa3 latents_avp; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[ctrlmx] sa3 latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)  avp latents: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)"

# ── HyperQueue server ───────────────────────────────────────────────────────────────────────
export HQ_SERVER_DIR="${RUNROOT}/hq-server/${SLURM_JOB_ID}"
mkdir -p "${HQ_SERVER_DIR}"
"${HQ_BIN}" server start &
until "${HQ_BIN}" job list &> /dev/null; do sleep 1; done
echo "[ctrlmx] hq server up (HQ_SERVER_DIR=${HQ_SERVER_DIR})"

# ── 8 workers, one per GCD. Each task's SLURM_PROCID -> its single visible GCD ───────────────
# Env before `hq worker start` is inherited by the worker and by the train subprocess it runs,
# so ROCR/HIP_VISIBLE_DEVICES=$SLURM_PROCID pins each worker to one distinct GCD.
srun --overlap --cpu-bind=none --mpi=none bash -c '
  export ROCR_VISIBLE_DEVICES=$SLURM_PROCID
  # ROCR ONLY — adding HIP_VISIBLE_DEVICES stacks (HIP indexes into the ROCR-filtered
  # 1-GPU list -> index N>0 = No-HIP-GPUs; 7/8 workers dead, 2026-07-21 job 20068082)
  '"${HQ_BIN}"' worker start --manager slurm --on-server-lost finish-running --cpus=7
' &
"${HQ_BIN}" worker wait "${SLURM_NTASKS}"
echo "[ctrlmx] ${SLURM_NTASKS} workers registered"

# ── submit all tasks. One HQ task per task-list line; each sets its own MIOpen DB under /tmp ──
# The bash -c body is DOUBLE-quoted so fixed paths interpolate now; \$HQ_TASK_ID stays literal
# for HQ to fill at task runtime. Task-list lines are apostrophe/backtick-free (generator
# guarantees this), so injecting one into the body is quote-safe.
i=0
while IFS= read -r CMD; do
  case "${CMD}" in ""|\#*) continue ;; esac
  i=$((i+1))
  "${HQ_BIN}" submit \
    --name="ctrlmx_${i}" \
    --cpus=7 \
    --stdout="${LOGDIR}/j%{JOB_ID}-t%{TASK_ID}.out" \
    --stderr="${LOGDIR}/j%{JOB_ID}-t%{TASK_ID}.err" \
    -- singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c "
      set -euo pipefail
      export HF_HOME=${MODELS} HF_HUB_OFFLINE=1
      export PYTHONPATH=${CODE}/control:${CODE}/stable-audio-3:${CODE}/lumi/vendor
      export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
      export MIOPEN_USER_DB_PATH=/tmp/miopen-\$HQ_TASK_ID MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-\$HQ_TASK_ID
      export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
      rm -rf \$MIOPEN_USER_DB_PATH; mkdir -p \$MIOPEN_USER_DB_PATH
      cd ${CODE}/stable-audio-3
      echo [ctrlmx task \$HQ_TASK_ID] GCD ROCR=\$ROCR_VISIBLE_DEVICES
      ${CMD}
    "
done < "${TASKLIST}"
echo "[ctrlmx] submitted ${i} tasks; draining across ${SLURM_NTASKS} GCDs"

# ── wait for the queue to drain, then tear down ─────────────────────────────────────────────
"${HQ_BIN}" job wait all || true   # task failures must not kill the tail under set -e
echo "[ctrlmx] all jobs finished:"
"${HQ_BIN}" job list --all || true
"${HQ_BIN}" worker stop all || true
"${HQ_BIN}" server stop || true
echo "[ctrlmx] DONE. runs under ${RUNROOT}/ , logs under ${LOGDIR}/"

# ── FALLBACK (module-free, no HQ) ────────────────────────────────────────────────────────────
# If HyperQueue is unavailable AND cannot be downloaded, replace the server/worker/submit block
# above with a GCD-pinned parallel drain of the same ${TASKLIST} (8-wide, one GCD per lane):
#   mapfile -t LINES < "${TASKLIST}"
#   run_one() { local gcd=$1 line=$2
#     ROCR_VISIBLE_DEVICES=$gcd HIP_VISIBLE_DEVICES=$gcd \
#     singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c "<same env>; $line"
#   }
#   idx=0
#   for line in "${LINES[@]}"; do
#     [ -z "$line" ] && continue
#     gcd=$(( idx % 8 )); run_one "$gcd" "$line" & idx=$((idx+1))
#     (( idx % 8 == 0 )) && wait     # crude: waits per wave of 8 (no early-refill)
#   done
#   wait
# HQ is strongly preferred: it refills a freed GCD immediately instead of waiting for the whole
# wave (matters here because LatCH heads finish in minutes but FiLM runs take much longer).
# A plain `sbatch --array=0-59%8 ctrl_matrix_array.sbatch` (SLURM_ARRAY_TASK_ID -> task-list line)
# is the other fallback now that direct sbatch works on this project (guide ADDENDUM 2026-07-15).
