#!/usr/bin/env python
"""gain_ladder_layer_restricted.py — Kim's follow-up (2026-07-21): is there a GAIN where the
onset adapters hold authority while staying under the disintegration thresholds?

Context (#56 eval): L8-15 trained-restricted ≈ full-baseline authority, but BOTH hf-blowout at
d6-12 at the calibrated gain 1.75 — the family partially encodes 'more onsets' as HF clicks,
and the L14-single 'clean' result was amputation artifact (1/24 drive under the threshold).
Hypothesis: cleanliness is a DRIVE-magnitude effect => a lower gain should trade spread for
cleanliness; the question is whether corr survives at the clean point, and whether L8-15's
clean point beats the full adapter's (if not, restriction buys nothing).

Ladder: gains {0.5, 0.75, 1.0, 1.25, 1.75, 2.5} x densities {3,6,9,12}, both adapters, same
seed/prompt/steps/cfg as the whole #44 family. Gate screen vs the ablate_layers2 'none' clip.
Per (adapter, gain): corr/spread/flags; verdict = max clean gain + its authority.

Run: FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/gain_ladder_layer_restricted.py
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

ADAPTERS = {
    "full24": "/run/media/kim/Mantu/sa3_control_runs/onset_Fusion_lr1e-4_randomcrop/riffer_final.pt",
    "L8-15":  "/run/media/kim/Mantu/sa3_control_runs/onset_Fusion_lr1e-4_randomcrop_L8-15/riffer_final.pt",
}
OUT = Path("/run/media/kim/Mantu/sa3_control_runs/gain_ladder_2026-07-21")
BASELINE_NONE = Path("/run/media/kim/Mantu/sa3_control_runs/ablate_layers2_2026-07-21/none_d3.wav")
GAINS = [0.5, 0.75, 1.0, 1.25, 1.75, 2.5]
DENSITIES = [3.0, 6.0, 9.0, 12.0]
SEED, DUR, STEPS, CFG = 4242, 20.0, 24, 6.0
PROMPT = "psychedelic goa trance"


def feats(f):
    import librosa
    y, sr = librosa.load(str(f), sr=22050, mono=True)
    S = np.abs(librosa.stft(y, n_fft=2048))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    return {"onsets": len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr),
            "flatness": float(np.mean(librosa.feature.spectral_flatness(S=S))),
            "zcr": float(np.mean(librosa.feature.zero_crossing_rate(y))),
            "hf": float(S[freqs > 6000].sum() / S.sum())}


def gate(m, base):
    r = []
    if m["flatness"] > 0.05 and m["flatness"] / max(base["flatness"], 1e-5) > 2.5:
        r.append("whitening")
    if m["hf"] > 0.05 and m["hf"] / max(base["hf"], 1e-5) > 2.0:
        r.append(f"hf({m['hf']:.3f})")
    if m["zcr"] > 0.15 and m["zcr"] / max(base["zcr"], 1e-5) > 1.6:
        r.append("zcr")
    return r


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    base = feats(BASELINE_NONE)
    report = {}
    for name, ckpt in ADAPTERS.items():
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
        print(f"[{name}] loaded", flush=True)

        report[name] = {}
        for g in GAINS:
            cells, flagged = [], {}
            for d in DENSITIES:
                f = OUT / f"{name}_g{int(g*100):03d}_d{int(d)}.wav"
                if not f.exists():
                    t = torch.tensor([[(d - norm["mean"]) / norm["std"]]], device="cuda", dtype=mdtype)
                    with torch.inference_mode():
                        ctrl = enc(t)
                    ctrl = torch.cat([ctrl, torch.zeros_like(ctrl)], dim=0)
                    with use_control_context(ControlContext(ctrl, gain=float(g))):
                        audio = sam.generate(prompt=PROMPT, duration=DUR, steps=STEPS,
                                             cfg_scale=CFG, seed=SEED, sampler_type="euler")
                    save_audio(f, audio[0], sam.model.sample_rate)
                m = feats(f)
                cells.append((d, round(m["onsets"], 2)))
                fl = gate(m, base)
                if fl:
                    flagged[f"d{int(d)}"] = fl
            a = np.array(cells)
            rep = {"corr": round(float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]), 3),
                   "spread": round(float(a[:, 1].max() - a[:, 1].min()), 2),
                   "cells": cells, "flags": flagged}
            report[name][g] = rep
            print(f"  [{name} g{g}] corr {rep['corr']:+.3f} spread {rep['spread']:5.2f} "
                  f"{'⚠ ' + ','.join(flagged) if flagged else 'clean'} "
                  f"cells={[c[1] for c in cells]}", flush=True)
        del sam, wrappers, enc
        torch.cuda.empty_cache()

    (OUT / "report.json").write_text(json.dumps(
        {"purpose": "gain ladder: clean operating point search (Kim follow-up 2026-07-21)",
         "baseline_none": base, "recipe": {"seed": SEED, "steps": STEPS, "cfg": CFG, "prompt": PROMPT},
         "result": report}, indent=2))
    print("\n=== clean-point verdict (highest clean gain per adapter) ===")
    for name, ladder in report.items():
        clean = [(g, v) for g, v in ladder.items() if not v["flags"]]
        if clean:
            g, v = max(clean, key=lambda kv: kv[0])
            print(f"  {name:8s} max clean gain {g}: corr {v['corr']:+.3f} spread {v['spread']:.2f}")
        else:
            print(f"  {name:8s} NO clean gain in ladder")
    print(f"-> {OUT}/report.json")


if __name__ == "__main__":
    main()
