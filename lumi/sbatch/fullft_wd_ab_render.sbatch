#!/bin/bash
# fullft_wd_ab_render.sbatch — RECOVER the wd A/B (20940322) verdict (CONTINUITY 2026-08-11).
# 20940322 FAILED (one arm crashed -> set -e aborted `wait` before the render tail, and the tail's
# table heredoc had the escaped-quote SyntaxError anyway). But TRAINING SUCCEEDED for the surviving
# arms — ckpts sit in runs/fullft_wd_ab/*/epoch=*.ckpt (wd0 + adamw_wd0p1, ep1/3/5). This job renders
# the cfg16 canary over whatever ckpts exist + prints the (FIXED) latent-std table. No training.
# Strategically: adamw_wd0p1 bounded = first real "well-tuned AdamW full-FT stays stable" data point
# (the arXiv 2509.02046 pivot). Pull the z0 after (renders/matrix_cells/fullft_wd_ab_*__cfg16__*.z0.npy)
# if you want C to recompute locally.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=00:40:00
#SBATCH --job-name=sa3_wd_ab_render
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
SNAP=${SNAP:-${CODE}/lumi/matrix_prompts_snapshot.json}
ROUT=${SCRATCH}/renders/matrix_cells

[ -n "${SIF}" ] || { echo "[wd-render] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[wd-render] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[wd-render] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }
CKN=$(ls ${SCRATCH}/runs/fullft_wd_ab/*/epoch=*.ckpt 2>/dev/null | grep -v '\.weights\.ckpt$' | wc -l)
[ "${CKN}" -gt 0 ] || { echo "[wd-render] FATAL: no ckpts in runs/fullft_wd_ab/*/"; exit 1; }
echo "[wd-render] ${CKN} ckpt(s) to render (cfg16 canary):"
ls -1 ${SCRATCH}/runs/fullft_wd_ab/*/epoch=*.ckpt 2>/dev/null | grep -v '\.weights\.ckpt$'

# ── render cfg16 per surviving checkpoint (saves z0.npy) ──
for RUN in ${SCRATCH}/runs/fullft_wd_ab/*/; do
  LABEL=$(basename "${RUN}")
  for CK in $(ls "${RUN}"epoch=*.ckpt 2>/dev/null | grep -v '\.weights\.ckpt$' | sort -V); do
    EP=$(basename "${CK}" | grep -oE 'epoch=[0-9]+' | grep -oE '[0-9]+')
    ROCR_VISIBLE_DEVICES=0 srun --exclusive -N1 -n1 --gpus=1 --cpus-per-task=7 \
      singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
source '"${VENV}"'/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0
export MIOPEN_USER_DB_PATH=/tmp/miopen-r MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-r TRITON_CACHE_DIR=/tmp/triton-r
rm -rf /tmp/miopen-r /tmp/triton-r; mkdir -p /tmp/miopen-r /tmp/triton-r
export PYTHONPATH='"${CODE}"'/stable-audio-3:'"${CODE}"'/control:'"${CODE}"'/lumi/vendor
python '"${CODE}"'/lumi/render_matrix_cells.py --label '"${LABEL}"' --tag ep'"${EP}"' \
    --ckpt "'"${CK}"'" --fullft --use-ema --prompts '"${SNAP}"' --out '"${ROUT}"' \
    --only-cfgs 16 --strengths 1.0 || echo "[wd-render] render '"${LABEL}"' ep'"${EP}"' FAILED (non-fatal)"
' || true
  done
done

echo "[wd-render] ===== LATENT-STD TABLE (the recovered verdict) ====="
singularity exec --bind ${PROJ},${SCRATCH},${FLASH} "${SIF}" bash -c '
source '"${VENV}"'/bin/activate
python - <<PYEOF
import numpy as np, glob, re, os
from collections import defaultdict
rows=defaultdict(list)
for f in sorted(glob.glob("'"${ROUT}"'/fullft_wd_ab_*__ep*__cfg16__*.z0.npy")):
    b=os.path.basename(f)
    m=re.search(r"fullft_wd_ab_(.+?)__ep(\d+)__",b)
    if not m: continue
    z=np.load(f).astype(np.float64)
    if z.ndim==3: z=z[0]
    if z.shape[0]!=256 and z.shape[-1]==256: z=z.T
    pc=z.std(axis=1)
    rows[(m.group(1),int(m.group(2)))].append((z.std(), int((pc>2.0).sum())))
print(f"{'arm':16s} {'ep':>3s}  {'global_std':>10s}  {'#chan>2.0':>10s}  (good~1.0 / 0; runaway climbs)")
for k in sorted(rows):
    v=rows[k]; gs=np.mean([a for a,_ in v]); nh=np.mean([b for _,b in v])
    print(f"{k[0]:16s} {k[1]:>3d}  {gs:>10.3f}  {nh:>10.1f}")
print("READ: wd0 (no decay) should CLIMB with ep = runaway confirmed; adamw_wd0p1 should stay ~1.0")
print("      = a well-tuned AdamW full-FT bounds it (the arXiv 2509.02046 pivot). NOTE: the fusion-wd0.1")
print("      fix arm did NOT survive the crash, so this is a PARTIAL verdict (runaway + AdamW only).")
PYEOF
'
echo "[wd-render] done. Pull: rsync ...renders/matrix_cells/fullft_wd_ab_*__cfg16__*.z0.npy -> local; C recomputes."
