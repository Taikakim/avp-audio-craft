#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
SA3PY=/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python
MIRPY=/home/kim/Projects/mir/mir/bin/python
OPB=/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_Fusion_opb_lr1.5e-4_30ep/riffer_step81000.pt
cd /home/kim/Projects/SAO/stable-audio-tools/avp_sa3 || exit 1
export PYTHONPATH=. FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
wait_gpu(){ for i in $(seq 1 40); do u=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -oiE 'used memory \(b\): [0-9]+' | grep -oE '[0-9]+'); [ "${u:-0}" -lt 2000000000 ] && return; sleep 6; done; }

echo "=== unit tests (no break) $(date +%H:%M) ==="
$SA3PY -m pytest sa3_control/tests/test_density_schedule.py sa3_control/tests/test_steered_generator.py -q 2>&1 | tail -4

echo "=== RIDGE render (triangular 2->14, gain-per-density) $(date +%H:%M) ==="; wait_gpu
$SA3PY sa3_control/steered_longform.py $OPB --shape triangular --lo 2 --hi 14 --duration 60 --window-sec 30 --overlap-sec 5 --ridge --out /home/kim/dbg_ridge.wav 2>&1 | grep -iE 'steered|error|OutOfMemory' | tail -2

echo "=== Audiobox CE + density-span  (A0 clean 7.19 | g6 sweep 3.80-5.05 | g3 5.51) $(date +%H:%M) ==="; wait_gpu
cd /home/kim/Projects/mir && $MIRPY - <<'PYEOF'
import sys, os; sys.path.insert(0, 'src')
from core.rocm_env import setup_rocm_env; setup_rocm_env()
from timbral.audiobox_aesthetics import analyze_audiobox_aesthetics as ab
import numpy as np, librosa
def dens_span(p):
    y,sr=librosa.load(p,sr=22050,mono=True); w=int(8*sr); h=int(4*sr); ds=[]
    for s in range(0,max(1,len(y)-w+1),h):
        seg=y[s:s+w]; on=librosa.onset.onset_detect(y=seg,sr=sr,units='time'); ds.append(len(on)/(len(seg)/sr))
    return (min(ds),max(ds)) if ds else (0,0)
p='/home/kim/dbg_ridge.wav'
if os.path.exists(p):
    r=ab(p); lo,hi=dens_span(p)
    v='CLEAN' if r['content_enjoyment']>=6 else ('borderline' if r['content_enjoyment']>=5 else 'glitchy')
    print(f"  RIDGE triangular: CE {r['content_enjoyment']:.2f}  PQ {r['production_quality']:.2f}  density {lo:.1f}..{hi:.1f} (span {hi-lo:.1f})  -> {v}")
else:
    print('  RIDGE render MISSING')
PYEOF
echo "DBG_RIDGE_DONE"
