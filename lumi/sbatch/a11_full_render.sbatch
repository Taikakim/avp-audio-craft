#!/bin/bash
# a11_full_render.sbatch — Kim direct 2026-08-21: "render all, full prompt set (suomi arms +
# the new suomi prompts), cfg 7, w1, 20s + pick three for native length per checkpoint, 8xGPU,
# pre-split, also ptm since these are adapters."
#
# Covers EVERY fat ckpt under runs/dorlor_ab/ (A11, native T256) and runs/subloss_k24/ (B10,
# native T512). Per ckpt, three passes: (1) full snapshot (suomi arms: +anchor/modal/random)
# cfg7 w1 20s on medium-base; (2) same adapter on PT medium (--pt-medium, label __ptm);
# (3) rb_common_0/1/2 at the arm's NATIVE frames. PRE-SPLIT: the (dir,ckpt) unit list is
# built once, ranks take units round-robin (lumi-ops rule) — idempotent per cell, so re-run
# after more arms finish just fills gaps. winning_fleet EXCLUDED on purpose: the torchrun
# restarts write into the same dirs as the Pattern-2 replica ladders (distinguishable by step
# count, but a mixed-era render would mislead the board).
# RUN: sbatch lumi/sbatch/a11_full_render.sbatch    (re-run later to fill new ckpts)
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=04:00:00
#SBATCH --job-name=a11_render
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif

# pre-split: build the unit list ONCE, before srun (assignment is deterministic per rank)
UNITS=${SCRATCH}/renders/a11_render_units.txt
: > "${UNITS}"
for d in ${SCRATCH}/runs/dorlor_ab/*/ ${SCRATCH}/runs/subloss_k24/*/; do
  [ -d "$d" ] || continue
  for ck in $(ls ${d}epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$"); do
    echo "${d%/}|${ck}" >> "${UNITS}"
  done
done
NU=$(wc -l < "${UNITS}")
echo "[a11r] ${NU} (arm,ckpt) units pre-split across 8 ranks"
[ "${NU}" -gt 0 ] || { echo "[a11r] FATAL: no ckpts found"; exit 1; }

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
R=${SLURM_PROCID}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
echo "[r${R}] alive $(hostname) $(date -Is)"
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export TRITON_CACHE_DIR=/tmp/triton-${R}
rm -rf /tmp/miopen-${R} /tmp/triton-${R}; mkdir -p /tmp/miopen-${R} /tmp/triton-${R}
UNITS=${SCRATCH}/renders/a11_render_units.txt
ROUT=${SCRATCH}/renders/matrix_cells; mkdir -p ${ROUT}
SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
SUOMIP=${CODE}/lumi/suomi_full_prompts.json
Q3=${CODE}/lumi/quickeval3_prompts.json
N=0
while IFS="|" read -r DIR CK; do
  N=$((N+1))
  [ $(( (N-1) % 8 )) -eq ${R} ] || continue
  NAME=$(basename "${DIR}")
  EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
  PR=${SNAP}; case "${NAME}" in *suomi*) PR=${SUOMIP};; esac
  NF=256; case "${NAME}" in subloss_k24_*) NF=512;; esac
  echo "[r${R}] UNIT ${NAME} ep${EP} (prompts $(basename ${PR}), native T${NF})"
  python ${CODE}/lumi/render_matrix_cells.py --label ${NAME} --tag ep${EP} \
    --ckpt "${CK}" --prompts ${PR} --out ${ROUT} --only-cfgs 7 --strengths 1.0 \
    || echo "[r${R}] ${NAME} ep${EP} base pass FAILED (continuing)"
  python ${CODE}/lumi/render_matrix_cells.py --label ${NAME} --tag ep${EP} \
    --ckpt "${CK}" --prompts ${PR} --out ${ROUT} --only-cfgs 7 --strengths 1.0 --pt-medium \
    || echo "[r${R}] ${NAME} ep${EP} ptm pass FAILED (continuing)"
  python ${CODE}/lumi/render_matrix_cells.py --label ${NAME} --tag ep${EP} \
    --ckpt "${CK}" --prompts ${Q3} --out ${ROUT} --only-cfgs 7 --strengths 1.0 --frames ${NF} \
    || echo "[r${R}] ${NAME} ep${EP} native pass FAILED (continuing)"
done < "${UNITS}"
echo "[r${R}] done"
'
echo "[a11r] cells now: $(ls ${SCRATCH}/renders/matrix_cells/dorlor_*__cfg7__*.wav ${SCRATCH}/renders/matrix_cells/subloss_k24_*__cfg7__*.wav 2>/dev/null | wc -l)"
