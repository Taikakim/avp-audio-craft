#!/usr/bin/env python
"""chain_gapfill_full.py — Kim 2026-09-15 (v2 of the concept): both clips stay
FULLY INTACT, placed end-to-end with a genuine 10s empty gap inserted between
them (not carved out of either clip); the gap is masked and generated, with
the chroma head ramping the guidance target from A's tail chroma to B's head
chroma across the gap. Distinct from chain_inpaint_blank.py, which wrongly
trimmed 10s off each clip instead of leaving them whole.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs-json", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--gap-sec", type=float, default=10.0)
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
    G_sec = args.gap_sec

    pairs = json.loads(args.pairs_json.read_text())
    for p in pairs:
        out_path = args.out_dir / f"{p['out_name']}.wav"
        if out_path.exists():
            print(f"[skip] {p['out_name']}", flush=True)
            continue

        A, sra = load(p["a_path"])
        B, srb = load(p["b_path"])
        assert sra == sr and srb == sr

        audio_ref = np.concatenate([
            A,
            np.zeros((A.shape[0], W_samp), dtype=A.dtype),
            B,
        ], axis=1)
        dur = audio_ref.shape[1] / sr
        w_lo = A.shape[1] / sr
        w_hi = w_lo + G_sec

        # chroma from A's own tail and B's own head (the material now
        # bordering the gap on each side)
        tailA = A[:, -W_samp:] if A.shape[1] >= W_samp else A
        headB = B[:, :W_samp] if B.shape[1] >= W_samp else B
        cA_tail = compute_same_chroma(tailA.T, sr).reshape(384, -1)
        cB_head = compute_same_chroma(headB.T, sr).reshape(384, -1)
        TA = round(A.shape[1] / sr * FPS)
        Tz = round(dur * FPS)
        W_lat = round(G_sec * FPS)
        cA_const = cA_tail[:, -1:].repeat(TA, axis=1) if cA_tail.shape[1] else np.zeros((384, TA), np.float32)
        # simpler + robust: hold A's OWN measured chroma constant over its own span,
        # B's over its own span, ramp only across the gap
        cA_full = compute_same_chroma(A.T, sr).reshape(384, -1)
        cB_full = compute_same_chroma(B.T, sr).reshape(384, -1)
        cA_full = cA_full[:, :TA] if cA_full.shape[1] >= TA else np.pad(cA_full, ((0, 0), (0, TA - cA_full.shape[1])), mode="edge")
        TB = Tz - TA - W_lat
        cB_full = cB_full[:, :TB] if cB_full.shape[1] >= TB else np.pad(cB_full, ((0, 0), (0, TB - cB_full.shape[1])), mode="edge")
        ramp = np.linspace(0, 1, W_lat, dtype=np.float32)[None, :]
        morph = cA_full[:, -1:] * (1 - ramp) + cB_full[:, :1] * ramp
        target = np.concatenate([cA_full, morph, cB_full], axis=1)[:, :Tz]

        print(f"[gen] {p['out_name']} dur={dur:.1f}s gap=[{w_lo:.1f},{w_hi:.1f}]s (full clips + true gap)", flush=True)
        out = model.generate(
            prompt=args.prompt, duration=dur, steps=args.steps, cfg_scale=args.cfg_scale,
            seed=1234, batch_size=1, sample_size=int((dur + 8) * sr),
            inpaint_audio=(sr, torch.tensor(audio_ref)),
            inpaint_mask_start_seconds=w_lo, inpaint_mask_end_seconds=w_hi,
            latch_configs=[{"model_path": CHROMA_HEAD, "target_raw": target,
                             "weight": 1.0, "end_pct": 0.6}],
            latch_hparams={"rho": CHROMA_GAIN, "mu": CHROMA_GAIN},
        )
        save_audio(str(out_path), out[0].float().cpu(), sr)
        print(f"[done] {p['out_name']}", flush=True)


if __name__ == "__main__":
    main()
