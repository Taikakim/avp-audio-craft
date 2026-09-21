#!/usr/bin/env python
"""mixtape_seam_align_test.py — Kim 2026-09-15: tests whether BPM-matching +
a BAR-quantized (not fixed-seconds) crossfade window fixes the "galloping"
rhythm problem Kim heard in the dual-conditioning test AND in the mixtape's
existing masked/crossfade seams: two clips at different BPMs, joined over a
FIXED time window, leave the DiT reconciling two incompatible rhythmic grids
in the seam. Audibly "deconstructed", not noise — chroma/spectral content
survives the blend (that IS latent-native), the DiT-RECONSTRUCTED rhythm
doesn't (EXPERIMENTS D15: pianoroll true-shuffled +0.022 n.s.; MASTER.md:
beat/downbeat_activation LatCH heads dead at any gain — no lever into rhythm
via the latent).

Reuses the proven machinery from chroma_morph_transitions.py (built 2026-07-07
for real full-track transitions, same underlying problem) rather than
re-deriving it: tempo_of (precise per-pair tempo — librosa's own reported BPM
is too coarse, 0.3 BPM error = ~100ms drift over a long blend = audible
gallop even bar-snapped), bungee_stretch (mir venv time-stretch, DJ
pitch-bend ramp back to native by window end), downbeat_near (bar-phase
snap), fine_align_shift (onset-concurrence xcorr, +/- half bar). New here:
short generated-clip pairs (not full tracks) via --pairs-json, a BARS-based
window (not a fixed-seconds one), a pre-a2a reference dump so the seam can be
judged before the generative pass touches it at all, and an EXPERIMENTAL
onset_envelope target_raw channel (targets the pre-a2a composite's own
measured onset curve, rescaled through the head's own std_mean/std_std so
only the temporal SHAPE is asserted — an attempt to keep the a2a regen
honest to the grid the bar-alignment already established; unproven, Kim
flagged it as a "maybe").

Per pair renders:
  {out}_preA2A.wav                bar-aligned + bpm-matched crossfade, NO a2a
  {out}_nl{NL}_chroma.wav         sine-bump a2a, chroma-ramp guidance ON
  {out}_nl{NL}_plain.wav          same, no guidance at all
  {out}_nl{NL}_chroma_onset.wav   chroma ON + experimental onset guidance
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
from chroma_morph_transitions import (  # noqa: E402
    CHROMA_GAIN, CHROMA_HEAD, FPS, bungee_stretch, compute_same_chroma,
    downbeat_near, encode, fine_align_shift, load, tempo_of,
)
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.inference.longform import slerp  # noqa: E402
from stable_audio_3.models.latch import load_latch_from_checkpoint  # noqa: E402

BRIDGE_CKPT = "/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt"
ONSET_HEAD = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_onset_envelope_best.pt"
ONSET_GAIN = 512.0  # per MASTER §5 sweep: energy-family heads operate ~512, not the 48-96 legacy default


def onset_envelope_np(audio, sr, n_frames):
    """librosa onset-strength envelope, resampled onto the latent grid (n_frames
    at FPS). NOT guaranteed to be in the same raw units as the head's own
    training feature -- see module docstring; the caller rescales through the
    head's own std_mean/std_std so only the SHAPE (not the absolute level) is
    asserted."""
    import librosa
    env = librosa.onset.onset_strength(y=audio.mean(0), sr=sr, hop_length=512)
    t_env = np.linspace(0, audio.shape[1] / sr, len(env))
    t_out = np.linspace(0, audio.shape[1] / sr, n_frames)
    return np.interp(t_out, t_env, env).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs-json", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--ckpt", default=BRIDGE_CKPT)
    ap.add_argument("--bars", type=int, default=4, help="crossfade window width in BARS at the matched tempo")
    ap.add_argument("--noise-levels", default="0.5,0.7")
    ap.add_argument("--seg-sec", type=float, default=12.0, help="audio kept per side of the junction")
    ap.add_argument("--a-frac", type=float, default=0.85, help="A's cut point as a fraction of ITS OWN length")
    ap.add_argument("--b-frac", type=float, default=0.15, help="B's entry point as a fraction of ITS OWN length")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--onset-test", action="store_true", default=False,
                     help="also render the experimental chroma+onset_envelope variant")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    nls = [float(x) for x in args.noise_levels.split(",")]

    meta = {
        "purpose": ("does BPM-matching (bungee) + a BAR-quantized crossfade window fix the "
                    "rhythmic-gallop problem Kim heard in dual_conditioned_sample.py and the "
                    "mixtape seams? Reuses chroma_morph_transitions.py's proven full-track "
                    "alignment machinery on short generated-clip pairs."),
        "bars": args.bars, "noise_levels": nls, "seg_sec": args.seg_sec,
        "steps": args.steps, "cfg": args.cfg_scale, "prompt": args.prompt,
        "chroma_head": CHROMA_HEAD, "chroma_gain": CHROMA_GAIN,
        "onset_head": ONSET_HEAD if args.onset_test else None, "onset_gain": ONSET_GAIN,
        "ckpt": args.ckpt,
        "kim_feedback": None,
    }
    (args.out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))

    print("[load] model", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([args.ckpt])
    sr = model.model.sample_rate

    onset_std_mean = onset_std_std = None
    if args.onset_test:
        h = load_latch_from_checkpoint(ONSET_HEAD, "cpu")
        onset_std_mean = float(h.metadata["std_mean"])
        onset_std_std = float(h.metadata["std_std"])
        print(f"[onset] head std_mean={onset_std_mean:.4f} std_std={onset_std_std:.4f}", flush=True)

    pairs = json.loads(args.pairs_json.read_text())
    for p in pairs:
        out_name = p["out_name"]
        A, sra = load(p["a_path"])
        B, srb = load(p["b_path"])
        assert sra == sr and srb == sr

        ta = tempo_of(A, sr, around_sec=A.shape[1] / sr / 2)
        tb = tempo_of(B, sr, around_sec=B.shape[1] / sr / 2)
        speed = ta / tb
        bar_sec = 4 * 60.0 / ta
        W = int(round(args.bars * bar_sec * FPS))
        seg_sec = max(args.seg_sec, 1.6 * W / FPS)
        print(f"[{out_name}] tempo A={ta:.1f} B={tb:.1f} speed={speed:.4f} "
              f"bar={bar_sec:.3f}s window={args.bars}bars={W}f seg={seg_sec:.1f}s", flush=True)

        a_end = downbeat_near(A, sr, args.a_frac * A.shape[1] / sr)
        b_start0 = downbeat_near(B, sr, args.b_frac * B.shape[1] / sr)
        A_seg = A[:, max(0, int((a_end - seg_sec) * sr)):int(a_end * sr)]

        raw_seg = B[:, int(b_start0 * sr):int((b_start0 + seg_sec * 1.5) * sr)]
        if abs(speed - 1.0) > 0.0005:
            Bseg_s = bungee_stretch(raw_seg, sr, speed, ramp_to=1.0, ramp_out_sec=W / FPS)
        else:
            Bseg_s = raw_seg
        B_seg = Bseg_s[:, :int(seg_sec * sr)]

        sh = fine_align_shift(A_seg, B_seg, sr, span_sec=W / FPS, max_shift_sec=bar_sec / 2)
        if abs(sh) > 0.004:
            print(f"  [align] B shifted {sh*1000:+.0f}ms (onset concurrence)", flush=True)
            if sh < 0:
                B_seg = Bseg_s[:, int(-sh * sr):int(-sh * sr) + int(seg_sec * sr)]
            else:
                pad = np.zeros((B_seg.shape[0], int(sh * sr)), dtype=B_seg.dtype)
                B_seg = np.concatenate([pad, B_seg], axis=1)[:, :int(seg_sec * sr)]

        zA = encode(model, A_seg, sr)
        zB = encode(model, B_seg, sr)
        cA = compute_same_chroma(A_seg.T, sr).reshape(384, -1)
        cB = compute_same_chroma(B_seg.T, sr).reshape(384, -1)
        TA = zA.shape[-1]

        t = torch.linspace(0, 1, W, device=zA.device, dtype=torch.float32).view(1, 1, -1)
        mid = slerp(zA[..., -W:].float(), zB[..., :W].float(), t).to(zA.dtype)
        z = torch.cat([zA[..., :-W], mid, zB[..., W:]], dim=-1)
        Tz = z.shape[-1]

        ramp = np.linspace(0, 1, W, dtype=np.float32)[None, :]
        cA_r = cA[:, :TA] if cA.shape[1] >= TA else np.pad(cA, ((0, 0), (0, TA - cA.shape[1])), mode="edge")
        cB_r = cB[:, :zB.shape[-1]] if cB.shape[1] >= zB.shape[-1] else np.pad(cB, ((0, 0), (0, zB.shape[-1] - cB.shape[1])), mode="edge")
        morph = cA_r[:, -W:] * (1 - ramp) + cB_r[:, :W] * ramp
        chroma_target = np.concatenate([cA_r[:, :-W], morph, cB_r[:, W:]], axis=1)[:, :Tz]

        dur = Tz / FPS
        pre = model.model.pretransform
        with torch.inference_mode():
            audio_ref = pre.decode(z.to(next(pre.parameters()).dtype))[0]
        save_audio(str(args.out_dir / f"{out_name}_preA2A.wav"), audio_ref.float().cpu(), sr)

        onset_target = None
        if args.onset_test:
            raw_env = onset_envelope_np(audio_ref.float().cpu().numpy(), sr, Tz)
            shape = (raw_env - raw_env.mean()) / (raw_env.std() + 1e-8)
            onset_target = (onset_std_mean + shape * onset_std_std).reshape(1, -1)

        Wlo, Whi = zA.shape[-1] - W, zA.shape[-1]
        depth_shape = torch.zeros(Tz)
        depth_shape[Wlo:Whi] = torch.sin(torch.linspace(0, torch.pi, W))
        z_ref = z.float().cpu()
        torch.manual_seed(4242)
        eps_ref = torch.randn_like(z_ref)

        variants = [("chroma", True, False), ("plain", False, False)]
        if args.onset_test:
            variants.append(("chroma_onset", True, True))

        for nl in nls:
            depth = (depth_shape * nl).view(1, 1, -1)

            def cb(d, _z=z_ref, _e=eps_ref, _d=depth):
                x, tt = d["x"], float(d["t"][0])
                n = min(x.shape[-1], _z.shape[-1])
                hold = (_d[..., :n] < tt)
                ref_t = ((1 - tt) * _z[..., :n] + tt * _e[..., :n]).to(x.device, x.dtype)
                xs = x[..., :n]
                x[..., :n].copy_(torch.where(hold.to(x.device), ref_t, xs))

            for tag, chroma_on, onset_on in variants:
                out_path = args.out_dir / f"{out_name}_nl{int(nl*100):02d}_{tag}.wav"
                if out_path.exists():
                    print(f"[skip] {out_path.name}", flush=True)
                    continue
                latch_configs = []
                if chroma_on:
                    latch_configs.append({"model_path": CHROMA_HEAD, "target_raw": chroma_target,
                                           "weight": 1.0, "end_pct": 0.6})
                if onset_on:
                    latch_configs.append({"model_path": ONSET_HEAD, "target_raw": onset_target,
                                           "weight": ONSET_GAIN / CHROMA_GAIN, "end_pct": 0.6})
                gen_kw = dict(prompt=args.prompt, duration=dur, steps=args.steps, cfg_scale=args.cfg_scale,
                              seed=1234, batch_size=1, sample_size=int((dur + 8) * sr),
                              init_audio=(sr, audio_ref.float()), init_noise_level=nl, callback=cb)
                if latch_configs:
                    gen_kw["latch_configs"] = latch_configs
                    gen_kw["latch_hparams"] = {"rho": CHROMA_GAIN, "mu": CHROMA_GAIN}
                print(f"[gen] {out_path.name} nl={nl}", flush=True)
                out = model.generate(**gen_kw)
                save_audio(str(out_path), out[0].float().cpu(), sr)
        print(f"[done] {out_name}", flush=True)


if __name__ == "__main__":
    main()
