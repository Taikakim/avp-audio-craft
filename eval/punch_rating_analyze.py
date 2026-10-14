#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-14)
"""punch_rating_analyze.py -- which objective metric tracks Kim's 1-5 improvement ratings? (run after he has rated; reads ratings.jsonl + metrics.json)

For every metric, Spearman rank correlation between the rating and the metric's change (level-matched steered minus original), with n and an approximate p-value, plus the
rating distribution and the mean rating by seed. A metric is only 'a meter of what Kim hears' if it correlates here (AUDIT-THE-INSTRUMENT rule: Audiobox and CLAP have not yet earned that).
    SAO/.venv/bin/python eval/punch_rating_analyze.py
"""
import json
import os
import sys
from collections import Counter

import numpy as np

DATA = "/run/media/kim/Mantu2/sa3_control_runs/punch_rating_20261014"


def spearman(x, y):
    from scipy.stats import spearmanr
    r, p = spearmanr(x, y)
    return float(r), float(p)


def main():
    rat = {}
    for l in open(f"{DATA}/ratings.jsonl"):
        if l.strip():
            r = json.loads(l)
            rat[r["id"]] = r["rating"]
    met = json.load(open(f"{DATA}/metrics.json"))
    man = {e["id"]: e for e in json.load(open(f"{DATA}/manifest.json"))["entries"]}
    ids = [i for i in rat if i in met]
    if len(ids) < 8:
        sys.exit(f"only {len(ids)} rated pairs with metrics; rate more first")
    print(f"{len(ids)} rated pairs. rating distribution:", dict(sorted(Counter(rat[i] for i in ids).items())), f"mean {np.mean([rat[i] for i in ids]):.2f}")
    keys = sorted({k for i in ids for k in met[i]["delta"]})
    rows = []
    for k in keys:
        pairs = [(rat[i], met[i]["delta"][k]) for i in ids if k in met[i]["delta"] and met[i]["delta"][k] == met[i]["delta"][k]]
        if len(pairs) >= 8 and len({p[1] for p in pairs}) > 2:
            r, p = spearman([a for a, _ in pairs], [b for _, b in pairs])
            rows.append((abs(r), k, r, p, len(pairs)))
    print(f"\n{'metric (matched steered minus original)':44s} {'rho':>6s} {'p':>8s} {'n':>4s}")
    for _, k, r, p, n in sorted(rows, reverse=True)[:25]:
        print(f"{k:44s} {r:+6.2f} {p:8.3f} {n:4d}" + ("  *" if p < 0.05 else ""))
    print("\nmean rating by seed (first 16):", {man[i]["seed"]: rat[i] for i in ids[:16]})
    print("NOTE: with ~60 pairs, |rho| < 0.25 is within noise; 25 metrics tested, so expect ~1 false star.")


if __name__ == "__main__":
    main()
