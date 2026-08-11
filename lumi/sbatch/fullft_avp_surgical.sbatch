#!/bin/bash
# fullft_avp_surgical.sbatch — the AVP "surgical levers" sweep (CONTINUITY, Kim direct 2026-08-11).
# Full-FT on Kim's OWN music (AVP aug×8, PRE-ENCODED latents_avp) — the ELEGANT-tier fast-follow to
# fullft_avp_regsweep, now on VERIFIED code (Hyperball / CMuon-AdaLN / force-scalar / x0-loss all PASS).
# Same rig as regsweep: bf16-mixed + T1024, 8 arms, 1 GCD each (single-GPU/arm), wandb-offline, z0-std probe tail.
#
# Goal: ISOLATE each surgical lever against the runaway control, then stack them all. Arms:
#   anchor       = fusion wd0.01                          -> the RUNAWAY control (should climb)
#   wd0p1        = fusion wd0.1                            -> Muon+decay baseline
#   force_scalar = fusion wd0.01 + --force-scalar-output  -> isolate: keep output projections off spectral path
#   cmuon        = fusion wd0.1  + --fusion-split-adaln   -> isolate: per-block NS5 on the AdaLN emitter
#   x0           = fusion wd0.1  + --x0-loss-weight 0.5   -> isolate: x0-consistency aux loss
#   SURGICAL     = fusion wd0.1  + AGC + output-std + force-scalar + cmuon + x0  -> EVERYTHING stacked
#   hyperball    = fusion wd0.0  + --hyperball            -> Hyperball retraction (wd ignored by design)
#   adamw_2e4    = adamw  2e-4 wd0.1 + grad-clip 1.0      -> recipe-faithful reference
# VERDICT = latent-std table (tail) + Kim's ears (does each lever bound the runaway AND learn AVP?).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=sa3_avp_surgical
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
# 2026-08-11: fp32-bs4 AND fp32-bs2 BOTH OOM'd one 64GB GCD with the SAME ~7GB-allocated/0-free signature
# (jobs 20993180, 21004204) — batch-INDEPENDENT, so NOT activation-bound (earlier estimate wrong). Kim:
# instrument VRAM + drop to T512/bs2 while diagnosing. FRAMES 1024->512 halves activations again; the
# [gpu-assign] echo + per-arm rocm-smi sampler below decide collision-vs-per-arm-too-big on the next smoke.
FRAMES=${FRAMES:-512}; EPOCHS=${EPOCHS:-10}; CKEVERY=${CKEVERY:-2}; BS=${BS:-2}; SEED=${SEED:-1}; PREC=${PREC:-fp32}
LR=${LR:-8e-5}; LOGGER=${LOGGER:-wandb}
LOUT=${LOUT:-0.1}; TGATE=${TGATE:-0.5}; AGCLAM=${AGCLAM:-0.01}; CLIPVAL=${CLIPVAL:-1.0}

[ -n "${SIF}" ] || { echo "[avp-surgical] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[avp-surgical] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[avp-surgical] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }
grep -q -- "--weight_decay" "${CODE}/stable-audio-3/scripts/train_lora.py" || { echo "[avp-surgical] FATAL: train_lora too old (no --weight_decay/--grad-clip-mode/--output-std-penalty) — code refresh"; exit 1; }
for FLAG in "--hyperball" "--force-scalar" "--x0-loss-weight" "--fusion-split-adaln"; do
  grep -q -- "${FLAG}" "${CODE}/stable-audio-3/scripts/train_lora.py" || { echo "[avp-surgical] FATAL: train_lora too old (no ${FLAG}) — code refresh (rsync train_lora.py + fusion vendor)"; exit 1; }
done

# ── stage pre-encoded AVP aug×8 latents to node-local NVMe once (captions ride in each crop's .json) ──
if [ ! -d "${FLASH}/latents_avp" ]; then
  [ -f "${SCRATCH}/latents_avp.tar.gz" ] || { echo "[avp-surgical] FATAL: ${SCRATCH}/latents_avp.tar.gz missing"; exit 1; }
  mkdir -p "${FLASH}/latents_avp"
  tar -xzf "${SCRATCH}/latents_avp.tar.gz" -C "${FLASH}/latents_avp" --strip-components=1
fi
NCROP=$(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)
echo "[avp-surgical] latents_avp (base+×8): ${NCROP} crops (expect ~2394)  T=${FRAMES} prec=${PREC} ep=${EPOCHS} bs=${BS}"

# ── 8 arms, one distinct GCD each, via ONE srun --ntasks=8 --gpus-per-task=1 ──
# --gpus-per-task=1 cgroup-pins each of the 8 tasks to a DISTINCT GCD (the verified
# efp_fp32_compare pattern). NO ROCR_VISIBLE_DEVICES + background-srun mix — that was
# the bug (all 8 arms landed on the SAME GCD -> 8-way OOM, job 20964697).
echo "[avp-surgical] launching 8 arms on 8 distinct GCDs (one srun --ntasks=8 --gpus-per-task=1; cgroup-pinned, NO ROCR)${SMOKE:+ [SMOKE: --steps 40]}"
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
export WANDB_MODE=offline WANDB_PROJECT=fullft_avp_surgical
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true
# ── VRAM instrumentation (Kim 2026-08-11): which physical GCD did Slurm give THIS arm? all-same => collision ──
echo "[gpu-assign] arm=${ARM} STEP_GPUS=${SLURM_STEP_GPUS:-} ORDINAL=${GPU_DEVICE_ORDINAL:-} ROCR=${ROCR_VISIBLE_DEVICES:-} HIP=${HIP_VISIBLE_DEVICES:-} CUDA=${CUDA_VISIBLE_DEVICES:-}"

# ── config (injected from the outer script; env-overridable there) ──
FRAMES='"${FRAMES}"'; EPOCHS='"${EPOCHS}"'; CKEVERY='"${CKEVERY}"'; BS='"${BS}"'; SEED='"${SEED}"'; PREC='"${PREC}"'; LOGGER='"${LOGGER}"'; LR='"${LR}"'
LOUT='"${LOUT}"'; TGATE='"${TGATE}"'; AGCLAM='"${AGCLAM}"'; CLIPVAL='"${CLIPVAL}"'; SMOKE='"${SMOKE:-}"'
REG="--output-std-penalty ${LOUT} --output-std-t-gate ${TGATE}"
AGC="--grad-clip-mode agc --agc-lambda ${AGCLAM}"
CLIP="--gradient_clip_val ${CLIPVAL}"

# ── arm table: ARM=SLURM_PROCID selects (LABEL, OPT, LR, WD, EXTRA) ──
case ${ARM} in
  0) LABEL=anchor;       OPT=fusion; ALR=${LR}; WD=0.01; EXTRA="" ;;
  1) LABEL=wd0p1;        OPT=fusion; ALR=${LR}; WD=0.1;  EXTRA="" ;;
  2) LABEL=force_scalar; OPT=fusion; ALR=${LR}; WD=0.01; EXTRA="--force-scalar-output" ;;
  3) LABEL=cmuon;        OPT=fusion; ALR=${LR}; WD=0.1;  EXTRA="--fusion-split-adaln" ;;
  4) LABEL=x0;           OPT=fusion; ALR=${LR}; WD=0.1;  EXTRA="--x0-loss-weight 0.5" ;;
  5) LABEL=SURGICAL;     OPT=fusion; ALR=${LR}; WD=0.1;  EXTRA="${AGC} ${REG} --force-scalar-output --fusion-split-adaln --x0-loss-weight 0.5" ;;
  6) LABEL=hyperball;    OPT=fusion; ALR=${LR}; WD=0.0;  EXTRA="--hyperball" ;;
  7) LABEL=adamw_2e4;    OPT=adamw;  ALR=2e-4;  WD=0.1;  EXTRA="${CLIP}" ;;
  *) echo "[avp-surgical] arm ${ARM} unassigned"; exit 0 ;;
esac

# SMOKE: fast 8-arm placement check (distinct GCDs, no OOM) before the full run.
if [ -n "${SMOKE}" ]; then RUNARGS="--steps ${SMOKE_STEPS:-150} --checkpoint_every ${SMOKE_CKSTEP:-75}"; else RUNARGS="--epochs ${EPOCHS} --checkpoint_every_epochs ${CKEVERY}"; fi

NAME=fullft_avp_surgical_${LABEL}
RUN=${SCRATCH}/runs/fullft_avp_surgical/${NAME}
mkdir -p "${RUN}"; export WANDB_DIR="${RUN}"
# per-arm VRAM curve (native rocm-smi, ~6s cadence, self-limiting ~9min, best-effort) -> where does memory blow up
( for _i in $(seq 1 90); do echo "=== t=$(date +%s) arm=${ARM} ===" >> "${RUN}/vram_${ARM}.log"; rocm-smi --showmeminfo vram >> "${RUN}/vram_${ARM}.log" 2>&1 || true; sleep 6; done ) &
echo "[avp-surgical] arm ${ARM} -> ${LABEL}: opt=${OPT} lr=${ALR} wd=${WD} extra=[${EXTRA}] runargs=[${RUNARGS}] -> ${RUN}"
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
  echo "[avp-surgical] arm ${ARM} (${LABEL}) DONE — $((SECONDS-_T0))s wall for runargs=[${RUNARGS}]" | tee -a "${RUN}"/train.log
else
  echo "[avp-surgical] arm ${ARM} (${LABEL}) FAILED — see ${RUN}/train.log (siblings unaffected)"
fi
'
# PROBE TAIL is best-effort telemetry — training already succeeded via the srun above; do NOT let
# a render/table hiccup (or a ckpt-less SMOKE) mark the whole job FAILED. Read the artifact, not the rc.
set +e
echo "[avp-surgical] all arms done. Checkpoints:"
ls -1 ${SCRATCH}/runs/fullft_avp_surgical/*/epoch=*.ckpt 2>/dev/null | grep -v '\.weights\.ckpt$' || true

# ── PROBE: render cfg16 canary per ckpt (saves z0.npy) + print the latent-std table (FIXED heredoc) ──
echo "[avp-surgical] rendering cfg16 canary per checkpoint..."
for RUN in ${SCRATCH}/runs/fullft_avp_surgical/*/; do
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
    --only-cfgs 16 --strengths 1.0 || echo "[avp-surgical] render '"${LABEL}"' ep'"${EP}"' FAILED (non-fatal)"
' || true
  done
done

echo "[avp-surgical] ===== LATENT-STD TABLE (bounding verdict) ====="
singularity exec --bind ${PROJ},${SCRATCH},${FLASH} "${SIF}" bash -c '
source '"${VENV}"'/bin/activate
python - <<PYEOF
import numpy as np, glob, re, os
from collections import defaultdict
rows=defaultdict(list)
for f in sorted(glob.glob("'"${ROUT}"'/fullft_avp_surgical_*__ep*__cfg16__*.z0.npy")):
    b=os.path.basename(f)
    m=re.search(r"fullft_avp_surgical_(.+?)__ep(\d+)__",b)
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
print("      those (pull fullft_avp_surgical_* cells) for how well each learns AVP. adamw_2e4 = recipe-faithful.")
PYEOF
'
echo "[avp-surgical] done. Pull cells (fullft_avp_surgical_*) to audition; std table above = bounding pre-screen."
