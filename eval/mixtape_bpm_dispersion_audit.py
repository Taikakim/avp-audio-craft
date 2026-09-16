#!/usr/bin/env python
"""mixtape_bpm_dispersion_audit.py — Kim 2026-09-16: mixtape_madmom_bpm.py reported a
median inter-downbeat interval with no dispersion check -- a clip with a genuinely
beatless intro/breakdown/outro could still get a confidently-reported but actually
noisy BPM. This re-runs madmom on all 82 clips and reports, per clip: n downbeats,
the interval MAD (median absolute deviation, robust) as a fraction of the median
interval, and the fraction of intervals more than 20% off the median (candidate
beatless/mistracked segments). CPU-only, no GPU.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
from chroma_morph_transitions import load  # noqa: E402
from dj_beatmatch import madmom_downbeats  # noqa: E402


def main():
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    clips = json.loads(in_path.read_text())
    results = []
    for i, c in enumerate(clips):
        audio, sr = load(c["path"])
        downbeats = madmom_downbeats(audio, sr)
        diffs = np.diff(downbeats) if len(downbeats) >= 2 else np.array([])
        if len(diffs) == 0:
            results.append({**c, "n_downbeats": len(downbeats), "mad_frac": None, "outlier_frac": None})
            print(f"[{i:02d}] {c['file'][:50]:50s} n_db={len(downbeats)} -- no intervals", flush=True)
            continue
        med = float(np.median(diffs))
        mad = float(np.median(np.abs(diffs - med)))
        mad_frac = mad / med if med > 0 else None
        outlier_frac = float(np.mean(np.abs(diffs - med) / med > 0.20)) if med > 0 else None
        results.append({**c, "n_downbeats": len(downbeats), "mad_frac": mad_frac, "outlier_frac": outlier_frac})
        flag = "  <-- HIGH DISPERSION" if (mad_frac is not None and mad_frac > 0.05) else ""
        print(f"[{i:02d}] {c['file'][:50]:50s} n_db={len(downbeats):3d} "
              f"mad_frac={mad_frac:.3f} outlier_frac={outlier_frac:.2f}{flag}", flush=True)

    bad = [r for r in results if r["mad_frac"] is not None and r["mad_frac"] > 0.05]
    print(f"\n[summary] {len(bad)}/{len(results)} clips with MAD > 5% of median interval", flush=True)
    for r in bad:
        print(f"  {r['file']}  bpm={r['bpm']:.1f}  mad_frac={r['mad_frac']:.3f}  "
              f"outlier_frac={r['outlier_frac']:.2f}  n_db={r['n_downbeats']}", flush=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"[done] wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
