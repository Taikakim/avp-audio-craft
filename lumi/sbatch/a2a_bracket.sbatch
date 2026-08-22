#!/bin/bash
# a2a_bracket.sbatch — EXPERIMENTS D14 (Kim direct 2026-08-22): cross-prompt a2a bracket at high
# noise across model families. 8 families, ONE PER RANK on one node.
#
# THE DESIGN, so nobody has to reverse it from the code:
#   T4096 (=380 s) crops drawn from our corpora -> re-noised to a sigma drawn at RANDOM in
#   [0.5, 0.9] -> denoised against a prompt STOLEN FROM ANOTHER CLIP (half the time from another
#   CORPUS). The mismatch is the instrument: it forces the model to choose between the init audio
#   and the caption, which is exactly where a control signal should assert itself.
#
# EVERY FAMILY SEES THE IDENTICAL GRID. a2a_bracket.py builds its plan from --plan-seed ALONE, so
# the crops, the donor prompts and the sigmas are the same for all 8 arms. Vary PLAN_SEED across
# WAVES, never across arms within a wave, or the family comparison is confounded by the draw.
#
# ⚠️ READ THE RESULT AS A DELTA, NOT AS QUALITY. W 2026-07-30: the mid-band a2a loss is the DiT
# ABANDONING HARMONY, not input fragility -- [0.5,0.9] straddles that band, so baseline
# degradation is the EXPECTED outcome. ~15% of cells are drawn from ANCHORS below the band (0.3,
# 0.4) purely as a yardstick, because D1 (the survival-curve twin) has never actually been run and
# without a low anchor "everything sounds degraded" is uninterpretable.
# ⚠️ CLAP-to-own-prompt is INVERTED here: the caption describes a different clip, so a HIGH score
# means the model discarded the init. That is the failure mode, not the win. (G is briefed.)
#
# NOT INCLUDED, deliberately: the pianoroll / mir_ctrl MIDI arm. Its control enters through the
# modular_local_embeds inlet, and SDEditReanchor builds its own conditioning dict (inpaint_mask +
# masked_input only) -- it would run UNCONDITIONED and look like a working arm. Kim asked for the
# midi control and it needs the reanchor conditioning path extended first; doing that blind on the
# last day of the allocation is how silent ablations happen. The morph/contour arm IS included and
# is conditioned properly, on the source crop's OWN contour over the same window.
#
# RUN: sbatch lumi/sbatch/a2a_bracket.sbatch        (N_CROPS=32 PLAN_SEED=... to vary)
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=04:00:00
#SBATCH --job-name=a2a_bracket
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif
ROUT=${SCRATCH}/renders/a2a_bracket
UNITS=${ROUT}/units.txt
mkdir -p ${ROUT}
N_CROPS=${N_CROPS:-32}
PLAN_SEED=${PLAN_SEED:-20260822}

# latents live on FLASH when a training job staged them (latents_sa3/latents_avp are tarballs on
# scratch with no loose npy), on SCRATCH otherwise. Resolve per dir, FATAL if neither has content.
res() {
  if [ "$(ls ${FLASH}/$1/*.npy 2>/dev/null | wc -l)" -gt 0 ]; then echo "${FLASH}/$1";
  elif [ "$(ls ${SCRATCH}/$1/*.npy 2>/dev/null | wc -l)" -gt 0 ]; then echo "${SCRATCH}/$1";
  else echo ""; fi
}
GOA=$(res latents_sa3); AVP=$(res latents_avp); SUO=$(res suomisoundi_latents); BIG=$(res latents_goa_bigset)
for v in GOA AVP SUO BIG; do
  [ -n "${!v}" ] || { echo "[a2a] FATAL: ${v} latents not found on FLASH or SCRATCH"; exit 1; }
done
echo "[a2a] corpora: goa=${GOA} avp=${AVP} suomi=${SUO} bigset=${BIG}"
C_GOA="goa:${GOA}:${CODE}/lumi/goa_longform_sidecar.json"
C_AVP="avpaug:${AVP}:${CODE}/lumi/avp_captions_tiered.json"
C_SUO="suomi:${SUO}:${CODE}/lumi/suomisoundi_caption_sidecar.json"
C_BIG="biggoa:${BIG}:${CODE}/lumi/goa_bigset_hinted_bylatent.json"
ALL4="--corpus ${C_GOA} --corpus ${C_AVP} --corpus ${C_SUO} --corpus ${C_BIG}"

pick() { ls $1 2>/dev/null | sort -t= -k2 -V | tail -1; }
SUB=${SCRATCH}/runs/subspace_loss_v3sel_grid_mt
K24=${SCRATCH}/runs/subloss_k24
A12=${SCRATCH}/runs/lr5e5_allsets
A13=$(pick "${SCRATCH}/runs/fullft_avp_subloss/*/epoch=*.ckpt")
MORPH=$(ls ${SCRATCH}/runs/morphcond/morph_L3_ft*/riffer_final.pt 2>/dev/null | head -1)

# units: LABEL|CKPT|BASE_STATE|CORPUS_ARGS|CONTROL_DIR   ("-" = none)
: > ${UNITS}.tmp
echo "baseline|none|-|${ALL4}|-"                                                        >> ${UNITS}.tmp
echo "sub_v3sel_k5|$(pick "${SUB}/subloss_v3sel_k5/epoch=*.ckpt")|-|${ALL4}|-"           >> ${UNITS}.tmp
echo "sub_v3sel_k12|$(pick "${SUB}/subloss_v3sel_k12/epoch=*.ckpt")|-|${ALL4}|-"         >> ${UNITS}.tmp
echo "sub_k24_bigmix|$(pick "${K24}/subloss_k24_bigmix_t512_bf16_s1/epoch=*.ckpt")|-|${ALL4}|-" >> ${UNITS}.tmp
echo "a12_warm|$(pick "${A12}/lr5e5mixwarm_*/epoch=*.ckpt")|-|${ALL4}|-"                 >> ${UNITS}.tmp
echo "a12_warmwsd|$(pick "${A12}/lr5e5mixwarmwsd_*/epoch=*.ckpt")|-|${ALL4}|-"           >> ${UNITS}.tmp
echo "a13_fullft_avp|none|${A13}|${ALL4}|-"                                              >> ${UNITS}.tmp
# morph: contour sidecars only exist for goa stems, so this arm runs goa-only BY NECESSITY
echo "morph_L3_ft|${MORPH}|-|--corpus ${C_GOA}|${SCRATCH}/latents_sa3_morphL3"           >> ${UNITS}.tmp
mv ${UNITS}.tmp ${UNITS}
echo "[a2a] units:"; cat ${UNITS}
awk -F'|' '$2!="none" && $2=="" {print "[a2a] FATAL: empty ckpt for "$1; bad=1} END{exit bad+0}' ${UNITS} || exit 1
awk -F'|' '$3!="-" && $3=="" {print "[a2a] FATAL: empty base-state for "$1; bad=1} END{exit bad+0}' ${UNITS} || exit 1

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
R=${SLURM_PROCID}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
echo "[r${R}] alive $(hostname) $(date -Is)"
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor:${CODE}/lumi
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export TRITON_CACHE_DIR=/tmp/triton-${R}
rm -rf /tmp/miopen-${R} /tmp/triton-${R}; mkdir -p /tmp/miopen-${R} /tmp/triton-${R}
ROUT=${SCRATCH}/renders/a2a_bracket
N=0
while IFS="|" read -r LABEL CK BASE CORP CDIR; do
  N=$((N+1)); [ $(( (N-1) % 8 )) -eq ${R} ] || continue
  echo "[r${R}] FAMILY ${LABEL}"
  EXTRA=""
  [ "${BASE}" != "-" ] && EXTRA="${EXTRA} --base-state-ckpt ${BASE}"
  [ "${CDIR}" != "-" ] && EXTRA="${EXTRA} --control-dir ${CDIR}"
  python ${CODE}/lumi/a2a_bracket.py --label ${LABEL} --ckpt "${CK}" ${CORP} ${EXTRA} \
    --out ${ROUT} --n-crops '"${N_CROPS}"' --frames 4096 \
    --noise-lo 0.5 --noise-hi 0.9 --anchors 0.3,0.4 --anchor-frac 0.15 \
    --cross-corpus-frac 0.5 --plan-seed '"${PLAN_SEED}"' --refs \
    || echo "[r${R}] ${LABEL} FAILED (continuing)"
done < "${SCRATCH}/renders/a2a_bracket/units.txt"
echo "[r${R}] done"
'
echo "[a2a] cells now: $(ls ${ROUT}/*.wav 2>/dev/null | wc -l)"
