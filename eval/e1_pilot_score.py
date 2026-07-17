#!/usr/bin/env python3
"""Score E1 pilot: guided arms vs nl-matched unguided ladder baselines (audio mode)."""
import json, sys
from pathlib import Path
sys.path.insert(0, "/home/kim/Projects/mir/src/tools")
import numpy as np, librosa
from recurrence_meter import calibrate_source, dynamics_stats

PILOT = Path("/run/media/kim/Mantu/sa3_control_runs/e1_pilot_20260716")
BASE = Path("/run/media/kim/Mantu/sa3_lora_runs/a2a_kaikkialla_newstack")
KEYS = ["r_max", "line_frac_8s", "line_frac_16s", "l_max_sec", "det_soft"]

def stats(p):
    y, sr = librosa.load(str(p), sr=22050, mono=True)
    c, d = calibrate_source(y, sr=sr), dynamics_stats(y, sr=sr)
    return {**{k: c.get(k) for k in ("r_max",)}, **{k: d.get(k) for k in KEYS if k != "r_max"}}

base_cache = {}
rows = []
for p in sorted(PILOT.glob("e1_nl*.wav")):
    nl = p.name.split("_")[1][2:]
    b = BASE / f"a2a_nl{nl}.wav"
    if nl not in base_cache:
        base_cache[nl] = stats(b)
    s, bs = stats(p), base_cache[nl]
    row = {"clip": p.name, **{k: round(s[k], 3) for k in KEYS},
           **{f"d_{k}": round(s[k] - bs[k], 3) for k in KEYS}}
    rows.append(row)
    print("%-22s lf8 %.3f (Δ%+.3f)  lf16 %.3f (Δ%+.3f)  lmax %4.0fs (Δ%+4.0f)  dsoft %.4f (Δ%+.4f)  rmax %.3f (Δ%+.3f)" % (
        p.name.replace(".wav",""), row["line_frac_8s"], row["d_line_frac_8s"], row["line_frac_16s"],
        row["d_line_frac_16s"], row["l_max_sec"], row["d_l_max_sec"], row["det_soft"], row["d_det_soft"],
        row["r_max"], row["d_r_max"]), flush=True)
for nl, bs in sorted(base_cache.items()):
    print("baseline nl%s: lf8 %.3f lf16 %.3f lmax %.0fs dsoft %.4f rmax %.3f" % (
        nl, bs["line_frac_8s"], bs["line_frac_16s"], bs["l_max_sec"], bs["det_soft"], bs["r_max"]))
(PILOT / "pilot_scores.json").write_text(json.dumps({"rows": rows, "baselines": base_cache}, indent=1))
print("wrote pilot_scores.json")
