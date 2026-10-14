#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-14)
"""air_head_bracket.py -- bracket the rms_energy_air head (value x gain) on ONE clip, bass+body heads fixed as in the 'cleanest' punch preset.

WHY (Kim 2026-10-14): the air head at the training median (-30.3 dB, gain 8448) made the 64 punch clips darker, not brighter. Which value/gain, if any,
lifts the 2.5-22 kHz band? Measured directly: air-band RMS (dB) and air minus total RMS (dB, loudness-free), plus centroid/zcr/crest. Level-matched wavs kept.
Usage: .venv/bin/python eval/air_head_bracket.py [seed]   (render server :8056 must be up)
"""
import json, os, sys, shutil
import numpy as np
import soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_rating_server as P

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 764
OUT = f"{P.DATA}/air_bracket_s{seed}"
os.makedirs(OUT, exist_ok=True)
pre = P.load_presets()
VALUES = [-30.33, -20.0, -10.0, 0.0]
GAINS = [2048.0, 8448.0, 24000.0]


def air_db(x, sr):
    m = x.mean(1) if x.ndim > 1 else x
    S = np.fft.rfft(m * 1.0)
    f = np.fft.rfftfreq(len(m), 1 / sr)
    tot = np.sqrt((np.abs(S) ** 2).sum() + 1e-20)
    air = np.sqrt((np.abs(S[f >= 2500]) ** 2).sum() + 1e-20)
    return 20 * np.log10(air / np.sqrt(len(m))), 20 * np.log10(air / tot)


def run(name, steered, air=None):
    if os.path.exists(f"{OUT}/{name}.wav"):
        return f"{OUT}/{name}.wav"          # resume: already rendered
    b = P.body(pre, "cleanest", seed, 1.0, 0.45, 30, steered)
    if air:
        b["latch"].append({"head": "rms_energy_air", "kind": "constant", "value": air[0], "gain": air[1], "start_pct": 0.0, "end_pct": 1.0})
    r = P.post(b)
    p = f"{OUT}/{name}.wav"
    shutil.copy(r["files"][0], p)
    return p


rows = []
arms = [("base", False, None), ("bass_body", True, None)] + [(f"air_v{v:g}_g{g:g}", True, (v, g)) for v in VALUES for g in GAINS]
paths = {}
for name, st, air in arms:
    paths[name] = run(name, st, air)
    print(name, flush=True)
xb, sr = sf.read(paths["base"], dtype="float32")
rb = np.sqrt((xb ** 2).mean())
for name, _, air in arms:
    x, _ = sf.read(paths[name], dtype="float32")
    g = rb / np.sqrt((x ** 2).mean()); g = min(g, 0.97 / np.abs(x).max()) if name != "base" else 1.0
    sf.write(f"{OUT}/{name}_matched.wav", x * g, sr, subtype="PCM_16")
    s = P.stats(x * g, sr)
    a_abs, a_rel = air_db(x * g, sr)
    rows.append({"arm": name, "air_value": air[0] if air else None, "air_gain": air[1] if air else None, "air_band_db": float(a_abs), "air_minus_total_db": float(a_rel), **{k: float(v) for k, v in s.items()}})
json.dump({"purpose": "air head value x gain bracket on one clip", "seed": seed, "rows": rows}, open(f"{OUT}/bracket.json", "w"), indent=1)
b0 = rows[0]["air_minus_total_db"]
print(f"{'arm':22s} air_dB  air-tot  d_vs_base  centroid  flat   crest")
for r in rows:
    print(f"{r['arm']:22s} {r['air_band_db']:6.1f} {r['air_minus_total_db']:7.1f} {r['air_minus_total_db']-b0:+8.1f}  {r['centroid']:7.0f}  {r['flat']:.3f}  {r['crest']:.2f}")
