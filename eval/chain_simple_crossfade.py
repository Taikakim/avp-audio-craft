#!/usr/bin/env python
"""chain_simple_crossfade.py — Kim 2026-09-16: the "improved crossfader" — replaces
chain_dj_overlay.py's dual-independent-outpaint overlay with a much simpler,
genuinely splice-safe mechanism: NO outpainting for the transition itself, just a
real-audio equal-power crossfade between A's own (faded) tail and B's own head,
precisely aligned via a reverse-polarity-difference ("null test") search in the
kick/bass band. Because both sides of the crossfade are the clips' OWN real audio
(never independently-generated bridge material), concatenating many such transitions
end to end is a genuinely non-duplicating splice -- unlike chain_dj_overlay.py, where
each pairwise render was a self-contained two-clip mix and every clip got heard twice
across neighbouring files.

Pipeline per pair (A outgoing, B incoming):
  1. real madmom downbeats -> crop A's usable end (find_downbeat_before, mir's
     create_training_crops.py -- backward-only snap, never overshoots) / B's usable
     start (find_closest_downbeat, same tool) to actual bars.
  2. bungee pre-bend, reused as-is from tonight's DJ-overlay build: A's tail creeps up
     toward a meeting tempo before the join (prebend_outgoing), B's head starts
     under-tempo and catches up to meet it (prebend_incoming).
  3. Precise alignment: reverse-polarity-difference search, band-limited to ~40-150Hz
     (kick/bass) -- minimizes ||A_tail - shift(B_head)||^2 over a small shift range,
     which is a DJ "null test" for where two kicks best coincide, and is mathematically
     the same thing as maximizing the cross-correlation of the two band-limited signals.
     ONLY meaningful because step 2 already brought both sides to one shared tempo
     across the window -- a pure sample-shift search has no reason to show a clean
     minimum otherwise (Kim's own caveat, and it's the right one).
  4. db_linear_crossfade of A's tail against B's (aligned) head over that window --
     ONE curve doing both the volume ramp-down AND the crossfade (Kim: "a 10% ramp-
     down at the end and crossfade the audio to the target"), linear in dB rather
     than equal-power, so the perceived transition rate is constant across the whole
     window instead of front/back-loaded (Kim's ear, 2026-09-16: the equal-power
     version's audible crossfade compressed into ~2s of a much longer nominal
     window -- see db_linear_crossfade's docstring for the exact mechanism). This IS
     the whole transition, no generative call needed for it.
  5. Also renders a "+a2a" variant: a light nl=0.7 sine-bump smoothing pass over just
     the crossfaded window, to test whether generative smoothing still helps at all now
     that the starting point is real overlapping audio rather than independently
     generated bridge material (a genuinely different question than it was against
     chain_dj_overlay.py's construction).
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
from scipy.signal import butter, sosfiltfilt

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
from chain_dj_overlay import BRIDGE_CKPT  # noqa: E402
from chroma_morph_transitions import load  # noqa: E402
from dj_beatmatch import (detect_quiet_points, madmom_downbeats,  # noqa: E402
                           prebend_incoming, prebend_outgoing)

sys.path.insert(0, "/home/kim/Projects/mir/src/tools")
from create_training_crops import find_closest_downbeat, find_downbeat_before  # noqa: E402
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402


def polarity_diff_align(a_tail, b_head, sr, max_shift_sec=0.08, band=(40.0, 150.0)):
    """Reverse-polarity ("null test") alignment: the shift of b_head that MINIMIZES
    ||a_tail - shift(b_head)||^2 in the kick/bass band -- where two kicks best cancel
    when phase-inverted, i.e. where they best coincide. Equivalent to maximizing
    cross-correlation of the band-limited signals; phrased Kim's way since it's the
    literal DJ null test. Returns the shift in seconds (positive = delay b_head)."""
    sos = butter(4, band, btype="bandpass", fs=sr, output="sos")
    a_b = sosfiltfilt(sos, a_tail.mean(0))
    b_b = sosfiltfilt(sos, b_head.mean(0))
    max_shift = round(max_shift_sec * sr)
    best_shift, best_energy = 0, np.inf
    for s in range(-max_shift, max_shift + 1):
        a0, b0 = max(0, -s), max(0, s)
        n = min(len(a_b) - a0, len(b_b) - b0)
        if n <= 0:
            continue
        diff = a_b[a0:a0 + n] - b_b[b0:b0 + n]
        energy = float(np.mean(diff ** 2))
        if energy < best_energy:
            best_energy, best_shift = energy, s
    return best_shift / sr


def equal_power_crossfade(a_tail, b_head):
    """UNUSED by default now -- kept for reference/comparison. Equal-POWER (cos/sin,
    cos^2+sin^2=1) is linear in POWER, not in perceived (dB) loudness: near t=0 the
    incoming gain sin(theta)~=theta makes its dB level 20*log10(theta) rise near-
    infinitely fast, so it jumps to near-full perceptual loudness almost immediately;
    symmetrically the outgoing track barely moves in dB at first then collapses just
    as fast right at the end. Net effect: a near-instant fade-up, a long stretch where
    both sound essentially fully present, a near-instant fade-down -- not an evenly
    paced crossfade, however long the nominal window is (Kim's ear, 2026-09-16: "the
    crossfade itself happens in like two seconds" despite a much longer window)."""
    n = min(a_tail.shape[1], b_head.shape[1])
    t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
    return a_tail[:, :n] * np.cos(t)[None, :] + b_head[:, :n] * np.sin(t)[None, :]


def bass_swap_crossfade(a_tail, b_head, sr, crossover_hz=150.0, late_frac=0.85):
    """Kim's DJ-EQ 'bass swap' (2026-09-16): mids/highs cross over on the normal
    linear timeline, but the kick/bass (below crossover_hz) stays dominated by A
    until late_frac of the window, then swaps rapidly to B over the remainder.
    Matches how Kim actually mixes by hand (cut/hold the bass, bring it in fast
    right when the new beat lands) and avoids two kicks clashing for the WHOLE
    overlap -- the thing Kim still hears as "out of sync" isn't primarily
    misalignment, it's two full-density kick patterns overlapping the entire
    window with nothing structural separating them. Requires A_tail/B_head to
    already share one tempo (same precondition as polarity_diff_align)."""
    n = min(a_tail.shape[1], b_head.shape[1])
    a, b = a_tail[:, :n], b_head[:, :n]
    sos_lo = butter(4, crossover_hz, btype="lowpass", fs=sr, output="sos")
    sos_hi = butter(4, crossover_hz, btype="highpass", fs=sr, output="sos")
    a_lo = sosfiltfilt(sos_lo, a, axis=1)
    a_hi = sosfiltfilt(sos_hi, a, axis=1)
    b_lo = sosfiltfilt(sos_lo, b, axis=1)
    b_hi = sosfiltfilt(sos_hi, b, axis=1)

    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    hi_mix = a_hi * (1.0 - t)[None, :] + b_hi * t[None, :]
    t_lo = np.clip((t - late_frac) / (1.0 - late_frac), 0.0, 1.0).astype(np.float32)
    lo_mix = a_lo * (1.0 - t_lo)[None, :] + b_lo * t_lo[None, :]
    return hi_mix + lo_mix


def linear_crossfade(a_tail, b_head):
    """Plain linear gain -- literally two volume knobs, one down (1-t) one up (t).
    Worst-case midpoint dip for two UNCORRELATED signals: (0.5^2+0.5^2)=0.5 power,
    i.e. ~3dB below either endpoint -- mild, generally inaudible, and nowhere near
    db_linear_crossfade's ~27dB hole. Simpler than equal-power (no trig), at the
    cost of that small dip equal-power exists to remove."""
    n = min(a_tail.shape[1], b_head.shape[1])
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    return a_tail[:, :n] * (1.0 - t)[None, :] + b_head[:, :n] * t[None, :]


def db_linear_crossfade(a_tail, b_head, floor_db=-60.0):
    """Crossfade whose GAIN is linear in dB -- constant PERCEIVED rate of change
    across the whole window, unlike equal_power_crossfade above. A's gain ramps
    0 -> floor_db, B's ramps floor_db -> 0, both linearly in dB, converted back to
    linear amplitude for mixing. Trade-off: total power is NOT conserved (no
    cos^2+sin^2=1 guarantee), so two uncorrelated signals can show a small level dip
    or bump near the midpoint -- accepted in exchange for an evenly-paced transition,
    which is the thing actually being asked for here."""
    n = min(a_tail.shape[1], b_head.shape[1])
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    a_gain = 10.0 ** ((t * floor_db) / 20.0)
    b_gain = 10.0 ** (((1.0 - t) * floor_db) / 20.0)
    return a_tail[:, :n] * a_gain[None, :] + b_head[:, :n] * b_gain[None, :]


def a2a_smooth_window(model, composite, sr, window_start_sec, window_sec, nl,
                       prompt, steps, cfg_scale, seed):
    """Sine-bump a2a (0 at the window edges, peak nl at centre) restricted to
    [window_start_sec, window_start_sec+window_sec] -- same mechanism as every other
    a2a pass tonight, just localized to the (much shorter) real-audio crossfade zone."""
    ds = model.model.pretransform.downsampling_ratio
    fps = sr / ds
    pre = model.model.pretransform
    p = next(pre.parameters())
    a = torch.tensor(composite, device=p.device, dtype=p.dtype).unsqueeze(0)
    with torch.inference_mode():
        z_ref = pre.encode(a).clone().float().cpu()
    Tz = z_ref.shape[-1]
    lo = round(window_start_sec * fps)
    hi = round((window_start_sec + window_sec) * fps)
    W = max(1, hi - lo)
    depth_shape = torch.zeros(Tz)
    depth_shape[lo:hi] = torch.sin(torch.linspace(0, torch.pi, W))
    depth = (depth_shape * nl).view(1, 1, -1)
    torch.manual_seed(4242)
    eps_ref = torch.randn_like(z_ref)

    def cb(d, _z=z_ref, _e=eps_ref, _d=depth):
        x, tt = d["x"], float(d["t"][0])
        n = min(x.shape[-1], _z.shape[-1])
        hold = (_d[..., :n] < tt)
        ref_t = ((1 - tt) * _z[..., :n] + tt * _e[..., :n]).to(x.device, x.dtype)
        x[..., :n].copy_(torch.where(hold.to(x.device), ref_t, x[..., :n]))

    dur = composite.shape[1] / sr
    out = model.generate(prompt=prompt, duration=dur, steps=steps, cfg_scale=cfg_scale,
                          seed=seed, batch_size=1, sample_size=int((dur + 8) * sr),
                          init_audio=(sr, torch.tensor(composite)), init_noise_level=nl,
                          callback=cb)[0].float().cpu().numpy()
    return out


def process_pair(model, sr, p, args, out_dir):
    A, sra = load(p["a_path"])
    B, srb = load(p["b_path"])
    assert sra == sr and srb == sr

    # Real madmom BPM (from mixtape_madmom_bpm.py, already fold-corrected and
    # anchored to this corpus's own metadata) -- NOT chroma_morph_transitions.
    # tempo_of(), which carries a hardcoded 110-185bpm fold band that is wrong
    # for this corpus (it spans 93-155bpm) and would silently 1.5x-fold slow
    # clips again, exactly the bug already found and fixed tonight.
    ta, tb = p["a_bpm"], p["b_bpm"]

    # Beat-aware cropping. Two paths:
    #  - PRECOMPUTED bounds (Kim 2026-09-17, via mixtape_bar_aware_bounds.py):
    #    a_end/b_start are each that clip's OWN entry/exit point, computed once
    #    from its own downbeat grid so it's identical whether the clip is acting
    #    as "A" here or was "B" in the previous pair -- bar count from entry to
    #    exit is a multiple of 4 ("the eventual clips you're mixing have
    #    downbeats divisible by four"), snapped to a zero crossing, and the exit
    #    point is chosen from a low-RMS spot in the clip's latter section where
    #    possible (avoids landing a transition mid-drop/mid-buildup).
    #  - fallback: the original per-pair a_frac/b_frac downbeat snap, via the
    #    ESTABLISHED mir tool (create_training_crops.py). A's END snaps BACKWARD
    #    ONLY (find_downbeat_before) so the crop never overshoots past the
    #    target point -- a plain nearest-neighbor snap (what this used to do)
    #    can pick a downbeat AFTER the target, silently lengthening A past
    #    where it was meant to end. B's START uses find_closest_downbeat
    #    (nearest, either direction), matching that tool's own convention.
    if "a_end_sec" in p and "b_start_sec" in p:
        a_end, b_start = float(p["a_end_sec"]), float(p["b_start_sec"])
    else:
        db_a = np.asarray(madmom_downbeats(A, sr))
        db_b = np.asarray(madmom_downbeats(B, sr))
        a_target = args.a_frac * A.shape[1] / sr
        b_target = args.b_frac * B.shape[1] / sr
        a_end = find_downbeat_before(db_a, a_target)
        a_end = float(a_end) if a_end is not None else a_target
        b_start = find_closest_downbeat(db_b, b_target)
        b_start = float(b_start) if b_start is not None else b_target
    A_use = A[:, :max(1, round(a_end * sr))]
    B_use = B[:, round(b_start * sr):]

    window_sec = args.crossfade_sec if args.crossfade_sec else args.crossfade_frac * (A_use.shape[1] / sr)
    tail_start = A_use.shape[1] - round(window_sec * sr)
    A_head, A_tail = A_use[:, :tail_start], A_use[:, tail_start:]

    target_bpm = ta + args.bend_bpm
    A_tail_bent = prebend_outgoing(A_tail, sr, ta, mix_point_sec=A_tail.shape[1] / sr,
                                    max_bonus_bpm=args.bend_bpm)
    quiet = detect_quiet_points(B_use, sr)
    catch_up_center = quiet[0] if quiet else 1.5
    B_bent = prebend_incoming(B_use, sr, tb, target_bpm, catch_up_center)

    # NOTE: the volume ramp-down and the crossfade are now ONE operation (the
    # db_linear_crossfade curve below), not a separate linear pre-fade stacked under
    # a second fade curve -- that double-attenuated A relative to B's ramp-up.
    n = A_tail_bent.shape[1]
    shift_sec = polarity_diff_align(A_tail_bent, B_bent[:, :n], sr,
                                     max_shift_sec=args.max_shift_sec)
    shift_n = round(shift_sec * sr)
    if shift_n > 0:
        B_aligned = np.concatenate([np.zeros((B_bent.shape[0], shift_n), dtype=B_bent.dtype), B_bent], axis=1)
    elif shift_n < 0:
        B_aligned = B_bent[:, -shift_n:]
    else:
        B_aligned = B_bent

    # Kim (2026-09-16): "why can't we just ramp the volume over the overlap region
    # like when turning one volume knob down and the other up" -- plain linear gain,
    # not equal-power's trig curve. Simpler mental model, and its worst-case dip for
    # two UNCORRELATED clips is a mild ~3dB sag at the midpoint -- nowhere near
    # db_linear_crossfade's ~27dB hole (that one attenuated by dB, which compounds
    # doubly badly), and generally accepted as inaudible in casual DJ mixing. The
    # window-length lever (the outpainted extension) is what actually controls
    # whether the transition FEELS long enough; this curve just governs how it feels
    # within whatever window it's given.
    overlap = linear_crossfade(A_tail_bent, B_aligned)
    W = overlap.shape[1]
    B_post = B_aligned[:, W:]

    plain = np.concatenate([A_head, overlap, B_post], axis=1)
    plain_path = out_dir / f"{p['out_name']}_plain.wav"
    save_audio(str(plain_path), torch.tensor(plain), sr)

    smoothed = a2a_smooth_window(model, plain, sr, A_head.shape[1] / sr, W / sr,
                                  args.nl, args.prompt, args.steps, args.cfg_scale, args.seed)
    a2a_path = out_dir / f"{p['out_name']}_a2a.wav"
    save_audio(str(a2a_path), torch.tensor(smoothed), sr)

    if args.bass_swap:
        bs_overlap = bass_swap_crossfade(A_tail_bent, B_aligned, sr,
                                          late_frac=args.bass_swap_late_frac)
        bs = np.concatenate([A_head, bs_overlap, B_post], axis=1)
        save_audio(str(out_dir / f"{p['out_name']}_bassswap.wav"), torch.tensor(bs), sr)

    return {"tempo_a": ta, "tempo_b": tb, "target_bpm": target_bpm,
            "align_shift_ms": shift_sec * 1000, "overlap_sec": W / sr,
            "a_head_sec": A_head.shape[1] / sr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs-json", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--ckpt", default=BRIDGE_CKPT)
    ap.add_argument("--crossfade-frac", type=float, default=0.10)
    ap.add_argument("--crossfade-sec", type=float, default=None,
                     help="absolute overlap length in seconds, overrides --crossfade-frac when set")
    ap.add_argument("--bend-bpm", type=float, default=2.0)
    ap.add_argument("--max-shift-sec", type=float, default=0.08)
    ap.add_argument("--nl", type=float, default=0.7)
    ap.add_argument("--bass-swap", action="store_true", default=False,
                     help="also render Kim's bass-swap variant (mids/highs cross early, bass holds from A until late)")
    ap.add_argument("--bass-swap-late-frac", type=float, default=0.85)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--a-frac", type=float, default=0.97)
    ap.add_argument("--b-frac", type=float, default=0.03)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    pairs = json.loads(args.pairs_json.read_text())
    print(f"[load] model, {len(pairs)} pairs", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([args.ckpt])
    sr = model.model.sample_rate

    for p in pairs:
        out_name = p["out_name"]
        if (args.out_dir / f"{out_name}_a2a.wav").exists():
            print(f"[skip] {out_name}", flush=True)
            continue
        print(f"[gen] {out_name}", flush=True)
        meas = process_pair(model, sr, p, args, args.out_dir)
        print(f"  tempo A={meas['tempo_a']:.1f} B={meas['tempo_b']:.1f} "
              f"target={meas['target_bpm']:.1f} align={meas['align_shift_ms']:+.1f}ms "
              f"overlap={meas['overlap_sec']:.2f}s", flush=True)
        (args.out_dir / f"{out_name}_run_meta.json").write_text(json.dumps({
            "purpose": "the 'improved crossfader' redesign: real-audio equal-power crossfade "
                       "(no outpainting) between A's faded tail and B's head, aligned via "
                       "reverse-polarity-difference null test in the kick/bass band, after "
                       "bungee pre-bend to a shared tempo. Genuinely splice-safe (no clip "
                       "duplicated across neighbouring transitions), unlike chain_dj_overlay.py.",
            "params": vars(args) | {"pairs_json": str(args.pairs_json)},
            "measured": meas, "kim_feedback": None,
        }, indent=2, default=str))
        print(f"[done] {out_name}", flush=True)

    print("[all done]", flush=True)


if __name__ == "__main__":
    main()
