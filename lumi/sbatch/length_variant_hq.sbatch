#!/bin/bash
# length_variant_hq.sbatch — LUMI leg of the 2026-08-02 length-variant eval run. Fans out the
# 220 render tasks (55 LUMI-resident terminal checkpoints x 4 passes: native / goa_organic-20s /
# ptm-native / ptm-20s) across ONE standard-g node's 8 GCDs via HyperQueue, HQ draining as workers
# free. This is CSC's >20-short-single-node-tasks case (throughput guide §1) — same pattern as
# lumi/sbatch/ctrl_matrix_hq.sbatch, adapted for RENDER (no latent staging; LUMI-staged models
# offline). Spec: docs/superpowers/specs/2026-08-02-eval-native-ptm-length-render-design.md.
#
# PATTERN SOURCES (reuse, not reinvent):
#   - ctrl_matrix_hq.sbatch                     — the HQ fan-out this is copied from (server + 8
#     ROCR-pinned workers + submit-loop + drain), incl. the ROCR-ONLY GCD-pinning fix.
#   - lumi/render_matrix_cells.py               — the per-(label,ckpt) render worker each task runs.
#   - lumi/length_variant_tasks.txt             — the task list (gen_length_variant_tasks.py, local).
#   - lumi/matrix_prompts_lenvar9.json / _goa.json — the 9-prompt (manifest-sourced) + goa-only snaps.
#
# GCD PINNING: srun launches 8 tasks (one per GCD); each exports ROCR_VISIBLE_DEVICES=$SLURM_PROCID
# ALONE before `hq worker start` — never also HIP_VISIBLE_DEVICES (they stack: HIP indexes into the
# ROCR-filtered 1-GPU list -> index N>0 = No-HIP-GPUs; 7/8 workers dead, 2026-07-21 job 20068082).
#
# VERIFY BY ARTIFACT COUNT, NOT sbatch rc: after the drain, count .wav/.mmline.json under RENDER_OUT
# (the guide's "count outputs, not the return code" rule) before trusting completion.
#
# INGEST (local, after): eval/ingest_native_cells.py pulls RENDER_OUT back, transcodes + appends the
# manifest; then rebuild dora_table/model_matrix. The 8 kept prompts' 20s stay LOCAL (rendered on
# 7.2.3) — LUMI only emits the genuinely-new cells, so no cross-backend duplication of existing 20s.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=sa3_lenvar_hq
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
# multitorch (ROCm7+FA2) per C's review 2026-08-04: sa3.sif (ROCm 6.2) + MIOPEN_FIND_MODE=2
# is the exact combo that hung this session on gfx90a's find-fallback, and native T2048/T4096
# conv shapes are unproven on it; multitorch is proven for our renders (melody-wall tails)
# and faster. MTSIF/RENDER_VENV overridable.
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${RENDER_VENV:-${SCRATCH}/sa3_train_venv_mt}
MODELS=${PROJ}/models
RENDER_OUT=${SCRATCH}/renders/length_variant
TASKLIST=${TASKLIST:-${CODE}/lumi/length_variant_tasks.txt}   # override for a ptm-only re-run
LOGDIR=${RENDER_OUT}/hq_logs
mkdir -p "${RENDER_OUT}" "${LOGDIR}"

[ -n "${SIF}" ] || { echo "[lenvar] FATAL: no lumi-multitorch-full under /appl/local/laifs/containers/ -- pass MTSIF=" 1>&2; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[lenvar] FATAL: ${VENV} missing -- run lumi/build_train_venv_mt.sh on uan, or pass RENDER_VENV=" 1>&2; exit 1; }
echo "[lenvar] image=${SIF} venv=${VENV}"

# fail-loud model staging check (C's review note 2): every task loads medium-base, the two
# ptm passes load medium -- if either isn't staged offline in PROJ/models all 220 tasks die
# at load, 24h allocation wasted. Mirrors goa_caption's pre-drain check.
# 2026-08-09 (W): the ORIGINAL form of this check tested that a snapshots/ DIRECTORY existed.
# It passed on a 1.2 GB PARTIAL cache of stable-audio-3-medium whose config file was absent,
# so all 110 ptm tasks of job 20663606 died at load while the job reported COMPLETED and the
# summary line printed "DONE. 5336 wav". Existence is not usability. This now RESOLVES
# each model the way the worker does -- hf_hub_download of the actual config, local files only --
# so a partial cache fails here, in seconds, instead of after a 2.5 h allocation.
singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c "
  export HF_HOME=${MODELS} HF_HUB_CACHE=${MODELS}/hub HF_HUB_OFFLINE=1
  python - <<'PREFLIGHT'
import sys
sys.path.insert(0, '${CODE}/stable-audio-3')
from stable_audio_3.model_configs import all_models
need = ['medium-base'] + (['medium'] if '--pt-medium' in open('${TASKLIST}').read() else [])
for name in need:
    cfg = all_models[name]
    try:
        cfg.resolve()
    except Exception as e:
        print(f'[lenvar] FATAL: {name} ({cfg.repo_id}) does not resolve from the offline cache: '
              f'{type(e).__name__}: {e}', file=sys.stderr)
        sys.exit(1)
    print(f'[lenvar] preflight OK: {name} resolves offline')
PREFLIGHT
" || { echo "[lenvar] FATAL: model preflight failed -- fix the cache before burning an allocation" 1>&2; exit 1; }

# ── HyperQueue binary: prefer the CSC module, honour an HQ_BIN override, else fail loud ──────
if [ -n "${HQ_BIN:-}" ]; then
  echo "[lenvar] using HQ_BIN override: ${HQ_BIN}"
else
  module use /appl/local/csc/modulefiles || true
  module load hyperqueue || true
  HQ_BIN=$(command -v hq || true)
fi
if [ -z "${HQ_BIN:-}" ]; then
  echo "[lenvar] FATAL: no hq binary (module load hyperqueue failed and HQ_BIN unset)." 1>&2
  echo "[lenvar] drop a static hq at ${CODE}/lumi/bin/hq and re-run with HQ_BIN=that path." 1>&2
  exit 1
fi
echo "[lenvar] hq: ${HQ_BIN} ($(${HQ_BIN} --version 2>/dev/null || echo version-unknown))"

# ── task list must be present (generated locally + committed; NOT generated on LUMI, since the
#    LUMI<->local ckpt mapping + manifest-sourced prompts are derived on the local side) ─────
if [ ! -s "${TASKLIST}" ]; then
  echo "[lenvar] FATAL: ${TASKLIST} absent/empty -- run lumi/gen_length_variant_tasks.py locally and sync it." 1>&2
  exit 1
fi
NTASKS=$(grep -cve '^[[:space:]]*$' "${TASKLIST}")
echo "[lenvar] ${NTASKS} render tasks in ${TASKLIST}"

# sanity: the prompt snapshots + worker must be present in the code tree
for f in "${CODE}/lumi/render_matrix_cells.py" "${CODE}/lumi/matrix_prompts_lenvar9.json" \
         "${CODE}/lumi/matrix_prompts_lenvar_goa.json"; do
  [ -s "$f" ] || { echo "[lenvar] FATAL: missing ${f}" 1>&2; exit 1; }
done

# ── HyperQueue server ───────────────────────────────────────────────────────────────────────
export HQ_SERVER_DIR="${RENDER_OUT}/hq-server/${SLURM_JOB_ID}"
mkdir -p "${HQ_SERVER_DIR}"
"${HQ_BIN}" server start &
until "${HQ_BIN}" job list &> /dev/null; do sleep 1; done
echo "[lenvar] hq server up (HQ_SERVER_DIR=${HQ_SERVER_DIR})"

# ── 8 workers, one per GCD. ROCR_VISIBLE_DEVICES=$SLURM_PROCID ALONE (see header) ───────────
srun --overlap --cpu-bind=none --mpi=none bash -c '
  export ROCR_VISIBLE_DEVICES=$SLURM_PROCID
  '"${HQ_BIN}"' worker start --manager slurm --on-server-lost finish-running --cpus=7
' &
"${HQ_BIN}" worker wait "${SLURM_NTASKS}"
echo "[lenvar] ${SLURM_NTASKS} workers registered"

# ── submit all render tasks. One HQ task per line; each sets its own MIOpen DB under /tmp ────
# Double-quoted body so fixed paths interpolate now; \$HQ_TASK_ID stays literal for HQ. Task
# lines are apostrophe/backtick-free (generator emits plain flags), so injecting one is quote-safe.
i=0
while IFS= read -r CMD; do
  case "${CMD}" in ""|\#*) continue ;; esac
  i=$((i+1))
  "${HQ_BIN}" submit \
    --name="lenvar_${i}" \
    --cpus=7 \
    --stdout="${LOGDIR}/j%{JOB_ID}-t%{TASK_ID}.out" \
    --stderr="${LOGDIR}/j%{JOB_ID}-t%{TASK_ID}.err" \
    -- singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c "
      set -euo pipefail
      source ${VENV}/bin/activate
      export HF_HOME=${MODELS} HF_HUB_OFFLINE=1
      # venv site-packages FIRST so our pins beat the image's /opt/venv (lr_equiv_grid_mt pattern)
      export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor\${PYTHONPATH:+:\$PYTHONPATH}
      # multitorch env per the proven lr_equiv_grid_mt block: NO MIOPEN_FIND_MODE=2 (the
      # sa3.sif/gfx90a find-fallback hang), NO MIOPEN_DISABLE_CACHE; per-task caches only.
      export PYTORCH_TUNABLEOP_ENABLED=0
      export MIOPEN_USER_DB_PATH=/tmp/miopen-\$HQ_TASK_ID MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-\$HQ_TASK_ID
      export TRITON_CACHE_DIR=/tmp/triton-\$HQ_TASK_ID
      export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
      rm -rf \$MIOPEN_USER_DB_PATH \$TRITON_CACHE_DIR; mkdir -p \$MIOPEN_USER_DB_PATH \$TRITON_CACHE_DIR
      cd ${CODE}/stable-audio-3
      echo [lenvar task \$HQ_TASK_ID] GCD ROCR=\$ROCR_VISIBLE_DEVICES
      ${CMD}
    "
done < "${TASKLIST}"
echo "[lenvar] submitted ${i} tasks; draining across ${SLURM_NTASKS} GCDs"

# ── wait for the queue to drain, then tear down ─────────────────────────────────────────────
"${HQ_BIN}" job wait all || true   # task failures must not kill the tail under set -e
echo "[lenvar] all jobs finished:"
"${HQ_BIN}" job list --all || true
"${HQ_BIN}" worker stop all || true
"${HQ_BIN}" server stop || true

# ── verify by ARTIFACT count, not rc (guide rule) ───────────────────────────────────────────
NW=$(find "${RENDER_OUT}" -maxdepth 1 -name '*.wav' 2>/dev/null | wc -l)
NM=$(find "${RENDER_OUT}" -maxdepth 1 -name '*.mmline.json' 2>/dev/null | wc -l)
echo "[lenvar] DONE. artifacts under ${RENDER_OUT}: ${NW} wav / ${NM} mmline.json ; logs ${LOGDIR}/"
# Assert against the TASK LIST, not against whatever happens to be on disk: a job that renders
# 80% of its cells exits COMPLETED and its own summary line looks identical to a finished run.
singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c \
  "python ${CODE}/lumi/check_render_complete.py --tasks ${TASKLIST} --out ${RENDER_OUT} --code ${CODE}"
CHECK_RC=$?
echo "[lenvar] NEXT (local): eval/ingest_native_cells.py to pull + transcode + append manifest, then rebuild the boards."
[ "$CHECK_RC" -eq 0 ] || { echo "[lenvar] INCOMPLETE -- see the per-label shortfall above; do NOT treat this run as done" 1>&2; exit 1; }
