#!/usr/bin/env python
"""safa_ab.py — SaFa latent-swap join vs slerp A/B on a long a2a render (task #27).

Kim's diagnosis: slerp/averaging joins suppress high-frequency latent variance ->
RMS collapse in long a2a. SaFa (arXiv:2502.05130) replaces overlap averaging with a
binary frame-level latent SWAP (interval w=1): every joined frame is an exact copy
of one side, so per-frame variance is fully preserved. This driver renders the SAME
long a2a twice — join_mode='slerp' vs 'swap' (stable_audio_3.inference.longform.
CrossfadeStitcher) — with identical window latents (same ckpt, seed, SDEdit
trajectory; only the seam join differs), and writes per-window RMS + HF-variance
trajectories to metrics.json beside the wavs.

Scope (mirrors the swap_join docstring): this is the JOIN-LEVEL swap, not the
paper's per-step joint diffusion — ChunkGenerator/sample_diffusion runs each
window's denoising as a closed loop, so frames are exchanged post-hoc between
fully-denoised windows.

Run (GPU box or LUMI; do NOT run the render on the shared local card):
    FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/safa_ab.py \
        --device cuda --out-dir <eval-drive-dir>
Pure-CPU unit test (no model, no audio):
    python eval/safa_ab.py --selftest
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))

SRC = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-analyzed/"
           "Aavepyora - Goddess Guerilla - Kaikki-Alla")
CKPT = ("/run/media/kim/Mantu/sa3_lora_runs/dora128_everything_8ep_lr1x/"
        "epoch=7-step=12216.ckpt")
PROMPT = ("goa trance, driving 16th-note bassline, acid leads, full arrangement, "
          "clean punchy production")
MODES = ("slerp", "swap")


# ---------------------------------------------------------------- metrics (numpy)

def latent_rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


def hf_variance(x: np.ndarray) -> float:
    """Variance of the first temporal difference — the HF latent component that
    interpolation cancels (SaFa Fig. 2: averaging suppresses exactly this)."""
    d = x[..., 1:] - x[..., :-1]
    return float(np.var(d.astype(np.float64)))


def region_stats(x: np.ndarray) -> dict:
    return {"rms": latent_rms(x), "hf_var": hf_variance(x)}


def trajectory(x: np.ndarray, bin_frames: int) -> list[dict]:
    out = []
    for s in range(0, x.shape[-1] - bin_frames + 1, bin_frames):
        st = region_stats(x[..., s:s + bin_frames])
        st["frame"] = s
        out.append(st)
    return out


# ---------------------------------------------------------------- assembly

def assemble(windows, overlap, join_mode):
    """Join overlapping window latents (list of (1,C,W) torch tensors, adjacent
    windows sharing `overlap` frames of source timeline) with the given join mode.
    Returns (assembled latent, per-seam stats)."""
    from stable_audio_3.inference.longform import CrossfadeStitcher
    import torch
    st = CrossfadeStitcher(blend_frames=overlap, join_mode=join_mode)
    out = windows[0]
    seams = []
    for k, win in enumerate(windows[1:], start=1):
        prev = out[..., -overlap:]
        new = win[..., :overlap]
        joined = st.transition_join(out, win, overlap)
        seams.append({
            "seam": k,
            "prev_tail": region_stats(prev.numpy()),
            "new_head": region_stats(new.numpy()),
            "joined": region_stats(joined.numpy()),
        })
        out = torch.cat([out[..., :-overlap], joined, win[..., overlap:]], dim=-1)
    return out, seams


# ---------------------------------------------------------------- render driver

def render(args):
    import soundfile as sf
    import torch
    from sa3_control.audio_io import save_audio
    from stable_audio_3 import StableAudioModel
    from stable_audio_3.inference.longform import SDEditReanchor

    args.out_dir.mkdir(parents=True, exist_ok=True)
    audio, sr = sf.read(args.track, dtype="float32", always_2d=True)
    audio = audio.T  # (C, N)

    model = StableAudioModel.from_pretrained("medium-base", device=args.device)
    model.load_lora([args.ckpt])
    if sr != model.model.sample_rate:
        raise ValueError(f"source sr {sr} != model sr {model.model.sample_rate}")
    pt = model.model.pretransform
    ds = pt.downsampling_ratio
    dtype = next(pt.model.parameters()).dtype
    W, ov = args.window_frames, args.overlap_frames
    hop = W - ov
    total_frames = min(args.max_frames, audio.shape[1] // ds)
    n_win = max(1, (total_frames - W) // hop + 1)
    print(f"[safa_ab] {n_win} windows x {W}f (overlap {ov}f), nl={args.nl}, "
          f"seed={args.seed}", flush=True)

    reanchor = SDEditReanchor(model, steps=args.steps, cfg_scale=args.cfg_scale)
    windows = []  # fully-denoised window latents, shared by both join modes
    for k in range(n_win):
        s = k * hop
        chunk = audio[:, s * ds:(s + W) * ds]
        with torch.no_grad():
            src_lat = pt.encode(torch.from_numpy(chunk)[None].to(args.device, dtype))
        lat = reanchor.reanchor(src_lat[..., :W], sigma_peak=args.nl,
                                prompt=args.prompt, seed=args.seed + k)
        windows.append(lat.float().cpu())
        print(f"[w{k:02d}] frames {s}-{s + W} rms={latent_rms(windows[-1].numpy()):.4f}",
              flush=True)

    metrics = {
        "windows": [region_stats(w.numpy()) | {"index": k}
                    for k, w in enumerate(windows)],
        "modes": {},
    }
    result = {}
    for mode in MODES:
        lat, seams = assemble(windows, ov, mode)
        traj = trajectory(lat.numpy(), bin_frames=ov)
        metrics["modes"][mode] = {"trajectory": traj, "seams": seams}
        with torch.no_grad():
            wav = pt.decode(lat.to(args.device, dtype))
        out_wav = args.out_dir / f"safa_ab_{mode}.wav"
        save_audio(out_wav, wav[0].float().cpu(), sr, normalize=True)
        inp_hf = np.mean([s["prev_tail"]["hf_var"] + s["new_head"]["hf_var"]
                          for s in seams]) / 2.0
        result[mode] = {
            "wav": out_wav.name,
            "seam_hf_var_ratio": float(np.mean(
                [s["joined"]["hf_var"] for s in seams]) / max(inp_hf, 1e-12)),
            "seam_rms_ratio": float(np.mean(
                [s["joined"]["rms"] for s in seams]) / max(np.mean(
                    [(s["prev_tail"]["rms"] + s["new_head"]["rms"]) / 2.0
                     for s in seams]), 1e-12)),
        }
        print(f"[{mode}] seam hf_var ratio {result[mode]['seam_hf_var_ratio']:.3f} "
              f"rms ratio {result[mode]['seam_rms_ratio']:.3f}", flush=True)

    (args.out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (args.out_dir / "run_meta.json").write_text(json.dumps({
        "purpose": "A/B: SaFa latent-swap join vs slerp on the same long a2a — do "
                   "the seams keep RMS/HF-variance under swap where slerp collapses?",
        "hypothesis": "slerp/averaging joins interpolate correlated window latents "
                      "and cancel their uncorrelated HF component -> HF-variance/RMS "
                      "collapse in long a2a; the SaFa w=1 frame-swap join copies "
                      "frames verbatim and preserves both (join-level swap, not the "
                      "paper's per-step joint diffusion — see swap_join docstring).",
        "mechanism_ref": "SAO/papers/2502.05130v3 Latent Swap Joint Diffusion for "
                         "2D Long-Form Latent Generation.pdf (Self-Loop Latent Swap, "
                         "Eq. 9-10, w=1)",
        "script": "SAO/eval/safa_ab.py",
        "join_impl": "stable-audio-3/stable_audio_3/inference/longform.py "
                     "(CrossfadeStitcher join_mode='slerp'|'swap', swap_join)",
        "track": Path(args.track).name,
        "ckpt": args.ckpt,
        "training_run": str(Path(args.ckpt).parent),
        "training_recipe": "dora128_everything_8ep_lr1x: DoRA r128 on medium-base, "
                           "8 epochs, lr 1x baseline; full args in the run dir's "
                           "log/sidecar (see training_run).",
        "training_dataset": "goa corpus, 'everything' caption set (Goa_Separated "
                            "full tracks; see run dir sidecar for counts/augmentation)",
        "eval_params": {"nl": args.nl, "seed": args.seed, "steps": args.steps,
                        "cfg_scale": args.cfg_scale, "prompt": args.prompt,
                        "window_frames": W, "overlap_frames": ov,
                        "max_frames": args.max_frames, "device": args.device,
                        "n_windows": n_win},
        "result": result,
        "kim_feedback": None,
    }, indent=2))
    print("[done]", flush=True)


# ---------------------------------------------------------------- CPU selftest

def selftest():
    """Pure-CPU: synthetic latents through both joins. Asserts the swap join
    preserves per-frame variance exactly (frames copied verbatim) while the slerp
    join shrinks the uncorrelated (HF) component, and that shapes match."""
    import torch
    from stable_audio_3.inference.longform import CrossfadeStitcher, swap_join

    torch.manual_seed(7)
    C, n = 64, 64
    base = torch.randn(1, C, n)          # shared content (correlated trajectories)
    na, nb = torch.randn(1, C, n), torch.randn(1, C, n)
    a, b = base + 0.5 * na, base + 0.5 * nb

    st_sl = CrossfadeStitcher(blend_frames=n, join_mode="slerp")
    st_sw = CrossfadeStitcher(blend_frames=n, join_mode="swap")
    j_sl = st_sl.transition_join(a, b, n)
    j_sw = st_sw.transition_join(a, b, n)
    assert j_sl.shape == j_sw.shape == a.shape, (j_sl.shape, j_sw.shape, a.shape)

    # swap = verbatim frame copies -> per-frame variance preserved exactly
    assert torch.equal(j_sw[..., 0::2], a[..., 0::2])
    assert torch.equal(j_sw[..., 1::2], b[..., 1::2])
    assert torch.equal(swap_join(a, b), j_sw)

    # residual (uncorrelated/HF) per-frame variance across channels, interior frames
    v_sw = ((j_sw - base)[..., 2:n - 2]).var(dim=1).mean().item()
    v_sl = ((j_sl - base)[..., 2:n - 2]).var(dim=1).mean().item()
    v_in = 0.5 * (((a - base).var(dim=1).mean() + (b - base).var(dim=1).mean()).item())
    assert abs(v_sw - v_in) / v_in < 0.05, f"swap changed variance: {v_sw} vs {v_in}"
    assert v_sl < 0.75 * v_sw, f"slerp shows no shrinkage: {v_sl} vs swap {v_sw}"

    # continuation_join keeps region length in both modes
    tail, region = torch.randn(1, C, 32), torch.randn(1, C, 48)
    for st in (st_sl, st_sw):
        st2 = CrossfadeStitcher(blend_frames=8, join_mode=st.join_mode)
        assert st2.continuation_join(tail, region).shape == region.shape

    # full assembly parity: same windows -> same output shape in both modes
    wins = [torch.randn(1, C, 96) for _ in range(3)]
    out_sl, seams_sl = assemble(wins, 16, "slerp")
    out_sw, seams_sw = assemble(wins, 16, "swap")
    assert out_sl.shape == out_sw.shape and len(seams_sl) == len(seams_sw) == 2
    r_sl = np.mean([s["joined"]["hf_var"] for s in seams_sl])
    r_sw = np.mean([s["joined"]["hf_var"] for s in seams_sw])
    print(f"selftest: interior residual pfv — input {v_in:.4f}, swap {v_sw:.4f} "
          f"(preserved), slerp {v_sl:.4f} (shrunk); assembled shape {tuple(out_sl.shape)}; "
          f"independent-window seam hf_var slerp {r_sl:.4f} vs swap {r_sw:.4f}")
    print("selftest: OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true",
                    help="pure-CPU unit test of both joins; no model/audio")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--track", default=str(SRC / "full_mix.flac"))
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--nl", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--window-frames", type=int, default=512)
    ap.add_argument("--overlap-frames", type=int, default=64)
    ap.add_argument("--max-frames", type=int, default=2048,
                    help="cap on total latent frames rendered (~190 s at 10.767 Hz)")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if args.out_dir is None:
        ap.error("--out-dir is required unless --selftest")
    render(args)


if __name__ == "__main__":
    main()
