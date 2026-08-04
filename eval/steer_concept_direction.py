#!/usr/bin/env python
"""steer_concept_direction.py — inject diff-in-means concept directions into the SA3
DiT residual stream during sampling (Phase 3; papers/arxiv-2505.18186.md, Kim ask
2026-07-11: "the 'happy' etc qualifiers might be very cool if we could steer by them").

Mechanics (paper's op adapted to diffusion): for chosen blocks, block_out += alpha * dir
on the last T positions (prepended memory tokens untouched); direction added ONLY to the
CONDITIONAL CFG branch — dit.py:483 builds torch.cat([cond, uncond]), so the conditional
is the FIRST half of the doubled batch. (Deep-research consensus 2026-07-11: steering the
uncond branch corrupts the CFG baseline subtraction -> off-manifold blowup; conditional-only
behaves like a refined prompt and stays anchored. papers/deep-research/
2026-07-11-activation-steering-dit-audio.md §"Target Selection".) The direction is
sigma-matched: a forward-pre-hook on the DiT reads the current timestep and the block
hooks use the direction from the nearest dumped sigma bucket {0.2, 0.5, 0.8}.

Run (SA3 venv, GPU):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/steer_concept_direction.py \
      --feature happy --alphas 0,2,-2,6,-6 --out-dir <dir>
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "latch"))
from sa3_control.audio_io import save_audio               # noqa: E402
from stable_audio_3 import StableAudioModel               # noqa: E402
from extract_layer_activations import get_blocks          # noqa: E402

DUMP = Path("/run/media/kim/Mantu/sa3_lora_runs/layer_activations_base")
SIG_KEYS = {0.2: "s20", 0.5: "s50", 0.8: "s80"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature", required=True, help="score column, e.g. happy / aggressive / onset_density")
    ap.add_argument("--layers", default=None, help="comma ints; default = report's recommended top-2")
    ap.add_argument("--alphas", default="0,2,-2,6,-6")
    ap.add_argument("--prompt", default="goa trance, 1996, 145")
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    z = np.load(DUMP / "concept_directions.npz")
    report = json.loads((DUMP / "concept_directions.json").read_text())["report"][args.feature]
    layers = ([int(x) for x in args.layers.split(",")] if args.layers
              else report["recommended_layers"][:2])
    alphas = [float(x) for x in args.alphas.split(",")]
    dirs = {s: torch.tensor(z[f"{args.feature}__{k}"]) for s, k in SIG_KEYS.items()}  # [24,1536]

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    dirs = {s: d.to(device, mdtype) for s, d in dirs.items()}
    blocks = get_blocks(model)

    ds = cdm.pretransform.downsampling_ratio
    sr = cdm.sample_rate
    T = int(np.ceil(args.duration * sr / ds))

    state = {"alpha": 0.0, "sigma": 0.5}

    def pre_hook(_m, hargs, hkwargs):
        t = hargs[1] if len(hargs) > 1 else hkwargs.get("t")
        if t is not None:
            state["sigma"] = float(t.flatten()[0])
        return None
    pre = cdm.model.register_forward_pre_hook(pre_hook, with_kwargs=True)

    def mk(layer_idx):
        def hook(_m, _inp, out):
            if state["alpha"] == 0.0:
                return out
            tup = isinstance(out, tuple)
            o = out[0] if tup else out
            s = min(SIG_KEYS, key=lambda k: abs(k - state["sigma"]))
            o = o.clone()
            # conditional branch only: CFG doubles the batch as cat([cond, uncond])
            # (dit.py:483); with no CFG doubling the whole batch IS conditional
            b = o.shape[0]
            nc = b // 2 if b > 1 else b
            o[:nc, -T:, :] += state["alpha"] * dirs[s][layer_idx]
            return (o, *out[1:]) if tup else o
        return hook
    hooks = [blocks[l].register_forward_hook(mk(l)) for l in layers]

    print(f"[steer] feature={args.feature} layers={layers} alphas={alphas} "
          f"(report best: {report['best']})", flush=True)
    renders = []
    try:
        for a in alphas:
            state["alpha"] = a
            out = model.generate(prompt=args.prompt, duration=args.duration,
                                 steps=args.steps, cfg_scale=args.cfg_scale,
                                 seed=args.seed, batch_size=1, sample_size=T * ds)
            tag = f"{args.feature}_a{a:+.1f}".replace("+0.0", "0")
            save_audio(args.out_dir / f"{tag}.wav", out[0].float().cpu(), sr, normalize=True)
            renders.append(tag)
            print(f"[done] {tag}", flush=True)
    finally:
        for h in hooks:
            h.remove()
        pre.remove()

    (args.out_dir / "run_meta.json").write_text(json.dumps(
        {"purpose": "diff-in-means concept-direction steering A/B (arxiv-2505.18186 "
                    "adaptation to SA3 DiT): base model, direction added to block outputs "
                    "on the CONDITIONAL CFG branch ONLY (first half of the doubled batch, "
                    "dit.py:483; per deep-research consensus 2026-07-11), sigma-matched "
                    "bucket, alpha ladder incl. 0 baseline and negative (anti-concept).",
         "feature": args.feature, "layers": layers, "alphas": alphas,
         "held_out_validation": report["best"], "prompt": args.prompt,
         "duration": args.duration, "steps": args.steps, "cfg_scale": args.cfg_scale,
         "seed": args.seed, "renders": renders,
         "directions_from": str(DUMP / "concept_directions.npz")}, indent=2))
    print(f"[all done] {len(renders)} renders -> {args.out_dir}", flush=True)


if __name__ == "__main__":
    main()
