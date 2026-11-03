#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-11-03)
"""d10_melody_intermittency.py -- EXPERIMENTS D10 (2026-08-20): does melody form in a few crucial sampling updates, or smoothly?

Records x0_hat at every Euler step of 42 unguided medium-base renders (14 canonical prompts x 3 seeds, 20 s, 50 steps, cfg 7) and, per frame and step, the size of its
change inside three subspaces: the 15-d melody basis (lumi/melody_subspace15_selective_v3.npz, the one the R2(t) gate uses), a random 15-d subspace orthogonal to it (the
null: same dimension, not melody), and the whole complement. Each step's change is divided by that step's mean across all clips, so the sampler's schedule, which makes
some steps big for everything, is taken out. D10's X2 note warned about exactly this.
  kurtosis     excess kurtosis of the residual over clips, frames, steps. Interval: 95% bootstrap over clips.
  hill         tail exponent of the top 1% (lower = heavier).
  top10_share  share of a clip's total path in its 10% largest steps, before removing the schedule, for reference.
  burst_share  share of the top-1% residual events falling in the busiest 20% of steps (20% = no clustering in t).
Meter: Gaussian and Pareto synthetic residuals run through the same numbers.
Reading: HEAVY means melody clearly above the null, and the R2(t) gate would become event-weighted. Otherwise D10 closes.
RUN: setsid nohup .venv/bin/python eval/d10_melody_intermittency.py render/score; GPU lock taken by eval/run_d10.sh.
"""
import argparse, json, os, sys, time
from pathlib import Path
import numpy as np
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "stable-audio-3")); sys.path.insert(0, str(HERE.parent / "control"))
OUT = HERE / "musicology" / "d10_melody_intermittency_2026-11-03"
DATA = Path("/home/kim/sao_runs/d10_melody_intermittency_20261103")
BASIS = HERE.parent / "lumi" / "melody_subspace15_selective_v3.npz"
STEPS, DUR, CFG, SEEDS = 50, 20.0, 7.0, 3


def subspaces():
    B = np.load(BASIS)["basis15"].astype(np.float64)
    r = np.random.default_rng(0).standard_normal((15, 256))
    r -= r @ B.T @ B
    q = np.linalg.qr(r.T)[0].T
    return B, q


def render():
    import mood_deconf_render as W
    import torch
    from stable_audio_3 import StableAudioModel
    DATA.mkdir(parents=True, exist_ok=True)
    B, R = subspaces()
    model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")
    Bt, Rt = (torch.tensor(x, dtype=torch.float32, device="cuda:0") for x in (B, R))
    plist = [p for p in W.prompts() if p["id"] != "prompt_dark"]
    jobs = [(p, p["seed"] + k) for p in plist for k in range(SEEDS)]
    # throwaway first render: the first-decode fault is after the latent, and this only reads latents, but the first process render is not used either
    model.generate(prompt=jobs[0][0]["text"], duration=DUR, steps=STEPS, cfg_scale=CFG, seed=jobs[0][1], batch_size=1)
    for n, (p, seed) in enumerate(jobs):
        f = DATA / f"{p['id']}__{seed}.npz"
        if f.exists():
            continue
        xs, ts = [], []
        def cb(d):
            xs.append(d["denoised"][0].float()); ts.append(float(d["t"].flatten()[0]))
        t0 = time.time()
        x = model.generate(prompt=p["text"], duration=DUR, steps=STEPS, cfg_scale=CFG, seed=seed, batch_size=1, callback=cb)
        assert len(xs) == STEPS, f"callback fired {len(xs)} times"
        X = torch.stack(xs); D = X[1:] - X[:-1]                                # [steps-1, 256, T]
        mel = (Bt @ D).pow(2).sum(1).sqrt().cpu().numpy().astype(np.float32)
        nul = (Rt @ D).pow(2).sum(1).sqrt().cpu().numpy().astype(np.float32)
        tot = D.pow(2).sum(1)
        comp = (tot - (Bt @ D).pow(2).sum(1)).clamp(min=0).sqrt().cpu().numpy().astype(np.float32)
        np.savez(f, mel=mel, nul=nul, comp=comp, t=np.array(ts, np.float32), audio_std=float(x.std()))
        print(n + 1, len(jobs), f.name, f"{time.time() - t0:.1f}s", flush=True)


def stats_of(A):
    """A: [clips, steps, frames] sizes."""
    r = A / (A.mean((0, 2), keepdims=True) + 1e-12)
    v = r.ravel()
    kurt = float(((v - v.mean()) ** 4).mean() / v.var() ** 2 - 3)
    s = np.sort(v)[::-1]; k = max(10, int(len(s) * .01))
    hill = float(1 / np.mean(np.log(s[:k] / s[k])))
    thr = np.quantile(v, .99); ev = (r > thr).sum((0, 2)).astype(float)
    burst = float(np.sort(ev)[::-1][: max(1, len(ev) // 5)].sum() / max(ev.sum(), 1))
    path = A.mean(2); top = np.sort(path, 1)[:, ::-1][:, : max(1, path.shape[1] // 10)].sum(1) / path.sum(1)
    return dict(kurtosis=round(kurt, 3), hill=round(hill, 2), burst_share=round(burst, 3), top10_share=round(float(top.mean()), 3)), ev


def score():
    OUT.mkdir(parents=True, exist_ok=True)
    fs = sorted(DATA.glob("*.npz"))
    Z = [np.load(f) for f in fs]
    A = {k: np.stack([z[k] for z in Z]) for k in ("mel", "nul", "comp")}
    res = {"n_clips": len(fs), "shape": list(A["mel"].shape), "t": [round(float(x), 4) for x in Z[0]["t"]]}
    rng = np.random.default_rng(0)
    res["meter"] = {"gaussian_chi15": stats_of(np.sqrt((rng.standard_normal((42, 49, 215, 15)) ** 2).sum(-1)))[0],
                    "pareto_a2": stats_of(1 + rng.pareto(2.0, (42, 49, 215)))[0]}
    for k, a in A.items():
        s, ev = stats_of(a)
        boots = [stats_of(a[rng.integers(0, len(a), len(a))])[0] for _ in range(200)]
        s["kurtosis_ci"] = [round(float(x), 3) for x in np.percentile([b["kurtosis"] for b in boots], [2.5, 97.5])]
        s["hill_ci"] = [round(float(x), 2) for x in np.percentile([b["hill"] for b in boots], [2.5, 97.5])]
        s["events_by_step"] = [int(x) for x in ev]
        s["speed_by_step"] = [round(float(x), 4) for x in a.mean((0, 2))]
        res[k] = s
    r_mel = A["mel"] / A["mel"].mean((0, 2), keepdims=True); r_nul = A["nul"] / A["nul"].mean((0, 2), keepdims=True)
    res["paired"] = {"kurtosis_mel_minus_null_by_clip": round(float(np.mean([stats_of(A["mel"][[i]])[0]["kurtosis"] - stats_of(A["nul"][[i]])[0]["kurtosis"] for i in range(len(fs))])), 3),
                     "clips_mel_above_null": int(sum(stats_of(A["mel"][[i]])[0]["kurtosis"] > stats_of(A["nul"][[i]])[0]["kurtosis"] for i in range(len(fs))))}
    json.dump(res, open(OUT / "results.json", "w"), indent=1)
    for k in ("meter", "paired"):
        print(k, res[k])
    for k in A:
        print(k, {x: res[k][x] for x in ("kurtosis", "kurtosis_ci", "hill", "hill_ci", "burst_share", "top10_share")}); print("  events", res[k]["events_by_step"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["render", "score"]); {"render": render, "score": score}[ap.parse_args().mode]()
