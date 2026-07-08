"""envelope_fidelity.py — source-vs-output envelope meter (pad-fill stack item b).

Kim's 'envelope timings should stay close to the example' operationalized:
given a SOURCE and an OUTPUT (a2a render, transition, etc., time-aligned),
measure (1) onset-timing fidelity, (2) per-band RMS envelope fidelity, and
(3) the PAD-FILL score: excess sustained output energy where the source is
quiet/inactive — the under-constraint attractor's signature (airy drones
appearing in regions the source never asked for). Numpy+librosa only.

CLI: python envelope_fidelity.py source.wav output.wav [--json out.json]
"""
import argparse
import json

import numpy as np

BANDS = [("bass", 20, 250), ("body", 250, 1200), ("mid", 1200, 5000), ("air", 5000, 16000)]
HOP = 1024


def _mono(a):
    return a.mean(axis=0) if a.ndim > 1 else a


def band_rms_envelopes(y, sr, hop=HOP):
    """(n_bands, frames) RMS envelopes via STFT band pooling."""
    import librosa
    S = np.abs(librosa.stft(y, n_fft=4096, hop_length=hop)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)
    out = []
    for _, lo, hi in BANDS:
        m = (freqs >= lo) & (freqs < hi)
        out.append(np.sqrt(S[m].mean(axis=0) + 1e-12))
    return np.stack(out)


def onset_envelope(y, sr, hop=HOP):
    import librosa
    return librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)


def _corr(a, b):
    n = min(len(a), len(b))
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def measure(source, output, sr, region=None):
    """Both (C,N) or (N,) float arrays at the same sr. region=(lo_sec,hi_sec)
    restricts the measurement (e.g. a transition window). Returns a dict."""
    s, o = _mono(np.asarray(source)), _mono(np.asarray(output))
    n = min(len(s), len(o))
    s, o = s[:n], o[:n]
    if region:
        lo, hi = (max(0, int(region[0] * sr)), min(n, int(region[1] * sr)))
        s, o = s[lo:hi], o[lo:hi]

    on_s, on_o = onset_envelope(s, sr), onset_envelope(o, sr)
    eb_s, eb_o = band_rms_envelopes(s, sr), band_rms_envelopes(o, sr)

    band_corr = {name: _corr(eb_s[i], eb_o[i]) for i, (name, _, _) in enumerate(BANDS)}

    # pad-fill: frames where the SOURCE is quiet (below its own 25th pct energy,
    # no onset activity) but the OUTPUT carries sustained energy well above the
    # source's level there. Reported as coverage + mean excess dB.
    tot_s = eb_s.mean(axis=0)
    tot_o = eb_o.mean(axis=0)
    m = min(len(tot_s), len(tot_o), len(on_s))
    tot_s, tot_o, on_sc = tot_s[:m], tot_o[:m], on_s[:m]
    # <= not <: digital-silence frames form an exact-value plateau at the
    # percentile itself, and strict less-than excludes the whole plateau
    quiet = (tot_s <= np.percentile(tot_s, 25)) & (on_sc <= np.percentile(on_sc, 40))
    floor = np.percentile(tot_s, 25) + 1e-9
    excess = tot_o / np.maximum(tot_s, floor)
    fill = quiet & (excess > 2.0)          # output >6 dB over source in quiet zones
    pad_fill_frac = float(fill.mean())
    pad_fill_db = float(20 * np.log10(excess[fill]).mean()) if fill.any() else 0.0

    # v2 — SUSTAINED-FLOOR DELTA (pads layered BEHIND active content; v1's
    # quiet-zone detector can't see them on a busy track). Per band, the "floor"
    # is a rolling low-percentile of the RMS envelope (~3 s windows): the
    # sustained bed under the transients. A positive output-vs-source floor
    # delta = added drones/pads regardless of how busy the source is.
    win = max(8, int(3.0 * sr / HOP))
    floor_delta = {}
    from numpy.lib.stride_tricks import sliding_window_view
    for i, (name, _, _) in enumerate(BANDS):
        es, eo = eb_s[i][:m], eb_o[i][:m]
        if len(es) <= win:
            floor_delta[name] = 0.0
            continue
        fs = np.percentile(sliding_window_view(es, win), 20, axis=1)
        fo = np.percentile(sliding_window_view(eo, win), 20, axis=1)
        floor_delta[name] = float(np.median(20 * np.log10((fo + 1e-9) / (fs + 1e-9))))
    hi_bands = [floor_delta[b] for b in ("body", "mid", "air")]
    pad_floor_db = float(np.mean([max(0.0, d) for d in hi_bands]))

    # scale-free variant: FLOOR-TO-PEAK ratio delta per band — pads raise the
    # sustained floor RELATIVE to the track's own transients, independent of
    # overall density/mastering differences between source and render.
    ratio_delta = {}
    for i, (name, _, _) in enumerate(BANDS):
        es, eo = eb_s[i][:m], eb_o[i][:m]
        rs = np.percentile(es, 20) / (np.percentile(es, 95) + 1e-9)
        ro = np.percentile(eo, 20) / (np.percentile(eo, 95) + 1e-9)
        ratio_delta[name] = float(20 * np.log10((ro + 1e-9) / (rs + 1e-9)))
    pad_ratio_db = float(np.mean([max(0.0, ratio_delta[b]) for b in ("body", "mid", "air")]))

    return {
        "onset_corr": _corr(on_s, on_o),
        "band_corr": band_corr,
        "band_corr_mean": float(np.mean(list(band_corr.values()))),
        "pad_fill_frac": pad_fill_frac,
        "pad_fill_db": pad_fill_db,
        "floor_delta_db": floor_delta,
        "pad_floor_db": pad_floor_db,
        "floor_peak_ratio_delta_db": ratio_delta,
        "pad_ratio_db": pad_ratio_db,
        "frames": int(m),
    }


def main():
    import soundfile as sf
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("output")
    ap.add_argument("--region", default=None, help="lo,hi seconds")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    s, sr1 = sf.read(args.source, dtype="float32", always_2d=True)
    o, sr2 = sf.read(args.output, dtype="float32", always_2d=True)
    assert sr1 == sr2, "sample-rate mismatch"
    region = tuple(float(x) for x in args.region.split(",")) if args.region else None
    rep = measure(s.T, o.T, sr1, region=region)
    print(json.dumps(rep, indent=2))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=2)


if __name__ == "__main__":
    main()
