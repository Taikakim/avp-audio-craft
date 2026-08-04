#!/usr/bin/env python
"""ablate_adapter_layers.py — per-layer-group ablation of the onset FiLM adapter's
cross-attn injections (task #44, Kim green-lit 2026-07-12).

Hypothesis (write-site vs compute-site, narrative §5): the adapter injects at all 24
blocks but the base model computes onset density in late self_attn/ff (L16-23). If
authority survives with ONLY late injections, control enters where rhythm is computed
and the early taps are redundant; the ablation pattern may also explain the 6-9
onsets/s saturation band.

Configs: all / none / early(L0-7) / mid(L8-15) / late(L16-23) x densities {3,6,9,12}
at gain 1.75 (Kim's calibrated default), fixed seed. Same onset meter across configs
(plain librosa — RELATIVE comparison only; absolute numbers carry the known drone
over-fire caveat).

Run: FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/ablate_adapter_layers.py
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

CKPT = "/run/media/kim/Mantu/sa3_control_runs/onset_Fusion_lr1e-4_randomcrop/riffer_final.pt"
OUT = Path("/run/media/kim/Mantu/sa3_control_runs/ablate_layers_2026-07-12")
CONFIGS = {"all": range(24), "none": [], "early": range(0, 8),
           "mid": range(8, 16), "late": range(16, 24)}
DENSITIES = [3.0, 6.0, 9.0, 12.0]
GAIN, SEED, DUR, STEPS, CFG = 1.75, 4242, 20.0, 24, 6.0
PROMPT = "psychedelic goa trance"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ck = torch.load(CKPT, map_location="cpu")
    cargs = ck.get("args", {})
    print("[ckpt args]", json.dumps({k: v for k, v in cargs.items() if not isinstance(v, (list, dict))},
                                    default=str)[:600], flush=True)
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

    sam = StableAudioModel.from_pretrained("medium-base", device="cuda")
    mdtype = next(sam.model.model.parameters()).dtype
    wrappers = install_adapters(sam, control_dim=control_dim)
    enc = ScalarAttributeEncoder(control_dim=control_dim, n_tokens=min(n_tokens, 16)).to("cuda")
    from sa3_control.generate import load_adapter_state
    load_adapter_state(ck["state"], wrappers, enc)
    for w in wrappers:
        w.adapter.to(device="cuda", dtype=mdtype)
    enc.to(device="cuda", dtype=mdtype).eval()
    print(f"[install] {len(wrappers)} wrappers", flush=True)

    # runtime per-wrapper gate (no edits to sa3_control)
    def gated_forward(self, x, context=None, **kw):
        base = self.base_attention(x, context=context, **kw)
        ctx = current_control_context()
        if ctx is not None and ctx.control_tokens is not None and getattr(self, "abl_on", True):
            base = base + ctx.gain * self.adapter(x, self.base_attention, ctx.control_tokens)
        return base
    ControlledCrossAttention.forward = gated_forward

    import librosa
    results = []
    for cname, keep in CONFIGS.items():
        keep = set(keep)
        for i, w in enumerate(wrappers):
            w.abl_on = i in keep
        for d in DENSITIES:
            t = torch.tensor([[(d - norm["mean"]) / norm["std"]]], device="cuda", dtype=mdtype)
            with torch.inference_mode():
                ctrl = enc(t)
            ctrl = torch.cat([ctrl, torch.zeros_like(ctrl)], dim=0)  # cond-only under CFG
            with use_control_context(ControlContext(ctrl, gain=GAIN)):
                audio = sam.generate(prompt=PROMPT, duration=DUR, steps=STEPS,
                                     cfg_scale=CFG, seed=SEED, sampler_type="euler")
            f = OUT / f"{cname}_d{int(d)}.wav"
            save_audio(f, audio[0], sam.model.sample_rate)
            y, sr = librosa.load(str(f), sr=22050, mono=True)
            meas = len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr)
            results.append({"config": cname, "requested": d, "measured": round(float(meas), 2)})
            print(f"[{cname} d{d:.0f}] measured {meas:.2f}", flush=True)

    # per-config authority = corr(requested, measured)
    rep = {}
    for cname in CONFIGS:
        rs = [(r["requested"], r["measured"]) for r in results if r["config"] == cname]
        a = np.array(rs)
        rep[cname] = {"corr": round(float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]), 3),
                      "spread": round(float(a[:, 1].max() - a[:, 1].min()), 2),
                      "cells": rs}
    (OUT / "run_meta.json").write_text(json.dumps(
        {"purpose": "per-layer-group ablation of the onset adapter's 24 cross-attn injections",
         "hypothesis": "write-site != compute-site: if authority survives with only LATE (L16-23) "
                       "injections active, control enters where the base model computes rhythm; "
                       "ablation pattern may explain the 6-9 onsets/s saturation band. "
                       "(narrative §5 / Kim green-light 2026-07-12)",
         "model_training": {"run": "onset_Fusion_lr1e-4_randomcrop (plain FusionOpt FiLM, Kim's "
                                   "07-07 ear-verdict checkpoint)", "checkpoint": "riffer_final.pt step 54000",
                            "dataset": "latents_sa3 T=4096 (5400 crops / 2677 tracks)"},
         "recipe": {"gain": GAIN, "seed": SEED, "duration": DUR, "steps": STEPS, "cfg": CFG,
                    "prompt": PROMPT, "densities": DENSITIES,
                    "meter": "plain librosa onset_detect — RELATIVE use only (drone over-fire caveat)"},
         "result": rep, "kim_feedback": None,
         "script": "SAO/eval/ablate_adapter_layers.py"}, indent=2))
    print("[report]", json.dumps({k: v["corr"] for k, v in rep.items()}), flush=True)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
