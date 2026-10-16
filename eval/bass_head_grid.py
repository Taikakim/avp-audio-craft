#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-16), derived from air_head_grid.py
"""bass_head_grid.py -- weight (gain) x target (value) matrices for the bass-head lr bracket's FINAL epochs (owner 2026-10-16: "all of these sound the same ... we could make
weight x target matrices of the final eps"). The bass_lr.html sweep used the preset's own bass slot (value -10.0 dB, gain 8448), where every new head moved the <150 Hz share by <0.4 dB.
Here the bass slot of the punch 'cleanest' preset is replaced by each head (production, B2 lr 1e-2, B3 lr 1e-3, B4 lr 1e-4; final epoch ep10 = EMA 1 ep) with
values {-16,-10,-4} dB x gains {1x,2x,4x,8x of 8448}; rho/mu stay as the preset; body slot unchanged; seeds 764 and 3050. Render server :8056 up (SAO/.venv)."""
import json, os, shutil, sys
import numpy as np
import soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_rating_server as P
import latch_drift_check as DC
RUN = "/run/media/kim/Mantu/latch_sweep/bass_lr_2026-10-16"
OUT = f"{RUN}/grid"; os.makedirs(OUT, exist_ok=True)
HEADS = {"production": None, "B2": f"{RUN}/B2_bass_d512_lr1e-2/latch_sa3_rms_energy_bass_ep10.pt", "B3": f"{RUN}/B3_bass_d512_lr1e-3/latch_sa3_rms_energy_bass_ep10.pt",
         "B4": f"{RUN}/B4_bass_d512_lr1e-4/latch_sa3_rms_energy_bass_ep10.pt"}
SEEDS, VALUES, MULTS = [764, 3050], [-16.0, -10.0, -4.0], [1, 2, 4, 8]
pre = P.load_presets()
def render(name, seed, head=None, v=None, mult=None, steered=True):
    p = f"{OUT}/s{seed}_{name}.wav"
    if os.path.exists(p): return p
    b = P.body(pre, "cleanest", seed, 1.0, 0.45, 30, steered)
    if steered and v is not None:
        for sl in b["latch"]:
            if sl["head"] == "rms_energy_bass":
                if head: sl["path"] = head
                sl["value"] = v; sl["gain"] = sl["gain"] * mult
    shutil.copy(P.post(b)["files"][0], p); return p
def share(x, sr):
    m = x.mean(1) if x.ndim > 1 else x; S = np.abs(np.fft.rfft(m)) ** 2; f = np.fft.rfftfreq(len(m), 1 / sr)
    return float(10 * np.log10(S[f < 150].sum() / S.sum()))
def clicks(x):
    d = np.diff(x.mean(1) if x.ndim > 1 else x); return float((np.abs(d) > 8 * d.std()).mean() * 1e4)
paths = {}
for s in SEEDS:
    paths[(s, "base")] = render("base", s, steered=False); paths[(s, "preset")] = render("preset", s)
    for h, hp in HEADS.items():
        for v in VALUES:
            for m in MULTS:
                n = f"{h}_v{v:g}_x{m}"; paths[(s, n)] = render(n, s, hp, v, m)
    print("rendered seed", s, flush=True)
rows = []
for (s, n), p in paths.items():
    x, sr = sf.read(p, dtype="float32"); xb, _ = sf.read(paths[(s, "base")], dtype="float32")
    g = 1.0 if n == "base" else min(float(np.sqrt((xb ** 2).mean()) / np.sqrt((x ** 2).mean())), 0.97 / np.abs(x).max())
    if n != "base": sf.write(p.replace(".wav", "_matched.wav"), x * g, sr, subtype="PCM_16")
    m = DC.measure(p); st = P.stats(x * g, sr)
    rows.append({"seed": s, "arm": n, "bass_share_db": share(x * g, sr), "clicks_per_1e4": clicks(x * g), "crest": float(st["crest"]), "centroid": float(st["centroid"]),
                 **{k: float(m[k]) for k in ("onset_rate", "hat_rate", "bpm")}})
json.dump(rows, open(f"{OUT}/grid.json", "w"), indent=1)
print("GRID DONE")
