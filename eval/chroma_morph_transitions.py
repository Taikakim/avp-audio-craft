#!/usr/bin/env python
"""chroma_morph_transitions.py — real-track transitions with chroma-morph steering
(Kim 2026-07-07).

Pipeline per A->B pair:
  1. tempo-estimate both (librosa, octave-folded); BUNGEE-stretch B to A's BPM
     (mir/.venv subprocess — B always follows A)
  2. cut segments: A's tail region ending on a beat, B (stretched) from a
     beat-rich point, starting on a beat
  3. SAME-encode both; latent slerp crossfade of W frames at the junction
  4. graded a2a refine of the composite at the requested noise level, WITH the
     PROVEN stem-chroma LatCH head (latch_sa3_chroma_other_best, cosine, gain
     ~2048 — the WORKLOG 2026-06-25 pitch-steering band) guided by a MORPH
     target: A's measured same_chroma -> blend across the window -> B's.
     Guidance stops at 60% of steps (content locks mid-trajectory).

Uses the new model.py support: latch_configs target_raw + guided-path init_latents.
Chroma targets via mir-same-chroma's compute_same_chroma (numpy/scipy, imported).
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
import time
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
CHROMA_HEAD = ("/run/media/kim/Mantu1/sa3_lora_runs/cu_reward_renders/analysis/"
               "chroma_heads/latch_sa3_chroma_other_best.pt")
CHROMA_GAIN = 2048.0
MIR_VENV_PY = "/home/kim/Projects/mir/.venv/bin/python"

TRACKS = {
    "kaikki":  "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-flac/009 goddess guerrilla (2006)/Aavepyora - Goddess Guerilla - Kaikki-Alla.flac",
    "angelic": "/run/media/kim/Mantu1/ai-music/Goa Dataset/0934. Hallucinogen - Angelic Particles (Remastered 2024).flac",
    "vapaus":  "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-flac/009 goddess guerrilla (2006)/Aavepyora - Goddess Guerilla - Vapausvoima.flac",
}
PAIRS = [("kaikki", "angelic"), ("angelic", "vapaus"), ("vapaus", "kaikki")]


def load(track):
    a, sr = sf.read(track, dtype="float32", always_2d=True)
    return a.T, sr  # (C, N)


def tempo_of(a, sr):
    import librosa
    mid = a.shape[1] // 2
    ex = a[:, max(0, mid - 30 * sr):mid + 30 * sr].mean(0)
    t, _ = librosa.beat.beat_track(y=ex, sr=sr, units="time")
    return float(np.atleast_1d(t)[0])


def bungee_stretch(audio, sr, speed):
    """Stretch via bungee in the mir venv (B follows A: speed = tempoA/tempoB inverse)."""
    with tempfile.TemporaryDirectory() as td:
        src, dst = f"{td}/in.npy", f"{td}/out.npy"
        np.save(src, audio.T)  # (N, C) for bungee
        code = f"""
import numpy as np
from bungee_python import bungee as B
d = np.load({src!r})
st = B.Bungee(sample_rate={sr}, channels=d.shape[1])
st.set_speed({speed})
out = np.asarray(st.process(d.astype(np.float32)), dtype=np.float32)
np.save({dst!r}, out)
"""
        subprocess.run([MIR_VENV_PY, "-c", code], check=True, capture_output=True)
        return np.load(dst).T  # back to (C, N)


def beat_near(a, sr, target_sec):
    import librosa
    lo = max(0, int((target_sec - 20) * sr))
    ex = a[:, lo:lo + int(40 * sr)].mean(0)
    _, beats = librosa.beat.beat_track(y=ex, sr=sr, units="time")
    if len(beats) == 0:
        return target_sec
    beats = beats + lo / sr
    return float(beats[np.argmin(np.abs(beats - target_sec))])


def encode(model, audio, sr):
    pre = model.model.pretransform
    p = next(pre.parameters())
    a = torch.tensor(audio, device=p.device, dtype=p.dtype).unsqueeze(0)
    with torch.inference_mode():
        return pre.encode(a).clone()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--ckpt", default="/run/media/kim/Mantu1/sa3_lora_runs/dora128_everything_8ep_lr1x/epoch=7-step=12216.ckpt")
    ap.add_argument("--windows", default="512,1024", help="crossfade lengths (latent frames)")
    ap.add_argument("--noise-levels", default="0.35,0.42,0.5,0.55")
    ap.add_argument("--seg-sec", type=float, default=75.0, help="audio per side of the junction")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--no-chroma-ref", action="store_true",
                    help="ALSO render a chroma-guidance-OFF reference per config")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    wins = [int(x) for x in args.windows.split(",")]
    nls = [float(x) for x in args.noise_levels.split(",")]

    meta = {"purpose": ("real-track transitions with CHROMA-MORPH steering: bungee "
                        "beatmatch (B follows A), latent slerp crossfade, graded a2a "
                        "refine at the listed noise levels with the proven stem-chroma "
                        "LatCH head morphing A-chroma->B-chroma across the window"),
            "pairs": PAIRS, "tracks": TRACKS,
            "gen": {"windows": wins, "noise_levels": nls, "seg_sec": args.seg_sec,
                    "steps": args.steps, "cfg": args.cfg_scale,
                    "chroma_head": CHROMA_HEAD, "chroma_gain": CHROMA_GAIN,
                    "guidance_end_pct": 0.6, "prompt": args.prompt},
            "checkpoints": {"adapter": args.ckpt}}
    (args.out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))

    print("[load] model", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([args.ckpt])
    sr = model.model.sample_rate

    audio_cache = {k: load(p) for k, p in TRACKS.items()}

    for a_key, b_key in PAIRS:
        A, sra = audio_cache[a_key]
        B, srb = audio_cache[b_key]
        assert sra == sr and srb == sr
        ta, tb = tempo_of(A, sr), tempo_of(B, sr)
        speed = ta / tb            # playback speed multiplies tempo: tb*speed = ta
        while speed > 1.35: speed /= 2
        while speed < 0.74: speed *= 2
        print(f"[{a_key}->{b_key}] tempo A={ta:.1f} B={tb:.1f} bungee speed={speed:.4f}", flush=True)
        Bs = bungee_stretch(B, sr, speed) if abs(speed - 1.0) > 0.005 else B

        # segments: A tail ending on beat at ~62% of A; B from beat at ~40%
        a_end = beat_near(A, sr, 0.62 * A.shape[1] / sr)
        b_start = beat_near(Bs, sr, 0.40 * Bs.shape[1] / sr)
        A_seg = A[:, int((a_end - args.seg_sec) * sr):int(a_end * sr)]
        B_seg = Bs[:, int(b_start * sr):int((b_start + args.seg_sec) * sr)]

        zA = encode(model, A_seg, sr)
        zB = encode(model, B_seg, sr)
        # chroma of each segment (384, T_latent-aligned)
        cA = compute_same_chroma(A_seg.T, sr).reshape(384, -1)   # (3,128,T) -> (384,T)
        cB = compute_same_chroma(B_seg.T, sr).reshape(384, -1)

        for W in wins:
            # composite: zA + slerp window + zB
            t = torch.linspace(0, 1, W, device=zA.device, dtype=torch.float32).view(1, 1, -1)
            mid = slerp(zA[..., -W:].float(), zB[..., :W].float(), t).to(zA.dtype)
            z = torch.cat([zA[..., :-W], mid, zB[..., W:]], dim=-1)
            Tz = z.shape[-1]
            # chroma morph target on the same grid
            TA = zA.shape[-1]
            ramp = np.linspace(0, 1, W, dtype=np.float32)[None, :]
            cA_r = cA[:, :TA] if cA.shape[1] >= TA else np.pad(cA, ((0, 0), (0, TA - cA.shape[1])), mode="edge")
            cB_r = cB[:, :zB.shape[-1]] if cB.shape[1] >= zB.shape[-1] else np.pad(cB, ((0, 0), (0, zB.shape[-1] - cB.shape[1])), mode="edge")
            morph = cA_r[:, -W:] * (1 - ramp) + cB_r[:, :W] * ramp
            target = np.concatenate([cA_r[:, :-W], morph, cB_r[:, W:]], axis=1)[:, :Tz]

            dur = Tz / FPS
            audio_ref = None  # decode lazily only if needed
            for nl in nls:
                for chroma_on in ([True, False] if args.no_chroma_ref else [True]):
                    tag = "chroma" if chroma_on else "plain"
                    out = args.out_dir / f"{a_key}2{b_key}__w{W}_nl{int(nl*100):02d}_{tag}.wav"
                    if out.exists():
                        print(f"[skip] {out.name}", flush=True)
                        continue
                    t0 = time.time()
                    if audio_ref is None:  # decode composite once per window
                        pre = model.model.pretransform
                        with torch.inference_mode():
                            audio_ref = pre.decode(z.to(next(pre.parameters()).dtype))[0]
                    kw = dict(prompt=args.prompt, duration=dur, steps=args.steps,
                              cfg_scale=args.cfg_scale, seed=1234, batch_size=1,
                              sample_size=int((dur + 8) * sr),
                              init_audio=(sr, audio_ref.float()), init_noise_level=nl)
                    if chroma_on:
                        kw["latch_configs"] = [{"model_path": CHROMA_HEAD,
                                                "target_raw": target,
                                                "weight": 1.0, "end_pct": 0.6}]
                        kw["latch_hparams"] = {"rho": CHROMA_GAIN, "mu": CHROMA_GAIN}
                    outa = model.generate(**kw)
                    save_audio(out, outa[0], sr, normalize=True)
                    print(f"[clip] {out.name}  {time.time()-t0:5.1f}s", flush=True)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
