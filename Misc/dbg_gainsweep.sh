#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
# Find the gain sweet spot: highest gain with listenable CE AND a real density sweep.
SA3PY=/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python
MIRPY=/home/kim/Projects/mir/mir/bin/python
OPB=/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_Fusion_opb_lr1.5e-4_30ep/riffer_step81000.pt
cd /home/kim/Projects/SAO/stable-audio-tools/avp_sa3 || exit 1
export PYTHONPATH=. FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
LF="$SA3PY sa3_control/steered_longform.py $OPB --shape triangular --lo 2 --hi 14 --duration 60 --window-sec 30 --overlap-sec 5"
wait_gpu(){ for i in $(seq 1 40); do u=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -oiE 'used memory \(b\): [0-9]+' | grep -oE '[0-9]+'); [ "${u:-0}" -lt 2000000000 ] && return; sleep 6; done; }

echo "=== render g1 $(date +%H:%M) ==="; wait_gpu; $LF --gain 1 --out /home/kim/dbg_g1.wav 2>&1 | grep -iE 'steered|OutOfMemory' | tail -1
echo "=== render g2 $(date +%H:%M) ==="; wait_gpu; $LF --gain 2 --out /home/kim/dbg_g2.wav 2>&1 | grep -iE 'steered|OutOfMemory' | tail -1

echo "=== GAIN vs CE vs density-sweep-span (triangular, 60s) $(date +%H:%M) ==="; wait_gpu
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
runs=[(0,'/home/kim/dbg_A0_pure_longform.wav'),(1,'/home/kim/dbg_g1.wav'),(2,'/home/kim/dbg_g2.wav'),
      (3,'/home/kim/dbg_E_lf_gain3sweep.wav'),(6,'/home/kim/steer_smoke.wav')]
print('  gain |  CE  | output density lo..hi (sweep span) | verdict')
for g,p in runs:
    if not os.path.exists(p): print(f'   {g:<3}   MISSING'); continue
    ce=ab(p).get('content_enjoyment',0); lo,hi=dens_span(p)
    v='clean' if ce>=6 else ('borderline' if ce>=5 else 'GLITCHY')
    print(f'   {g:<3} | {ce:4.2f} | {lo:4.1f}..{hi:4.1f}  (span {hi-lo:4.1f})           | {v}')
PYEOF
echo "DBG_GAINSWEEP_DONE"
