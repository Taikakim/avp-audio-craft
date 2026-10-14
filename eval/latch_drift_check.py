#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-14)
"""latch_drift_check.py -- what ELSE moved when a LatCH head steered one feature? (side-effect audit, CPU only, no re-render)

WHY (Kim 2026-10-14, recalling the June density head: "barrages of 16th hihats, changed the BPM"). A head that hits its target feature can do it the
cheap way. The disintegration gate (docs/superpowers/specs/2026-07-20-control-head-disintegration-gate.md) catches buzz/whitening; this catches
the other failure -- the steered clip is CLEAN but a feature nobody asked for moved: tempo, hi-hat density, brightness, loudness.

INPUT: a manifest JSON, a list of {"id", "base", "steered", optional "target"} -- `base` is the same seed/prompt UNSTEERED (gain 0), `steered`
the guided render. Wavs, any length/rate. For each pair it measures (numpy/scipy/soundfile only):
  onset_rate   onsets/s of the full-band spectral flux           hat_rate   onsets/s of the >6 kHz band (the hi-hat barrage meter)
  bpm          tempo from the <200 Hz (kick-band) onset envelope, comb-scored over 1-4 beat lags, parabolic-interpolated -- NEVER rounded (diffusion audio is not on an integer grid;
               Antigravity 2026-10-08, profiles/antigravity.journal.md) and folded into [95,190) like extract_density_targets.pick_tempo
  centroid     spectral centroid (Hz)       rms_db   loudness
Reports delta = steered - base per feature, and z = delta / (the spread of that feature across the BASE clips) so features in different units are
comparable; |z| >= --flag (default 1.0) is flagged. AUDIT NOTE: this is a screen, not madmom; its tempo estimate is only trustworthy as a DIFFERENCE
between two renders of the same material, and only where the kick carries the pulse (a full-band version was fooled by added hats: 146 -> 97). Positive control: tests/test_latch_drift_check.py renders click tracks where one feature really moved.

RUN: /home/kim/Projects/SAO/.venv/bin/python eval/latch_drift_check.py --manifest pairs.json [--flag 1.0] [--out drift.json]
"""
import argparse
import json
import sys

import numpy as np
import soundfile as sf
from scipy.signal import stft, find_peaks

FEATURES = ("onset_rate", "hat_rate", "bpm", "centroid", "rms_db")


def _mono(x):
    return x.mean(1) if x.ndim > 1 else x


def _flux(S, mask):
    mag = np.abs(S[mask]).astype(np.float64)
    d = np.maximum(np.diff(np.log1p(10 * mag), axis=1), 0).sum(0)
    return np.concatenate([[0.0], d])


def _rate(env, hop_s, dur):
    if env.max() <= 0:
        return 0.0
    e = env - np.convolve(env, np.ones(9) / 9, mode="same")
    pk, _ = find_peaks(e, height=e.std() * 1.5, distance=max(1, int(0.06 / hop_s)))
    return len(pk) / dur


def _bpm(env, hop_s, lo=95.0, hi=190.0):
    """Comb score over beat multiples: a candidate tempo is rewarded for autocorrelation at 1,2,3,4 beats, not just its strongest lag.
    (The plain argmax-of-autocorrelation version read a hi-hat-rich 146 BPM clip as 97 -- it locked onto a 3-sixteenth lag.)"""
    e = env - env.mean()
    ac = np.correlate(e, e, "full")[len(e) - 1:]
    ac = ac / (ac[0] + 1e-12)
    cand = np.arange(lo, hi, 0.1)
    lag = 60.0 / cand / hop_s                              # beat period in (fractional) frames
    if 4.5 * lag.max() >= len(ac):
        return float("nan")
    x = np.arange(len(ac))
    score = sum(np.interp(k * lag, x, ac) for k in (1, 2, 3, 4)) / 4.0
    return float(cand[int(np.argmax(score))])              # 0.1 BPM grid: continuous enough, never rounded to an integer


def measure(path):
    x, sr = sf.read(path, dtype="float32", always_2d=False)
    x = _mono(x)
    dur = len(x) / sr
    n = 1024 if sr <= 24000 else 2048
    f, t, S = stft(x, fs=sr, nperseg=n, noverlap=n - n // 4)
    hop_s = (n // 4) / sr
    mag = np.abs(S)
    full = _flux(S, np.ones_like(f, dtype=bool))
    hat = _flux(S, f >= 6000)
    low = _flux(S, f < 200)                                # kick band: tempo is read HERE so a hi-hat barrage cannot masquerade as a tempo change
    cen = float(((f[:, None] * mag).sum(0) / (mag.sum(0) + 1e-9)).mean())
    return {"onset_rate": _rate(full, hop_s, dur), "hat_rate": _rate(hat, hop_s, dur), "bpm": _bpm(low, hop_s),
            "centroid": cen, "rms_db": float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9))}


def compare(pairs, flag=1.0):
    rows = []
    for p in pairs:
        b, s = measure(p["base"]), measure(p["steered"])
        rows.append({"id": p["id"], "target": p.get("target"), "base": b, "steered": s,
                     "delta": {k: s[k] - b[k] for k in FEATURES}})
    spread = {k: float(np.nanstd([r["base"][k] for r in rows])) if len(rows) > 1 else float("nan") for k in FEATURES}
    # with a single pair there is no across-clip spread -> fall back to a unit-free relative change so a single pair still reads
    for r in rows:
        r["z"] = {}
        for k in FEATURES:
            if np.isfinite(spread[k]) and spread[k] > 1e-9:
                r["z"][k] = r["delta"][k] / spread[k]
            else:
                r["z"][k] = r["delta"][k] / (abs(r["base"][k]) + 1e-9)
        r["flags"] = [k for k in FEATURES if np.isfinite(r["z"][k]) and abs(r["z"][k]) >= flag and k != r.get("target")]
    summ = {k: {"mean_delta": float(np.nanmean([r["delta"][k] for r in rows])), "mean_abs_z": float(np.nanmean([abs(r["z"][k]) for r in rows])),
                "n_flagged": sum(k in r["flags"] for r in rows)} for k in FEATURES}
    return {"rows": rows, "base_spread": spread, "summary": summ, "flag": flag}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--flag", type=float, default=1.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = compare(json.load(open(a.manifest)), a.flag)
    print(f"{'feature':12s} {'mean delta':>11s} {'mean |z|':>9s} {'flagged':>8s}   (z = delta / spread of that feature across base clips; target feature excluded from flags)")
    for k, v in res["summary"].items():
        print(f"{k:12s} {v['mean_delta']:11.2f} {v['mean_abs_z']:9.2f} {v['n_flagged']:>5d}/{len(res['rows'])}")
    for r in res["rows"]:
        if r["flags"]:
            print(f"  {r['id']}: " + ", ".join(f"{k} {r['delta'][k]:+.2f} (z {r['z'][k]:+.1f})" for k in r["flags"]))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
