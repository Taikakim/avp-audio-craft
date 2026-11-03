#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
# Narrow WHY the active control adapter degrades CE: gain vs path vs sweep.
SA3PY=/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python
MIRPY=/home/kim/Projects/mir/mir/bin/python
OPB=/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_Fusion_opb_lr1.5e-4_30ep/riffer_step81000.pt
cd /home/kim/Projects/SAO/stable-audio-tools/avp_sa3 || exit 1
export PYTHONPATH=. FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
LF="$SA3PY sa3_control/steered_longform.py $OPB --duration 60 --window-sec 30 --overlap-sec 5"

echo "=== C: onset_eval (sam.generate WORKING path) gain 6 density 8, 20s — path discriminator $(date +%H:%M) ==="
$SA3PY sa3_control/onset_eval.py $OPB --gains 6 --densities 8 --duration 20 --seed 777 --out /tmp/dbg_oe6 2>&1 | grep -iE 'wrote|->' | tail -2
cp /tmp/dbg_oe6/onset_g6_d8.wav /home/kim/dbg_C_native_gain6.wav 2>/dev/null

echo "=== B: longform gain 6 CONSTANT density 8 (no sweep) — sweep discriminator $(date +%H:%M) ==="
$LF --shape triangular --gain 6 --lo 8 --hi 8 --out /home/kim/dbg_B_lf_gain6const.wav 2>&1 | grep -iE 'steered|error|Trace' | tail -2

echo "=== E: longform gain 3 sweep (lower gain) — gain fix candidate $(date +%H:%M) ==="
$LF --shape triangular --gain 3 --lo 2 --hi 14 --out /home/kim/dbg_E_lf_gain3sweep.wav 2>&1 | grep -iE 'steered|error|Trace' | tail -2

echo "=== AUDIOBOX (Goa baseline PQ7.60 CE6.11 | A0 clean PQ7.85 CE7.19 | g6-sweep CE3.80) $(date +%H:%M) ==="
cd /home/kim/Projects/mir && $MIRPY - <<'PYEOF'
import sys, os; sys.path.insert(0, 'src')
from core.rocm_env import setup_rocm_env; setup_rocm_env()
from timbral.audiobox_aesthetics import analyze_audiobox_aesthetics as ab
clips = [('C  native sam.generate g6 (path)', '/home/kim/dbg_C_native_gain6.wav'),
         ('B  longform g6 CONSTANT (no sweep)', '/home/kim/dbg_B_lf_gain6const.wav'),
         ('E  longform g3 sweep (lower gain)', '/home/kim/dbg_E_lf_gain3sweep.wav')]
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
echo "DBG_ISOLATE_DONE"
