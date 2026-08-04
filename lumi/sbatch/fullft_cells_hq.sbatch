#!/bin/bash
# fullft_cells_hq.sbatch — the FULL standard model-matrix grid for every fullft arm, on LUMI
# (Kim direct 2026-07-21: "I also want the full ft evals from LUMI" — two local GPU wedges in
# 12 h; checkpoints are $SCRATCH-resident anyway).
#
# WHAT: one HQ task per fullft (label, last-epoch ckpt) under ${SCRATCH}/runs/fullft — 10 arms
# today (goa/avp x t256..t4096), each rendering 18 prompts x cfg{1,7,16} x w1.0 = 54 cells of
# 20 s / steps 24 with the EXACT local grid axes (lumi/matrix_prompts_snapshot.json — same
# prompt ids/texts/seeds, so the cells join the board directly). Outputs: wav + z0 + .mmline
# fragments in ${SCRATCH}/renders/matrix_cells, merged to matrix_manifest.jsonl at the end.
# Kim pulls; W's ingest transcodes + appends + rebuilds + ships (same flow as native cells).
#
# PATTERN: native_cells_hq.sbatch / ctrl_matrix_hq.sbatch verbatim (hq server + 8 GCD-pinned
# workers). HQ TRAP: task failures do NOT reach the sbatch rc — success = wav count vs 540.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=03:00:00
#SBATCH --job-name=sa3_fullft_cells_hq
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
OUTDIR=${SCRATCH}/renders/matrix_cells
RUNROOT=${SCRATCH}/runs/fullft_cells_hq
LOGDIR=${RUNROOT}/hq_logs
TASKLIST=${RUNROOT}/tasks-${SLURM_JOB_ID}.txt
PROMPTS=${CODE}/lumi/matrix_prompts_snapshot.json
mkdir -p "${OUTDIR}" "${RUNROOT}" "${LOGDIR}"
[ -f "${PROMPTS}" ] || { echo "[fullft-cells] FATAL: ${PROMPTS} missing (scp it with the code)"; exit 1; }

if [ -z "${HQ_BIN:-}" ]; then
  module use /appl/local/csc/modulefiles || true
  module load hyperqueue || true
  HQ_BIN=$(command -v hq || true)
fi
[ -n "${HQ_BIN:-}" ] || { echo "[fullft-cells] FATAL: no hq binary"; exit 1; }

# ── one task per fullft arm: the LAST epoch's slim ckpt (falls back to fat if no slim) ──
: > "${TASKLIST}"
for D in "${SCRATCH}"/runs/fullft/fullft_*/; do
  [ -d "${D}" ] || continue
  LABEL=$(basename "${D}")
  CK=$(ls "${D}"/epoch=*.weights.ckpt 2>/dev/null | sort -V | tail -1)
  [ -n "${CK}" ] || CK=$(ls "${D}"/epoch=*.ckpt 2>/dev/null | sort -V | tail -1)
  [ -n "${CK}" ] || { echo "[fullft-cells] no ckpt in ${LABEL}, skip"; continue; }
  EP=$(basename "${CK}" | grep -oE 'epoch=[0-9]+' | grep -oE '[0-9]+')
  echo "python ${CODE}/lumi/render_matrix_cells.py --label ${LABEL} --tag ep${EP} --ckpt ${CK} --prompts ${PROMPTS} --out ${OUTDIR}" >> "${TASKLIST}"
done
NTASKS=$(grep -cve '^[[:space:]]*$' "${TASKLIST}" || true)
echo "[fullft-cells] ${NTASKS} arm tasks (54 cells each -> expect $((NTASKS * 54)) wavs)"
cat "${TASKLIST}"
[ "${NTASKS}" -gt 0 ] || { echo "[fullft-cells] nothing to do"; exit 0; }

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
echo "[fullft-cells] ${SLURM_NTASKS} workers up"

i=0
while IFS= read -r CMD; do
  case "${CMD}" in ""|\#*) continue ;; esac
  i=$((i+1))
  "${HQ_BIN}" submit \
    --name="ftcells_${i}" \
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
      echo [ftcells task \$HQ_TASK_ID] GCD ROCR=\$ROCR_VISIBLE_DEVICES
      ${CMD}
    "
done < "${TASKLIST}"
echo "[fullft-cells] submitted ${i}; draining"
"${HQ_BIN}" job wait all || true   # task failures must NOT skip the merge/success-check tail (set -e)
"${HQ_BIN}" job list --all || true
"${HQ_BIN}" worker stop all || true
"${HQ_BIN}" server stop || true

python3 - <<PYEOF
import glob, json
frags = sorted(glob.glob("${OUTDIR}/*.mmline.json"))
with open("${OUTDIR}/matrix_manifest.jsonl", "w") as f:
    for p in frags:
        f.write(json.dumps(json.load(open(p))) + "\n")
print(f"[fullft-cells] merged {len(frags)} manifest lines -> matrix_manifest.jsonl")
PYEOF
NWAV=$(ls "${OUTDIR}"/*.wav 2>/dev/null | wc -l)
echo "[fullft-cells] SUCCESS CHECK: ${NWAV} wavs vs $((NTASKS * 54)) expected"
echo "[fullft-cells] per-task errors (if any): ${LOGDIR}/j*-t*.err — sbatch rc 0 is NOT task success"
