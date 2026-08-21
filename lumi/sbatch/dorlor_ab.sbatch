#!/bin/bash
# dorlor_ab.sbatch — Kim direct 2026-08-21: "DoRA vs LoRA, goa big set, batch 8 GA 2 (or 16
# direct if VRAM suffices), t256, bf16, lr 1e-4, AdamW and Fusion, warmup 1/4 epoch, LR to
# cosine at a knee ~ep8, Fusion with ALL damping fixes, rank 128, 4 nodes x 8 GPUs, 32 epochs.
# I'm mystified why we are getting so bad results now again."
#
# THE DIAGNOSTIC A/B^2: adapter (DoRA-rows vs plain LoRA) x optimizer (AdamW-WSD vs braked
# Fusion), everything else pinned at the healthiest known settings: TRUE 8-way DDP (torchrun),
# bf16 (=> FA2 on multitorch), T256, per-rank batch 16 default (W's monotonic batch finding;
# BS=8 GA=2 fallback knob), rank 128 alpha 45 (ratified winning value; ALPHA=128 to replicate
# the healthy bf16cmp twins instead), 32 epochs, ckpt every 2.
#   - AdamW arms: --lr_schedule wsd (warmup 0.25 ep -> flat -> cosine from ep8) — the FIRST
#     scheduled-AdamW runs in the campaign (every prior AdamW run was constant-LR: A2 walk).
#   - Fusion arms: --fusion-decay wsd (flat until 25% = ep8, then decay) + --fusion-snr row —
#     the full damping kit from the A-series.
# CORPUS CAVEAT recorded up front: bigset is 27.7% near-lossless vs old goa 75.9% (W audit) —
# if all four arms land mediocre-but-healthy, suspect the corpus before the optimizers.
#
# RUN (4 jobs):
#   ARM=dora_adamw  sbatch lumi/sbatch/dorlor_ab.sbatch
#   ARM=dora_fusion sbatch lumi/sbatch/dorlor_ab.sbatch
#   ARM=lora_adamw  sbatch lumi/sbatch/dorlor_ab.sbatch
#   ARM=lora_fusion sbatch lumi/sbatch/dorlor_ab.sbatch
# VERIFY (per job, within minutes): LOCAL_RANK 0..7 once each; steps/epoch ~ 12524/(16*8)=97
#   (or /(8*2*8)=97 with the fallback knobs — same optimizer-step count); ckpts UN-versioned;
#   AdamW arms print "[lr] WSD: ..." and Fusion arms "[fusion] decay: wsd ...".
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=dorlor_ab
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

ARM=${ARM:?set ARM=dora_adamw|dora_fusion|lora_adamw|lora_fusion}
DATASET=${DATASET:-biggoa}      # biggoa | suomi | avpaug | goa (old set, latents_sa3)
BS=${BS:-16}
GA=${GA:-1}
RANK=${RANK:-128}
ALPHA=${ALPHA:-45}
LR=${LR:-1e-4}
SEED=${SEED:-1}
# EPOCH SCALING (Kim extended to all corpora 2026-08-21): epochs default so every corpus gets
# ~3,100 optimizer steps at eff batch 128 (bigset's 32-ep budget); ckpt cadence -> ~10 ladders.
# Knee stays at 25% of the run; warmup fixed at 0.78% of total steps (bigset's 0.25 ep).
case "${DATASET}" in
  biggoa) DIRS="latents_goa_bigset";  SIDES="${CODE}/lumi/goa_bigset_hinted_bylatent.json"; PROBS="0,0,1";           EPD=32;  CKD=2 ;;
  suomi)  DIRS="suomisoundi_latents"; SIDES="${CODE}/lumi/suomisoundi_caption_sidecar.json"; PROBS="0.25,0.45,0.30"; EPD=320; CKD=32 ;;
  avpaug) DIRS="latents_avp";         SIDES="${CODE}/lumi/avp_captions_tiered.json";        PROBS="0,0.9,0.1";       EPD=160; CKD=16 ;;
  goa)    DIRS="latents_sa3";         SIDES="${CODE}/lumi/goa_longform_sidecar.json";       PROBS="0.6,0.3,0.1";     EPD=64;  CKD=8 ;;
  *) echo "[dorlor] FATAL: unknown DATASET ${DATASET}"; exit 1 ;;
esac
EPOCHS=${EPOCHS:-${EPD}}
CKEVERY=${CKEVERY:-${CKD}}
KNEE=${KNEE:-$((EPOCHS / 4))}
WARMUP_FRAC=${WARMUP_FRAC:-0.0078}
case "${ARM}" in
  dora_adamw)  AD=dora-rows; OPT=adamw ;;
  dora_fusion) AD=dora-rows; OPT=fusion ;;
  lora_adamw)  AD=lora;      OPT=adamw ;;
  lora_fusion) AD=lora;      OPT=fusion ;;
  *) echo "[dorlor] FATAL: bad ARM ${ARM}"; exit 1 ;;
esac
NAME=dorlor_${DATASET}_${ARM}_r${RANK}a${ALPHA}_t256_bf16_bs$((BS*GA*8))_s${SEED}
RUN=${SCRATCH}/runs/dorlor_ab/${NAME}
DIR=${DIRS}
SIDE=${SIDES}

[ -n "${SIF}" ] || { echo "[dorlor] FATAL: no multitorch image"; exit 1; }
[ -f "${SIDE}" ] || { echo "[dorlor] FATAL: sidecar missing"; exit 1; }
grep -q '"WSD"' ${CODE}/stable-audio-3/stable_audio_3/training/utils.py \
  || { echo "[dorlor] FATAL: WSD scheduler not synced"; exit 1; }

# staging with LOCK (fixes the 2026-08-21 stampede: N jobs cp-ing the same flash dir at once)
LOCKDIR=${FLASH}/.stage_${DIR}.lock
if [ "$(ls ${FLASH}/${DIR}/*.npy 2>/dev/null | wc -l)" -eq 0 ]; then
  if mkdir "${LOCKDIR}" 2>/dev/null; then
    echo "[dorlor] staging ${DIR} -> flash (lock held)"
    mkdir -p "${FLASH}/${DIR}"
    cp ${SCRATCH}/${DIR}/*.npy "${FLASH}/${DIR}/" 2>/dev/null
    cp ${SCRATCH}/${DIR}/*.json "${FLASH}/${DIR}/" 2>/dev/null || true
    rmdir "${LOCKDIR}"
  else
    echo "[dorlor] another job is staging ${DIR}; waiting"
    while [ -d "${LOCKDIR}" ]; do sleep 20; done
  fi
fi
N=$(ls ${FLASH}/${DIR}/*.npy 2>/dev/null | wc -l)
[ "${N}" -gt 0 ] || { echo "[dorlor] FATAL: staging failed"; exit 1; }
# json top-up: a dir staged before its jsons existed on scratch skips staging forever
# (stage-if-empty checks npy only); train_lora's dataset REQUIRES the .json metas.
if [ "$(ls ${FLASH}/${DIR}/*.json 2>/dev/null | wc -l)" -eq 0 ]; then
  cp ${SCRATCH}/${DIR}/*.json "${FLASH}/${DIR}/" 2>/dev/null || true
fi
NJ=$(ls ${FLASH}/${DIR}/*.json 2>/dev/null | wc -l)
[ "${NJ}" -gt 0 ] || { echo "[dorlor] FATAL: no .json metas for ${DIR} on flash OR scratch — rsync them from local first (train_lora requires them)"; exit 1; }
echo "[dorlor] ${DIR}: ${N} latents, ${NJ} json metas on flash"

mkdir -p "${RUN}"
echo "[dorlor] CONFIG NAME=${NAME} AD=${AD} OPT=${OPT} BS=${BS}/rank GA=${GA} (eff $((BS*GA*8))) LR=${LR} KNEE=ep${KNEE} EPOCHS=${EPOCHS}"
cat > "${RUN}/run_meta.json" <<META
{"run": "${NAME}", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "Kim direct 2026-08-21 ('mystified why so bad now'): adapter x optimizer A/B^2 on bigset at healthy settings — DoRA/LoRA x AdamW-WSD/braked-Fusion, true DDP, big batch, T256 bf16.",
 "recipe": {"adapter": "${AD}", "rank": ${RANK}, "alpha": ${ALPHA}, "optimizer": "${OPT}",
            "lr": "${LR}", "lr_schedule": "wsd knee ep${KNEE} (adamw) / fusion-decay wsd + snr row/grad-source (fusion)",
            "warmup": "0.25 epoch", "precision": "bf16 (FA2)", "frames": 256,
            "batch_per_rank": ${BS}, "grad_accum": ${GA}, "gpus": 8, "ddp": "torchrun (verified pattern)",
            "effective_batch": $((BS*GA*8)), "epochs": ${EPOCHS}, "seed": ${SEED}},
 "dataset": {"name": "${DATASET}", "dirs": "${DIRS}", "caption_probs": "${PROBS}",
             "caveat": "bigset 27.7% near-lossless vs old goa 75.9% (W audit) — corpus is a suspect in any uniform mediocrity"},
 "script": "lumi/sbatch/dorlor_ab.sbatch", "result": null, "kim_feedback": null}
META

OPTARGS=""
if [ "${OPT}" = "adamw" ]; then
  OPTARGS="--lr_schedule wsd --lr_knee_epoch ${KNEE}"
else
  OPTARGS="--fusion-decay wsd --fusion-decay-start-frac $(python3 -c "print(${KNEE}/${EPOCHS})") --fusion-snr row"
fi

srun --nodes=1 --ntasks=1 --cpus-per-task=56 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/stable-audio-tools:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-dorlor MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-dorlor
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2
export TRITON_CACHE_DIR=/tmp/triton-dorlor PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-dorlor /tmp/triton-dorlor; mkdir -p /tmp/miopen-dorlor /tmp/triton-dorlor
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536
torchrun --standalone --nnodes=1 --nproc-per-node=8 \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --base_precision bf16 \
  --adapter_type '"${AD}"' --rank '"${RANK}"' --lora_alpha '"${ALPHA}"' \
  --optimizer '"${OPT}"' --lr '"${LR}"' '"${OPTARGS}"' \
  --warmup-frac '"${WARMUP_FRAC}"' \
  --encoded_dir ${FLASH}/'"${DIR}"' --caption_sidecar '"${SIDE}"' --caption_probs "'"${PROBS}"'" \
  --frames 256 --batch_size '"${BS}"' --accumulate_grad_batches '"${GA}"' \
  --num_workers 4 --seed '"${SEED}"' \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  --no_demos --logger csv --name '"${NAME}"' \
  --save_dir '"${RUN}"' \
  2>&1
'
rc=$?
echo "[dorlor] srun rc=${rc}; ckpts: $(ls ${RUN}/*.ckpt 2>/dev/null | wc -l)"
grep -h "LOCAL_RANK" ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out 2>/dev/null | sort | uniq -c | head -10
exit ${rc}
