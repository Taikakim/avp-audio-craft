#!/usr/bin/env python
"""chain_crossfade_a2a.py — Kim 2026-09-15: crossfade + audio-to-audio hybrid.
Two full clips overlap by a fixed window; a latent-space slerp crossfade forms
the base, and an a2a regeneration is layered on top whose per-frame noise
strength follows a sine bump across the window -- 0 at the edges, peaking at
`--peak-nl` (default 0.7) at the window centre, back to 0 -- via the
sinesweep hold/release callback mechanism from chroma_morph_transitions.py
(same math, ported to the short-generated-clip chain instead of full tracks).
Chroma-ramp guidance rides on top, same as the other chain scripts.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/control")
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from sa3_control.audio_io import save_audio  # noqa: E402
from harmonic.same_chroma import compute_same_chroma  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.inference.longform import slerp  # noqa: E402

FPS = 44100 / 4096
CHROMA_HEAD = ("/run/media/kim/Mantu/sa3_lora_runs/cu_reward_renders/analysis/"
               "chroma_heads/latch_sa3_chroma_other_best.pt")
CHROMA_GAIN = 2048.0
BRIDGE_CKPT = "/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt"


def load(track):
    try:
        a, sr = sf.read(track, dtype="float32", always_2d=True)
        if sr != 44100:
            raise ValueError("resample")
    except Exception:
        with tempfile.TemporaryDirectory() as td:
            wav = f"{td}/dec.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-i", track, "-ar", "44100",
                            "-ac", "2", wav], check=True)
            a, sr = sf.read(wav, dtype="float32", always_2d=True)
    return a.T, sr


def encode(model, audio, sr):
    pre = model.model.pretransform
    p = next(pre.parameters())
    a = torch.tensor(audio, device=p.device, dtype=p.dtype).unsqueeze(0)
    with torch.inference_mode():
        return pre.encode(a).clone()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs-json", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--overlap-sec", type=float, default=10.0)
    ap.add_argument("--peak-nl", type=float, default=0.7)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("[load] model", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([BRIDGE_CKPT])
    sr = model.model.sample_rate
    W = round(args.overlap_sec * FPS)

    pairs = json.loads(args.pairs_json.read_text())
    for p in pairs:
        out_path = args.out_dir / f"{p['out_name']}.wav"
        if out_path.exists():
            print(f"[skip] {p['out_name']}", flush=True)
            continue

        A, sra = load(p["a_path"])
        B, srb = load(p["b_path"])
        assert sra == sr and srb == sr

        zA = encode(model, A, sr)
        zB = encode(model, B, sr)
        cA = compute_same_chroma(A.T, sr).reshape(384, -1)
        cB = compute_same_chroma(B.T, sr).reshape(384, -1)

        t = torch.linspace(0, 1, W, device=zA.device, dtype=torch.float32).view(1, 1, -1)
        mid = slerp(zA[..., -W:].float(), zB[..., :W].float(), t).to(zA.dtype)
        z = torch.cat([zA[..., :-W], mid, zB[..., W:]], dim=-1)
        Tz = z.shape[-1]
        TA = zA.shape[-1]

        ramp = np.linspace(0, 1, W, dtype=np.float32)[None, :]
        cA_r = cA[:, :TA] if cA.shape[1] >= TA else np.pad(cA, ((0, 0), (0, TA - cA.shape[1])), mode="edge")
        cB_r = cB[:, :zB.shape[-1]] if cB.shape[1] >= zB.shape[-1] else np.pad(cB, ((0, 0), (0, zB.shape[-1] - cB.shape[1])), mode="edge")
        morph = cA_r[:, -W:] * (1 - ramp) + cB_r[:, :W] * ramp
        target = np.concatenate([cA_r[:, :-W], morph, cB_r[:, W:]], axis=1)[:, :Tz]

        dur = Tz / FPS
        pre = model.model.pretransform
        with torch.inference_mode():
            audio_ref = pre.decode(z.to(next(pre.parameters()).dtype))[0]

        # sine-bump depth: 0 outside the window, peak-nl at the window centre
        Wlo, Whi = TA - W, TA
        depth_shape = torch.zeros(Tz)
        depth_shape[Wlo:Whi] = torch.sin(torch.linspace(0, torch.pi, W))
        z_ref = z.float().cpu()
        torch.manual_seed(4242)
        eps_ref = torch.randn_like(z_ref)
        depth = (depth_shape * args.peak_nl).view(1, 1, -1)

        def cb(d, _z=z_ref, _e=eps_ref, _d=depth):
            x, tt = d["x"], float(d["t"][0])
            n = min(x.shape[-1], _z.shape[-1])
            hold = (_d[..., :n] < tt)
            ref_t = ((1 - tt) * _z[..., :n] + tt * _e[..., :n]).to(x.device, x.dtype)
            xs = x[..., :n]
            x[..., :n].copy_(torch.where(hold.to(x.device), ref_t, xs))

        print(f"[gen] {p['out_name']} dur={dur:.1f}s seam=[{Wlo/FPS:.1f},{Whi/FPS:.1f}]s peak_nl={args.peak_nl}", flush=True)
        out = model.generate(
            prompt=args.prompt, duration=dur, steps=args.steps, cfg_scale=args.cfg_scale,
            seed=1234, batch_size=1, sample_size=int((dur + 8) * sr),
            init_audio=(sr, audio_ref.float()), init_noise_level=args.peak_nl,
            callback=cb,
            latch_configs=[{"model_path": CHROMA_HEAD, "target_raw": target,
                             "weight": 1.0, "end_pct": 0.6}],
            latch_hparams={"rho": CHROMA_GAIN, "mu": CHROMA_GAIN},
        )
        save_audio(str(out_path), out[0].float().cpu(), sr)
        print(f"[done] {p['out_name']}", flush=True)


if __name__ == "__main__":
    main()
