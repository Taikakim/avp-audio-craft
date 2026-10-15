#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-15)
"""dora_blend_bracket.py -- asymmetric DoRA-vs-base blending across DiT blocks on the punch clips (owner's idea 2026-10-15: "mix some of the original model back in in the latter layers
where the texture is created", on the DoRA alone and/or on top of the LatCH steering). The 'cleanest' punch preset = DoRA (strength 0.45) + bass/body LatCH; the profile multiplies the
DoRA strength per block (render server dora.block_strengths, dora.blend). Two blend semantics: default = scale only the low-rank direction (magnitude stays full); 'interp' = true weight
interpolation W + s(W_dora - W). Per clip: air-band share vs the original, centroid / flatness / crest, click screen (biased by brightness), onset/hat/bpm drift vs the unprofiled render.
Run (render server up WITH the profile patch):  .venv/bin/python eval/dora_blend_bracket.py     Output: Mantu2/latch_sweep/dora_blend_2026-10-15/ (clips/*.wav, bracket.json)
"""
import json, os, shutil, sys
import numpy as np
import soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_rating_server as P
import latch_drift_check as DC

OUT = "/run/media/kim/Mantu/latch_sweep/dora_blend_2026-10-15"
os.makedirs(f"{OUT}/clips", exist_ok=True)
SEEDS = [764, 1337, 3017, 3050]
pre = P.load_presets()
# name -> (steered(bool: latch heads on), block_strengths, blend)
ARMS = {
    "base": (False, None, None),
    "cleanest": (True, None, None),
    "late12_x0.5": (True, {"12-23": 0.5}, None),
    "late12_x0": (True, {"12-23": 0.0}, None),
    "late16_x0": (True, {"16-23": 0.0}, None),
    "late12_x0.5_interp": (True, {"12-23": 0.5}, "interp"),
    "late12_x0_interp": (True, {"12-23": 0.0}, "interp"),
    "early12_x0_control": (True, {"0-11": 0.0}, None),
    "doraonly_late12_x0.5": ("dora_only", {"12-23": 0.5}, None),
    "doraonly_late12_x0": ("dora_only", {"12-23": 0.0}, None),
}


def render(name, seed):
    p = f"{OUT}/clips/s{seed}_{name}.wav"
    if os.path.exists(p):
        return p
    mode, prof, blend = ARMS[name]
    b = P.body(pre, "cleanest", seed, 1.0, 0.45, 30, name != "base")
    if mode == "dora_only":
        b["latch"] = []
    if prof or blend:
        b["dora"] = {**(b.get("dora") or {}), **({"block_strengths": prof} if prof else {}), **({"blend": blend} if blend else {})}
    shutil.copy(P.post(b)["files"][0], p)
    return p


def clicks(x):
    d = np.diff(x.mean(1)); return float((np.abs(d) > 8 * d.std()).mean() * 1e4)


def air_share(x, sr):
    m = x.mean(1); S = np.abs(np.fft.rfft(m)) ** 2; f = np.fft.rfftfreq(len(m), 1 / sr)
    return float(10 * np.log10(S[f >= 2500].sum() / S.sum()))


rows = []
for s in SEEDS:
    paths = {n: render(n, s) for n in ARMS}
    xb, sr = sf.read(paths["base"], dtype="float32")
    for n, p in paths.items():
        x, _ = sf.read(p, dtype="float32")
        g = float(np.sqrt((xb ** 2).mean()) / np.sqrt((x ** 2).mean())) if n != "base" else 1.0
        g = min(g, 0.97 / np.abs(x).max())
        if n != "base":
            sf.write(p.replace(".wav", "_matched.wav"), x * g, sr, subtype="PCM_16")
        st = P.stats(x * g, sr); m = DC.measure(p)
        rows.append({"seed": s, "arm": n, "air_share_db": air_share(x * g, sr), "clicks_per_1e4": clicks(x * g), **{k: float(v) for k, v in st.items()},
                     **{k: float(m[k]) for k in ("onset_rate", "hat_rate", "bpm")}})
    print("seed", s, "done", flush=True)
    json.dump(rows, open(f"{OUT}/bracket.json", "w"), indent=1)
R = {(r["seed"], r["arm"]): r for r in rows}
print(f"{'arm':26s} dAir  dCentroid dFlat  dCrest  clicks  dOnset dHat  (vs ORIGINAL, level-matched, mean of {len(SEEDS)} seeds)")
for a in ARMS:
    f = lambda k: float(np.mean([R[(s, a)][k] - R[(s, "base")][k] for s in SEEDS]))
    print(f"{a:26s} {f('air_share_db'):+5.2f} {f('centroid'):+8.0f} {f('flat'):+7.4f} {f('crest'):+6.2f} {np.mean([R[(s,a)]['clicks_per_1e4'] for s in SEEDS]):6.2f} {f('onset_rate'):+6.2f} {f('hat_rate'):+6.2f}")
