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
# corpus (12,523 tracks, goa_archive) which is still preencoding as of this writing. Once
# that lands at ${SCRATCH}/latents_goa_bigset, resubmit with GOA_DIR=latents_goa_bigset for
# the real mixed run Kim actually asked for -- this stand-in is a deliberate, flagged
# substitution, not a silent one.
#
# ── WARMUP_EPOCHS (not WARMUP_FRAC directly) ── Kim asked for "warmup of 0.5 epochs", an
# absolute epoch count, not train_lora.py's --warmup-frac (a fraction of TOTAL steps across
# all epochs). Computed here as WARMUP_FRAC = WARMUP_EPOCHS / EPOCHS so "0.5 epochs" means
# the same thing regardless of how many EPOCHS this run ends up doing.
#
# ── DDP: THIRD launch pattern tonight, this one from the actual CSC/LUMI reference recipe
#    (~/Projects/llm-fine-tuning-examples, run-finetuning-lumi-gpu8.sh -- Kim pointed at it
#    2026-08-17). Rounds 1-2 both used --gpus-per-task=1 srun with N tasks, relying on
#    Lightning's SLURMEnvironment to auto-detect a DDP group from SLURM_NTASKS/SLURM_PROCID:
#      round 1: omitted --devices -- job 21161065 SILENTLY trained as 8 uncoordinated
#        single-GPU copies (confirmed via train_rank*.log: LOCAL_RANK: 0 on ALL 8 ranks, and
#        ckpt_dup_delta.py: the 5 "duplicate" checkpoints had genuinely diverged weights,
#        521/522 tensors differ, max_abs_diff ~0.25-0.27 -- not floating-point noise).
#      round 2: added --devices 8 -- crashed outright (job 21245565,
#        MisconfigurationException: "You requested gpu: [0..7] But your machine only has:
#        [0]" -- cgroup-isolated --gpus-per-task=1 means each process only ever sees ONE
#        GPU, so --devices N>1 asks Lightning to grab N GPUs from inside a single process).
#    CSC's own reference recipe does neither: --ntasks=1 (ONE task, all 8 GPUs visible, no
#    cgroup isolation) + `torchrun --standalone --nproc-per-node=8` INSIDE that task, which
#    spawns and coordinates the 8 worker processes itself via RANK/LOCAL_RANK/WORLD_SIZE env
#    vars -- sidesteps SLURMEnvironment guessing entirely. Lightning auto-detects
#    TorchElasticEnvironment from those vars. REQUIRED companion fix (train_lora.py, same
#    commit): torch.cuda.set_device(LOCAL_RANK) added before model load, since with all 8
#    GPUs visible per process (no cgroup remap), torch.device("cuda") would otherwise
#    resolve every rank to physical GPU 0 -- the exact "Pattern 1 OOM" fullft_avp_aug.sbatch
#    already warned about. UNVERIFIED end to end -- SMOKE test first (see RUN below).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
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
WEIGHT_DECAY=${WEIGHT_DECAY:-0.03}
RUNTAG=${RUNTAG:-}
NAME=fullft_mixed_avp_${GOA_DIR}_t4096${RUNTAG:+_${RUNTAG}}
RUN=${SCRATCH}/runs/${NAME}
SIDECAR=${CODE}/lumi/goa_longform_sidecar.json
SMOKE=${SMOKE:-0}
mkdir -p "${RUN}" "${FLASH}"

[ -n "${SIF}" ] || { echo "[fullft-mixed] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[fullft-mixed] FATAL: ${VENV} missing"; exit 1; }
grep -q -- "--warmup-frac" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[fullft-mixed] FATAL: train_lora.py missing --warmup-frac (code refresh needed)"; exit 1; }
grep -q -- 'LOCAL_RANK.*set_device\|set_device.*LOCAL_RANK' "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[fullft-mixed] FATAL: train_lora.py missing the LOCAL_RANK set_device fix (code refresh needed -- REQUIRED for torchrun, else all ranks OOM on GPU 0)"; exit 1; }
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
echo "[fullft-mixed] latents_avp: ${NAVP} crops, ${GOA_DIR}: ${NGOA} crops (total ~$((NAVP+NGOA)))  image=${SIF}  SMOKE=${SMOKE}"
echo "[fullft-mixed] GOA_DIR=${GOA_DIR} BS=${BS} GA=${GA} (per-GPU $((BS*GA)), GLOBAL eff batch $((BS*GA*8)) across 8 torchrun-coordinated ranks) FRAMES=${FRAMES} PREC=${PREC} LR=${LR} EPOCHS=${EPOCHS} CKEVERY=${CKEVERY} WARMUP_EPOCHS=${WARMUP_EPOCHS} (frac=${WARMUP_FRAC}) GRAD_CLIP_MODE=${GRAD_CLIP_MODE} WEIGHT_DECAY=${WEIGHT_DECAY} RUNTAG=${RUNTAG:-none} NAME=${NAME}"

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME_ARGS=()
[ -n "${FATCKPT}" ] && { RESUME_ARGS=(--resume_ckpt "${FATCKPT}"); echo "[fullft-mixed] resuming from ${FATCKPT}"; }

STEP_ARGS=(--epochs "${EPOCHS}")
[ "${SMOKE}" = "1" ] && STEP_ARGS=(--steps 20)   # omitting --epochs caps max_steps=--steps

srun --nodes=1 --ntasks=1 --cpus-per-task=56 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-mixed MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-mixed
export TRITON_CACHE_DIR=/tmp/triton-mixed PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-mixed /tmp/triton-mixed; mkdir -p /tmp/miopen-mixed /tmp/triton-mixed
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

echo "[fullft-mixed] node=$(hostname) launching torchrun --nproc-per-node=8"
torchrun --standalone --nnodes=1 --nproc-per-node=8 \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
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
  '"${STEP_ARGS[*]}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  '"${RESUME_ARGS[*]}"' \
  --num_workers 6 --seed 1 --no_demos --logger csv \
  --name '"${NAME}"' 2>&1 | tee -a '"${RUN}"'/train.log
'
echo "[fullft-mixed] DONE — verify (read log, not rc):"
echo "  ranks: grep -h LOCAL_RANK ${RUN}/train.log | sort -u   (want LOCAL_RANK 0..7, NOT eight 0s)"
echo "  NO -vN ckpts (dup writers): ls ${RUN}/epoch=*-v[0-9]*.ckpt 2>/dev/null && echo BAD || echo ok"
ls -la "${RUN}" 2>/dev/null | grep -E "epoch=|train.log" | head
