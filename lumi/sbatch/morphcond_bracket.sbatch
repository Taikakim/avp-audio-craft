#!/bin/bash
# morphcond_bracket.sbatch — MORPH-CONTOUR conditioning bracket (Kim direct 2026-08-21:
# "the morph stuff — the one actually new idea we have"). D12's landed contour-token stack
# gets its first training: K&P dense-rank contour symbols from the f0 melody line, three
# alphabet RESOLUTIONS (L2=3 symbols "up/eq/down", L3=13, L4=75), conditioned through the
# proven Head-B melody_contour path (Embedding(vocab) -> decoupled cross-attn adapters),
# on BOTH backbones (medium-base + the fresh fullft_avpaug ep19 EMA).
# 8 single-GCD arms:  r0-2: L2/L3/L4 on base   r3-5: L2/L3/L4 on FT
#                     r6-7: L3 base/FT seed 2 (variance pair on the middle resolution)
# Recipe = B9's Head-B settings (fusion, ema 0.999, ga2, bs4, crop 512, 12 ep, val 0.1,
# early-stop 4). Sidecars: latents_sa3_morphL{2,3,4}/ (build_morph_streams.py, rsync'd).
# RUN: FT_CKPT=<avpaug ep19 fat ckpt> sbatch lumi/sbatch/morphcond_bracket.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=morphcond
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
FT_CKPT=${FT_CKPT:?set FT_CKPT=<full-FT fat ckpt>}
SEED=${SEED:-1}
RUNROOT=${SCRATCH}/runs/morphcond
echo "[morph] CONFIG FT_CKPT=${FT_CKPT} node=$(hostname) $(date -Is)"
[ -f "${FT_CKPT}" ] || { echo "[morph] FATAL: FT_CKPT missing"; exit 1; }
for L in 2 3 4; do
  [ -f "${SCRATCH}/latents_sa3_morphL${L}/000006.melody8.npy" ] \
    || { echo "[morph] FATAL: morphL${L} sidecars not rsynced (stat-probe)"; exit 1; }
done
[ -f "${FLASH}/latents_sa3/000003.npy" ] || { echo "[morph] FATAL: flash latents missing"; exit 1; }
grep -q "melody-vocab" ${CODE}/control/sa3_control/train.py || { echo "[morph] FATAL: control code stale"; exit 1; }
echo "[morph] preflight passed; launching 8 arms"
mkdir -p "${RUNROOT}"
cat > "${RUNROOT}/run_meta.json" <<META
{"run": "morphcond_bracket", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "D12 first training (Kim: 'the one actually new idea'): K&P contour-symbol conditioning from f0, alphabet resolution L2/L3/L4 x backbone base/FT(avpaug ep19 EMA) + L3 seed pair. Head-B path, vocab 5/15/77.",
 "recipe": "B9 headb settings: fusion ema0.999 ga2 bs4 crop512 12ep val0.1 early-stop",
 "sidecars": "latents_sa3_morphL{2,3,4} (build_morph_streams.py: f0_other semitones, voiced-stride-4 grid, tol 0.5 st)",
 "script": "lumi/sbatch/morphcond_bracket.sbatch", "kim_feedback": null}
META

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
R=${SLURM_PROCID}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
echo "[r${R}] rank alive on $(hostname) $(date -Is)"
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
LAT=${FLASH}/latents_sa3
case ${R} in
  0) L=2; BK=base; SD=1 ;;  1) L=3; BK=base; SD=1 ;;  2) L=4; BK=base; SD=1 ;;
  3) L=2; BK=ft;   SD=1 ;;  4) L=3; BK=ft;   SD=1 ;;  5) L=4; BK=ft;   SD=1 ;;
  6) L=3; BK=base; SD=2 ;;  7) L=3; BK=ft;   SD=2 ;;
esac
case ${L} in 2) VOCAB=5 ;; 3) VOCAB=15 ;; 4) VOCAB=77 ;; esac
EXTRA=""; [ "${BK}" = "ft" ] && EXTRA="--base-state-ckpt ${FT}"
NAME=morph_L${L}_${BK}_s${SD}
python -m sa3_control.train \
  --control-mode melody_contour --melody-dir ${SCRATCH}/latents_sa3_morphL${L} \
  --melody-vocab ${VOCAB} \
  --model medium-base ${EXTRA} \
  --encoded_dir ${LAT} --crop-frames 512 --random-crop \
  --optimizer fusion --ema 0.999 --grad-accum 2 --batch 4 \
  --max-epochs 12 --val-frac 0.1 --early-stop-patience 4 \
  --seed ${SD} --run-name ${NAME} \
  --save-dir ${RUNROOT}/${NAME} \
  2>&1 | sed "s/^/[r${R}:${NAME}] /"
ARM_RC=${PIPESTATUS[0]}
echo "[r${R}] ${NAME} done rc=${ARM_RC}"
exit ${ARM_RC}
'
rc=$?
echo "[morph] srun rc=${rc}; arm dirs: $(ls -d ${RUNROOT}/*/ 2>/dev/null | wc -l)"
exit ${rc}
