#!/usr/bin/env python
"""chain_dj_overlay.py — Kim 2026-09-16: DJ-style long OVERLAY mix between two
short SA3-generated mixtape clips (A = outgoing, B = incoming) — as opposed to
the seam/crossfade family (chroma_morph_transitions.py, mixtape_seam_align_test.py,
chain_outpaint_xfade_a2a.py), which join clips over a short bar-quantized window.
Here the transition material is TWO independently outpainted extensions (A's own
forward continuation, B's own backward "precede" continuation) that are meant to
play SIMULTANEOUSLY, overlaid — the way a human DJ lets an outgoing track's own
natural tail run underneath an incoming track's own natural intro, rather than
splicing a bridge between them.

Pipeline (Kim's design, this session — see the numbered steps inline below):
  1. load A, B
  2. real madmom downbeats -> snap A's usable end / B's usable start to them
     (NOT the librosa-estimate downbeat_near() — that stays the fallback elsewhere)
  3. precise BPM (tempo_of, per-pair median inter-beat interval)
  4. pre-bend BOTH clips before the overlap exists: A's tail nudges UP to
     +bend_bpm by the point the overlap starts; B's head starts DOWN at
     -bend_bpm and mostly catches up by a detected quiet/fill point near its start
  5. outpaint A forward by outpaint_mult x its own (post-prebend) duration,
     outpaint B backward ("precede") by outpaint_mult x ITS own duration — the
     overlap window is this newly generated material on each side, overlaid,
     not concatenated
  6. fine onset-concurrence alignment (fine_align_shift) of B within the overlap,
     on top of the coarse downbeat snap + BPM pre-bend
  7. EQ sweep on B over the overlap span (thin -> bass-snap at the nearest
     downbeat inside the overlap)
  8. re-encode both post-processed overlap segments to SAME latents, latent
     slerp crossfade over the FULL overlap span
  9. decode the composite as the pre-a2a reference ("*_preA2A.wav"), then a
     sine-bump a2a refine pass (0 at the overlap edges, peak nl at centre) with
     chroma-ramp LatCH guidance
  10. run_meta.json sidecar per pair (purpose/params/checkpoint/prompt/seed +
      everything measured along the way)

Reuses, rather than re-derives, the already-tested machinery from this session's
sibling scripts: chroma_morph_transitions.py (load, tempo_of, fine_align_shift,
encode, compute_same_chroma, CHROMA_HEAD/CHROMA_GAIN/FPS), the outpaint mechanism
from outpaint_lengthen.py (zero-padded inpaint_audio + inpaint_mask_*_seconds),
the "precede" backward-outpaint direction + layered-guidance / sine-bump a2a
pattern from chain_outpaint_xfade_a2a.py, and the full-overlap-span slerp +
preA2A-dump convention from mixtape_seam_align_test.py.

=====================================================================
RECONCILED against the real dj_beatmatch.py / dj_eq_sweep.py (2026-09-16
integration pass) — the three files were written in parallel by separate
agents and the original call sites here assumed a different contract than
what those two modules actually shipped with. Fixed at the call sites below
(this file), since dj_beatmatch.py / dj_eq_sweep.py are the more
independently-reusable pieces. Real contracts, for reference:

  madmom_downbeats(audio, sr) -> list[float]
      Real (madmom) downbeat/bar-start times in seconds, sorted ascending.
      `audio` is (C, N) or (N,); mir-venv subprocess via the beat_grid CLI,
      isolated-temp-dir per call (works around its folder-named-sidecar bug).

  snap_downbeat(downbeats, target_sec) -> float
      Takes a DOWNBEAT LIST (from madmom_downbeats), not audio — nearest
      entry to target_sec, or target_sec unchanged if the list is empty.
      (The original assumption here was snap_downbeat(audio, sr,
      target_sec) — wrong arity; fixed below to call madmom_downbeats()
      first.)

  detect_quiet_points(audio, sr, hop_sec=0.5) -> list[float]
      RMS local minima, sorted by TIME ascending — NOT by energy. (The
      original assumption here was "index 0 is already the quietest
      candidate"; real dj_beatmatch.py sorts chronologically, so index 0 is
      merely the EARLIEST minimum, which can land right at the start of the
      clip. Fixed below by filtering out anything inside the first half-bar
      before taking the first candidate.)

  prebend_outgoing(audio, sr, bpm, mix_point_sec, max_bonus_bpm=2.0,
                    normal_step=0.25, quiet_step=0.5) -> np.ndarray
      Bends from t=0 OF THE AUDIO PASSED IN up to `mix_point_sec`, reaching
      `bpm + max_bonus_bpm` there, then holds to the end of that audio. It
      does NOT take a [region_start, region_end] window into a longer clip
      (that was this file's original wrong assumption) — to bend only the
      last `bend_bars` bars of A, the call below SLICES A_use into a
      head/tail first and only bends the tail.

  prebend_incoming(audio, sr, bpm, target_bpm, catch_up_center_sec,
                    catch_up_width_sec=3.0, start_undershoot_frac=0.3) -> np.ndarray
      Ramps to an actual `target_bpm` (not a small +/-delta off B's own
      native tempo, which was this file's original wrong assumption and
      also would never actually close the tempo gap with A) — the call
      below passes A's post-prebend tempo (ta + bend_bpm) as the target, so
      B is genuinely beatmatched to A by the time the overlap starts.

  eq_sweep_incoming(audio, sr, t_start, t_kick, t_end, low_cut_hz=250.0,
                     high_cut_hz=8000.0, bass_ramp_sec=0.3, ...) -> np.ndarray
      Requires t_start/t_end (region bounds), not just t_kick (this file's
      original wrong assumption omitted them, which would TypeError).
      Called below with t_start=0.0, t_end=overlap_sec — B_overlap_audio IS
      the whole active region, so there's no passthrough boundary to worry
      about within this call.

None of the above is called with GPU code; they're plain numpy/audio DSP per
Kim's brief. This script itself only touches the GPU via StableAudioModel.
=====================================================================
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

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from chroma_morph_transitions import (  # noqa: E402
    CHROMA_GAIN, CHROMA_HEAD, FPS, compute_same_chroma, encode,
    fine_align_shift, load, tempo_of,
)
from dj_beatmatch import (  # noqa: E402
    detect_quiet_points, madmom_downbeats, prebend_incoming, prebend_outgoing,
    snap_downbeat,
)
from dj_eq_sweep import eq_sweep_incoming  # noqa: E402
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.inference.longform import slerp  # noqa: E402

BRIDGE_CKPT = "/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt"


def _first_quiet_time(quiet_points, default=0.0):
    """Normalize detect_quiet_points()'s return (bare seconds, or (time, energy)
    tuples) to a single float time -- contract says index 0 is already the
    quietest / most fill-like candidate."""
    if quiet_points is None or len(quiet_points) == 0:
        return float(default)
    first = quiet_points[0]
    if isinstance(first, (tuple, list, np.ndarray)):
        return float(first[0])
    return float(first)


def _t_kick_in_overlap(overlap_audio, sr, default_frac=0.5):
    """Nearest real downbeat to the START of the (already fine-aligned) overlap
    audio, i.e. seconds-from-overlap-start where B's bass should snap in. Falls
    back to the overlap's own midpoint if madmom finds nothing inside it (short
    clips, quiet material) -- an explicit, logged fallback rather than a crash."""
    dur = overlap_audio.shape[1] / sr
    downs = madmom_downbeats(overlap_audio, sr)
    inside = [d for d in downs if 0.0 <= d <= dur]
    if inside:
        return float(min(inside))
    return float(dur * default_frac)


def outpaint_forward(model, audio, sr, ext_sec, prompt, steps, cfg_scale, seed):
    """A grows an organic tail (outpaint_lengthen.py's mechanism): zero-pad by
    ext_sec, inpaint exactly the padded region."""
    dur = audio.shape[1] / sr
    pad = np.concatenate([audio, np.zeros((audio.shape[0], round(ext_sec * sr)), dtype=audio.dtype)], axis=1)
    total = pad.shape[1] / sr
    out = model.generate(
        prompt=prompt, duration=total, steps=steps, cfg_scale=cfg_scale,
        seed=seed, batch_size=1, sample_size=int((total + 8) * sr),
        inpaint_audio=(sr, torch.tensor(pad)),
        inpaint_mask_start_seconds=dur, inpaint_mask_end_seconds=total,
    )[0].float().cpu().numpy()
    return out


def outpaint_backward(model, audio, sr, ext_sec, prompt, steps, cfg_scale, seed):
    """B grows an organic lead-in ("precede" direction, chain_outpaint_xfade_a2a.py's
    mechanism): zero-pad BEFORE the audio, inpaint exactly that leading region."""
    pad = np.concatenate([np.zeros((audio.shape[0], round(ext_sec * sr)), dtype=audio.dtype), audio], axis=1)
    total = pad.shape[1] / sr
    out = model.generate(
        prompt=prompt, duration=total, steps=steps, cfg_scale=cfg_scale,
        seed=seed, batch_size=1, sample_size=int((total + 8) * sr),
        inpaint_audio=(sr, torch.tensor(pad)),
        inpaint_mask_start_seconds=0.0, inpaint_mask_end_seconds=ext_sec,
    )[0].float().cpu().numpy()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs-json", type=Path, required=True,
                     help='JSON list of {"out_name", "a_path", "b_path"}')
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--ckpt", default=BRIDGE_CKPT)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--nl", type=float, default=0.8,
                     help="sine-bump a2a peak strength at the overlap centre (0.7-0.8 confirmed by ear)")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--a-frac", type=float, default=0.97,
                     help="A's usable-end snap target, as a fraction of A's own length")
    ap.add_argument("--b-frac", type=float, default=0.03,
                     help="B's usable-start snap target, as a fraction of B's own length")
    ap.add_argument("--bend-bars", type=float, default=8.0,
                     help="length (in bars, at the clip's own measured tempo) of the "
                          "pre-bend region at A's tail / B's head")
    ap.add_argument("--bend-bpm", type=float, default=2.0,
                     help="pre-bend depth: A ramps UP to +this by the overlap start, "
                          "B starts DOWN at -this and ramps back to native")
    ap.add_argument("--outpaint-mult", type=float, default=2.0,
                     help="each side's outpaint extension length, as a multiple of "
                          "that side's OWN (post-prebend) duration")
    ap.add_argument("--guidance-end-pct", type=float, default=0.6,
                     help="LatCH chroma guidance stops at this fraction of a2a steps "
                          "(content locks mid-trajectory -- matches the rest of this codebase)")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("[load] model", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([args.ckpt])
    sr = model.model.sample_rate

    pairs = json.loads(args.pairs_json.read_text())
    for p in pairs:
        out_name = p["out_name"]
        out_path = args.out_dir / f"{out_name}.wav"
        meta_path = args.out_dir / f"{out_name}_run_meta.json"
        if out_path.exists():
            print(f"[skip] {out_name}", flush=True)
            continue
        t_pair0 = time.time()

        # ---- step 1: load ----
        A, sra = load(p["a_path"])
        B, srb = load(p["b_path"])
        assert sra == sr and srb == sr

        # ---- step 3 (measured before the crop so the tempo estimate sees real
        # material on both sides of the eventual cut): precise BPM ----
        ta = tempo_of(A, sr, around_sec=args.a_frac * A.shape[1] / sr)
        tb = tempo_of(B, sr, around_sec=args.b_frac * B.shape[1] / sr)
        print(f"[{out_name}] tempo A={ta:.2f} B={tb:.2f}", flush=True)

        # ---- step 2: real madmom downbeats, snap A's usable end / B's usable start ----
        # (real snap_downbeat(downbeats, target_sec) takes a downbeat LIST, not
        # audio -- fixed here from the original assumed snap_downbeat(audio, sr,
        # target_sec), which doesn't match dj_beatmatch.py's actual arity.)
        a_downbeats = madmom_downbeats(A, sr)
        b_downbeats = madmom_downbeats(B, sr)
        a_end = snap_downbeat(a_downbeats, args.a_frac * A.shape[1] / sr)
        b_start0 = snap_downbeat(b_downbeats, args.b_frac * B.shape[1] / sr)
        A_use = A[:, :max(1, round(a_end * sr))]
        B_use = B[:, max(0, round(b_start0 * sr)):]
        print(f"  [snap] A_end={a_end:.3f}s (A_use {A_use.shape[1]/sr:.2f}s)  "
              f"B_start={b_start0:.3f}s (B_use {B_use.shape[1]/sr:.2f}s)", flush=True)

        # ---- step 4: pre-bend BOTH clips before the overlap exists ----
        # A: prebend_outgoing only bends from t=0 of the audio it's given, up
        # to its own mix_point_sec -- there's no [region_start, region_end]
        # window into a longer clip (the original call here assumed one and
        # would TypeError). To keep the "only the last bend_bars bars move"
        # design, slice A_use into head/tail and bend only the tail.
        bar_sec_a = 4 * 60.0 / ta
        region_sec_a = args.bend_bars * bar_sec_a
        A_dur0 = A_use.shape[1] / sr
        a_split = round(max(0.0, A_dur0 - region_sec_a) * sr)
        A_head, A_tail = A_use[:, :a_split], A_use[:, a_split:]
        A_tail_bent = prebend_outgoing(
            A_tail, sr, ta, A_tail.shape[1] / sr,
            max_bonus_bpm=args.bend_bpm,
        )
        A_bent = np.concatenate([A_head, A_tail_bent], axis=1)

        # B: real prebend_incoming ramps to an actual target_bpm, not a small
        # +/-delta off B's own native tempo (the original call here passed
        # start_bpm_delta, which doesn't exist on the real signature, and
        # omitted the required target_bpm) -- the meeting tempo is what A
        # will actually be playing at once bent, so the overlap is genuinely
        # beatmatched, not just nudged.
        bar_sec_b = 4 * 60.0 / tb
        target_bpm_b = ta + args.bend_bpm
        quiet = detect_quiet_points(B_use, sr)
        # dj_beatmatch.py's detect_quiet_points sorts by TIME, not energy (the
        # original assumption here was "index 0 = quietest") -- skip anything
        # inside the first half-bar so the catch-up point doesn't land right
        # on B_use's own onset.
        quiet_usable = [q for q in quiet if q >= 0.5 * bar_sec_b]
        catch_up_center_sec = _first_quiet_time(
            quiet_usable or quiet, default=args.bend_bars * bar_sec_b * 0.5)
        B_bent = prebend_incoming(
            B_use, sr, tb, target_bpm_b,
            catch_up_center_sec=catch_up_center_sec,
        )
        print(f"  [bend] A tail -> +{args.bend_bpm:g} bpm ({ta+args.bend_bpm:.2f} bpm) over "
              f"last {region_sec_a:.2f}s | B head starts below native, ramps to "
              f"{target_bpm_b:.2f} bpm, catch-up @ {catch_up_center_sec:.2f}s "
              f"(quiet-point pick)", flush=True)

        # ---- step 5: outpaint A forward / B backward, each by outpaint_mult x
        # its OWN post-prebend duration ----
        A_dur2 = A_bent.shape[1] / sr
        B_dur2 = B_bent.shape[1] / sr
        ext_A_sec = args.outpaint_mult * A_dur2
        ext_B_sec = args.outpaint_mult * B_dur2
        print(f"  [outpaint] A +{ext_A_sec:.2f}s forward | B +{ext_B_sec:.2f}s backward (precede)", flush=True)
        A_ext = outpaint_forward(model, A_bent, sr, ext_A_sec, args.prompt, args.steps, args.cfg_scale, args.seed)
        B_ext = outpaint_backward(model, B_bent, sr, ext_B_sec, args.prompt, args.steps, args.cfg_scale, args.seed)

        # The overlap window is the outpainted material itself, played
        # simultaneously -- ASSUMPTION: since ext_A_sec and ext_B_sec generally
        # differ (A and B are independent clips), the actual overlaid span is
        # their MIN; each side's own excess (the part of its extension farthest
        # from the join) plays alone, adjacent to the overlap, not inside it --
        # matching the standard adjacent-join convention already used elsewhere
        # in this codebase (slerp on zA[...,-W:] against zB[...,:W]).
        overlap_sec = min(ext_A_sec, ext_B_sec)
        overlap_samp = round(overlap_sec * sr)
        A_pre_audio = A_ext[:, :-overlap_samp] if overlap_samp else A_ext
        B_post_audio = B_ext[:, overlap_samp:] if overlap_samp else B_ext
        A_overlap_audio = A_ext[:, -overlap_samp:]
        B_overlap_audio = B_ext[:, :overlap_samp]

        # ---- step 6: fine onset-concurrence alignment of B within the overlap ----
        # (bar_sec_b already computed in step 4, above)
        sh = fine_align_shift(A_overlap_audio, B_overlap_audio, sr,
                               span_sec=overlap_sec, max_shift_sec=bar_sec_b / 2)
        if abs(sh) > 0.004:
            print(f"  [align] B shifted {sh*1000:+.0f}ms within the overlap (onset concurrence)", flush=True)
            if sh < 0:
                shift_n = round(-sh * sr)
                B_overlap_audio = np.concatenate(
                    [B_overlap_audio[:, shift_n:], B_post_audio[:, :shift_n]], axis=1)
            else:
                shift_n = round(sh * sr)
                pad = np.zeros((B_overlap_audio.shape[0], shift_n), dtype=B_overlap_audio.dtype)
                B_overlap_audio = np.concatenate([pad, B_overlap_audio[:, :-shift_n]], axis=1)

        # ---- step 7: EQ sweep on B over the overlap span ----
        # (real eq_sweep_incoming requires t_start/t_end, not just t_kick --
        # the original call here omitted them and would TypeError. B_overlap_audio
        # IS the whole active region here, so t_start=0.0/t_end=overlap_sec, and
        # there's no passthrough boundary within this call to worry about.)
        t_kick = _t_kick_in_overlap(B_overlap_audio, sr)
        print(f"  [eq] t_kick={t_kick:.3f}s inside the {overlap_sec:.2f}s overlap", flush=True)
        B_overlap_audio = eq_sweep_incoming(B_overlap_audio, sr, t_start=0.0,
                                             t_kick=t_kick, t_end=overlap_sec)

        # ---- step 8: re-encode, latent slerp crossfade over the FULL overlap span ----
        zA_pre = encode(model, A_pre_audio, sr) if A_pre_audio.shape[1] else None
        zA_ov = encode(model, A_overlap_audio, sr)
        zB_ov = encode(model, B_overlap_audio, sr)
        zB_post = encode(model, B_post_audio, sr) if B_post_audio.shape[1] else None
        W = min(zA_ov.shape[-1], zB_ov.shape[-1])
        t = torch.linspace(0, 1, W, device=zA_ov.device, dtype=torch.float32).view(1, 1, -1)
        z_overlap = slerp(zA_ov[..., :W].float(), zB_ov[..., :W].float(), t).to(zA_ov.dtype)
        parts = [z for z in (zA_pre, z_overlap, zB_post) if z is not None]
        z = torch.cat(parts, dim=-1)
        Tz = z.shape[-1]
        TA_pre = zA_pre.shape[-1] if zA_pre is not None else 0

        # chroma-ramp guidance target, same recipe as chroma_morph_transitions.py /
        # chain_outpaint_xfade_a2a.py: A's measured chroma -> blend across the
        # overlap window -> B's, computed on the FINAL (post-align/EQ) audio.
        A_full_for_chroma = np.concatenate([A_pre_audio, A_overlap_audio], axis=1)
        B_full_for_chroma = np.concatenate([B_overlap_audio, B_post_audio], axis=1)
        cA = compute_same_chroma(A_full_for_chroma.T, sr).reshape(384, -1)
        cB = compute_same_chroma(B_full_for_chroma.T, sr).reshape(384, -1)
        TA_full = TA_pre + W
        ramp = np.linspace(0, 1, W, dtype=np.float32)[None, :]
        cA_r = cA[:, :TA_full] if cA.shape[1] >= TA_full else np.pad(cA, ((0, 0), (0, TA_full - cA.shape[1])), mode="edge")
        cB_len = W + (zB_post.shape[-1] if zB_post is not None else 0)
        cB_r = cB[:, :cB_len] if cB.shape[1] >= cB_len else np.pad(cB, ((0, 0), (0, cB_len - cB.shape[1])), mode="edge")
        morph = cA_r[:, -W:] * (1 - ramp) + cB_r[:, :W] * ramp
        chroma_target = np.concatenate([cA_r[:, :-W] if TA_pre else cA_r[:, :0],
                                         morph, cB_r[:, W:]], axis=1)[:, :Tz]

        dur = Tz / FPS
        pre = model.model.pretransform
        with torch.inference_mode():
            audio_ref = pre.decode(z.to(next(pre.parameters()).dtype))[0]

        # ---- step 9a: pre-a2a reference dump ----
        preA2A_path = args.out_dir / f"{out_name}_preA2A.wav"
        save_audio(str(preA2A_path), audio_ref.float().cpu(), sr, normalize=True)
        print(f"  [preA2A] {preA2A_path.name}  dur={dur:.2f}s", flush=True)

        # ---- step 9b: sine-bump a2a refine, chroma-ramp guidance, over the FULL
        # overlap span (0 at overlap edges, peak nl at centre) ----
        depth_shape = torch.zeros(Tz)
        depth_shape[TA_pre:TA_pre + W] = torch.sin(torch.linspace(0, torch.pi, W))
        z_ref = z.float().cpu()
        torch.manual_seed(4242)
        eps_ref = torch.randn_like(z_ref)
        depth = (depth_shape * args.nl).view(1, 1, -1)

        def cb(d, _z=z_ref, _e=eps_ref, _d=depth):
            x, tt = d["x"], float(d["t"][0])
            n = min(x.shape[-1], _z.shape[-1])
            hold = (_d[..., :n] < tt)
            ref_t = ((1 - tt) * _z[..., :n] + tt * _e[..., :n]).to(x.device, x.dtype)
            xs = x[..., :n]
            x[..., :n].copy_(torch.where(hold.to(x.device), ref_t, xs))

        print(f"  [a2a] nl={args.nl} chroma-guided over the {overlap_sec:.2f}s overlap", flush=True)
        out = model.generate(
            prompt=args.prompt, duration=dur, steps=args.steps, cfg_scale=args.cfg_scale,
            seed=args.seed, batch_size=1, sample_size=int((dur + 8) * sr),
            init_audio=(sr, audio_ref.float()), init_noise_level=args.nl, callback=cb,
            # NOTE (per chain_outpaint_xfade_a2a.py): rho/mu are GLOBAL sampler
            # hparams shared by every head in latch_configs; per-head strength
            # rides on "weight" alone. Single head here, so weight=1.0.
            latch_configs=[{"model_path": CHROMA_HEAD, "target_raw": chroma_target,
                             "weight": 1.0, "end_pct": args.guidance_end_pct}],
            latch_hparams={"rho": CHROMA_GAIN, "mu": CHROMA_GAIN},
        )
        save_audio(str(out_path), out[0].float().cpu(), sr, normalize=True)

        # ---- step 10: run_meta.json sidecar, per pair ----
        meta = {
            "purpose": ("DJ-style long OVERLAY mix (not a seam crossfade): A's own "
                        "outpainted-forward tail and B's own outpainted-backward "
                        "('precede') head play SIMULTANEOUSLY over the overlap span, "
                        "after real-downbeat snapping, BPM pre-bend on both sides, "
                        "onset-concurrence fine-alignment, and an EQ sweep bringing "
                        "B's bass in at the nearest downbeat inside the overlap."),
            "a_path": p["a_path"], "b_path": p["b_path"],
            "checkpoint": args.ckpt, "prompt": args.prompt, "seed": args.seed,
            "params": {
                "steps": args.steps, "cfg_scale": args.cfg_scale, "nl": args.nl,
                "a_frac": args.a_frac, "b_frac": args.b_frac,
                "bend_bars": args.bend_bars, "bend_bpm": args.bend_bpm,
                "outpaint_mult": args.outpaint_mult,
                "guidance_end_pct": args.guidance_end_pct,
                "chroma_head": CHROMA_HEAD, "chroma_gain": CHROMA_GAIN,
            },
            "measured": {
                "tempo_a_bpm": ta, "tempo_b_bpm": tb,
                "target_bpm_b": target_bpm_b,
                "a_end_downbeat_sec": a_end, "b_start_downbeat_sec": b_start0,
                "catch_up_center_sec": catch_up_center_sec,
                "ext_a_sec": ext_A_sec, "ext_b_sec": ext_B_sec,
                "overlap_sec": overlap_sec, "fine_align_shift_sec": sh,
                "t_kick_sec": t_kick, "composite_duration_sec": dur,
            },
            "outputs": {"preA2A": preA2A_path.name, "final": out_path.name},
            "kim_feedback": None,
        }
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"[done] {out_name}  ({time.time()-t_pair0:.1f}s)", flush=True)
    print("[all done]", flush=True)


if __name__ == "__main__":
    main()
