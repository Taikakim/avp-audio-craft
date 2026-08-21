#!/bin/bash
# pianoroll_fullft.sbatch — T256 FULL FINE-TUNE conditioned on a MuScriptor piano roll
# (Kim direct 2026-08-21: "t256 full fine tune with a 256x128 matrix for notes as a
# conditioner on its own lane, sample matched, stretched to clip length, from the
# muscriptor midis"). The notes lane: (128, T) velocity roll -> B7's modular local-cond
# inlet (zero-init per-frame additive projections, blocks 12-23) on a FULL fine-tune
# (no lora_config -> the freeze-out bug class structurally absent). AdamW + WSD knee 25%.
# The in-training control-ablation meter rides along: control_gain > 0 in the log = the
# model demonstrably uses the NOTES. goa corpus (muscriptor ids), torchrun true DDP.
# RUN: sbatch lumi/sbatch/pianoroll_fullft.sbatch          (SEED=2 for a pair)
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=proll_fullft
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
SEED=${SEED:-1}
BS=${BS:-4}
GA=${GA:-2}
EPOCHS=${EPOCHS:-16}
NAME=proll_fullft_t256_bf16_s${SEED}
RUN=${SCRATCH}/runs/pianoroll_fullft/${NAME}
echo "[proll] CONFIG ${NAME} node=$(hostname) $(date -Is)"
[ -f "${SCRATCH}/latents_sa3_proll/000003.ctrl.npy" ] || { echo "[proll] FATAL: proll sidecars not rsynced (stat-probe)"; exit 1; }
[ -f "${FLASH}/latents_sa3/000003.npy" ] || { echo "[proll] FATAL: flash latents missing"; exit 1; }
grep -q '"pianoroll"' ${CODE}/stable-audio-3/scripts/mir_control.py || { echo "[proll] FATAL: mir_control stale (no pianoroll pack)"; exit 1; }
# proll sidecars live on scratch; the wrapper resolves <latent_dir>_proll, so link scratch dir next to flash latents
[ -e "${FLASH}/latents_sa3_proll" ] || ln -s ${SCRATCH}/latents_sa3_proll ${FLASH}/latents_sa3_proll 2>/dev/null || true
echo "[proll] preflight passed"
mkdir -p "${RUN}"
cat > "${RUN}/run_meta.json" <<META
{"run": "${NAME}", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "Kim direct 2026-08-21: NOTES LANE — T256 full-FT conditioned on the MuScriptor piano roll (128ch velocity/64 at latent rate, crop-sliced) via the modular local-cond inlet. control_gain in control_ablation.jsonl = does the model use the notes.",
 "recipe": {"mode": "FULL fine-tune", "optimizer": "adamw + WSD knee 25%", "lr": "1e-4", "precision": "bf16",
            "frames": 256, "batch_per_rank": ${BS}, "grad_accum": ${GA}, "gpus": 8, "ddp": "torchrun",
            "effective_batch": $((BS*GA*8)), "epochs": ${EPOCHS}, "seed": ${SEED}, "ema": true,
            "mir_ctrl": {"pack": "pianoroll", "channels": 128, "blocks": "12-23", "dropout": 0.2}},
 "dataset": {"name": "goa latents_sa3 (muscriptor ids)", "caption": "goa_longform_sidecar 0.6,0.3,0.1"},
 "script": "lumi/sbatch/pianoroll_fullft.sbatch", "kim_feedback": null}
META
srun --nodes=1 --ntasks=1 --cpus-per-task=56 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
echo "[proll] container up $(date -Is)"
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/stable-audio-tools:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-proll MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-proll
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2
export TRITON_CACHE_DIR=/tmp/triton-proll PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-proll /tmp/triton-proll; mkdir -p /tmp/miopen-proll /tmp/triton-proll
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536
torchrun --standalone --nnodes=1 --nproc-per-node=8 \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --full-finetune --base_precision bf16 \
  --optimizer adamw --lr 1e-4 --lr_schedule wsd \
  --use-ema \
  --encoded_dir ${FLASH}/latents_sa3 \
  --caption_sidecar ${CODE}/lumi/goa_longform_sidecar.json --caption_probs "0.6,0.3,0.1" \
  --mir_ctrl_pack pianoroll --mir_ctrl_source ctrl --mir_ctrl_blocks 12-23 \
  --mir_ctrl_dropout 0.2 --mir_ctrl_ablation_every 200 \
  --frames 256 --batch_size '"${BS}"' --accumulate_grad_batches '"${GA}"' \
  --num_workers 4 --seed '"${SEED}"' --warmup-frac 0.0078 \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs 2 \
  --no_demos --logger csv --name '"${NAME}"' \
  --save_dir '"${RUN}"' \
  2>&1
'
rc=$?
echo "[proll] srun rc=${rc}; ckpts: $(ls ${RUN}/*.ckpt 2>/dev/null | wc -l)"
grep -h "LOCAL_RANK" ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out 2>/dev/null | sort | uniq -c | head -10
exit ${rc}
