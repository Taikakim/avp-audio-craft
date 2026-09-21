#!/usr/bin/env python
"""mixtape_lengthen_and_prep.py — Kim 2026-09-16 (overnight batch): extends every
mixtape clip to 3x its own length (outpaint_lengthen.py's validated mechanism —
Kim's own listening report on 2x/3x/4x/6x was strongly positive), then treats the
LAST THIRD of the resulting clip as an "outgoing" DJ segment: a volume fade-down plus
an ASCENDING-noise-level a2a pass (0 at the start of the last third, peak nl at the
very end -- NOT the symmetric sine-bump used elsewhere in this codebase, since this
segment doesn't return to stability at the far edge, it's meant to dissolve into
whatever comes next). This 1/3 is intended to become the "outgoing" (A) side of the
DJ-overlay mixing built earlier tonight (chain_dj_overlay.py).

Two independent transformations on the last-third audio, applied in this order:
  1. Fade: linear gain ramp 1.0 -> FADE_FLOOR across the region (on the waveform,
     before re-generation, so the model's own regeneration is conditioned on
     genuinely decaying energy, not just re-enveloped after the fact).
  2. Ascending a2a: ordinary audio-to-audio regeneration whose EFFECTIVE noise level
     rises monotonically from 0 (start of region, audio untouched) to --peak-nl
     (default 0.8, matching tonight's validated seam setting) at the region's end,
     via the same per-frame "hold at a reference trajectory until global t drops
     below this frame's own depth" callback used throughout this codebase's
     sine-bump a2a -- just with a ramp depth_shape instead of a sine bump.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
from chain_dj_overlay import outpaint_forward, BRIDGE_CKPT  # noqa: E402
from chroma_morph_transitions import load  # noqa: E402
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402

FADE_FLOOR = 0.05


def fade_tail(audio, region_start_samp):
    """Linear gain ramp 1.0 -> FADE_FLOOR from region_start_samp to the clip end."""
    out = audio.copy()
    n = out.shape[1] - region_start_samp
    if n <= 0:
        return out
    ramp = np.linspace(1.0, FADE_FLOOR, n, dtype=out.dtype)
    out[:, region_start_samp:] *= ramp[None, :]
    return out


def ascending_a2a(model, audio, sr, region_start_sec, peak_nl, prompt, steps, cfg_scale, seed):
    """Audio-to-audio over the WHOLE clip, but only the last-third region is ever
    allowed to depart from the reference, and only progressively -- depth_shape is 0
    before region_start_sec and ramps 0->peak_nl linearly to the clip's end."""
    dur = audio.shape[1] / sr
    ds = model.model.pretransform.downsampling_ratio
    fps = sr / ds

    pre = model.model.pretransform
    p = next(pre.parameters())
    a = torch.tensor(audio, device=p.device, dtype=p.dtype).unsqueeze(0)
    with torch.inference_mode():
        z_ref = pre.encode(a).clone().float().cpu()
    Tz = z_ref.shape[-1]
    region_start_f = round(region_start_sec * fps)

    depth_shape = torch.zeros(Tz)
    if region_start_f < Tz:
        depth_shape[region_start_f:] = torch.linspace(0.0, 1.0, Tz - region_start_f)
    depth = (depth_shape * peak_nl).view(1, 1, -1)

    torch.manual_seed(4242)
    eps_ref = torch.randn_like(z_ref)

    def cb(d, _z=z_ref, _e=eps_ref, _d=depth):
        x, tt = d["x"], float(d["t"][0])
        n = min(x.shape[-1], _z.shape[-1])
        hold = (_d[..., :n] < tt)
        ref_t = ((1 - tt) * _z[..., :n] + tt * _e[..., :n]).to(x.device, x.dtype)
        xs = x[..., :n]
        x[..., :n].copy_(torch.where(hold.to(x.device), ref_t, xs))

    out = model.generate(
        prompt=prompt, duration=dur, steps=steps, cfg_scale=cfg_scale, seed=seed,
        batch_size=1, sample_size=int((dur + 8) * sr),
        init_audio=(sr, torch.tensor(audio)), init_noise_level=peak_nl, callback=cb,
    )[0].float().cpu().numpy()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips-json", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--ckpt", default=BRIDGE_CKPT)
    ap.add_argument("--length-mult", type=float, default=3.0,
                     help="total final length as a multiple of the clip's own length "
                          "(3.0 = extend by 2x own length, outpaint_lengthen.py convention)")
    ap.add_argument("--peak-nl", type=float, default=0.8)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    clips = json.loads(args.clips_json.read_text())
    print(f"[load] model, {len(clips)} clips", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([args.ckpt])
    sr = model.model.sample_rate

    manifest = []
    for i, c in enumerate(clips):
        out_path = args.out_dir / f"{c['id']}_len{args.length_mult:g}x.wav"
        if out_path.exists():
            print(f"[skip] {out_path.name}", flush=True)
            continue
        audio, sra = load(c["path"])
        assert sra == sr
        orig_dur = audio.shape[1] / sr
        ext_sec = (args.length_mult - 1.0) * orig_dur
        print(f"[{i:02d}/{len(clips)}] {c['file'][:55]:55s} orig={orig_dur:.1f}s "
              f"-> +{ext_sec:.1f}s", flush=True)

        extended = outpaint_forward(model, audio, sr, ext_sec, args.prompt,
                                     args.steps, args.cfg_scale, args.seed)
        total_dur = extended.shape[1] / sr
        last_third_start_sec = total_dur * 2.0 / 3.0
        last_third_start_samp = round(last_third_start_sec * sr)

        faded = fade_tail(extended, last_third_start_samp)
        treated = ascending_a2a(model, faded, sr, last_third_start_sec, args.peak_nl,
                                 args.prompt, args.steps, args.cfg_scale, args.seed)

        save_audio(str(out_path), torch.tensor(treated), sr)
        manifest.append({
            "id": c["id"], "file": c["file"], "orig_dur": orig_dur,
            "total_dur": total_dur, "last_third_start_sec": last_third_start_sec,
            "peak_nl": args.peak_nl, "out": out_path.name,
        })
        (args.out_dir / "run_meta.json").write_text(json.dumps({
            "purpose": "overnight batch: 3x-lengthen every mixtape clip (outpaint_lengthen.py "
                       "mechanism) then fade + ascending-nl a2a (peak 0.8) the last third, "
                       "prepping it as the 'outgoing' segment for the DJ-overlay mixing built "
                       "earlier tonight (chain_dj_overlay.py).",
            "length_mult": args.length_mult, "peak_nl": args.peak_nl, "ckpt": args.ckpt,
            "steps": args.steps, "cfg_scale": args.cfg_scale, "prompt": args.prompt,
            "seed": args.seed, "kim_feedback": None, "clips": manifest,
        }, indent=2))
        print(f"  [done] {out_path.name}  total={total_dur:.1f}s  "
              f"last_third_from={last_third_start_sec:.1f}s", flush=True)

    print("[all done]", flush=True)


if __name__ == "__main__":
    main()
