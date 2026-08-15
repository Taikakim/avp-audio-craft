#!/bin/bash
# subloss_goa_k20_fullft.sbatch — CONTINUITY 2026-08-15 (Kim direct): scale the subspace-
# weighted RF loss (#59) up from its original lightweight DoRA+AdamW grid (K in {2,5,12},
# T512, subspace_loss_v3sel_grid_mt.sbatch) to the SAME full-FT+FusionOpt+EMA+warmup+AGC
# recipe used tonight for fullft_avp_aug_warmup_agc — on GOA, K=20 (past the old grid's
# max), T1024, fp32 (Kim: "actually, make it fp32").
#
# ── WHY THIS IS A BIGGER CHANGE THAN "K12 -> K20" (flagging, not silently deciding) ──
# "warmup" only has meaning under --optimizer fusion (train_lora.py: "FusionOpt only... No
# effect for adamw"), and --use-ema is full-finetune ONLY (LoRA/DoRA force-disables it) --
# so asking for EMA+warmup+AGC together necessarily means switching off the original K-grid's
# adamw+DoRA-adapter setup onto fusion+full-FT. Also defaulting to the melody-SELECTIVE v3
# basis (whitened-CSP, 5.1x melody-over-codec-noise SNR held-out) rather than the older v2
# basis the original "subloss_goa_k{2,5,12}" runs used (v2 measured ~1.0x selectivity on
# held-out data -- the probable reason #59 read weak) -- v3 is the confirmed-better one.
#
# ── DDP: Pattern 2, IDENTICAL launch to fullft_avp_aug.sbatch (proven tonight, job 21148122)
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=48:00:00
#SBATCH --job-name=sa3_subloss_goa_k20
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
K=${K:-20}
BASIS_NAME=${BASIS_NAME:-melody_subspace15_selective_v3.npz}
BS=${BS:-2}; GA=${GA:-2}; FRAMES=${FRAMES:-1024}; PREC=${PREC:-fp32}; LR=${LR:-1e-4}; EPOCHS=${EPOCHS:-20}; CKEVERY=${CKEVERY:-2}
# BS/GA changed 2026-08-15 after job 21148584 OOM'd at the original BS=4 (see
# fullft_avp_aug.sbatch's matching post-mortem comment -- EMA is hardcoded ON below and its
# memory overhead isn't safely covered by just any batch size that "looks small enough" on
# paper). BS=2 GA=2 (effective 4, same as before) is the one pattern proven surviving
# tonight (the T4096 mixed run).
WARMUP_FRAC=${WARMUP_FRAC:-0.05}
GRAD_CLIP_MODE=${GRAD_CLIP_MODE:-agc}
RUNTAG=${RUNTAG:-}
NAME=subloss_goa_k${K}${RUNTAG:+_${RUNTAG}}
RUN=${SCRATCH}/runs/${NAME}
BASIS=${CODE}/lumi/${BASIS_NAME}
SIDECAR=${CODE}/lumi/goa_longform_sidecar.json
mkdir -p "${RUN}" "${FLASH}"

[ -n "${SIF}" ] || { echo "[subloss-k20] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[subloss-k20] FATAL: ${VENV} missing"; exit 1; }
grep -q -- "--warmup-frac" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[subloss-k20] FATAL: train_lora.py missing --warmup-frac (code refresh needed)"; exit 1; }
grep -q -- "--subspace-loss-basis\|--subspace_loss_basis" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[subloss-k20] FATAL: train_lora.py missing --subspace-loss-basis (code refresh needed)"; exit 1; }
[ -f "${BASIS}" ] || { echo "[subloss-k20] FATAL: ${BASIS} not shipped"; exit 1; }
[ -f "${SIDECAR}" ] || { echo "[subloss-k20] FATAL: ${SIDECAR} not shipped"; exit 1; }

if [ ! -d "${FLASH}/latents_sa3" ]; then
  mkdir -p "${FLASH}/latents_sa3"
  tar -xzf "${SCRATCH}/latents_sa3.tar.gz" -C "${FLASH}/latents_sa3" --strip-components=1
fi
NCROP=$(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)
echo "[subloss-k20] latents_sa3 (goa): ${NCROP} crops (expect ~5400)  image=${SIF}"
echo "[subloss-k20] K=${K} BASIS=${BASIS_NAME} BS=${BS} GA=${GA} (eff batch $((BS*GA))) FRAMES=${FRAMES} PREC=${PREC} LR=${LR} EPOCHS=${EPOCHS} CKEVERY=${CKEVERY} WARMUP_FRAC=${WARMUP_FRAC} GRAD_CLIP_MODE=${GRAD_CLIP_MODE} RUNTAG=${RUNTAG:-none} NAME=${NAME}"

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

# fp32 fused-SDPA probe (#68/aug8 recipe): native fp32 attention if the fused kernel is
# available, else cast bf16 for the SDPA only. Only runs when PREC=fp32.
if [ "'"${PREC}"'" = "fp32" ]; then
  if python - <<PYEOF
import torch
from torch.nn.attention import sdpa_kernel, SDPBackend
q = torch.randn(1, 24, 4096, 64, device="cuda", dtype=torch.float32)
try:
    with sdpa_kernel([SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION]):
        torch.nn.functional.scaled_dot_product_attention(q, q, q)
    raise SystemExit(0)
except SystemExit as e:
    raise
except Exception:
    raise SystemExit(1)
PYEOF
  then export SA3_SDPA_CAST_BF16=0; else export SA3_SDPA_CAST_BF16=1; fi
  echo "[rank ${SLURM_PROCID}] fp32 SDPA cast_bf16=${SA3_SDPA_CAST_BF16}"
fi

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME=""; [ -n "${FATCKPT}" ] && { RESUME="--resume_ckpt ${FATCKPT}"; echo "[subloss-k20] resuming from ${FATCKPT}"; }

echo "[rank ${SLURM_PROCID}/${SLURM_NTASKS}] node=$(hostname) local=${SLURM_LOCALID} TRAIN '"${NAME}"'"
python ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --full-finetune \
  --encoded_dir ${FLASH}/latents_sa3 \
  --save_dir "'"${RUN}"'" \
  --optimizer fusion \
  --use-ema --ema-beta 0.9999 \
  --warmup-frac '"${WARMUP_FRAC}"' \
  --grad-clip-mode '"${GRAD_CLIP_MODE}"' \
  --subspace-loss-basis '"${BASIS}"' --subspace-loss-weight '"${K}"' \
  --base_precision '"${PREC}"' \
  --lr '"${LR}"' --batch_size '"${BS}"' --accumulate_grad_batches '"${GA}"' \
  --frames '"${FRAMES}"' --beat-aware-crop \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  ${RESUME} \
  --num_workers 6 --seed 1 --no_demos --logger csv \
  --caption_sidecar "'"${SIDECAR}"'" --caption_probs 0,0,1 \
  --name '"${NAME}"' 2>&1 | tee -a '"${RUN}"'/train_rank${SLURM_PROCID}.log
'
echo "[subloss-k20] DONE — verify (read log, not rc):"
echo "  NO -vN ckpts (dup writers): ls ${RUN}/epoch=*-v[0-9]*.ckpt 2>/dev/null && echo BAD || echo ok"
ls -la "${RUN}" 2>/dev/null | grep -E "epoch=|train_rank0" | head
