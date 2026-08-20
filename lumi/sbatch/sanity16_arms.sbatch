#!/bin/bash
# sanity16_arms.sbatch — CONTINUITY 2026-08-18, Kim direct:
#   "we need to make a sanity test: T256, 1e-4 (Zach said he uses it these days) LoRA, rank 16, as
#    bread and butter the trainer comes from Stability. 60 epochs. Each set (goa, big goa, avp, avp
#    aug, suomisoundi) alone, and big goa + suomisoundi, big + suomi + avp aug and suomisoundi +
#    avp, each on 1 gpu."  + "Also DoRA of the same setup, but without the 8x lone".
#
# WHY THIS EXISTS. Every recent arm has ridden on something of ours — FusionOpt, spectral WD, Adagc,
# forced weight norm, DoRA at s=1, fp32. When many of them come out broken at once, none of those can
# be cleared, because no run in the campaign is a control. This is the control: the STOCK Stability
# path (plain LoRA, AdamW, rank 16, lr 1e-4, T256) held fixed while ONLY the dataset varies. If these
# come out fine, the corpora are fine and the fault is in our additions. If these come out broken
# too, the fault is upstream of everything we built, and the dataset axis tells us which corpus.
#
# 🔴 WHAT THIS RUN DELIBERATELY DOES NOT USE, because the point is to be boring:
#   no FusionOpt (--optimizer adamw, the train_lora.py default and torch's own AdamW)
#   no spectral WD, no Adagc, no forced weight norm, no hyperball
#   no EMA — it is force-disabled for adapters by UPSTREAM Stability code
#     (stable_audio_3/training/diffusion.py:80, "Don't use EMA with LoRA", present at the 2026-05-21
#      merge-base, verified — not something we switched off)
#
# ⚠️ CONSTANT LR IS UNAVOIDABLE HERE AND IT MATTERS FOR READING THE RESULT (C, 2026-08-18).
#   train_lora.py never sets optimizer_configs['diffusion']['scheduler'], and upstream's
#   configure_optimizers only builds a scheduler when that key exists — so every run we have ever
#   done trains at constant LR. FusionOpt hides this because it carries its own loss-driven Polyak
#   step size (γ_t = γ_base·clamp(loss_ema/gnorm_ema), set via opt.set_loss()); plain AdamW has NO
#   such damping and its update is ~lr per coordinate regardless of gradient magnitude, so at
#   constant LR it takes identically-sized steps forever. Measured consequence on the one AdamW
#   sweep we have (adamw_bf16_sweep, 6 runs): path efficiency 0.31-0.39 and peak velocity at the
#   FINAL epoch, against 0.65-0.75 and decaying velocity for all 19 non-AdamW runs. So expect these
#   arms to wander, and JUDGE THEM BY THE SOUPED/CENTROID CHECKPOINT, not by the last one
#   (control/sa3_control/make_soup.py; each trajectory json names its own soup-center).
#   This is not a reason to skip the test — a wandering control is still a control, and every arm
#   here wanders identically — but reading only the terminal checkpoint would be reading noise.
#
# RUN:
#   ADAPTER=lora sbatch lumi/sbatch/sanity16_arms.sbatch
#   ADAPTER=dora sbatch lumi/sbatch/sanity16_arms.sbatch
#   ARMS="suomi biggoa" ADAPTER=lora sbatch ...        # subset
#   SMOKE=1 ADAPTER=lora sbatch --time=00:30:00 ...    # 20 steps per arm, proves the wiring
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=sanity16
#SBATCH --output=%x-%j.out

set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

ADAPTER=${ADAPTER:?set ADAPTER=lora or ADAPTER=dora}
case "${ADAPTER}" in
  lora) ADAPTER_ARG="--adapter_type lora" ;;
  dora) ADAPTER_ARG="--adapter_type dora-rows" ;;
  *) echo "[sanity] FATAL: ADAPTER must be lora|dora"; exit 1 ;;
esac

RANK=${RANK:-16}
ALPHA=${ALPHA:-16}          # alpha = rank (s=1), the MASTER convention
LR=${LR:-1e-4}              # Zach's current working point
FRAMES=${FRAMES:-256}
EPOCHS=${EPOCHS:-60}
BS=${BS:-8}
CKEVERY=${CKEVERY:-2}       # every 2 epochs: the deadline WILL truncate the big-corpus arms, and a
                            # truncated run is only a wasted run if it checkpointed too sparsely
SMOKE=${SMOKE:-0}
RUNROOT=${RUNROOT:-${SCRATCH}/runs/sanity16_${ADAPTER}}

# ── dataset registry ────────────────────────────────────────────────────────────────────────────
# name | latent dirs (comma-sep, under $SCRATCH) | sidecars (comma-sep, aligned 1:1 with the dirs)
# Aligned 1:1 ON PURPOSE: train_lora.py pairs --encoded_dir and --caption_sidecar positionally, so a
# mismatched count silently pairs the wrong sidecar with the wrong corpus and every caption misses.
SIDE_AVP=${SIDE_AVP:-${CODE}/lumi/avp_captions_tiered.json}
SIDE_SUOMI=${SIDE_SUOMI:-${CODE}/lumi/suomisoundi_caption_sidecar.json}
SIDE_BIGGOA=${SIDE_BIGGOA:-${CODE}/lumi/goa_bigset_hinted_bylatent.json}
SIDE_GOA=${SIDE_GOA:-}      # intentionally EMPTY — see the goa arm's guard below

declare -A DSET_DIRS DSET_SIDE
DSET_DIRS[goa]="latents_sa3"                                    ; DSET_SIDE[goa]="${SIDE_GOA}"
DSET_DIRS[biggoa]="latents_goa_bigset"                          ; DSET_SIDE[biggoa]="${SIDE_BIGGOA}"
DSET_DIRS[avpaug]="latents_avp"                                 ; DSET_SIDE[avpaug]="${SIDE_AVP}"
DSET_DIRS[avp]="latents_avp"                                    ; DSET_SIDE[avp]="${SIDE_AVP}"
DSET_DIRS[suomi]="suomisoundi_latents"                          ; DSET_SIDE[suomi]="${SIDE_SUOMI}"
DSET_DIRS[biggoa_suomi]="latents_goa_bigset,suomisoundi_latents"; DSET_SIDE[biggoa_suomi]="${SIDE_BIGGOA},${SIDE_SUOMI}"
DSET_DIRS[biggoa_suomi_avpaug]="latents_goa_bigset,suomisoundi_latents,latents_avp"
DSET_SIDE[biggoa_suomi_avpaug]="${SIDE_BIGGOA},${SIDE_SUOMI},${SIDE_AVP}"
DSET_DIRS[suomi_avp]="suomisoundi_latents,latents_avp"          ; DSET_SIDE[suomi_avp]="${SIDE_SUOMI},${SIDE_AVP}"

ARMS=${ARMS:-"goa biggoa avp avpaug suomi biggoa_suomi biggoa_suomi_avpaug suomi_avp"}
read -ra ARM_LIST <<< "${ARMS}"

[ -n "${SIF}" ] || { echo "[sanity] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[sanity] FATAL: ${VENV} missing"; exit 1; }
mkdir -p "${RUNROOT}"

# ── WALL-CLOCK vs WORKLOAD GUARD ────────────────────────────────────────────────────────────────
# SMOKE=1 is an env-var prefix on the submit line, and a prefix that gets lost in a copy-paste turns
# a 20-step smoke into a 60-epoch run under whatever --time was meant for the smoke. That happened
# THREE times on 2026-08-18, and each time the symptom arrived ~40 minutes later as a TIMEOUT, which
# also silently voids any --dependency=afterok chain hanging off this job. The mismatch is knowable
# at startup, so it should be fatal at startup.
TLIM_MIN=$(squeue -h -j "${SLURM_JOB_ID:-0}" -o "%l" 2>/dev/null | awk -F'[-:]' '
  NF==4 {print $1*1440 + $2*60 + $3; next}     # D-HH:MM:SS
  NF==3 {print $1*60 + $2; next}               # HH:MM:SS
  NF==2 {print $1; next}                       # MM:SS
  {print 0}')
if [ "${SMOKE}" != "1" ] && [ "${TLIM_MIN:-0}" -gt 0 ] && [ "${TLIM_MIN}" -lt 240 ]; then
  echo "[sanity] FATAL: EPOCHS=${EPOCHS} but this job's time limit is only ${TLIM_MIN} min."
  echo "[sanity]   That is a smoke-test time limit on a full-length run -- almost certainly a lost"
  echo "[sanity]   SMOKE=1 on the submit line. Left alone this would TIMEOUT and, if anything is"
  echo "[sanity]   chained to it with --dependency=afterok, silently prevent that work from ever"
  echo "[sanity]   running. Submit with SMOKE=1 for a smoke, or give it --time=24:00:00 for real."
  echo "[sanity]   Override deliberately with ALLOW_SHORT=1 if you truly want a truncated run."
  [ "${ALLOW_SHORT:-0}" = "1" ] || exit 1
fi
echo "[sanity] time limit: ${TLIM_MIN:-unknown} min   SMOKE=${SMOKE}"
echo "[sanity] ADAPTER=${ADAPTER} rank=${RANK} alpha=${ALPHA} lr=${LR} T=${FRAMES} bs=${BS} epochs=${EPOCHS}"
echo "[sanity] optimizer=adamw (stock), no fusion / no spectral-wd / no agc / no fwn / no EMA"
echo "[sanity] runroot=${RUNROOT}"

# ── PREFLIGHT: refuse an arm rather than launch it blind ────────────────────────────────────────
# Eight arms started together fail eight different ways in one log. Every check below exists because
# its failure is otherwise SILENT: a missing latent dir trains on nothing, a missing sidecar trains
# on empty captions, and a key mismatch rejects every sample and surfaces as a RecursionError
# thousands of frames deep (MASTER / lumi-ops §"live-encode gotchas" #3).
GOOD=(); SKIP=()
for A in "${ARM_LIST[@]}"; do
  DIRS="${DSET_DIRS[$A]:-}"; SIDES="${DSET_SIDE[$A]:-}"
  if [ -z "${DIRS}" ]; then SKIP+=("${A}: unknown arm name"); continue; fi
  if [ -z "${SIDES//,/}" ]; then
    SKIP+=("${A}: NO SIDECAR CONFIGURED -- see the goa note; set SIDE_GOA=... to enable"); continue
  fi
  IFS=',' read -ra DD <<< "${DIRS}"; IFS=',' read -ra SS <<< "${SIDES}"
  if [ "${#DD[@]}" -ne "${#SS[@]}" ]; then
    SKIP+=("${A}: ${#DD[@]} latent dir(s) but ${#SS[@]} sidecar(s) -- positional pairing would misalign"); continue
  fi
  BAD=""
  for d in "${DD[@]}"; do
    N=$(ls "${SCRATCH}/${d}"/*.npy 2>/dev/null | head -1)
    [ -n "${N}" ] || BAD="${BAD} missing-or-empty:${d}"
  done
  for s in "${SS[@]}"; do [ -f "${s}" ] || BAD="${BAD} missing-sidecar:$(basename ${s})"; done
  if [ -n "${BAD}" ]; then SKIP+=("${A}:${BAD}"); else GOOD+=("${A}"); fi
done

echo "[sanity] arms READY (${#GOOD[@]}): ${GOOD[*]:-none}"
if [ "${#SKIP[@]}" -gt 0 ]; then
  echo "[sanity] arms SKIPPED (${#SKIP[@]}):"
  for s in "${SKIP[@]}"; do echo "[sanity]   ${s}"; done
fi
[ "${#GOOD[@]}" -gt 0 ] || { echo "[sanity] FATAL: nothing runnable"; exit 1; }
[ "${#GOOD[@]}" -le 8 ] || { echo "[sanity] FATAL: ${#GOOD[@]} arms > 8 GCDs"; exit 1; }

# ── stage latents to /flash once, shared by all arms ────────────────────────────────────────────
ALL_DIRS=$(for A in "${GOOD[@]}"; do echo "${DSET_DIRS[$A]}" | tr ',' '\n'; done | sort -u)
for d in ${ALL_DIRS}; do
  if [ ! -d "${FLASH}/${d}" ]; then
    echo "[sanity] staging ${d} -> ${FLASH}"
    mkdir -p "${FLASH}/${d}"
    cp "${SCRATCH}/${d}"/*.npy "${SCRATCH}/${d}"/*.json "${FLASH}/${d}/" 2>/dev/null || true
  fi
  echo "[sanity]   ${d}: $(ls ${FLASH}/${d}/*.npy 2>/dev/null | wc -l) latents on flash"
done

run_arm() {
  local NAME=$1 GCD=$2
  local RUN=${RUNROOT}/${NAME}
  local PORT=$((29500 + GCD))
  mkdir -p "${RUN}"
  local DIRS_ARG="" SIDE_ARG=""
  IFS=',' read -ra DD <<< "${DSET_DIRS[$NAME]}"
  for d in "${DD[@]}"; do DIRS_ARG="${DIRS_ARG:+${DIRS_ARG},}${FLASH}/${d}"; done
  SIDE_ARG="${DSET_SIDE[$NAME]}"

  cat > "${RUN}/run_meta.json" <<META
{
  "run": "sanity16_${ADAPTER}_${NAME}",
  "created": "$(date -Iseconds)",
  "slurm_job": "${SLURM_JOB_ID:-unset}",
  "purpose": "CONTROL ARM. Stock Stability training path (plain ${ADAPTER}, AdamW, rank ${RANK}, lr ${LR}, T${FRAMES}) with the DATASET as the only variable, to determine whether recent widespread model failures come from our additions (FusionOpt / spectral WD / Adagc / forced weight norm / fp32 / s=1 adapters) or from the corpora themselves.",
  "hypothesis": "If the stock path trains cleanly on a corpus, that corpus is exonerated and the fault is in our stack. If it fails on the same corpora our arms failed on, the fault is in the data.",
  "dataset": {"name": "${NAME}", "latents": "${DSET_DIRS[$NAME]}", "pre_encoded": true,
              "caption_sidecar": "${SIDE_ARG}"},
  "recipe": {"adapter": "${ADAPTER}", "rank": ${RANK}, "alpha": ${ALPHA}, "lr": "${LR}",
             "batch_size": ${BS}, "gpus": 1, "frames": ${FRAMES}, "epochs": ${EPOCHS},
             "optimizer": "adamw", "precision": "bf16", "lr_schedule": "NONE (constant)",
             "ema": "force-disabled upstream for adapters"},
  "known_gaps": ["Constant LR with plain AdamW does not converge -- judge by the souped/centroid checkpoint, not the terminal one. See the header."],
  "script": "lumi/sbatch/sanity16_arms.sbatch",
  "result": null,
  "kim_feedback": null
}
META

  local STEP_ARGS="--epochs ${EPOCHS}"
  [ "${SMOKE}" = "1" ] && STEP_ARGS="--steps 20"

  srun --overlap --nodes=1 --ntasks=1 --cpus-per-task=6 \
    singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
# overlay FIRST so it shadows the image venv, AND append the inherited path so the image own
# /opt/venv (where torch lives) survives -- both halves are load-bearing (lumi-ops §containers)
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/stable-audio-tools:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export ROCR_VISIBLE_DEVICES='"${GCD}"'      # ROCR only; never also HIP_VISIBLE_DEVICES (they stack)
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=6 MKL_NUM_THREADS=6
# N INDEPENDENT single-GCD arms in ONE job: Lightning derives one rendezvous port from the shared
# SLURM_JOB_ID, so arm 0 wins the TCPStore and the other seven die on EADDRINUSE. SLURM_JOB_NAME=bash
# makes SLURMEnvironment.detect() return False -> single-process LightningEnvironment, no shared
# port. Distinct MASTER_PORT is the belt to that braces. (lumi-ops, live-encode gotcha #2.)
export SLURM_JOB_NAME=bash
export MASTER_PORT='"${PORT}"'
export MIOPEN_USER_DB_PATH=/tmp/miopen-'"${GCD}"' MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-'"${GCD}"'
export TRITON_CACHE_DIR=/tmp/triton-'"${GCD}"' PYTORCH_TUNABLEOP_ENABLED=0
mkdir -p /tmp/miopen-'"${GCD}"' /tmp/triton-'"${GCD}"'
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
python ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --base_precision bf16 \
  '"${ADAPTER_ARG}"' --rank '"${RANK}"' --lora_alpha '"${ALPHA}"' \
  --optimizer adamw --lr '"${LR}"' \
  --encoded_dir '"${DIRS_ARG}"' --caption_sidecar '"${SIDE_ARG}"' \
  --frames '"${FRAMES}"' --batch_size '"${BS}"' --num_workers 4 --no_demos \
  '"${STEP_ARGS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  --save_dir '"${RUN}"' \
  2>&1 | sed "s/^/['"${NAME}"'] /"
' &
}

# Collect PIDs so each arm's EXIT STATUS is checked individually. A bare `wait` returns the status
# of the last job only, so this script used to exit 0 even if every arm had crashed -- which makes an
# `--dependency=afterok` gate on it worthless in BOTH directions: a total failure would look like
# success and launch the dependents anyway. If this job is being used as a smoke gate, its exit code
# is the entire point.
PIDS=(); NAMES=()
i=0
for A in "${GOOD[@]}"; do
  echo "[sanity] launching ${A} on GCD ${i}"
  run_arm "${A}" "${i}"
  PIDS+=($!); NAMES+=("${A}")
  i=$((i+1))
  sleep 5      # stagger model load; 8 simultaneous HF loads off one Lustre dir is a thundering herd
done

NFAIL=0
for k in "${!PIDS[@]}"; do
  if wait "${PIDS[$k]}"; then
    echo "[sanity] arm OK      ${NAMES[$k]}"
  else
    echo "[sanity] arm FAILED  ${NAMES[$k]} (rc=$?)"
    NFAIL=$((NFAIL+1))
  fi
done
echo "[sanity] all ${#GOOD[@]} arm(s) finished; ${NFAIL} failed"
for A in "${GOOD[@]}"; do
  echo "[sanity]   ${A}: $(ls ${RUNROOT}/${A}/*.ckpt 2>/dev/null | wc -l) checkpoint(s)"
done
# NB checkpoint COUNT is deliberately not the pass criterion: SMOKE=1 runs 20 steps, which is fewer
# than CKEVERY=2 epochs, so a perfectly healthy smoke legitimately writes zero checkpoints. Exit
# status is the criterion.
if [ "${NFAIL}" -gt 0 ]; then
  echo "[sanity] EXIT 1 -- ${NFAIL} arm(s) failed. Any --dependency=afterok job will correctly NOT run."
  exit 1
fi
echo "[sanity] NEXT: trajectory stats on these (PAR=2), then soup the centroid -- do NOT judge"
echo "[sanity]   these by the terminal checkpoint, constant-LR AdamW does not settle."
