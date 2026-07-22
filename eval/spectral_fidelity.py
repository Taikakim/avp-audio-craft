#!/usr/bin/env python3
"""
spectral_fidelity.py -- the "spectral cleanness / harmonic fidelity / pad-fill" metric axis
that CLAP + clip_metrics.db are BLIND to (Kim 2026-07-22: the fp32-vs-bf16 difference his ear
hears -- fp32 = sparse, focused sources (kickbass/arps/lead); bf16 = spectrum FILLED with
believable droning pads / atmospherics). Companion to eval/clap_score.py.

Per clip (essentia, framewise -> median), the measurable signature of "few focused sounds vs
a filled spectrum":
  tonal_to_noise   -- energy IN spectral peaks / total energy. HIGH = clean tonal sources;
                      LOW = energy smeared between partials (the "mush" / pad-fill).
  spectral_gini    -- Gini of the magnitude spectrum. HIGH = sparse/concentrated (few sounds);
                      LOW = filled/everywhere.
  spectral_crest   -- max/mean of the spectrum. HIGH = peaky/focused.
  dissonance       -- essentia sensory roughness between partials. HIGH = clashing/mushy.
  inharmonicity    -- partials' deviation from integer multiples of f0. HIGH = detuned/noisy
                      harmonic series (the OPPOSITE of "clean harmonics above a fundamental").
  spectral_complexity -- essentia peak count. HIGH = busier/more-filled spectrum.
  flux_cv          -- std/mean of spectral flux over time. LOW = STATIC (drone-like); HIGH = dynamic.

RUN (mir venv -- essentia):
  mir/bin/python eval/spectral_fidelity.py --models bf16cmp_avp_t512_bs8_lr1e4 fp32cmp_avp_t512_bs8_lr1e4 \
      --sample-per-model 250 --out /tmp/specfid_fp32_vs_bf16.csv
Reads clip names from eval/clap_degen_model_matrix.csv; clips from ~/.cache/evals_aac/model_matrix/.
--reverb adds AudioCommons RT60/reverb_prob/depth (SLOW, per-file timeout) -- off by default.
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

CLIPS = Path.home() / ".cache/evals_aac/model_matrix"
CLAP = Path("/home/kim/Projects/SAO/eval/clap_degen_model_matrix.csv")
SR = 44100


def gini(x):
    x = np.sort(np.abs(np.asarray(x, dtype=np.float64)))
    n = x.size
    s = x.sum()
    if n == 0 or s == 0:
        return 0.0
    return float((2.0 * np.sum(np.arange(1, n + 1) * x) / (n * s)) - (n + 1.0) / n)


def measure(path, es, algos):
    w, spec, speaks, diss, pitch, hpeaks, inharm, scx = algos
    audio = es.MonoLoader(filename=str(path), sampleRate=SR)()
    if audio.size < 4096:
        return None
    ttn, gi, cr, ds, ih, cx = [], [], [], [], [], []
    flux_series, prev = [], None
    for frame in es.FrameGenerator(audio, frameSize=2048, hopSize=1024, startFromZero=True):
        s = spec(w(frame))
        tot = float(np.sum(s ** 2)) + 1e-12
        freqs, mags = speaks(s)
        ttn.append(float(np.sum(mags ** 2)) / tot)          # tonal-to-noise (peak energy / total)
        gi.append(gini(s))
        cr.append(float(s.max() / (s.mean() + 1e-12)))
        cx.append(float(scx(s)))
        if len(freqs) >= 2:
            ds.append(float(diss(freqs, mags)))
            f0, conf = pitch(s)
            if f0 > 0 and conf > 0.2:
                try:
                    hf, hm = hpeaks(freqs, mags, f0)
                    ih.append(float(inharm(hf, hm)))
                except Exception:
                    pass
        if prev is not None:
            flux_series.append(float(np.sqrt(np.sum((s - prev) ** 2))))
        prev = s
    med = lambda a: float(np.median(a)) if a else float("nan")
    fl = np.asarray(flux_series) if flux_series else np.array([0.0])
    return {
        "tonal_to_noise": med(ttn), "spectral_gini": med(gi), "spectral_crest": med(cr),
        "dissonance": med(ds), "inharmonicity": med(ih), "spectral_complexity": med(cx),
        "flux_cv": float(fl.std() / (fl.mean() + 1e-12)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", help="model labels to score (default: all)")
    ap.add_argument("--sample-per-model", type=int, default=0, help="0 = all cells of each model")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reverb", action="store_true", help="add AudioCommons RT60/reverb (SLOW)")
    a = ap.parse_args()

    import essentia.standard as es
    algos = (es.Windowing(type="hann"), es.Spectrum(),
             es.SpectralPeaks(sampleRate=SR, magnitudeThreshold=1e-4, maxPeaks=100, orderBy="frequency"),
             es.Dissonance(), es.PitchYinFFT(sampleRate=SR), es.HarmonicPeaks(),
             es.Inharmonicity(), es.SpectralComplexity(sampleRate=SR))

    rows = [r for r in csv.DictReader(open(CLAP)) if r.get("duration_mode") != "native"]
    if a.models:
        rows = [r for r in rows if r["model"] in a.models]
    if a.sample_per_model > 0:
        by = {}
        for r in rows:
            by.setdefault(r["model"], []).append(r)
        rows = []
        for m, rs in by.items():
            step = max(1, len(rs) // a.sample_per_model)
            rows += rs[::step][:a.sample_per_model]
    print(f"[specfid] {len(rows)} clips over {len(set(r['model'] for r in rows))} models")

    out = []
    for i, r in enumerate(rows):
        p = CLIPS / r["file"]
        if not p.exists():
            continue
        try:
            m = measure(p, es, algos)
        except Exception as ex:
            print(f"[specfid] skip {r['file']}: {ex}")
            continue
        if m is None:
            continue
        m.update({"file": r["file"], "model": r["model"], "ckpt": r["ckpt"],
                  "cfg": r["cfg"], "strength": r["strength"], "clap_matched": r["clap_matched"]})
        out.append(m)
        if (i + 1) % 100 == 0:
            print(f"[specfid] {i + 1}/{len(rows)}")

    cols = ["file", "model", "ckpt", "cfg", "strength", "clap_matched", "tonal_to_noise",
            "spectral_gini", "spectral_crest", "dissonance", "inharmonicity",
            "spectral_complexity", "flux_cv"]
    with a.out.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        for r in out:
            wr.writerow({k: r.get(k) for k in cols})
    print(f"[specfid] wrote {a.out} ({len(out)} clips)")


if __name__ == "__main__":
    main()
