#!/usr/bin/env python
"""longform_crossfade_eval.py — 2048-frame renders with a 512-frame latent slerp
crossfade in the middle, per arm (Kim 2026-07-07).

Each render: segment A (seed S1, 1280 frames) latent-crossfaded into segment B
(seed S2, 1280 frames) using the longform machinery's slerp (CrossfadeStitcher.
transition_join) -> 768 + 512 + 768 = 2048 frames (~190 s). Both seed orders
rendered per arm. Prompt: the aggr eval prompt only.

Reuses stable_audio_3.inference.longform (the SDEdit/crossfade tech we already
have) rather than re-deriving the blend.
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
from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.inference.longform import CrossfadeStitcher  # noqa: E402

# arm registry shared with the short-clip harness
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_prompt_styles import DEFAULT_ARMS, ARM_STRENGTH  # noqa: E402

PROMPT = "aggressive upbeat goa trance"
FRAMES_PER_SEC = 44100 / 4096  # SAME 4096x downsampling = 10.7666 Hz


def gen_latents(model, seed, frames, steps, cfg):
    dur = frames / FRAMES_PER_SEC
    z = model.generate(prompt=PROMPT, duration=dur, steps=steps, cfg_scale=cfg,
                       seed=seed, batch_size=1, return_latents=True)
    if z.shape[-1] < frames:
        raise RuntimeError(f"got {z.shape[-1]} frames, wanted {frames}")
    return z[..., :frames]


def decode(model, z):
    """Decode latents -> audio; halve into two overlapping chunks on OOM."""
    pre = model.model.pretransform
    # slerp's float32 ramp promotes the latents; match the decoder's dtype/device
    p = next(pre.parameters())
    z = z.to(device=p.device, dtype=p.dtype)
    try:
        with torch.inference_mode():
            return pre.decode(z)[0].float().cpu()
    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache()
        ov = 64  # frames of decode overlap, audio-crossfaded
        mid = z.shape[-1] // 2
        with torch.inference_mode():
            a = pre.decode(z[..., :mid + ov])[0].float().cpu()
            torch.cuda.empty_cache()
            b = pre.decode(z[..., mid - ov:])[0].float().cpu()
        spf = 4096  # samples per frame
        n = 2 * ov * spf
        ramp = torch.linspace(0, 1, n).view(1, n)
        blend = a[:, -n:] * (1 - ramp) + b[:, :n] * ramp
        return torch.cat([a[:, :-n], blend, b[:, n:]], dim=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--arms", default="base,newcap5,newcap8,evr1x,evr3x,evr3x_w033")
    ap.add_argument("--frames", type=int, default=2048)
    ap.add_argument("--xfade", type=int, default=512)
    ap.add_argument("--steps", type=int, default=16)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--seeds", default="1234,4242")
    args = ap.parse_args()

    s1, s2 = [int(s) for s in args.seeds.split(",")]
    seg = (args.frames + args.xfade) // 2          # 1280 for 2048/512
    keep = seg - args.xfade                        # 768 un-blended frames per side
    stitcher = CrossfadeStitcher()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "purpose": ("longform latent-crossfade audition: 2048-frame renders, 512-frame "
                    "slerp crossfade mid-render between two seeds' segments, per arm "
                    "(incl. evr3x at strength 0.33); longform.py CrossfadeStitcher tech"),
        "gen": {"prompt": PROMPT, "frames": args.frames, "xfade_frames": args.xfade,
                "segment_frames": seg, "steps": args.steps, "cfg": args.cfg_scale,
                "seed_pairs": [[s1, s2], [s2, s1]]},
        "related": ["SAO/eval/longform_crossfade_eval.py",
                    "stable-audio-3/stable_audio_3/inference/longform.py"],
        "checkpoints": {},
    }

    for arm in args.arms.split(","):
        if arm in ARM_STRENGTH:
            ckpt, strength = DEFAULT_ARMS[ARM_STRENGTH[arm][0]], ARM_STRENGTH[arm][1]
        else:
            ckpt, strength = DEFAULT_ARMS[arm], 1.0
        meta["checkpoints"][arm] = ((ckpt or "medium-base (no adapter)") +
                                    (f" @strength {strength}" if strength != 1.0 else ""))
        print(f"[load] {arm} ...", flush=True)
        model = StableAudioModel.from_pretrained("medium-base", device="cuda")
        if ckpt:
            model.load_lora([str(ckpt)])
            if strength != 1.0:
                model.set_lora_strength(strength)
        sr = model.model.sample_rate
        for sa, sb in ((s1, s2), (s2, s1)):
            out = args.out_dir / f"{arm}__aggr_xfade_s{sa}to{sb}.wav"
            if out.exists():
                print(f"[skip] {out.name}", flush=True)
                continue
            t0 = time.time()
            zA = gen_latents(model, sa, seg, args.steps, args.cfg_scale)
            zB = gen_latents(model, sb, seg, args.steps, args.cfg_scale)
            mid = stitcher.transition_join(zA, zB[..., :args.xfade], args.xfade)
            z = torch.cat([zA[..., :keep], mid, zB[..., args.xfade:]], dim=-1)
            assert z.shape[-1] == args.frames, z.shape
            audio = decode(model, z)
            save_audio(out, audio, sr, normalize=True)
            print(f"[clip] {out.name}  {time.time()-t0:5.1f}s  "
                  f"({z.shape[-1]} frames)", flush=True)
        del model
        torch.cuda.empty_cache()

    (args.out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
