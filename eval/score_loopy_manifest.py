#!/usr/bin/env python3
"""score_loopy_manifest.py -- E0 meter validation (plan 2026-07-15 §2-E0).

Scores every clip in eval/loopy_labeled_manifest.json with mir's recurrence meter
(novelty_curve + dynamics_stats), computes per-statistic AUC (loopy vs good), and
adds a SYNTHETIC arm: each good clip also scored as a tiled-loop construction
(15 s segment tiled to full length) -- ground-truth-by-construction positives to
supplement the n=8 real-loopy side (F's manifest shortfall_note, 2026-07-15).

Run with the mir venv (librosa):
  /home/kim/Projects/mir/mir/bin/python eval/score_loopy_manifest.py
Writes eval/loopy_scores.json and prints the AUC table.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/kim/Projects/mir/src/tools")
from recurrence_meter import calibrate_source, dynamics_stats, novelty_curve  # noqa: E402

SAO = Path("/home/kim/Projects/SAO")
MANIFEST = SAO / "eval/loopy_labeled_manifest.json"
OUT = SAO / "eval/loopy_scores.json"

# statistic -> orientation (+1: higher = loopier, -1: lower = loopier)
STATS = {
    "r_max": +1, "r_median": +1, "novelty_floor": -1,
    "corr_dim": -1, "det": +1, "det_soft": +1,
    "line_frac_8s": +1, "line_frac_16s": +1, "l_max_sec": +1,
}


def score_signal(y, sr):
    cal = calibrate_source(y, sr=sr)
    dyn = dynamics_stats(y, sr=sr)
    row = {k: cal.get(k) for k in ("r_max", "r_median", "novelty_floor")}
    row.update({k: dyn.get(k) for k in STATS if k not in row})
    row["n_patches"] = dyn.get("n_patches")
    return row


def auc(pos, neg):
    """Mann-Whitney AUC: P(pos > neg) + 0.5*ties."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return None
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(pos) * len(neg)))


def main():
    import librosa
    man = json.load(open(MANIFEST))
    rows = []
    for c in man["clips"]:
        y, sr = librosa.load(c["path"], sr=22050, mono=True)
        row = {"path": c["path"], "label": c["label"], "arm": "real",
               "dur_sec": round(len(y) / sr, 1), **score_signal(y, sr)}
        rows.append(row)
        print(f"  scored [{c['label']:5s}] {Path(c['path']).name} ({row['dur_sec']}s)")
        # synthetic arm: tile a mid-clip 15 s segment to the full length
        if c["label"] == "good" and len(y) > 40 * sr:
            seg = y[len(y) // 3: len(y) // 3 + 15 * sr]
            loop = np.tile(seg, int(np.ceil(len(y) / len(seg))))[: len(y)]
            rows.append({"path": c["path"], "label": "loopy", "arm": "synthetic",
                         "dur_sec": round(len(y) / sr, 1), **score_signal(loop, sr)})

    def table(arm_filter, title):
        print(f"\n=== AUC ({title}) ===")
        out = {}
        for stat, orient in STATS.items():
            pos = [r[stat] for r in rows if r["label"] == "loopy" and r[stat] is not None
                   and arm_filter(r)]
            neg = [r[stat] for r in rows if r["label"] == "good" and r[stat] is not None]
            a = auc(np.array(pos) * orient, np.array(neg) * orient)
            out[stat] = a
            if a is not None:
                print(f"  {stat:15s} AUC={a:.3f}   (n_loopy={len(pos)}, n_good={len(neg)})")
        return out

    auc_real = table(lambda r: r["arm"] == "real", "real labels: 8 loopy vs 15 good")
    auc_synth = table(lambda r: r["arm"] == "synthetic", "synthetic tiled-loops vs good")

    OUT.write_text(json.dumps({"rows": rows, "auc_real": auc_real,
                               "auc_synthetic": auc_synth,
                               "manifest_shortfall": man.get("shortfall_note")}, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
