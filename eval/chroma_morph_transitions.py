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


def bungee_stretch(audio, sr, speed, ramp_to=None, ramp_out_sec=0.0):
    """Time-stretch via bungee (streaming, mir venv). speed applies from the start;
    if ramp_to is given, speed ramps linearly (in tempo domain) from `speed` to
    `ramp_to` over the first `ramp_out_sec` seconds of OUTPUT — the DJ pitch-bend:
    matched at the transition, native afterwards."""
    with tempfile.TemporaryDirectory() as td:
        src, dst = f"{td}/in.npy", f"{td}/out.npy"
        np.save(src, audio.T)  # (N, C) for bungee
        code = f"""
import numpy as np
from bungee_python import bungee as B
d = np.load({src!r}).astype(np.float32)
sr = {sr}
st = B.Bungee(sample_rate=sr, channels=d.shape[1])
speed0, ramp_to, ramp_out = {speed}, {ramp_to if ramp_to is not None else 'None'}, {ramp_out_sec}
chunk = int(0.25 * sr)
outs, out_sec = [], 0.0
for lo in range(0, d.shape[0], chunk):
    if ramp_to is None or out_sec >= ramp_out:
        sp = speed0 if ramp_to is None else ramp_to
    else:
        f = out_sec / ramp_out
        sp = speed0 + f * (ramp_to - speed0)
    st.set_speed(float(sp))
    y = np.asarray(st.process(d[lo:lo + chunk]), dtype=np.float32)
    if y.ndim == 1:
        y = y.reshape(-1, d.shape[1])
    outs.append(y)
    out_sec += y.shape[0] / sr
np.save({dst!r}, np.concatenate(outs, axis=0))
"""
        subprocess.run([MIR_VENV_PY, "-c", code], check=True, capture_output=True)
        return np.load(dst).T  # back to (C, N)


def downbeat_near(a, sr, target_sec):
    """Nearest DOWNBEAT (bar start): librosa beats, phase = strongest mean onset
    energy among the 4 candidate phases (Kim: snap to positions divisible by 4)."""
    import librosa
    lo = max(0, int((target_sec - 30) * sr))
    ex = a[:, lo:lo + int(60 * sr)].mean(0)
    _, beats = librosa.beat.beat_track(y=ex, sr=sr, units="time")
    if len(beats) < 8:
        return target_sec
    env = librosa.onset.onset_strength(y=ex, sr=sr)
    et = librosa.times_like(env, sr=sr)
    strength = np.interp(beats, et, env)
    phase = int(np.argmax([strength[p::4].mean() for p in range(4)]))
    downs = beats[phase::4] + lo / sr
    return float(downs[np.argmin(np.abs(downs - target_sec))])


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
    ap.add_argument("--tempo-mode", choices=("ramp", "follow"), default="ramp",
                    help="ramp = B matched to A's tempo AT the transition, bending to its "
                         "NATIVE tempo by window end (DJ pitch-bend, default); "
                         "follow = B stays at A's tempo throughout (the first batch's behaviour)")
    ap.add_argument("--no-chroma-ref", action="store_true",
                    help="ALSO render a chroma-guidance-OFF reference per config")
    ap.add_argument("--mode", choices=("refine", "inpaint", "sinesweep"), default="refine",
                    help="refine = whole-composite a2a at each nl (the 07-07 first batch); "
                         "inpaint = PURE transition: original audio outside the window, "
                         "chroma-guided inpaint generation of the bridge (no nl dimension); "
                         "sinesweep = Kim's per-frame DEPTH sweep: a2a strength 0 at window "
                         "edges -> nl (peak) at centre -> 0, via a release-schedule callback")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    wins = [int(x) for x in args.windows.split(",")]
    nls = [float(x) for x in args.noise_levels.split(",")]
    # segments must comfortably contain the largest crossfade window
    args.seg_sec = max(args.seg_sec, 1.6 * max(wins) / FPS)

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
        print(f"[{a_key}->{b_key}] tempo A={ta:.1f} B={tb:.1f} match speed={speed:.4f} "
              f"mode={args.tempo_mode}", flush=True)

        # segments anchored on DOWNBEATS (bar starts); B anchored on the RAW track
        a_end = downbeat_near(A, sr, 0.62 * A.shape[1] / sr)
        b_start0 = downbeat_near(B, sr, 0.40 * B.shape[1] / sr)
        bar_sec = 4 * 60.0 / ta   # A's bar length (B is matched to it at the window)
        A_seg = A[:, int((a_end - args.seg_sec) * sr):int(a_end * sr)]

        zA = encode(model, A_seg, sr)
        cA = compute_same_chroma(A_seg.T, sr).reshape(384, -1)   # (3,128,T) -> (384,T)

        for W_req in wins:
            # quantize the window to WHOLE BARS; compensate the sub-frame residual
            # by shifting B's cut so kicks align exactly inside the blend
            bars = max(1, round((W_req / FPS) / bar_sec))
            W = int(round(bars * bar_sec * FPS))
            residual = W / FPS - bars * bar_sec          # seconds, |r| < 1 frame
            cut = b_start0 + residual
            raw_seg = B[:, int(cut * sr):int((cut + args.seg_sec * 1.5) * sr)]
            if abs(speed - 1.0) > 0.005:
                # ramp: matched to A's tempo at the window, bending to NATIVE by
                # window end (DJ pitch-bend); follow: matched throughout
                ramp_to = 1.0 if args.tempo_mode == "ramp" else None
                Bseg_s = bungee_stretch(raw_seg, sr, speed,
                                        ramp_to=ramp_to, ramp_out_sec=W / FPS)
            else:
                Bseg_s = raw_seg
            B_seg = Bseg_s[:, :int(args.seg_sec * sr)]
            zB = encode(model, B_seg, sr)
            cB = compute_same_chroma(B_seg.T, sr).reshape(384, -1)
            print(f"  [win] req {W_req}f -> {W}f = {bars} bars (residual {residual*1000:+.1f}ms)", flush=True)
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
            if args.mode == "sinesweep":
                # per-frame depth: 0 outside the window, sine bump peaking at nl
                Wlo, Whi = zA.shape[-1] - W, zA.shape[-1]
                depth_shape = torch.zeros(Tz)
                depth_shape[Wlo:Whi] = torch.sin(torch.linspace(0, torch.pi, W))
                nls_eff = nls
            elif args.mode == "inpaint":
                nls_eff = [None]
                # window bounds in the composite (frames -> seconds)
                w_lo = (zA.shape[-1] - W) / FPS
                w_hi = zA.shape[-1] / FPS
            else:
                nls_eff = nls
            for nl in nls_eff:
                for chroma_on in ([True, False] if args.no_chroma_ref else [True]):
                    tag = "chroma" if chroma_on else "plain"
                    nl_tag = "inpaint" if nl is None else f"nl{int(nl*100):02d}"
                    out = args.out_dir / f"{a_key}2{b_key}__w{W}_{nl_tag}_{tag}.wav"
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
                              sample_size=int((dur + 8) * sr))
                    if nl is None:  # pure-transition inpaint of the window
                        kw["inpaint_audio"] = (sr, audio_ref.float())
                        kw["inpaint_mask_start_seconds"] = w_lo
                        kw["inpaint_mask_end_seconds"] = w_hi
                    elif args.mode == "sinesweep":
                        # start at peak depth; frames stay clamped to the reference
                        # trajectory until global t falls to their own sine depth
                        kw["init_audio"] = (sr, audio_ref.float())
                        kw["init_noise_level"] = nl
                        z_ref = z.float().cpu()
                        torch.manual_seed(4242)
                        eps_ref = torch.randn_like(z_ref)
                        depth = (depth_shape * nl).view(1, 1, -1)

                        def cb(d, _z=z_ref, _e=eps_ref, _d=depth):
                            x, tt = d["x"], float(d["t"][0])
                            n = min(x.shape[-1], _z.shape[-1])
                            hold = (_d[..., :n] < tt)  # not yet released
                            ref_t = ((1 - tt) * _z[..., :n] + tt * _e[..., :n]).to(x.device, x.dtype)
                            xs = x[..., :n]
                            x[..., :n].copy_(torch.where(hold.to(x.device), ref_t, xs))

                        kw["callback"] = cb
                    else:
                        kw["init_audio"] = (sr, audio_ref.float())
                        kw["init_noise_level"] = nl
                    if chroma_on:
                        kw["latch_configs"] = [{"model_path": CHROMA_HEAD,
                                                "target_raw": target,
                                                "weight": 1.0, "end_pct": 0.6}]
                        kw["latch_hparams"] = {"rho": CHROMA_GAIN, "mu": CHROMA_GAIN}
                    outa = model.generate(**kw)
                    y = outa[0].float().cpu().numpy()
                    if nl is None:
                        # splice ORIGINAL audio back outside the window (1s fades)
                        ref = audio_ref.float().cpu().numpy()
                        n = min(y.shape[1], ref.shape[1])
                        y, ref = y[:, :n], ref[:, :n]
                        lo_n, hi_n = int(w_lo * sr), min(int(w_hi * sr), n)
                        f = int(1.0 * sr)
                        outy = ref.copy()
                        outy[:, lo_n:hi_n] = y[:, lo_n:hi_n]
                        r = np.linspace(0, 1, f, dtype=np.float32)
                        if lo_n - f >= 0:
                            outy[:, lo_n - f:lo_n] = ref[:, lo_n - f:lo_n] * (1 - r) + y[:, lo_n - f:lo_n] * r
                        if hi_n + f <= n:
                            outy[:, hi_n:hi_n + f] = y[:, hi_n:hi_n + f] * (1 - r) + ref[:, hi_n:hi_n + f] * r
                        y = outy
                    save_audio(out, torch.tensor(y), sr, normalize=True)
                    print(f"[clip] {out.name}  {time.time()-t0:5.1f}s", flush=True)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
