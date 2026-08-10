#!/bin/bash
# fullft_wd_ab.sbatch — WEIGHT-DECAY A/B for the full-FT latent-scale runaway (CONTINUITY 2026-08-10).
#
# WHY: every LUMI full fine-tune (#68 fullft_bigset, precision_ladder — all FusionOpt) decoded to
# spectral drone. Measured cause (from the sampled latents): the model's output scale RUNS AWAY during
# training — global latent std 0.7(good) -> 1.3(ep3) -> 5.6(ep7); #channels with std>2.0: 0 -> 4 -> 166
# of 256. Root cause: FusionOpt's weight_decay DEFAULTS TO 0.0 (fusion_opt.py:196) and the full-FT path
# never set it, so nothing bounds NS5/Muon's grad-magnitude-independent update-norm growth. Confirmed at
# the optimiser level, deterministically, in stable-audio-tools/tests/test_fusion_weight_decay.py (wd=0
# runs away, wd=0.1 bounds; AdamW's 0.01 is too weak for FusionOpt).
#
# THIS JOB confirms the fix on the REAL model and answers the two open questions at once:
#   arm0  wd0          : fusion, weight_decay 0.0            -> REPRODUCE the runaway (current condition)
#   arm1  wd0p1        : fusion, weight_decay 0.1 + clip 1.0 -> THE FIX (bounded?)
#   arm2  adamw_wd0p1  : AdamW,  weight_decay 0.1            -> optimiser control: is it fusion-specific,
#                                                              or does an AdamW FULL-FT also need it?
#                                                              (breaks the adapter-vs-fullft confound —
#                                                               all our prior AdamW runs were adapters)
# Identical otherwise: pre-encoded latents_sa3, fp32, T256, lr 8e-5, bs4, EMA, 6ep, ckpt every 2 — i.e.
# the precision_ladder harness (single-GPU per arm, which ALSO droned), varying ONLY the regularisation.
# The tail renders the cfg16 canary per checkpoint and prints the latent-std table (reproduces the local
# analysis on the real model): wd0 should climb, wd0p1/adamw should stay ~1.0.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=3
#SBATCH --ntasks-per-node=3
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=08:00:00
#SBATCH --job-name=sa3_fullft_wd_ab
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
# STEM-keyed sidecar matching the numeric latents_sa3 filenames (same as precision_ladder). Caption
# regime is irrelevant to a regularisation ISOLATE (identical across all 3 arms).
SIDECAR=${SIDECAR:-${CODE}/lumi/goa_longform_sidecar.json}
PROBS=${PROBS:-0.3,0.4,0.3}
SNAP=${SNAP:-${CODE}/lumi/matrix_prompts_snapshot.json}
FRAMES=${FRAMES:-256}; EPOCHS=${EPOCHS:-6}; LR=${LR:-8e-5}; BS=${BS:-4}; SEED=${SEED:-1}; CKEVERY=${CKEVERY:-2}
ROUT=${SCRATCH}/renders/matrix_cells

[ -n "${SIF}" ] || { echo "[wd-ab] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[wd-ab] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[wd-ab] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }

# stage pre-encoded latents to FLASH once (same as the ladder)
if [ ! -d "${FLASH}/latents_sa3" ]; then
  mkdir -p "${FLASH}/latents_sa3"
  tar -xzf "${SCRATCH}/latents_sa3.tar.gz" -C "${FLASH}/latents_sa3" --strip-components=1
fi

# arm spec: "LABEL  OPTIMIZER  WEIGHT_DECAY  EXTRA_FLAGS"
# --weight_decay routes to spectral_wd (the 2D DiT matrices) for fusion; to the single AdamW group
# for adamw. wd0p01 REPRODUCES #68's ACTUAL condition (builder default spectral_wd=0.01 — too weak
# for NS5/Muon), NOT wd=0; wd0p1 is the fix; adamw arm is the optimiser control (breaks the
# adapter-vs-fullft confound — a real AdamW FULL-FT).
ARM_SPECS=(
  "wd0p01       fusion  0.01  "
  "wd0p1        fusion  0.1   --gradient_clip_val 1.0"
  "adamw_wd0p1  adamw   0.1   "
)

run_arm () {
  local GCD=$1 LABEL=$2 OPT=$3 WD=$4; shift 4; local EXTRA="$*"
  local NAME=fullft_wd_ab_${LABEL}
  local RUN=${SCRATCH}/runs/fullft_wd_ab/${NAME}
  mkdir -p "${RUN}"
  ROCR_VISIBLE_DEVICES=${GCD} srun --exclusive -N1 -n1 --gpus=1 --cpus-per-task=7 \
    singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186; CODE=${PROJ}/code
source '"${VENV}"'/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-'"${GCD}"' MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-'"${GCD}"'
export TRITON_CACHE_DIR=/tmp/triton-'"${GCD}"' PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-'"${GCD}"' /tmp/triton-'"${GCD}"'; mkdir -p /tmp/miopen-'"${GCD}"' /tmp/triton-'"${GCD}"'
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
# single-process Lightning (avoid the shared SLURM DDP rendezvous port — 3 arms would collide)
export SLURM_JOB_NAME=bash MASTER_ADDR=127.0.0.1 MASTER_PORT=$((29500 + '"${GCD}"'))
python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base --full-finetune \
    --encoded_dir ${FLASH}/latents_sa3 \
    --caption_sidecar "'"${SIDECAR}"'" --caption_probs "'"${PROBS}"'" \
    --save_dir "'"${RUN}"'" \
    --optimizer '"${OPT}"' --weight_decay '"${WD}"' '"${EXTRA}"' \
    --use-ema --ema-beta 0.9999 \
    --base_precision fp32 \
    --lr '"${LR}"' --batch_size '"${BS}"' \
    --frames '"${FRAMES}"' --beat-aware-crop \
    --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
    --num_workers 6 --seed '"${SEED}"' --no_demos --logger csv \
    --name '"${NAME}"' 2>&1 | tee -a "'"${RUN}"'"/train.log
' &
}

echo "[wd-ab] image=${SIF}  T=${FRAMES} ep=${EPOCHS} lr=${LR} bs=${BS} seed=${SEED} ckevery=${CKEVERY}"
gcd=0
for spec in "${ARM_SPECS[@]}"; do run_arm ${gcd} ${spec}; gcd=$((gcd + 1)); done
wait
echo "[wd-ab] all arms trained. Checkpoints:"
ls -1 ${SCRATCH}/runs/fullft_wd_ab/*/epoch=*.ckpt 2>/dev/null | grep -v '\.weights\.ckpt$' || true

# ── PROBE: render the cfg16 canary for every checkpoint (saves z0.npy), then print the latent-std
#    table. cfg16 is the early-warning axis (surfaced #68's drift an epoch before cfg1/7). ──
echo "[wd-ab] rendering cfg16 canary cells per checkpoint..."
for RUN in ${SCRATCH}/runs/fullft_wd_ab/*/; do
  LABEL=$(basename "${RUN}")
  for CK in $(ls "${RUN}"epoch=*.ckpt 2>/dev/null | grep -v '\.weights\.ckpt$' | sort -V); do
    EP=$(basename "${CK}" | grep -oE 'epoch=[0-9]+' | grep -oE '[0-9]+')
    ROCR_VISIBLE_DEVICES=0 srun --exclusive -N1 -n1 --gpus=1 --cpus-per-task=7 \
      singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
source '"${VENV}"'/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0
export PYTHONPATH='"${CODE}"'/stable-audio-3:'"${CODE}"'/control:'"${CODE}"'/lumi/vendor
python '"${CODE}"'/lumi/render_matrix_cells.py --label '"${LABEL}"' --tag ep'"${EP}"' \
    --ckpt "'"${CK}"'" --fullft --use-ema --prompts '"${SNAP}"' --out '"${ROUT}"' \
    --only-cfgs 16 --strengths 1.0 || echo "[wd-ab] render '"${LABEL}"' ep'"${EP}"' FAILED (non-fatal)"
' || true
  done
done

echo "[wd-ab] ===== LATENT-STD TABLE (the verdict) ====="
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
print(f"{'arm':14s} {'ep':>3s}  {'global_std':>10s}  {'#chan>2.0':>10s}  (good~1.0 / 0; runaway climbs)")
for k in sorted(rows):
    v=rows[k]; gs=np.mean([a for a,_ in v]); nh=np.mean([b for _,b in v])
    print(f"{k[0]:14s} {k[1]:>3d}  {gs:>10.3f}  {nh:>10.1f}")
print("VERDICT: wd0p01 (== #68 condition) climbs with ep; wd0p1 + adamw_wd0p1 stay ~1.0 =>")
print("         spectral_wd 0.01 is too weak for NS5/Muon; 0.1 is the fix; and (adamw bounded")
print("         too) it is the DECAY STRENGTH, not full-FT itself.")
PYEOF
'
echo "[wd-ab] DONE. Pull cells (fullft_wd_ab_*) if auditioning; the std table above is the headline."
