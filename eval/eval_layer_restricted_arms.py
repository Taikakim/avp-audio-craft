#!/usr/bin/env python
"""eval_layer_restricted_arms.py — authority + disintegration screen for the layer-restricted
onset adapters (task #56, trained 2026-07-21: L8-15 and L13-15, exact 07-12 baseline recipe).

Renders each arm at its TRAINED config (all installed taps active — the restricted ones are
the only non-zero adapters, the rest are zero-init no-ops), densities {3,6,9,12} at gain 1.75,
same seed/prompt/steps/cfg as the whole #44 family, and reports corr/spread against the three
references (full 24-tap baseline: corr .912 spread 8.05 but HF-flagged; L14 single-tap
ablation: corr .968 spread 7.1 clean; none: flat 4.25-4.4). Gate screen reuses the
ablate_layers2 'none' clip as the same-recipe unsteered baseline.

Run: FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/eval_layer_restricted_arms.py
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
from sa3_control.adapters import ControlContext, use_control_context          # noqa: E402
from sa3_control.conditioner import ScalarAttributeEncoder                    # noqa: E402
from sa3_control.generate import load_adapter_state                           # noqa: E402
from stable_audio_3 import StableAudioModel                                   # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disintegration_metrics import measure, gate                              # noqa: E402

ARMS = {
    "L8-15":  "/run/media/kim/Mantu/sa3_control_runs/onset_Fusion_lr1e-4_randomcrop_L8-15/riffer_final.pt",
    "L13-15": "/run/media/kim/Mantu/sa3_control_runs/onset_Fusion_lr1e-4_randomcrop_L13-15/riffer_final.pt",
}
OUT = Path("/run/media/kim/Mantu/sa3_control_runs/layer_restricted_eval_2026-07-21")
BASELINE_NONE = Path("/run/media/kim/Mantu/sa3_control_runs/ablate_layers2_2026-07-21/none_d3.wav")
DENSITIES = [3.0, 6.0, 9.0, 12.0]
GAIN, SEED, DUR, STEPS, CFG = 1.75, 4242, 20.0, 24, 6.0
PROMPT = "psychedelic goa trance"
REFS = {"all24_baseline": {"corr": 0.912, "spread": 8.05, "gate": "HF-FLAGGED d6-12"},
        "L14_single_abl": {"corr": 0.968, "spread": 7.10, "gate": "clean"}}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    base = measure(BASELINE_NONE)
    print(f"[baseline none] {json.dumps({k: round(v, 4) for k, v in base.items()})}")

    report = {}
    for arm, ckpt in ARMS.items():
        ck = torch.load(ckpt, map_location="cpu")
        cargs = ck.get("args", {})
        raw = ck.get("scalar_norm")
        norm = ({"mean": float(raw[0]), "std": float(raw[1])} if isinstance(raw, (list, tuple))
                else {"mean": float(raw["mean"]), "std": float(raw["std"])} if isinstance(raw, dict)
                else {"mean": 7.1, "std": 2.5})
        sam = StableAudioModel.from_pretrained("medium-base", device="cuda")
        mdtype = next(sam.model.model.parameters()).dtype
        wrappers = install_adapters(sam, control_dim=int(cargs.get("control_dim", 768)))
        enc = ScalarAttributeEncoder(control_dim=int(cargs.get("control_dim", 768)),
                                     n_tokens=min(int(cargs.get("n_tokens", 256)), 16)).to("cuda")
        load_adapter_state(ck["state"], wrappers, enc)
        for w in wrappers:
            w.adapter.to(device="cuda", dtype=mdtype)
        enc.to(device="cuda", dtype=mdtype).eval()
        print(f"[{arm}] loaded ({cargs.get('adapter_layers', '?')} trained)", flush=True)

        cells, flags = [], {}
        for d in DENSITIES:
            f = OUT / f"{arm}_d{int(d)}.wav"
            if not f.exists():
                t = torch.tensor([[(d - norm["mean"]) / norm["std"]]], device="cuda", dtype=mdtype)
                with torch.inference_mode():
                    ctrl = enc(t)
                ctrl = torch.cat([ctrl, torch.zeros_like(ctrl)], dim=0)
                with use_control_context(ControlContext(ctrl, gain=GAIN)):
                    audio = sam.generate(prompt=PROMPT, duration=DUR, steps=STEPS,
                                         cfg_scale=CFG, seed=SEED, sampler_type="euler")
                save_audio(f, audio[0], sam.model.sample_rate)
            m = measure(f)
            cells.append((d, round(m["onsets"], 2)))
            r = gate(m, base)["reasons"]
            if r:
                flags[f"d{int(d)}"] = r
            print(f"  [{arm} d{d:.0f}] onsets {m['onsets']:.2f}  hf {m['hf']:.4f}"
                  f"  {'⚠ ' + ','.join(r) if r else 'clean'}", flush=True)
        a = np.array(cells)
        report[arm] = {"corr": round(float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]), 3),
                       "spread": round(float(a[:, 1].max() - a[:, 1].min()), 2),
                       "cells": cells, "gate_flags": flags, "ckpt": ckpt}
        del sam, wrappers, enc
        torch.cuda.empty_cache()

    (OUT / "report.json").write_text(json.dumps(
        {"purpose": "authority + gate for the layer-restricted arms (task #56)",
         "recipe": {"gain": GAIN, "seed": SEED, "steps": STEPS, "cfg": CFG, "prompt": PROMPT},
         "references": REFS, "result": report}, indent=2))
    print("\n=== VERDICT vs references ===")
    for k, v in REFS.items():
        print(f"  {k:16s} corr {v['corr']:+.3f} spread {v['spread']:.2f}  {v['gate']}")
    for arm, v in report.items():
        gate = "clean" if not v["gate_flags"] else "⚠ " + json.dumps(v["gate_flags"])
        print(f"  {arm:16s} corr {v['corr']:+.3f} spread {v['spread']:.2f}  {gate}")
    print(f"-> {OUT}/report.json")


if __name__ == "__main__":
    main()
