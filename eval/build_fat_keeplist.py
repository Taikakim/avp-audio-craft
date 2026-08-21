#!/usr/bin/env python3
"""build_fat_keeplist.py — PQ-aware fat-checkpoint retention (Kim 2026-08-21: "a 60ep model
might have cooked at ep20 already... check PQ scores to determine the sequence").

Queries clip_metrics.db for per-(run,epoch) mean PQ (from rendered cells named
<run>__epN__...), and per run emits the FAT-keep epochs: {last, PQ-argmax epoch, its
rendered neighbours (one ckpt either side)}. Runs with no scored cells are omitted —
the prune tool falls back to --fat-policy kim for them.

Output: fat_keeplist.json {run_name: [epochs]} -> rsync to LUMI ->
  prune_optimizer_states.py --fat-policy kim --keep-list .../fat_keeplist.json
"""
import json
import re
import sqlite3
from collections import defaultdict

DB = "/home/kim/Projects/SAO/eval/clip_metrics.db"
OUT = "/home/kim/Projects/SAO/eval/fat_keeplist.json"

rows = sqlite3.connect(DB).execute(
    "SELECT path, pq FROM metrics WHERE pq IS NOT NULL AND path LIKE '%__ep%'").fetchall()
acc = defaultdict(lambda: defaultdict(list))
for p, pq in rows:
    m = re.search(r"([A-Za-z0-9_.\-]+)__ep(\d+)__", p.rsplit("/", 1)[-1])
    if m:
        acc[m.group(1)][int(m.group(2))].append(pq)

keep = {}
for run, eps in acc.items():
    if len(eps) < 3:
        continue
    mean = {e: sum(v) / len(v) for e, v in eps.items()}
    order = sorted(mean)
    best = max(mean, key=mean.get)
    i = order.index(best)
    sel = {order[-1], best}
    if i > 0: sel.add(order[i - 1])
    if i < len(order) - 1: sel.add(order[i + 1])
    keep[run] = sorted(sel)

json.dump(keep, open(OUT, "w"), indent=1)
print(f"[keeplist] {len(keep)} runs with PQ-derived retention -> {OUT}")
for r in sorted(keep)[:8]:
    print(f"  {r}: {keep[r]}")
