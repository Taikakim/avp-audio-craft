#!/usr/bin/env python
"""chain_inpaint_prototype.py — prototype for the Kone-portfolio mixtape chain
transitions (Kim 2026-09-15): fixed 10s bidirectional INPAINT seam between two
already-generated clips, with the proven stem-chroma LatCH head ramping the
guidance target from A's measured chroma to B's across the seam.

Reuses the exact mechanism from chroma_morph_transitions.py --mode inpaint
(decode a slerp-seeded composite for inpaint context, mask only the seam,
let the model regenerate it with both real sides as context) but generalized
to short (~47.5s) generated clips instead of full tracks, with a small fixed
window instead of the downbeat-searched one, and no bungee tempo-stretch yet
(prototype scope: validate the chroma-ramp/inpaint smoothness in isolation).
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
            raise ValueError(f"native sr {sr} != 44100, resample via ffmpeg")
    except Exception:
        with tempfile.TemporaryDirectory() as td:
            wav = f"{td}/dec.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-i", track, "-ar", "44100",
                            "-ac", "2", wav], check=True)
            a, sr = sf.read(wav, dtype="float32", always_2d=True)
    return a.T, sr  # (C, N)


def encode(model, audio, sr):
    pre = model.model.pretransform
    p = next(pre.parameters())
    a = torch.tensor(audio, device=p.device, dtype=p.dtype).unsqueeze(0)
    with torch.inference_mode():
        return pre.encode(a).clone()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs-json", type=Path, required=True,
                     help="JSON list of {a_path, b_path, out_name} objects")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--overlap-sec", type=float, default=10.0)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("[load] model", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([BRIDGE_CKPT])
    sr = model.model.sample_rate

    pairs = json.loads(args.pairs_json.read_text())
    W = round(args.overlap_sec * FPS)

    for p in pairs:
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
        w_lo = (TA - W) / FPS
        w_hi = TA / FPS

        pre = model.model.pretransform
        with torch.inference_mode():
            audio_ref = pre.decode(z.to(next(pre.parameters()).dtype))[0]

        print(f"[gen] {p['out_name']} dur={dur:.1f}s seam=[{w_lo:.1f},{w_hi:.1f}]s", flush=True)
        out = model.generate(
            prompt=args.prompt, duration=dur, steps=args.steps, cfg_scale=args.cfg_scale,
            seed=1234, batch_size=1, sample_size=int((dur + 8) * sr),
            inpaint_audio=(sr, audio_ref.float()),
            inpaint_mask_start_seconds=w_lo, inpaint_mask_end_seconds=w_hi,
            latch_configs=[{"model_path": CHROMA_HEAD, "target_raw": target,
                             "weight": 1.0, "end_pct": 0.6}],
            latch_hparams={"rho": CHROMA_GAIN, "mu": CHROMA_GAIN},
        )
        save_audio(str(args.out_dir / f"{p['out_name']}.wav"), out[0].float().cpu(), sr)
        print(f"[done] {p['out_name']}", flush=True)


if __name__ == "__main__":
    main()
