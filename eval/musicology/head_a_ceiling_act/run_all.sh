#!/usr/bin/env bash
# run_all.sh — Head A ACTIVATION ceiling, full overnight chain.
# Lock discipline per MASTER §5: pid-aware GPU mutex, held across the
# extraction burst and the training burst, released between.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SAO=/home/kim/Projects/SAO
PY="$SAO/.venv/bin/python"
LOCK="$SAO/.gpu.lock"
FL="$SAO/Misc/filelock.py"
HANDLE=continuity-heada2
LOG="$HERE/run_all.log"

say() { echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }

say "=== run_all start (pid $$) ==="

# ---- burst 1: smoke test + extraction ----
say "waiting for GPU lock (extraction)..."
python3 "$FL" acquire "$LOCK" --handle "$HANDLE" --pid-aware --pid $$ --timeout 43200 >> "$LOG" 2>&1
rc=$?
if [ "$rc" -ne 0 ]; then say "LOCK ACQUIRE FAILED rc=$rc — aborting"; exit 3; fi
SMOKE=/tmp/claude-1000/-home-kim-Projects-SAO/49cd5391-27e7-4545-8295-a1053db2a077/scratchpad/heada2_smoke
rm -rf "$SMOKE"; mkdir -p "$SMOKE"
say "lock held — smoke test (4 crops, 1 cell, 1 epoch)"
HEADA2_ACTS_DIR="$SMOKE" "$PY" "$HERE/extract_acts.py" --n-train 2 --n-val 1 --n-test 1 >> "$HERE/smoke.log" 2>&1 \
  && HEADA2_ACTS_DIR="$SMOKE" HEADA2_RESULTS="$SMOKE/results.json" \
     "$PY" "$HERE/train_readout_act.py" --t 0.5 --layer 12 --epochs 1 --patience 1 >> "$HERE/smoke.log" 2>&1
src=$?
if [ "$src" -ne 0 ]; then
  python3 "$FL" release "$LOCK" --handle "$HANDLE" >> "$LOG" 2>&1
  say "SMOKE FAILED rc=$src — aborting (lock released), see smoke.log"
  exit 5
fi
say "smoke OK — full extraction"
"$PY" "$HERE/extract_acts.py" >> "$HERE/extract.log" 2>&1
xrc=$?
python3 "$FL" release "$LOCK" --handle "$HANDLE" >> "$LOG" 2>&1
say "extraction rc=$xrc (lock released)"
if [ "$xrc" -ne 0 ]; then say "EXTRACTION FAILED — aborting"; exit 4; fi

# ---- burst 2: readout sweep + conditional stages ----
say "waiting for GPU lock (training)..."
python3 "$FL" acquire "$LOCK" --handle "$HANDLE" --pid-aware --pid $$ --timeout 43200 >> "$LOG" 2>&1
rc=$?
if [ "$rc" -ne 0 ]; then say "LOCK ACQUIRE FAILED rc=$rc — aborting"; exit 3; fi
say "lock held — sweep"
srcfail=0
for t in 0.2 0.5 0.8; do
  for L in 0 2 4 6 8 10 12 14 16 18 20 22; do
    "$PY" "$HERE/train_readout_act.py" --t "$t" --layer "$L" >> "$HERE/sweep.log" 2>&1
    rc=$?
    say "cell t=$t L=$L rc=$rc"
    [ "$rc" -ne 0 ] && srcfail=$((srcfail+1))
  done
done
say "sweep done ($srcfail failed cells) — post_sweep"
"$PY" "$HERE/post_sweep.py" >> "$HERE/sweep.log" 2>&1
prc=$?
python3 "$FL" release "$LOCK" --handle "$HANDLE" >> "$LOG" 2>&1
say "post_sweep rc=$prc (lock released)"
say "=== run_all DONE ==="
touch "$HERE/.RUN_DONE"
exit 0
