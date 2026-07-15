#!/usr/bin/env python3
"""width_metric.py — stereo-width level stats for eval manifests (C's gate-(b)
follow-up, 2026-07-15: width is a standard eval column for long-context arms
and the fp32 campaign's a2a evals).

Computes the gate-validated statistics per clip — width mean/std (side/(mid+side)
RMS, [0,1], 0=mono), L/R Pearson correlation mean, early/late quarter means —
and merges them into the run dir's run_meta.json under `width_metrics`
{clip_basename: {...}}. The meter is the same code the corpus sidecars carry
(mir whole_track_expanded._stereo_fields), so eval numbers and corpus bands are
comparable. Reference points from the gate pair (base model, 380 s, 24 steps):
single-shot T=4096 width ~0.24 / corr ~0.74; windowed T=1024 ~0.36 / ~0.40.

Run (mir venv):
  /home/kim/Projects/mir/mir/bin/python eval/width_metric.py <run_dir_or_wavs...>
"""
import json
import os
import sys

sys.path.insert(0, "/home/kim/Projects/mir/src")
import numpy as np
from core.file_utils import read_audio
from spectral.whole_track_expanded import ExpandedExtractor

_ex = ExpandedExtractor(enable_models=False)


def width_stats(path: str) -> dict:
    raw, sr = read_audio(path)
    if raw.ndim == 1 or raw.shape[1] != 2:
        return {"mono_source": True}
    f = _ex._stereo_fields(raw.astype(np.float32), raw.shape[0], sr, 100)
    w, c = f["stereo_width_ts"], f["stereo_corr_ts"]
    n = len(w)
    return {"width_mean": round(float(w.mean()), 4),
            "width_std": round(float(w.std()), 4),
            "corr_mean": round(float(c.mean()), 4),
            "width_early": round(float(w[: n // 4].mean()), 4),
            "width_late": round(float(w[-n // 4:].mean()), 4)}


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    wavs, run_dirs = [], set()
    for a in args:
        if os.path.isdir(a):
            run_dirs.add(a)
            wavs += [os.path.join(a, f) for f in sorted(os.listdir(a))
                     if f.lower().endswith((".wav", ".flac"))]
        else:
            wavs.append(a)
            run_dirs.add(os.path.dirname(a) or ".")
    per_dir = {}
    for p in wavs:
        s = width_stats(p)
        per_dir.setdefault(os.path.dirname(p) or ".", {})[os.path.basename(p)] = s
        print(f"{os.path.basename(p)}: {s}")
    for d, table in per_dir.items():
        meta_path = os.path.join(d, "run_meta.json")
        meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
        meta.setdefault("width_metrics", {}).update(table)
        tmp = meta_path + ".tmp"
        json.dump(meta, open(tmp, "w"), indent=2, ensure_ascii=False)
        os.replace(tmp, meta_path)
        print(f"[width] {len(table)} clips -> {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
