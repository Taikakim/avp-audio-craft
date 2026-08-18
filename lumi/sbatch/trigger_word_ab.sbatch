#!/bin/bash
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=64G
#SBATCH --time=00:30:00
#SBATCH --job-name=trigger_ab
#SBATCH --output=%x-%j.out
#SBATCH --open-mode=append
#
# trigger_word_ab.sbatch — WINTERMUTE 2026-08-18. Settles one question in 8 cells:
# DID THE AVP FINETUNES LEARN THE TRIGGER WORD, or did we only ever ask them wrong?
#
# Kim: "the base model's understanding of aavepyörä is just noise, but I was expecting a full
# finetune would learn away from that." Measured: the avp training captions contain 'aavepyörä'
# 4724x (longform) / 7140x (tiered) and 'aavepyora' ZERO times -- while EVERY eval prompt we have
# ever rendered used 'aavepyora'. Different strings to a text encoder. So every trig2/housestyle
# cell on the board asked a finetuned model for a token it saw zero times in training and got
# back roughly what the base model gives. Not a training failure; the wrong question.
#
# THE CONTROL: trig2 and trig2_uml carry the SAME SEED and differ ONLY in the spelling. A
# different seed would confound the token with the sample and make the pair worthless.
#
# MUST BE AN AVP MODEL. The suomisoundi captions contain the trigger 0 times, so those arms
# cannot answer this no matter how they sound. Default below is a full-finetune; set FULLFT=0
# and point RUN at an adapter run to test one of those instead.
#
# WHAT THE RESULT MEANS:
#   trig2_uml sounds like Kim's music, trig2 is noise  -> learned; every past trigger cell is void
#   both are noise                                     -> not learned, and the spelling was a red herring
#   both sound alike                                   -> the token is not doing any work either way
#
# VERIFY: ls ${ROUT}/${LABEL}__* | wc -l  -> want 8, not 0.
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

RUN=${RUN:?set RUN=<run dir containing epoch=*.ckpt>, e.g. ${SCRATCH}/runs/fullft/fullft_avp_t256}
LABEL=${LABEL:-$(basename ${RUN})_trigab}
SNAP=${SNAP:-${CODE}/lumi/trigger_ab_prompts.json}
ROUT=${ROUT:-${SCRATCH}/renders/matrix_cells}
FRAMES=${FRAMES:-256}
FULLFT=${FULLFT:-1}

[ -n "${SIF}" ] || { echo "[trigab] FATAL: no lumi-multitorch-full image"; exit 1; }
echo "[env] IMG=$(basename "${SIF}")"
[ -f "${SNAP}" ] || { echo "[trigab] FATAL: ${SNAP} not shipped -- refresh the code tree"; exit 1; }
grep -q "aavepyörä" "${SNAP}" || { echo "[trigab] FATAL: ${SNAP} has no umlaut form -- the whole point of this job. Encoding lost in transfer?"; exit 1; }
[ -d "${RUN}" ] || { echo "[trigab] FATAL: RUN=${RUN} missing"; exit 1; }

CK=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1)
[ -n "${CK}" ] || CK=$(ls "${RUN}"/*.ckpt 2>/dev/null | sort -V | tail -1)
[ -n "${CK}" ] || { echo "[trigab] FATAL: no checkpoint in ${RUN}"; exit 1; }
echo "[trigab] ${LABEL}: $(basename ${CK})"
FF_ARG=""; [ "${FULLFT}" = "1" ] && FF_ARG="--fullft"
mkdir -p "${ROUT}"

srun --nodes=1 --ntasks=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
source '"${VENV}"'/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH='"${VENV}"'/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTHONIOENCODING=utf-8 LC_ALL=C.UTF-8
export MIOPEN_USER_DB_PATH=/tmp/miopen-trigab MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-trigab
export TRITON_CACHE_DIR=/tmp/triton-trigab PYTORCH_TUNABLEOP_ENABLED=0
mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
python ${CODE}/lumi/render_matrix_cells.py \
    --label '"${LABEL}"' --tag trigab \
    --ckpt "'"${CK}"'" '"${FF_ARG}"' \
    --prompts '"${SNAP}"' --out '"${ROUT}"' \
    --only-cfgs 7,16 --strengths 1.0 --frames '"${FRAMES}"'
'
echo "[trigab] done -- VERIFY THE ARTIFACTS: $(ls ${ROUT}/${LABEL}__* 2>/dev/null | wc -l) cells (want 8)"
