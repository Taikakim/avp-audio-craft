"""Measure the ema_help renders (did EMA help the retrained heads steer?). mir venv."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, "/home/kim/Projects/mir/src")
from latch_sa3_sweep_measure import measure, read_audio  # reuse the exact extractors
OUT = "/run/media/kim/Mantu/sa3_control_runs/ema_help_20260719"
man = json.load(open(os.path.join(OUT, "ema_help_manifest.json")))
res = {}   # (feature,gain) -> {variant: (measured, target)}
for c in man:
    p = os.path.join(OUT, c["clip"])
    if not os.path.exists(p): continue
    try:
        audio, sr = read_audio(p)
        mono = audio.mean(axis=1).astype(np.float32) if audio.ndim > 1 else audio.astype(np.float32)
        m = measure(c["feature"], mono, sr)
    except Exception as e:
        m = None
    if m is None: continue
    res.setdefault((c["feature"], c["gain"]), {})[c["variant"]] = (m, c["target"])
# report: for each feature, does ema move measured CLOSER to the (high) target than shipped?
print(f"{'feature':20s} {'gain':>6s} {'target':>9s} {'shipped':>9s} {'ema20':>9s} {'ema40':>9s}  best")
feat_win = {}
for (feat, gain), d in sorted(res.items()):
    tgt = list(d.values())[0][1]
    sh = d.get('shipped',(None,))[0]; e2 = d.get('ema20',(None,))[0]; e4 = d.get('ema40',(None,))[0]
    def toward(v): return abs(v-tgt) if v is not None else 9e9  # closer to target = better steering
    cands = {'shipped':toward(sh),'ema20':toward(e2),'ema40':toward(e4)}
    best = min(cands, key=cands.get)
    feat_win.setdefault(feat, []).append(best)
    f=lambda v:f"{v:9.3f}" if v is not None else "     -   "
    print(f"{feat:20s} {int(gain):6d} {tgt:9.3f} {f(sh)} {f(e2)} {f(e4)}  {best}")
print("\n=== per-feature: which variant steered closest to target most often ===")
for feat, wins in feat_win.items():
    from collections import Counter
    print(f"  {feat:20s} {dict(Counter(wins))}")
