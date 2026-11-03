#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
# THE GATE: does the longform machinery work WITHOUT any adapter at all?
SA3PY=/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python
MIRPY=/home/kim/Projects/mir/mir/bin/python
OPB=/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_Fusion_opb_lr1.5e-4_30ep/riffer_step81000.pt
PROMPT="goa trance, psychedelic, driving, 145 bpm"

echo "=== A0: PURE longform, NO adapter installed (longform_render.py, medium-base, 60s) $(date +%H:%M) ==="
( cd /home/kim/Projects/SAO/stable-audio-3 && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE $SA3PY scripts/longform_render.py \
    --model medium-base --prompt "$PROMPT" --duration 60 --window-sec 30 --overlap-sec 5 \
    -o /home/kim/dbg_A0_pure_longform.wav 2>&1 | grep -iE 'longform|drift|error|Trace|Error' | tail -6 )

echo "=== D: NATIVE single-window floor — no longform, no adapter (onset_eval gain 0, 20s) $(date +%H:%M) ==="
( cd /home/kim/Projects/SAO/stable-audio-tools/avp_sa3 && PYTHONPATH=. FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE $SA3PY \
    sa3_control/onset_eval.py $OPB --gains 0 --densities 8 --duration 20 --seed 777 --out /tmp/dbg_oe0 2>&1 | grep -iE 'wrote|->' | tail -2 )
cp /tmp/dbg_oe0/onset_g0_d8.wav /home/kim/dbg_D_native_gain0.wav 2>/dev/null

echo "=== MEASURE: windowed RMS stability (max-jump = glitch proxy) + onset density $(date +%H:%M) ==="
$MIRPY - <<'PY'
import numpy as np, librosa, os
def report(p, lbl):
    if not os.path.exists(p): return f"  {lbl:34s} MISSING"
    y,sr=librosa.load(p,sr=22050,mono=True)
    w=int(0.25*sr); rms=np.array([np.sqrt((y[i:i+w]**2).mean()) for i in range(0,len(y)-w,w)])
    jump=float(np.abs(np.diff(rms)).max()) if len(rms)>1 else 0.0
    on=librosa.onset.onset_detect(y=y,sr=sr,units='time'); dens=len(on)/(len(y)/sr)
    return f"  {lbl:34s} {len(y)/sr:5.1f}s  RMS {rms.min():.3f}-{rms.max():.3f}  max-jump {jump:.3f}  onset/s {dens:.1f}"
print(report("/home/kim/dbg_D_native_gain0.wav",   "D  native (no LF, no adapter)"))
print(report("/home/kim/dbg_A0_pure_longform.wav", "A0 pure longform (no adapter) [GATE]"))
print(report("/home/kim/steer_smoke.wav",          "steer_smoke (LF+adapter g6 sweep)"))
print(report("/home/kim/steered_runs/opb_triangular.wav", "opb_triangular (glitchy 6min)"))
PY
echo "DBG_BASELINE_DONE"
