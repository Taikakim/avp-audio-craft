#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
# Phase-1 isolation for the glitchy steered longform. Each clip changes ONE variable.
cd /home/kim/Projects/SAO/stable-audio-tools/avp_sa3 || exit 1
SA3PY=/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python
MIRPY=/home/kim/Projects/mir/mir/bin/python
OPB=/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_Fusion_opb_lr1.5e-4_30ep/riffer_step81000.pt
export PYTHONPATH=. FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
LF="$SA3PY sa3_control/steered_longform.py $OPB --duration 60 --window-sec 30 --overlap-sec 5"

echo "=== A: longform, gain 0 (NO control) — tests the paradigm alone $(date +%H:%M) ==="
$LF --shape triangular --gain 0 --lo 2 --hi 14 --out /home/kim/dbg_A_gain0.wav 2>&1 | grep -iE 'steered|error|Trace' | tail -3
echo "=== B: longform, gain 6 CONSTANT density 8 — high gain, no sweep $(date +%H:%M) ==="
$LF --shape triangular --gain 6 --lo 8 --hi 8 --out /home/kim/dbg_B_gain6const.wav 2>&1 | grep -iE 'steered|error|Trace' | tail -3
echo "=== C+D: onset_eval (NATIVE single-window, no longform code) gain 0 + gain 6, density 8, 20s $(date +%H:%M) ==="
$SA3PY sa3_control/onset_eval.py $OPB --gains 0,6 --densities 8 --duration 20 --seed 777 --out /tmp/dbg_oe6 2>&1 | grep -iE 'wrote|corr|->' | tail -4
cp /tmp/dbg_oe6/onset_g0_d8.wav /home/kim/dbg_D_native_gain0.wav 2>/dev/null   # native baseline (no control, no longform)
cp /tmp/dbg_oe6/onset_g6_d8.wav /home/kim/dbg_C_native_gain6.wav 2>/dev/null   # native + control gain 6 (no longform)

echo "=== MEASURE: windowed RMS stability (glitch proxy) + onset density $(date +%H:%M) ==="
$MIRPY - <<'PY'
import numpy as np, librosa, glob, os
def report(p):
    if not os.path.exists(p): return f"  {os.path.basename(p):24s} MISSING"
    y,sr=librosa.load(p,sr=22050,mono=True)
    w=int(0.25*sr); rms=np.array([np.sqrt((y[i:i+w]**2).mean()) for i in range(0,len(y)-w,w)])
    jump=np.abs(np.diff(rms)).max() if len(rms)>1 else 0
    on=librosa.onset.onset_detect(y=y,sr=sr,units='time'); dens=len(on)/(len(y)/sr)
    return f"  {os.path.basename(p):24s} dur {len(y)/sr:4.1f}s  RMS {rms.min():.3f}-{rms.max():.3f}  max-jump {jump:.3f}  onset/s {dens:.1f}"
for p in ["/home/kim/dbg_D_native_gain0.wav","/home/kim/dbg_C_native_gain6.wav","/home/kim/dbg_A_gain0.wav","/home/kim/dbg_B_gain6const.wav","/home/kim/steer_smoke.wav","/home/kim/steered_runs/opb_triangular.wav"]:
    print(report(p))
PY
echo "DBG_GLITCH_DONE"
