#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-14)
"""latch_phaseE_render.py -- eval clips for every finished LatCH bracket arm (onset_per_beat_ts density heads), same seed/prompt as an unsteered baseline.

WHY (Kim 2026-10-14: "generate eval clips for all of the finished runs"). Phase E finished with val losses that differ by less than the 0.004 noise rule except
depth 8; val loss does not say whether a head STEERS. This renders each arm's best.pt at three density targets and two gains next to a shared unsteered baseline,
so the pairs can be scored with eval/latch_drift_check.py, latch_melodic_tensor.py and the Essentia/Audiobox batteries, and listened to.
Modelled on eval/latch_sa3_sweep_render.py (same T=512 frames rule, 24 steps, cfg 7, medium-base, constant-target guidance, rho=mu=gain).
Target = std_mean + k*std_std from the checkpoint's own statistics (opb: mean 2.94 / std 1.18 onsets-per-beat on the bigset), k in {-1, +1, +2}.
Gains 512 and 2048 are a GUESS for this head (energy heads operate ~512, MASTER s5); no density-head gain ladder exists yet, so both are rendered.
Resumable (manifest). Run: see the wrapper in the docstring of run_phaseE_render.sh -- takes the GPU lock itself.
    ROCR_VISIBLE_DEVICES=0 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE MIOPEN_FIND_MODE=2 SAO/.venv/bin/python eval/latch_phaseE_render.py [--arms E01,E05] [--out DIR]
"""
import argparse
import json
import os
import sys
import time

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

PHASE = "/run/media/kim/Mantu2/latch_sweep/modular_2026-09-30/phaseE"
OUT = "/run/media/kim/Mantu2/latch_sweep/modular_2026-09-30/phaseE_eval_clips"
FEATURE = "onset_per_beat_ts"
KS = [-1.0, 1.0, 2.0]
GAINS = [512.0, 2048.0]
STEPS, CFG, DURATION = 24, 7.0, 47.56
PROMPTS = [
    {"id": "p0", "text": "aggressive upbeat goa trance", "seed": 1234},
    {"id": "p1", "text": "90s psytrance, mystical aggressive goa trance, hypnotic, energetic, 143 bpm, the bassline is a beefy moog snappy saw wave 16ths bass, "
                         "the drums have classic 909 kick and open hihat sounds, roland 303 style distorted resonant acid riffs play syncopated rhythms", "seed": 764},
]


def save(audio, model, path):
    import numpy as np
    import soundfile as sf
    a = audio.cpu().float().numpy() if hasattr(audio, "cpu") else np.asarray(audio)
    if a.ndim == 3:
        a = a[0]
    if a.shape[0] in (1, 2):
        a = a.T
    pk = max(1e-9, float(abs(a).max()))
    if pk > 1:
        a = a / pk
    sf.write(path, a, model.model.sample_rate)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="", help="comma list of arm-name prefixes, e.g. E01,E05 (default: all in SUMMARY.tsv)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    import torch
    from stable_audio_3 import StableAudioModel
    rows = [l.split("\t") for l in open(os.path.join(PHASE, "SUMMARY.tsv")).read().splitlines() if l.strip()]
    arms = [r[0] for r in rows if (not a.arms or any(r[0].startswith(p) for p in a.arms.split(",")))]
    os.makedirs(a.out, exist_ok=True)
    mp = os.path.join(a.out, "manifest.json")
    man = json.load(open(mp)) if os.path.exists(mp) else {"cells": []}
    done = {c["clip"] for c in man["cells"]}
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")

    def cell(name, **kw):
        if name in done:
            return None
        t0 = time.time()
        audio = model.generate(duration=DURATION, steps=STEPS, cfg_scale=CFG, **kw)
        save(audio, model, os.path.join(a.out, name))
        return round(time.time() - t0, 1)

    for p in PROMPTS:
        n = f"baseline__{p['id']}.wav"
        dt = cell(n, prompt=p["text"], seed=p["seed"])
        if dt is not None:
            man["cells"].append({"clip": n, "arm": "baseline", "prompt_id": p["id"], "prompt": p["text"], "seed": p["seed"], "elapsed": dt})
            json.dump(man, open(mp, "w"), indent=1)
            print(f"[baseline/{p['id']}] {dt}s", flush=True)
    for arm in arms:
        ck = os.path.join(PHASE, arm, f"latch_sa3_{FEATURE}_best.pt")
        if not os.path.exists(ck):
            print("MISSING", ck, flush=True)
            continue
        meta = torch.load(ck, map_location="cpu", weights_only=False)
        mean, std = float(meta.get("std_mean", 0.0)), float(meta.get("std_std", 1.0)) or 1.0
        for k in KS:
            for g in GAINS:
                for p in PROMPTS:
                    n = f"{arm}__k{k:+.0f}__g{int(g)}__{p['id']}.wav"
                    tgt = mean + k * std
                    dt = cell(n, prompt=p["text"], seed=p["seed"], latch_configs=[{"model_path": ck, "kind": "constant", "value": tgt, "weight": 1.0}],
                              latch_hparams={"rho": g, "mu": g})
                    if dt is None:
                        continue
                    man["cells"].append({"clip": n, "arm": arm, "k": k, "target": tgt, "gain": g, "prompt_id": p["id"], "seed": p["seed"],
                                         "ckpt": ck, "val_loss": meta.get("val_loss"), "epoch": meta.get("epoch"), "elapsed": dt})
                    json.dump(man, open(mp, "w"), indent=1)
                    print(f"[{arm}/k{k:+.0f}/g{int(g)}/{p['id']}] {dt}s", flush=True)
    json.dump({
        "purpose": "Eval clips for every finished Phase E LatCH density head (onset_per_beat_ts), each next to a same-seed unsteered baseline (Kim 2026-10-14).",
        "hypothesis": "Val-loss differences below 0.004 do not separate the arms; steering behaviour (does the density move, does anything else) might. Depth 8 (best val 0.1844) is the only arm beyond the noise rule.",
        "related": {"script": "SAO/eval/latch_phaseE_render.py", "experiments": "EXPERIMENTS.md E5 Phase E", "heads": PHASE, "checks": ["eval/latch_drift_check.py", "eval/latch_melodic_tensor.py", "eval/essentia_zoo_battery.py"]},
        "recipe": {"model": "medium-base, no adapter", "steps": STEPS, "cfg": CFG, "duration_sec": DURATION, "targets": "std_mean + k*std_std", "k": KS, "gains": GAINS,
                   "notes": "gains are a guess for this head; baseline is shared per prompt, same seed"},
        "result": None, "kim_feedback": None, "status": "rendered; not yet scored or listened to"},
        open(os.path.join(a.out, "run_meta.json"), "w"), indent=2)
    print(f"DONE {len(man['cells'])} cells -> {a.out}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
