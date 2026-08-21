#!/bin/bash
# fullft_suomi_warm.sbatch — Kim direct 2026-08-21: "suomisoundi full ft over both our best
# avp and (old) goa full ft. T1024, Fusion (all damping bells and whistles) + the subspace
# k5 scaling. Spectral WD larger than we're used to, cosine schedule over 32 epochs."
#
# Two arms (one node each): ARM=avpaug19 (fullft_avpaug t1024 fp32 ep19 EMA — the vetted B9
# backbone) | ARM=goaft (fullft_goa_t4096 at its MID checkpoint — goa fullfts degrade with
# training, W/G 2026-08-21, so warm-starting from "last" would bake in a near-worst base).
# Warm-start via train_lora --init_state_ckpt (weights only, EMA-preferred, fresh optimizer).
# Recipe: FULL-FT T1024 bf16, FusionOpt (mona+ns5+normuon+sf) + snr row gate + COSINE
# in-optimizer decay over all 32 epochs + spectral WD 0.2 (Kim: larger than the usual 0.1;
# the runaway lesson says 0.01 was too weak for NS5 — never omit) + EMA. Subspace: v3sel
# 15-dim melody basis, K=5 (the melody-wall winner). NO forced/force_scalar arms — the drone
# ablation showed force_scalar RUNS AWAY (54/54) while plain fusion stays clean.
# RUN: ARM=avpaug19 sbatch lumi/sbatch/fullft_suomi_warm.sbatch
#      ARM=goaft    sbatch lumi/sbatch/fullft_suomi_warm.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=suomift
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
ARM=${ARM:-avpaug19}
SEED=${SEED:-1}
BS=${BS:-2}
GA=${GA:-2}
EPOCHS=${EPOCHS:-32}
LR=${LR:-5e-5}
K=${K:-5}
DIR=suomisoundi_latents
SIDE=${CODE}/lumi/suomisoundi_caption_sidecar.json
BASIS=${CODE}/lumi/melody_subspace15_selective_v3.npz

[ -n "${SIF}" ] || { echo "[suomift] FATAL: no multitorch image"; exit 1; }
[ -f "${SIDE}" ] || { echo "[suomift] FATAL: sidecar missing"; exit 1; }
[ -f "${BASIS}" ] || { echo "[suomift] FATAL: basis missing"; exit 1; }
grep -q "init_state_ckpt" ${CODE}/stable-audio-3/scripts/train_lora.py || { echo "[suomift] FATAL: train_lora stale (no --init_state_ckpt)"; exit 1; }

# resolve the warm-start backbone
case "${ARM}" in
  avpaug19)
    INIT=${SCRATCH}/runs/fullft_fleet/fullft_avpaug_t1024_fp32_lr1e-4_s1/epoch=19-step=5980-v1.ckpt ;;
  goaft)
    mapfile -t GCKS < <(ls ${SCRATCH}/runs/*/fullft_goa_t4096/epoch=*.ckpt ${SCRATCH}/runs/fullft_goa_t4096/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -t= -k2 -V)
    [ "${#GCKS[@]}" -gt 0 ] || { echo "[suomift] FATAL: no fullft_goa_t4096 ckpts found"; exit 1; }
    INIT=${GCKS[$((${#GCKS[@]}/2))]} ;;
  *) echo "[suomift] FATAL: unknown ARM ${ARM}"; exit 1 ;;
esac
[ -f "${INIT}" ] || { echo "[suomift] FATAL: warm-start ckpt missing: ${INIT}"; exit 1; }
NAME=suomift_warm_${ARM}_t1024_bf16_k${K}_s${SEED}
RUN=${SCRATCH}/runs/suomift_warm/${NAME}
echo "[suomift] CONFIG ${NAME} INIT=${INIT} node=$(hostname) $(date -Is)"

# staging with LOCK (dorlor pattern: stage-if-EMPTY + json top-up)
LOCKDIR=${FLASH}/.stage_${DIR}.lock
if [ "$(ls ${FLASH}/${DIR}/*.npy 2>/dev/null | wc -l)" -eq 0 ]; then
  if mkdir "${LOCKDIR}" 2>/dev/null; then
    echo "[suomift] staging ${DIR} -> flash (lock held)"
    mkdir -p "${FLASH}/${DIR}"
    cp ${SCRATCH}/${DIR}/*.npy "${FLASH}/${DIR}/" 2>/dev/null
    cp ${SCRATCH}/${DIR}/*.json "${FLASH}/${DIR}/" 2>/dev/null || true
    rmdir "${LOCKDIR}"
  else
    echo "[suomift] another job is staging ${DIR}; waiting"
    while [ -d "${LOCKDIR}" ]; do sleep 20; done
  fi
fi
N=$(ls ${FLASH}/${DIR}/*.npy 2>/dev/null | wc -l)
[ "${N}" -gt 0 ] || { echo "[suomift] FATAL: staging failed"; exit 1; }
if [ "$(ls ${FLASH}/${DIR}/*.json 2>/dev/null | wc -l)" -eq 0 ]; then
  cp ${SCRATCH}/${DIR}/*.json "${FLASH}/${DIR}/" 2>/dev/null || true
fi
NJ=$(ls ${FLASH}/${DIR}/*.json 2>/dev/null | wc -l)
[ "${NJ}" -gt 0 ] || { echo "[suomift] FATAL: no .json metas on flash OR scratch"; exit 1; }
echo "[suomift] ${DIR}: ${N} latents, ${NJ} json metas on flash"

mkdir -p "${RUN}"
cat > "${RUN}/run_meta.json" <<META
{"run": "${NAME}", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "Kim direct 2026-08-21: suomisoundi FULL-FT warm-started from the ${ARM} full-FT — can the idiosyncratic suomi sound be learned on top of an already-shifted base better than from medium-base?",
 "warm_start": "${INIT}",
 "recipe": {"mode": "FULL fine-tune, warm-start (weights only, EMA-preferred)",
            "optimizer": "fusion (mona+ns5+normuon+sf) + snr row + cosine decay over all ${EPOCHS} ep",
            "lr": "${LR}", "spectral_wd": 0.2, "precision": "bf16", "frames": 1024,
            "batch_per_rank": ${BS}, "grad_accum": ${GA}, "gpus": 8, "ddp": "torchrun",
            "effective_batch": $((BS*GA*8)), "epochs": ${EPOCHS}, "seed": ${SEED}, "ema": true,
            "subspace": {"basis": "melody_subspace15_selective_v3.npz", "K": ${K}}},
 "dataset": {"name": "suomisoundi (1260)", "caption": "suomisoundi_caption_sidecar 0.25,0.45,0.30"},
 "script": "lumi/sbatch/fullft_suomi_warm.sbatch", "kim_feedback": null}
META

srun --nodes=1 --ntasks=1 --cpus-per-task=56 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
echo "[suomift] container up $(date -Is)"
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/stable-audio-tools:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-suomift MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-suomift
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2
export TRITON_CACHE_DIR=/tmp/triton-suomift PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-suomift /tmp/triton-suomift; mkdir -p /tmp/miopen-suomift /tmp/triton-suomift
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536
torchrun --standalone --nnodes=1 --nproc-per-node=8 \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --full-finetune --base_precision bf16 \
  --init_state_ckpt '"${INIT}"' \
  --optimizer fusion --lr '"${LR}"' --weight_decay 0.2 \
  --fusion-decay cosine --fusion-snr row \
  --warmup-frac 0.0078 \
  --use-ema \
  --subspace-loss-basis '"${BASIS}"' --subspace-loss-weight '"${K}"' \
  --encoded_dir ${FLASH}/'"${DIR}"' \
  --caption_sidecar '"${SIDE}"' --caption_probs "0.25,0.45,0.30" \
  --frames 1024 --batch_size '"${BS}"' --accumulate_grad_batches '"${GA}"' \
  --num_workers 4 --seed '"${SEED}"' \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs 4 \
  --no_demos --logger csv --name '"${NAME}"' \
  --save_dir '"${RUN}"' \
  2>&1
'
rc=$?
echo "[suomift] srun rc=${rc}; ckpts: $(ls ${RUN}/*.ckpt 2>/dev/null | wc -l)"
grep -h "LOCAL_RANK" ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out 2>/dev/null | sort | uniq -c | head -10
exit ${rc}
