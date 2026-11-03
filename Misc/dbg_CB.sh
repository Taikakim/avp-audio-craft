#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
# Re-run C (working-path discriminator) + B (sweep discriminator) with a GPU-drain wait
# between renders to dodge the VRAM-release race.
SA3PY=/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python
MIRPY=/home/kim/Projects/mir/mir/bin/python
OPB=/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_Fusion_opb_lr1.5e-4_30ep/riffer_step81000.pt
cd /home/kim/Projects/SAO/stable-audio-tools/avp_sa3 || exit 1
export PYTHONPATH=. FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE

wait_gpu(){ for i in $(seq 1 40); do
  u=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -oiE 'used memory \(b\): [0-9]+' | grep -oE '[0-9]+');
  [ "${u:-0}" -lt 2000000000 ] && { echo "  [gpu free: $((${u:-0}/1048576))MB]"; return; }; sleep 6; done; echo "  [gpu still busy]"; }

echo "=== C: onset_eval (sam.generate WORKING path) gain 6 density 8, 20s $(date +%H:%M) ==="; wait_gpu
$SA3PY sa3_control/onset_eval.py $OPB --gains 6 --densities 8 --duration 20 --seed 777 --out /tmp/dbg_oe6 2>&1 | grep -iE 'wrote|->|error|OutOfMemory' | tail -2
cp /tmp/dbg_oe6/onset_g6_d8.wav /home/kim/dbg_C_native_gain6.wav 2>/dev/null && echo "  C saved" || echo "  C MISSING"

echo "=== B: longform gain 6 CONSTANT density 8, 60s $(date +%H:%M) ==="; wait_gpu
$SA3PY sa3_control/steered_longform.py $OPB --shape triangular --gain 6 --lo 8 --hi 8 --duration 60 --window-sec 30 --overlap-sec 5 --out /home/kim/dbg_B_lf_gain6const.wav 2>&1 | grep -iE 'steered|error|OutOfMemory' | tail -2

echo "=== AUDIOBOX (A0 clean CE7.19 | g6-sweep CE3.80 | g3-sweep CE5.51) $(date +%H:%M) ==="; wait_gpu
cd /home/kim/Projects/mir && $MIRPY - <<'PYEOF'
import sys, os; sys.path.insert(0, 'src')
from core.rocm_env import setup_rocm_env; setup_rocm_env()
from timbral.audiobox_aesthetics import analyze_audiobox_aesthetics as ab
for lbl, p in [('C  native sam.generate g6 (WORKING path)', '/home/kim/dbg_C_native_gain6.wav'),
               ('B  longform g6 CONSTANT (no sweep)', '/home/kim/dbg_B_lf_gain6const.wav')]:
    if not os.path.exists(p): print(f'  {lbl:42s} MISSING'); continue
    try:
        r = ab(p)
        print(f'  {lbl:42s} PQ {r.get("production_quality",0):.2f}  CE {r.get("content_enjoyment",0):.2f}  '
              f'PC {r.get("production_complexity",0):.2f}  CU {r.get("content_usefulness",0):.2f}')
    except Exception as e:
        print(f'  {lbl:42s} ERR {repr(e)[:90]}')
PYEOF
echo "DBG_CB_DONE"
