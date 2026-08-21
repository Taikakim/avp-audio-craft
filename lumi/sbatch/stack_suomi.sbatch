#!/bin/bash
# stack_suomi.sbatch — Kim direct 2026-08-21: "I want the suomisoundi DoRAs rendered vs avp and
# goa full fts — the sound is so idiosyncratic that I'm not sure if we can even reproduce it."
# The suomi-idiosyncrasy transfer test: every clean torchrun-era suomi adapter stacked on
# avp/goa full-FT backbones, rendered on the SUOMI prompt set (suomi_full_prompts.json — 23
# prompts incl. anchor/modal/random), cfg7, strengths 0.5/1.0/1.5.
#
# Adapters (last + mid ckpt each; wfleet suomi EXCLUDED — its dirs mix Pattern-2 replica
# ladders with torchrun restarts, a mixed-era pick would mislead):
#   runs/dorlor_ab/dorlor_suomi_dora_adamw_*  (A11)
#   runs/dorlor_ab/dorlor_suomi_dora_fusion_* (A11)
#   runs/subloss_k24/subloss_k24_suomi_*      (B10)
# Backbones: fullft_avp_t256 ep153 (W list) + fullft_avpaug ep19 EMA (B9 backbone) + the goa
# full-FT at its MID checkpoint (goa fullfts degrade with training — G/W 2026-08-21, spearman
# epoch->PQ -0.434 — so "last" would strap the adapter to a near-worst base).
# RUN: sbatch lumi/sbatch/stack_suomi.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=04:00:00
#SBATCH --job-name=stack_suomi
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif

ROUT=${SCRATCH}/renders/stack_suomi
UNITS=${ROUT}/stack_units.txt
mkdir -p ${ROUT}

singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" python3 - <<'PYEOF' > ${UNITS}.tmp || { echo "[sstack] FATAL: unit build failed"; cat ${UNITS}.tmp; exit 1; }
import glob, os, re, sys
sys.path.insert(0, "/project/project_465003186/code/lumi")
from genre_fusion_shards import resolve_ckpt
RUNS = "/scratch/project_465003186/runs"

def fats(d):  # sorted fat ckpts of a run dir
    cks = [c for c in glob.glob(os.path.join(d, "epoch=*.ckpt")) if not c.endswith(".weights.ckpt")]
    return sorted(cks, key=lambda c: int(re.search(r"epoch=(\d+)", c).group(1)))

def last_and_mid(d):
    cks = fats(d)
    assert cks, f"no ckpts under {d}"
    picks = [cks[-1]]
    if len(cks) > 2 and cks[len(cks)//2] != cks[-1]:
        picks.append(cks[len(cks)//2])
    return picks

adapters = []  # (short_label, tag, path)
patterns = [RUNS + "/dorlor_ab/dorlor_suomi_dora_adamw_*",
            RUNS + "/dorlor_ab/dorlor_suomi_dora_fusion_*",
            RUNS + "/subloss_k24/*suomi*"]
for pat in patterns:
    dirs = sorted(d for d in glob.glob(pat) if os.path.isdir(d))
    if not dirs:
        print(f"[sstack] WARNING: no run dir for {pat}", file=sys.stderr)
    for d in dirs:
        name = os.path.basename(d)
        short = re.sub(r"_r128a128_t256_bf16_bs\d+(_s\d+)$", r"\1", name)
        short = re.sub(r"_t512_bf16(_s\d+)$", r"\1", short)
        for ck in last_and_mid(d):
            ep = re.search(r"epoch=(\d+)", ck).group(1)
            adapters.append((short, f"ep{ep}", ck))
assert adapters, "no suomi adapters found at all"

fts = []
p, _ = resolve_ckpt(RUNS, "fullft_avp_t256", "153")
assert p, "backbone unresolved: fullft_avp_t256 ep153"
fts.append(("avpft153", p))
AUG19 = RUNS + "/fullft_fleet/fullft_avpaug_t1024_fp32_lr1e-4_s1/epoch=19-step=5980-v1.ckpt"
assert os.path.exists(AUG19), f"backbone missing: {AUG19}"
fts.append(("avpaug19", AUG19))
goa_dirs = sorted(glob.glob(RUNS + "/*/fullft_goa_t4096") + glob.glob(RUNS + "/fullft_goa_t4096"))
assert goa_dirs, "no fullft_goa_t4096 run dir found"
gcks = fats(goa_dirs[0])
assert gcks, f"no ckpts under {goa_dirs[0]}"
gmid = gcks[len(gcks)//2]
gep = re.search(r"epoch=(\d+)", gmid).group(1)
fts.append((f"goaft{gep}", gmid))

for ad_short, ad_tag, ad_path in adapters:
    for ft_short, ft_path in fts:
        print(f"{ad_short}_{ad_tag}_on_{ft_short}|{ad_tag}|{ad_path}|{ft_path}")
print(f"[sstack] {len(adapters)} suomi adapters x {len(fts)} backbones = "
      f"{len(adapters)*len(fts)} combos; goa backbone = {gmid}", file=sys.stderr)
PYEOF
mv ${UNITS}.tmp ${UNITS}
NU=$(wc -l < "${UNITS}")
echo "[sstack] ${NU} (adapter,backbone) combos pre-split across 8 ranks"
[ "${NU}" -gt 0 ] || { echo "[sstack] FATAL: no combos"; exit 1; }

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
UNITS=${SCRATCH}/renders/stack_suomi/stack_units.txt
ROUT=${SCRATCH}/renders/stack_suomi
SUOMIP=${CODE}/lumi/suomi_full_prompts.json
N=0
while IFS="|" read -r LABEL TAG ADCK FTCK; do
  N=$((N+1))
  [ $(( (N-1) % 8 )) -eq ${R} ] || continue
  echo "[r${R}] UNIT ${LABEL} (adapter $(basename ${ADCK}) on $(basename ${FTCK}))"
  python ${CODE}/lumi/render_matrix_cells.py --label ${LABEL} --tag ${TAG} \
    --ckpt "${ADCK}" --base-state-ckpt "${FTCK}" --prompts ${SUOMIP} --out ${ROUT} \
    --only-cfgs 7 --strengths 0.5,1.0,1.5 \
    || echo "[r${R}] ${LABEL} FAILED (continuing)"
done < "${UNITS}"
echo "[r${R}] done"
'
echo "[sstack] cells now: $(ls ${ROUT}/*__cfg7__*.wav 2>/dev/null | wc -l)"
