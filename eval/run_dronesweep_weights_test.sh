#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-16)
# run_dronesweep_weights_test.sh -- the AVP drone-sweep weights test (eval/dronesweep_weights_test.py, 72 renders + 3 ckpt loads)
# in the free afternoon slot: waits for the E12 night chain (FiLM full run) to finish, then the GPU lock + free VRAM; encodes, scores.
#   bash eval/run_dronesweep_weights_test.sh        (run in background)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/sa3_control_runs/dronesweep_weights_20261016
STAGE=$HOME/evals_aac/dronesweep_weights
MIR_PY=/home/kim/Projects/mir/mir/bin/python
export ROCR_VISIBLE_DEVICES=0 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
cd "$SAO" || exit 2
while pgrep -f "^bash (/home/kim/Projects/SAO/)?eval/run_film_e12_night\.sh$" >/dev/null; do
    echo "$(date +%H:%M) E12 night chain still running"; sleep 300
done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE drone-sweep weights test (EMA/online/base-blend/anchor, 72 renders), ~30 min" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
echo "$(date +%H:%M) GPU acquired"
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
"$SAO/.venv/bin/python" eval/dronesweep_weights_test.py
echo "$(date +%H:%M) render rc=$?; cells written: $(wc -l < "$OUT/cells.jsonl") / 72"
mkdir -p "$STAGE"
for w in "$OUT"/*.wav; do
    d="$STAGE/$(basename "$w" .wav).m4a"; [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 128k "$1"'
"$MIR_PY" control/sa3_control/clip_metrics.py --roots dronesweep_weights --workers 12 2>&1 | tail -1
"$MIR_PY" control/sa3_control/clip_metrics_audiobox.py --roots dronesweep_weights 2>&1 | tail -1
echo "$(date +%H:%M) ALL DONE"
