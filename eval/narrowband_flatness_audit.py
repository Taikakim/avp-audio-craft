#!/usr/bin/env python
"""narrowband_flatness_audit.py — Kim 2026-09-16: tests whether spectral flatness
computed WITHIN the 1-3kHz band (rather than broadband hf_ratio) separates the 43
clips Kim flagged as "biting/harsh" from the rest of the 82-clip mixtape corpus.
Per Kim's own diagnosis: broadband HF energy doesn't distinguish a legitimately
bright full mix from a narrowband resonant spike (hi-hat, screaming acid filter) --
a band-local flatness/peakiness measure should. Labels are explicitly noisy (Kim
didn't listen to every clip fully; unflagged ones "seem OK" but not guaranteed) --
audited as a real but imperfect signal, not ground truth. CPU-only, no GPU.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import stft

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
from chroma_morph_transitions import load  # noqa: E402 (has the m4a/ffmpeg fallback)

BAND = (1000.0, 3000.0)


def narrowband_metrics(audio, sr, band=BAND):
    mono = audio.mean(axis=0)
    f, _, Zxx = stft(mono, fs=sr, nperseg=2048, noverlap=1536)
    power = np.abs(Zxx) ** 2
    mask = (f >= band[0]) & (f <= band[1])
    band_power = power[mask, :]
    eps = 1e-12
    gm = np.exp(np.mean(np.log(band_power + eps), axis=0))
    am = np.mean(band_power, axis=0) + eps
    flatness = gm / am
    peak = np.max(band_power, axis=0)
    median = np.median(band_power, axis=0) + eps
    peak_db = 10 * np.log10(peak / median)
    return {
        "flatness_p5": float(np.percentile(flatness, 5)),
        "flatness_median": float(np.median(flatness)),
        "peak_db_p95": float(np.percentile(peak_db, 95)),
        "peak_db_median": float(np.median(peak_db)),
    }


def main():
    clips_json = Path(sys.argv[1])
    tagged_txt = Path(sys.argv[2])
    out_json = Path(sys.argv[3])

    clips = json.loads(clips_json.read_text())
    tagged_files = set(tagged_txt.read_text().strip().splitlines())

    results = []
    for i, c in enumerate(clips):
        audio, sr = load(c["path"])
        m = narrowband_metrics(audio, sr)
        m.update({"id": c["id"], "file": c["file"], "hf_ratio": c.get("hf_ratio"),
                  "flagged": c["file"] in tagged_files})
        results.append(m)
        print(f"[{i:02d}/{len(clips)}] flagged={int(m['flagged'])} "
              f"flat_p5={m['flatness_p5']:.4f} flat_med={m['flatness_median']:.4f} "
              f"peakdB_p95={m['peak_db_p95']:.1f} hf_ratio={m['hf_ratio']}", flush=True)

    out_json.write_text(json.dumps(results, indent=2))

    flagged = [r for r in results if r["flagged"]]
    rest = [r for r in results if not r["flagged"]]
    print(f"\n[groups] flagged n={len(flagged)}  rest n={len(rest)}", flush=True)
    for key in ("flatness_p5", "flatness_median", "peak_db_p95", "peak_db_median"):
        fv = [r[key] for r in flagged]
        rv = [r[key] for r in rest]
        print(f"  {key}: flagged mean={np.mean(fv):.4f} median={np.median(fv):.4f} | "
              f"rest mean={np.mean(rv):.4f} median={np.median(rv):.4f}", flush=True)

    # rank-based separation check (Mann-Whitney U via rank sum, no scipy.stats dependency assumed here)
    from scipy.stats import mannwhitneyu
    for key in ("flatness_p5", "flatness_median", "peak_db_p95", "peak_db_median"):
        fv = [r[key] for r in flagged]
        rv = [r[key] for r in rest]
        u, p = mannwhitneyu(fv, rv, alternative="two-sided")
        auc = u / (len(fv) * len(rv))
        print(f"  {key}: Mann-Whitney U p={p:.4f}  AUC-like separation={auc:.3f} "
              f"(0.5=no separation, closer to 0 or 1=better)", flush=True)

    # baseline: does broadband hf_ratio separate them at all, for comparison?
    fv = [r["hf_ratio"] for r in flagged if r["hf_ratio"] is not None]
    rv = [r["hf_ratio"] for r in rest if r["hf_ratio"] is not None]
    u, p = mannwhitneyu(fv, rv, alternative="two-sided")
    auc = u / (len(fv) * len(rv))
    print(f"  [baseline] hf_ratio: Mann-Whitney U p={p:.4f} AUC-like={auc:.3f}", flush=True)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
