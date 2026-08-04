#!/usr/bin/env python
"""ablate_adapter_layers2.py — #44 follow-up (Kim direct 2026-07-21): early+late combo and
single-layer injection sweep of the onset FiLM adapter's 24 cross-attn taps.

Extends eval/ablate_adapter_layers.py (2026-07-12: all/none/early/mid/late; late-only was the
only subset with positive authority, mid-only ANTI-correlated). Two new questions:
  * earlylate (L0-7 + L16-23): is mid needed at all when both ends are present? If corr ≈ all-taps,
    the mid taps are dead weight; if it collapses, mid is load-bearing in co-adaptation.
  * L00..L23 singles: a per-layer LEVERAGE/SIGN profile. Kim's own caveat, recorded: a single tap
    is maximally OOD for an adapter trained with all 24 co-adapting — expect weak/noisy effects,
    and read the profile as "which taps carry self-sufficient signal + which flip sign", NOT as
    per-layer authority. (The in-distribution answer needs retrained layer-restricted adapters —
    that's the #53-adjacent training experiment, not this.)

all/none re-rendered as in-run controls (same code path, comparable numbers).
Resumable: existing wavs are re-measured, not re-rendered.

Run: FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/ablate_adapter_layers2.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
from sa3_control.audio_io import save_audio                                   # noqa: E402
from sa3_control.inject import install_adapters                               # noqa: E402
from sa3_control.adapters import (ControlledCrossAttention, ControlContext,   # noqa: E402
                                  use_control_context, current_control_context)
from sa3_control.conditioner import ScalarAttributeEncoder                    # noqa: E402
from stable_audio_3 import StableAudioModel                                   # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disintegration_metrics import measure, gate                              # noqa: E402

CKPT = "/run/media/kim/Mantu/sa3_control_runs/onset_Fusion_lr1e-4_randomcrop/riffer_final.pt"
OUT = Path("/run/media/kim/Mantu/sa3_control_runs/ablate_layers2_2026-07-21")
CONFIGS = {"all": list(range(24)), "none": [],
           "earlylate": list(range(0, 8)) + list(range(16, 24))}
CONFIGS.update({f"L{i:02d}": [i] for i in range(24)})
DENSITIES = [3.0, 6.0, 9.0, 12.0]
GAIN, SEED, DUR, STEPS, CFG = 1.75, 4242, 20.0, 24, 6.0   # identical to the 07-12 run
PROMPT = "psychedelic goa trance"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ck = torch.load(CKPT, map_location="cpu")
    cargs = ck.get("args", {})
    control_dim = int(cargs.get("control_dim", 768))
    n_tokens = int(cargs.get("n_tokens", 16))
    raw = ck.get("scalar_norm")
    if isinstance(raw, (list, tuple)):
        norm = {"mean": float(raw[0]), "std": float(raw[1])}
    elif isinstance(raw, dict):
        norm = {"mean": float(raw["mean"]), "std": float(raw["std"])}
    else:
        norm = {"mean": float(cargs.get("scalar_mean", 7.1)),
                "std": float(cargs.get("scalar_std", 2.5))}
    print("[norm]", norm, flush=True)

    # skip the (expensive) model load entirely if every wav already exists
    todo = [(c, d) for c in CONFIGS for d in DENSITIES
            if not (OUT / f"{c}_d{int(d)}.wav").exists()]
    sam = wrappers = enc = mdtype = None
    if todo:
        sam = StableAudioModel.from_pretrained("medium-base", device="cuda")
        mdtype = next(sam.model.model.parameters()).dtype
        wrappers = install_adapters(sam, control_dim=control_dim)
        enc = ScalarAttributeEncoder(control_dim=control_dim, n_tokens=min(n_tokens, 16)).to("cuda")
        from sa3_control.generate import load_adapter_state
        load_adapter_state(ck["state"], wrappers, enc)
        for w in wrappers:
            w.adapter.to(device="cuda", dtype=mdtype)
        enc.to(device="cuda", dtype=mdtype).eval()
        print(f"[install] {len(wrappers)} wrappers, {len(todo)} renders to do", flush=True)

        def gated_forward(self, x, context=None, **kw):
            base = self.base_attention(x, context=context, **kw)
            ctx = current_control_context()
            if ctx is not None and ctx.control_tokens is not None and getattr(self, "abl_on", True):
                base = base + ctx.gain * self.adapter(x, self.base_attention, ctx.control_tokens)
            return base
        ControlledCrossAttention.forward = gated_forward

    results, stats = [], {}
    for cname, keep in CONFIGS.items():
        keep = set(keep)
        if wrappers is not None:
            for i, w in enumerate(wrappers):
                w.abl_on = i in keep
        for d in DENSITIES:
            f = OUT / f"{cname}_d{int(d)}.wav"
            if not f.exists():
                t = torch.tensor([[(d - norm["mean"]) / norm["std"]]], device="cuda", dtype=mdtype)
                with torch.inference_mode():
                    ctrl = enc(t)
                ctrl = torch.cat([ctrl, torch.zeros_like(ctrl)], dim=0)  # cond-only under CFG
                with use_control_context(ControlContext(ctrl, gain=GAIN)):
                    audio = sam.generate(prompt=PROMPT, duration=DUR, steps=STEPS,
                                         cfg_scale=CFG, seed=SEED, sampler_type="euler")
                save_audio(f, audio[0], sam.model.sample_rate)
            m = stats[f"{cname}_d{int(d)}"] = measure(f)
            results.append({"config": cname, "requested": d, "measured": round(float(m["onsets"]), 2)})
            print(f"[{cname} d{d:.0f}] measured {m['onsets']:.2f}", flush=True)

    # disintegration screen vs the same-recipe unsteered clip (none_d3), shared gate
    base = stats["none_d3"]
    flags = {clip: gate(m, base)["reasons"] for clip, m in sorted(stats.items())
             if gate(m, base)["blown"]}
    (OUT / "disintegration_flags.json").write_text(json.dumps(flags, indent=1))

    rep = {}
    for cname in CONFIGS:
        rs = [(r["requested"], r["measured"]) for r in results if r["config"] == cname]
        a = np.array(rs)
        rep[cname] = {"corr": round(float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]), 3),
                      "spread": round(float(a[:, 1].max() - a[:, 1].min()), 2),
                      "cells": rs}
    (OUT / "run_meta.json").write_text(json.dumps(
        {"purpose": "#44 follow-up: earlylate combo + single-layer leverage/sign profile of the "
                    "onset adapter's 24 cross-attn taps",
         "caveat": "single-tap configs are maximally OOD for an all-tap-trained adapter (Kim's own "
                   "caveat at commissioning) — read L* rows as leverage/sign, not authority; the "
                   "in-distribution version = retrain with restricted taps (layer-restricted "
                   "adapter training, #53-adjacent)",
         "baseline_run": "ablate_layers_2026-07-12 (all/none/early/mid/late)",
         "model_training": {"run": "onset_Fusion_lr1e-4_randomcrop", "checkpoint": "riffer_final.pt step 54000"},
         "recipe": {"gain": GAIN, "seed": SEED, "duration": DUR, "steps": STEPS, "cfg": CFG,
                    "prompt": PROMPT, "densities": DENSITIES,
                    "meter": "plain librosa onset_detect — RELATIVE use only"},
         "result": rep, "kim_feedback": None,
         "script": "SAO/eval/ablate_adapter_layers2.py"}, indent=2))
    print("[report]", json.dumps({k: v["corr"] for k, v in rep.items()}), flush=True)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
