#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e23b_morph_synth.py -- EXPERIMENTS E23 part (b): feed the morph-contour conditioner CLEAN, high-contrast synthetic contours. D17's A/B found no following, but its streams
came from Melodia on real stems, which are noisy. If the renders do not follow even a clean line, the conditioner learned nothing about contour; if they do, the real streams were the problem.

Streams: K&P L3 contour symbols (the training encoding, eval/build_morph_streams.py) of known lines over T=512 (47.6 s): 8 s rising phrases and their mirror, 10 s and 5 s waves in both phases.
Controls: a shuffled stream (the rising stream cut into 8 blocks, shuffled) and the null (zero tokens, no conditioning).
Checkpoints: D17 deconvolved steps 4000 and 10000 (the online weights). Gains 1, 2, 4. 3 seeds. One prompt, the training-eval prompt. Base render recipe as in melody_pilot_eval: 24 steps, cfg 7, Euler.
Score (Melodia on the mix, meter validated in E23a): corr with the fed line minus corr with its mirror, and the same for the shuffled control. Chance 0, max 2.
Outputs: ~/evals_aac/control_runs/e23b_morph_synth_20261103/. RUN: eval/run_e23b.sh
"""
import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "control"))
sys.path.insert(0, str(HERE.parent / "stable-audio-3"))
sys.path.insert(0, "/home/kim/Projects/mir")
import numpy as np
from src.conditioners.contour_streams import contour_stream, expand_to_frames

OUT = Path("/home/kim/evals_aac/control_runs/e23b_morph_synth_20261103")
RUN = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/morph_L3_lion_r128_bs32_2026-09-09/deconv")
CKPTS = {"step4000": RUN / "riffer_step4000.pt", "step10000": RUN / "riffer_step10000.pt"}
PROMPT = "psychedelic goa trance, hypnotic melodic acid lead line, driving rolling bassline, 143 BPM"
N = 512
FPS = 44100 / 4096
DUR = N / FPS
GAINS = (1.0, 2.0, 4.0)
SEEDS = (607, 1234, 5678)
TOL = 0.5
STRIDE = 4
L = 3
MIRROR = {"rise8": "fall8", "fall8": "rise8", "wave10": "wave10_anti", "wave10_anti": "wave10", "wave5": "wave5_anti", "wave5_anti": "wave5"}
SHAPES = ("rise8", "fall8", "wave10", "wave10_anti", "wave5", "wave5_anti")
SPAN = {"rise8": 16.0, "fall8": 16.0, "wave10": 24.0, "wave10_anti": 24.0, "wave5": 24.0, "wave5_anti": 24.0}


def line(name, n):
    """0..1 shape over n frames. Repeating phrases, because the K&P encoding reads motion under 0.5 semitones per grid point (0.37 s) as flat, so one slow line over 47 s reads as no motion."""
    secs = np.linspace(0, DUR, n)
    tri = lambda p: 1 - np.abs(2 * ((secs / p) % 1) - 1)
    saw = (secs / 8.0) % 1
    return {"rise8": saw, "fall8": 1 - saw, "wave10": tri(10.0), "wave10_anti": 1 - tri(10.0), "wave5": tri(5.0), "wave5_anti": 1 - tri(5.0)}[name]


def stream_of(name):
    semis = line(name, N) * SPAN[name]
    pts = np.arange(N)[::STRIDE]
    syms, anch = contour_stream(semis, pts, L=L, tol=TOL)
    s = expand_to_frames(syms, anch, N)
    return np.where(s < 0, 0, s + 1).astype(np.int64)


def shuffled_up():
    s = stream_of("rise8")
    blocks = np.array_split(s, 8)
    idx = np.random.default_rng(23).permutation(8)
    return np.concatenate([blocks[i] for i in idx]).astype(np.int64)


def cells():
    out = []
    for ck in CKPTS:
        for seed in SEEDS:
            out.append(dict(id=f"{ck}__null__s{seed}", ck=ck, shape="null", gain=0.0, seed=seed))
            for g in GAINS:
                out.append(dict(id=f"{ck}__shuffled__g{g:.0f}__s{seed}", ck=ck, shape="shuffled", gain=g, seed=seed))
                for s in SHAPES:
                    out.append(dict(id=f"{ck}__{s}__g{g:.0f}__s{seed}", ck=ck, shape=s, gain=g, seed=seed))
    return out


def render(only):
    import torch
    from functools import partial
    from sa3_control.adapters import ControlContext, use_control_context
    from sa3_control.audio_io import save_audio
    from sa3_control.generate import build_conditioner, load_adapter_state
    from sa3_control.inject import install_adapters
    from stable_audio_3 import StableAudioModel
    from stable_audio_3.models.lora import add_lora, LoRAParametrization

    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    todo = [c for c in cells() if c["id"] not in done and c["ck"] == only]
    print(only, len(todo), "clips to render", flush=True)
    if not todo:
        return
    ck = torch.load(CKPTS[only], map_location="cpu", weights_only=False)
    assert ck.get("control_mode") == "melody_contour", ck.get("control_mode")
    cargs = ck.get("args", {})
    sam = StableAudioModel.from_pretrained(cargs.get("model", "medium-base"), device="cuda:0")
    md = next(sam.model.model.parameters()).dtype
    dit = sam.model.model
    if int(ck.get("dora_rank", 0) or 0) > 0:
        r = int(ck["dora_rank"])
        alpha = ck.get("dora_alpha") or float(r)
        add_lora(dit, {torch.nn.Linear: {"weight": partial(LoRAParametrization.from_linear, rank=r, lora_alpha=alpha, adapter_type="dora-rows")},
                       torch.nn.Conv1d: {"weight": partial(LoRAParametrization.from_conv1d, rank=r, lora_alpha=alpha, adapter_type="dora-rows")}})
    wrappers = install_adapters(sam, control_dim=int(cargs.get("control_dim", 768)))
    if int(ck.get("dora_rank", 0) or 0) > 0:
        _, unexpected = dit.load_state_dict(ck["lora_state"], strict=False)
        assert not unexpected, unexpected[:4]
    enc = build_conditioner(ck, "cuda:0", md)
    load_adapter_state(ck["state"], wrappers, enc)
    for w in wrappers:
        w.adapter.to(device="cuda:0", dtype=md)
    enc.to(device="cuda:0", dtype=md).eval()
    streams = {s: stream_of(s) for s in SHAPES}
    streams["shuffled"] = shuffled_up()
    print("distinct symbols", {k: len(set(v.tolist())) for k, v in streams.items()}, flush=True)
    with log.open("a") as f:
        for c in todo:
            with torch.inference_mode():
                ctrl = enc(torch.from_numpy(streams[c["shape"]] if c["shape"] != "null" else np.zeros(N, dtype=np.int64))[None].to("cuda:0"))
            ctrl = torch.cat([ctrl, torch.zeros_like(ctrl)], dim=0)
            with use_control_context(ControlContext(ctrl, gain=c["gain"] if c["shape"] != "null" else 1.0)):
                a = sam.generate(prompt=PROMPT, duration=DUR, steps=24, cfg_scale=7.0, seed=c["seed"], sampler_type="euler")
            a = a.float().cpu()
            if not bool(torch.isfinite(a).all()) or float(a.std()) < 1e-3:
                print("FAULT", c["id"], flush=True)
                continue
            tmp = OUT / "_t.wav"
            save_audio(str(tmp), a[0], 44100, normalize=True)
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{c['id']}.m4a")], check=True)
            tmp.unlink()
            f.write(json.dumps(c) + "\n")
            f.flush()


def measure():
    import essentia.standard as es
    cells_ = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    corr = lambda a, b: float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else 0.0
    rows = []
    for c in cells_:
        x = es.MonoLoader(filename=str(OUT / f"{c['id']}.m4a"), sampleRate=44100)()
        f0, _ = es.PredominantPitchMelodia(frameSize=2048, hopSize=441, sampleRate=44100, minFrequency=55, maxFrequency=1760)(es.EqualLoudness()(x))
        f0 = np.asarray(f0, dtype=np.float64)
        v = f0 > 0
        st = 12 * np.log2(f0[v] / 440.0)
        r = dict(c, span=float(np.percentile(st, 95) - np.percentile(st, 5)), voiced=float(v.mean()))
        names = SHAPES if c["shape"] in ("null", "shuffled") else [c["shape"]]
        r["follow"] = {s: corr(st, line(s, len(f0))[v]) - corr(st, line(MIRROR[s], len(f0))[v]) for s in names}
        rows.append(r)
    (OUT / "per_clip.json").write_text(json.dumps(rows, indent=0))
    L, tab = ["follow = corr with the fed line minus corr with its mirror, Melodia on the mix. Chance 0, max 2. null / shuffled: the same clip scored against each line, so their spread shows what chance looks like.", ""], []
    for ck in CKPTS:
        for g in GAINS:
            vals = defaultdict(list)
            for r in rows:
                if r["ck"] == ck and r["gain"] == g and r["shape"] in SHAPES:
                    vals[r["shape"]].append(r["follow"][r["shape"]])
            shuf = [v for r in rows if r["ck"] == ck and r["gain"] == g and r["shape"] == "shuffled" for v in r["follow"].values()]
            fed = [x for v in vals.values() for x in v]
            row = dict(ck=ck, gain=g, fed=round(float(np.mean(fed)), 3), positive=int(sum(x > 0 for x in fed)), n=len(fed), shuffled_abs=round(float(np.mean(np.abs(shuf))), 3), by_shape={k: round(float(np.mean(v)), 3) for k, v in vals.items()})
            tab.append(row)
            L.append(f"{ck:10s} gain {g:.0f}: fed {row['fed']:+.3f} positive {row['positive']}/{row['n']}; shuffled |follow| {row['shuffled_abs']:.3f}; {row['by_shape']}")
        nul = [v for r in rows if r["ck"] == ck and r["shape"] == "null" for v in r["follow"].values()]
        L.append(f"{ck:10s} null |follow| {np.mean(np.abs(nul)):.3f}")
    (OUT / "report.json").write_text(json.dumps(tab, indent=1))
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "measure"), required=True)
    ap.add_argument("--ck", default="step4000")
    a = ap.parse_args()
    render(a.ck) if a.stage == "render" else measure()
