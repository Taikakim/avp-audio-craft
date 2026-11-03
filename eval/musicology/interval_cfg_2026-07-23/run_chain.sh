#!/bin/bash
# run_chain.sh -- interval-CFG overnight chain: full render grid -> hook/clap/disint
# scoring -> per-cell analysis. Locks handled inside each stage (render + hook take
# the fleet .gpu.lock themselves, handle CONTINUITY-icfg; clap/disint are CPU).
# rc captured on its own line per the sequencer gotcha (never $(date) on the rc line).
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/sa3_lora_runs/interval_cfg_2026-07-23
LOG="$SAO/.icfg_chain.log"

echo "[chain] render stage start" >> "$LOG"
date >> "$LOG"
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
  "$SAO/stable-audio-3/.venv/bin/python" "$SAO/eval/interval_cfg_render.py" >> "$LOG" 2>&1
rc=$?
echo "[chain] render rc=$rc" >> "$LOG"
# verify the ARTIFACT, not the rc: 216 cells expected (incl. 36 symlinked controls)
nwav=$(ls "$OUT/renders" | grep -c '\.wav$')
echo "[chain] wav count: $nwav / 216" >> "$LOG"
if [ "$nwav" -lt 200 ]; then
  echo "[chain] STOP: render incomplete ($nwav/216) -- rerun resumable render first" >> "$LOG"
  exit 1
fi

echo "[chain] scoring stage start" >> "$LOG"
date >> "$LOG"
"$SAO/.venv/bin/python" "$SAO/eval/musicology/interval_cfg_2026-07-23/score_and_analyze.py" >> "$LOG" 2>&1
rc=$?
echo "[chain] score rc=$rc" >> "$LOG"
echo "[chain] done" >> "$LOG"
date >> "$LOG"
