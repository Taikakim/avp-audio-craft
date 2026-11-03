#!/bin/bash
# GPU phase of the chroma-turning probe: lock -> render 26 cells -> muscriptor
# transcribe -> release. Analysis is CPU, done after, outside the lock.
set -u
cd /home/kim/Projects/SAO
D=eval/musicology/chroma_turning_2026-07-22
LOG=$D/gpu_phase.log

echo "=== $(date -Is) waiting for .gpu.lock ===" >> "$LOG"
# Courtesy wait: the current holder (continuity-melenc2) records a transient CLI pid,
# so --pid-aware would see DEAD and steal a live session's lock. Only proceed to
# acquire when the lock file is absent OR untouched for >20 min (genuinely stale).
deadline=$(( $(date +%s) + 21600 ))
while :; do
  if [ ! -e .gpu.lock ]; then break; fi
  age=$(( $(date +%s) - $(stat -c %Y .gpu.lock) ))
  holder=$(python3 Misc/filelock.py check /home/kim/Projects/SAO/.gpu.lock 2>&1)
  case "$holder" in *CONTINUITY-chromaturn*) break ;; esac
  if [ "$age" -gt 1200 ]; then
    echo "$(date -Is) lock stale (age ${age}s) — reclaiming: $holder" >> "$LOG"
    break
  fi
  if [ $(date +%s) -gt $deadline ]; then
    echo "TIMEOUT waiting for lock: $holder" >> "$LOG"
    exit 3
  fi
  sleep 60
done
python3 Misc/filelock.py acquire /home/kim/Projects/SAO/.gpu.lock \
  --handle CONTINUITY-chromaturn --pid-aware --pid $$ --timeout 21600 >> "$LOG" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
  echo "LOCK-FAIL rc=$rc" >> "$LOG"
  exit 3
fi
echo "=== lock acquired, rendering ===" >> "$LOG"

.venv/bin/python $D/chromaturn.py render >> "$LOG" 2>&1
rc_render=$?
echo "render rc=$rc_render" >> "$LOG"

n_wavs=$(ls $D/renders/*.wav 2>/dev/null | wc -l)
echo "wavs present: $n_wavs" >> "$LOG"

rc_tr=99
if [ "$n_wavs" -gt 0 ]; then
  echo "=== transcribing (muscriptor) ===" >> "$LOG"
  .venv/bin/python eval/hook_eval_renders.py \
    --wavs "$D/renders/*.wav" \
    --out $D/hook_scores.jsonl \
    --midi-dir $D/hook_scores_midi \
    --bpm 161.499 >> "$LOG" 2>&1
  rc_tr=$?
  echo "transcribe rc=$rc_tr" >> "$LOG"
fi

python3 Misc/filelock.py release /home/kim/Projects/SAO/.gpu.lock \
  --handle CONTINUITY-chromaturn >> "$LOG" 2>&1
echo "=== $(date -Is) lock released; render_rc=$rc_render transcribe_rc=$rc_tr wavs=$n_wavs ===" >> "$LOG"
n_mids=$(ls $D/hook_scores_midi/*.mid 2>/dev/null | wc -l)
echo "mids present: $n_mids" >> "$LOG"
if [ $rc_render -ne 0 ] || [ "$n_wavs" -lt 35 ] || [ "$n_mids" -lt "$n_wavs" ]; then
  exit 4
fi
exit 0
