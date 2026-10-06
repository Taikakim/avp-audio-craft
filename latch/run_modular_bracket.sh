#!/usr/bin/env bash
# run_modular_bracket.sh — sequential LatCH arms for the modular-optimizer bracket (C, 2026-09-30).
# Kim: re-check the May LatCH findings (width, batch, lr, optimizer) under the new ModularOptimizer,
# then try likely-good combinations. One arm at a time; each takes the GPU through gpu_guard and
# WAITS (does not skip) when another instance holds it -- W works on the GUI on the same card.
#
# usage: bash latch/run_modular_bracket.sh <armfile> <out_root>
#   armfile: one arm per line:  <name> <extra train_latch args...>   (# comments ok)
# Per arm: <out_root>/<name>/train.log, weights, and a line in <out_root>/SUMMARY.tsv
# (name, wall_s, best_val, last_val, args). Resumable: an arm with a SUMMARY line is skipped.
set -uo pipefail
ARMS=$1; OUT=$2
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
# SAVE_ALL=1: keep every epoch checkpoint (needed for weight-trajectory analytics) instead of only the best.
SAVE_FLAG="--save-best-only"; [ "${SAVE_ALL:-0}" = "1" ] && SAVE_FLAG=""
mkdir -p "$OUT"; touch "$OUT/SUMMARY.tsv"
cd /tmp || exit 1
while read -r name rest; do
  [[ -z "${name:-}" || "$name" == \#* ]] && continue
  if grep -q "^${name}	" "$OUT/SUMMARY.tsv"; then echo "[bracket] skip $name (done)"; continue; fi
  # SHARE_GPU=1: Kim's explicit OK to run beside another instance's job (enough VRAM free, 2026-10-06).
  # Skips the lock entirely -- the lock exists because two concurrent GPU jobs hard-crashed the box in July.
  if [ "${SHARE_GPU:-0}" != "1" ]; then
    until "$SAO/Misc/gpu_guard.sh" acquire CONTINUITY $$ >/dev/null 2>&1; do
      echo "[bracket] GPU busy, waiting 120 s before $name"; sleep 120
    done
  else
    echo "[bracket] SHARE_GPU=1: not taking the GPU lock for $name"
  fi
  mkdir -p "$OUT/$name"
  echo "[bracket] start $name: $rest"
  t0=$(date +%s)
  # shellcheck disable=SC2086
  $PY "$TRAIN" $rest --save-dir "$OUT/$name" --run-name "$name" $SAVE_FLAG > "$OUT/$name/train.log" 2>&1
  rc=$?
  t1=$(date +%s)
  [ "${SHARE_GPU:-0}" != "1" ] && "$SAO/Misc/gpu_guard.sh" release CONTINUITY >/dev/null 2>&1
  best=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | cut -d= -f2 | sort -g | head -1)
  last=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | tail -1 | cut -d= -f2)
  printf '%s\t%s\t%s\t%s\trc=%s\t%s\n' "$name" "$((t1 - t0))" "${best:-NA}" "${last:-NA}" "$rc" "$rest" >> "$OUT/SUMMARY.tsv"
  echo "[bracket] done $name in $((t1 - t0)) s, best val ${best:-NA} (rc $rc; teardown segfaults after saving are known)"
done < "$ARMS"
echo "[bracket] ALL DONE"
