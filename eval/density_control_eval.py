#!/usr/bin/env python
"""density_control_eval.py — LatCH vs FiLM vs both-at-half density control over the
short-clip eval grid (Kim 2026-07-07).

For every (arm x prompt x style x seed) of the newcap8_promptstyle grid, render 6
control conditions:
    latch_d3 / latch_d7 — onset_envelope LatCH guidance, beat_grid target at
                          density*60 BPM, rho=mu=LATCH_GAIN
    film_d3  / film_d7  — FusionCC onset-density FiLM adapter, gain FILM_GAIN
    both_d3  / both_d7  — both simultaneously at HALF each
Densities 3 and 7 onsets/sec. Same gen params as the base grid (47s/16 steps/cfg6).

LatCH gain: the 14-head sweep (MASTER §5) found onset heads dead for CONSTANT
targets at any gain; this re-tests with impulse-train (beat_grid) targets at the
energy-head operating gain 512. FiLM gain 6.0 = steered_longform's default.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import argparse
import json
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
from sa3_control.audio_io import save_audio  # noqa: E402
from sa3_control.adapters import ControlContext, use_control_context  # noqa: E402
from sa3_control.inject import install_adapters  # noqa: E402
from sa3_control.conditioner import ScalarAttributeEncoder  # noqa: E402
from sa3_control.generate import load_adapter_state  # noqa: E402

from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.models import transformer as _sa3_tf  # noqa: E402
_sa3_tf.flex_attention_available = False
_sa3_tf.flex_attention_compiled = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_prompt_styles import DEFAULT_ARMS, ARM_STRENGTH, PROMPTS  # noqa: E402

LATCH_HEAD = ("/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/"
              "latch_sa3_onset_envelope_best.pt")
FILM_CKPT = ("/run/media/kim/Mantu1/sa3_control_runs/"
             "onset_FusionCC_lr1e-4_randomcrop/riffer_final.pt")
LATCH_GAIN = 512.0
FILM_GAIN = 6.0
DENSITIES = (3.0, 7.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--arms", default="base,newcap5,newcap8,evr1x,evr3x,evr3x_w033")
    ap.add_argument("--steps", type=int, default=16)
    ap.add_argument("--duration", type=float, default=47.0)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--seeds", default="1234,4242")
    args = ap.parse_args()

    seeds = [int(s) for s in args.seeds.split(",")]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    device = "cuda"

    film_ck = torch.load(FILM_CKPT, map_location="cpu", weights_only=False)
    mean, std = film_ck.get("scalar_norm", [7.219, 1.424])
    n_tokens = min(int(film_ck["args"].get("n_tokens", 16)), 16)
    control_dim = int(film_ck["args"].get("control_dim", 768))

    meta = {
        "purpose": ("density-control comparison over the prompt-style grid: onset LatCH "
                    "(beat_grid impulse target) vs FusionCC FiLM adapter vs both-at-half, "
                    "densities 3 and 7 onsets/sec"),
        "control": {"latch_head": LATCH_HEAD, "latch_gain_rho_mu": LATCH_GAIN,
                    "film_ckpt": FILM_CKPT, "film_gain": FILM_GAIN,
                    "densities": list(DENSITIES),
                    "half_weight_rule": "both condition: film gain/2 + latch rho,mu/2"},
        "gen": {"duration": args.duration, "steps": args.steps, "cfg": args.cfg_scale,
                "seeds": seeds},
        "checkpoints": {},
        "related": ["SAO/eval/density_control_eval.py",
                    "SAO/eval/eval_prompt_styles.py (the uncontrolled grid)"],
    }

    for arm in args.arms.split(","):
        if arm in ARM_STRENGTH:
            ckpt, strength = DEFAULT_ARMS[ARM_STRENGTH[arm][0]], ARM_STRENGTH[arm][1]
        else:
            ckpt, strength = DEFAULT_ARMS[arm], 1.0
        meta["checkpoints"][arm] = ((ckpt or "medium-base (no adapter)") +
                                    (f" @strength {strength}" if strength != 1.0 else ""))
        print(f"[load] {arm} ...", flush=True)
        sam = StableAudioModel.from_pretrained("medium-base", device=device)
        if ckpt:
            sam.load_lora([str(ckpt)])
            if strength != 1.0:
                sam.set_lora_strength(strength)
        md = next(sam.model.model.parameters()).dtype
        sr = sam.model.sample_rate
        wrappers = install_adapters(sam, control_dim=control_dim)
        enc = ScalarAttributeEncoder(control_dim=control_dim, n_tokens=n_tokens)
        load_adapter_state(film_ck["state"], wrappers, enc)
        for w in wrappers:
            w.adapter.to(device=device, dtype=md)
        enc.to(device=device, dtype=md).eval()

        def film_ctx(density, gain):
            s = torch.tensor([(density - mean) / std], device=device, dtype=md)
            ctrl = enc(s)
            cc = torch.cat([ctrl, torch.zeros_like(ctrl)], 0)  # cond + trained-null uncond
            return use_control_context(ControlContext(cc, gain=gain))

        def latch_cfg(density, weight_scale):
            return ([{"model_path": LATCH_HEAD, "kind": "beat_grid",
                      "value": density * 60.0, "weight": 1.0}],
                    {"rho": LATCH_GAIN * weight_scale, "mu": LATCH_GAIN * weight_scale})

        for label, plain, styled in PROMPTS:
            for style, prompt in (("plain", plain), ("styled", styled)):
                for seed in seeds:
                    for d in DENSITIES:
                        dn = int(d)
                        for cond in (f"latch_d{dn}", f"film_d{dn}", f"both_d{dn}"):
                            out = args.out_dir / f"{arm}__{label}_{style}_s{seed}__{cond}.wav"
                            if out.exists():
                                print(f"[skip] {out.name}", flush=True)
                                continue
                            t0 = time.time()
                            kw = dict(prompt=prompt, duration=args.duration,
                                      steps=args.steps, cfg_scale=args.cfg_scale,
                                      seed=seed, batch_size=1)
                            if cond.startswith("latch"):
                                lc, hp = latch_cfg(d, 1.0)
                                audio = sam.generate(latch_configs=lc, latch_hparams=hp, **kw)
                            elif cond.startswith("film"):
                                with film_ctx(d, FILM_GAIN):
                                    audio = sam.generate(**kw)
                            else:  # both at half
                                lc, hp = latch_cfg(d, 0.5)
                                with film_ctx(d, FILM_GAIN / 2):
                                    audio = sam.generate(latch_configs=lc,
                                                         latch_hparams=hp, **kw)
                            save_audio(out, audio[0], sr, normalize=True)
                            print(f"[clip] {out.name}  {time.time()-t0:5.1f}s", flush=True)
        del sam, wrappers, enc
        torch.cuda.empty_cache()

    (args.out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
