#!/usr/bin/env python3
"""stereo_phase_meter.py — DoRA inter-channel-phase / comb-artifact diagnostic meter.

Sibling of eval/width_metric.py. Implements the band-resolved stereo-phase metrics
from the "DoRA inter-channel-phase / comb-artifact" test plan (pass 1, existing-audio):

  (a) L/R magnitude-squared coherence gamma^2(f)  — per band + broadband + time-resolved
  (b) mid/side energy ratio                        — per band + over time (mean/std/early/late)
  (c) stereo width / L-R correlation (broadband)   — REUSED from width_metric.width_stats
  (d) comb / early-reflection detector             — mid-channel real cepstrum (0.5-20 ms)
  (e) vector-sum deficit                           — per band (mid-collapse / phase-cancellation)

Design notes / reuse (do NOT re-derive — see CLAUDE.md discovery rule):
  * read_audio        <- mir core.file_utils         (soundfile convention: stereo -> (N, 2) float32)
  * width_stats       <- eval/width_metric.py        (metric (c); wraps ExpandedExtractor._stereo_fields,
                                                       the same corpus meter, so numbers are comparable)
  * STFT / coherence  <- scipy.signal (stft, coherence) — the only genuinely new machinery here.
  * (latch.lagged_xcorr was evaluated for the secondary comb ripple cross-check per the plan but
     is unsuitable — it always includes lag 0 and returns the trivial autocorrelation self-peak;
     replaced by a guarded normalized autocorrelation over comb-plausible lags. See _comb_detector.)

This pass writes ONLY a standalone JSON sidecar (--out); it never mutates the corpus run_meta.json
(unlike width_metric.py). Mono files are reported and skipped — they cannot test inter-channel phase.

Run (mir venv — REQUIRED; width_stats pulls the mir ExpandedExtractor):
  /home/kim/Projects/mir/mir/bin/python eval/stereo_phase_meter.py \
      --out /path/phase_metrics.json  <wav_or_dir> [<wav_or_dir> ...]  [--label NAME ...]

--label NAME applies to every file listed AFTER it (repeatable), so callers can group legs
(e.g. `--label base base__*.wav --label dora r16_originals__*.wav`). The parsed
(model, prompt, seed, epoch, step) is also emitted per clip when the filename matches the
avp_board_seeds template, for the downstream paired/Wilcoxon analysis.
"""
import json
import os
import re
import sys

# ---- hard import guard: fail loudly with a clear message (mir venv required) ----
try:
    sys.path.insert(0, "/home/kim/Projects/mir/src")
    sys.path.insert(0, "/home/kim/Projects/SAO/eval")
    sys.path.insert(0, "/home/kim/Projects/SAO/latch")
    import numpy as np
    from scipy.signal import stft, coherence
    from core.file_utils import read_audio            # mir
    from width_metric import width_stats              # eval/width_metric.py -> metric (c)
    from probe_layer_feature_map import lagged_xcorr  # latch -> secondary comb cross-check
except Exception as e:  # noqa: BLE001
    sys.stderr.write(
        "FATAL: stereo_phase_meter.py could not import a required dependency.\n"
        f"  underlying error: {type(e).__name__}: {e}\n"
        "  This script MUST run under the mir venv, which provides numpy/scipy/soundfile,\n"
        "  the mir source tree (core.file_utils / ExpandedExtractor), and reaches the SAO\n"
        "  eval/ + latch/ modules that are added to sys.path above.\n"
        "  Correct invocation:\n"
        "    /home/kim/Projects/mir/mir/bin/python "
        "/home/kim/Projects/SAO/eval/stereo_phase_meter.py --out OUT.json FILE.wav ...\n"
    )
    sys.exit(2)

FS = 44100
NPERSEG = 2048       # ~46 ms, bin ~= 21.5 Hz
NOVERLAP = 1536      # 75%
EPS = 1e-12

# Fixed analysis bands (Hz) — where reverb/comb/room sit. Top band clamped to Nyquist.
BANDS = [(0, 250), (250, 500), (500, 1000), (1000, 2000),
         (2000, 4000), (4000, 8000), (8000, 16000), (16000, 22050)]
BAND_LABELS = [f"{lo}-{hi}" for lo, hi in BANDS]

# broadband coherence band (avoids DC rumble + brittle top octave)
BROAD_LO, BROAD_HI = 200.0, 8000.0

# comb / early-reflection quefrency window: 0.5-20 ms @ 44.1 kHz -> samples [22, 882]
COMB_Q_LO = int(round(0.0005 * FS))   # 22
COMB_Q_HI = int(round(0.0200 * FS))   # 882

# avp_board_seeds filename template (no zero-pad in the full grid; some tags are non-numeric)
_FNAME_RE = re.compile(
    r"^(?P<model>base|r16_originals)__epoch(?P<epoch>[0-9a-zA-Z]+)_"
    r"(?:step|)(?P<step>[0-9a-zA-Z]+)__(?P<prompt>[a-zA-Z0-9]+)__s(?P<seed>[a-zA-Z0-9]+)\.wav$"
)


def _band_masks(freqs):
    """Boolean bin masks for each fixed band, computed once against an STFT/coherence f-axis."""
    return [((freqs >= lo) & (freqs < hi)) for lo, hi in BANDS]


def _parse_name(basename):
    m = _FNAME_RE.match(basename)
    if not m:
        return {}
    d = m.groupdict()
    out = {"model": d["model"], "prompt": d["prompt"], "seed": "s" + d["seed"],
           "epoch_tag": d["epoch"], "step_tag": d["step"]}
    # numeric epoch/step when possible (full grid); leave None for tags like "05_fine"/"warm"
    for k_src, k_dst in (("epoch", "epoch_num"), ("step", "step_num")):
        try:
            out[k_dst] = int(d[k_src])
        except ValueError:
            out[k_dst] = None
    return out


def _coherence_bands(l, r, masks):
    """Whole-signal magnitude-squared coherence gamma^2(f) -> per-band means + broadband mean."""
    f, cxy = coherence(l, r, fs=FS, window="hann", nperseg=NPERSEG, noverlap=NOVERLAP)
    band = [float(np.mean(cxy[m])) if m.any() else float("nan") for m in masks]
    bb_mask = (f >= BROAD_LO) & (f < BROAD_HI)
    broadband = float(np.mean(cxy[bb_mask])) if bb_mask.any() else float("nan")
    return band, broadband, f


def _coherence_timeresolved(l, r, masks):
    """Coherence over 2 s sliding windows (hop 1 s) -> per-band mean & std across windows."""
    win, hop = 2 * FS, 1 * FS
    n = len(l)
    per_win = []  # list of per-band vectors
    if n >= win:
        starts = range(0, n - win + 1, hop)
        for s0 in starts:
            fw, cw = coherence(l[s0:s0 + win], r[s0:s0 + win], fs=FS,
                               window="hann", nperseg=NPERSEG, noverlap=NOVERLAP)
            per_win.append([float(np.mean(cw[m])) if m.any() else np.nan for m in masks])
    if not per_win:
        return [None] * len(BANDS), [None] * len(BANDS), 0
    arr = np.asarray(per_win)  # (n_win, n_band)
    return ([float(x) for x in np.nanmean(arr, axis=0)],
            [float(x) for x in np.nanstd(arr, axis=0)],
            int(arr.shape[0]))


def _stft_ms_metrics(l, r, masks):
    """STFT-domain mid/side energy ratio (b) and vector-sum deficit (e), per band + over time."""
    _, _, L = stft(l, fs=FS, window="hann", nperseg=NPERSEG, noverlap=NOVERLAP)
    _, _, R = stft(r, fs=FS, window="hann", nperseg=NPERSEG, noverlap=NOVERLAP)
    M = 0.5 * (L + R)
    S = 0.5 * (L - R)
    aM2, aS2 = np.abs(M) ** 2, np.abs(S) ** 2
    side_ratio = aS2 / (aM2 + aS2 + EPS)                       # (f, t) in [0,1]
    vsd = np.abs(L + R) / (np.abs(L) + np.abs(R) + EPS)        # (f, t), 1=in-phase -> 0=anti

    side_ratio_band = [float(side_ratio[m].mean()) if m.any() else float("nan") for m in masks]
    vsd_band = [float(vsd[m].mean()) if m.any() else float("nan") for m in masks]

    # time series: mean over frequency per frame (mirror width_stats early/late quarter split)
    sr_ts = side_ratio.mean(axis=0)
    nt = len(sr_ts)
    q = max(1, nt // 4)
    side_ts = {
        "side_ratio_mean": float(sr_ts.mean()),
        "side_ratio_std": float(sr_ts.std()),
        "side_ratio_early": float(sr_ts[:q].mean()),
        "side_ratio_late": float(sr_ts[-q:].mean()),
    }
    return side_ratio_band, vsd_band, side_ts


def _comb_detector(mid):
    """(d) Mid-channel real-cepstrum comb / early-reflection detector.

    Framed 4096-hann, hop 2048; per frame ceps = irfft(log(|rfft|+eps)); scan the
    0.5-20 ms quefrency window for the dominant reflection peak. Secondary cross-check:
    lagged_xcorr autocorrelation ripple of the frame-averaged log-magnitude spectrum.
    """
    frame, hop = 4096, 2048
    win = np.hanning(frame)
    peaks, lags_ms, logmags = [], [], []
    for s0 in range(0, max(1, len(mid) - frame + 1), hop):
        seg = mid[s0:s0 + frame]
        if len(seg) < frame:
            break
        mag = np.abs(np.fft.rfft(seg * win))
        logmag = np.log(mag + EPS)
        ceps = np.fft.irfft(logmag)
        qwin = np.abs(ceps[COMB_Q_LO:COMB_Q_HI])
        if qwin.size:
            k = int(np.argmax(qwin))
            peaks.append(float(qwin[k]))
            lags_ms.append((COMB_Q_LO + k) / FS * 1000.0)
        logmags.append(logmag)

    if not peaks:
        return {"comb_peak_median": None, "comb_peak_p95": None,
                "comb_lag_ms_modal": None, "comb_xcorr_secondary": None, "comb_n_frames": 0}

    peaks_a = np.asarray(peaks)
    lags_a = np.asarray(lags_ms)
    # modal lag: coarse 0.5 ms histogram over the quefrency window
    edges = np.arange(0.5, 20.0 + 0.5, 0.5)
    hist, _ = np.histogram(lags_a, bins=edges)
    modal_lag = float((edges[int(np.argmax(hist))] + 0.25)) if hist.sum() else float(np.median(lags_a))

    # secondary: ripple periodicity of the mean log-mag spectrum (a comb from a delay tau imprints
    # a periodic ripple of period 1/tau Hz on the spectrum -> an autocorrelation side-peak).
    # NOTE (deviation, see header): the plan named latch.lagged_xcorr for this, but it always
    # includes lag 0 / the trivial self-alignment and returns the global |corr| max, which for an
    # autocorrelation is unavoidably 1.0 -- it cannot be constrained to a non-zero lag band. So the
    # ripple is measured with a guarded normalized autocorrelation over comb-plausible lags instead;
    # lagged_xcorr's signed-Pearson convention is kept in spirit. Comb tau in [0.5,20] ms -> ripple
    # period [50,2000] Hz -> ~[2,93] STFT bins (bin ~= 21.5 Hz).
    mean_lm = np.asarray(logmags).mean(axis=0)
    mean_lm = mean_lm - mean_lm.mean()
    lo_bin, hi_bin = 2, min(93, len(mean_lm) // 2 - 1)
    if hi_bin > lo_bin and np.any(mean_lm):
        ac = np.correlate(mean_lm, mean_lm, mode="full")
        ac = ac[len(mean_lm) - 1:]           # non-negative lags
        ac = ac / (ac[0] + EPS)              # normalize by lag-0 energy
        seg = ac[lo_bin:hi_bin + 1]
        k = int(np.argmax(seg))
        xlag = lo_bin + k                     # ripple period in STFT bins
        xcorr = float(seg[k])                 # ripple strength (normalized autocorr side-peak)
    else:
        xlag, xcorr = 0, 0.0

    return {
        "comb_peak_median": float(np.median(peaks_a)),
        "comb_peak_p95": float(np.percentile(peaks_a, 95)),
        "comb_lag_ms_modal": modal_lag,
        "comb_xcorr_secondary": {"lag_bins": int(xlag), "corr": float(xcorr)},
        "comb_n_frames": int(len(peaks)),
    }


def analyze(path):
    """Full per-clip metric dict, or {'mono_source': True} / {'error': ...} on skip."""
    raw, sr = read_audio(path)
    raw = np.asarray(raw)
    if raw.ndim == 1 or raw.shape[-1] != 2:
        return {"mono_source": True, "note": "not 2-channel; cannot test inter-channel phase"}
    if sr != FS:
        # bands / quefrency windows are calibrated to 44.1 kHz; record but proceed with actual sr note
        return {"error": f"unexpected sample rate {sr} (expected {FS}); skipped"}

    l = raw[:, 0].astype(np.float64)
    r = raw[:, 1].astype(np.float64)
    mid = 0.5 * (l + r)
    masks_cxy = None

    coh_band, coh_bb, fcxy = _coherence_bands(l, r, _band_masks(
        coherence(l[:NPERSEG * 4], r[:NPERSEG * 4], fs=FS, window="hann",
                  nperseg=NPERSEG, noverlap=NOVERLAP)[0]))
    # (recompute masks on the real coherence f-axis to be exact)
    masks_cxy = _band_masks(fcxy)
    coh_band, coh_bb, _ = _coherence_bands(l, r, masks_cxy)
    coh_ts_mean, coh_ts_std, n_win = _coherence_timeresolved(l, r, masks_cxy)

    # STFT f-axis for the mid/side + vsd bands
    fstft, _, _ = stft(l[:NPERSEG * 4], fs=FS, window="hann", nperseg=NPERSEG, noverlap=NOVERLAP)
    masks_stft = _band_masks(fstft)
    side_ratio_band, vsd_band, side_ts = _stft_ms_metrics(l, r, masks_stft)

    comb = _comb_detector(mid)
    wstats = width_stats(path)  # metric (c) — broadband width/corr controls

    def _round(x):
        return None if x is None else (round(x, 6) if isinstance(x, float) else x)

    return {
        "n_samples": int(raw.shape[0]),
        "duration_s": round(raw.shape[0] / FS, 3),
        "band_labels": BAND_LABELS,
        # (a)
        "coh_band": [_round(x) for x in coh_band],
        "coh_broadband": _round(coh_bb),
        "coh_band_ts_mean": [_round(x) for x in coh_ts_mean],
        "coh_band_ts_std": [_round(x) for x in coh_ts_std],
        "coh_n_windows": n_win,
        # (b)
        "side_ratio_band": [_round(x) for x in side_ratio_band],
        **{k: _round(v) for k, v in side_ts.items()},
        # (e)
        "vsd_band": [_round(x) for x in vsd_band],
        # (d)
        **{k: (_round(v) if not isinstance(v, dict) else v) for k, v in comb.items()},
        # (c) broadband controls
        "width_stats": wstats,
    }


def _expand_args(argv):
    """Manual parse: --out PATH, --label NAME (applies to following files), files/dirs."""
    out_path, cur_label = None, None
    items = []  # (path, label)
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            i += 1
            out_path = argv[i] if i < len(argv) else None
        elif a == "--label":
            i += 1
            cur_label = argv[i] if i < len(argv) else None
        elif a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        elif os.path.isdir(a):
            for f in sorted(os.listdir(a)):
                if f.lower().endswith((".wav", ".flac")):
                    items.append((os.path.join(a, f), cur_label))
        else:
            items.append((a, cur_label))
        i += 1
    return out_path, items


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 1
    out_path, items = _expand_args(argv)
    if out_path is None:
        sys.stderr.write("FATAL: --out PATH is required.\n")
        return 2
    if not items:
        sys.stderr.write("FATAL: no input audio files given.\n")
        return 2

    report, rows = {}, []
    n_mono, n_err = 0, 0
    for path, label in items:
        base = os.path.basename(path)
        try:
            res = analyze(path)
        except Exception as e:  # noqa: BLE001 — one bad clip must not abort the batch
            res = {"error": f"{type(e).__name__}: {e}"}
        if label is not None:
            res["label"] = label
        res.update(_parse_name(base))
        report[base] = res
        if res.get("mono_source"):
            n_mono += 1
            print(f"[skip mono] {base}")
            continue
        if res.get("error"):
            n_err += 1
            print(f"[skip err ] {base}: {res['error']}")
            continue
        rows.append((base, res))

    # human-readable summary table to stdout
    if rows:
        cols = ["coh_bb", "coh_1-2k", "coh_2-4k", "coh_4-8k",
                "sr_2-4k", "vsd_2-4k", "comb_p50", "comb_p95", "width", "corr"]
        hdr = f"{'clip':52s} " + " ".join(f"{c:>9s}" for c in cols)
        print("\n" + hdr)
        print("-" * len(hdr))
        for base, r in rows:
            cb, sb, vb = r["coh_band"], r["side_ratio_band"], r["vsd_band"]
            w = r.get("width_stats", {})

            def g(x):
                return f"{x:9.4f}" if isinstance(x, (int, float)) else f"{'--':>9s}"
            vals = [r["coh_broadband"], cb[3], cb[4], cb[5],
                    sb[4], vb[4], r["comb_peak_median"], r["comb_peak_p95"],
                    w.get("width_mean"), w.get("corr_mean")]
            print(f"{base[:52]:52s} " + " ".join(g(v) for v in vals))
        print(f"\n(bands: {', '.join(BAND_LABELS)} Hz)")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    meta = {"_config": {"fs": FS, "nperseg": NPERSEG, "noverlap": NOVERLAP,
                        "bands_hz": BANDS, "broadband_hz": [BROAD_LO, BROAD_HI],
                        "comb_quefrency_samples": [COMB_Q_LO, COMB_Q_HI]},
            "clips": report}
    tmp = out_path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, out_path)
    print(f"\n[phase] {len(rows)} analyzed, {n_mono} mono-skipped, {n_err} err-skipped "
          f"-> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
