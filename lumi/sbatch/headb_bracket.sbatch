#!/bin/bash
# headb_bracket.sbatch — Head B melody-conditioning BRACKET eval on LUMI (CONTINUITY 2026-07-24).
# Moved to LUMI because the local GPU is a chronic bottleneck (perma-contended + the local
# TRAIN crashed with ROCm heap corruption). Headless GCD, no lock/VRAM dance, known-good env.
# Spec: docs/superpowers/specs/2026-07-22-melodic-latch-film.md §2/§8.
#
# WHAT: every headb_melody ckpt PAST step 5280 (epochs ~9-15 + final = 8 ckpts) x cfg{1,7,16}
#   x gain{1.0,1.5} = 6 settings/ckpt. Per cell: 4 motif-conditioned + null-floor renders (via
#   melody_pilot_eval.py render, HEADB_* env overrides) -> muscriptor transcription. The CPU
#   `analyze` step (adoption vs null + disintegration gate) runs LOCALLY after the pull (needs
#   clip_metrics/disintegration_metrics tooling), so this job = render + transcribe only.
# BASE-PT no-adapter baseline for the final ckpt stays G's pt-medium render (separate).
#
# PREREQ: $SCRATCH/runs/headb_melody/riffer_*.pt (already there from the training job 20190732).
#   medium-base + T5-Gemma cached in $MODELS (proven by the base_native_grid render job 20218220).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=60G
#SBATCH --time=08:00:00
#SBATCH --job-name=sa3_headb_bracket
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${CODE:-$PROJ/code}; SIF=${SIF:-$PROJ/containers/sa3.sif}; MODELS=${PROJ}/models
CKDIR=${SCRATCH}/runs/headb_melody
OUT=${SCRATCH}/renders/headb_bracket; mkdir -p "${OUT}"
CKPTS="riffer_step5940 riffer_step6600 riffer_step7260 riffer_step7920 riffer_step8580 riffer_step9240 riffer_step9900 riffer_final"
CFGS="1 7 16"; GAINS="1.0 1.5"

for ck in ${CKPTS}; do
  [ -f "${CKDIR}/${ck}.pt" ] || { echo "[headb-bracket] FATAL: missing ${CKDIR}/${ck}.pt"; exit 1; }
done
echo "[headb-bracket] 8 ckpts present; grid cfg{${CFGS// /,}} x gain{${GAINS// /,}}"

srun singularity exec --bind "${PROJ}","${SCRATCH}","${FLASH}",/tmp "${SIF}" bash -c '
set -euo pipefail
CODE='"${CODE}"'; CKDIR='"${CKDIR}"'; OUT='"${OUT}"'
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export MIOPEN_USER_DB_PATH=/tmp/miopen-headb-$$ MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-headb-$$
mkdir -p "$MIOPEN_USER_DB_PATH"
for ck in '"${CKPTS}"'; do
  for c in '"${CFGS}"'; do for g in '"${GAINS}"'; do
    CELL=$OUT/${ck}_cfg${c}_g${g}
    HEADB_OUT=$CELL HEADB_CFG=$c HEADB_GAIN=$g \
      python $CODE/control/sa3_control/melody_pilot_eval.py render --ckpt $CKDIR/${ck}.pt \
      || echo "[headb-bracket] RENDER-WARN $ck cfg$c g$g"
    n=$(ls "$CELL/renders"/*.wav 2>/dev/null | wc -l || true)  # ls exits 2 on missing dir; do not let set -e kill the job
    # muscriptor transcription -> hook_scores.jsonl / hook_scores_midi (exact paths analyze reads)
    python $CODE/eval/hook_eval_renders.py --wavs "$CELL/renders/*.wav" \
      --out "$CELL/hook_scores.jsonl" --midi-dir "$CELL/hook_scores_midi" --bpm 143 \
      || echo "[headb-bracket] TRANSCRIBE-WARN $ck cfg$c g$g"
    echo "[cell $ck cfg$c g$g] wavs=$n mids=$(ls "$CELL/hook_scores_midi"/*.mid 2>/dev/null | wc -l)"
  done; done
done
'
NWAV=$(find "${OUT}" -name '*.wav' 2>/dev/null | wc -l)
echo "[headb-bracket] done -> ${OUT} : ${NWAV} wavs (expect ~$((8*3*2*8)) = 384)"
[ "${NWAV}" -ge 300 ] || { echo "[headb-bracket] SUCCESS-CHECK LOW (${NWAV}<300) — inspect ${OUT}"; exit 1; }
