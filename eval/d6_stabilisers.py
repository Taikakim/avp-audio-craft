#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-04)
"""d6_stabilisers.py -- EXPERIMENTS D6: do stabilisers give chroma guidance more steering for the same cleanliness?
Head: same_chroma C3 lr 1e-3 ep10 EMA, the E13 winner. Same 3 prompts x 4 targets, 2 seeds, medium-base, 20 s, 24 steps, cfg 7 as E13's ladder. Two gains.
  raw      the reference, reproduces E13's ladder
  clipA/B  soft cap on the guidance step's norm relative to the state (latch_guided._soft_clip_step); caps picked from the probe
  stopR95  no guidance once the melody subspace is 95% recovered, from lumi/melody_r2_vs_t_medium-base.json; the budget moves to the earlier steps
  stopR90, stopR80  the same at 90% and 80%. 99% is never reached on this 24-step schedule, whose last sigma is 0.16
  tier2    per-band weights from Tier-2's reliability, D11: bass 0.323-0.136, mid 0.449-0.220, air 0.526-0.266, matched minus null
  midonly  all weight on the mid band, the band E13 is scored on, as an extreme of the same idea
Scoring and gate as E13 (eval/chroma_e13_render.measure, control_head_disintegration_eval.gate); every arm against the same-prompt, same-seed guided gain-0 render.
Stages: probe (step sizes, GPU, one render), render (GPU), report (mir venv, after clip_metrics). Outputs ~/evals_aac/control_runs/chroma_stabilisers_d6_20261104/. RUN: eval/run_d6_stabilisers.sh
"""
import os

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)
import argparse
import gc
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = Path("/home/kim/evals_aac/control_runs/chroma_stabilisers_d6_20261104")
R2 = HERE.parent / "lumi" / "melody_r2_vs_t_medium-base.json"
GAINS = (4096, 16384)
TARGETS = ("C", "Am", "keylift", "i-VI-III-VII")
SEEDS = (1234, 5678)
BAND = 128
# Probe, goa C: the variance step is 0.2% to 1.6% of ||x|| at gain 4096, 0.2% to 10% at 16384, largest from sigma 0.68 down.
CLIPS = {"clipA": 0.01, "clipB": 0.003}
TIER2 = {"bass": 0.323 - 0.136, "mid": 0.449 - 0.220, "air": 0.526 - 0.266}


def band_weights(b, m, a):
    return [float(b)] * BAND + [float(m)] * BAND + [float(a)] * BAND


def stop_pct(sigmas, frac):
    """First step at which the model has recovered at least frac of the melody subspace (R2 at that sigma), as a fraction of the steps."""
    d = json.loads(R2.read_text())
    t, r = np.asarray(d["t"]), np.asarray(d["r2_melody"])
    o = np.argsort(t)
    r_at = np.interp(sigmas[:-1], t[o], r[o])
    idx = np.nonzero(r_at >= frac)[0]
    return (int(idx[0]) if idx.size else len(r_at)) / len(r_at)


def arms(sigmas, clips):
    m = max(TIER2.values())
    a = {"raw": {}, "stopR95": {"end_pct": stop_pct(sigmas, 0.95)}, "stopR90": {"end_pct": stop_pct(sigmas, 0.90)}, "stopR80": {"end_pct": stop_pct(sigmas, 0.80)}, "tier2": {"dim_weights": band_weights(TIER2["bass"] / m, TIER2["mid"] / m, TIER2["air"] / m)}, "midonly": {"dim_weights": band_weights(0, 1, 0)}}
    for k, c in clips.items():
        a[k] = {"softclip": c}
    return a


def render(stage, clips):
    import torch
    from stable_audio_3 import StableAudioModel
    from sa3_control.audio_io import save_audio
    import chroma_e13_render as E
    from stable_audio_3.inference import latch_guided as LG

    OUT.mkdir(parents=True, exist_ok=True)
    head = str(E.heads()["C3_ep10_ema1"])
    n_frames = int(round(E.DURATION_SEC * E.FPS))
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    captured = {}
    orig = LG.sample_flow_euler_multi_latch_guided

    def spy(m, x, sigmas, guides, **kw):
        captured["sigmas"] = sigmas.detach().float().cpu().numpy()
        return orig(m, x, sigmas, guides, **kw)

    import stable_audio_3.model as SM

    SM.sample_flow_euler_multi_latch_guided = spy

    def gen(pid, tid, g, s, a):
        cfg = {"model_path": head, "target_raw": E.build_target(tid or "C", n_frames), "weight": 1.0, "loss_type": "cosine"}
        if "end_pct" in a:
            cfg["end_pct"] = a["end_pct"]
        if "dim_weights" in a:
            cfg["dim_weights"] = a["dim_weights"]
        hp = {"rho": float(g), "mu": float(g), "guide_softclip": float(a.get("softclip", 0.0))}
        if a.get("log"):
            hp["log_norms"] = True
        sink = []
        audio = model.generate(prompt=E.prompt_text(pid), duration=E.DURATION_SEC, steps=E.STEPS, cfg_scale=E.CFG, seed=s, latch_configs=[cfg], latch_hparams=hp, latents_sink=sink)
        return audio, sink[-1].float()

    if stage == "probe":
        for g in GAINS:
            gen("goa", "C", g, 1234, {"log": True})
        print("sigmas", [round(float(v), 4) for v in captured["sigmas"]], flush=True)
        for frac in (0.95, 0.99):
            print("stop at", frac, stop_pct(captured["sigmas"], frac), flush=True)
        return
    gen("goa", "C", 0, 1, {})  # one render fills in the schedule
    plan = arms(captured["sigmas"], clips)
    print({k: {kk: vv for kk, vv in v.items() if kk != "dim_weights"} for k, v in plan.items()}, flush=True)
    log_p = OUT / "cells.jsonl"
    done = {json.loads(l)["clip"] for l in log_p.read_text().splitlines()} if log_p.exists() else set()
    cells = [(None, p, None, 0, s) for p in E.PROMPTS for s in SEEDS]
    cells += [(k, p, t, g, s) for k in plan for g in GAINS for p in E.PROMPTS for t in TARGETS for s in SEEDS]
    meta = {"purpose": "EXPERIMENTS D6: does a soft cap on the step, stopping late, or per-band weights give chroma guidance more steering for the same cleanliness?", "hypothesis": "The stabilisers keep late heavy steps from damaging the render, so hit and cos rise at equal gate. E13x found no collapse up to gain 32768 on this head, so the expected room is small.", "head": "same_chroma C3 lr 1e-3 ep10 EMA", "training_recipe": "latch/run_chroma_retrain.sh", "dataset_info": "goa latents_sa3, 5400 crops, other-stem SAME chroma targets", "arms": {k: {kk: vv for kk, vv in v.items() if kk != "dim_weights"} for k, v in plan.items()}, "gains": GAINS, "prompts": E.PROMPTS, "targets": TARGETS, "seeds": SEEDS, "related": ["eval/d6_stabilisers.py", "eval/run_d6_stabilisers.sh", "EXPERIMENTS.md D6", "eval/chroma_e13_render.py"], "kim_feedback": None}
    (OUT / "run_meta.json").write_text(json.dumps(meta, indent=1))
    with log_p.open("a") as f:
        for k, pid, tid, g, s in cells:
            name = f"base0__{pid}__s{s}" if g == 0 else f"{k}__{pid}__{tid}__g{g}__s{s}"
            if f"{name}.m4a" in done:
                continue
            audio, z = gen(pid, tid, g, s, plan.get(k, {}))
            wav = audio[0].float().cpu()
            if not torch.isfinite(z).all() or not torch.isfinite(wav).all() or float(wav.std()) < 1e-3:
                print("FAULT", name, flush=True)
                continue
            wp = OUT / f"{name}.wav"
            save_audio(str(wp), wav, E.sc.SAME_SR)
            m = E.measure(wav.numpy(), tid, n_frames)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{name}.m4a")], check=True)
            wp.unlink()
            f.write(json.dumps({"clip": f"{name}.m4a", "arm": k or "base", "prompt": pid, "target": tid, "gain": g, "seed": s, "m": m, "z_std": round(float(z.std()), 4)}) + "\n")
            f.flush()
            del audio, z, wav
            gc.collect()
            torch.cuda.empty_cache()


def report():
    import sqlite3

    from control_head_disintegration_eval import DB, gate

    rows = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    met = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ?", (f"{OUT}/%",))}
    base = {(c["prompt"], c["seed"]): c for c in rows if c["gain"] == 0}
    rng = np.random.default_rng(1)

    def d(c, band, f):
        return c["m"][c["target"]][band][f] - base[(c["prompt"], c["seed"])]["m"][c["target"]][band][f]

    def ci(v):
        v = np.asarray(v)
        b = [rng.choice(v, v.size).mean() for _ in range(4000)]
        return f"{v.mean():+.3f} [{np.percentile(b, 2.5):+.3f}, {np.percentile(b, 97.5):+.3f}]"

    idx = {(c["arm"], c["prompt"], c["target"], c["gain"], c["seed"]): c for c in rows}
    L = ["Change vs the same-seed gain-0 render, n = 24 per cell. cos and hit in the mid band (bass in brackets). 'vs raw' is paired, same prompt, target, seed: hit mid. Measured, not heard."]
    out = {}
    for g in GAINS:
        for arm in sorted({c["arm"] for c in rows if c["gain"] == g}, key=lambda a: (a != "raw", a)):
            cs = [c for c in rows if c["arm"] == arm and c["gain"] == g]
            why, fails, ce, zr = Counter(), 0, [], []
            for c in cs:
                b = base[(c["prompt"], c["seed"])]
                mc, mb = met.get(str(OUT / c["clip"])), met.get(str(OUT / b["clip"]))
                zr.append(c["z_std"] / b["z_std"])
                if mc and mb:
                    bad, w, _ = gate({**mc, "z_std": c["z_std"]}, {**mb, "z_std": b["z_std"]}, rhythmic=False)
                    fails += int(bad)
                    why.update(x.split("(")[0] for x in w)
                    if mc.get("ce") is not None:
                        ce.append(mc["ce"] - mb["ce"])
            pair = [d(c, "mid", "hit") - d(idx[("raw", c["prompt"], c["target"], g, c["seed"])], "mid", "hit") for c in cs if ("raw", c["prompt"], c["target"], g, c["seed"]) in idx]
            line = f"g{g} {arm:8s} n {len(cs)}  cos {np.mean([d(c, 'mid', 'fcos') for c in cs]):+.3f} ({np.mean([d(c, 'bass', 'fcos') for c in cs]):+.3f})  hit {np.mean([d(c, 'mid', 'hit') for c in cs]):+.3f} ({np.mean([d(c, 'bass', 'hit') for c in cs]):+.3f})  vs raw {ci(pair) if arm != 'raw' else '-'}  gate {fails}/{len(cs)} {dict(why)}  dCE {np.mean(ce) if ce else float('nan'):+.2f}  z ratio {np.mean(zr):.3f}"
            L.append(line)
            out[f"{arm}_g{g}"] = line
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("probe", "render", "report"), required=True)
    ap.add_argument("--clips", default=None, help="name=cap,... overriding the caps")
    a = ap.parse_args()
    if a.stage == "report":
        report()
    else:
        clips = CLIPS if not a.clips else {kv.split("=")[0]: float(kv.split("=")[1]) for kv in a.clips.split(",")}
        render(a.stage, clips)
