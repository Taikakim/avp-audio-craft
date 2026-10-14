#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-14)
"""latch_drift_check.py -- what ELSE moved when a LatCH head steered one feature? (side-effect audit, CPU only, no re-render)

REVISED SAME DAY (Kim): steering legitimately changes MORE than the steered axis -- a grainy thin render fixed with the bass/mid heads kept its melodies and
lost its graininess while the whole timbre/dynamics/balance changed, and that is a WIN. So change is not harm. The meter therefore splits features:
  CONTENT (should survive; flagged when it moves): tempo (kick-band, continuous), onset rate, hat onset rate, chroma_sim (framewise cosine of 12-bin chroma,
          REPORTED ONLY, not yet calibrated -- see compare()), rhythm_sim (correlation of the kick-band onset envelopes = 'do the hits land in the same places').
  TIMBRE/BALANCE (allowed to move; reported, never flagged): centroid, rms_db, band balance.
It says nothing about whether the result is BETTER (graininess gone is invisible here) -- that is a quality meter's job (Audiobox CE/PQ, clip_metrics.db,
the disintegration gate), run alongside.

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
CONTENT = ("onset_rate", "hat_rate", "bpm")          # flagged on change
FREE = ("centroid", "rms_db")                        # timbre/balance: reported, never flagged
SIMS = ("chroma_sim", "rhythm_sim")                  # pairwise, 1.0 = unchanged; only rhythm_sim flags (below --min-sim)


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


def _chroma(f, mag):
    ok = (f >= 55) & (f <= 2000)
    pc = np.round(12 * np.log2(f[ok] / 440.0)).astype(int) % 12
    C = np.zeros((12, mag.shape[1]))
    for k in range(12):
        C[k] = mag[ok][pc == k].sum(0)
    return C / (np.linalg.norm(C, axis=0, keepdims=True) + 1e-9)


def measure(path, with_series=False):
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
    m = {"onset_rate": _rate(full, hop_s, dur), "hat_rate": _rate(hat, hop_s, dur), "bpm": _bpm(low, hop_s),
         "centroid": cen, "rms_db": float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9))}
    if with_series:
        m["_low"], m["_chroma"] = low, _chroma(f, mag)
    return m


def _sims(mb, ms):
    n = min(mb["_chroma"].shape[1], ms["_chroma"].shape[1])
    chroma = float((mb["_chroma"][:, :n] * ms["_chroma"][:, :n]).sum(0).mean())
    a, b = mb["_low"][:n], ms["_low"][:n]
    rhythm = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else float("nan")
    return {"chroma_sim": chroma, "rhythm_sim": rhythm}


def compare(pairs, flag=1.0, min_sim=0.7):
    rows = []
    for p in pairs:
        mb, ms = measure(p["base"], True), measure(p["steered"], True)
        sims = _sims(mb, ms)
        b = {k: v for k, v in mb.items() if not k.startswith("_")}
        s_ = {k: v for k, v in ms.items() if not k.startswith("_")}
        rows.append({"id": p["id"], "target": p.get("target"), "base": b, "steered": s_, "sims": sims,
                     "delta": {k: s_[k] - b[k] for k in FEATURES}})
    spread = {k: float(np.nanstd([r["base"][k] for r in rows])) if len(rows) > 1 else float("nan") for k in FEATURES}
    for r in rows:
        r["z"] = {}
        for k in FEATURES:
            if np.isfinite(spread[k]) and spread[k] > 1e-9:
                r["z"][k] = r["delta"][k] / spread[k]
            else:      # a single pair has no across-clip spread -> unit-free relative change
                r["z"][k] = r["delta"][k] / (abs(r["base"][k]) + 1e-9)
        r["flags"] = [k for k in CONTENT if np.isfinite(r["z"][k]) and abs(r["z"][k]) >= flag and k != r.get("target")]
        # rhythm_sim is flagged; chroma_sim is REPORTED ONLY: on synthetic pairs it scored an EQ'd (same notes) clip 0.73-0.80 and a one-semitone shift 0.70,
        # i.e. no usable gap. It needs calibrating on real renders (same-seed steered vs a DIFFERENT-seed render as the negative control) before it may flag.
        if np.isfinite(r["sims"]["rhythm_sim"]) and r["sims"]["rhythm_sim"] < min_sim:
            r["flags"].append("rhythm_sim")
    summ = {k: {"mean_delta": float(np.nanmean([r["delta"][k] for r in rows])), "mean_abs_z": float(np.nanmean([abs(r["z"][k]) for r in rows])),
                "n_flagged": sum(k in r["flags"] for r in rows), "kind": "content" if k in CONTENT else "free (never flagged)"} for k in FEATURES}
    for k in SIMS:
        summ[k] = {"mean": float(np.nanmean([r["sims"][k] for r in rows])), "min": float(np.nanmin([r["sims"][k] for r in rows])),
                   "n_flagged": sum(k in r["flags"] for r in rows), "kind": "content"}
    return {"rows": rows, "base_spread": spread, "summary": summ, "flag": flag, "min_sim": min_sim}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--flag", type=float, default=1.0)
    ap.add_argument("--min-sim", type=float, default=0.7, help="chroma_sim / rhythm_sim below this is flagged")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = compare(json.load(open(a.manifest)), a.flag, a.min_sim)
    print(f"{'feature':12s} {'mean delta':>11s} {'mean |z|':>9s} {'flagged':>8s}   kind   (z = delta / spread across base clips)")
    for k, v in res["summary"].items():
        if k in SIMS:
            print(f"{k:12s} {'mean ' + format(v['mean'], '.3f'):>11s} {'min ' + format(v['min'], '.3f'):>9s} {v['n_flagged']:>5d}/{len(res['rows'])}   {v['kind']}")
        else:
            print(f"{k:12s} {v['mean_delta']:11.2f} {v['mean_abs_z']:9.2f} {v['n_flagged']:>5d}/{len(res['rows'])}   {v['kind']}")
    for r in res["rows"]:
        if r["flags"]:
            print(f"  {r['id']}: " + ", ".join((f"{k} {r['sims'][k]:.2f}" if k in SIMS else f"{k} {r['delta'][k]:+.2f} (z {r['z'][k]:+.1f})") for k in r["flags"]))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
