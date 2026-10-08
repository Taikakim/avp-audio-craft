#!/usr/bin/env python
"""render_v7_smoketest.py -- 4-stem v7 transition smoke test, pre-computed stems.

Replaces render_v7_4track_smoketest_fast.py (and the copies in ..._FULL.py / ..._FULL2.py) with the
review fixes by KUANG 2026-10-08 (see antigravity.kuang.log). Same job, same stems, same windows:
  * the DSP layers live in mixtape_v7_dsp.py and are unit-tested;
  * a failed or non-finite generation STOPS the run (--allow-fallback restores the old
    behaviour) and the file name says which path produced the `other` layer;
  * run_meta.json is written per run (spec R0.6 / section 5 item 12);
  * --no-generate renders everything except the generative `other` layer, with no GPU,
    no SA3 and no mir-same-chroma, so the DSP can be auditioned and tested anywhere;
  * Phase 0 (8a72197): A is Bungee-stretched to B's tempo, windows snap to downbeats, B is kick-aligned. After EACH of
    those steps the result is MEASURED on the audio (stretch vs the scaled beat map, A vs B kick grid, generated layer vs
    the real onsets) because a beat/downbeat map is only valid for the audio it was made on.
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

import mixtape_v7_dsp as dsp

SR = 44100
STEM_NAMES = ["drums", "bass", "other", "vocals", "residual"]   # residual = mix - sum(stems) (spec S4)
KICK_FC = 150.0                                                  # spec: kick = drums below 150 Hz

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
ENV_DOWNBEATS = "V7_DOWNBEATS"      # optional: downbeats_native.json of the Phase 0 run (8a72197 hard-coded a drive path here)
ENV_BUNGEE = "V7_BUNGEE_PY"         # optional: the interpreter that has bungee_python


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


class SyncError(RuntimeError):
    """A sync check failed under --require-sync. Never swallowed by --allow-fallback."""


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--order", default=os.environ.get(ENV["order"]), help=f"order_used.json (env {ENV['order']})")
    ap.add_argument("--stems-dir", default=os.environ.get(ENV["stems_dir"]), help=f"env {ENV['stems_dir']}")
    ap.add_argument("--bounds", default=D_BOUNDS)
    ap.add_argument("--downbeats", default=os.environ.get(ENV_DOWNBEATS),
                    help=f"downbeats_native.json: {{clip id: [downbeat seconds]}}. Gives each clip's tempo and snaps the "
                         f"windows to downbeats; without it the order file's bpm and the bounds are used. env {ENV_DOWNBEATS}")
    ap.add_argument("--bungee-python", default=os.environ.get(ENV_BUNGEE),
                    help=f"interpreter that has bungee_python (default: dsp.MIR_BUNGEE_PY). env {ENV_BUNGEE}")
    ap.add_argument("--no-stretch", action="store_true",
                    help="do not stretch A to B's tempo (e.g. on a machine without Bungee). The gap is recorded and the "
                         "A-vs-B sync check then fails for any real tempo gap")
    ap.add_argument("--map-tol-ms", type=float, default=8.0,
                    help="after a stretch, the stretched audio's kick onsets must sit within this of the scaled beat map; "
                         "beyond it the stretched stems are shifted to match and the result is re-measured")
    ap.add_argument("--max-stretch-shift-ms", type=float, default=100.0,
                    help="the largest stretcher latency the kick check will correct (about 1/4 beat at 140 BPM). Beyond it "
                         "the offset is ambiguous modulo the beat, so it is reported as unverified instead of corrected")
    ap.add_argument("--phase-span", type=float, default=0.25,
                    help="kick phase alignment searches +-this fraction of a beat (spec R0.3: 0.25)")
    ap.add_argument("--out-dir", default=os.environ.get(ENV["out_dir"]), help=f"env {ENV['out_dir']}")
    ap.add_argument("--clips", default="2:6", help="slice of the order list, start:stop (default 2:6 = clips 2..5)")
    ap.add_argument("--w-bars", type=int, default=8,
                    help="window length in bars. 8, not 9: the window is centred on the boundary, so an even "
                         "count puts both edges on bar lines (spec R0.4 wants 12 or 16 for the real mix)")
    ap.add_argument("--default-bpm", type=float, default=140.0, help="used, and logged, only if a clip has no 'bpm'")
    ap.add_argument("--blend-ms", type=float, default=50.0, help="bass hand-over blend (spec: <= 50 ms)")
    ap.add_argument("--kick-ramp", choices=("auto", "equal_power", "linear"), default="auto",
                    help="kick-band crossfade. Linear is right ONLY when both kicks share one grid (they add coherently: "
                         "the baseline Kim accepted on 2026-10-08 used it after Phase 0); on kicks that are not aligned it digs "
                         "a -2.9 dB hole, and equal-power on aligned kicks swells the low end +3 dB. auto = linear when the "
                         "A-vs-B sync check passes for that transition, equal-power when it does not (recorded as kick_ramp_used)")
    ap.add_argument("--drum-split", choices=("zero_phase", "lr4"), default="zero_phase",
                    help="how the drums are split into kick / percussion. zero_phase adds back to the drums exactly (spec S4). "
                         "lr4 is the causal split of the first patch that the accepted 2026-10-08 baseline used (its recombination "
                         "differs from the drums by +2.6 dB); use it to reproduce that baseline bit for bit")
    ap.add_argument("--no-generate", action="store_true", help="skip the model: `other` = plain crossfade, labelled so")
    ap.add_argument("--allow-fallback", action="store_true",
                    help="if generation fails, continue with the plain crossfade (labelled in the file name and meta)")
    ap.add_argument("--other-mode", choices=("lora_latch", "base_a2a"), default="lora_latch",
                    help="how `other` is generated, both as a single-pass audio-to-audio refine of the real crossfade. "
                         "lora_latch: adapter --ckpt-b plus the LatCH chroma head steering toward the morph target "
                         "(what 1307106 does). base_a2a: the base model alone, no adapter, no head, no sa3_control; "
                         "the fallback that runs wherever the base weights are")
    ap.add_argument("--model", default="medium-base", help="model name for StableAudioModel.from_pretrained")
    ap.add_argument("--device", default="cuda", help="cuda, xpu or cpu")
    ap.add_argument("--precision", choices=("auto", "fp16", "fp32"), default="auto",
                    help="weights precision. auto = fp16 on cuda, fp32 elsewhere (measured on this laptop: fp16/bf16 give "
                         "NaN on the Arc XPU for medium-class models)")
    ap.add_argument("--cfg-scale", type=float, default=6.0, help="a base model wants cfg > 1 (demos use 2-7); 6.0 is the proven chroma_morph value")
    ap.add_argument("--sync-tol-ms", type=float, default=25.0,
                    help="A and B kick grids must agree within this at every bar (the spec's R0.3 residual search is +-1/4 beat)")
    ap.add_argument("--gen-lag-tol-ms", type=float, default=12.0,
                    help="the generated `other` may sit this far from the onsets of the real crossfade it started from")
    ap.add_argument("--require-sync", action="store_true",
                    help="make the two sync checks fatal (default: record in run_meta.json and print a WARNING)")
    ap.add_argument("--noise-schedule", choices=("sine", "flat"), default="sine",
                    help="sine = noise 0 at the window edges, the noise level at the midpoint, 0 at the end "
                         "(per latent frame, the sinesweep callback of chroma_morph_transitions.py); flat = constant")
    ap.add_argument("--noise-levels", default="0.5,0.6,0.7",
                    help="comma list; one output per level. The PEAK of the sine schedule (midpoint), or the constant "
                         "level with --noise-schedule flat")
    ap.add_argument("--a2a-prompt", default="goa trance, psytrance, rolling bassline", help="base_a2a prompt (lora_latch uses --prompt-b)")
    ap.add_argument("--chunked-decode", action="store_true", help="decode in chunks to cut peak VRAM")
    ap.add_argument("--sample-pad-sec", type=float, default=None,
                    help="pass sample_size=(window + this) s to generate, as 1307106 did with 8; default: the model's auto window")
    ap.add_argument("--edge-bars", type=float, default=1.0,
                    help="generated `other` fades in from / out to the real crossfade over this many bars at each end "
                         "(spec R0.5: >= 1), so the window starts and ends as the untouched clips do")
    ap.add_argument("--drum-inpaint-bars", type=int, nargs="*", default=[],
                    help="masked drum inpaint variants, e.g. 2 4: the central N bars of the (aligned, crossfaded) drum window "
                         "are regenerated, the real drums are the context on both sides. Needs the base weights (no adapter)")
    ap.add_argument("--drum-prompt", default="goa trance drum loop, kick, hi-hats, percussion, no melody")
    ap.add_argument("--drum-cfg", type=float, default=6.0)
    ap.add_argument("--inpaint-grid-tol-ms", type=float, default=30.0,
                    help="an inpainted span's kicks must sit within this of the grid of the real kicks around it (vintage goa "
                         "has 10-20 ms of jitter and swing in the data, so a metronome tolerance would be wrong)")
    ap.add_argument("--other-slerp", action="store_true", help="also render a latent-slerp `other` variant")
    ap.add_argument("--other-inpaint-bars", type=int, nargs="*", default=[],
                    help="masked inpaint of the `other` stem over the central N bars, e.g. 2 4 (9c0ddd1); prompt --prompt-b, cfg --other-cfg")
    ap.add_argument("--other-cfg", type=float, default=6.0)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--latch-gain", type=float, default=2048.0)
    ap.add_argument("--ckpt-a", default=os.environ.get(ENV["ckpt_a"]),
                    help=f"unused since 1307106 (single adapter); kept so existing command lines still parse. env {ENV['ckpt_a']}")
    ap.add_argument("--ckpt-b", default=os.environ.get(ENV["ckpt_b"]), help=f"lora_latch adapter. env {ENV['ckpt_b']}")
    ap.add_argument("--chroma-head", default=os.environ.get(ENV["chroma_head"]), help=f"lora_latch. env {ENV['chroma_head']}")
    ap.add_argument("--prompt-a", default="aggressive upbeat goa trance", help="unused since 1307106")
    ap.add_argument("--prompt-b", default="driving pulsating psytrance", help="lora_latch prompt")
    args = ap.parse_args(argv)
    try:
        args.noise_levels = [float(v) for v in str(args.noise_levels).split(",") if v.strip()]
        assert args.noise_levels and all(0.0 < v <= 1.0 for v in args.noise_levels)
    except (ValueError, AssertionError):
        ap.error("--noise-levels must be a comma list of numbers in (0, 1]")
    lora = not args.no_generate and args.other_mode == "lora_latch"
    need = ["order", "stems_dir", "out_dir"] + (["ckpt_b", "chroma_head"] if lora else [])
    missing = [f"--{n.replace('_', '-')} (or ${ENV[n]})" for n in need if not getattr(args, n)]
    if missing:
        ap.error("missing: " + ", ".join(missing))
    return args


def add_drum_bands(clip, split="zero_phase"):
    """Split the WHOLE drums stem once, slice windows afterwards. zero_phase: low + high == drums exactly. lr4: the causal
    split of the first patch (the accepted 2026-10-08 baseline). Do this AFTER any stretch: stretching the two bands
    separately would not add back up to the stretched drums."""
    drums = clip["drums"].astype(np.float64)
    clip["drums_lo"], clip["drums_hi"] = (dsp.split_zero_phase(drums, KICK_FC, SR) if split == "zero_phase"
                                          else dsp.lr4_split(drums, KICK_FC, SR))
    return clip


def load_stems(stems_dir, idx, split="zero_phase"):
    d = Path(stems_dir) / f"{idx:02d}"
    out = {}
    for n in STEM_NAMES:
        x, sr = sf.read(str(d / f"{n}.wav"), dtype="float32")
        if sr != SR:
            raise ValueError(f"{d / (n + '.wav')}: sample rate {sr}, expected {SR}")
        out[n] = (x.T if x.ndim == 2 else x[None, :])
    return add_drum_bands(out, split)


def clip_tempo(downbeats, clip, default_bpm):
    """(bpm, source): from the downbeat map if there is one, else the order file, else the default. The fit is a
    least-squares slope through ALL downbeats (dsp.fit_bpm), not the median bar interval: madmom quantises bar intervals
    to 10 ms and the resulting 0.4 % ratio error was the hi-hat gallop (ANTIGRAVITY, 2026-10-08)."""
    if len(downbeats) > 2:
        return dsp.fit_bpm(downbeats), "downbeats"
    if clip.get("bpm"):
        return float(clip["bpm"]), "order"
    return float(default_bpm), "default"


def stretch_clip(raw, downbeats, speed, args, rec):
    """Bungee-stretch every stem of the outgoing clip A by `speed` (A's tempo -> B's) and make sure the maps still describe
    the audio. Returns (stretched clip incl. drum bands, downbeats on the stretched audio).

    Two checks, both on the audio: (1) each stem has the length speed implies (a stretcher that returns a truncated or
    wrong-length result must stop the run); (2) the stretched drums' kick onsets are compared with the ORIGINAL onsets
    scaled by 1/speed. The scaled map is only a prediction: a stretcher with latency puts every beat late, and a window
    snapped to the scaled downbeats would then be off by that latency. If the median offset exceeds --map-tol-ms the
    stretched stems are shifted to match and re-measured; if it cannot be verified under --require-sync, stop."""
    out = {}
    for n in STEM_NAMES:
        y = dsp.bungee_stretch(raw[n], speed, SR, python=args.bungee_python)
        expect = raw[n].shape[-1] / speed
        if abs(y.shape[-1] - expect) > 0.01 * expect:
            raise RuntimeError(f"bungee returned {y.shape[-1]} samples for {raw[n].shape[-1]} at speed {speed:.4f} "
                               f"(expected about {expect:.0f}) on stem {n}")
        out[n] = y
    predicted = dsp.kick_onsets(raw["drums"], SR) / speed
    _, off = dsp.grid_offsets_ms(predicted, dsp.kick_onsets(out["drums"], SR))
    lat = float(np.median(off)) if off.size else None
    rec["stretch_map_offset_ms"] = None if lat is None else round(lat, 1)
    shift = 0
    verified = lat is not None and abs(lat) <= args.map_tol_ms
    if lat is not None and not verified and abs(lat) > args.max_stretch_shift_ms:
        # Kicks repeat every beat, so a kick-grid offset is only known modulo the beat (wrapped to +-half an inter-onset
        # interval): 300 ms of latency reads as -111 ms at 146 BPM. Correcting by the wrong beat would pass every later
        # kick check while leaving the downbeat map a whole beat out. Past a plausible latency, refuse to guess.
        print(f"  WARNING stretch offset {lat:+.1f} ms is larger than a plausible stretcher latency "
              f"({args.max_stretch_shift_ms:g} ms): a kick grid cannot tell it from a whole-beat shift, NOT corrected", flush=True)
    elif lat is not None and not verified:
        shift = -int(round(lat / 1000.0 * SR))                   # lat > 0: stretched audio is LATE, so advance it
        out = {n: dsp.shift_samples(v, shift) for n, v in out.items()}
        _, off2 = dsp.grid_offsets_ms(predicted, dsp.kick_onsets(out["drums"], SR))
        after = float(np.median(off2)) if off2.size else None
        rec["stretch_map_offset_after_ms"] = None if after is None else round(after, 1)
        verified = after is not None and abs(after) <= args.map_tol_ms
        print(f"  Stretch moved the beats {lat:+.1f} ms from the scaled map; shifted the stems by {shift} samples, "
              f"now {after if after is None else round(after, 1)} ms", flush=True)
    rec["stretch_map_verified"] = bool(verified)
    if not verified:
        print(f"  WARNING the stretched audio could not be verified against the beat map (offset {lat} ms, "
              f"tolerance {args.map_tol_ms})", flush=True)
        if args.require_sync:
            raise SyncError(f"stretch of {rec.get('a')}: beat map not verified (offset {lat} ms)")
    # The map is the scaled prediction. When the stems had to be shifted, they were moved ONTO that prediction, so the
    # map stays as it is; adding the shift would move it away from the corrected audio (a test pins this with the
    # kick alignment off, because the alignment would otherwise hide a stale map).
    db_eff = downbeats / speed if len(downbeats) else downbeats
    return add_drum_bands(out, args.drum_split), db_eff


def sine_depth(frames, peak):
    """Per-latent-frame noise depth: 0 at the first frame, `peak` at the midpoint, 0 at the last."""
    import torch
    return peak * torch.sin(torch.linspace(0.0, math.pi, frames))


def sine_hold_callback(z_ref, depth, eps):
    """Sampler callback that makes the per-frame depth real. Ported from the `sinesweep` mode of
    chroma_morph_transitions.py: the sampler starts every frame at the PEAK noise level, and a frame whose own depth
    is lower is held on the reference trajectory x_t = (1-t) z_ref + t eps until the global t falls to that depth;
    only then does the model denoise it. Frames at the window edges (depth 0) are never released, so they come out
    as the reference; the middle is re-generated most.

    z_ref, depth, eps: (1, C, T), (1, 1, T), (1, C, T) on the cpu. The callback edits x in place."""
    import torch

    def cb(d):
        x = d["x"]
        tt = float(torch.as_tensor(d["t"]).reshape(-1)[0])
        n = min(x.shape[-1], z_ref.shape[-1])
        hold = depth[..., :n] < tt                       # not yet released
        ref_t = ((1.0 - tt) * z_ref[..., :n] + tt * eps[..., :n]).to(x.device, x.dtype)
        x[..., :n].copy_(torch.where(hold.to(x.device), ref_t, x[..., :n]))

    return cb


def generate_sine_a2a(model, other_ref, duration, args, nl, target=None):
    """Single-pass audio-to-audio refine of the plain crossfade of the two real `other` windows.

    The crossfade is the init audio. The noise level follows --noise-schedule: sine = 0 at the window edges, `nl` at
    the midpoint, 0 again at the end (sine_hold_callback); flat = one constant `nl`. With `target` (the (1, 384, T)
    chroma morph target) the LatCH head at --chroma-head steers the refine, as chroma_morph_transitions.py does
    (rho = mu = --latch-gain, off after 60 % of the steps); without it this is the base model alone, which needs no
    adapter, no head and no sa3_control. Returns (C, N) float32 numpy."""
    import torch
    lora = target is not None
    kw = dict(
        prompt=args.prompt_b if lora else args.a2a_prompt, duration=duration, steps=args.steps,
        cfg_scale=args.cfg_scale, seed=args.seed, batch_size=1,
        init_audio=(SR, torch.tensor(np.asarray(other_ref), dtype=torch.float32)),
        init_noise_level=nl,                             # sine: the PEAK, where the sampler starts
        chunked_decode=True if args.chunked_decode else None)
    if args.sample_pad_sec is not None:                  # 1307106 used (duration + 8) s; default = the model's own auto window
        kw["sample_size"] = int((duration + args.sample_pad_sec) * SR)
    if lora:
        kw["latch_configs"] = [{"model_path": args.chroma_head, "target_raw": target, "weight": 1.0, "end_pct": 0.6}]
        kw["latch_hparams"] = {"rho": args.latch_gain, "mu": args.latch_gain}
    if args.noise_schedule == "sine":
        pre = model.model.pretransform
        p = next(pre.parameters())
        # END-pad to whole frames first: the encoder crops the front of any other length, which put the held frames of the
        # sine schedule up to 93 ms out of time with the audio the sampler uses (measured: -75.1 ms at N mod 4096 = 3314).
        ref_p = dsp.pad_end_to_frame(np.asarray(other_ref), pre.downsampling_ratio)
        with torch.inference_mode():
            z_ref = pre.encode(torch.tensor(ref_p, device=p.device, dtype=p.dtype).unsqueeze(0)).float().cpu()
        depth = sine_depth(z_ref.shape[-1], nl).view(1, 1, -1)
        eps = torch.randn(z_ref.shape, generator=torch.Generator().manual_seed(4242))
        kw["callback"] = sine_hold_callback(z_ref, depth, eps)
    out = model.generate(**kw)
    return out[0].float().cpu().numpy()


def generated_layer_lag(gen, ref, bar, w_bars):
    """Median per-bar onset lag (ms) of a generated layer against the real crossfade it started from, trusted only on the
    bars where the two share onsets (correlation >= 0.2). None if no bar qualifies."""
    lags = []
    for k in range(w_bars):
        sl = slice(k * bar, (k + 1) * bar)
        if gen[:, sl].shape[-1] == bar:
            lag, corr = dsp.onset_lag_ms(gen[:, sl], ref[:, sl], SR)
            if corr >= 0.2:
                lags.append(lag)
    return round(float(np.median(lags)), 1) if lags else None


def latent_slerp_other(model, other_a, other_b, L):
    """Latent crossfade of the `other` stem (ported from 799b349): encode both windows, slerp across the whole window,
    decode. No generation, so no hallucination, and no time-domain comb filtering between the two. Frames are 4096 samples
    wide, so the interpolation is only as good as the A/B alignment that Phase 0 achieved. Returns (C, L) float32."""
    import torch
    from stable_audio_3.inference.longform import slerp
    pre = model.model.pretransform
    p = next(pre.parameters())
    ratio = pre.downsampling_ratio                        # end-pad to whole frames: see dsp.pad_end_to_frame
    other_a, other_b = dsp.pad_end_to_frame(np.asarray(other_a), ratio), dsp.pad_end_to_frame(np.asarray(other_b), ratio)
    with torch.inference_mode():
        za = pre.encode(torch.tensor(other_a, device=p.device, dtype=p.dtype).unsqueeze(0)).float()
        zb = pre.encode(torch.tensor(other_b, device=p.device, dtype=p.dtype).unsqueeze(0)).float()
        n = min(za.shape[-1], zb.shape[-1])
        t = torch.linspace(0, 1, n, device=za.device).view(1, 1, -1)
        z = slerp(za[..., :n], zb[..., :n], t)
        out = pre.decode(z.to(p.dtype))[0].float().cpu().numpy()
    return np.pad(out, ((0, 0), (0, max(0, L - out.shape[-1]))))[:, :L]


def drum_inpaint(model, drums_xf, n_bars, bpm, L, args, prompt=None, cfg=None):
    """Masked inpaint of the central n_bars of a stem window (ported from 799b349; 9c0ddd1 reuses it for `other`). The real
    audio is the context on both sides; only the masked span comes from the generation (50 ms edge fades). Runs on whatever
    weights the model holds: the base model unless a lora_latch run has loaded the adapter. Returns (audio, lo_s, hi_s)."""
    import torch
    W_sec = L / SR
    bar = 240.0 / bpm
    lo = W_sec / 2 - n_bars * bar / 2
    hi = lo + n_bars * bar
    kw = dict(prompt=prompt or args.drum_prompt, duration=W_sec, steps=args.steps, cfg_scale=cfg or args.drum_cfg, seed=args.seed, batch_size=1,
              inpaint_audio=(SR, torch.tensor(drums_xf, dtype=torch.float32)),
              inpaint_mask_start_seconds=float(lo), inpaint_mask_end_seconds=float(hi),
              chunked_decode=True if args.chunked_decode else None)
    if args.sample_pad_sec is not None:
        kw["sample_size"] = int((W_sec + args.sample_pad_sec) * SR)
    gen = model.generate(**kw)[0].float().cpu().numpy()
    dsp.assert_finite(gen, f"inpaint {n_bars} bar")
    gen = np.pad(gen, ((0, 0), (0, max(0, L - gen.shape[-1]))))[:, :L]
    gen, _ = dsp.match_rms(gen, drums_xf)
    i0, i1 = int(lo * SR), int(hi * SR)
    f = int(0.05 * SR)
    w = np.zeros(L, dtype=np.float32)
    w[i0:i1] = 1.0
    w = np.convolve(w, np.hanning(2 * f + 1) / np.hanning(2 * f + 1).sum(), mode="same").astype(np.float32)
    return drums_xf * (1 - w) + gen * w, lo, hi


def inpaint_grid_check(drums_xf, drums_in, lo, hi, bpm, tol_ms):
    """The plan's own timing check, automated: did the generated bridge keep the kick grid of the real drums around it?
    The grid is fitted to the kicks OUTSIDE the mask; the kicks INSIDE it (minus the 50 ms fades) are compared with it.
    Returns a record with the residuals; ok is False if the span has no kicks at all (a silent bridge), fewer than 75 % of the
    expected kicks, or any kick beyond max(tolerance, 1.5 x the real kicks' own maximum deviation)."""
    ref = dsp.kick_onsets(drums_xf, SR)
    ref = ref[(ref < lo) | (ref > hi)]
    test = dsp.kick_onsets(drums_in, SR)
    test = test[(test > lo + 0.05) & (test < hi - 0.05)]
    res = dsp.grid_residuals_ms(ref, test, 60.0 / bpm)
    rec = {"kicks_in_span": int(len(test)), "expected_kicks": int(round((hi - lo) / (60.0 / bpm)))}
    # What the REAL kicks do in the same span: the natural jitter and swing of the material (vintage goa: 10-20 ms). A generated
    # bridge is only as bad as it exceeds this, so it is recorded next to the verdict.
    real = dsp.kick_onsets(drums_xf, SR)
    real = dsp.grid_residuals_ms(ref, real[(real > lo + 0.05) & (real < hi - 0.05)], 60.0 / bpm)
    if real.size:
        rec["real_max_abs_ms"] = round(float(np.abs(real).max()), 1)
        rec["real_median_abs_ms"] = round(float(np.median(np.abs(real))), 1)
    if res.size == 0:
        return dict(rec, ok=False, why="no kicks in the masked span" if len(test) == 0 else "no real kicks to fit a grid to")
    # The limit is relative to the real material: on the Arc the REAL kicks in the same span deviated by max 35-42 ms (median
    # 30-33), so a flat 30 ms would fail the real thing. 1.5 x the real maximum, never below the flat tolerance.
    limit = max(tol_ms, 1.5 * rec.get("real_max_abs_ms", 0.0))
    return dict(rec, max_abs_ms=round(float(np.abs(res).max()), 1), median_abs_ms=round(float(np.median(np.abs(res))), 1),
                limit_ms=round(float(limit), 1), ok=bool(np.abs(res).max() <= limit and len(test) >= 0.75 * rec["expected_kicks"]))


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
        stems[c["id"]] = load_stems(args.stems_dir, all_clips.index(c), args.drum_split)
        print(f"Loaded stems for {c['id']}", flush=True)
    dbs = {}
    if args.downbeats and Path(args.downbeats).exists():
        dbs = json.loads(Path(args.downbeats).read_text())
        print(f"Loaded downbeats for {len(dbs)} clips from {args.downbeats}", flush=True)

    sa3_model = None
    generating = not args.no_generate                          # the generative `other` layer
    variants_wanted = bool(args.other_slerp or args.drum_inpaint_bars or args.other_inpaint_bars)
    if generating or variants_wanted:
        from stable_audio_3 import StableAudioModel
        half = args.precision == "fp16" or (args.precision == "auto" and args.device.startswith("cuda"))
        print(f"Initializing SA3 model {args.model} on {args.device}, {'fp16' if half else 'fp32'} ({args.other_mode})...", flush=True)
        sa3_model = StableAudioModel.from_pretrained(args.model, device=args.device, model_half=half)
        if generating and args.other_mode == "lora_latch":
            # ONCE per run: 1307106 loaded it again on every transition. Note a live adapter is the 13e fault
            # condition on the ROCm box (training-findings 13e): the finite guards below make a hit visible.
            sa3_model.load_lora([args.ckpt_b])

    for i in range(len(clips) - 1):
        cA, cB = clips[i], clips[i + 1]
        print(f"Processing Transition {i + 1}: {cA['id']} -> {cB['id']}", flush=True)
        rec = {"i": i, "a": cA["id"], "b": cB["id"]}
        meta["transitions"].append(rec)

        dbA = np.array(dbs.get(cA["id"], []), dtype=float)
        dbB = np.array(dbs.get(cB["id"], []), dtype=float)
        bpm_a, rec["bpm_source"] = clip_tempo(dbA, cA, args.default_bpm)
        bpm_b, rec["bpm_source_b"] = clip_tempo(dbB, cB, args.default_bpm)
        bpm = bpm_b                                           # the window runs at B's tempo
        rec.update(bpm=bpm_b, bpm_a=bpm_a, bpm_b=bpm_b, gap_bpm=bpm_b - bpm_a)

        # PHASE 0 step 1: stretch the OUTGOING clip A to B's tempo (B is never stretched; R0.2).
        speed = bpm_b / bpm_a
        rec["bungee_speed"] = float(speed)
        rec["stretch_within_spec"] = bool(abs(bpm_b - bpm_a) <= 5.0 and abs(speed - 1.0) <= 0.06)
        if not rec["stretch_within_spec"]:
            print(f"  WARNING tempo gap {bpm_b - bpm_a:+.1f} BPM, stretch x{speed:.3f}: the spec says to fix the ORDER "
                  f"(gap <= 5 BPM, factor within 6 %), not to stretch harder (R0.2)", flush=True)
        sA, sB = stems[cA["id"]], stems[cB["id"]]
        dbA_eff, rec["stretched"] = dbA, False
        if abs(speed - 1.0) >= 0.005:
            if args.no_stretch:
                print(f"  --no-stretch: A stays at {bpm_a:.2f} BPM, B at {bpm_b:.2f}; the kick grids WILL drift", flush=True)
            else:
                print(f"  Bungee stretching outgoing clip {cA['id'][:32]} x{speed:.4f} ({bpm_a:.2f} -> {bpm_b:.2f} BPM)...", flush=True)
                try:
                    sA, dbA_eff = stretch_clip(sA, dbA, speed, args, rec)
                except Exception as e:                        # noqa: BLE001  (SyncError, wrong length, Bungee missing)
                    rec["error"] = repr(e)
                    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
                    raise
                rec["stretched"] = True

        W_sec = args.w_bars * 4 * 60 / bpm_b
        L = int(round(W_sec * SR))
        scale = speed if rec["stretched"] else 1.0            # the bounds are in A's ORIGINAL time base
        # PHASE 0 step 2: centre both windows on downbeats of the audio they will be cut from (dbA_eff is on the
        # stretched time base). One seconds->samples conversion each; both windows have length L by construction.
        if len(dbA_eff) > 2 and len(dbB) > 2:
            a_db = float(dbA_eff[np.argmin(np.abs(dbA_eff - bounds[cA["id"]]["end_pre_zc"] / scale))])
            b_db = float(dbB[np.argmin(np.abs(dbB - bounds[cB["id"]]["start"]))])
            rec["snapped_to_downbeats"] = True
        else:
            a_db, b_db = bounds[cA["id"]]["end_pre_zc"] / scale, bounds[cB["id"]]["start"]
            rec["snapped_to_downbeats"] = False
        a_lo = int(round(a_db * SR)) - L // 2
        b_lo = int(round(b_db * SR)) - L // 2

        def win(s, name, lo):
            return dsp.safe_slice(s[name], lo, lo + L)

        # PHASE 0 step 3: kick-envelope phase alignment. phase_shift returns the delay to apply to B (> 0 = B is early);
        # a window START moves the other way: b_lo -= shift. (8a72197 added it; the sign is pinned by a test.)
        shift, ncc_b, ncc_0 = dsp.phase_shift(win(sA, "drums", a_lo), win(sB, "drums", b_lo),
                                              round(60.0 / bpm_b * SR), sr=SR, span=args.phase_span)
        b_lo -= shift
        rec.update(phase_shift_samples=int(shift), phase_shift_ms=float(shift / SR * 1000), ncc_best=ncc_b, ncc_zero=ncc_0)
        print(f"  Kick phase alignment: shift = {rec['phase_shift_ms']:+.2f} ms (NCC {ncc_0:.3f} -> {ncc_b:.3f})", flush=True)

        bar = int(round(4 * 60 / bpm * SR))

        # SYNC CHECK 1 (after the stretch, the snap and the alignment, before the layers are built and anything is
        # generated): are A and B on ONE kick grid inside the window? Measured on the audio the window is actually cut
        # from, because a stored beat/downbeat map is only valid for the audio it was made on. Per bar (a phase error)
        # AND as a drift over the window (a tempo-ratio error: 3.99 ms/s was the hi-hat gallop of 2026-10-08, invisible
        # in a per-bar median over 4 bars but 56 ms over 14 s). If they are not on one grid (--no-stretch, a gap too big
        # to stretch, an alignment beyond +-phase-span), the a2a bakes the offset in: it starts from the crossfade of
        # two misaligned grids.
        ta, off = dsp.grid_offsets_ms(dsp.kick_onsets(win(sA, "drums", a_lo), SR), dsp.kick_onsets(win(sB, "drums", b_lo), SR))
        per_bar = []
        for k in range(args.w_bars):
            sel = (ta >= k * bar / SR) & (ta < (k + 1) * bar / SR)
            per_bar.append(float(np.median(off[sel])) if sel.any() else None)
        drift = dsp.drift_ms_per_s(ta, off)
        rec["ab_kick_offsets_ms"] = [None if v is None else round(v, 1) for v in per_bar]
        rec["ab_drift_ms_per_s"] = round(drift, 2)
        rec["ab_grid_synced"], rec["ab_outlier_bars"] = dsp.grid_verdict(per_bar, drift, W_sec, args.sync_tol_ms)
        if rec["ab_outlier_bars"] and rec["ab_grid_synced"]:
            print(f"  note: bar(s) {rec['ab_outlier_bars']} of {args.w_bars} are off the grid (a fill or a break?), the rest agree; "
                  f"offsets {rec['ab_kick_offsets_ms']}", flush=True)
        if not rec["ab_grid_synced"]:
            print(f"  WARNING clips {cA['id']} -> {cB['id']} are NOT on one kick grid (B re A per bar, ms: "
                  f"{rec['ab_kick_offsets_ms']}, drift {drift:+.2f} ms/s = {drift * W_sec:+.0f} ms over the window, tolerance "
                  f"{args.sync_tol_ms}) even after {'the stretch and ' if rec['stretched'] else ''}the kick alignment "
                  f"({rec['phase_shift_ms']:+.1f} ms)", flush=True)
            if args.require_sync:
                rec["error"] = "ab grid not synced"
                (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
                raise SyncError(f"transition {i}: A and B kick grids differ by {rec['ab_kick_offsets_ms']} ms per bar, "
                                f"drift {drift:+.2f} ms/s")

        bass, ga, gb = dsp.bass_handover(win(sA, "bass", a_lo), win(sB, "bass", b_lo), L // 2,
                                         int(round(SR * args.blend_ms / 1000.0)))
        # The kick band crossfades linearly ONLY when the two kicks share a grid (coherent sum); otherwise equal-power.
        ramp = args.kick_ramp if args.kick_ramp != "auto" else ("linear" if rec["ab_grid_synced"] else "equal_power")
        rec["kick_ramp_used"] = ramp
        drums = dsp.drums_crossfade(win(sA, "drums_lo", a_lo), win(sA, "drums_hi", a_lo),
                                    win(sB, "drums_lo", b_lo), win(sB, "drums_hi", b_lo), kick=ramp)
        vocals = dsp.crossfade(win(sA, "vocals", a_lo), win(sB, "vocals", b_lo))
        resid = dsp.crossfade(win(sA, "residual", a_lo), win(sB, "residual", b_lo), kind="linear")
        other_a, other_b = win(sA, "other", a_lo), win(sB, "other", b_lo)
        other_ref = dsp.crossfade(other_a, other_b)          # reference level, and the labelled fallback

        rec["min_bass_power_gain"] = float(np.sqrt(ga ** 2 + gb ** 2).min())
        rec["outputs"] = []                                   # one entry per file written for this transition

        def check_gen(layer, label):
            """SYNC CHECK 2 (after generation or slerp): does the layer still sit on the onsets of the real crossfade it
            came from? Per bar, trusted only where the two share onsets (correlation >= 0.2)."""
            lag = generated_layer_lag(layer, other_ref, bar, args.w_bars)
            synced = lag is not None and abs(lag) <= args.gen_lag_tol_ms
            if not synced:
                print(f"  WARNING generated `other` ({label}) is not verified on the real onsets "
                      f"(median lag {lag} ms, tolerance {args.gen_lag_tol_ms})", flush=True)
                if args.require_sync:
                    raise SyncError(f"transition {i} {label}: generated other lags {lag} ms")
            return {"gen_lag_ms": lag, "gen_synced": bool(synced)}

        def emit(other, other_path, extra, drums_layer=None):
            drums_used = drums if drums_layer is None else drums_layer
            trans = (bass + drums_used + other + vocals + resid).astype(np.float64)
            out = dict(extra, other_path=other_path, peak=float(np.abs(trans).max()))
            out["clipped_if_pcm16"] = bool(out["peak"] > 1.0)
            name = out_dir / f"v7_smoke_trans_FAST_{i}_{other_path}.wav"
            sf.write(str(name), trans.T, SR, subtype="FLOAT")    # float: nothing clips here; normalise the whole mix once
            out["file"] = name.name
            rec["outputs"].append(out)
            print(f"  wrote {name.name} (peak {out['peak']:.2f}, other: {other_path})", flush=True)

        if not generating:
            emit(other_ref, "skipped", {"nl": None})              # the plain crossfade: the baseline (and the benchmark)
        target = chroma_morph_target(other_a, other_b) if generating and args.other_mode == "lora_latch" else None
        for nl in (args.noise_levels if generating else []):
            label = f"{args.other_mode}_nl{int(round(nl * 100))}"      # the file name says which path made `other`
            try:
                t_gen = time.time()
                gen = generate_sine_a2a(sa3_model, other_ref, W_sec, args, nl, target)
                extra = {"nl": nl, "gen_seconds": round(time.time() - t_gen, 1)}
                extra["other_peak"] = dsp.assert_finite(gen, f"transition {i} other nl{nl}")
                extra["other_len_delta"] = int(gen.shape[-1] - L)     # logged, then padded or trimmed
                gen = np.pad(gen, ((0, 0), (0, max(0, L - gen.shape[-1]))))[:, :L]
                gen, extra["other_gain"] = dsp.match_rms(gen, other_ref)
                extra.update(check_gen(gen, label))                   # SYNC CHECK 2
                other = dsp.edge_blend(gen, other_ref, min(int(round(args.edge_bars * bar)), L // 2))   # spec R0.5, S4
                emit(other, label, extra)
            except SyncError as e:
                rec["error"] = repr(e)
                rec["outputs"].append({"nl": nl, "other_path": "FAILED", "error": repr(e)})
                (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
                raise                                             # a sync failure is never turned into a fallback
            except Exception as e:                                # noqa: BLE001
                rec["error"] = repr(e)
                if not args.allow_fallback:
                    rec["outputs"].append({"nl": nl, "other_path": "FAILED", "error": repr(e)})
                    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
                    raise
                print(f"Generative inference failed at nl {nl}, FALLING BACK to crossfade: {e!r}", flush=True)
                emit(other_ref, "fallback_crossfade", {"nl": nl, "error": repr(e)})
                break                                         # one labelled fallback per transition, not one per level

        # VARIANTS (ported from 799b349): latent-slerp `other`, masked drum inpaint. Independent of --other-mode: they use the
        # plain crossfade (or the slerp) for `other`. They need the model but not the generative `other` layer.
        if variants_wanted:
            tag = "slerp"

            def other_inpaint(ob):
                """Masked inpaint of the `other` stem; level-matched, checked against the real onsets like every generated layer
                (SYNC CHECK 2), edges are the real crossfade (the mask is central, so only the fades differ)."""
                t_gen = time.time()
                ot, _, _ = drum_inpaint(sa3_model, other_ref, ob, bpm_b, L, args, prompt=args.prompt_b, cfg=args.other_cfg)
                ot, gain = dsp.match_rms(ot, other_ref)
                info = {"gen_seconds": round(time.time() - t_gen, 1), "other_gain": gain, "adapter_live": bool(generating and args.other_mode == "lora_latch")}
                info.update(check_gen(ot, f"other inpaint {ob} bar"))
                return ot, info

            try:
                other_sl = None
                if args.other_slerp:
                    t_gen = time.time()
                    sl = latent_slerp_other(sa3_model, other_a, other_b, L)
                    extra = {"gen_seconds": round(time.time() - t_gen, 1), "other_peak": dsp.assert_finite(sl, f"transition {i} slerp")}
                    sl, extra["other_gain"] = dsp.match_rms(sl, other_ref)
                    extra.update(check_gen(sl, "d-xfade_o-slerp"))
                    other_sl = dsp.edge_blend(sl, other_ref, min(int(round(args.edge_bars * bar)), L // 2)) if args.edge_bars > 0 else sl
                    emit(other_sl, "d-xfade_o-slerp", dict(extra, drums="xfade", other="slerp"))
                for nb in args.drum_inpaint_bars:
                    tag = f"inpaint{nb}bar"
                    t_gen = time.time()
                    dr_in, lo_s, hi_s = drum_inpaint(sa3_model, drums, nb, bpm_b, L, args)
                    chk = inpaint_grid_check(drums, dr_in, lo_s, hi_s, bpm_b, args.inpaint_grid_tol_ms)    # the plan's timing check
                    extra = {"gen_seconds": round(time.time() - t_gen, 1), "mask_s": [round(lo_s, 3), round(hi_s, 3)],
                             "inpaint_grid": chk, "adapter_live": bool(generating and args.other_mode == "lora_latch")}
                    if not chk["ok"]:
                        print(f"  WARNING inpainted drums ({nb} bar) left the kick grid or have no kicks: {chk}", flush=True)
                        if args.require_sync:
                            raise SyncError(f"transition {i} drum inpaint {nb} bar: {chk}")
                    emit(other_ref, f"d-inpaint{nb}bar_o-skipped", dict(extra, drums=f"inpaint{nb}bar", other="skipped"), drums_layer=dr_in)
                    if other_sl is not None:
                        emit(other_sl, f"d-inpaint{nb}bar_o-slerp", dict(extra, drums=f"inpaint{nb}bar", other="slerp"), drums_layer=dr_in)
                    for ob in args.other_inpaint_bars:                # drum bridge x `other` bridge (9c0ddd1)
                        tag = f"inpaint{nb}bar+other{ob}"
                        ot_in = other_inpaint(ob)
                        emit(ot_in[0], f"d-inpaint{nb}bar_o-inpaint{ob}bar", dict(extra, drums=f"inpaint{nb}bar", other=f"inpaint{ob}bar", **ot_in[1]),
                             drums_layer=dr_in)
                for ob in (args.other_inpaint_bars if not args.drum_inpaint_bars else []):
                    tag = f"other{ob}"
                    ot_in = other_inpaint(ob)
                    emit(ot_in[0], f"d-xfade_o-inpaint{ob}bar", dict(drums="xfade", other=f"inpaint{ob}bar", **ot_in[1]))
            except SyncError as e:
                rec["error"] = repr(e)
                rec["outputs"].append({"other_path": "FAILED", "variant": tag, "error": repr(e)})
                (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
                raise
            except Exception as e:                                # noqa: BLE001
                rec["error"] = repr(e)
                rec["outputs"].append({"other_path": "FAILED", "variant": tag, "error": repr(e)})
                (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
                if not args.allow_fallback:
                    raise
                print(f"Variant {tag} failed, continuing (--allow-fallback): {e!r}", flush=True)

    meta["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
    print(f"Done. {len(meta['transitions'])} transitions and run_meta.json in {out_dir}", flush=True)


if __name__ == "__main__":
    main()
