#!/bin/bash
# fullft_reg_ab.sbatch — REGULARIZATION A/B for the full-FT latent-scale runaway (CONTINUITY 2026-08-10).
# Spec: docs/superpowers/specs/2026-08-10-fullft-regularization-ab.md
#
# WHY: the first A/B (fullft_wd_ab.sbatch) showed plain weight_decay 0.1 BOUNDS the FusionOpt full-FT
# latent-scale runaway (global std 0.7->5.6 ep3->ep7; #chan>2.0 0->166/256). But wd is BLUNT — it shrinks
# every weight direction, incl. the subtle feature-bearing ones we're trying to strengthen. This job tests
# whether GENTLER / MORE TARGETED regularizers bound the runaway with less collateral on fine detail:
#   - AGC (Adaptive Gradient Clipping, NFNets): scale-relative per-output-unit grad clip — reins in only
#     large-grad-relative-to-scale units (--grad-clip-mode agc --agc-lambda 0.01).
#   - output-std penalty: penalize z0_hat's per-channel std drifting off the data's, in the LOSS not the
#     weights, gated to low noise (--output-std-penalty LOUT --output-std-t-gate 0.5). Logs both stds to
#     the CSV each step so the runaway is readable WITHOUT a render.
#
# 8 arms = {limiter} x {output-reg} at wd 0.01, + wd/wd-full references (1 arm per GCD, single-GPU each —
# the precision_ladder / fullft_wd_ab pattern, which itself droned, so the reg comparison is faithful).
# Reproduces the failing setup: full-FT, big goa set via LIVE-ENCODE (--data_dir + sidecar, like
# fullft_bigset), bf16-mixed (Kim: speed; a precision confound vs the fp32 #68, but the reg comparison is
# INTERNAL so it holds), T512, bs4, 10ep, FusionOpt(all-on)+EMA. Tail renders the cfg16 canary per
# checkpoint + prints the latent-std table (same probe as wd_ab): anchor should climb (positive control);
# a winner tracks ~1.0 with 0 non-finite AND retains detail >= the `wd` baseline (Kim's ears + DSP proxy).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=sa3_fullft_reg_ab
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

# ── Corpus: big goa set via LIVE-ENCODE (--data_dir -> in-loop SAME encode), mirroring fullft_bigset.
#    RELPATH-keyed T1/T2/T3 sidecar (caption regime is IDENTICAL across all 8 arms -> irrelevant to a
#    regularization ISOLATE, but must resolve or every clip __reject__'s -> empty dataset). ──
BIGSET_DIR=${BIGSET_DIR:-${SCRATCH}/goa_archive}
BIGSET_SIDECAR=${BIGSET_SIDECAR:-${SCRATCH}/goa_caption_sidecar.json}
PROBS=${PROBS:-0.3,0.4,0.3}
SNAP=${SNAP:-${CODE}/lumi/matrix_prompts_snapshot.json}

# Reg knobs + training config (T512 / bs4 / 10ep / ckpt every 2 / bf16-mixed per spec).
LOUT=${LOUT:-0.1}; TGATE=${TGATE:-0.5}; AGCLAM=${AGCLAM:-0.01}; CLIPVAL=${CLIPVAL:-1.0}
FRAMES=${FRAMES:-512}; EPOCHS=${EPOCHS:-10}; CKEVERY=${CKEVERY:-2}
LR=${LR:-8e-5}; BS=${BS:-4}; SEED=${SEED:-1}; PREC=${PREC:-bf16-mixed}
ROUT=${SCRATCH}/renders/matrix_cells

# ── WANDB (G, 2026-08-10, delegation part 5): compute nodes have no internet, so every arm runs
#    WANDB_MODE=offline -- writes local run files under its own $SCRATCH run dir (persists with
#    the checkpoints, never on $FLASH), zero network calls, zero credential needed on LUMI at all
#    (offline mode doesn't auth -- keeps a WANDB_API_KEY off every shared-visible LUMI process,
#    per the CLI-args/env-are-visible-to-other-users note in the lumi-ops SKILL). Sync is a
#    SEPARATE, later step run wherever we DO have network + our wandb login (see the SKILL's
#    "wandb offline -> sync" section) -- `wandb sync <pulled_run_dir>/wandb/offline-run-*` per
#    arm, once Kim's rsync lands the run dirs home. LOGGER stays overridable (this script's own
#    ${VAR:-default} convention) so a future reuse can still fall back to --logger csv.
LOGGER=${LOGGER:-wandb}

# ── SPEED KNOBS (spec: 10ep x 23k live-encode ~ 6-12h/arm). STEPS caps optimizer steps (drops --epochs;
#    train_lora ignores --steps when --epochs is set, so STEPS mode passes ONLY --steps). SUBSET caps the
#    corpus to the first N files via a symlink tree that PRESERVES the relpath layout, so the
#    relpath-keyed sidecar still matches (data_dir must stay relpath-consistent or captions drop). ──
if [ -n "${STEPS:-}" ]; then
  LENARG="--steps ${STEPS} --checkpoint_every ${CKSTEPS:-500}"
  echo "[reg-ab] STEPS MODE: --steps ${STEPS} (checkpoint every ${CKSTEPS:-500})"
else
  LENARG="--epochs ${EPOCHS} --checkpoint_every_epochs ${CKEVERY}"
fi

DATA_DIR="${BIGSET_DIR}"
if [ -n "${SUBSET:-}" ]; then
  STAGE=${FLASH}/reg_ab_subset
  echo "[reg-ab] SUBSET MODE: first ${SUBSET} files -> ${STAGE} (relpath-preserving symlink tree)"
  rm -rf "${STAGE}"; mkdir -p "${STAGE}"
  head -n "${SUBSET}" "${BIGSET_DIR}/filelist.txt" > "${STAGE}/filelist.txt"
  while IFS= read -r rel; do
    [ -n "${rel}" ] || continue
    mkdir -p "${STAGE}/$(dirname "${rel}")"
    ln -sf "${BIGSET_DIR}/${rel}" "${STAGE}/${rel}"
  done < "${STAGE}/filelist.txt"
  DATA_DIR="${STAGE}"
fi

[ -n "${SIF}" ] || { echo "[reg-ab] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[reg-ab] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[reg-ab] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }
[ -d "${DATA_DIR}" ] || { echo "[reg-ab] FATAL: data dir ${DATA_DIR} missing"; exit 1; }
[ -f "${DATA_DIR}/filelist.txt" ] || { echo "[reg-ab] FATAL: ${DATA_DIR}/filelist.txt missing (curated audio list)"; exit 1; }
[ -f "${BIGSET_SIDECAR}" ] || { echo "[reg-ab] FATAL: caption sidecar ${BIGSET_SIDECAR} missing"; exit 1; }
grep -q -- "--augment" "${CODE}/stable-audio-3/scripts/train_lora.py" || { echo "[reg-ab] FATAL: train_lora missing --augment (code refresh)"; exit 1; }
grep -q -- "--grad-clip-mode" "${CODE}/stable-audio-3/scripts/train_lora.py" || { echo "[reg-ab] FATAL: train_lora missing --grad-clip-mode / --output-std-penalty (code refresh)"; exit 1; }

# ── arm spec: "LABEL  OPTIMIZER  LR  WEIGHT_DECAY  EXTRA_FLAGS..." — per-arm optimizer + LR so a
#    FAIRLY-TUNED AdamW arm can sit alongside the fusion arms. For fusion, --weight_decay routes to
#    spectral_wd (the 2D DiT matrices where the runaway lives); for adamw it's the single AdamW group.
#    EXTRA carries the limiter + output-reg. (spec §Arms + Part-I fair-baseline correction 2026-08-10) ──
REG="--output-std-penalty ${LOUT} --output-std-t-gate ${TGATE}"
AGC="--grad-clip-mode agc --agc-lambda ${AGCLAM}"
CLIP="--gradient_clip_val ${CLIPVAL}"
# AdamW's optimum LR is HIGHER than Muon's (arXiv 2509.02046 "Fantastic Pretraining Optimizers": prior
# Muon>AdamW claims came from an UNDER-tuned AdamW; the real 1.4B-scale gap is ~1.1x, not 2x). So the
# adamw arm must NOT reuse fusion's ${LR}=8e-5 or it's handicapped. Default a fair 2e-4; env-override
# ADAMW_LR to run the 2-3 point LR bracket that a *proper* fair tune needs (1e-4 / 3e-4 / 6e-4).
ADAMW_LR=${ADAMW_LR:-2e-4}
ARM_SPECS=(
  "anchor      fusion  ${LR}        0.01  "
  "reg_only    fusion  ${LR}        0.01  ${REG}"
  "clip        fusion  ${LR}        0.01  ${CLIP}"
  "clip_reg    fusion  ${LR}        0.01  ${CLIP} ${REG}"
  "agc         fusion  ${LR}        0.01  ${AGC}"
  "agc_reg     fusion  ${LR}        0.01  ${AGC} ${REG}"
  "wd          fusion  ${LR}        0.1   "
  "adamw_fair  adamw   ${ADAMW_LR}  0.1   ${CLIP}"
)
# NOTE: replaced the low-information 'wd_agc_reg' (everything-on) arm with 'adamw_fair' — a fairly-tuned
# AdamW full-FT (lr ${ADAMW_LR}, wd 0.1, grad-clip, NO output-std/agc): the Part-I question "does a
# well-tuned AdamW just train stably at ~1.1x the cost, making the Muon-repair machinery moot?". ONE arm
# at ONE LR is a START, not a fair tune — resubmit with ADAMW_LR sweep for the real answer.

run_arm () {
  local GCD=$1 LABEL=$2 OPT=$3 ALR=$4 WD=$5; shift 5; local EXTRA="$*"
  local NAME=fullft_reg_ab_${LABEL}
  local RUN=${SCRATCH}/runs/fullft_reg_ab/${NAME}
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
# 20954346'"'"'s clip-arm OOM message named PYTORCH_ALLOC_CONF (no HIP_ prefix) as the fix, not
# the var above -- set both names defensively in case this torch build reads the newer unified
# one and silently ignored the ROCm-specific name (unconfirmed root cause, cheap to cover).
export PYTORCH_ALLOC_CONF=expandable_segments:True
# single-process Lightning (avoid the shared SLURM DDP rendezvous port — 8 arms would collide)
export SLURM_JOB_NAME=bash MASTER_ADDR=127.0.0.1 MASTER_PORT=$((29500 + '"${GCD}"'))
# offline wandb: no compute-node internet, no credential on LUMI -- WANDB_DIR keeps the run
# files inside this arm'"'"'s own $SCRATCH run dir so they pull home with the checkpoints.
# WANDB_PROJECT (C, 2026-08-10 patch to train_lora.py): groups all 8 arms under ONE wandb
# project (arm label becomes the per-arm run name) so they overlay on one A/B dashboard --
# without it each arm lands in its own separate project (train_lora'"'"'s prior default).
export WANDB_MODE=offline WANDB_DIR='"${RUN}"' WANDB_PROJECT=fullft_reg_ab
# live-encode: 6 workers x big decoded audio tensors -> raise the open-file limit (file_system sharing)
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true
python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base --full-finetune \
    --data_dir "'"${DATA_DIR}"'" \
    --caption_sidecar "'"${BIGSET_SIDECAR}"'" --caption_probs "'"${PROBS}"'" \
    --augment \
    --save_dir "'"${RUN}"'" \
    --optimizer '"${OPT}"' --weight_decay '"${WD}"' '"${EXTRA}"' \
    --use-ema --ema-beta 0.9999 \
    --base_precision '"${PREC}"' \
    --lr '"${ALR}"' --batch_size '"${BS}"' \
    --frames '"${FRAMES}"' --beat-aware-crop \
    '"${LENARG}"' \
    --num_workers 6 --seed '"${SEED}"' --no_demos --logger '"${LOGGER}"' \
    --name '"${NAME}"' 2>&1 | tee -a "'"${RUN}"'"/train.log
' &
}

echo "[reg-ab] image=${SIF}  data=${DATA_DIR} ($(wc -l < ${DATA_DIR}/filelist.txt) files)  sidecar=${BIGSET_SIDECAR}"
echo "[reg-ab] T=${FRAMES} prec=${PREC} lr=${LR} bs=${BS} seed=${SEED} LOUT=${LOUT} tgate=${TGATE} agc=${AGCLAM} clip=${CLIPVAL}  ${LENARG}"
gcd=0
for spec in "${ARM_SPECS[@]}"; do run_arm ${gcd} ${spec}; gcd=$((gcd + 1)); done
wait
echo "[reg-ab] all arms trained. Checkpoints:"
ls -1 ${SCRATCH}/runs/fullft_reg_ab/*/epoch=*.ckpt 2>/dev/null | grep -v '\.weights\.ckpt$' || true

# ── PROBE: render the cfg16 canary for every checkpoint (saves z0.npy), then print the latent-std
#    table. cfg16 is the early-warning axis (surfaced #68's drift an epoch before cfg1/7). ──
echo "[reg-ab] rendering cfg16 canary cells per checkpoint..."
for RUN in ${SCRATCH}/runs/fullft_reg_ab/*/; do
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
    --only-cfgs 16 --strengths 1.0 || echo "[reg-ab] render '"${LABEL}"' ep'"${EP}"' FAILED (non-fatal)"
' || true
  done
done

echo "[reg-ab] ===== LATENT-STD TABLE (the bounding verdict) ====="
singularity exec --bind ${PROJ},${SCRATCH},${FLASH} "${SIF}" bash -c '
source '"${VENV}"'/bin/activate
python - <<PYEOF
import numpy as np, glob, re, os
from collections import defaultdict
rows=defaultdict(list)
for f in sorted(glob.glob("'"${ROUT}"'/fullft_reg_ab_*__ep*__cfg16__*.z0.npy")):
    b=os.path.basename(f)
    m=re.search(r"fullft_reg_ab_(.+?)__ep(\d+)__",b)
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
print("VERDICT: anchor should climb (positive control). A bounding arm tracks ~1.0 with 0 non-finite;")
print("         reg_only/agc test whether the GENTLE levers bound it; agc_reg vs wd is the detail")
print("         headline (needs Kim ears + the disintegration/HF-retention DSP proxy, not std alone).")
PYEOF
'
echo "[reg-ab] DONE. Pull cells (fullft_reg_ab_*) for audition; the std table is bounding-only —"
echo "         the detail question (agc_reg vs wd) is decided by Kim's ears + the DSP proxy."
if [ "${LOGGER}" = "wandb" ]; then
  echo "[reg-ab] wandb offline run dirs (8 arms), pull + sync per lumi-ops SKILL:"
  ls -d ${SCRATCH}/runs/fullft_reg_ab/*/wandb/offline-run-* 2>/dev/null || echo "  (none yet — check after arms finish)"
fi
