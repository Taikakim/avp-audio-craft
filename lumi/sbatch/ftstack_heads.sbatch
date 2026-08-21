#!/bin/bash
# ftstack_heads.sbatch — B9: the control stack retrained ON TOP of our best FULL FINETUNE
# (CONTINUITY 2026-08-21, Kim direct: "take our best full finetune, and train our FiLM,
# melody and LATCH heads with best known values and Fusion on top of that instead of the
# base model").
#
# 8 single-GCD arms on one node:
#   r0  Head-B FiLM (melody_contour) on the FULL-FT backbone   <- the backbone-dependent piece
#   r1  Head-B FiLM on medium-base                             <- matched control (same seed)
#   r2  f0_other melody head   r3  f0_bass melody head         <- D3 best values (EMA 0.999,
#   r4  hpcp                   r5  rms_energy_bass                 val split BY SOURCE TRACK)
#   r6  onset_envelope         r7  spectral_flatness           <- strongest steering features
# Heads (r2-7) are latent readouts (backbone-free by construction) — retrained here with the
# BEST KNOWN recipe: Fusion SF-NorMuon (ns5,normuon,sf) + adaln_zero + bf16 hot dtype + EMA
# 0.999 + cosine fusion-decay (the braked Fusion — undamped NS5 is the drone mechanism) +
# held-out val split by source_track (83329a8: crop-split leaks sibling crops).
#
# KNOB (required): FT_CKPT=/scratch/.../runs/fullft_fleet/<arm>/epoch=N.ckpt  (FAT ckpt; the
#   EMA shadow weights are loaded — that is what deploys). Candidates, best-first:
#   - today's fullft_fleet arms (AdamW matched controls, EMA on): fullft_avpaug/mix3/suomi/...
#   - fullft_mixed_wdfix (completed, bounded-norm, z0 std 1.134 healthy)
#   - the precision-ladder fp16 arm (Kim's "sound of its own" pick)
#
# PREREQ on LUMI: latents_sa3/*.TIMESERIES.npz co-located with latents (rsync ~3.1G — .npz
#   does NOT collide with the dataset's *.npy glob); ${SCRATCH}/latents_sa3_melody/ (melody8
#   streams, ~10M); code: control/ + stable-audio-3/scripts/latch/ synced.
# RUN:  FT_CKPT=/scratch/.../epoch=N.ckpt sbatch lumi/sbatch/ftstack_heads.sbatch
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=ftstack_heads
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

FT_CKPT=${FT_CKPT:?set FT_CKPT=<path to full-FT fat ckpt on scratch>}
echo "[ftstack] CONFIG FT_CKPT=${FT_CKPT} SEED=${SEED:-1} node=$(hostname) $(date -Is)"
SEED=${SEED:-1}
RUNROOT=${SCRATCH}/runs/ftstack_heads

[ -f "${FT_CKPT}" ] || { echo "[ftstack] FATAL: FT_CKPT not found: ${FT_CKPT}"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[ftstack] FATAL: venv missing"; exit 1; }
[ -d "${SCRATCH}/latents_sa3_melody" ] || { echo "[ftstack] FATAL: latents_sa3_melody missing — rsync melody8 streams"; exit 1; }
# LATENTS FROM FLASH (2026-08-21): scratch latents_sa3 lost its base .npy (Jul-14 tar);
# flash carries the full staged set. PREFLIGHT BY SINGLE-FILE STAT, NOT GLOB: a 5400-file
# glob on flash under concurrent training load took >20 s from a login node (F measured)
# and wedged attempt 3 in the preflight — three stats give the same one-key guarantee
# for three metadata ops. (And the banner below now prints FIRST, so "counting" and
# "wedged" stay distinguishable — the 8910bb4 lesson, reopened once, closed again.)
LATDIR=${FLASH}/latents_sa3
echo "[ftstack] preflight: stat-probing ${LATDIR} (known stem 000003)"
[ -f "${LATDIR}/000003.npy" ] || { echo "[ftstack] FATAL: base latents missing in ${LATDIR}"; exit 1; }
[ -f "${LATDIR}/000003.TIMESERIES.npz" ] || { echo "[ftstack] FATAL: TIMESERIES npz missing in ${LATDIR}"; exit 1; }
[ -f "${LATDIR}/000003.json" ] || { echo "[ftstack] FATAL: json metas missing in ${LATDIR}"; exit 1; }
grep -q "base-state-ckpt" ${CODE}/control/sa3_control/train.py \
  || { echo "[ftstack] FATAL: control/ code stale (no --base-state-ckpt)"; exit 1; }
[ -f "${CODE}/stable-audio-3/scripts/latch/train_latch.py" ] \
  || { echo "[ftstack] FATAL: latch trainer not synced"; exit 1; }

echo "[ftstack] preflight passed; launching srun (8 single-GCD arms)"
mkdir -p "${RUNROOT}"
cat > "${RUNROOT}/run_meta.json" <<META
{"run": "ftstack_heads", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "B9 (Kim direct 2026-08-21): FiLM/Head-B + melody f0 + LatCH heads retrained with best known values + Fusion, Head-B on the FULL-FT backbone (FT_CKPT EMA weights) vs base control.",
 "ft_ckpt": "${FT_CKPT}", "seed": ${SEED},
 "recipe": {"headb": "melody_contour, fusion, ema 0.999, grad-accum 2, crop 512, val 0.1",
            "heads": "fusion ns5,normuon,sf + adaln_zero + bf16 hot + ema 0.999 + fusion-decay cosine + val-frac 0.15 group-by source_track"},
 "script": "lumi/sbatch/ftstack_heads.sbatch", "result": null, "kim_feedback": null}
META

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
R=${SLURM_PROCID}
echo "[r${R}] rank alive on $(hostname) $(date -Is)"
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/stable-audio-tools:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2
export TRITON_CACHE_DIR=/tmp/triton-${R} PYTORCH_TUNABLEOP_ENABLED=0
mkdir -p /tmp/miopen-${R} /tmp/triton-${R}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
RUNROOT='"${RUNROOT}"'
FT='"${FT_CKPT}"'
SEED='"${SEED}"'
LAT=${FLASH}/latents_sa3

headb () {  # $1 = ft|base
  local TAG=$1 EXTRA=""
  [ "${TAG}" = "ft" ] && EXTRA="--base-state-ckpt ${FT}"
  python -m sa3_control.train \
    --control-mode melody_contour --melody-dir ${SCRATCH}/latents_sa3_melody \
    --model medium-base ${EXTRA} \
    --encoded_dir ${LAT} --crop-frames 512 --random-crop \
    --optimizer fusion --ema 0.999 --grad-accum 2 --batch 4 \
    --max-epochs 12 --val-frac 0.1 --early-stop-patience 4 \
    --seed ${SEED} --run-name headb_${TAG}_s${SEED} \
    --save-dir ${RUNROOT}/headb_${TAG}_s${SEED} \
    2>&1 | sed "s/^/[r${R}:headb-${TAG}] /"
  return ${PIPESTATUS[0]}   # sed launders $? — the 21430195 8-min-COMPLETED lesson
}
head_arm () {  # $1 = feature, extra args in $2...
  local FEAT=$1; shift
  python ${CODE}/stable-audio-3/scripts/latch/train_latch.py \
    --feature ${FEAT} --latent-dir ${LAT} --target-source npz \
    --optimizer fusion --components ns5,normuon,sf --t-injection adaln_zero \
    --hot-dtype bf16 --fusion-decay cosine --ema 0.999 \
    --val-frac 0.15 --val-group-by source_track --val-seed 1234 \
    --epochs 30 --batch-size 32 --seed ${SEED} "$@" \
    --save-dir ${RUNROOT}/latch_${FEAT}_s${SEED} \
    2>&1 | sed "s/^/[r${R}:${FEAT}] /"
  return ${PIPESTATUS[0]}
}
case ${R} in
  0) headb ft ;;
  1) headb base ;;
  2) head_arm f0_other --voiced-field f0_other_voiced_ts ;;
  3) head_arm f0_bass  --voiced-field f0_bass_voiced_ts ;;
  4) head_arm hpcp ;;
  5) head_arm rms_energy_bass ;;
  6) head_arm onset_envelope ;;
  7) head_arm spectral_flatness ;;
esac
ARM_RC=$?
echo "[r${R}] arm done rc=${ARM_RC}"
exit ${ARM_RC}
'
rc=$?
echo "[ftstack] srun rc=${rc}"
echo "[ftstack] VERIFY: ls ${RUNROOT}/*/ (8 arm dirs); headb pair = headb_ft_s${SEED} vs headb_base_s${SEED}"
exit ${rc}
