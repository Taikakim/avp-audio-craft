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


def latent_slerp_other(model, other_a, other_b, L):
    """Latent crossfade of the `other` stem: encode both windows, slerp across the whole window, decode."""
    import torch
    from stable_audio_3.inference.longform import slerp
    pre = model.model.pretransform
    p = next(pre.parameters())
    with torch.inference_mode():
        za = pre.encode(torch.tensor(other_a, device=p.device, dtype=p.dtype).unsqueeze(0)).float()
        zb = pre.encode(torch.tensor(other_b, device=p.device, dtype=p.dtype).unsqueeze(0)).float()
        n = min(za.shape[-1], zb.shape[-1])
        t = torch.linspace(0, 1, n, device=za.device).view(1, 1, -1)
        z = slerp(za[..., :n], zb[..., :n], t)
        out = pre.decode(z.to(p.dtype))[0].float().cpu().numpy()
    return np.pad(out, ((0, 0), (0, max(0, L - out.shape[-1]))))[:, :L]


def drum_inpaint(model, drums_xf, n_bars, bpm, L, args, prompt=None, cfg=None):
    """Masked inpaint of the central n_bars of the (already crossfaded) drum window; the real drums are
    the context on both sides. Only the masked span is taken from the generation (50 ms edge fades)."""
    import torch
    W_sec = L / SR
    bar = 240.0 / bpm
    lo = W_sec / 2 - n_bars * bar / 2
    hi = lo + n_bars * bar
    out = model.generate(
        prompt=prompt or args.drum_prompt, duration=W_sec, steps=args.steps, cfg_scale=cfg or args.drum_cfg,
        seed=args.seed, batch_size=1, sample_size=int((W_sec + 8) * SR),
        inpaint_audio=(SR, torch.tensor(drums_xf, dtype=torch.float32)),
        inpaint_mask_start_seconds=float(lo), inpaint_mask_end_seconds=float(hi))
    gen = out[0].float().cpu().numpy()
    dsp.assert_finite(gen, f"drum inpaint {n_bars} bar")
    gen = np.pad(gen, ((0, 0), (0, max(0, L - gen.shape[-1]))))[:, :L]
    gen, _ = dsp.match_rms(gen, drums_xf)
    i0, i1 = int(lo * SR), int(hi * SR)
    f = int(0.05 * SR)
    w = np.zeros(L, dtype=np.float32)
    w[i0:i1] = 1.0
    w = np.convolve(w, np.hanning(2 * f + 1) / np.hanning(2 * f + 1).sum(), mode="same").astype(np.float32)
    return drums_xf * (1 - w) + gen * w


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--order", default=os.environ.get(ENV["order"]), help=f"order_used.json (env {ENV['order']})")
    ap.add_argument("--stems-dir", default=os.environ.get(ENV["stems_dir"]), help=f"env {ENV['stems_dir']}")
    ap.add_argument("--bounds", default=D_BOUNDS)
    ap.add_argument("--downbeats", default=os.environ.get("V7_DOWNBEATS", "/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/downbeats_native.json"),
                    help="path to downbeats_native.json")
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
    ap.add_argument("--drum-inpaint-bars", type=int, nargs="*", default=[],
                    help="masked drum inpaint variants, e.g. 2 4 (central N bars of the window); needs GPU+SA3")
    ap.add_argument("--drum-prompt", default="goa trance drum loop, kick, hi-hats, percussion, no melody")
    ap.add_argument("--drum-cfg", type=float, default=6.0)
    ap.add_argument("--other-slerp", action="store_true", help="also render a latent-slerp `other` variant")
    ap.add_argument("--other-inpaint-bars", type=int, nargs="*", default=[],
                    help="masked inpaint of the `other` stem over the central N bars, e.g. 2 4")
    ap.add_argument("--other-cfg", type=float, default=6.0)
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
    if (not args.no_generate) or args.drum_inpaint_bars or args.other_slerp or args.other_inpaint_bars:
        sys.path.insert(0, "/home/kim/Projects/SAO/eval")
        from stable_audio_3 import StableAudioModel
        print("Initializing SA3 Model...", flush=True)
        sa3_model = StableAudioModel.from_pretrained("medium-base", device="cuda")
        if args.no_generate and args.ckpt_b and hasattr(sa3_model, "load_lora"):
            sa3_model.load_lora([args.ckpt_b])

    dbs = {}
    if args.downbeats and Path(args.downbeats).exists():
        dbs = json.loads(Path(args.downbeats).read_text())
        print(f"Loaded downbeats from {args.downbeats} ({len(dbs)} tracks)", flush=True)

    for i in range(len(clips) - 1):
        cA, cB = clips[i], clips[i + 1]
        print(f"Processing Transition {i + 1}: {cA['id']} -> {cB['id']}", flush=True)
        rec = {"i": i, "a": cA["id"], "b": cB["id"]}
        meta["transitions"].append(rec)

        dbA = np.array(dbs.get(cA["id"], []))
        dbB = np.array(dbs.get(cB["id"], []))

        def get_exact_bpm(db, fallback):
            if len(db) > 2:
                # Linear regression over downbeats for exact bar duration without 10ms detection noise
                slope, _ = np.polyfit(np.arange(len(db)), db, 1)
                return float(240.0 / slope)
            return float(fallback)

        bpm_a = get_exact_bpm(dbA, cA.get("bpm") or args.default_bpm)
        bpm_b = get_exact_bpm(dbB, cB.get("bpm") or args.default_bpm)
        bpm_val = cA.get("bpm")
        rec["bpm_source"] = "order" if bpm_val else ("downbeats" if len(dbA) > 2 else "default")
        rec["bpm_a"] = bpm_a
        rec["bpm_b"] = bpm_b
        rec["bpm"] = bpm_b
        rec["gap_bpm"] = bpm_b - bpm_a

        # 1. Bungee time-stretch outgoing clip A to match B's tempo
        speed = bpm_b / bpm_a
        rec["bungee_speed"] = float(speed)
        sA = stems[cA["id"]]
        if abs(speed - 1.0) >= 0.005:
            print(f"  Bungee stretching outgoing track {cA['id'][:32]} by {speed:.4f} ({bpm_a:.2f} -> {bpm_b:.2f} BPM)...", flush=True)
            sA_eff = {k: dsp.bungee_stretch(sA[k], speed, sr=SR) for k in sA}
            dbA_eff = dbA / speed if len(dbA) else dbA
        else:
            sA_eff = sA
            dbA_eff = dbA

        # 2. Window duration at B's tempo
        W_sec = args.w_bars * 4 * 60 / bpm_b
        L = int(round(W_sec * SR))

        # 3. Downbeat snapping: center transition window on nearest downbeats
        if len(dbA_eff) > 2 and len(dbB) > 2:
            a_target = bounds[cA["id"]]["end_pre_zc"] / speed
            b_target = bounds[cB["id"]]["start"]
            a_db = float(dbA_eff[np.argmin(abs(dbA_eff - a_target))])
            b_db = float(dbB[np.argmin(abs(dbB - b_target))])
            a_lo = int(round(a_db * SR)) - L // 2
            b_lo = int(round(b_db * SR)) - L // 2
        else:
            a_lo = int(round((bounds[cA["id"]]["end_pre_zc"] / speed) * SR)) - L // 2
            b_lo = int(round(bounds[cB["id"]]["start"] * SR)) - L // 2

        sB = stems[cB["id"]]

        def win(s, name, lo):
            return dsp.safe_slice(s[name], lo, lo + L)

        # 4. Kick transient phase alignment over +-1/4 beat
        beat_samples = round(60.0 / bpm_b * SR)
        shift, ncc_b, ncc_0 = dsp.phase_shift(win(sA_eff, "drums", a_lo), win(sB, "drums", b_lo), beat_samples, sr=SR)
        # Note: phase_shift returns s where delaying B by +s samples aligns with A.
        # To delay B within the slice, the slice into B must start earlier: b_lo -= shift.
        b_lo -= shift
        rec["phase_shift_samples"] = int(shift)
        rec["phase_shift_ms"] = float(shift / SR * 1000)
        rec["ncc_best"] = float(ncc_b)
        rec["ncc_zero"] = float(ncc_0)
        print(f"  Kick phase alignment: shift = {rec['phase_shift_ms']:+.2f} ms (NCC: {ncc_0:.3f} -> {ncc_b:.3f})", flush=True)

        bass, ga, gb = dsp.bass_handover(win(sA_eff, "bass", a_lo), win(sB, "bass", b_lo), L // 2,
                                         int(round(SR * args.blend_ms / 1000.0)))
        drums = dsp.drums_crossfade(win(sA_eff, "drums", a_lo), win(sB, "drums", b_lo), SR)
        vocals = dsp.crossfade(win(sA_eff, "vocals", a_lo), win(sB, "vocals", b_lo))
        resid = dsp.crossfade(win(sA_eff, "residual", a_lo), win(sB, "residual", b_lo), kind="linear")
        other_a, other_b = win(sA_eff, "other", a_lo), win(sB, "other", b_lo)
        other_ref = dsp.crossfade(other_a, other_b)          # reference level, and the labelled fallback

        other, other_path = other_ref, "skipped"
        if sa3_model is not None and not args.no_generate:
            try:
                import torch
                target = chroma_morph_target(other_a, other_b)
                
                if hasattr(sa3_model, "generate"):
                    if hasattr(sa3_model, "load_lora"):
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
                    rec["other_path"] = "generative"
                else:
                    from mixtape_v7_generative_inference import dual_latch_guided_generate
                    gen, _ = dual_latch_guided_generate(
                        model=sa3_model, ckpt_a=args.ckpt_a, ckpt_b=args.ckpt_b,
                        prompt_a=args.prompt_a, prompt_b=args.prompt_b, duration=W_sec,
                        chroma_target_tensor=target, chroma_head_path=args.chroma_head,
                        steps=args.steps, seed=args.seed, latch_gain=args.latch_gain)
                    gen = gen.numpy()
                    rec["other_peak"] = dsp.assert_finite(gen, f"transition {i} other")
                    rec["other_len_delta"] = int(gen.shape[-1] - L)
                    gen = np.pad(gen, ((0, 0), (0, max(0, L - gen.shape[-1]))))[:, :L]
                    other, rec["other_gain"] = dsp.match_rms(gen, other_ref)
                    other_path = "generative"
                    rec["other_path"] = other_path
                    trans = (bass + drums + other + vocals + resid).astype(np.float64)
                    rec["peak"] = float(np.abs(trans).max())
                    rec["clipped_if_pcm16"] = bool(rec["peak"] > 1.0)
                    rec["min_bass_power_gain"] = float(np.sqrt(ga ** 2 + gb ** 2).min())
                    name = out_dir / f"v7_smoke_trans_FAST_{i}_{other_path}.wav"
                    sf.write(str(name), trans.T, SR, subtype="FLOAT")
                    rec["file"] = name.name
                    print(f"  wrote {name.name} (peak {rec['peak']:.2f}, other: {other_path})", flush=True)
            except Exception as e:                                # noqa: BLE001
                rec["error"] = repr(e)
                if not args.allow_fallback:
                    rec["other_path"] = "FAILED"
                    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
                    raise
                print(f"Generative inference failed, FALLING BACK to crossfade: {e!r}", flush=True)
                other_path = "fallback_crossfade"
                rec["other_path"] = other_path
                
                trans = (bass + drums + other + vocals + resid).astype(np.float64)
                rec["peak"] = float(np.abs(trans).max())
                rec["clipped_if_pcm16"] = bool(rec["peak"] > 1.0)
                rec["min_bass_power_gain"] = float(np.sqrt(ga ** 2 + gb ** 2).min())
                name = out_dir / f"v7_smoke_trans_FAST_{i}_{other_path}.wav"
                sf.write(str(name), trans.T, SR, subtype="FLOAT")
                rec["file"] = name.name
                print(f"  wrote {name.name} (peak {rec['peak']:.2f}, other: {other_path})", flush=True)
        else:
            rec["other_path"] = other_path
            # (drums_variant, other_variant) renders; baseline first
            variants = [("xfade", "skipped", drums, other)]
            if sa3_model is not None:
                other_sl = other
                if args.other_slerp:
                    other_sl = latent_slerp_other(sa3_model, other_a, other_b, L)
                    other_sl, _ = dsp.match_rms(other_sl, other_ref)
                    variants.append(("xfade", "slerp", drums, other_sl))
                for nb in args.drum_inpaint_bars:
                    dr_in = drum_inpaint(sa3_model, drums, nb, bpm_b, L, args)
                    variants.append((f"inpaint{nb}bar", "skipped", dr_in, other))
                    if args.other_slerp:
                        variants.append((f"inpaint{nb}bar", "slerp", dr_in, other_sl))
                    for ob in args.other_inpaint_bars:
                        ot_in = drum_inpaint(sa3_model, other_ref, ob, bpm_b, L, args,
                                             prompt=args.prompt_b, cfg=args.other_cfg)
                        ot_in, _ = dsp.match_rms(ot_in, other_ref)
                        variants.append((f"inpaint{nb}bar", f"inpaint{ob}bar", dr_in, ot_in))
                if not args.drum_inpaint_bars:
                    for ob in args.other_inpaint_bars:
                        ot_in = drum_inpaint(sa3_model, other_ref, ob, bpm_b, L, args,
                                             prompt=args.prompt_b, cfg=args.other_cfg)
                        ot_in, _ = dsp.match_rms(ot_in, other_ref)
                        variants.append(("xfade", f"inpaint{ob}bar", drums, ot_in))
            rec["variants"] = []
            for dn, on, d_, o_ in variants:
                trans = (bass + d_ + o_ + vocals + resid).astype(np.float64)
                v = {"drums": dn, "other": on, "peak": float(np.abs(trans).max())}
                v["clipped_if_pcm16"] = bool(v["peak"] > 1.0)
                fname = (f"v7_smoke_trans_FAST_{i}_skipped.wav" if (dn, on) == ("xfade", "skipped")
                         else f"v7_smoke_trans_FAST_{i}_d-{dn}_o-{on}.wav")
                name = out_dir / fname
                sf.write(str(name), trans.T, SR, subtype="FLOAT")
                v["file"] = name.name
                rec["variants"].append(v)
                print(f"  wrote {name.name} (peak {v['peak']:.2f})", flush=True)
            rec["peak"] = rec["variants"][0]["peak"]
            rec["clipped_if_pcm16"] = rec["variants"][0]["clipped_if_pcm16"]
            rec["min_bass_power_gain"] = float(np.sqrt(ga ** 2 + gb ** 2).min())
            rec["file"] = rec["variants"][0]["file"]

    meta["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
    print(f"Done. {len(meta['transitions'])} transitions and run_meta.json in {out_dir}", flush=True)


if __name__ == "__main__":
    main()
