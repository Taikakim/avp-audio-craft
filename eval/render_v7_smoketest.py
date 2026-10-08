#!/usr/bin/env python
"""render_v7_smoketest.py -- 4-stem v7 transition smoke test, pre-computed stems.

Replaces render_v7_4track_smoketest_fast.py (and the copies in ..._FULL.py / ..._FULL2.py) with the
review fixes by KUANG 2026-10-08 (see antigravity.kuang.log). Same job, same stems, same windows:
  * the DSP layers live in mixtape_v7_dsp.py and are unit-tested;
  * a failed or non-finite generation STOPS the run (--allow-fallback restores the old
    behaviour) and the file name says which path produced the `other` layer;
  * run_meta.json is written per run (spec R0.6 / section 5 item 12);
  * --no-generate renders everything except the generative `other` layer, with no GPU,
    no SA3 and no mir-same-chroma, so the DSP can be auditioned and tested anywhere.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

import mixtape_v7_dsp as dsp

SR = 44100
STEM_NAMES = ["drums", "bass", "other", "vocals", "residual"]   # residual = mix - sum(stems) (spec S4)

# No drive paths in the tree (docs/GIT-PROTOCOL.md section 4): the first version hard-coded its drive
# mounts; they are still in git history. Pass the flags or set the environment variables.
D_BOUNDS = "/tmp/bounds_structural.json"        # where mixtape_structural_bounds.py writes
ENV = {
    "order": "V7_ORDER",            # .../mixtape_v7_phase0/order_used.json
    "stems_dir": "V7_STEMS",        # .../mixtape_v7_stems  (one NN/ folder per clip)
    "out_dir": "V7_SMOKE_OUT",
    "ckpt_a": "V7_CKPT_A",          # only needed unless --no-generate
    "ckpt_b": "V7_CKPT_B",
    "chroma_head": "V7_CHROMA_HEAD",
}


def get_chroma(audio, sr):
    """SAME chroma of a (C, N) window -> (1, 384, T) tensor. (3,128,T) -> (384,T), as everywhere else."""
    import torch
    sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
    from harmonic.same_chroma import compute_same_chroma
    c = compute_same_chroma(audio.T, sr).reshape(384, -1)
    return torch.tensor(c).unsqueeze(0)


def chroma_morph_target(other_a, other_b):
    import torch
    chroma_a, chroma_b = get_chroma(other_a, SR), get_chroma(other_b, SR)
    n = chroma_a.shape[-1]
    up = torch.linspace(0, 1, n).view(1, 1, -1)
    return (chroma_a * (1 - up) + chroma_b * up).float()


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--order", default=os.environ.get(ENV["order"]), help=f"order_used.json (env {ENV['order']})")
    ap.add_argument("--stems-dir", default=os.environ.get(ENV["stems_dir"]), help=f"env {ENV['stems_dir']}")
    ap.add_argument("--bounds", default=D_BOUNDS)
    ap.add_argument("--out-dir", default=os.environ.get(ENV["out_dir"]), help=f"env {ENV['out_dir']}")
    ap.add_argument("--clips", default="2:6", help="slice of the order list, start:stop (default 2:6 = clips 2..5)")
    ap.add_argument("--w-bars", type=int, default=8,
                    help="window length in bars. 8, not 9: the window is centred on the boundary, so an even "
                         "count puts both edges on bar lines (spec R0.4 wants 12 or 16 for the real mix)")
    ap.add_argument("--default-bpm", type=float, default=140.0, help="used, and logged, only if a clip has no 'bpm'")
    ap.add_argument("--blend-ms", type=float, default=50.0, help="bass hand-over blend (spec: <= 50 ms)")
    ap.add_argument("--no-generate", action="store_true", help="skip the model: `other` = plain crossfade, labelled so")
    ap.add_argument("--allow-fallback", action="store_true",
                    help="if generation fails, continue with the plain crossfade (labelled in the file name and meta)")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--latch-gain", type=float, default=2048.0)
    ap.add_argument("--ckpt-a", default=os.environ.get(ENV["ckpt_a"]), help=f"env {ENV['ckpt_a']}")
    ap.add_argument("--ckpt-b", default=os.environ.get(ENV["ckpt_b"]), help=f"env {ENV['ckpt_b']}")
    ap.add_argument("--chroma-head", default=os.environ.get(ENV["chroma_head"]), help=f"env {ENV['chroma_head']}")
    ap.add_argument("--prompt-a", default="aggressive upbeat goa trance")
    ap.add_argument("--prompt-b", default="driving pulsating psytrance")
    args = ap.parse_args(argv)
    need = ["order", "stems_dir", "out_dir"] + ([] if args.no_generate else ["ckpt_a", "ckpt_b", "chroma_head"])
    missing = [f"--{n.replace('_', '-')} (or ${ENV[n]})" for n in need if not getattr(args, n)]
    if missing:
        ap.error("missing: " + ", ".join(missing))
    return args


def load_stems(stems_dir, idx):
    d = Path(stems_dir) / f"{idx:02d}"
    out = {}
    for n in STEM_NAMES:
        x, sr = sf.read(str(d / f"{n}.wav"), dtype="float32")
        if sr != SR:
            raise ValueError(f"{d / (n + '.wav')}: sample rate {sr}, expected {SR}")
        out[n] = (x.T if x.ndim == 2 else x[None, :])
    return out


def main(argv=None):
    args = parse_args(argv)
    a0, a1 = (int(v) for v in args.clips.split(":"))
    all_clips = json.loads(Path(args.order).read_text())
    clips = all_clips[a0:a1]
    bounds = json.loads(Path(args.bounds).read_text())
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "purpose": "v7 4-stem transition smoke test (pre-computed stems)",
        "hypothesis": "bass hand-over + drums crossfade + generated `other` give a seam-free transition window",
        "kill_criterion": "any non-finite stem, or `other` generation falling back, ends the run",
        "args": dict(vars(args)),
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kim_feedback": None,
        "transitions": [],
    }

    stems = {}
    for c in clips:
        stems[c["id"]] = load_stems(args.stems_dir, all_clips.index(c))
        print(f"Loaded stems for {c['id']}", flush=True)

    sa3_model = None
    if not args.no_generate:
        sys.path.insert(0, "/home/kim/Projects/SAO/eval")
        from stable_audio_3 import StableAudioModel
        from mixtape_v7_generative_inference import dual_latch_guided_generate
        print("Initializing SA3 Model...", flush=True)
        sa3_model = StableAudioModel.from_pretrained("medium-base", device="cuda")

    for i in range(len(clips) - 1):
        cA, cB = clips[i], clips[i + 1]
        print(f"Processing Transition {i + 1}: {cA['id']} -> {cB['id']}", flush=True)
        rec = {"i": i, "a": cA["id"], "b": cB["id"]}
        meta["transitions"].append(rec)

        bpm = cA.get("bpm")
        rec["bpm_source"] = "order" if bpm else "default"
        bpm = float(bpm or args.default_bpm)
        rec["bpm"] = bpm
        W_sec = args.w_bars * 4 * 60 / bpm
        L = int(round(W_sec * SR))
        # one seconds->samples conversion each; both windows have length L by construction
        a_lo = int(round(bounds[cA["id"]]["end_pre_zc"] * SR)) - L // 2
        b_lo = int(round(bounds[cB["id"]]["start"] * SR)) - L // 2
        sA, sB = stems[cA["id"]], stems[cB["id"]]

        def win(s, name, lo):
            return dsp.safe_slice(s[name], lo, lo + L)

        bass, ga, gb = dsp.bass_handover(win(sA, "bass", a_lo), win(sB, "bass", b_lo), L // 2,
                                         int(round(SR * args.blend_ms / 1000.0)))
        drums = dsp.drums_crossfade(win(sA, "drums", a_lo), win(sB, "drums", b_lo), SR)
        vocals = dsp.crossfade(win(sA, "vocals", a_lo), win(sB, "vocals", b_lo))
        resid = dsp.crossfade(win(sA, "residual", a_lo), win(sB, "residual", b_lo), kind="linear")
        other_a, other_b = win(sA, "other", a_lo), win(sB, "other", b_lo)
        other_ref = dsp.crossfade(other_a, other_b)          # reference level, and the labelled fallback

        other, other_path = other_ref, "skipped"
        if sa3_model is not None:
            try:
                import torch
                target = chroma_morph_target(other_a, other_b)
                sa3_model.load_lora([args.ckpt_b])
                
                for nl in [0.5, 0.6, 0.7]:
                    Tz2 = int(np.ceil(W_sec * sa3_model.model.sample_rate / sa3_model.model.pretransform.downsampling_ratio))
                    dshape = torch.sin(torch.linspace(0, torch.pi, Tz2))
                    depth2 = (dshape * nl).view(1, 1, -1)
                    
                    pre2 = sa3_model.model.pretransform
                    pp = next(pre2.parameters())
                    with torch.inference_mode():
                        z_ref2 = pre2.encode(torch.tensor(other_ref, device=pp.device, dtype=pp.dtype).unsqueeze(0)).float().cpu()
                    torch.manual_seed(args.seed)
                    eps2 = torch.randn_like(z_ref2)
                    
                    def cb2(d, _z=z_ref2, _e=eps2, _d=depth2):
                        x, tt = d["x"], float(d["t"][0])
                        nn = min(x.shape[-1], _z.shape[-1], _d.shape[-1])
                        hold = (_d[..., :nn] < tt)
                        ref_t = _z[..., :nn] * (1 - tt) + _e[..., :nn] * tt
                        x[..., :nn] = torch.where(hold.to(x.device), ref_t.to(x.dtype).to(x.device), x[..., :nn])
                    
                    kw = dict(prompt=args.prompt_b, duration=W_sec, steps=args.steps, cfg_scale=6.0,
                              seed=args.seed, batch_size=1, sample_size=int((W_sec + 8) * SR),
                              init_audio=(SR, torch.tensor(other_ref, dtype=torch.float32)), init_noise_level=nl,
                              latch_configs=[{"model_path": args.chroma_head, "target_raw": target, "weight": 1.0, "end_pct": 0.6}],
                              latch_hparams={"rho": args.latch_gain, "mu": args.latch_gain}, callback=cb2)
                    gen = sa3_model.generate(**kw)[0].float().cpu().numpy()
                    
                    rec_nl = rec.copy()
                    rec_nl["nl"] = nl
                    rec_nl["other_peak"] = dsp.assert_finite(gen, f"transition {i} other nl{nl}")
                    rec_nl["other_len_delta"] = int(gen.shape[-1] - L)
                    gen = np.pad(gen, ((0, 0), (0, max(0, L - gen.shape[-1]))))[:, :L]
                    other, rec_nl["other_gain"] = dsp.match_rms(gen, other_ref)
                    other_path = f"nl{int(nl*100)}"
                    rec_nl["other_path"] = other_path
                    
                    trans = (bass + drums + other + vocals + resid).astype(np.float64)
                    rec_nl["peak"] = float(np.abs(trans).max())
                    rec_nl["clipped_if_pcm16"] = bool(rec_nl["peak"] > 1.0)
                    rec_nl["min_bass_power_gain"] = float(np.sqrt(ga ** 2 + gb ** 2).min())
                    name = out_dir / f"v7_smoke_trans_FAST_{i}_{other_path}.wav"
                    sf.write(str(name), trans.T, SR, subtype="FLOAT")
                    rec_nl["file"] = name.name
                    print(f"  wrote {name.name} (peak {rec_nl['peak']:.2f}, other: {other_path})", flush=True)
            except Exception as e:                                # noqa: BLE001
                rec["error"] = repr(e)
                if not args.allow_fallback:
                    rec["other_path"] = "FAILED"
                    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
                    raise
                print(f"Generative inference failed, FALLING BACK to crossfade: {e!r}", flush=True)
                other_path = "fallback_crossfade"
                
                trans = (bass + drums + other + vocals + resid).astype(np.float64)
                rec["peak"] = float(np.abs(trans).max())
                rec["clipped_if_pcm16"] = bool(rec["peak"] > 1.0)
                rec["min_bass_power_gain"] = float(np.sqrt(ga ** 2 + gb ** 2).min())
                name = out_dir / f"v7_smoke_trans_FAST_{i}_{other_path}.wav"
                sf.write(str(name), trans.T, SR, subtype="FLOAT")
                rec["file"] = name.name
                print(f"  wrote {name.name} (peak {rec['peak']:.2f}, other: {other_path})", flush=True)
        else:
            trans = (bass + drums + other + vocals + resid).astype(np.float64)
            rec["peak"] = float(np.abs(trans).max())
            rec["clipped_if_pcm16"] = bool(rec["peak"] > 1.0)
            rec["min_bass_power_gain"] = float(np.sqrt(ga ** 2 + gb ** 2).min())
            name = out_dir / f"v7_smoke_trans_FAST_{i}_{other_path}.wav"
            sf.write(str(name), trans.T, SR, subtype="FLOAT")
            rec["file"] = name.name
            print(f"  wrote {name.name} (peak {rec['peak']:.2f}, other: {other_path})", flush=True)

    meta["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
    print(f"Done. {len(meta['transitions'])} transitions and run_meta.json in {out_dir}", flush=True)


if __name__ == "__main__":
    main()
