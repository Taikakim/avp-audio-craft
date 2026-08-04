#!/usr/bin/env python
"""arc_rollout_dataset.py — ARC-Forcing rollout dataset builder (task #46 part 1).

Exposure-bias training data: the model must learn to continue from ITS OWN drifted
output, not from ground truth. Per sample: cut a T=1024 window from a latents_sa3
crop, split into context (first --tctx frames, default 512) + continuation; re-render
the context through the model a2a-style (latent-domain SDEdit at --rollout-nl, per-
sample seed) so the stored context is the model's own imperfect reconstruction; save
the TRUE full window as the target with a mask marking the clamped context region.

Data contract (shared, task #46): one .npz per sample —
  context_latent  fp16 (256, Tctx)   the RE-RENDERED (drifted) context
  target_latent   fp16 (256, 1024)   the TRUE window (context + continuation);
                                     loss frames are mask==0
  mask            uint8 (1024,)      1 = frame CLAMPED (context visible to model),
                                     0 = to-generate. mask[:Tctx] = 1.
  prompt          str                from the crop's .json meta
  meta            json str           source stem, crop offset, rollout nl, ckpt id, seed
plus a manifest.json at dir root (hypothesis, ckpt recipe, dataset info, params).

Rollout path: reuses stable_audio_3.inference.longform.SDEditReanchor — the tested
latent-space a2a (sample_diffusion(init_data=latent, init_noise_level=nl,
decode=False)); the latent inits the sampler directly, no decode->re-encode round trip
(generate(init_audio=...) only takes audio and would waste a SAME decode+encode).

Run (LUMI / GPU): FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python \
    eval/arc_rollout_dataset.py --out <dir> --lora-ckpt <ckpt> --n-samples 2000
Smoke (CPU, no model, no GPU): .venv/bin/python eval/arc_rollout_dataset.py \
    --out /tmp/arc_smoke --dry-run
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

LATENTS = Path("/home/kim/Projects/latents_sa3")
LATENT_CH = 256
T_TOTAL = 1024      # context + free region, frames (multiples-of-256 rule, MASTER §5)
SRC_T = 4096        # latents_sa3 crop length
FPS = 10.7666       # SA3 latent frame rate


def pick_samples(stems, n, rng, align):
    """Seeded (stem, offset) picks, deduped; offsets on the align grid."""
    n_off = (SRC_T - T_TOTAL) // align + 1
    picks, seen, attempts = [], set(), 0
    while len(picks) < n and attempts < n * 20:
        attempts += 1
        key = (int(rng.integers(len(stems))), int(rng.integers(n_off)) * align)
        if key in seen:
            continue
        seen.add(key)
        picks.append((stems[key[0]], key[1]))
    return picks


class DryRollout:
    """--dry-run stand-in: fabricates the 're-render' (context + noise), no torch."""
    ckpt_id = "dry-run (no model)"

    def __init__(self, nl):
        self.nl = nl

    def rollout(self, context, prompt, seed):
        rng = np.random.default_rng(seed)
        drift = rng.standard_normal(context.shape).astype(np.float32)
        return (context.astype(np.float32) * (1 - 0.1 * self.nl)
                + 0.1 * self.nl * drift).astype(np.float16)


class ModelRollout:
    """Latent-domain SDEdit re-render via longform.SDEditReanchor (reuse, tested)."""

    def __init__(self, args):
        import torch
        from stable_audio_3 import StableAudioModel
        from stable_audio_3.inference.longform import SDEditReanchor
        self.torch = torch
        model = StableAudioModel.from_pretrained(args.model, device=args.device)
        if args.lora_ckpt:
            model.load_lora([args.lora_ckpt])
        self.reanchor = SDEditReanchor(model, steps=args.steps, cfg_scale=args.cfg_scale)
        self.nl = args.rollout_nl
        self.ckpt_id = (Path(args.lora_ckpt).name if args.lora_ckpt else args.model)

    def rollout(self, context, prompt, seed):
        z = self.torch.from_numpy(context.astype(np.float32))[None]  # (1, 256, Tctx)
        out = self.reanchor.reanchor(z, self.nl, prompt, seed)
        return out[0].cpu().numpy().astype(np.float16)


def write_manifest(args, out_dir, ckpt_id, n_source_files):
    files = sorted(p.name for p in out_dir.glob("*.npz"))
    manifest = {
        "hypothesis": "ARC-Forcing / exposure bias: training continuation on ground-truth "
                      "context never shows the model its own drift; clamping a SDEdit "
                      "re-render of the context (the model's own imperfect reconstruction) "
                      "as the visible region teaches it to continue from drifted state.",
        "contract": {
            "context_latent": f"fp16 (256, {args.tctx}) — re-rendered (drifted) context",
            "target_latent": f"fp16 (256, {T_TOTAL}) — TRUE window; train on mask==0 frames",
            "mask": f"uint8 ({T_TOTAL},) — 1 = clamped context visible to model, "
                    "0 = to-generate; mask[:tctx] = 1",
            "prompt": "str", "meta": "json str (source stem, crop offset, rollout nl, ckpt id)",
        },
        "ckpt_recipe": {"model": args.model, "lora_ckpt": args.lora_ckpt,
                        "ckpt_id": ckpt_id},
        "dataset_info": {"latents_dir": str(args.latents_dir),
                         "n_source_files": n_source_files,
                         "source_grid": f"(1, {LATENT_CH}, {SRC_T}) fp16, {FPS} Hz"},
        "generation_params": {"tctx": args.tctx, "t_total": T_TOTAL,
                              "rollout_nl": args.rollout_nl, "steps": args.steps,
                              "cfg_scale": args.cfg_scale, "seed": args.seed,
                              "n_samples": args.n_samples,
                              "offset_align": args.offset_align,
                              "dry_run": args.dry_run},
        "script": "SAO/eval/arc_rollout_dataset.py",
        "files": files,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--latents-dir", type=Path, default=LATENTS)
    ap.add_argument("--n-samples", type=int, default=2000)
    ap.add_argument("--tctx", type=int, default=512,
                    help="context frames (multiple of 256; rest of T=1024 is to-generate)")
    ap.add_argument("--rollout-nl", type=float, default=0.5,
                    help="SDEdit init_noise_level for the context re-render")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--model", default="medium-base")
    ap.add_argument("--lora-ckpt", default=None,
                    help="adapter whose OWN drift the dataset should capture")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--offset-align", type=int, default=256,
                    help="crop-offset grid in frames")
    ap.add_argument("--limit", type=int, default=None, help="stop after N samples (smoke)")
    ap.add_argument("--dry-run", action="store_true",
                    help="no model: fabricate the re-render, write one sample end-to-end")
    args = ap.parse_args()
    assert 0 < args.tctx < T_TOTAL and args.tctx % 256 == 0, "--tctx must be a multiple of 256 in (0, 1024)"
    args.out.mkdir(parents=True, exist_ok=True)
    if args.dry_run and args.limit is None:
        args.limit = 1

    if args.latents_dir.is_dir():
        stems = sorted(p.stem for p in args.latents_dir.glob("*.npy"))
    else:
        stems = []
    if not stems:
        assert args.dry_run, f"no .npy under {args.latents_dir}"
        stems = ["fabricated"]
    rng = np.random.default_rng(args.seed)
    picks = pick_samples(stems, args.n_samples, rng, args.offset_align)
    todo = [(i, s, o) for i, (s, o) in enumerate(picks)
            if not (args.out / f"{i:06d}.npz").exists()]
    print(f"[arc] {len(stems)} source crops -> {len(picks)} picks (seed {args.seed}); "
          f"{len(todo)} to do, tctx={args.tctx}, nl={args.rollout_nl}", flush=True)

    roller = DryRollout(args.rollout_nl) if args.dry_run else ModelRollout(args)
    write_manifest(args, args.out, roller.ckpt_id, len(stems))
    if not args.dry_run:
        print(f"[arc] {roller.ckpt_id} loaded on {args.device}", flush=True)

    done = 0
    for idx, stem, off in todo:
        if args.limit is not None and done >= args.limit:
            break
        t0 = time.time()
        npy = args.latents_dir / f"{stem}.npy"
        if npy.exists():
            lat = np.load(npy)     # (256, 4096) fp16 (some older files (1, 256, 4096))
            if lat.ndim == 3:
                lat = lat[0]
            src_meta = json.loads((args.latents_dir / f"{stem}.json").read_text())
            prompt = src_meta.get("prompt", "")
        else:  # dry-run without the corpus (e.g. LUMI smoke before data sync)
            lat = np.random.default_rng(idx).standard_normal(
                (LATENT_CH, SRC_T)).astype(np.float16)
            prompt = "fabricated dry-run latent"
        if lat.shape[-1] < off + T_TOTAL:
            print(f"[skip {idx:06d}] {stem}: only {lat.shape[-1]} frames", flush=True)
            continue
        window = lat[:, off:off + T_TOTAL]              # TRUE window (256, 1024)
        rollout_seed = (args.seed * 1_000_003 + idx) % (2 ** 31)
        ctx_render = roller.rollout(window[:, :args.tctx], prompt, rollout_seed)
        mask = np.zeros(T_TOTAL, dtype=np.uint8)
        mask[:args.tctx] = 1
        meta = json.dumps({"source_stem": stem, "crop_offset": off,
                           "t_total": T_TOTAL, "tctx": args.tctx,
                           "rollout_nl": args.rollout_nl, "steps": args.steps,
                           "cfg_scale": args.cfg_scale, "ckpt_id": roller.ckpt_id,
                           "rollout_seed": rollout_seed, "fps": FPS})
        out_path = args.out / f"{idx:06d}.npz"
        # dot-prefixed so the manifest glob skips it; .npz kept (savez appends it otherwise)
        tmp = out_path.with_name(f".{out_path.name}.tmp.npz")
        np.savez(tmp, context_latent=ctx_render.astype(np.float16),
                 target_latent=window.astype(np.float16), mask=mask,
                 prompt=prompt, meta=meta)
        tmp.rename(out_path)
        done += 1
        print(f"[{done}/{len(todo)}] {idx:06d} <- {stem}@{off} "
              f"({time.time() - t0:.1f}s)", flush=True)

    write_manifest(args, args.out, roller.ckpt_id, len(stems))
    print(f"[arc done] {done} written, manifest updated", flush=True)


if __name__ == "__main__":
    main()
