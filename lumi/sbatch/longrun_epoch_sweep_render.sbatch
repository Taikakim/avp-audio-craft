#!/bin/bash
# longrun_epoch_sweep_render.sbatch — CONTINUITY 2026-08-18, Kim direct:
#   "don't pull epochs past 64 now... I have a suspicion those models are very cooked by now, and
#    pulling the last checkpoints would leave us with trash. We should then create our clips every
#    10th checkpoint for those very long runs. To speed things up, choose just three prompts at
#    cfg 7 / w 1 for each at the 20s and native lengths."
#
# WHY THIS EXISTS AND WHAT IT OVERTURNS: the standing convention is "the terminal fat is the run's
# result — pull that, slims elsewhere". For runs that went to ep69/134/153/228 that convention is
# probably WRONG: past some point the model is overtrained and the last checkpoint is the worst one
# to keep. Rather than guess, render a ladder across the run and let Kim's ears pick the epoch. Only
# then is it worth spending 20-41 GB of transfer on a fat.
#
# So this is a SELECTION instrument, not a results render: 3 prompts x cfg7 x w1 x {20s, native},
# every 10th checkpoint. Deliberately small per checkpoint — the question is "where on this run does
# quality peak / collapse", which a 3-prompt probe answers, not "how good is this model", which
# needs the full board.
#
# RUN (one long run per submit; SET the run dir):
#   RUN=/scratch/project_465003186/runs/fullft/fullft_avp_t256 LABEL=fullft_avp_t256_sweep \
#     sbatch --nodes=1 --time=06:00:00 lumi/sbatch/longrun_epoch_sweep_render.sbatch
# Candidates (terminal epoch > 64, i.e. the ones excluded from the pull list):
#   fullft/fullft_avp_t256 (ep153) · fullft/fullft_goa_t256 (ep69)
#   fp32_winning/winning_avp_t512_a128_fp32 (ep228) · fp32_winning/winning_goa_t512_a128_fp32 (ep134)
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=06:00:00
#SBATCH --job-name=sa3_longrun_sweep
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

RUN=${RUN:?set RUN=<run dir containing epoch=*.ckpt>}
LABEL=${LABEL:-$(basename ${RUN})_sweep}
EVERY=${EVERY:-10}                 # every Nth checkpoint
SNAP=${SNAP:-${CODE}/lumi/matrix_prompts_3x.json}   # 3 prompts, cfgs=[7]
ROUT=${ROUT:-${SCRATCH}/renders/matrix_cells}
FRAMES_SHORT=${FRAMES_SHORT:-256}  # ~23.8 s — the "20s" grid cell (MASTER: frames are multiples of
                                   # 256; 20 s would be ~215 frames, a ragged tile that maps badly
                                   # onto the GEMM/flash-attn kernels)
FRAMES_NATIVE=${FRAMES_NATIVE:-}   # empty = the checkpoint's own trained length (renderer default)
FULLFT=${FULLFT:-1}                # these candidates are all full-finetunes
EMA=${EMA:-0}

[ -n "${SIF}" ] || { echo "[sweep] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[sweep] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[sweep] FATAL: prompt snapshot ${SNAP} missing"; exit 1; }
[ -d "${RUN}" ] || { echo "[sweep] FATAL: run dir ${RUN} missing"; exit 1; }

# every Nth checkpoint by EPOCH (not by file order — pruned runs have gaps, and -vN duplicates from
# the uncoordinated-trainer era would otherwise be counted as separate rungs).
mapfile -t ALL < <(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v '\.weights\.ckpt$' | grep -v -- '-v[0-9]*\.ckpt$' | sort -V)
[ "${#ALL[@]}" -gt 0 ] || { echo "[sweep] FATAL: no fat ckpt in ${RUN}"; exit 1; }
PICK=()
for c in "${ALL[@]}"; do
  EP=$(basename "$c" | sed 's/.*epoch=//; s/-step=.*//')
  if [ $(( EP % EVERY )) -eq 0 ]; then PICK+=("$c"); fi
done
# always include the terminal one, so the ladder has its endpoint even if it is not a multiple
LAST="${ALL[-1]}"
[[ " ${PICK[*]} " == *" ${LAST} "* ]] || PICK+=("${LAST}")

echo "[sweep] RUN=${RUN}"
echo "[sweep] ${#ALL[@]} fat ckpt(s) present; rendering ${#PICK[@]} of them (every ${EVERY}th + terminal)"
echo "[sweep] prompts=$(python3 -c "import json;print(len(json.load(open('${SNAP}'))['prompts']))") cfg=7 w=1.0 lengths={${FRAMES_SHORT}f, native}"
echo "[sweep] label=${LABEL} -> ${ROUT}"
for c in "${PICK[@]}"; do echo "[sweep]   $(basename $c)"; done
mkdir -p "${ROUT}"

FF_ARG=""; [ "${FULLFT}" = "1" ] && FF_ARG="--fullft"
EMA_ARG=""; [ "${EMA}" = "1" ] && EMA_ARG="--use-ema"

srun --nodes=1 --ntasks=1 --cpus-per-task=56 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-sweep MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-sweep
export TRITON_CACHE_DIR=/tmp/triton-sweep PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-sweep /tmp/triton-sweep; mkdir -p /tmp/miopen-sweep /tmp/triton-sweep
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
for CK in '"${PICK[*]}"'; do
  EP=$(basename "${CK}" | sed "s/.*epoch=//; s/-step=.*//")
  for LEN in short native; do
    if [ "${LEN}" = "short" ]; then FR="--frames '"${FRAMES_SHORT}"'"; TAG="ep${EP}_20s"; else FR=""; TAG="ep${EP}_native"; fi
    echo "[sweep] ${TAG} <- ${CK}"
    python ${CODE}/lumi/render_matrix_cells.py \
        --label '"${LABEL}"' --tag ${TAG} \
        --ckpt "${CK}" '"${FF_ARG}"' '"${EMA_ARG}"' \
        --prompts '"${SNAP}"' --out '"${ROUT}"' \
        --only-cfgs 7 --strengths 1.0 ${FR} \
      || echo "[sweep] ${TAG} FAILED (non-fatal, continuing the ladder)"
  done
done
'
echo "[sweep] done. cells:"; ls "${ROUT}"/${LABEL}__* 2>/dev/null | wc -l
echo "[sweep] NEXT: audition the ladder, pick the epoch that actually sounds right, and pull THAT"
echo "[sweep]   fat — do not assume the terminal checkpoint is the run's best (that assumption is"
echo "[sweep]   exactly what this sweep exists to test)."
