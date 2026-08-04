#!/bin/bash
# native_cells_hq.sbatch — native-training-length model-matrix cells for LUMI-resident
# checkpoints, HQ-packed on ONE node (CONTINUITY 2026-07-21; W-split: LUMI half).
#
# WHY: T>=2048 native cells (188-380 s renders) crashed Kim's desktop display (VRAM);
# the checkpoints needing them are on $SCRATCH anyway. eval/model_matrix_gen.py now
# SKIPS those locally ([native-skip] -> LUMI lane); this job is that lane.
#
# WHAT: enumerates every run dir under ${SCRATCH}/runs whose label carries t>=2048
# (fullft_*, fp32cmp_*t4096*, longctx_t2048*, future fp32frames_* arms), one HQ task
# per (label, checkpoint) = one ~200-380 s render on one GCD. Output contract (agreed
# with W, DM 2026-07-21): flat ${SCRATCH}/renders/native_cells/ with
#   {label}__{tag}__cfg7__w100__kl_bracket_0__s1000__d<D>.wav + .z0.npy + .mmline.json
# merged at the end into native_manifest.jsonl. Kim pulls; W ingests (transcode m4a,
# existence-check, append manifest, rebuild+ship).
#
# PATTERN: ctrl_matrix_hq.sbatch verbatim (hq server + 8 GCD-pinned workers + drain).
# HQ TRAP: task failures do NOT propagate to the sbatch exit code — success check is
# counting wavs vs tasks (printed at the end), never `sacct`.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=sa3_native_cells_hq
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
OUTDIR=${SCRATCH}/renders/native_cells
RUNROOT=${SCRATCH}/runs/native_cells_hq
LOGDIR=${RUNROOT}/hq_logs
TASKLIST=${RUNROOT}/tasks-${SLURM_JOB_ID}.txt
mkdir -p "${OUTDIR}" "${RUNROOT}" "${LOGDIR}"

# ── HyperQueue binary (module first, HQ_BIN override honoured) ──────────────────────────
if [ -z "${HQ_BIN:-}" ]; then
  module use /appl/local/csc/modulefiles || true
  module load hyperqueue || true
  HQ_BIN=$(command -v hq || true)
fi
[ -n "${HQ_BIN:-}" ] || { echo "[native] FATAL: no hq binary (module or HQ_BIN)"; exit 1; }
echo "[native] hq: ${HQ_BIN}"

# ── task list: every (label, ckpt) under runs/ whose label carries t>=2048 ──────────────
# find one- and two-level run dirs containing epoch=* checkpoints; label = dir basename;
# T parsed from the label's t<digits> token; dedupe epoch via .weights.ckpt preference.
: > "${TASKLIST}"
find "${SCRATCH}/runs" -maxdepth 3 -name "epoch=*.ckpt" 2>/dev/null | sed 's|/[^/]*$||' | sort -u | \
while read -r D; do
  LABEL=$(basename "${D}")
  T=$(echo "${LABEL}" | grep -oE '(^|_)t[0-9]+' | grep -oE '[0-9]+' | head -1 || true)
  [ -n "${T}" ] && [ "${T}" -ge 2048 ] || continue
  ls "${D}"/epoch=*.ckpt 2>/dev/null | sed 's/\.weights\.ckpt$/.ckpt/' | sort -u | \
  while read -r CK; do
    # prefer the slim .weights.ckpt when both exist (identical state_dict, faster load)
    W="${CK%.ckpt}.weights.ckpt"; [ -f "${W}" ] && CK="${W}"
    [ -f "${CK}" ] || continue
    EP=$(basename "${CK}" | grep -oE 'epoch=[0-9]+' | grep -oE '[0-9]+')
    echo "python ${CODE}/lumi/render_native_cells.py --label ${LABEL} --tag ep${EP} --frames ${T} --ckpt ${CK} --out ${OUTDIR}" >> "${TASKLIST}"
  done
done
NTASKS=$(grep -cve '^[[:space:]]*$' "${TASKLIST}" || true)
echo "[native] ${NTASKS} (label,ckpt) tasks:"
sed 's/.*--label /  /;s/ --frames.*//' "${TASKLIST}" | sort | uniq -c | sort -rn | head -40
[ "${NTASKS}" -gt 0 ] || { echo "[native] nothing to do"; exit 0; }

# ── HQ server + 8 GCD-pinned workers (ctrl_matrix_hq pattern verbatim) ──────────────────
export HQ_SERVER_DIR="${RUNROOT}/hq-server/${SLURM_JOB_ID}"
mkdir -p "${HQ_SERVER_DIR}"
"${HQ_BIN}" server start &
until "${HQ_BIN}" job list &> /dev/null; do sleep 1; done
srun --overlap --cpu-bind=none --mpi=none bash -c '
  export ROCR_VISIBLE_DEVICES=$SLURM_PROCID
  # ROCR ONLY — exporting HIP_VISIBLE_DEVICES too STACKS with it (HIP indexes into the
  # ROCR-filtered 1-GPU list, so index N>0 = No-HIP-GPUs) — 2026-07-21 failure, 7/8
  # workers GPU-less; the proven muscriptor block uses ROCR alone.
  '"${HQ_BIN}"' worker start --manager slurm --on-server-lost finish-running --cpus=7
' &
"${HQ_BIN}" worker wait "${SLURM_NTASKS}"
echo "[native] ${SLURM_NTASKS} workers up"

i=0
while IFS= read -r CMD; do
  case "${CMD}" in ""|\#*) continue ;; esac
  i=$((i+1))
  "${HQ_BIN}" submit \
    --name="native_${i}" \
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
      echo [native task \$HQ_TASK_ID] GCD ROCR=\$ROCR_VISIBLE_DEVICES
      ${CMD}
    "
done < "${TASKLIST}"
echo "[native] submitted ${i}; draining"
"${HQ_BIN}" job wait all || true   # task failures must NOT skip the merge/success-check tail (set -e)
"${HQ_BIN}" job list --all || true
"${HQ_BIN}" worker stop all || true
"${HQ_BIN}" server stop || true

# ── merge per-cell manifest fragments + the honest success count (the HQ trap) ──────────
python3 - <<PYEOF
import glob, json
frags = sorted(glob.glob("${OUTDIR}/*.mmline.json"))
with open("${OUTDIR}/native_manifest.jsonl", "w") as f:
    for p in frags:
        f.write(json.dumps(json.load(open(p))) + "\n")
print(f"[native] merged {len(frags)} manifest lines -> native_manifest.jsonl")
PYEOF
# per-task cell counts (2026-07-22 grid widening, Kim): fullft tasks -> 3 cells
# (cfg x {1,7,16}, strength collapses to 1.0), everything else -> 9 (3 cfg x 3 strengths).
NFULL=$(grep -c 'render_native_cells.py --label fullft_' "${TASKLIST}" || true)
NEXPECT=$(( NFULL * 3 + (NTASKS - NFULL) * 9 ))
NWAV=$(ls "${OUTDIR}"/*.wav 2>/dev/null | wc -l)
echo "[native] SUCCESS CHECK: ${NWAV} wavs on disk vs ${NEXPECT} expected (${NTASKS} tasks; ${NFULL} fullft x3 + $((NTASKS-NFULL)) adapter x9)"
echo "[native] NOTE: pre-widening 120s-window wavs from job 20094760 are NOT counted here if Kim purged them; if not purged they inflate NWAV — purge before trusting the count."
echo "[native] failures (if any) live in ${LOGDIR}/j*-t*.err — sbatch exit 0 does NOT mean all tasks passed"
