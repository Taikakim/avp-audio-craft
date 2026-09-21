#!/usr/bin/env python
"""chain_gapfill_sinesweep.py — Kim 2026-09-15: a parallel hybrid version,
does NOT replace the existing three. Two stages per pair:

  1. Gap-fill (like chain_gapfill_full.py, but 20s instead of 10s): both
     clips fully intact, a genuine 20s empty gap between them, masked and
     generated with chroma-ramp guidance -- produces one complete, gapless
     composite.
  2. Sine-sweep a2a smoothing pass ON TOP of that result: a second
     generative pass over the same 20s region (the sinesweep hold/release
     mechanism from chain_crossfade_a2a.py, peak strength 0.7 at the
     region's centre), using stage 1's own output as the seed/reference —
     smooths the boundary between the freshly generated gap and the real
     audio on either side.
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


def build_chroma_target(A, B, sr, W_lat, TA, Tz):
    cA = compute_same_chroma(A.T, sr).reshape(384, -1)
    cB = compute_same_chroma(B.T, sr).reshape(384, -1)
    cA_r = cA[:, :TA] if cA.shape[1] >= TA else np.pad(cA, ((0, 0), (0, TA - cA.shape[1])), mode="edge")
    TB = Tz - TA - W_lat
    cB_r = cB[:, :TB] if cB.shape[1] >= TB else np.pad(cB, ((0, 0), (0, TB - cB.shape[1])), mode="edge")
    ramp = np.linspace(0, 1, W_lat, dtype=np.float32)[None, :]
    morph = cA_r[:, -1:] * (1 - ramp) + cB_r[:, :1] * ramp
    return np.concatenate([cA_r, morph, cB_r], axis=1)[:, :Tz]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs-json", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--gap-sec", type=float, default=20.0)
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
    W_samp = round(args.gap_sec * sr)
    W_lat = round(args.gap_sec * FPS)

    pairs = json.loads(args.pairs_json.read_text())
    for p in pairs:
        out_path = args.out_dir / f"{p['out_name']}.wav"
        if out_path.exists():
            print(f"[skip] {p['out_name']}", flush=True)
            continue

        A, sra = load(p["a_path"])
        B, srb = load(p["b_path"])
        assert sra == sr and srb == sr

        # ---- stage 1: gap-fill ----
        audio_ref = np.concatenate([A, np.zeros((A.shape[0], W_samp), dtype=A.dtype), B], axis=1)
        dur = audio_ref.shape[1] / sr
        w_lo = A.shape[1] / sr
        w_hi = w_lo + args.gap_sec
        TA = round(A.shape[1] / sr * FPS)
        Tz = round(dur * FPS)
        target1 = build_chroma_target(A, B, sr, W_lat, TA, Tz)

        print(f"[gen1] {p['out_name']} gapfill dur={dur:.1f}s gap=[{w_lo:.1f},{w_hi:.1f}]s", flush=True)
        stage1 = model.generate(
            prompt=args.prompt, duration=dur, steps=args.steps, cfg_scale=args.cfg_scale,
            seed=1234, batch_size=1, sample_size=int((dur + 8) * sr),
            inpaint_audio=(sr, torch.tensor(audio_ref)),
            inpaint_mask_start_seconds=w_lo, inpaint_mask_end_seconds=w_hi,
            latch_configs=[{"model_path": CHROMA_HEAD, "target_raw": target1,
                             "weight": 1.0, "end_pct": 0.6}],
            latch_hparams={"rho": CHROMA_GAIN, "mu": CHROMA_GAIN},
        )[0].float().cpu()

        # ---- stage 2: sine-sweep a2a smoothing over the same region ----
        z = encode(model, stage1.numpy(), sr)
        Tz2 = z.shape[-1]
        depth_shape = torch.zeros(Tz2)
        Wlo_f, Whi_f = TA, TA + W_lat
        depth_shape[Wlo_f:Whi_f] = torch.sin(torch.linspace(0, torch.pi, W_lat))
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

        target2 = build_chroma_target(A, B, sr, W_lat, TA, Tz2)
        print(f"[gen2] {p['out_name']} sinesweep peak_nl={args.peak_nl}", flush=True)
        pre = model.model.pretransform
        with torch.inference_mode():
            stage1_audio_ref = pre.decode(z.to(next(pre.parameters()).dtype))[0]
        stage2 = model.generate(
            prompt=args.prompt, duration=Tz2 / FPS, steps=args.steps, cfg_scale=args.cfg_scale,
            seed=1234, batch_size=1, sample_size=int((Tz2 / FPS + 8) * sr),
            init_audio=(sr, stage1_audio_ref.float()), init_noise_level=args.peak_nl,
            callback=cb,
            latch_configs=[{"model_path": CHROMA_HEAD, "target_raw": target2,
                             "weight": 1.0, "end_pct": 0.6}],
            latch_hparams={"rho": CHROMA_GAIN, "mu": CHROMA_GAIN},
        )
        save_audio(str(out_path), stage2[0].float().cpu(), sr)
        print(f"[done] {p['out_name']}", flush=True)


if __name__ == "__main__":
    main()
