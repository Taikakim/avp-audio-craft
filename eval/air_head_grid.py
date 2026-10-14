#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-15)
"""air_head_grid.py -- value x gain grid for the retrained air heads A2 and A5 (Kim 2026-10-15: "request higher values but with less weight").
Third slot on the punch 'cleanest' preset; values {-10, 0, +10} dB x gains {2048, 4096, 8448}; 4 seeds. Raw wavs -> air_head_2026-10-14/grid/; metrics as in air_head_compare
(air share vs original, click rate, drift content vs bass+body). Realised band levels: eval/air_realised_levels.py (mir venv) on the same dir. Render server :8056 up."""
import json, os, shutil, sys
import numpy as np
import soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_rating_server as P
import latch_drift_check as DC
AH = "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-14"
OUT = f"{AH}/grid"; os.makedirs(OUT, exist_ok=True)
HD = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_rms_energy_air_%s_best.pt"
HEADS = {"A2": HD % "a2", "A5": HD % "a5"}
SEEDS, VALUES, GAINS = [764, 1337, 3017, 3050], [-10.0, 0.0, 10.0], [2048.0, 4096.0, 8448.0]
pre = P.load_presets()
def render(name, seed, head=None, v=None, g=None):
    p = f"{OUT}/s{seed}_{name}.wav"
    if os.path.exists(p): return p
    b = P.body(pre, "cleanest", seed, 1.0, 0.45, 30, name != "base")
    if head: b["latch"].append({"path": head, "head": "rms_energy_air", "kind": "constant", "value": v, "gain": g, "start_pct": 0.0, "end_pct": 1.0})
    shutil.copy(P.post(b)["files"][0], p); return p
def clicks(x):
    d = np.diff(x.mean(1) if x.ndim > 1 else x); return float((np.abs(d) > 8 * d.std()).mean() * 1e4)
def air_share(x, sr):
    m = x.mean(1) if x.ndim > 1 else x; S = np.abs(np.fft.rfft(m)) ** 2; f = np.fft.rfftfreq(len(m), 1 / sr)
    return float(10 * np.log10(S[f >= 2500].sum() / S.sum()))
paths = {}
for s in SEEDS:
    paths[(s, "base")] = render("base", s); paths[(s, "bass_body")] = render("bass_body", s)
    for h, hp in HEADS.items():
        for v in VALUES:
            for g in GAINS:
                n = f"{h}_v{v:g}_g{int(g)}"; paths[(s, n)] = render(n, s, hp, v, g)
    print("rendered seed", s, flush=True)
rows = []
for (s, n), p in paths.items():
    x, sr = sf.read(p, dtype="float32"); xb, _ = sf.read(paths[(s, "base")], dtype="float32")
    g = 1.0 if n == "base" else min(float(np.sqrt((xb ** 2).mean()) / np.sqrt((x ** 2).mean())), 0.97 / np.abs(x).max())
    if n != "base": sf.write(p.replace(".wav", "_matched.wav"), x * g, sr, subtype="PCM_16")
    m = DC.measure(p); st = P.stats(x * g, sr)
    rows.append({"seed": s, "arm": n, "air_share_db": air_share(x * g, sr), "clicks_per_1e4": clicks(x * g), "crest": float(st["crest"]), "centroid": float(st["centroid"]),
                 **{k: float(m[k]) for k in ("onset_rate", "hat_rate", "bpm")}})
json.dump(rows, open(f"{OUT}/grid.json", "w"), indent=1)
print("GRID DONE")
