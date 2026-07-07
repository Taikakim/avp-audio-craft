#!/usr/bin/env python
"""transition_lab.py — three transition constructions (Kim 2026-07-07, after the
512-frame latent slerp got noisy over the transition on goa material):

  v1_inpaint   — the model-native answer: hard-cut A|B, mask the window around the
                 cut, let the trained inpainting fill the bridge with context from
                 both sides ("the information exists in the model — drag it out").
  v2_beatmatch — decode, tempo-match B to A (librosa), beat-phase align, equal-power
                 AUDIO crossfade (no latent midpoint to fall off the manifold).
  v3_sinemask  — the brave one: v2's audio re-noised to 0.3 and re-denoised with a
                 GRADED per-frame clamp (sine bump over the transition window): the
                 middle of the transition regenerates the most, edges stay anchored.
                 Implemented via the euler callback (in-place x clamp to the
                 reference trajectory) — no custom sampler.

Arms: newcap8 + base. Prompt: aggr. Seed pair 1234->4242. ~190s outputs.
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

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_prompt_styles import DEFAULT_ARMS  # noqa: E402

PROMPT = "aggressive upbeat goa trance"
FPS = 44100 / 4096            # latent frames per second

# extra arms beyond eval_prompt_styles' registry (Kim 2026-07-07 round 2:
# HoF pick + ~5400-step ckpts, "around 5400 probably can't go wrong")
EXTRA_ARMS = {
    "hof":      "/run/media/kim/Mantu1/sa3_lora_runs/sa3-goa-dora-47s-b4-cont/x20b3ygb/checkpoints/epoch=3-step=5400.ckpt",
    "newstack": "/run/media/kim/Mantu1/sa3_lora_runs/dora16_goa_newstack_8ep/epoch=3-step=5400.ckpt",
    "evr1x54":  "/run/media/kim/Mantu1/sa3_lora_runs/dora128_everything_8ep_lr1x/epoch=3-step=6108.ckpt",
}


def gen_latents(model, seed, steps, cfg, seg):
    z = model.generate(prompt=PROMPT, duration=seg / FPS, steps=steps, cfg_scale=cfg,
                       seed=seed, batch_size=1, return_latents=True)
    return z[..., :seg]


def decode(model, z):
    pre = model.model.pretransform
    p = next(pre.parameters())
    with torch.inference_mode():
        return pre.decode(z.to(device=p.device, dtype=p.dtype))[0].float().cpu()


def beatmatch_crossfade(a, b, sr, fade_sec=16.0):
    """Tempo-match b to a, beat-phase align, equal-power crossfade. numpy stereo (C,N)."""
    import librosa
    am, bm = a.mean(0), b.mean(0)
    ta, beats_a = librosa.beat.beat_track(y=am, sr=sr, units="time")
    tb, beats_b = librosa.beat.beat_track(y=bm, sr=sr, units="time")
    ta, tb = float(np.atleast_1d(ta)[0]), float(np.atleast_1d(tb)[0])
    rate = tb / ta if ta > 0 and tb > 0 else 1.0   # stretch b by this to match a
    # librosa tempo octave errors: fold the ratio back toward 1 (goa tempos are close)
    while rate > 1.35:
        rate /= 2
    while rate < 0.74:
        rate *= 2
    print(f"[v2] tempo A={ta:.1f} B={tb:.1f} -> stretch rate {rate:.4f}", flush=True)
    b_st = np.stack([librosa.effects.time_stretch(ch, rate=rate) for ch in b])
    _, beats_bs = librosa.beat.beat_track(y=b_st.mean(0), sr=sr, units="time")

    # crossfade region: end of a; align b's beat grid phase to a's
    fade_n = int(fade_sec * sr)
    a_end = a.shape[1]
    fade_start = a_end - fade_n
    # a's first beat inside the fade
    ba = beats_a[beats_a >= fade_start / sr]
    anchor_a = float(ba[0]) if len(ba) else fade_start / sr
    # b's beat near its start-of-use point — 25% in, capped at 24 s (short
    # segments: the old fixed 24 s left less material than the fade needed)
    b_dur = b_st.shape[1] / sr
    b_use = min(24.0, 0.25 * b_dur)
    bb = beats_bs[beats_bs >= b_use]
    anchor_b = float(bb[0]) if len(bb) else b_use
    # b enters so that anchor_b lands exactly on anchor_a
    b_offset = int(anchor_b * sr) - int((anchor_a - fade_start / sr) * sr)
    b_cut = b_st[:, max(b_offset, 0):]
    if b_cut.shape[1] < fade_n:                      # clamp fade to material
        fade_n = b_cut.shape[1]
        fade_start = a_end - fade_n

    t = np.linspace(0, np.pi / 2, fade_n, dtype=np.float32)
    fo, fi = np.cos(t), np.sin(t)                    # equal power
    xf = a[:, fade_start:] * fo + b_cut[:, :fade_n] * fi
    out = np.concatenate([a[:, :fade_start], xf, b_cut[:, fade_n:]], axis=1)
    return out, rate, anchor_a


def sine_mask(frames, lo, hi, device, dtype):
    """(1,1,frames): 0 outside [lo,hi], sine bump peaking 1.0 at the centre."""
    m = torch.zeros(frames, device=device, dtype=dtype)
    n = hi - lo
    m[lo:hi] = torch.sin(torch.linspace(0, torch.pi, n, device=device, dtype=dtype))
    return m.view(1, 1, -1)


def sinemask_refine(model, audio_np, sr, nl, lo_f, hi_f, steps, cfg, seed):
    """Graded SDEdit: renoise to `nl`, denoise; per-step clamp x toward the fixed
    reference trajectory with weight (1 - mask) — centre regenerates most."""
    pre = model.model.pretransform
    p = next(pre.parameters())
    a = torch.tensor(audio_np, device=p.device, dtype=p.dtype).unsqueeze(0)
    with torch.inference_mode():
        z_ref = pre.encode(a).clone()
    torch.manual_seed(seed)
    eps_ref = torch.randn_like(z_ref.float()).to(z_ref.dtype)
    m = sine_mask(z_ref.shape[-1], lo_f, hi_f, z_ref.device, torch.float32)

    def cb(d):
        x, t = d["x"], d["t"]                        # live tensor, per-batch t
        n = min(x.shape[-1], z_ref.shape[-1], m.shape[-1])  # generate may pad/crop
        tt = t.view(-1, 1, 1).to(torch.float32)
        ref_t = (1 - tt) * z_ref[..., :n].float() + tt * eps_ref[..., :n].float()
        blend = (m[..., :n] * x[..., :n].float() + (1 - m[..., :n]) * ref_t).to(x.dtype)
        x[..., :n].copy_(blend)

    out = model.generate(prompt=PROMPT, duration=audio_np.shape[1] / sr,
                         steps=steps, cfg_scale=cfg, seed=seed, batch_size=1,
                         init_audio=(sr, a[0]), init_noise_level=nl, callback=cb)
    return out[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--arms", default="newcap8,base")
    ap.add_argument("--frames-total", type=int, default=2048,
                    help="total composite length in latent frames")
    ap.add_argument("--xfade-frames", type=int, default=0,
                    help="transition window frames (0 = frames_total/4)")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--steps", type=int, default=16)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--seeds", default="1234,4242")
    ap.add_argument("--sinemask-nl", type=float, default=0.3)
    args = ap.parse_args()
    s1, s2 = [int(x) for x in args.seeds.split(",")]
    TOTAL = args.frames_total
    XF = args.xfade_frames or TOTAL // 4
    SEG = (TOTAL + XF) // 2
    CUT = TOTAL // 2
    WIN = (CUT - XF // 2, CUT + XF // 2)
    total_sec = TOTAL / FPS
    args.out_dir.mkdir(parents=True, exist_ok=True)
    ALL_ARMS = {**DEFAULT_ARMS, **EXTRA_ARMS}

    meta = {"purpose": ("transition constructions after the latent-slerp noise verdict: "
                        "v1 model-native inpaint bridge / v2 beatmatch+audio crossfade / "
                        "v3 sine-masked graded SDEdit (peak nl %.2f at transition centre)"
                        % args.sinemask_nl),
            "gen": {"prompt": PROMPT, "steps": args.steps, "cfg": args.cfg_scale,
                    "seeds": [s1, s2], "window_frames": WIN, "total_frames": TOTAL},
            "checkpoints": {}, "related": ["SAO/eval/transition_lab.py"]}

    for arm in args.arms.split(","):
        ckpt = ALL_ARMS[arm]
        meta["checkpoints"][arm] = ckpt or "medium-base (no adapter)"
        print(f"[load] {arm}", flush=True)
        model = StableAudioModel.from_pretrained("medium-base", device=args.device)
        if ckpt:
            model.load_lora([str(ckpt)])
        sr = model.model.sample_rate
        t0 = time.time()
        zA = gen_latents(model, s1, args.steps, args.cfg_scale, SEG)
        zB = gen_latents(model, s2, args.steps, args.cfg_scale, SEG)

        # --- v1: hard cut + native inpaint over the window --------------------
        z_hard = torch.cat([zA[..., :CUT], zB[..., SEG - (TOTAL - CUT):]], dim=-1)
        assert z_hard.shape[-1] == TOTAL
        hard_audio = decode(model, z_hard)
        out = model.generate(prompt=PROMPT, duration=TOTAL / FPS, steps=args.steps,
                             cfg_scale=args.cfg_scale, seed=s1, batch_size=1,
                             inpaint_audio=(sr, hard_audio),
                             inpaint_mask_start_seconds=WIN[0] / FPS,
                             inpaint_mask_end_seconds=WIN[1] / FPS)
        save_audio(args.out_dir / f"{arm}__{TOTAL}f_v1_inpaint.wav", out[0], sr, normalize=True)
        print(f"[v1] {arm} {time.time()-t0:.0f}s", flush=True)

        # --- v2: decode, beatmatch, audio crossfade ---------------------------
        a_np = decode(model, zA).numpy()
        b_np = decode(model, zB).numpy()
        v2, rate, anchor = beatmatch_crossfade(a_np, b_np, sr,
                                               fade_sec=min(16.0, total_sec / 6))
        save_audio(args.out_dir / f"{arm}__{TOTAL}f_v2_beatmatch.wav",
                   torch.tensor(v2), sr, normalize=True)
        print(f"[v2] {arm} stretch={rate:.4f} anchor={anchor:.1f}s", flush=True)

        # --- v3: sine-masked graded refine of a SEGMENT around the transition,
        # spliced back into v2 (avoids long-audio latent-length mismatches; the
        # mask is 0 at segment edges so the splice joins near-identical content)
        fade_c = (a_np.shape[1] - int(min(16.0, total_sec / 6) / 2 * sr)) / sr
        v2_len_s = v2.shape[1] / sr
        half_seg = min(48.0, total_sec / 3)
        lo_s, hi_s = max(fade_c - half_seg, 0.0), min(fade_c + half_seg, v2_len_s)
        lo_n, hi_n = int(lo_s * sr), int(hi_s * sr)
        seg = v2[:, lo_n:hi_n]
        centre = fade_c - lo_s
        half_win = min(24.0, total_sec / 6)
        lo_f = max(int((centre - half_win) * FPS), 0)
        hi_f = int((centre + half_win) * FPS)
        refined = sinemask_refine(model, seg, sr, args.sinemask_nl, lo_f, hi_f,
                                  args.steps, args.cfg_scale, s1)
        r = refined.float().cpu().numpy()[:, :seg.shape[1]]
        if r.shape[1] < seg.shape[1]:                    # pad from original tail
            r = np.concatenate([r, seg[:, r.shape[1]:]], axis=1)
        # 1 s safety crossfades at the splice edges
        f = int(1.0 * sr)
        ramp = np.linspace(0, 1, f, dtype=np.float32)
        r[:, :f] = seg[:, :f] * (1 - ramp) + r[:, :f] * ramp
        r[:, -f:] = r[:, -f:] * (1 - ramp) + seg[:, -f:] * ramp
        v3 = v2.copy()
        v3[:, lo_n:hi_n] = r
        save_audio(args.out_dir / f"{arm}__{TOTAL}f_v3_sinemask.wav",
                   torch.tensor(v3), sr, normalize=True)
        print(f"[v3] {arm} seg {lo_s:.0f}-{hi_s:.0f}s  total {time.time()-t0:.0f}s", flush=True)

        del model
        if args.device == "cuda":
            torch.cuda.empty_cache()

    (args.out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
