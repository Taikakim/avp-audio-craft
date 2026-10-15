#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-15)
"""air_epoch_sweep.py -- render ONE punch clip (seed 764, bass+body 'cleanest' preset + air head as 3rd slot, -10 dB, gain 24000) with EVERY finite per-epoch checkpoint of
the overnight air-head runs (latch_sweep/air_head_2026-10-15_overnight O1-O5, plus the 1000-step bracket A2 for reference), to see WHERE QUALITY PEAKED.
WHY (Kim 2026-10-15): lr may have been too high for Schedule-Free+; the val loss alone does not say which epoch SOUNDS best. Per clip: air-band share vs the original,
centroid, crest, click rate (screen only: biased by brightness), content drift (onset/hat rate, bpm). Checkpoints with non-finite weights are skipped and listed.
Run (render server :8056 up, SAO/.venv):  .venv/bin/python eval/air_epoch_sweep.py      Output: <overnight>/epoch_sweep/ (clips/*.wav, sweep.json)
Saved checkpoints are EMA weights (half-life 2 ep) for the O arms; A2 used half-life 0.5 ep.
"""
import glob, json, os, re, shutil, sys
import numpy as np
import soundfile as sf
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_rating_server as P
import latch_drift_check as DC

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--dirs", nargs="*", default=None, help="run dirs holding latch_sa3_rms_energy_air_ep*.pt (default: the overnight O1-O5 + bracket A2)")
ap.add_argument("--out", default=None)
ARGS = ap.parse_args()
ON = "/run/media/kim/Mantu/latch_sweep/air_head_2026-10-15_overnight"
A2 = "/run/media/kim/Mantu/latch_sweep/air_head_2026-10-14/A2_d512dp8_lr1e-2"
OUT = ARGS.out or f"{ON}/epoch_sweep"
DIRS = ARGS.dirs if ARGS.dirs else sorted(glob.glob(f"{ON}/O*")) + [A2]
os.makedirs(f"{OUT}/clips", exist_ok=True)
SEED, GAIN, VALUE = 764, 24000.0, -10.0
pre = P.load_presets()


def finite(p):
    sd = torch.load(p, map_location="cpu", weights_only=False)
    sd = sd.get("model", sd.get("state_dict", sd)) if isinstance(sd, dict) else sd
    return all(bool(torch.isfinite(v).all()) for v in sd.values() if torch.is_tensor(v) and v.is_floating_point())


def render(name, head=None):
    p = f"{OUT}/clips/{name}.wav"
    if os.path.exists(p):
        return p
    b = P.body(pre, "cleanest", SEED, 1.0, 0.45, 30, name != "base")
    if head:
        b["latch"].append({"path": head, "head": "rms_energy_air", "kind": "constant", "value": VALUE, "gain": GAIN, "start_pct": 0.0, "end_pct": 1.0})
    shutil.copy(P.post(b)["files"][0], p)
    return p


def clicks(x):
    d = np.diff(x.mean(1)); return float((np.abs(d) > 8 * d.std()).mean() * 1e4)


def air_share(x, sr):
    m = x.mean(1); S = np.abs(np.fft.rfft(m)) ** 2; f = np.fft.rfftfreq(len(m), 1 / sr)
    return float(10 * np.log10(S[f >= 2500].sum() / S.sum()))


jobs, skipped = [], []
for d in DIRS:
    arm = os.path.basename(d).split("_")[0]  # O1..O5, A2, O6, A2b
    for p in sorted(glob.glob(f"{d}/latch_sa3_rms_energy_air_ep*.pt"), key=lambda q: (int(re.search(r"_ep(\d+)", q).group(1)), q)):
        ep = int(re.search(r"_ep(\d+)", p).group(1)); tag = re.search(r"_ep\d+(_ema[\d.]+?|_online)?\.pt", p).group(1) or ""
        if arm == "A2" and ep > 7: continue
        if arm == "A2b" and ep > 7: continue
        (jobs if finite(p) else skipped).append((arm, ep, tag, p)) if True else None
print(f"{len(jobs)} finite checkpoints, {len(skipped)} non-finite skipped", flush=True)
base = render("base"); bm = render("bass_body")
xb, sr = sf.read(base, dtype="float32")
rows = []
def measure(name, p, arm, ep, tag):
    x, _ = sf.read(p, dtype="float32")
    g = float(np.sqrt((xb ** 2).mean()) / np.sqrt((x ** 2).mean())) if name != "base" else 1.0
    g = min(g, 0.97 / np.abs(x).max())
    if name != "base": sf.write(p.replace(".wav", "_matched.wav"), x * g, sr, subtype="PCM_16")
    st = P.stats(x * g, sr); m = DC.measure(p)
    rows.append({"arm": arm, "epoch": ep, "tag": tag, "name": name, "air_share_db": air_share(x * g, sr), "clicks_per_1e4": clicks(x * g),
                 **{k: float(v) for k, v in st.items()}, **{k: float(m[k]) for k in ("onset_rate", "hat_rate", "bpm")}})
measure("base", base, "base", 0, ""); measure("bass_body", bm, "bass_body", 0, "")
for arm, ep, tag, hp in jobs:
    name = f"{arm}_ep{ep:02d}{tag}"
    measure(name, render(name, hp), arm, ep, tag)
    print("done", name, flush=True)
    json.dump({"rows": rows, "skipped": [(a, e, t) for a, e, t, _ in skipped]}, open(f"{OUT}/sweep.json", "w"), indent=1)
print("SWEEP DONE", flush=True)
