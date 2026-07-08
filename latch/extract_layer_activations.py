#!/usr/bin/env python
"""extract_layer_activations.py — the GPU half of the layer×feature map
(probe_layer_feature_map.py's deferred extract_activations, implemented).

For N sampled crops from latents_sa3: noise the REAL latent to each requested
sigma (fixed eps seed), run ONE conditioned DiT forward (the crop's own stored
prompt, generate()'s own conditioning assembly mirrored), capture every
transformer block's output via forward hooks, subsample frames, save per-sigma
npz packs consumable by run_map(). Complements W's latent-dim×feature xcorr
(input-space) with the DiT's internal representation space — and gives the
TADA-style localization question its correlational answer.

Run (SA3 venv, GPU):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python \
      ../latch/extract_layer_activations.py --n-crops 150 --out-dir <dir>
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from stable_audio_3 import StableAudioModel


def get_blocks(model):
    """The `layers.N` sites: the DiT's ContinuousTransformer blocks."""
    dit = model.dit  # DiTWrapper
    tf = None
    for name, mod in dit.named_modules():
        if name.endswith("transformer") and hasattr(mod, "layers"):
            tf = mod
            break
    if tf is None:
        raise RuntimeError("could not locate ContinuousTransformer with .layers")
    return list(tf.layers)


def extract(model, z, prompt, seconds_total, sigmas, frame_idx, eps_seed=7):
    """z: [1,256,T] latent. Returns {sigma: [L, len(frame_idx), d] fp16}."""
    device = next(model.model.model.parameters()).device
    mdtype = next(model.model.model.parameters()).dtype
    cdm = model.model

    conditioning = [{"prompt": prompt, "seconds_total": seconds_total}]
    tensors = cdm.conditioner(conditioning, str(device))
    # inpaint conditioning: zeros mask/input (text-to-audio convention — the DiT
    # projects local_add_cond with a bias, None != zeros; MASTER §5)
    T = z.shape[-1]
    mask = torch.zeros((1, 1, T), device=device)
    tensors["inpaint_mask"] = [mask]
    tensors["inpaint_masked_input"] = [torch.zeros_like(z, device=device)]
    cond_inputs = cdm.get_conditioning_inputs(tensors)
    cond_inputs = {k: (v.type(mdtype) if torch.is_tensor(v) else v)
                   for k, v in cond_inputs.items()}

    blocks = get_blocks(model)
    grabbed = {}
    hooks = []

    def mk(i):
        def hook(_m, _inp, out):
            o = out[0] if isinstance(out, tuple) else out
            # [1, T(+prepend), d] -> keep the LAST T positions (memory tokens are
            # prepended), then subsample the requested frames
            o = o[0, -T:, :]
            grabbed[i] = o[frame_idx].detach().to(torch.float16).cpu()
        return hook

    for i, b in enumerate(blocks):
        hooks.append(b.register_forward_hook(mk(i)))

    out = {}
    try:
        g = torch.Generator(device="cpu").manual_seed(eps_seed)
        eps = torch.randn(z.shape, generator=g).to(device, mdtype)
        z = z.to(device, mdtype)
        for s in sigmas:
            x_t = (1 - s) * z + s * eps
            t = torch.full((1,), float(s), device=device, dtype=mdtype)
            grabbed.clear()
            with torch.no_grad():
                cdm.model(x_t, t, **cond_inputs)
            out[s] = torch.stack([grabbed[i] for i in range(len(blocks))]).numpy()
    finally:
        for h in hooks:
            h.remove()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latent-dir", default="/home/kim/Projects/latents_sa3")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--n-crops", type=int, default=150)
    ap.add_argument("--n-frames", type=int, default=96, help="subsampled frames/crop")
    ap.add_argument("--sigmas", default="0.2,0.5,0.8")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    sigmas = [float(x) for x in args.sigmas.split(",")]

    rng = np.random.default_rng(args.seed)
    stems = sorted(p.stem for p in Path(args.latent_dir).glob("*.npy"))
    picks = rng.choice(len(stems), size=min(args.n_crops, len(stems)), replace=False)
    picks = [stems[i] for i in sorted(picks)]

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    manifest = {"crops": [], "sigmas": sigmas, "n_frames": args.n_frames,
                "frame_stride_note": "uniform grid over T=4096", "eps_seed": 7,
                "model": "medium-base (no adapter)"}
    t_all = time.time()
    for ci, stem in enumerate(picks):
        z = torch.tensor(np.load(f"{args.latent_dir}/{stem}.npy")).float()
        if z.dim() == 2:
            z = z.unsqueeze(0)
        T = z.shape[-1]
        frame_idx = np.linspace(0, T - 1, args.n_frames).astype(int)
        meta = json.load(open(f"{args.latent_dir}/{stem}.json"))
        t0 = time.time()
        acts = extract(model, z, meta.get("prompt", ""),
                       float(meta.get("seconds_total", T / 10.7666)),
                       sigmas, frame_idx)
        for s, arr in acts.items():
            np.save(args.out_dir / f"{stem}__s{int(s*100):02d}.npy", arr)
        manifest["crops"].append({"stem": stem, "frames": frame_idx.tolist()})
        if ci % 10 == 0:
            print(f"[{ci+1}/{len(picks)}] {stem} {time.time()-t0:.1f}s", flush=True)
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest))
    print(f"[done] {len(picks)} crops x {len(sigmas)} sigmas in "
          f"{(time.time()-t_all)/60:.1f} min -> {args.out_dir}", flush=True)


if __name__ == "__main__":
    main()
