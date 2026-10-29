#!/usr/bin/env python3
"""Morph A/B step 3 with an instrument that passes its own positive control: does a morph-contour
render follow ITS fed melody contour more than another stem's, and more than the unconditioned render?

HISTORY (read before changing the meter, CONTINUITY 2026-10-29):
1. eval/morph_contour_ab.py rebuilt the render's line from MuScriptor MIDI and scored exact contour
   symbols. Its positive control (reference audio vs its own fed stream) read 0.073: wrong quantity.
2. The fed stream is `f0_other_ts` (mir whole_track_expanded._melody: PredominantPitchMelodia,
   frame 2048 / hop 441 @ 44.1 kHz, 55-1760 Hz, after EqualLoudness, on the Goa_Separated `other`
   stem), pooled to the latent grid by mir/src/tools/crop_timeseries_resample.py, then contour-encoded.
   This script reproduces that path EXACTLY on whole tracks (raw 100 Hz agreement 1.000, pooled
   99.5% within 0.5 st, measured on 000600) -- but MELODIA IS INPUT-LENGTH DEPENDENT: its contour
   selection uses statistics over the whole input, so the same stem read over a 47 s window agrees
   with the whole-track reading on only 52% of frames (19% octave-off on 000600). A render IS a 47 s
   window, so the fed stream cannot be reproduced symbol-for-symbol from any render.
3. Exact contour SYMBOLS then compound every pitch error: on the known positive (reference clip ->
   Demucs -> Melodia vs the store) symbol agreement is 0.13 against 0.08 for a wrong stem. Useless.
4. The CURVE CORRELATION has range on the same known positive: Pearson r of the semitone curves on
   jointly voiced frames, own 0.43 vs foreign -0.07 (4 stems). It is also invariant to transposition
   and scale, which is what a contour conditioner controls (rank order, not absolute pitch); exact-
   semitone match would score a perfectly followed but transposed line at zero. Spearman (fully
   monotone-invariant, like the contour codes) is reported alongside.

PRIMARY METER: r(render curve, store curve of the fed stem) vs r(render, the other stems' curves)
(foreign floor) and vs the unconditioned render of the same arm/stem (null baseline).
Gate on the known positive (reference clips, same path as renders): own r >= GATE_R and own -
foreign >= GATE_GAP. Thresholds set from the instrument's calibration, before any render was scored.
Symbol agreement (the old meter) stays in the JSON as a secondary column.

Run under the mir venv (demucs, essentia), GPU for Demucs, inside Misc/gpu_guard.sh:
  /home/kim/Projects/mir/mir/bin/python eval/morph_f0_contour_ab.py --renders <run>/clips \
      --out <run>/morph_f0_contour_ab.json
f0 per wav is cached as <clips>/f0other/<name>.npz (Demucs other + mix Melodia), so re-scoring never
re-separates.
"""
import argparse
import glob
import json
import math
import os
import statistics as st
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/home/kim/Projects/mir/src/tools")
from morph_contour_ab import (LAT, L_OF_VOCAB, STRIDE, TOL_ST, agree, sign_p,  # noqa: E402
                              stream_from_truth)
from src.conditioners.contour_streams import contour_stream, expand_to_frames  # noqa: E402
from crop_timeseries_resample import build_crop_timeseries  # noqa: E402

SR = 44100
LATENT_HOP = 4096                      # SAME: one latent frame = 4096 samples at 44.1 kHz
MIN_JOINT = 40                         # jointly voiced frames needed for a correlation
GATE_R, GATE_GAP = 0.30, 0.20


# ---------------------------------------------------------------- extraction

def melodia(mono44: np.ndarray) -> np.ndarray:
    """mir whole_track_expanded._melody, the `other` voice, verbatim settings."""
    import essentia.standard as es
    el = es.EqualLoudness(sampleRate=SR)
    mel = es.PredominantPitchMelodia(frameSize=2048, hopSize=441, sampleRate=SR,
                                     minFrequency=55.0, maxFrequency=1760.0)
    return np.asarray(mel(el(np.ascontiguousarray(mono44, dtype=np.float32)))[0], dtype=np.float32)


class Separator:
    def __init__(self, device="cuda", shifts=0):
        import torch
        from demucs.pretrained import get_model
        self.torch = torch
        self.model = get_model("htdemucs").to(device).eval()
        self.device, self.shifts = device, shifts
        self.idx = self.model.sources.index("other")

    def other(self, stereo: np.ndarray) -> np.ndarray:
        """(N, 2) float at 44.1 kHz -> mono `other` stem. Normalisation as demucs.separate does."""
        from demucs.apply import apply_model
        torch = self.torch
        wav = torch.from_numpy(np.ascontiguousarray(stereo.T, dtype=np.float32))
        ref = wav.mean(0)
        mu, sd = ref.mean(), ref.std() + 1e-8
        with torch.no_grad():
            src = apply_model(self.model, ((wav - mu) / sd)[None], device=self.device,
                              shifts=self.shifts, split=True, overlap=0.25, progress=False)[0]
        o = src[self.idx] * sd + mu
        return o.mean(0).cpu().numpy()


def read_stereo(path, start=None, frames=None):
    import soundfile as sf
    x, sr = sf.read(path, start=start or 0, frames=-1 if frames is None else frames,
                    dtype="float32", always_2d=True)
    assert sr == SR, f"{path}: {sr} Hz, expected {SR}"
    return x if x.shape[1] == 2 else np.repeat(x[:, :1], 2, axis=1)


def f0_cached(wav, cache_dir, sep_factory):
    os.makedirs(cache_dir, exist_ok=True)
    cp = os.path.join(cache_dir, os.path.basename(wav)[:-4] + ".npz")
    if os.path.exists(cp):
        z = np.load(cp)
        return z["f0_sep"], z["f0_mix"], float(z["dur"])
    x = read_stereo(wav)
    f0_mix = melodia(x.mean(1))
    f0_sep = melodia(sep_factory().other(x))
    np.savez(cp, f0_sep=f0_sep, f0_mix=f0_mix, dur=x.shape[0] / SR)
    return f0_sep, f0_mix, x.shape[0] / SR


# ---------------------------------------------------------------- curves and meters

def curve(f0_100hz: np.ndarray, dur: float, n: int) -> np.ndarray:
    """100 Hz Melodia f0 -> semitone curve on the n-frame latent grid, NaN where unvoiced
    (sentinel-aware pooling, voiced = pooled validity > 0.5, as the store was built)."""
    out = build_crop_timeseries({"f0_other_ts": f0_100hz, "f0_other_voiced_ts": (f0_100hz > 0).astype(np.float32)},
                                {"frame_rate": 100.0, "duration": dur}, 0.0, dur, n, strict=False)
    s = np.full(n, np.nan)
    if "f0_other_ts" in out:
        f, v = np.asarray(out["f0_other_ts"], np.float64), np.asarray(out["f0_other_voiced_ts"]) > 0.5
        s[v] = 12.0 * np.log2(np.maximum(f[v], 1e-3) / 440.0)
    return s


def store_curve(stem: str, w0: int, n: int) -> np.ndarray:
    z = np.load(f"{LAT}/{stem}.TIMESERIES.npz")
    f = np.asarray(z["f0_other_ts"], np.float64)[w0:w0 + n]
    v = np.asarray(z["f0_other_voiced_ts"])[w0:w0 + n] > 0.5
    s = np.full(n, np.nan)
    s[v] = 12.0 * np.log2(np.maximum(f[v], 1e-3) / 440.0)
    return s


def encode(semis: np.ndarray, L: int):
    """semitone curve (NaN = unvoiced) -> contour symbols, exactly as stream_from_truth."""
    v = ~np.isnan(semis)
    vals = np.where(v, semis, 0.0)
    pts = np.flatnonzero(v)[::STRIDE]
    if pts.size < L + 2:
        return None
    syms, anch = contour_stream(vals, pts, L=L, tol=TOL_ST)
    s = expand_to_frames(syms, anch, len(semis))
    return np.where(s < 0, 0, s + 1).astype(np.int8)


def _rank(x):
    o = np.argsort(x, kind="mergesort")
    r = np.empty(len(x))
    r[o] = np.arange(len(x))
    return r


def corr(a: np.ndarray, b: np.ndarray) -> dict:
    m = ~np.isnan(a) & ~np.isnan(b)
    k = int(m.sum())
    if k < MIN_JOINT or np.std(a[m]) == 0 or np.std(b[m]) == 0:
        return {"r": float("nan"), "rho": float("nan"), "n": k}
    return {"r": float(np.corrcoef(a[m], b[m])[0, 1]),
            "rho": float(np.corrcoef(_rank(a[m]), _rank(b[m]))[0, 1]), "n": k}


def _m(xs):
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    return float(st.mean(xs)) if xs else float("nan")


def score(c, own_curve, foreign_curves, own_stream, foreign_streams, L):
    o = corr(c, own_curve)
    fr = [corr(c, f) for f in foreign_curves]
    e = encode(c, L)
    sym_o = agree(e, own_stream)[0] if e is not None else float("nan")
    sym_f = [agree(e, s)[0] for s in foreign_streams] if e is not None else []
    return {"r_own": o["r"], "rho_own": o["rho"], "n_joint": o["n"],
            "r_foreign": _m([x["r"] for x in fr]), "rho_foreign": _m([x["rho"] for x in fr]),
            "voiced_frac": float((~np.isnan(c)).mean()),
            "sym_own": sym_o, "sym_foreign": _m(sym_f)}


def _diffs(rows, null, against):
    out = []
    for r in rows:
        if against == "foreign":
            d = r["r_own"] - r["r_foreign"]
        else:
            nl = null.get((r["arm"], r["stem"]))
            d = float("nan") if nl is None else r["r_own"] - nl["r_own"]
        if not math.isnan(d):
            out.append(d)
    return out


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--renders", required=True, help="dir with <cell>.wav/.json/.stream.npy and refs/")
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--shifts", type=int, default=0, help="Demucs shifts (mir's DEMUCS_CONFIG uses 0)")
    ap.add_argument("--pc-only", action="store_true", help="positive controls only (the reference clips)")
    a = ap.parse_args()
    cache = os.path.join(a.renders, "f0other")
    _sep = []

    def sep_factory():
        if not _sep:
            _sep.append(Separator(a.device, a.shifts))
        return _sep[0]

    cells = []
    for jf in sorted(glob.glob(os.path.join(a.renders, "*.json"))):
        d = json.load(open(jf))
        if "stem" in d and os.path.exists(jf[:-5] + ".wav"):
            cells.append((jf, d))
    fed, win = {}, {}
    vocab = None
    for jf, d in cells:
        vocab = vocab or int(d["vocab"])
        stem = str(d["stem"])
        win.setdefault(stem, tuple(d["window"]))
        if d.get("conditioned"):
            s = np.load(jf[:-5] + ".stream.npy").astype(np.int8)
            if not np.array_equal(fed.setdefault(stem, s), s):
                raise SystemExit(f"fed stream for stem {stem} differs between cells ({jf})")
    L = L_OF_VOCAB[vocab]
    stems = sorted(fed)
    n = len(next(iter(fed.values())))
    print(f"cells {len(cells)}  stems {stems}  vocab {vocab} (L={L})  frames {n}")
    tgt = {s: store_curve(s, win[s][0], n) for s in stems}

    # ---- calibration on known positives
    pc = {"PC0_store_symbols_vs_fed": [], "PC1_true_other_window": [], "PC2_ref_demucs": [], "mix_ref_no_sep": []}
    for stem in stems:
        w0 = win[stem][0]
        truth = stream_from_truth(stem, L)
        if truth is not None:
            pc["PC0_store_symbols_vs_fed"].append(agree(truth[w0:w0 + n], fed[stem])[0])
        fc = [tgt[s] for s in stems if s != stem]
        fs_ = [fed[s] for s in stems if s != stem]
        cm = json.load(open(f"{LAT}/{stem}.json"))
        op = os.path.join(os.path.dirname(cm["source_path"]), "other.flac")
        if os.path.exists(op):
            x = read_stereo(op, int(cm["start_sample"]) + w0 * LATENT_HOP, n * LATENT_HOP)
            pc["PC1_true_other_window"].append(score(curve(melodia(x.mean(1)), x.shape[0] / SR, n),
                                                     tgt[stem], fc, fed[stem], fs_, L))
        rw = os.path.join(a.renders, "refs", f"ref__{stem}.wav")
        if os.path.exists(rw):
            f_sep, f_mix, dur = f0_cached(rw, cache, sep_factory)
            pc["PC2_ref_demucs"].append(score(curve(f_sep, dur, n), tgt[stem], fc, fed[stem], fs_, L))
            pc["mix_ref_no_sep"].append(score(curve(f_mix, dur, n), tgt[stem], fc, fed[stem], fs_, L))
    print(f"PC0 store window symbols vs fed stream (bookkeeping, must be 1): {_m(pc['PC0_store_symbols_vs_fed']):.4f}")
    print("CALIBRATION (known positives; own = vs ITS stem's store curve, foreign = vs the other stems'):")
    for k in ("PC1_true_other_window", "PC2_ref_demucs", "mix_ref_no_sep"):
        v = pc[k]
        print(f"  {k:22s} r own {_m([x['r_own'] for x in v]):+.3f} for {_m([x['r_foreign'] for x in v]):+.3f} | "
              f"rho own {_m([x['rho_own'] for x in v]):+.3f} for {_m([x['rho_foreign'] for x in v]):+.3f} | "
              f"symbols own {_m([x['sym_own'] for x in v]):.3f} for {_m([x['sym_foreign'] for x in v]):.3f}")
    r_own = _m([x["r_own"] for x in pc["PC2_ref_demucs"]])
    r_for = _m([x["r_foreign"] for x in pc["PC2_ref_demucs"]])
    gate = r_own >= GATE_R and (r_own - r_for) >= GATE_GAP
    print(f"GATE on PC2 (r own >= {GATE_R}, own - foreign >= {GATE_GAP}): {'PASS' if gate else 'FAIL'} "
          f"({r_own:+.3f} / {r_own - r_for:+.3f})")
    if a.pc_only:
        return

    # ---- renders
    rows = []
    for i, (jf, d) in enumerate(cells):
        f_sep, _, dur = f0_cached(jf[:-5] + ".wav", cache, sep_factory)
        stem = str(d["stem"])
        sc = score(curve(f_sep, dur, n), tgt[stem], [tgt[s] for s in stems if s != stem],
                   fed[stem], [fed[s] for s in stems if s != stem], L)
        rows.append({"arm": str(d.get("label")), "stem": stem,
                     "gain": float(d.get("gain", 1.0)) if d.get("conditioned") else None, **sc})
        if (i + 1) % 25 == 0:
            print(f"  scored {i + 1}/{len(cells)}", flush=True)

    null = {(r["arm"], r["stem"]): r for r in rows if r["gain"] is None}
    summary = {}
    for arm in sorted({r["arm"] for r in rows}):
        rs = [r for r in rows if r["arm"] == arm]
        per = {}
        nl = [r for r in rs if r["gain"] is None]
        if nl:
            per["null"] = {"n": len(nl), "r_own": _m([r["r_own"] for r in nl]),
                           "r_foreign": _m([r["r_foreign"] for r in nl])}
        for g in sorted({r["gain"] for r in rs if r["gain"] is not None}):
            gr = [r for r in rs if r["gain"] == g]
            dof, dnl = _diffs(gr, null, "foreign"), _diffs(gr, null, "null")
            per[str(g)] = {"n": len(gr), "r_own": _m([r["r_own"] for r in gr]),
                           "r_foreign": _m([r["r_foreign"] for r in gr]),
                           "rho_own": _m([r["rho_own"] for r in gr]),
                           "own_minus_foreign": _m(dof), "pos_vs_foreign": sum(x > 0 for x in dof),
                           "n_vs_foreign": len(dof),
                           "own_minus_null": _m(dnl), "pos_vs_null": sum(x > 0 for x in dnl), "n_vs_null": len(dnl),
                           "sym_own": _m([r["sym_own"] for r in gr]), "sym_foreign": _m([r["sym_foreign"] for r in gr])}
        summary[arm] = per

    print(f"\nRESULTS{'' if gate else ' (GATE FAILED: for the record only, NOT a result)'} "
          f"-- r = pitch-curve correlation with the fed stem's curve:")
    for arm, per in summary.items():
        nl = per.get("null", {})
        print(f"  {arm:36s} null r own {nl.get('r_own', float('nan')):+.3f} for {nl.get('r_foreign', float('nan')):+.3f}")
        for g, v in per.items():
            if g == "null":
                continue
            print(f"      g{g:<4s} r own {v['r_own']:+.3f} for {v['r_foreign']:+.3f}  own-for {v['own_minus_foreign']:+.3f} "
                  f"({v['pos_vs_foreign']}/{v['n_vs_foreign']})  own-null {v['own_minus_null']:+.3f} "
                  f"({v['pos_vs_null']}/{v['n_vs_null']})")
    pooled = {}
    for tag, sel in (("all conditioned", lambda r: True),
                     ("raw EMA arms", lambda r: "deconv" not in r["arm"]),
                     ("deconv arms", lambda r: "deconv_step" in r["arm"]),
                     ("deconvclamp arms", lambda r: "deconvclamp" in r["arm"])):
        cs = [r for r in rows if r["gain"] is not None and sel(r)]
        dof, dnl = _diffs(cs, null, "foreign"), _diffs(cs, null, "null")
        p1, p2 = sum(x > 0 for x in dof), sum(x > 0 for x in dnl)
        pooled[tag] = {"own_minus_foreign": _m(dof), "pos": p1, "n": len(dof), "p": sign_p(p1, len(dof)),
                       "own_minus_null": _m(dnl), "pos_null": p2, "n_null": len(dnl), "p_null": sign_p(p2, len(dnl))}
        print(f"POOLED {tag:17s} own-for {_m(dof):+.4f} {p1}/{len(dof)} p={sign_p(p1, len(dof)):.3g} | "
              f"own-null {_m(dnl):+.4f} {p2}/{len(dnl)} p={sign_p(p2, len(dnl)):.3g}")

    json.dump({"gate": gate, "gate_thresholds": {"r_own": GATE_R, "gap": GATE_GAP},
               "calibration": pc, "summary": summary, "pooled": pooled, "rows": rows,
               "method": "Demucs htdemucs other stem -> Melodia (mir _melody settings) -> sentinel pool to the "
                         "latent grid -> Pearson r / Spearman rho vs the fed stem's store f0 curve (jointly voiced "
                         "frames); symbols = stream_from_truth encoding, secondary"},
              open(a.out, "w"), indent=1, default=float)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
