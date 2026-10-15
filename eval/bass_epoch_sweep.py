# Owner: GHOST-NOTE (created 2026-10-16), derived from air_epoch_sweep.py
"""bass_epoch_sweep.py -- the bass-head low-lr bracket (latch/run_bass_lr.sh) by ear: render ONE punch clip (seed 764, the 'cleanest' preset) once with the PRODUCTION bass head
(reference) and once per saved checkpoint with that checkpoint swapped into the preset's bass slot (body head stays production). Same level-matching and metrics as air_epoch_sweep.
Checkpoints: ep<N>.pt = EMA 1 ep, ep<N>_ema0.25.pt, ep<N>_online.pt. Run (render server :8056 up, SAO/.venv):  .venv/bin/python eval/bass_epoch_sweep.py --dirs <run dirs> --out <dir>
Added metric: bass share (<150 Hz) vs the unguided clip, since bass RMS is what the head steers.
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
ap.add_argument("--dirs", nargs="*", required=True, help="run dirs holding latch_sa3_rms_energy_bass_ep*.pt")
ap.add_argument("--out", required=True)
ARGS = ap.parse_args()
OUT = ARGS.out
DIRS = ARGS.dirs
os.makedirs(f"{OUT}/clips", exist_ok=True)
SEED = 764
pre = P.load_presets()


def finite(p):
    sd = torch.load(p, map_location="cpu", weights_only=False)
    sd = sd.get("model", sd.get("state_dict", sd)) if isinstance(sd, dict) else sd
    return all(bool(torch.isfinite(v).all()) for v in sd.values() if torch.is_tensor(v) and v.is_floating_point())


def render(name, head=None):
    p = f"{OUT}/clips/{name}.wav"
    if os.path.exists(p):
        return p
    b = P.body(pre, "cleanest", SEED, 1.0, 0.45, 30, name != "base")  # dora strength 0.45 as in the air sweeps
    if head:
        for sl in b["latch"]:
            if sl["head"] == "rms_energy_bass":
                sl["path"] = head
    shutil.copy(P.post(b)["files"][0], p)
    return p


def clicks(x):
    d = np.diff(x.mean(1)); return float((np.abs(d) > 8 * d.std()).mean() * 1e4)


def air_share(x, sr):  # here: BASS share (<150 Hz), key kept as air_share_db so the metrics/page code is reusable
    m = x.mean(1); S = np.abs(np.fft.rfft(m)) ** 2; f = np.fft.rfftfreq(len(m), 1 / sr)
    return float(10 * np.log10(S[f < 150].sum() / S.sum()))


jobs, skipped = [], []
for d in DIRS:
    arm = os.path.basename(d).split("_")[0]  # B2 / B3 / B4
    for p in sorted(glob.glob(f"{d}/latch_sa3_rms_energy_bass_ep*.pt"), key=lambda q: (int(re.search(r"_ep(\d+)", q).group(1)), q)):
        ep = int(re.search(r"_ep(\d+)", p).group(1)); tag = re.search(r"_ep\d+(_ema[\d.]+?|_online)?\.pt", p).group(1) or ""
        (jobs if finite(p) else skipped).append((arm, ep, tag, p)) if True else None
print(f"{len(jobs)} finite checkpoints, {len(skipped)} non-finite skipped", flush=True)
base = render("base"); bm = render("production_bass_body", None)
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
measure("base", base, "base", 0, ""); measure("production_bass_body", bm, "production", 0, "")
for arm, ep, tag, hp in jobs:
    name = f"{arm}_ep{ep:02d}{tag}"
    measure(name, render(name, hp), arm, ep, tag)
    print("done", name, flush=True)
    json.dump({"rows": rows, "skipped": [(a, e, t) for a, e, t, _ in skipped]}, open(f"{OUT}/sweep.json", "w"), indent=1)
print("SWEEP DONE", flush=True)
