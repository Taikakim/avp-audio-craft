#!/bin/bash
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=suomi_audition
#SBATCH --output=%x-%j.out
#SBATCH --open-mode=append
#
# suomisoundi_audition_render.sbatch — WINTERMUTE 2026-08-18, to Kim's spec (relayed via C):
# audition the four suomisoundi DoRA arms with a prompt set suited to the corpus.
#
#   * HALF the prompts replaced with suomisoundi-appropriate ones (lumi/suomisoundi_prompts_snapshot.json:
#     9 new, grounded in the corpus's own measured caption vocabulary; 9 standard ones KEPT VERBATIM
#     with their ids+seeds as controls, so those cells stay comparable with every other board model)
#   * cfg 7 AND 16          (not just the cfg7 operating point)
#   * weights 0.6, 1.0, 1.5
#   * EVERY 2ND CHECKPOINT  ("it's a new set altogether" — a dense ladder, not the every-10th probe)
#
# SCALE — 2592 cells, NOT the ~12960 first estimated. Two corrections, both worth keeping:
#   (1) each arm has 12 checkpoints, not 30: training ran 60 epochs at checkpoint_every_epochs=5.
#       Every 2nd of 12 = 6 (+ the terminal, which the picker always appends).
#   (2) these arms are T=256, so the renderer's "native" length IS 256 frames — identical to the
#       "20s" short cell. The sibling longrun_epoch_sweep_render.sbatch renders BOTH variants
#       because its candidates are long-context; here that would render every cell twice for
#       nothing. ONE length only.
#   18 prompts x 2 cfgs x 3 weights = 108 cells/ckpt; x ~7 ckpts x 4 arms ~= 3024 upper bound.
#
# ADAPTERS, NOT FULL-FINETUNES: no --fullft (0.8 GB r32 / 7.4 GB r256 adapter files), and NO
# --use-ema — train_lora.py force-disables EMA for LoRA/DoRA regardless of the flag, so there is
# no EMA weight set to load and asking for one would fail or silently no-op.
#
# VERIFY, never trust the exit code:
#   ls ${ROUT}/suomi_*__*.wav | wc -l     -> want ~3000, not 4 (the count IS the check)
#   grep -c "cells rendered" <out>
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

RUNROOT=${RUNROOT:-${SCRATCH}/runs/suomisoundi_dora}
ARMS=${ARMS:-"suomi_r32_lr1e-4 suomi_r32_lr3e-5 suomi_r256_lr1e-4 suomi_r256_lr3e-5"}
EVERY=${EVERY:-2}
SNAP=${SNAP:-${CODE}/lumi/suomisoundi_prompts_snapshot.json}
ROUT=${ROUT:-${SCRATCH}/renders/matrix_cells}
FRAMES=${FRAMES:-256}
CFGS=${CFGS:-"7,16"}                # comma-separated: render_matrix_cells.py parses these with .split(",")
STRENGTHS=${STRENGTHS:-"0.6,1.0,1.5"}   # comma-separated, same reason

[ -n "${SIF}" ] || { echo "[audition] FATAL: no lumi-multitorch-full image"; exit 1; }
echo "[env] IMG=$(basename "${SIF}")"
[ -f "${VENV}/bin/activate" ] || { echo "[audition] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[audition] FATAL: prompt snapshot ${SNAP} not shipped -- refresh the code tree"; exit 1; }
mkdir -p "${ROUT}"

for ARM in ${ARMS}; do
  RUN="${RUNROOT}/${ARM}"
  [ -d "${RUN}" ] || { echo "[audition] SKIP ${ARM}: ${RUN} missing"; continue; }
  # Pick every EVERY-th checkpoint by EPOCH NUMBER, always including the terminal one.
  mapfile -t ALL < <(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V)
  [ ${#ALL[@]} -gt 0 ] || { echo "[audition] SKIP ${ARM}: no fat checkpoints"; continue; }
  PICK=()
  for c in "${ALL[@]}"; do
    EP=$(basename "$c" | sed -E 's/^epoch=([0-9]+).*/\1/')
    if [ $(( EP % EVERY )) -eq 0 ]; then PICK+=("$c"); fi
  done
  LAST="${ALL[-1]}"
  case " ${PICK[*]} " in *" ${LAST} "*) ;; *) PICK+=("${LAST}") ;; esac
  echo "[audition] ${ARM}: ${#ALL[@]} checkpoints present, rendering ${#PICK[@]}"

  srun --nodes=1 --ntasks=1 --cpus-per-task=56 \
    singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
source '"${VENV}"'/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH='"${VENV}"'/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export MIOPEN_USER_DB_PATH=/tmp/miopen-audition MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-audition
export TRITON_CACHE_DIR=/tmp/triton-audition PYTORCH_TUNABLEOP_ENABLED=0
mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
for CK in '"${PICK[*]}"'; do
  EP=$(basename "${CK}" | sed -E "s/^epoch=([0-9]+).*/\1/")
  echo "[audition] '"${ARM}"' ep${EP}"
  python ${CODE}/lumi/render_matrix_cells.py \
      --label '"${ARM}"' --tag ep${EP} \
      --ckpt "${CK}" \
      --prompts '"${SNAP}"' --out '"${ROUT}"' \
      --only-cfgs '"${CFGS}"' --strengths '"${STRENGTHS}"' \
      --frames '"${FRAMES}"'
done
'
done

echo "[audition] finished -- VERIFY THE ARTIFACTS, not this exit code:"
for ARM in ${ARMS}; do
  echo "  ${ARM}: $(ls ${ROUT}/${ARM}__* 2>/dev/null | wc -l) cells"
done
