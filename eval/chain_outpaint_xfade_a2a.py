#!/usr/bin/env python
"""chain_outpaint_xfade_a2a.py — Kim 2026-09-15: addresses two complaints
about the inpaint-based transitions (RMS drop at the seam, abrupt-sounding
change) with a different construction:

  1. Outpaint A forward by 10s (its own model/prompt/seed) -- A grows an
     organic tail instead of ending on a hard cut.
  2. Outpaint B backward by 10s ("precede", its own model/prompt/seed) --
     B grows an organic lead-in.
  3. Place the two extended clips directly adjacent (no gap, no overlap).
  4. Latent-space slerp crossfade over the seam (the extended tail of A
     against the extended head of B) -- smooths the join in latent space
     rather than a hard edit.
  5. Audio-to-audio pass on top with the sine-bump strength envelope (peak
     0.7 at the seam centre) -- the same "abrupt changes" fix already
     proven in chain_crossfade_a2a.py.

Also layers TWO guidance channels: the proven chroma-ramp (A's chroma toward
B's across the seam), and a NEW rms_energy_air target holding HF energy at
the head's own calibration average (-32.96 dB) -- an attempt at the "equalise
searing highs toward the average" ask. This only affects the newly generated
seam material; it cannot retroactively fix harshness in the original,
unmodified clip audio on either side.
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
HF_HEAD = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_rms_energy_air_best.pt"
HF_TARGET_DB = -32.9611  # the head's own std_mean -- "the average"
HF_GAIN = 512.0  # moderate authority per the MASTER §5 sweep; avoid overdriving
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
    ap.add_argument("--ext-sec", type=float, default=10.0)
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
    W_samp = round(args.ext_sec * sr)
    W_lat = round(args.ext_sec * FPS)

    pairs = json.loads(args.pairs_json.read_text())
    for p in pairs:
        out_path = args.out_dir / f"{p['out_name']}.wav"
        if out_path.exists():
            print(f"[skip] {p['out_name']}", flush=True)
            continue

        A, sra = load(p["a_path"])
        B, srb = load(p["b_path"])
        assert sra == sr and srb == sr
        A_dur = A.shape[1] / sr
        B_dur = B.shape[1] / sr

        # ---- step 1: outpaint A forward ----
        A_pad = np.concatenate([A, np.zeros((A.shape[0], W_samp), dtype=A.dtype)], axis=1)
        print(f"[gen] {p['out_name']} outpaint A", flush=True)
        A_ext = model.generate(
            prompt=args.prompt, duration=A_dur + args.ext_sec, steps=args.steps, cfg_scale=args.cfg_scale,
            seed=1234, batch_size=1, sample_size=int((A_dur + args.ext_sec + 8) * sr),
            inpaint_audio=(sr, torch.tensor(A_pad)),
            inpaint_mask_start_seconds=A_dur, inpaint_mask_end_seconds=A_dur + args.ext_sec,
        )[0].float().cpu().numpy()

        # ---- step 2: outpaint B backward (precede) ----
        B_pad = np.concatenate([np.zeros((B.shape[0], W_samp), dtype=B.dtype), B], axis=1)
        print(f"[gen] {p['out_name']} outpaint B (precede)", flush=True)
        B_ext = model.generate(
            prompt=args.prompt, duration=args.ext_sec + B_dur, steps=args.steps, cfg_scale=args.cfg_scale,
            seed=1234, batch_size=1, sample_size=int((args.ext_sec + B_dur + 8) * sr),
            inpaint_audio=(sr, torch.tensor(B_pad)),
            inpaint_mask_start_seconds=0.0, inpaint_mask_end_seconds=args.ext_sec,
        )[0].float().cpu().numpy()

        # ---- step 3+4: place adjacent, latent slerp crossfade over the seam ----
        zA = encode(model, A_ext, sr)
        zB = encode(model, B_ext, sr)
        TA = zA.shape[-1]
        t = torch.linspace(0, 1, W_lat, device=zA.device, dtype=torch.float32).view(1, 1, -1)
        mid = slerp(zA[..., -W_lat:].float(), zB[..., :W_lat].float(), t).to(zA.dtype)
        z = torch.cat([zA[..., :-W_lat], mid, zB[..., W_lat:]], dim=-1)
        Tz = z.shape[-1]

        cA = compute_same_chroma(A_ext.T, sr).reshape(384, -1)
        cB = compute_same_chroma(B_ext.T, sr).reshape(384, -1)
        ramp = np.linspace(0, 1, W_lat, dtype=np.float32)[None, :]
        cA_r = cA[:, :TA] if cA.shape[1] >= TA else np.pad(cA, ((0, 0), (0, TA - cA.shape[1])), mode="edge")
        cB_r = cB[:, :zB.shape[-1]] if cB.shape[1] >= zB.shape[-1] else np.pad(cB, ((0, 0), (0, zB.shape[-1] - cB.shape[1])), mode="edge")
        morph = cA_r[:, -W_lat:] * (1 - ramp) + cB_r[:, :W_lat] * ramp
        chroma_target = np.concatenate([cA_r[:, :-W_lat], morph, cB_r[:, W_lat:]], axis=1)[:, :Tz]
        hf_target = np.full((1, Tz), HF_TARGET_DB, dtype=np.float32)

        dur = Tz / FPS
        pre = model.model.pretransform
        with torch.inference_mode():
            audio_ref = pre.decode(z.to(next(pre.parameters()).dtype))[0]

        # ---- step 5: sine-bump a2a on top ----
        depth_shape = torch.zeros(Tz)
        depth_shape[TA - W_lat:TA] = torch.sin(torch.linspace(0, torch.pi, W_lat))
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

        print(f"[gen] {p['out_name']} xfade+a2a dur={dur:.1f}s peak_nl={args.peak_nl}", flush=True)
        out = model.generate(
            prompt=args.prompt, duration=dur, steps=args.steps, cfg_scale=args.cfg_scale,
            seed=1234, batch_size=1, sample_size=int((dur + 8) * sr),
            init_audio=(sr, audio_ref.float()), init_noise_level=args.peak_nl,
            callback=cb,
            # NOTE: rho/mu are GLOBAL sampler hparams shared by every head in
            # latch_configs (per-config "rho"/"mu" keys are silently ignored) --
            # per-head strength is set via "weight" instead, scaled relative to
            # the shared CHROMA_GAIN base (HF_GAIN/CHROMA_GAIN ratio).
            latch_configs=[
                {"model_path": CHROMA_HEAD, "target_raw": chroma_target, "weight": 1.0, "end_pct": 0.6},
                {"model_path": HF_HEAD, "target_raw": hf_target, "weight": HF_GAIN / CHROMA_GAIN, "end_pct": 0.6},
            ],
            latch_hparams={"rho": CHROMA_GAIN, "mu": CHROMA_GAIN},
        )
        save_audio(str(out_path), out[0].float().cpu(), sr)
        print(f"[done] {p['out_name']}", flush=True)


if __name__ == "__main__":
    main()
