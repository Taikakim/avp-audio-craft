#!/bin/bash
# stack_cells.sbatch — Kim direct 2026-08-21: "create a few sets of adapter cell runs by using
# the good DoRAs on our good full finetunes!" — every ADAPTER from W's known-good list
# (genre_fusion_checkpoints.txt, fullft rows excluded, _ptm suffix stripped: the underlying
# adapter is the same file) stacked on each of THREE good full-FT backbones:
#   avpft90   = fullft_avp_t256 ep90        (W list)
#   avpft153  = fullft_avp_t256 ep153       (W list)
#   avpaug19  = fullft_avpaug_t1024_fp32_lr1e-4_s1 ep19 EMA (the vetted B9 backbone)
# Cells: standard 20s matrix grid (matrix_prompts_snapshot.json prompts/seeds), cfg7,
# strengths 0.5/1.0/1.5 — the strength axis is the experiment: how much adapter a shifted
# base tolerates. Labels: <adapter>_ep<N>_on_<ft-short> so the board keeps stacked cells
# distinct from base-adapter cells. Idempotent per cell (re-run fills gaps).
# RUN: sbatch lumi/sbatch/stack_cells.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=06:00:00
#SBATCH --job-name=stack_cells
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif

ROUT=${SCRATCH}/renders/stack_cells
UNITS=${ROUT}/stack_units.txt
mkdir -p ${ROUT}

# resolve adapters (non-fullft rows of W's list) + the three backbones ONCE, pre-split.
singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" python3 - <<'PYEOF' > ${UNITS}.tmp || { echo "[stack] FATAL: unit build failed"; cat ${UNITS}.tmp; exit 1; }
import sys, re
sys.path.insert(0, "/project/project_465003186/code/lumi")
from genre_fusion_shards import resolve_ckpt
RUNS = "/scratch/project_465003186/runs"
fts = []
for short, label, ep in (("avpft90", "fullft_avp_t256", "90"), ("avpft153", "fullft_avp_t256", "153")):
    p, _ = resolve_ckpt(RUNS, label, ep)
    assert p, f"backbone unresolved: {label} ep{ep}"
    fts.append((short, p))
AUG19 = RUNS + "/fullft_fleet/fullft_avpaug_t1024_fp32_lr1e-4_s1/epoch=19-step=5980-v1.ckpt"
import os
assert os.path.exists(AUG19), f"backbone missing: {AUG19}"
fts.append(("avpaug19", AUG19))
seen, adapters = set(), []
for line in open("/project/project_465003186/code/lumi/genre_fusion_checkpoints.txt"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    parts = line.split()
    label, ep = parts[0], parts[1]
    if label.startswith("fullft_"):
        continue
    base_label = re.sub(r"_ptm$", "", label)
    if (base_label, ep) in seen:
        continue
    seen.add((base_label, ep))
    p, _ = resolve_ckpt(RUNS, label, ep)
    assert p, f"adapter unresolved: {label} ep{ep}"
    adapters.append((base_label, ep, p))
for ad_label, ad_ep, ad_path in adapters:
    for ft_short, ft_path in fts:
        print(f"{ad_label}_ep{ad_ep}_on_{ft_short}|ep{ad_ep}|{ad_path}|{ft_path}")
print(f"[stack] {len(adapters)} adapters x {len(fts)} backbones = {len(adapters)*len(fts)} combos",
      file=sys.stderr)
PYEOF
mv ${UNITS}.tmp ${UNITS}
NU=$(wc -l < "${UNITS}")
echo "[stack] ${NU} (adapter,backbone) combos pre-split across 8 ranks"
[ "${NU}" -gt 0 ] || { echo "[stack] FATAL: no combos"; exit 1; }

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
R=${SLURM_PROCID}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
echo "[r${R}] alive $(hostname) $(date -Is)"
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export TRITON_CACHE_DIR=/tmp/triton-${R}
rm -rf /tmp/miopen-${R} /tmp/triton-${R}; mkdir -p /tmp/miopen-${R} /tmp/triton-${R}
UNITS=${SCRATCH}/renders/stack_cells/stack_units.txt
ROUT=${SCRATCH}/renders/stack_cells
SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
N=0
while IFS="|" read -r LABEL TAG ADCK FTCK; do
  N=$((N+1))
  [ $(( (N-1) % 8 )) -eq ${R} ] || continue
  echo "[r${R}] UNIT ${LABEL} (adapter $(basename ${ADCK}) on $(basename ${FTCK}))"
  python ${CODE}/lumi/render_matrix_cells.py --label ${LABEL} --tag ${TAG} \
    --ckpt "${ADCK}" --base-state-ckpt "${FTCK}" --prompts ${SNAP} --out ${ROUT} \
    --only-cfgs 7 --strengths 0.5,1.0,1.5 \
    || echo "[r${R}] ${LABEL} FAILED (continuing)"
done < "${UNITS}"
echo "[r${R}] done"
'
echo "[stack] cells now: $(ls ${ROUT}/*__cfg7__*.wav 2>/dev/null | wc -l)"
