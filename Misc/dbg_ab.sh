#!/bin/bash
SA3PY=/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python
MIRPY=/home/kim/Projects/mir/mir/bin/python

echo "=== A0: PURE longform (re-run on clean GPU, no adapter, 60s) $(date +%H:%M) ==="
( cd /home/kim/Projects/SAO/stable-audio-3 && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE $SA3PY scripts/longform_render.py \
    --model medium-base --prompt "goa trance, psychedelic, driving, 145 bpm" --duration 60 --window-sec 30 --overlap-sec 5 \
    -o /home/kim/dbg_A0_pure_longform.wav 2>&1 | grep -iE 'longform|drift|error|Trace|Error' | tail -6 )

echo "=== AUDIOBOX AESTHETICS (Goa baseline: PQ 7.60  CE 6.11  CU 7.46  PC 5.81) $(date +%H:%M) ==="
cd /home/kim/Projects/mir && $MIRPY - <<'PYEOF'
import sys, os; sys.path.insert(0, 'src')
from core.rocm_env import setup_rocm_env; setup_rocm_env()
from timbral.audiobox_aesthetics import analyze_audiobox_aesthetics as ab
clips = [('D  native (no LF, no adapter)', '/home/kim/dbg_D_native_gain0.wav'),
         ('A0 pure longform (no adapter) GATE', '/home/kim/dbg_A0_pure_longform.wav'),
         ('steer_smoke (LF+adapter g6 sweep)', '/home/kim/steer_smoke.wav'),
         ('opb_triangular (glitchy 6min)', '/home/kim/steered_runs/opb_triangular.wav')]
for lbl, p in clips:
    if not os.path.exists(p):
        print(f'  {lbl:38s} MISSING'); continue
    try:
        r = ab(p)
        print(f'  {lbl:38s} PQ {r.get("production_quality",0):.2f}  CE {r.get("content_enjoyment",0):.2f}  '
              f'PC {r.get("production_complexity",0):.2f}  CU {r.get("content_usefulness",0):.2f}')
    except Exception as e:
        print(f'  {lbl:38s} ERR {repr(e)[:90]}')
PYEOF
echo "DBG_AB_DONE"
