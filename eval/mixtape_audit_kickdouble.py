#!/usr/bin/env python
"""mixtape_audit_kickdouble.py — does a transition ADD kick onsets that are not on the beat? (the a2a stutter)

WHY (GHOST-NOTE 2026-10-07). The owner heard the a2a-smoothed v7b mixes stutter between clips: kicks misplaced or firing extra
onsets. Every gate we had (sample jumps, replay, beat grid) passed them, because jump counts reward smoothing and a
beat-grid detector reports the grid, not the extra hits. This audit counts kick-band onsets directly:
  M1  onsets per beat inside each transition window, relative to the same measure on the clip bodies of the SAME mix
      (a clean four-on-the-floor window is ~1.0x its bodies; extra/doubled kicks push it up);
  M2  OFF-GRID fraction: share of kick onsets farther than TOL ms from the nearest point of the window's own beat grid
      (grid = median onset phase at the local tempo, fitted per window).
STATUS: NOT VALIDATED, do not use as a gate. On the staged v7b pair the result FLIPS with the peak threshold: default thresholds
(distance 0.12 s, height 0.5 x p85) gave a2a higher than plain in 26/31 windows (median +0.07 onsets/beat); a more sensitive
setting (0.09 s, 0.3 x p80) gave 12/31, and on synthetic four-on-the-floor with six extra hits it detects only 1-2 of them. A
detector whose verdict depends on a free threshold has no dynamic range here (kick and rolling bass overlap in 40-120 Hz). The
G1 rhythm-integrity meter (EXPERIMENTS G1) is the proper route; this stays as a documented dead end.
It is an INSTRUMENT, so it is validated on a known pair before use: the plain v7b mix (clean per the owner) must score
lower than its a2a twin (glitchy per the owner) at the transitions. Run it on both and compare; a number is only a
finding if plain and a2a separate.

USAGE  .venv/bin/python eval/mixtape_audit_kickdouble.py --mix MIX.{wav,m4a} --timeline timeline.json [--tol 35] [--json OUT]
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import butter, find_peaks, hilbert, resample_poly, sosfiltfilt

SR = 44100


def load_mono(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def kick_transients(x):
    """40-120 Hz band, Hilbert envelope, positive derivative -> (onset times s, strengths) at ~4 kHz."""
    m = resample_poly(x, 1, 11)
    fs = SR / 11
    b = sosfiltfilt(butter(4, (40, 120), "bandpass", fs=fs, output="sos"), m)
    env = sosfiltfilt(butter(2, 50, "low", fs=fs, output="sos"), np.abs(hilbert(b)))
    d = np.clip(np.gradient(env), 0, None)
    pk, pr = find_peaks(d, distance=int(0.12 * fs), height=np.percentile(d, 85) * 0.5)
    return pk / fs, d[pk]


def window_stats(t, a, t0, t1, tol_ms):
    sel = (t >= t0) & (t <= t1)
    tt, aa = t[sel], a[sel]
    if len(tt) < 6:
        return None
    strong = tt[aa >= 0.5 * np.median(aa)]
    if len(strong) < 6:
        return None
    ibi = np.diff(strong)
    beat = float(np.median(ibi[(ibi > 0.3) & (ibi < 0.9)])) if ((ibi > 0.3) & (ibi < 0.9)).any() else float(np.median(ibi))
    phase = (strong % beat)
    ang = np.angle(np.exp(2j * np.pi * phase / beat).mean())
    ph0 = (ang / (2 * np.pi)) % 1.0 * beat                  # circular mean phase of the strong onsets
    off = np.abs(((tt - ph0 + beat / 2) % beat) - beat / 2) * 1000
    return {"n": int(len(tt)), "per_beat": float(len(tt) / ((t1 - t0) / beat)), "beat_s": beat,
            "offgrid_frac": float((off > tol_ms).mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mix", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--tol", type=float, default=35.0)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    x = load_mono(a.mix)
    t, st = kick_transients(x)
    tl = json.loads(Path(a.timeline).read_text())
    tr = tl["trans"]
    rows, body = [], []
    for k in range(len(tr) - 1):
        lo, hi = tr[k][1] + 2, tr[k + 1][0] - 2
        if hi - lo > 6:
            s = window_stats(t, st, lo, hi, a.tol)
            if s:
                body.append(s)
    bpb = np.median([b["per_beat"] for b in body]) if body else 1.0
    bog = np.median([b["offgrid_frac"] for b in body]) if body else 0.0
    for k, (t0, t1) in enumerate(tr):
        s = window_stats(t, st, t0, t1, a.tol)
        if s:
            s.update({"trans": k, "ratio_vs_body": s["per_beat"] / bpb})
            rows.append(s)
    r = np.array([x_["ratio_vs_body"] for x_ in rows]);o = np.array([x_["offgrid_frac"] for x_ in rows])
    print(f"{Path(a.mix).name}: {len(rows)} windows | onsets/beat vs body: med {np.median(r):.2f} p90 {np.percentile(r, 90):.2f} max {r.max():.2f}"
          f" | off-grid frac: med {np.median(o):.2f} p90 {np.percentile(o, 90):.2f} (bodies: {bog:.2f}, n={len(body)})")
    if a.json:
        Path(a.json).write_text(json.dumps({"rows": rows, "body_per_beat": bpb, "body_offgrid": bog}, indent=1))
    return r, o


if __name__ == "__main__":
    main()
