#!/bin/bash
# fullft_mixed_avp_goa_t4096.sbatch — CONTINUITY 2026-08-15 (Kim direct): "the best I hope"
# run -- full-FT, FusionOpt, EMA, warmup, AGC, T4096, bf16, MIXED avp-aug + goa dataset, one
# node, 8 GPUs. Combines three things proven separately tonight, never together:
#   - the proven T4096 full-FT batch config (efp_fullft_t4096.sbatch, 2026-07-17):
#     BS=2 + accumulate_grad_batches=2 (effective batch 4) -- T4096 bf16 full-FT is tight at
#     batch 4 live (~55GB/64GB GCD), so grad-accum keeps token-count parity while halving
#     live activation memory. NOT a guess -- this exact config already trained successfully.
#   - tonight's warmup+AGC stabilization recipe (fullft_avp_aug_warmup_agc, job 21148122)
#   - multi-source --encoded_dir mixing (train_lora.py's comma-separated dirs/sidecars/
#     weights, each source keeps its own caption path)
#
# ── GOA_DIR is a ONE-VARIABLE SWAP ── defaults to latents_sa3 (5400 crops, already pre-
# encoded, what every other goa run used tonight) as a stand-in for the TRUE big-goa
# corpus (12,523 tracks, goa_archive) which is still preencoding as of this writing (job
# 21148858, after fixing the kernel-OOM bug in pre_encode_dataset.py). Once that lands at
# ${SCRATCH}/latents_goa_bigset, resubmit with GOA_DIR=latents_goa_bigset for the real
# mixed run Kim actually asked for -- this stand-in is a deliberate, flagged substitution,
# not a silent one.
#
# ── WARMUP_EPOCHS (not WARMUP_FRAC directly) ── Kim asked for "warmup of 0.5 epochs", an
# absolute epoch count, not train_lora.py's --warmup-frac (a fraction of TOTAL steps across
# all epochs). Computed here as WARMUP_FRAC = WARMUP_EPOCHS / EPOCHS so "0.5 epochs" means
# the same thing regardless of how many EPOCHS this run ends up doing.
#
# ── DDP: Pattern 2, IDENTICAL launch to fullft_avp_aug.sbatch / subloss_goa_k20_fullft.sbatch
#    (both proven tonight, jobs 21148122 / submitted after quoting was verified).
#    CORRECTION (2026-08-17, 2 rounds): I first claimed the missing --devices flag was the
#    root cause of job 21161065's colliding -v1..-v4 checkpoints and "fixed" it by ADDING
#    --devices 8 --num_nodes 1. That was WRONG -- fullft_avp_aug.sbatch (job #68, the actual
#    proven precedent) uses this EXACT --gpus-per-task=1-with-NO---devices pattern and
#    explicitly documents "trains fine with no -vN ckpts" (see its own DDP comment block).
#    Adding --devices 8 here crashed immediately instead (job 21245565,
#    MisconfigurationException: "You requested gpu: [0..7] But your machine only has: [0]" --
#    with cgroup-isolated --gpus-per-task=1, each process only ever sees ONE GPU, so an
#    explicit --devices N>1 asks Lightning to grab N GPUs from inside a single process, which
#    fails outright). This IS the exact failure train_lora.py's own --devices help text
#    describes -- but I misread "an explicit N dies loudly instead of silently" as "so add an
#    explicit N to fix it," when it actually just means the SAME underlying misconfiguration
#    surfaces differently, not that --devices cures anything here. REVERTED to no --devices
#    (matching #68 exactly). The TRUE cause of 21161065's divergence (confirmed real via
#    ckpt_dup_delta.py: 521/522 tensors differ, max_abs_diff ~0.25-0.27 -- genuine divergence,
#    not noise) is still OPEN -- something about the multi-source --encoded_dir mixing this
#    script uses (which #68 doesn't) is the next suspect, not yet investigated.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=48:00:00
#SBATCH --job-name=sa3_fullft_mixed_t4096
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

GOA_DIR=${GOA_DIR:-latents_sa3}
BS=${BS:-2}; GA=${GA:-2}; FRAMES=${FRAMES:-4096}; PREC=${PREC:-bf16}; LR=${LR:-1e-4}
EPOCHS=${EPOCHS:-8}; CKEVERY=${CKEVERY:-1}
WARMUP_EPOCHS=${WARMUP_EPOCHS:-0.5}
WARMUP_FRAC=$(awk -v w="${WARMUP_EPOCHS}" -v e="${EPOCHS}" 'BEGIN{printf "%.6f", w/e}')
GRAD_CLIP_MODE=${GRAD_CLIP_MODE:-agc}
# WEIGHT_DECAY (2026-08-15, Kim direct: "the ones we pulled, apparently there's problems"):
# this script SHIPPED WITHOUT --weight_decay, meaning FusionOpt's spectral_wd defaulted to
# 0.01 -- the exact value the 2026-08-10 drone-runaway incident diagnosed as too weak for
# the NS5/Muon orthogonalized update on a full-FT run (MASTER.md/SKILL.md "FULL-FT
# LATENT-SCALE RUNAWAY" bullet). --grad-clip-mode agc is a DIFFERENT, orthogonal mechanism
# (per-step gradient magnitude clip) that does nothing to counteract multi-epoch weight-norm
# creep -- it was never going to fix this. Confirmed via the pulled ep0 z0.npy renders:
# literal numerical inf at cfg7/cfg16 (cfg1 still mostly sane) -- same CFG-amplified
# instability shape as the confirmed-corrupted precision_ladder_t256_bf16mixed dronesweep,
# just caught earlier in the trajectory (ep0 vs its ep9 full collapse). --weight_decay 0.1
# is the proven fix (routes to spectral_wd, independent of grad-clip-mode -- both apply).
WEIGHT_DECAY=${WEIGHT_DECAY:-0.03}
# LOWERED from 0.1 (2026-08-17, Kim direct): the 0.1-run's rendered ep7 checkpoint (job
# 21161065, label fullft_mixed_wdfix_ddpbug) sounded droning/thin -- underfitting, not the
# earlier inf-blown-latents corruption. 0.1 stopped the numerical runaway but may have been
# strong enough at only 8 epochs to drag the model back toward base/pretrained character
# faster than the target style develops. 0.03 is the new default; still >> FusionOpt's own
# 0.01 default (the value that caused the ORIGINAL drone-runaway), so the anti-runaway
# protection stays, just less aggressive. UNVERIFIED which value is actually right -- this
# run is the test.
RUNTAG=${RUNTAG:-}
NAME=fullft_mixed_avp_${GOA_DIR}_t4096${RUNTAG:+_${RUNTAG}}
RUN=${SCRATCH}/runs/${NAME}
SIDECAR=${CODE}/lumi/goa_longform_sidecar.json
mkdir -p "${RUN}" "${FLASH}"

[ -n "${SIF}" ] || { echo "[fullft-mixed] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[fullft-mixed] FATAL: ${VENV} missing"; exit 1; }
grep -q -- "--warmup-frac" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[fullft-mixed] FATAL: train_lora.py missing --warmup-frac (code refresh needed)"; exit 1; }
[ -f "${SIDECAR}" ] || { echo "[fullft-mixed] FATAL: ${SIDECAR} not shipped"; exit 1; }

for DS in latents_avp "${GOA_DIR}"; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    [ -f "${SCRATCH}/${DS}.tar.gz" ] || { echo "[fullft-mixed] FATAL: ${SCRATCH}/${DS}.tar.gz missing"; exit 1; }
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
NAVP=$(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)
NGOA=$(ls ${FLASH}/${GOA_DIR}/*.npy 2>/dev/null | wc -l)
echo "[fullft-mixed] latents_avp: ${NAVP} crops, ${GOA_DIR}: ${NGOA} crops (total ~$((NAVP+NGOA)))  image=${SIF}"
echo "[fullft-mixed] GOA_DIR=${GOA_DIR} BS=${BS} GA=${GA} (per-GPU $((BS*GA)), GLOBAL eff batch $((BS*GA*8)) across 8 real DDP ranks) FRAMES=${FRAMES} PREC=${PREC} LR=${LR} EPOCHS=${EPOCHS} CKEVERY=${CKEVERY} WARMUP_EPOCHS=${WARMUP_EPOCHS} (frac=${WARMUP_FRAC}) GRAD_CLIP_MODE=${GRAD_CLIP_MODE} WEIGHT_DECAY=${WEIGHT_DECAY} RUNTAG=${RUNTAG:-none} NAME=${NAME}"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUN='"${RUN}"'
VENV='"${VENV}"'
source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${SLURM_PROCID} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${SLURM_PROCID}
export TRITON_CACHE_DIR=/tmp/triton-${SLURM_PROCID} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-${SLURM_PROCID} /tmp/triton-${SLURM_PROCID}; mkdir -p /tmp/miopen-${SLURM_PROCID} /tmp/triton-${SLURM_PROCID}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME=""; [ -n "${FATCKPT}" ] && { RESUME="--resume_ckpt ${FATCKPT}"; echo "[fullft-mixed] resuming from ${FATCKPT}"; }

echo "[rank ${SLURM_PROCID}/${SLURM_NTASKS}] node=$(hostname) local=${SLURM_LOCALID} TRAIN '"${NAME}"'"
python ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --full-finetune \
  --encoded_dir ${FLASH}/latents_avp,${FLASH}/'"${GOA_DIR}"' \
  --caption_sidecar ,'"${SIDECAR}"' --caption_probs 0,0,1 \
  --save_dir "'"${RUN}"'" \
  --optimizer fusion \
  --use-ema --ema-beta 0.9999 \
  --warmup-frac '"${WARMUP_FRAC}"' \
  --grad-clip-mode '"${GRAD_CLIP_MODE}"' \
  --weight_decay '"${WEIGHT_DECAY}"' \
  --base_precision '"${PREC}"' \
  --lr '"${LR}"' --batch_size '"${BS}"' --accumulate_grad_batches '"${GA}"' \
  --frames '"${FRAMES}"' \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  ${RESUME} \
  --num_workers 6 --seed 1 --no_demos --logger csv \
  --name '"${NAME}"' 2>&1 | tee -a '"${RUN}"'/train_rank${SLURM_PROCID}.log
'
echo "[fullft-mixed] DONE — verify (read log, not rc):"
echo "  NO -vN ckpts (dup writers): ls ${RUN}/epoch=*-v[0-9]*.ckpt 2>/dev/null && echo BAD || echo ok"
ls -la "${RUN}" 2>/dev/null | grep -E "epoch=|train_rank0" | head
