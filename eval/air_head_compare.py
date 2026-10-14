#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-15)
"""air_head_compare.py -- the retrained air-RMS heads (modular optimiser bracket, latch_sweep/air_head_2026-10-14) vs the production AdamW head, on a few seeds.

WHY (Kim 2026-10-14/15): the production rms_energy_air head glitches at large guidance weights and changes content, unlike the bass/mid/body heads. This renders
bass+body (fixed, as in the punch 'cleanest' preset) + each air head as a third slot at -10 dB, gain {8448, 24000}, and measures per clip: air-band share vs the
original, centroid/flatness/crest, a CLICK rate (samples whose first difference is >8 sigma, a screen for glitches), and the drift-check CONTENT features
(onset rate, hat rate, tempo; delta vs the unsteered original AND vs bass+body alone, so 'what the air head adds' is isolated). Level-matched wavs are kept.
Run (render server :8056 up):  .venv/bin/python eval/air_head_compare.py     Output: air_head_2026-10-14/compare/
"""
import json, os, shutil, sys
import numpy as np
import soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_rating_server as P
import latch_drift_check as DC

AH = "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-14"
OUT = f"{AH}/compare"
os.makedirs(OUT, exist_ok=True)
HEADS = {"old_adamw": "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_rms_energy_air_best.pt"}
for a in ["A2_d512dp8_lr1e-2", "A4_d512dp8_lr1e-3", "A5_d256dp8_lr1e-2", "A6_d512dp8_lr1e-2_soap"]:
    HEADS[a.split("_")[0] + "_" + a.split("_")[-1] if "soap" in a else a.split("_")[0]] = f"{AH}/{a}/latch_sa3_rms_energy_air_ep7.pt"
SEEDS = [764, 1337, 3017, 3050]
GAINS = [8448.0, 24000.0]
pre = P.load_presets()


def render(name, seed, head=None, gain=None):
    p = f"{OUT}/s{seed}_{name}.wav"
    if os.path.exists(p):
        return p
    b = P.body(pre, "cleanest", seed, 1.0, 0.45, 30, name != "base")
    if head:
        b["latch"].append({"path": head, "head": "rms_energy_air", "kind": "constant", "value": -10.0, "gain": gain, "start_pct": 0.0, "end_pct": 1.0})
    shutil.copy(P.post(b)["files"][0], p)
    return p


def clicks(x):
    d = np.diff(x.mean(1) if x.ndim > 1 else x)
    return float((np.abs(d) > 8 * d.std()).mean() * 1e4)     # per 10k samples


def air_share(x, sr):
    m = x.mean(1) if x.ndim > 1 else x
    S = np.abs(np.fft.rfft(m)) ** 2
    f = np.fft.rfftfreq(len(m), 1 / sr)
    return float(10 * np.log10(S[f >= 2500].sum() / S.sum()))


paths = {}
for s in SEEDS:
    paths[(s, "base")] = render("base", s)
    paths[(s, "bass_body")] = render("bass_body", s)
    for h, hp in HEADS.items():
        for g in GAINS:
            paths[(s, f"{h}_g{int(g)}")] = render(f"{h}_g{int(g)}", s, hp, g)
    print("rendered seed", s, flush=True)
rows = []
for (s, name), p in paths.items():
    x, sr = sf.read(p, dtype="float32")
    xb, _ = sf.read(paths[(s, "base")], dtype="float32")
    g = float(np.sqrt((xb ** 2).mean()) / np.sqrt((x ** 2).mean())) if name != "base" else 1.0
    if name != "base":
        g = min(g, 0.97 / np.abs(x).max())
        sf.write(p.replace(".wav", "_matched.wav"), x * g, sr, subtype="PCM_16")
    st = P.stats(x * g, sr)
    m = DC.measure(p)
    rows.append({"seed": s, "arm": name, "air_share_db": air_share(x * g, sr), "clicks_per_1e4": clicks(x * g), **{k: float(v) for k, v in st.items()},
                 **{k: float(m[k]) for k in ("onset_rate", "hat_rate", "bpm")}})
json.dump(rows, open(f"{OUT}/compare.json", "w"), indent=1)
R = {(r["seed"], r["arm"]): r for r in rows}
arms = ["base", "bass_body"] + [f"{h}_g{int(g)}" for h in HEADS for g in GAINS]
print(f"{'arm':22s} dAir_vs_base  clicks  crest  dOnset/s dHat/s dBPM  | vs bass+body: dOnset dHat dBPM")
for a in arms:
    def mean(f): return float(np.mean([f(R[(s, a)], R[(s, "base")], R[(s, "bass_body")]) for s in SEEDS]))
    print(f"{a:22s} {mean(lambda r,b,bb: r['air_share_db']-b['air_share_db']):+8.2f}   {mean(lambda r,b,bb: r['clicks_per_1e4']):6.2f} {mean(lambda r,b,bb: r['crest']):6.2f}"
          f"  {mean(lambda r,b,bb: r['onset_rate']-b['onset_rate']):+6.2f} {mean(lambda r,b,bb: r['hat_rate']-b['hat_rate']):+6.2f} {mean(lambda r,b,bb: r['bpm']-b['bpm']):+6.2f}"
          f"  | {mean(lambda r,b,bb: r['onset_rate']-bb['onset_rate']):+6.2f} {mean(lambda r,b,bb: r['hat_rate']-bb['hat_rate']):+6.2f} {mean(lambda r,b,bb: r['bpm']-bb['bpm']):+6.2f}")
