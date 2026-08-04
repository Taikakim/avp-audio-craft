#!/bin/bash
# headb_bracket_local.sh — LOCAL transcribe + analyze of the LUMI-rendered Head-B melody
# bracket (job 20336044: 384 wavs / 48 cells = 8 ckpts past-5280 × cfg{1,7,16} × gain{1,1.5}).
# The LUMI SIF lacks muscriptor+mido, so transcription can only run HERE in SAO/.venv
# (hook_eval_renders.py's own venv note). Three phases:
#   (1) GPU  — muscriptor transcribe each cell's 8 wavs -> hook_scores.jsonl + hook_scores_midi
#              (single SAO/.gpu.lock hold for the batch; resumable — a cached .mid skips the GPU).
#   (2) CPU  — melody_pilot_eval.py analyze per cell (HEADB_OUT=$cell) -> results.json
#              (adoption vs empirical null floor + disintegration gate + z0 causal check).
#   (3) CPU  — cross-cell rollup -> bracket_summary.tsv (does Head-B steer, at which cfg/gain).
# Idempotent: phase 1 skips scored clips, phase 2/3 just overwrite their derived files.
#
# Usage: control/sa3_control/headb_bracket_local.sh [ROOT]
#   ROOT default = the canonical LUMI-pull dir for this bracket.
set -uo pipefail
ROOT=${1:-/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/renders/headb_bracket}
SAO=/home/kim/Projects/SAO
PY=${SAO}/.venv/bin/python
LOCK=${SAO}/.gpu.lock
FLK=${SAO}/Misc/filelock.py
HOOK=${SAO}/eval/hook_eval_renders.py
MPE=${SAO}/control/sa3_control/melody_pilot_eval.py
ROLL=${SAO}/control/sa3_control/headb_bracket_rollup.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2

mapfile -t CELLS < <(ls -d "${ROOT}"/*/ 2>/dev/null)
[ ${#CELLS[@]} -eq 0 ] && { echo "[headb-local] no cell dirs under ${ROOT} — pull the LUMI renders first"; exit 1; }
echo "[headb-local] ${#CELLS[@]} cell dirs under ${ROOT}"

# ── Phase 1: GPU transcription (one lock hold for the whole batch; G-first — acquire blocks
#    while another instance holds the card, and pid-aware only breaks a DEAD holder) ──
python3 "${FLK}" acquire "${LOCK}" --handle CONTINUITY --pid-aware --pid $$ \
  || { echo "[headb-local] could not acquire ${LOCK}"; exit 1; }
trap 'python3 "'"${FLK}"'" release "'"${LOCK}"'" --handle CONTINUITY 2>/dev/null' EXIT
echo "[headb-local] GPU lock held; transcribing 8 wavs/cell"
for cell in "${CELLS[@]}"; do
  w=$(ls "${cell}"renders/*.wav 2>/dev/null | wc -l || true)
  [ "${w}" -eq 0 ] && { echo "[skip] $(basename "${cell}"): 0 wavs"; continue; }
  "${PY}" "${HOOK}" --wavs "${cell}renders/*.wav" --out "${cell}hook_scores.jsonl" \
    --midi-dir "${cell}hook_scores_midi" --bpm 143 --device cuda \
    || echo "[headb-local] TRANSCRIBE-WARN $(basename "${cell}")"
done
python3 "${FLK}" release "${LOCK}" --handle CONTINUITY 2>/dev/null
trap - EXIT
echo "[headb-local] transcription done; GPU lock released"

# ── Phase 2: CPU analyze per cell ──
for cell in "${CELLS[@]}"; do
  [ -f "${cell}manifest.json" ] || { echo "[skip-analyze] $(basename "${cell}"): no manifest.json"; continue; }
  if HEADB_OUT="${cell}" "${PY}" "${MPE}" analyze > "${cell}analyze.tsv" 2>"${cell}analyze.err"; then
    echo "[analyze] $(basename "${cell}") -> results.json"
  else
    echo "[headb-local] ANALYZE-WARN $(basename "${cell}") (see ${cell}analyze.err)"
  fi
done

# ── Phase 3: cross-cell rollup ──
"${PY}" "${ROLL}" "${ROOT}" | tee "${ROOT}/bracket_summary.tsv"
echo "[headb-local] done -> ${ROOT}/bracket_summary.tsv"
