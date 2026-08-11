#!/bin/bash
# fullft_avp_regsweep.sbatch — the AVP recipe sweep (CONTINUITY, Kim direct 2026-08-11).
# Full-FT on Kim's OWN music (AVP aug×8, PRE-ENCODED latents_avp) so he hears how well each recipe learns
# what's unique + gets publishables. bf16-mixed + T1024 for speed. 8 arms, 1 GCD each (single-GPU, the
# precision_ladder/wd_ab pattern), ALL on VERIFIED code (no rushed new arms).
#
# WEIGHTED TOWARD THE RECIPE-FAITHFUL ANSWER (Zach Evans, SA Discord 2026-08-11: SA3-base was pretrained
# MOSTLY with AdamW; Muon came late/brief for variable-length. So a well-tuned AdamW full-FT is the faithful
# continuation AND has no runaway — Part I: Muon only ~1.1× at scale). Arms:
#   anchor      = fusion wd0.01  -> the RUNAWAY control (should climb)
#   wd0p1       = fusion wd0.1   -> "make sustained Muon behave" via proper decay
#   wd0p1_agc   = fusion wd0.1 + AGC (decay + scale-relative clip)
#   agc         = fusion wd0.01 + AGC alone (isolate the clip)
#   outstd      = fusion wd0.01 + output-std penalty (objective-adjacent lever)
#   adamw_1e4/2e4/3e4 = FAIRLY-TUNED AdamW full-FT, 3-point LR bracket (the primary; Part-I says tune its
#                       OWN lr, not fusion's 8e-5) + grad-clip.
# ELEGANT tier (Hyperball / SFWN / CMuon / σReparam) needs new code -> separate verified fast-follow job,
# NOT rushed here. VERDICT = latent-std table (tail) + Kim's ears (does it bound the runaway AND learn AVP?).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=sa3_avp_regsweep
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
# T1024 / fp32 / bs4 / 10ep, ckpt every 2. 2026-08-11: PREC fp32 (was bf16-mixed — that kept norm weights
# fp32 vs bf16 input => "cannot dispatch to fused" => slow fallback: 6.5h / 0 ckpts). fp32=32-true is the
# proven-throughput mode (#68 full-FT checkpointed on 1 GCD). Timed smoke measures s/step before full launch.
FRAMES=${FRAMES:-1024}; EPOCHS=${EPOCHS:-10}; CKEVERY=${CKEVERY:-2}; BS=${BS:-4}; SEED=${SEED:-1}; PREC=${PREC:-fp32}
LR=${LR:-8e-5}; LOGGER=${LOGGER:-wandb}
LOUT=${LOUT:-0.1}; TGATE=${TGATE:-0.5}; AGCLAM=${AGCLAM:-0.01}; CLIPVAL=${CLIPVAL:-1.0}

[ -n "${SIF}" ] || { echo "[avp-sweep] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[avp-sweep] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[avp-sweep] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }
grep -q -- "--weight_decay" "${CODE}/stable-audio-3/scripts/train_lora.py" || { echo "[avp-sweep] FATAL: train_lora too old (no --weight_decay/--grad-clip-mode/--output-std-penalty) — code refresh"; exit 1; }

# ── stage pre-encoded AVP aug×8 latents to node-local NVMe once (captions ride in each crop's .json) ──
if [ ! -d "${FLASH}/latents_avp" ]; then
  [ -f "${SCRATCH}/latents_avp.tar.gz" ] || { echo "[avp-sweep] FATAL: ${SCRATCH}/latents_avp.tar.gz missing"; exit 1; }
  mkdir -p "${FLASH}/latents_avp"
  tar -xzf "${SCRATCH}/latents_avp.tar.gz" -C "${FLASH}/latents_avp" --strip-components=1
fi
NCROP=$(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)
echo "[avp-sweep] latents_avp (base+×8): ${NCROP} crops (expect ~2394)  T=${FRAMES} prec=${PREC} ep=${EPOCHS} bs=${BS}"

# ── 8 arms, one distinct GCD each, via ONE srun --ntasks=8 --gpus-per-task=1 ──
# --gpus-per-task=1 cgroup-pins each of the 8 tasks to a DISTINCT GCD (the verified
# efp_fp32_compare pattern). NO ROCR_VISIBLE_DEVICES + background-srun mix — that was
# the bug (all 8 arms landed on the SAME GCD -> 8-way OOM, job 20964697).
echo "[avp-sweep] launching 8 arms on 8 distinct GCDs (one srun --ntasks=8 --gpus-per-task=1; cgroup-pinned, NO ROCR)${SMOKE:+ [SMOKE: --steps 40]}"
srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186; CODE=${PROJ}/code
source '"${VENV}"'/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-${ARM} /tmp/triton-${ARM}; mkdir -p /tmp/miopen-${ARM} /tmp/triton-${ARM}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True PYTORCH_ALLOC_CONF=expandable_segments:True
# SLURM_JOB_NAME=bash forces Lightning LightningEnvironment (single-process) so the 8
# DIFFERENT-config tasks do NOT try to form one broken DDP group / collide on the DDP
# port. NO MASTER_PORT (unneeded once single-process). NO ROCR_VISIBLE_DEVICES anywhere.
export SLURM_JOB_NAME=bash
export WANDB_MODE=offline WANDB_PROJECT=fullft_avp_regsweep
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

# ── config (injected from the outer script; env-overridable there) ──
FRAMES='"${FRAMES}"'; EPOCHS='"${EPOCHS}"'; CKEVERY='"${CKEVERY}"'; BS='"${BS}"'; SEED='"${SEED}"'; PREC='"${PREC}"'; LOGGER='"${LOGGER}"'; LR='"${LR}"'
LOUT='"${LOUT}"'; TGATE='"${TGATE}"'; AGCLAM='"${AGCLAM}"'; CLIPVAL='"${CLIPVAL}"'; SMOKE='"${SMOKE:-}"'
REG="--output-std-penalty ${LOUT} --output-std-t-gate ${TGATE}"
AGC="--grad-clip-mode agc --agc-lambda ${AGCLAM}"
CLIP="--gradient_clip_val ${CLIPVAL}"

# ── arm table: ARM=SLURM_PROCID selects (LABEL, OPT, LR, WD, EXTRA) ──
case ${ARM} in
  0) LABEL=anchor;    OPT=fusion; ALR=${LR}; WD=0.01; EXTRA="" ;;
  1) LABEL=wd0p1;     OPT=fusion; ALR=${LR}; WD=0.1;  EXTRA="" ;;
  2) LABEL=wd0p1_agc; OPT=fusion; ALR=${LR}; WD=0.1;  EXTRA="${AGC}" ;;
  3) LABEL=agc;       OPT=fusion; ALR=${LR}; WD=0.01; EXTRA="${AGC}" ;;
  4) LABEL=outstd;    OPT=fusion; ALR=${LR}; WD=0.01; EXTRA="${REG}" ;;
  5) LABEL=adamw_1e4; OPT=adamw;  ALR=1e-4;  WD=0.1;  EXTRA="${CLIP}" ;;
  6) LABEL=adamw_2e4; OPT=adamw;  ALR=2e-4;  WD=0.1;  EXTRA="${CLIP}" ;;
  7) LABEL=adamw_3e4; OPT=adamw;  ALR=3e-4;  WD=0.1;  EXTRA="${CLIP}" ;;
  *) echo "[avp-sweep] arm ${ARM} unassigned"; exit 0 ;;
esac

# SMOKE: fast 8-arm placement check (distinct GCDs, no OOM) before the full run.
if [ -n "${SMOKE}" ]; then RUNARGS="--steps ${SMOKE_STEPS:-150} --checkpoint_every ${SMOKE_CKSTEP:-75}"; else RUNARGS="--epochs ${EPOCHS} --checkpoint_every_epochs ${CKEVERY}"; fi

NAME=fullft_avp_regsweep_${LABEL}
RUN=${SCRATCH}/runs/fullft_avp_regsweep/${NAME}
mkdir -p "${RUN}"; export WANDB_DIR="${RUN}"
echo "[avp-sweep] arm ${ARM} -> ${LABEL}: opt=${OPT} lr=${ALR} wd=${WD} extra=[${EXTRA}] runargs=[${RUNARGS}] -> ${RUN}"
_T0=${SECONDS}
if python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base --full-finetune \
    --encoded_dir ${FLASH}/latents_avp \
    --save_dir "${RUN}" \
    --optimizer ${OPT} --weight_decay ${WD} ${EXTRA} \
    --use-ema --ema-beta 0.9999 \
    --base_precision ${PREC} \
    --lr ${ALR} --batch_size ${BS} \
    --frames ${FRAMES} --beat-aware-crop \
    ${RUNARGS} \
    --num_workers 6 --seed ${SEED} --no_demos --logger ${LOGGER} \
    --name ${NAME} 2>&1 | tee -a "${RUN}"/train.log; then
  echo "[avp-sweep] arm ${ARM} (${LABEL}) DONE — $((SECONDS-_T0))s wall for runargs=[${RUNARGS}]" | tee -a "${RUN}"/train.log
else
  echo "[avp-sweep] arm ${ARM} (${LABEL}) FAILED — see ${RUN}/train.log (siblings unaffected)"
fi
'
# PROBE TAIL is best-effort telemetry — training already succeeded via the srun above; do NOT let
# a render/table hiccup (or a ckpt-less SMOKE) mark the whole job FAILED. Read the artifact, not the rc.
set +e
echo "[avp-sweep] all arms done. Checkpoints:"
ls -1 ${SCRATCH}/runs/fullft_avp_regsweep/*/epoch=*.ckpt 2>/dev/null | grep -v '\.weights\.ckpt$' || true

# ── PROBE: render cfg16 canary per ckpt (saves z0.npy) + print the latent-std table (FIXED heredoc) ──
echo "[avp-sweep] rendering cfg16 canary per checkpoint..."
for RUN in ${SCRATCH}/runs/fullft_avp_regsweep/*/; do
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
    --only-cfgs 16 --strengths 1.0 || echo "[avp-sweep] render '"${LABEL}"' ep'"${EP}"' FAILED (non-fatal)"
' || true
  done
done

echo "[avp-sweep] ===== LATENT-STD TABLE (bounding verdict) ====="
singularity exec --bind ${PROJ},${SCRATCH},${FLASH} "${SIF}" bash -c '
source '"${VENV}"'/bin/activate
python - <<PYEOF
import numpy as np, glob, re, os
from collections import defaultdict
rows=defaultdict(list)
for f in sorted(glob.glob("'"${ROUT}"'/fullft_avp_regsweep_*__ep*__cfg16__*.z0.npy")):
    b=os.path.basename(f)
    m=re.search(r"fullft_avp_regsweep_(.+?)__ep(\d+)__",b)
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
print("READ: anchor climbs = runaway on AVP too. Arms tracking ~1.0 w/ 0 non-finite = bounded; then AUDITION")
print("      those (pull fullft_avp_regsweep_* cells) for how well each learns AVP. adamw_* = recipe-faithful.")
PYEOF
'
echo "[avp-sweep] done. Pull cells (fullft_avp_regsweep_*) to audition; std table above = bounding pre-screen."
