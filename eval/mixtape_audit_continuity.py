#!/usr/bin/env python
"""mixtape_audit_continuity.py — does the assembled DJ mix play every clip FORWARD without jumps?

WHY (CONTINUITY, 2026-10-07). Kim listened to the v6 mix: "as the clips transition into each other there is a
temporal gap". The corruption scans (sample jumps, audio_corruption_scan.py) cannot see that: the audio is
clean, it is just in the wrong place. This audit tracks, for every window of the mix, WHERE in its source clip
that audio comes from, and flags places where the source position does not advance with the mix clock.
Measured on v6: all 39 splices REPLAY (the incoming clip restarts at its entry point instead of continuing ~10 s
later, found to within 10 ms), which no earlier check caught. A pipeline change is not done until this passes.

METHOD: low-pass the mix and each source clip at 150 Hz (kick + bass carry the groove and survive tempo
bends), 1 kHz sampling. For each hop of the mix take a WIN-second window, normalised-cross-correlate it with the
clips that can be playing there (the clip owning that time from the timeline, and its neighbours), keep the best
source position p(t). Among near-best peaks the one closest to "previous position + hop" wins (loops repeat).
Flag where p(t+hop) - p(t) - hop deviates by more than TOL seconds (a jump or an unannounced tempo change) or
where the best clip changes without the source position landing on that clip's expected entry.

USAGE  .venv/bin/python eval/mixtape_audit_continuity.py --mix MIX.wav --order order_final.json \\
          --timeline timeline.json [--mix-id v6_a2a] [--hop 4 --win 6 --tol 0.25] [--json OUT.json]
  order_final.json : list of {id, path} in play order (path = the clip wav the mix was built from)
  timeline.json    : output of eval/build_dj_mixes_section.py (private copy; has clip_bounds)
Exit code 1 if any discontinuity is found. Run from a dir that is not the SAO root (torchcodec shadow).
"""
import argparse
import json
import subprocess
import sys

import numpy as np
from scipy.signal import butter, fftconvolve, resample_poly, sosfiltfilt

FS = 44100 / 44          # 1002.27 Hz after the 44x decimation


def lowband(path):
    y = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", "44100", "-"],
                                     capture_output=True).stdout, dtype=np.float32)
    return resample_poly(sosfiltfilt(butter(4, 150, "low", fs=44100, output="sos"), y), 1, 44)


def ncc(src, seg):
    """Normalised cross-correlation of seg against every position of src (valid positions only)."""
    n = len(seg)
    seg0 = seg - seg.mean()
    num = fftconvolve(src, seg0[::-1], mode="valid")
    cs, cs2 = np.concatenate([[0], np.cumsum(src)]), np.concatenate([[0], np.cumsum(src ** 2)])
    m = len(src) - n + 1
    mu = (cs[n:n + m] - cs[:m]) / n
    var = np.maximum((cs2[n:n + m] - cs2[:m]) / n - mu ** 2, 1e-12)
    return num / (np.sqrt(var) * np.linalg.norm(seg0) + 1e-12)


def track(mix, srcs, bounds, hop, win, prev_hint=None):
    """-> list of (t, clip_idx, source_sec, r)."""
    out, prev = [], None
    t = 0.0
    dur = len(mix) / FS
    while t + win <= dur:
        seg = mix[int(t * FS):int((t + win) * FS)]
        mid = t + win / 2
        i = int(np.searchsorted(bounds, mid, side="right") - 1)
        best = None
        for c in (i - 1, i, i + 1):
            if not 0 <= c < len(srcs) or len(srcs[c]) <= len(seg):
                continue
            s = ncc(srcs[c], seg)
            rmax = float(s.max())
            cand = np.nonzero(s >= 0.97 * rmax)[0]
            if prev is not None and prev[0] == c and len(cand):
                k = int(cand[np.argmin(np.abs(cand / FS - (prev[1] + hop)))])
            else:
                k = int(np.argmax(s))
            if best is None or s[k] > best[3]:
                best = (c, t, k / FS, float(s[k]))
        if best is not None:
            out.append(best)
            prev = (best[0], best[2])
        t += hop
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mix", required=True)
    ap.add_argument("--order", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--mix-id", default=None)
    ap.add_argument("--hop", type=float, default=4.0)
    ap.add_argument("--win", type=float, default=6.0)
    ap.add_argument("--tol", type=float, default=0.25)
    ap.add_argument("--min-r", type=float, default=0.6, help="ignore windows whose best match is weaker (two clips overlapping)")
    ap.add_argument("--cluster", type=float, default=12.0, help="merge flags closer than this many seconds into one finding")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    order = json.load(open(a.order))
    tls = json.load(open(a.timeline))
    tl = tls[a.mix_id] if a.mix_id else (tls if "clip_bounds" in tls else next(iter(tls.values())))
    bounds = tl["clip_bounds"]
    mix = lowband(a.mix)
    srcs = [lowband(c["path"]) for c in order]
    pts = [p for p in track(mix, srcs, bounds, a.hop, a.win) if p[3] >= a.min_r]
    flags = []
    for p0, p1 in zip(pts, pts[1:]):
        dt = p1[1] - p0[1]
        if p1[0] == p0[0]:
            dev = (p1[2] - p0[2]) - dt
            if abs(dev) > a.tol:
                flags.append({"t": round(p0[1] + a.win / 2, 1), "clip": p0[0] + 1, "kind": "jump", "dev_s": round(dev, 2)})
        elif p1[0] != p0[0] + 1:
            flags.append({"t": round(p0[1] + a.win / 2, 1), "clip": p1[0] + 1, "kind": "clip_order", "dev_s": None})
    merged = []
    for f in flags:                      # one finding per event: keep the largest deviation of a cluster
        if merged and f["t"] - merged[-1]["t"] < a.cluster:
            if abs(f["dev_s"] or 0) > abs(merged[-1]["dev_s"] or 0):
                merged[-1] = f
        else:
            merged.append(f)
    flags = merged
    print(f"{len(pts)} tracked windows, {len(flags)} discontinuities (tol {a.tol}s)")
    for f in flags[:60]:
        print(f"  t={f['t']:7.1f}s clip {f['clip']:2d} {f['kind']:10s} dev {f['dev_s']}")
    if flags:
        d = [f['dev_s'] for f in flags if f['dev_s'] is not None]
        print(f"deviation seconds: median {np.median(d):.2f}, min {min(d):.2f}, max {max(d):.2f}")
    if a.json:
        json.dump({"windows": len(pts), "flags": flags}, open(a.json, "w"), indent=1)
    sys.exit(1 if flags else 0)


if __name__ == "__main__":
    main()
