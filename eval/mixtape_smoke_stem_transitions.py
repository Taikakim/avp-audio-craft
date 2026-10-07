#!/usr/bin/env python
"""mixtape_smoke_stem_transitions.py — Stem-recomposed smoke transitions (Kim 2026-10-07).

Architecture:
1. Drums Dual-Stream (24 dB LR4 crossover at 800 Hz):
   - Low drums (<800 Hz, kick): lagged/asymmetric handover at ~80% downbeat alongside bass.
   - High drums (>800 Hz, hats/percussion): SA3 masked inpainting over middle 50% ([0.25L, 0.75L])
     with 1/8 L sine boundary crossfades and post-generation 800 Hz HP cleaning.
2. Bass Asymmetric Crossover:
   - Outgoing bass filtered down into downbeat H (~80%), incoming bass lands at H.
   - Rolling RMS leveling to guarantee 0 dB volume dip across the window.
3. "Other" (Synth/Melodic) Stems (5 Comparative Variants):
   - v1: baseline_audio_crossfade (energy-preserving)
   - v2: baseline_audio_filter_sweep (LP down + HP down towards 0 Hz from Nyquist)
   - v3: opt1_slerp (filtered stems -> SAME encode -> SLERP -> decode)
   - v4: opt2_slerp_a2a06 (Option 1 SLERP -> sine-bump A2A at nl=0.6)
   - v5: opt3_latentmix_a2a06 (raw latent mix -> sine-bump A2A at nl=0.6)
4. Residual:
   - Added back with equal-power gain for seamless boundary reconstruction.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import numpy as np
import soundfile as sf
import torch
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, fftconvolve, sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stable_audio_3 import StableAudioModel
from stable_audio_3.inference.longform import slerp

SR = 44100
BRIDGE_CKPT = "/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt"
FC_DRUM_CROSSOVER = 800.0


def lr4_sos(fc, kind):
    """Linkwitz-Riley 4th order (24 dB/octave). Flat sum magnitude."""
    fc = max(20.0, min(float(fc), SR / 2 - 100.0))
    return np.vstack([butter(2, fc, kind, fs=SR, output="sos")] * 2)


def lr4_filter(x, fc, kind):
    return sosfilt(lr4_sos(fc, kind), x, axis=-1).astype(np.float32)


def tv_filter(x, fc_of_n, kind, block=256):
    out = np.empty_like(x)
    cache, zi = {}, None
    for lo in range(0, x.shape[1], block):
        hi = min(lo + block, x.shape[1])
        fc = float(fc_of_n(np.array([(lo + hi) // 2]))[0])
        fc = max(20.0, min(fc, SR / 2 - 100.0))
        key = int(round(np.log(fc) / 0.01))
        if key not in cache:
            cache[key] = lr4_sos(float(np.exp(key * 0.01)), kind)
        sos = cache[key]
        if zi is None or zi.shape[0] != sos.shape[0]:
            zi = np.zeros((sos.shape[0], x.shape[0], 2))
        y, zi = sosfilt(sos, x[:, lo:hi], axis=-1, zi=zi)
        out[:, lo:hi] = y
    return out


def match_len(x, target_len):
    if x.shape[1] >= target_len:
        return x[:, :target_len]
    return np.pad(x, ((0, 0), (0, target_len - x.shape[1])), mode="edge")


def energy_preserving_crossfade(a, b, n):
    a = match_len(a, n)
    b = match_len(b, n)
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    denom = np.sqrt((1.0 - t) ** 2 + t ** 2)
    ga = (1.0 - t) / denom
    gb = t / denom
    return a * ga[None, :] + b * gb[None, :]


def sine_crossfade_seam(a, b, n_fade):
    th = np.linspace(0.0, np.pi / 2, n_fade, dtype=np.float32)
    wa = np.cos(th)[None, :]
    wb = np.sin(th)[None, :]
    return a * wa + b * wb


def rolling_rms(x, win_samples):
    p = np.mean(x ** 2, axis=0)
    w = np.ones(win_samples) / win_samples
    return np.sqrt(np.maximum(fftconvolve(p, w, mode="same"), 1e-12))


def safe_slerp(a, b, t, eps=1e-4):
    """Slerp with norm clamping to avoid zero-norm numerical issues."""
    na = a.norm(dim=1, keepdim=True)
    nb = b.norm(dim=1, keepdim=True)
    near_zero = (na < eps) | (nb < eps)
    slerped = slerp(a, b, t)
    linear = (1.0 - t) * a + t * b
    return torch.where(near_zero, linear, slerped)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shift-samples", type=int, default=None)
    ap.add_argument("--trans-idx", type=int, default=1, help="Transition index (default 1: clip 01 -> 02)")
    ap.add_argument("--stems-dir", default="/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_stems")
    ap.add_argument("--phase0-dir", default="/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0")
    ap.add_argument("--out-dir", default="/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_smoke")
    ap.add_argument("--staging-dir", default="/home/kim/staging/kone-mixtape/smoke")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(args.staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load transition metadata
    phase0 = Path(args.phase0_dir)
    tl = json.loads((phase0 / "timeline.json").read_text())
    meta = json.loads((phase0 / "run_meta.json").read_text())
    order = json.loads((phase0 / "order_used.json").read_text())
    dbc = json.loads((phase0 / "downbeats_native.json").read_text())

    k = args.trans_idx
    c1_id = order[k]["id"]
    c2_id = order[k + 1]["id"]
    stems_a_dir = Path(args.stems_dir) / f"{k:02d}"
    stems_b_dir = Path(args.stems_dir) / f"{k+1:02d}"

    print(f"[smoke] Transition {k}: {c1_id[:35]} -> {c2_id[:35]}", flush=True)

    t_start, t_end = tl["trans"][k]
    L_sec = t_end - t_start
    L = int(round(L_sec * SR))
    shift_samp = args.shift_samples if args.shift_samples is not None else meta["transitions"][k]["shift_samples"]

    db1 = np.array(dbc[c1_id])
    db2 = np.array(dbc[c2_id])
    bounds = json.loads(Path("/tmp/bounds_structural.json").read_text())
    bk1 = bounds[c1_id]
    bk2 = bounds[c2_id]
    out_s1 = float(db1[np.argmin(abs(db1 - bk1["end_pre_zc"]))])
    out_i1 = int(np.argmin(abs(db1 - out_s1)))
    W = meta["transitions"][k]["window_bars"]
    p1 = int(round(db1[out_i1 - W] * SR))
    in_s2 = float(db2[np.argmin(abs(db2 - bk2["start"]))])
    in_i2 = int(np.argmin(abs(db2 - in_s2)))
    p2 = int(round(db2[in_i2] * SR))

    print(f"  Window: L={L_sec:.2f}s ({L} samples, {W} bars), A cut={p1/SR:.2f}s, B cut={p2/SR:.2f}s, shift={shift_samp}", flush=True)

    # 2. Load stems and ensure exact length L
    def load_stem(stem_dir, name):
        f = stem_dir / f"{name}.wav"
        x, sr = sf.read(str(f), dtype="float32")
        assert sr == SR
        return x.T.copy()

    drums_A = match_len(load_stem(stems_a_dir, "drums")[:, p1 : p1 + L], L)
    bass_A = match_len(load_stem(stems_a_dir, "bass")[:, p1 : p1 + L], L)
    other_A = match_len(load_stem(stems_a_dir, "other")[:, p1 : p1 + L] + load_stem(stems_a_dir, "vocals")[:, p1 : p1 + L], L)
    res_A = match_len(load_stem(stems_a_dir, "residual")[:, p1 : p1 + L], L)

    b_start = max(0, p2 + shift_samp)
    drums_B = match_len(load_stem(stems_b_dir, "drums")[:, b_start : b_start + L], L)
    bass_B = match_len(load_stem(stems_b_dir, "bass")[:, b_start : b_start + L], L)
    other_B = match_len(load_stem(stems_b_dir, "other")[:, b_start : b_start + L] + load_stem(stems_b_dir, "vocals")[:, b_start : b_start + L], L)
    res_B = match_len(load_stem(stems_b_dir, "residual")[:, b_start : b_start + L], L)

    res_mix = energy_preserving_crossfade(res_A, res_B, L)

    # Handover downbeat calculation for both Kick (<800 Hz) and Bass
    a_db_win = (db1 - p1 / SR) * SR
    # Handover H is exactly 4 bars into the window (W_half)
    H = int(a_db_win[out_i1 - W + 4])
    pass # cand_db = a_db_win[(a_db_win > 0.65 * L) & (a_db_win < 0.92 * L)]
    h_idx = H # int(cand_db[np.argmin(abs(cand_db - 0.80 * L))]) if len(cand_db) else int(0.80 * L)
    print(f"[handover] Shared downbeat H: sample {h_idx} ({h_idx/SR:.2f}s / {h_idx/L*100:.1f}% of window)", flush=True)

    # 3. Process Bass (Asymmetric Handover + Rolling RMS Leveling)
    print("[bass] Asymmetric crossover with rolling RMS leveling...", flush=True)
    fade_len = int(round(0.040 * SR))
    bass_out_A = np.zeros((2, L), dtype=np.float32)
    bass_out_A[:, :h_idx - fade_len // 2] = bass_A[:, :h_idx - fade_len // 2]
    th = np.linspace(0, np.pi / 2, fade_len, dtype=np.float32)
    ramp_down = np.cos(th)[None, :]
    bass_out_A[:, h_idx - fade_len // 2 : h_idx + fade_len // 2] = (
        bass_A[:, h_idx - fade_len // 2 : h_idx + fade_len // 2] * ramp_down
    )

    bass_out_B = np.zeros((2, L), dtype=np.float32)
    ramp_len = L - h_idx
    th_in = np.linspace(0, np.pi / 2, ramp_len, dtype=np.float32)
    ramp_up = np.sin(th_in)[None, :]
    bass_out_B[:, h_idx:] = bass_B[:, h_idx:] * ramp_up
    bass_mix_raw = bass_out_A + bass_out_B

    # Rolling RMS leveling
    bar_samp = int(round(4 * 60.0 / 136.0 * SR))
    rms_a_target = np.sqrt(np.mean(bass_A[:, :h_idx] ** 2))
    rms_b_target = np.sqrt(np.mean(bass_B[:, h_idx:] ** 2))
    t_curve = np.linspace(0.0, 1.0, L, dtype=np.float32)
    target_rms_envelope = (1.0 - t_curve) * rms_a_target + t_curve * rms_b_target
    current_rms = rolling_rms(bass_mix_raw, bar_samp)
    rms_ratio = np.clip(target_rms_envelope / np.maximum(current_rms, 1e-6), 0.7, 1.4)
    rms_ratio_smooth = gaussian_filter1d(rms_ratio, sigma=bar_samp // 4)
    bass_mix = match_len(bass_mix_raw * rms_ratio_smooth[None, :], L)
    sf.write(str(out_dir / "smoke_bass_asymmetric.wav"), bass_mix.T, SR, subtype="FLOAT")

    # 4. Drums: 24 dB LR4 Crossover at 800 Hz
    print(f"[drums] 24 dB LR4 crossover at {FC_DRUM_CROSSOVER:.0f} Hz...", flush=True)
    drums_A_low = match_len(lr4_filter(drums_A, FC_DRUM_CROSSOVER, "low"), L)
    drums_A_high = match_len(lr4_filter(drums_A, FC_DRUM_CROSSOVER, "high"), L)
    drums_B_low = match_len(lr4_filter(drums_B, FC_DRUM_CROSSOVER, "low"), L)
    drums_B_high = match_len(lr4_filter(drums_B, FC_DRUM_CROSSOVER, "high"), L)

    # Low Drums Stream (<800 Hz, Kick): Lagged handover on downbeat H (same as bass)
    drums_low_out_A = np.zeros((2, L), dtype=np.float32)
    drums_low_out_A[:, :h_idx - fade_len // 2] = drums_A_low[:, :h_idx - fade_len // 2]
    drums_low_out_A[:, h_idx - fade_len // 2 : h_idx + fade_len // 2] = (
        drums_A_low[:, h_idx - fade_len // 2 : h_idx + fade_len // 2] * ramp_down
    )

    drums_low_out_B = np.zeros((2, L), dtype=np.float32)
    drums_low_out_B[:, h_idx:] = drums_B_low[:, h_idx:] * ramp_up
    drums_low_mix = match_len(drums_low_out_A + drums_low_out_B, L)

    # High Drums Stream (>800 Hz, Hats/Percussion): SA3 masked inpainting over middle 50%
    print("[drums-high] Masked inpainting (>800 Hz) over middle 50%...", flush=True)
    w_lo = 0.25 * L_sec
    w_hi = 0.75 * L_sec
    i_lo = int(round(w_lo * SR))
    i_hi = int(round(w_hi * SR))

    drum_high_ref = np.zeros((2, L), dtype=np.float32)
    drum_high_ref[:, :i_lo] = drums_A_high[:, :i_lo]
    drum_high_ref[:, i_hi:] = drums_B_high[:, i_hi:]

    # 5. Load SA3 model
    print("[model] Loading SA3 + merging adapter...", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([BRIDGE_CKPT])
    from model_matrix_gen import merge_adapters
    merge_adapters(model.model)
    pre = model.model.pretransform
    dtype = next(pre.parameters()).dtype
    device = "cuda"

    # Inpaint high drum stream
    drum_high_inp_raw = model.generate(
        prompt="TrackType: Instrument, Instruments: hi-hats, cymbals, metallic percussion, 136 BPM",
        duration=L_sec,
        steps=args.steps,
        cfg_scale=args.cfg_scale,
        seed=args.seed,
        batch_size=1,
        sample_size=int((L_sec + 8) * SR),
        inpaint_audio=(SR, torch.tensor(drum_high_ref)),
        inpaint_mask_start_seconds=w_lo,
        inpaint_mask_end_seconds=w_hi,
    )[0].float().cpu().numpy()
    drum_high_inp_raw = match_len(drum_high_inp_raw, L)

    # Post-filter with 800 Hz highpass to eliminate sub-bleed
    drum_high_inp_clean = match_len(lr4_filter(drum_high_inp_raw, FC_DRUM_CROSSOVER, "high"), L)

    # Sinusoidal boundary crossfades with 25% overlap (1/8 L on each side)
    ov = int(round(0.125 * L))
    drums_high_mix = np.zeros((2, L), dtype=np.float32)
    s0_l, s1_l = max(0, i_lo - ov // 2), min(L, i_lo + ov // 2)
    fl_l = s1_l - s0_l
    drums_high_mix[:, :s0_l] = drums_A_high[:, :s0_l]
    drums_high_mix[:, s0_l:s1_l] = sine_crossfade_seam(drums_A_high[:, s0_l:s1_l], drum_high_inp_clean[:, s0_l:s1_l], fl_l)

    s0_r, s1_r = max(0, i_hi - ov // 2), min(L, i_hi + ov // 2)
    fl_r = s1_r - s0_r
    drums_high_mix[:, s1_l:s0_r] = drum_high_inp_clean[:, s1_l:s0_r]
    drums_high_mix[:, s0_r:s1_r] = sine_crossfade_seam(drum_high_inp_clean[:, s0_r:s1_r], drums_B_high[:, s0_r:s1_r], fl_r)
    drums_high_mix[:, s1_r:] = drums_B_high[:, s1_r:]

    # Recombine low and high drum streams
    drums_mix = match_len(drums_low_mix + drums_high_mix, L)
    sf.write(str(out_dir / "smoke_drums_inpainted.wav"), drums_mix.T, SR, subtype="FLOAT")

    # 6. "Other" Stems: 5 Comparative Variants
    print("[other] Processing 5 comparative variants...", flush=True)

    # Variant 1: baseline_audio_crossfade
    print("  -> Variant 1: baseline_audio_crossfade", flush=True)
    other_v1 = energy_preserving_crossfade(other_A, other_B, L)

    # Variant 2: baseline_audio_filter_sweep
    print("  -> Variant 2: baseline_audio_filter_sweep", flush=True)
    fc_lp = lambda n: 18000.0 * (40.0 / 18000.0) ** (np.asarray(n, dtype=np.float64) / L)
    fc_hp = lambda n: 18000.0 * (20.0 / 18000.0) ** (np.asarray(n, dtype=np.float64) / L)
    other_A_lp = match_len(tv_filter(other_A, fc_lp, "low"), L)
    other_B_hp = match_len(tv_filter(other_B, fc_hp, "high"), L)
    other_v2 = energy_preserving_crossfade(other_A_lp, other_B_hp, L)

    # Variant 3: opt1_slerp (filtered stems -> SAME encode -> SLERP -> decode)
    print("  -> Variant 3: opt1_slerp", flush=True)
    with torch.inference_mode():
        zA_filt = pre.encode(torch.tensor(other_A_lp, device=device, dtype=dtype).unsqueeze(0)).float()
        zB_filt = pre.encode(torch.tensor(other_B_hp, device=device, dtype=dtype).unsqueeze(0)).float()
        Tz = min(zA_filt.shape[-1], zB_filt.shape[-1])
        t_ramp = torch.linspace(0.0, 1.0, Tz, device=device).view(1, 1, -1)
        z_slerp = safe_slerp(zA_filt[..., :Tz], zB_filt[..., :Tz], t_ramp)
        z_slerp = torch.clamp(z_slerp, -3.5, 3.5)
        other_v3 = pre.decode(z_slerp.to(dtype))[0].float().cpu().numpy()
        other_v3 = match_len(other_v3, L)

    # Variant 4: opt2_slerp_a2a06 (Variant 3 -> sine-bump A2A at nl=0.6)
    print("  -> Variant 4: opt2_slerp_a2a06", flush=True)
    nl_peak = 0.6
    depth_shape = torch.sin(torch.linspace(0, torch.pi, Tz, device=device)) * nl_peak
    depth = depth_shape.view(1, 1, -1)
    eps_ref = torch.randn_like(z_slerp)

    def cb_slerp(d, _z=z_slerp, _e=eps_ref, _d=depth):
        x, tt = d["x"], float(d["t"][0])
        n_f = min(x.shape[-1], _z.shape[-1])
        hold = (_d[..., :n_f] < tt)
        ref_t = ((1 - tt) * _z[..., :n_f] + tt * _e[..., :n_f]).to(x.device, x.dtype)
        x[..., :n_f].copy_(torch.where(hold.to(x.device), ref_t, x[..., :n_f]))

    other_v4 = model.generate(
        prompt="TrackType: Instrument, Instruments: synthesizer, atmospheric pads, goa trance melodies",
        duration=L_sec,
        steps=args.steps,
        cfg_scale=args.cfg_scale,
        seed=args.seed,
        batch_size=1,
        sample_size=int((L_sec + 8) * SR),
        init_audio=(SR, torch.tensor(other_v3)),
        init_noise_level=nl_peak,
        callback=cb_slerp,
    )[0].float().cpu().numpy()
    other_v4 = match_len(other_v4, L)

    # Variant 5: opt3_latentmix_a2a06 (raw latent mix + sine-bump A2A nl=0.6)
    print("  -> Variant 5: opt3_latentmix_a2a06", flush=True)
    with torch.inference_mode():
        zA_raw = pre.encode(torch.tensor(other_A, device=device, dtype=dtype).unsqueeze(0)).float()
        zB_raw = pre.encode(torch.tensor(other_B, device=device, dtype=dtype).unsqueeze(0)).float()
        z_mix = zA_raw[..., :Tz] * (1.0 - t_ramp) + zB_raw[..., :Tz] * t_ramp
        other_v5_init = pre.decode(z_mix.to(dtype))[0].float().cpu().numpy()
        other_v5_init = match_len(other_v5_init, L)

    eps_ref5 = torch.randn_like(z_mix)
    def cb_mix(d, _z=z_mix, _e=eps_ref5, _d=depth):
        x, tt = d["x"], float(d["t"][0])
        n_f = min(x.shape[-1], _z.shape[-1])
        hold = (_d[..., :n_f] < tt)
        ref_t = ((1 - tt) * _z[..., :n_f] + tt * _e[..., :n_f]).to(x.device, x.dtype)
        x[..., :n_f].copy_(torch.where(hold.to(x.device), ref_t, x[..., :n_f]))

    other_v5 = model.generate(
        prompt="TrackType: Instrument, Instruments: synthesizer, atmospheric pads, goa trance melodies",
        duration=L_sec,
        steps=args.steps,
        cfg_scale=args.cfg_scale,
        seed=args.seed,
        batch_size=1,
        sample_size=int((L_sec + 8) * SR),
        init_audio=(SR, torch.tensor(other_v5_init)),
        init_noise_level=nl_peak,
        callback=cb_mix,
    )[0].float().cpu().numpy()
    other_v5 = match_len(other_v5, L)

    variants = {"baseline_audio_crossfade": other_v1}

    # 7. Assemble full master transitions
    print("[assemble] Compiling full master transitions...", flush=True)
    report = {}
    for name, other_stem in variants.items():
        full_mix = drums_mix + bass_mix + other_stem + res_mix
        peak = float(np.abs(full_mix).max())
        full_mix = full_mix * (10 ** (-0.5 / 20.0)) / max(peak, 1e-9)

        wav_path = out_dir / f"smoke_trans{k:02d}_{name}.wav"
        other_path = out_dir / f"smoke_trans{k:02d}_other_{name}.wav"
        sf.write(str(wav_path), full_mix.T, SR, subtype="PCM_16")
        sf.write(str(other_path), other_stem.T, SR, subtype="PCM_16")

        shutil.copy2(wav_path, staging_dir / wav_path.name)
        shutil.copy2(other_path, staging_dir / other_path.name)

        mid_s = L // 2
        rms_mid = 20 * np.log10(np.sqrt(np.mean(full_mix[:, mid_s - SR : mid_s + SR] ** 2)))
        rms_start = 20 * np.log10(np.sqrt(np.mean(full_mix[:, :SR] ** 2)))
        rms_end = 20 * np.log10(np.sqrt(np.mean(full_mix[:, -SR:] ** 2)))
        report[name] = {
            "peak": peak,
            "rms_start_db": float(rms_start),
            "rms_mid_db": float(rms_mid),
            "rms_end_db": float(rms_end),
            "mid_vs_mean_endpoints_db": float(rms_mid - (rms_start + rms_end) / 2),
        }
        print(f"  {name:28s}: mid_vs_endpoints={report[name]['mid_vs_mean_endpoints_db']:+.2f} dB", flush=True)

    shutil.copy2(out_dir / "smoke_drums_inpainted.wav", staging_dir / f"smoke_trans{k:02d}_drums_inpainted.wav")
    shutil.copy2(out_dir / "smoke_bass_asymmetric.wav", staging_dir / f"smoke_trans{k:02d}_bass_asymmetric.wav")

    (out_dir / f"smoke_trans{k:02d}_report.json").write_text(json.dumps(report, indent=2))
    print(f"[done] All smoke transitions written to {out_dir} and staged at {staging_dir}", flush=True)


if __name__ == "__main__":
    main()
