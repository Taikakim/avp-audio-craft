#!/usr/bin/env python
"""mixtape_audit_kick.py — v7 gate 2 at ~1 ms: kick spacing across every transition, with clip bodies as control.

WHY (GHOST-NOTE 2026-10-07, C's item B): mixtape_audit_grid.py reads madmom beats, which sit on a 10 ms grid, so
a single 20 ms 'failure' is two grid steps of quantisation. Here kick onsets come from the 40-150 Hz Hilbert
envelope of the FINISHED mix, peak-picked on its derivative at the full sample rate (~1 ms after smoothing), and
each transition window (+- margin) is compared with the same measure on clip BODIES (no transition), which is the
noise floor of the method on this material. A window is only 'off' if it is clearly worse than the bodies.

USAGE  .venv/bin/python eval/mixtape_audit_kick.py --mix MIX.wav --timeline timeline.json [--tol 15] [--json OUT]
Run from a dir that is not the SAO root.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, find_peaks, hilbert, resample_poly, sosfiltfilt


def kick_onsets(x, sr, beats, half=0.045):
    """madmom beats (10 ms grid) refined to the kick onset: argmax of the rising edge of the 40-150 Hz envelope within
    +-45 ms of each beat, ~0.25 ms resolution (decimated to 4 kHz). Beat SELECTION stays madmom's, so a 16th-note bass
    pulse cannot be mistaken for a kick; only the QUANTISATION is removed."""
    m = x.mean(1) if x.ndim == 2 else x
    m = resample_poly(m, 1, 11)                           # 44.1k -> 4.0091 kHz
    fs = sr / 11
    b = sosfiltfilt(butter(4, (40, 150), "bandpass", fs=fs, output="sos"), m)
    env = np.abs(hilbert(b))
    env = sosfiltfilt(butter(2, 60, "low", fs=fs, output="sos"), env)
    d = np.gradient(env)
    d = np.clip(d, 0, None)
    w = int(half * fs)
    out = []
    for t in beats:
        c = int(round(t * fs))
        lo, hi = max(0, c - w), min(len(d), c + w)
        if hi - lo < 4:
            continue
        out.append((lo + int(np.argmax(d[lo:hi]))) / fs)
    return np.array(out)


def ibi_dev(ons):
    if len(ons) < 6:
        return None
    ibi = np.diff(ons)
    ref = np.median(ibi)
    ok = np.abs(ibi - ref) < 0.5 * ref                     # drop missed/double detections (a skipped kick = 2x)
    ibi = ibi[ok]
    return 1000 * (ibi - np.median(ibi)) if len(ibi) >= 4 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mix", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--tol", type=float, default=15.0)
    ap.add_argument("--margin", type=float, default=4.0)
    ap.add_argument("--beats", required=True, help=".npy of madmom beat times for this mix (mixtape_audit_grid.py --beats)")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    x, sr = sf.read(a.mix, dtype="float32")
    ons = kick_onsets(x, sr, np.load(a.beats))
    tl = json.loads(Path(a.timeline).read_text())
    rows, ctrl = [], []
    tr = tl["trans"]
    for k, (t0, t1) in enumerate(tr):
        sel = ons[(ons >= t0 - a.margin) & (ons <= t1 + a.margin)]
        dv = ibi_dev(sel)
        if dv is None:
            rows.append({"trans": k, "note": "too few kicks"})
            continue
        rows.append({"trans": k, "t0": t0, "t1": t1, "n_kicks": int(len(sel)), "worst_ms": float(np.abs(dv).max()),
                     "p90_ms": float(np.percentile(np.abs(dv), 90)), "n_out": int((np.abs(dv) > a.tol).sum())})
    # control: body stretches between window k end + margin and window k+1 start - margin
    for k in range(len(tr) - 1):
        lo, hi = tr[k][1] + a.margin, tr[k + 1][0] - a.margin
        if hi - lo < 4:
            continue
        dv = ibi_dev(ons[(ons >= lo) & (ons <= hi)])
        if dv is not None:
            ctrl.append(float(np.abs(dv).max()))
    cw = np.array([r["worst_ms"] for r in rows if "worst_ms" in r])
    cc = np.array(ctrl)
    bad = [r for r in rows if r.get("worst_ms", 0) > max(a.tol, 2 * np.median(cc)) ]
    print(f"{len(rows)} windows: worst-interval ms med {np.median(cw):.1f} p90 {np.percentile(cw, 90):.1f} max {cw.max():.1f}"
          f" | clip-body control (n={len(cc)}): med {np.median(cc):.1f} p90 {np.percentile(cc, 90):.1f} max {cc.max():.1f}")
    print(f"windows clearly worse than the bodies (> max(tol {a.tol:.0f} ms, 2x control median)): {len(bad)}")
    for r in bad:
        print("  ", r)
    if a.json:
        Path(a.json).write_text(json.dumps({"rows": rows, "control_worst_ms": ctrl, "bad": [r["trans"] for r in bad]}, indent=1))


if __name__ == "__main__":
    main()
