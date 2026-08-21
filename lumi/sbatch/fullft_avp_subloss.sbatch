#!/bin/bash
# fullft_avp_subloss.sbatch — Kim direct 2026-08-22 (~03:00), "let one run roll on alone":
# AVP, T1024, lr 2.5e-5, FULL-FT, AdamW (wd at default), subspace-loss weighting in, schedule
# flat until ep10 then cosine, to ep64. "This one has a very mellow LR and some nice controls
# that have been helpful."
#
# THREE THINGS RESOLVED BEFORE WRITING THIS, all of which changed the spec:
#  1. ADAGC IS NOT IMPLEMENTED. No flag, no code, anywhere in the trainer or optimizer. It exists
#     for us only as EXPERIMENTS E2, a PLANNED bracket on the LatCH melody head. Dropped -- it
#     would have to be written, not enabled.
#  2. SPECTRAL WD IS FUSIONOPT-ONLY (build_fusion_param_groups -> per-group weight_decay on the 2D
#     DiT matrices). Under --optimizer adamw there is no such path; --weight_decay is plain
#     decoupled AdamW decay. Kim: "AdamW WD can be at default" => omitted entirely (0.01).
#  3. LIVE ENCODE CANNOT DELIVER THE AUGMENTATION KIM WANTS. --augment (live-encode only) covers
#     sub_frame_shift / gain / stereo_width / polarity. PITCH SHIFT AND TIME STRETCH ARE
#     --aug-heavy ONLY, and that path lazily loads torchaudio transforms -- the sox-adjacent thing
#     CLAUDE.md bans in favour of bungee. Kim: "bungee augs will be mandatory, especially the
#     pitch augs". Bungee is OFFLINE (CPU, HyperQueue) by construction, so the ONLY route to
#     bungee pitch augmentation is a PRE-AUGMENTED, PRE-ENCODED latent dir. Hence this trains on
#     latents_avp (the existing avp aug set, 2394 crops) and NOT on a --data_dir live-encode.
#     Kim's own instinct -- "SAMEs encode fast on CPU, could we pre-calculate in parallel?" -- is
#     exactly right and is already built: aug8_encode.sbatch is a two-phase CPU-bungee-then-
#     SAME-L-encode job on one node. It is not a tonight job (its bungee_python-in-container risk
#     is still open, and $SCRATCH/avp_src showed no wav/flac at depth<=3).
#
# CAPTIONS: avp_captions_tiered.json, tiers 0,0.9,0.1 -- AVP granite measured 3.84x rare-term
# recall vs chance, i.e. genuinely grounded (unlike bigset, which must ride 0,0,1).
# ORIG=1 swaps to latents_avp_originals (288 crops, NO augmentation) if the clean set is wanted.
#
# EPOCH MATH (Kim raised this himself): 2394 crops at effective batch 8 = ~299 steps/epoch, so
# ep64 ~= 19k steps with the knee at ep10 (~3k flat, then cosine to 10% of lr over ~16k). On the
# 288-crop ORIG set it is 36 steps/epoch and ep64 is only ~2.3k steps -- raise EPOCHS there.
#
# ⚠ DISK: full-FT fats are ~31 GB EACH (not the ~2 GB an adapter run writes). CKEVERY=8 => 8 rungs
# => ~250 GB. Do NOT drop CKEVERY to 4 here without checking scratch free space first; 16 rungs is
# ~500 GB and would fill scratch under an active pull.
#
# RUN: sbatch lumi/sbatch/fullft_avp_subloss.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=fullft_avp_subloss
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

ORIG=${ORIG:-0}
DIR=$([ "${ORIG}" = "1" ] && echo latents_avp_originals || echo latents_avp)
BS=${BS:-1}
GA=${GA:-1}
LR=${LR:-2.5e-5}
SEED=${SEED:-1}
EPOCHS=${EPOCHS:-64}
KNEE=${KNEE:-10}
CKEVERY=${CKEVERY:-8}
SUBW=${SUBW:-5}
BASIS=${BASIS:-${CODE}/lumi/melody_subspace15_selective_v3.npz}
SIDE=${CODE}/lumi/avp_captions_tiered.json
PROBS=${PROBS:-0,0.9,0.1}

NAME=fullft_avp$([ "${ORIG}" = "1" ] && echo orig)_t1024_bf16_lr25e6_sub${SUBW}v3sel_wsd${KNEE}_bs$((BS*GA*8))_s${SEED}
RUN=${SCRATCH}/runs/fullft_avp_subloss/${NAME}

[ -n "${SIF}" ] || { echo "[fas] FATAL: no multitorch image"; exit 1; }
[ -d "${VENV}" ] || { echo "[fas] FATAL: no train venv at ${VENV}"; exit 1; }
[ -f "${BASIS}" ] || { echo "[fas] FATAL: subspace basis missing: ${BASIS}"; exit 1; }
[ -f "${SIDE}" ]  || { echo "[fas] FATAL: caption sidecar missing"; exit 1; }

# staging (locked; shares latents_avp with the A12 arms)
if [ "$(ls ${FLASH}/${DIR}/*.npy 2>/dev/null | wc -l)" -eq 0 ]; then
  L=${FLASH}/.stage_${DIR}.lock
  if mkdir "${L}" 2>/dev/null; then
    echo "[fas] staging ${DIR} -> flash (lock held)"
    mkdir -p "${FLASH}/${DIR}"
    if [ -f "${SCRATCH}/${DIR}.tar.gz" ]; then
      tar -xzf "${SCRATCH}/${DIR}.tar.gz" -C "${FLASH}/${DIR}" --strip-components=1
    else
      cp ${SCRATCH}/${DIR}/*.npy "${FLASH}/${DIR}/" 2>/dev/null
    fi
    cp ${SCRATCH}/${DIR}/*.json "${FLASH}/${DIR}/" 2>/dev/null || true
    rmdir "${L}"
  else
    echo "[fas] another job is staging ${DIR}; waiting"
    while [ -d "${L}" ]; do sleep 20; done
  fi
fi
N=$(ls ${FLASH}/${DIR}/*.npy 2>/dev/null | wc -l)
NJ=$(ls ${FLASH}/${DIR}/*.json 2>/dev/null | wc -l)
[ "${N}" -gt 0 ] && [ "${NJ}" -gt 0 ] || { echo "[fas] FATAL: ${DIR} staged empty (${N} npy / ${NJ} json)"; exit 1; }
SPE=$((N/(BS*GA*8)))
echo "[fas] NAME=${NAME} dir=${DIR} crops=${N} eff_batch=$((BS*GA*8)) steps/epoch~${SPE} epochs=${EPOCHS} (~$((SPE*EPOCHS)) steps) knee=ep${KNEE} lr=${LR} subspace=${SUBW}"

mkdir -p "${RUN}"
cat > "${RUN}/run_meta.json" <<META
{"run": "${NAME}", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "Kim direct 2026-08-22 'let one run roll on alone': mellow-LR full-FT on AVP at T1024 with the controls that have helped -- subspace-loss weighting and a flat-then-cosine schedule.",
 "recipe": {"full_finetune": true, "optimizer": "adamw (wd at default 0.01)", "lr": "${LR}",
            "lr_schedule": "wsd: warmup 0.78% -> flat to ep${KNEE} -> cosine to 10%",
            "precision": "bf16", "frames": 1024, "beat_aware_crop": true,
            "subspace_loss_weight": ${SUBW}, "subspace_loss_basis": "melody_subspace15_selective_v3.npz",
            "batch_per_rank": ${BS}, "gpus": 8, "effective_batch": $((BS*GA*8)),
            "ddp": "torchrun --standalone (verified pattern)", "epochs": ${EPOCHS}, "seed": ${SEED}},
 "dropped_from_the_ask": {"adagc": "NOT IMPLEMENTED in this trainer (EXPERIMENTS E2 is a planned LatCH-head bracket, not a DiT feature)",
                          "spectral_wd_0.02": "spectral_wd is FusionOpt-only; under adamw --weight_decay is plain decoupled decay. Kim: leave at default.",
                          "live_encode_with_augmentation": "--augment covers phase/gain/width/polarity only; pitch+stretch are --aug-heavy = the banned torchaudio path. Bungee pitch augs are offline-only, so a pre-augmented latent dir is the ONLY route."},
 "dataset": {"dir": "${DIR}", "crops": ${N}, "sidecar": "avp_captions_tiered.json", "caption_probs": "${PROBS}",
             "caption_note": "AVP granite measured 3.84x rare-term recall vs chance = grounded"},
 "script": "lumi/sbatch/fullft_avp_subloss.sbatch", "result": null, "kim_feedback": null}
META

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
export MIOPEN_USER_DB_PATH=/tmp/miopen-fas MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-fas
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2
export TRITON_CACHE_DIR=/tmp/triton-fas PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-fas /tmp/triton-fas; mkdir -p /tmp/miopen-fas /tmp/triton-fas
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536
torchrun --standalone --nnodes=1 --nproc-per-node=8 \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --base_precision bf16 --full-finetune \
  --optimizer adamw --lr '"${LR}"' \
  --lr_schedule wsd --lr_knee_epoch '"${KNEE}"' --warmup-frac 0.0078 \
  --subspace-loss-weight '"${SUBW}"' --subspace-loss-basis '"${BASIS}"' \
  --encoded_dir ${FLASH}/'"${DIR}"' --caption_sidecar '"${SIDE}"' --caption_probs "'"${PROBS}"'" \
  --frames 1024 --beat-aware-crop \
  --batch_size '"${BS}"' --accumulate_grad_batches '"${GA}"' \
  --num_workers 6 --seed '"${SEED}"' \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  --no_demos --logger csv --name '"${NAME}"' \
  --save_dir '"${RUN}"' \
  2>&1
'
rc=$?
echo "[fas] srun rc=${rc}; ckpts: $(ls ${RUN}/*.ckpt 2>/dev/null | wc -l)"
grep -h "LOCAL_RANK" ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out 2>/dev/null | sort | uniq -c | head -10
exit ${rc}
