"""Tier-1 windowed-a2a breathing loop (#35, Kim's design; docs/a2a-loop-attractor.md).

Walks the source in overlapping windows; each window is re-rendered a2a at the
BreathingController's current init_noise_level; the OUTPUT window is measured for
recurrence+novelty (W's recurrence_meter3, injected); the controller sets the next
window's nl. Returns the crossfade-joined audio plus the per-window (nl, recurrence,
novelty) trajectories — the "does it breathe" eval artifact.

The loop (`breathing_loop`) is pure orchestration: `render` and `measure` are injected,
so it runs and tests with no GPU and no dependency on the meter's exact signature. Real
GPU adapters (`make_a2a_renderer`, `calibrate_source`) live at the bottom and are only
touched when running for real.
"""
from __future__ import annotations
import numpy as np


def plan_windows(total_sec: float, window_sec: float, overlap_sec: float):
    """Overlapping window plan over [0, total_sec]. Starts sit on a fixed stride grid
    (window - overlap) so every adjacent pair overlaps by exactly overlap_sec; the last
    window is clamped to end exactly at total_sec."""
    if overlap_sec >= window_sec:
        raise ValueError("overlap_sec must be < window_sec")
    stride = window_sec - overlap_sec
    wins = []
    start = 0.0
    while start < total_sec - 1e-9:
        end = min(start + window_sec, total_sec)
        wins.append((start, end))
        if end >= total_sec - 1e-9:
            break
        start += stride
    return wins


def _crossfade_join(pieces, sr: int, overlap_sec: float):
    """Equal-power (cos/sin) crossfade join over the overlap between consecutive
    output windows."""
    if len(pieces) == 1:
        return pieces[0]
    n = int(round(overlap_sec * sr))
    out = pieces[0]
    for nxt in pieces[1:]:
        m = min(n, out.shape[1], nxt.shape[1])
        if m <= 0:
            out = np.concatenate([out, nxt], axis=1)
            continue
        t = np.linspace(0, np.pi / 2, m, dtype=np.float32)
        fo, fi = np.cos(t), np.sin(t)
        seam = out[:, -m:] * fo + nxt[:, :m] * fi
        out = np.concatenate([out[:, :-m], seam, nxt[:, m:]], axis=1)
    return out


def breathing_loop(source, sr, window_sec, overlap_sec, render, measure, controller,
                   lookback_sec=40.0):
    """Run the closed-loop breathing a2a.

    source: (C, N) float array.  render(win_audio, nl)->out_audio (C, n).
    measure(context_audio, new_len)->(recurrence, novelty): measures the LAST `new_len`
    samples of the accumulated-output context — the loop is a phrase repeating ACROSS
    windows, so the meter needs lookback into prior windows (validation 2026-07-10:
    isolated-window measurement is blind to the long-range loop). controller:
    BreathingController. Returns (full_audio (C, ~N), traj dict nl/recurrence/novelty).
    """
    total_sec = source.shape[1] / sr
    wins = plan_windows(total_sec, window_sec, overlap_sec)
    pieces, nl_t, rec_t, nov_t = [], [], [], []
    accum = None
    for lo, hi in wins:
        chunk = source[:, int(lo * sr):int(hi * sr)]
        nl = controller.nl
        nl_t.append(nl)
        out = render(chunk, nl)
        pieces.append(out)
        accum = out if accum is None else np.concatenate([accum, out], axis=1)
        new_len = out.shape[1]
        ctx = accum[:, -(int(lookback_sec * sr) + new_len):]   # trailing lookback + new
        rec, nov = measure(ctx, new_len)
        rec_t.append(rec)
        nov_t.append(nov)
        controller.update(nov, recurrence=rec)   # novelty-primary; sets next window's nl
    full = _crossfade_join(pieces, sr, overlap_sec)
    return full, {"nl": nl_t, "recurrence": rec_t, "novelty": nov_t}


def _source_features(source, sr, window_sec, overlap_sec):
    """Per-window (onset_density, rms, hf_energy) for the ORIGINAL track (librosa).
    hf_energy = mean STFT magnitude in 3-6 kHz. One pass; break/fill/density flags derive
    from these."""
    import librosa
    mono = source.mean(axis=0).astype(np.float32) if source.ndim == 2 else source.astype(np.float32)
    ods, rms, hf = [], [], []
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    band = (freqs >= 3000) & (freqs <= 6000)
    for lo, hi in plan_windows(source.shape[-1] / sr, window_sec, overlap_sec):
        seg = mono[int(lo * sr):int(hi * sr)]
        ods.append(float(np.mean(librosa.onset.onset_strength(y=seg, sr=sr))) if seg.size else 0.0)
        rms.append(float(np.sqrt(np.mean(seg ** 2))) if seg.size else 0.0)
        S = np.abs(librosa.stft(seg, n_fft=2048)) if seg.size else np.zeros((1025, 1))
        hf.append(float(np.mean(S[band])) if band.any() else 0.0)
    return {"onset": ods, "rms": rms, "hf": hf}


def derive_source_flags(feats, break_pct=25.0, fill_pct=80.0):
    """Pure: from per-window features derive break / fill / low_density bool lists.
    break = quiet AND sparse (low tail of onset & rms); fill = burst (high tail of onset
    AND hf) with rms above the track mean; low_density = onset below the track mean."""
    od = np.asarray(feats["onset"], float)
    rm = np.asarray(feats["rms"], float)
    hf = np.asarray(feats["hf"], float)
    breaks = _flag_breaks(od, rm, pct=break_pct)
    od_hi, hf_hi, rm_mean = np.percentile(od, fill_pct), np.percentile(hf, fill_pct), rm.mean()
    fills = [(bool(o >= od_hi) and bool(h >= hf_hi) and bool(r > rm_mean))
             for o, h, r in zip(od, hf, rm)]
    low_density = [bool(o < od.mean()) for o in od]
    return {"break": breaks, "fill": fills, "low_density": low_density}


def _flag_breaks(onset_density, rms, pct=25.0):
    """A window is a SOURCE break/pause when BOTH its onset-density and RMS sit in the
    low tail of the source's own distribution (quiet AND sparse) — self-calibrated, so
    it adapts per track. Pure: takes the per-window arrays, returns a bool list."""
    od = np.asarray(onset_density, float)
    rm = np.asarray(rms, float)
    od_thr = np.percentile(od, pct)
    rm_thr = np.percentile(rm, pct)
    return [(bool(o <= od_thr) and bool(r <= rm_thr)) for o, r in zip(od, rm)]


def source_break_flags(source, sr, window_sec, overlap_sec, pct=25.0):
    """Per-window break flags for the ORIGINAL track (onset-density + RMS, librosa).
    Feedforward signal for BreathingControllerV2: duck nl hard where the source pauses."""
    import librosa
    mono = source.mean(axis=0).astype(np.float32) if source.ndim == 2 else source.astype(np.float32)
    ods, rms = [], []
    for lo, hi in plan_windows(source.shape[-1] / sr, window_sec, overlap_sec):
        seg = mono[int(lo * sr):int(hi * sr)]
        env = librosa.onset.onset_strength(y=seg, sr=sr)
        ods.append(float(np.mean(env)))
        rms.append(float(np.sqrt(np.mean(seg ** 2)) if seg.size else 0.0))
    return _flag_breaks(ods, rms, pct=pct)


def breathing_loop_v2(source, sr, window_sec, overlap_sec, render, measure, controller,
                      source_breaks, lookback_sec=40.0):
    """v2 loop: controller.step(source_break, prev_novelty) — feedforward source-break
    ducking + novelty feedback. source_breaks: per-window bool list (len == n windows)."""
    wins = plan_windows(source.shape[1] / sr, window_sec, overlap_sec)
    if len(source_breaks) != len(wins):
        raise ValueError(f"source_breaks {len(source_breaks)} != windows {len(wins)}")
    pieces, nl_t, rec_t, nov_t = [], [], [], []
    accum, prev_nov = None, None
    for k, (lo, hi) in enumerate(wins):
        nl = controller.step(source_break=source_breaks[k], prev_novelty=prev_nov)
        nl_t.append(nl)
        out = render(source[:, int(lo * sr):int(hi * sr)], nl)
        pieces.append(out)
        accum = out if accum is None else np.concatenate([accum, out], axis=1)
        new_len = out.shape[1]
        ctx = accum[:, -(int(lookback_sec * sr) + new_len):]
        rec, nov = measure(ctx, new_len)
        prev_nov = nov
        rec_t.append(rec)
        nov_t.append(nov)
    full = _crossfade_join(pieces, sr, overlap_sec)
    return full, {"nl": nl_t, "recurrence": rec_t, "novelty": nov_t, "source_break": list(source_breaks)}


def hf_envelope_var(audio, sr, lo=3000, hi=6000):
    """Scale-invariant temporal variance (CV^2) of the 3-6 kHz energy envelope. LOW =
    constant high-frequency energy = the 'static/stringy' averaging signature (Kim)."""
    import librosa
    mono = audio.mean(axis=0) if getattr(audio, "ndim", 1) == 2 else audio
    S = np.abs(librosa.stft(mono.astype(np.float32), n_fft=2048))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    env = S[(freqs >= lo) & (freqs <= hi)].sum(axis=0)
    m = float(env.mean())
    return float(np.var(env) / (m * m + 1e-12))


def calibrate_hf_static(source, sr, window_sec, overlap_sec, pct=25.0):
    """Threshold for OUTPUT HF-staticness = the source's own low-tail HF envelope variance;
    an output window below it is flatter-than-the-source = going static."""
    vs = [hf_envelope_var(source[:, int(lo * sr):int(hi * sr)], sr)
          for lo, hi in plan_windows(source.shape[1] / sr, window_sec, overlap_sec)]
    return float(np.percentile(vs, pct))


def breathing_loop_v3(source, sr, window_sec, overlap_sec, render, measure, controller,
                      source_flags, hf_static_thr, lookback_sec=40.0):
    """v3 loop: v3 controller driven by feedforward source flags (break/fill/low_density)
    + feedback (output novelty via `measure`, output HF-staticness via hf_envelope_var)."""
    wins = plan_windows(source.shape[1] / sr, window_sec, overlap_sec)
    brk, fil, low = source_flags["break"], source_flags["fill"], source_flags["low_density"]
    if not (len(brk) == len(fil) == len(low) == len(wins)):
        raise ValueError("source_flags length != n windows")
    pieces = []
    tr = {"nl": [], "recurrence": [], "novelty": [], "hf_var": [], "hf_static": [],
          "source_break": list(brk), "source_fill": list(fil), "source_low_density": list(low)}
    accum, prev_nov, prev_hf_static = None, None, False
    for k, (lo, hi) in enumerate(wins):
        nl = controller.step(source_break=brk[k], source_fill=fil[k], source_low_density=low[k],
                             prev_novelty=prev_nov, prev_hf_static=prev_hf_static)
        tr["nl"].append(nl)
        out = render(source[:, int(lo * sr):int(hi * sr)], nl)
        pieces.append(out)
        accum = out if accum is None else np.concatenate([accum, out], axis=1)
        new_len = out.shape[1]
        rec, nov = measure(accum[:, -(int(lookback_sec * sr) + new_len):], new_len)
        prev_nov = nov
        hfv = hf_envelope_var(out, sr)
        prev_hf_static = bool(hfv < hf_static_thr)
        tr["recurrence"].append(rec)
        tr["novelty"].append(nov)
        tr["hf_var"].append(hfv)
        tr["hf_static"].append(prev_hf_static)
    return _crossfade_join(pieces, sr, overlap_sec), tr


def make_novelty_measure(sr, curve_fn):
    """Adapt W's novelty_curve into measure(context_audio, new_len)->(rec, nov): run the
    curve over the whole trailing context, then reduce (nanmedian) over ONLY the patches
    that fall in the NEW window region (last new_len samples) — so the new window's
    novelty is measured WITH lookback into the preceding windows. curve_fn is injected
    (recurrence_meter.novelty_curve) so this stays importable without the mir dep."""
    def measure(ctx_audio, new_len):
        mono = ctx_audio.mean(axis=0).astype(np.float32)
        res = curve_fn(mono, sr=sr)
        t = np.asarray(res["time"], dtype=float)
        new_start = (ctx_audio.shape[1] - new_len) / sr
        mask = t >= new_start
        def red(key):
            a = np.asarray(res[key], dtype=float)[mask]
            return float(np.nanmedian(a)) if a.size and np.any(~np.isnan(a)) else float("nan")
        return red("recurrence"), red("novelty")
    return measure


# ---- real GPU / meter adapters (not unit-tested; need the model + W's meter) --------

def make_a2a_renderer(model, prompt, seed, steps, cfg):
    """Adapt an SA3 model into render(win_audio, nl) -> out_audio, via SDEdit a2a
    (mirrors eval/a2a_fulltrack.a2a: budget-sized generate with init_audio)."""
    import torch

    def render(win_audio, nl):
        a = torch.tensor(win_audio)
        dur = win_audio.shape[1] / model.model.sample_rate
        ds = model.model.pretransform.downsampling_ratio
        budget = int(np.ceil((dur + 8.0) * model.model.sample_rate / ds)) * ds
        out = model.generate(prompt=prompt, duration=dur, steps=steps, cfg_scale=cfg,
                             seed=seed, batch_size=1, sample_size=budget,
                             init_audio=(model.model.sample_rate, a),
                             init_noise_level=float(nl))
        return out[0].float().cpu().numpy()[:, :win_audio.shape[1]]
    return render


def calibrate_source(source, sr, window_sec, overlap_sec, measure,
                     rec_pct=95.0, nov_pct=5.0):
    """Self-calibrate the controller thresholds from the SOURCE's own windows: the
    source's recurrence ceiling (r_src_max = p95) and novelty floor (p5) — the loop
    is only 'too much' relative to what the original itself did (Kim's design)."""
    total_sec = source.shape[1] / sr
    recs, novs = [], []
    for lo, hi in plan_windows(total_sec, window_sec, overlap_sec):
        rec, nov = measure(source[:, int(lo * sr):int(hi * sr)])
        recs.append(rec)
        novs.append(nov)
    return {"r_src_max": float(np.percentile(recs, rec_pct)),
            "novelty_floor": float(np.percentile(novs, nov_pct))}
