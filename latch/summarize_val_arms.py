#!/usr/bin/env python3
"""summarize_val_arms.py — read LatCH training logs that carry a held-out val curve and say,
per arm, whether the head generalised and where it turned over.

WHY (C, 2026-08-18): with a val curve there is finally something to read, and the thing worth
reading is not the final number — it is the GAP between the best val epoch and the last one. A
head whose val loss bottoms at epoch 12 and climbs for the next 28 is a head we have been
training 3x too long, and until today nothing in the pipeline could have told us: train_latch.py
had no val set, so `_best.pt` was the lowest TRAINING loss = the most-memorised epoch.

WHAT THE COLUMNS MEAN
    best_val / @ep   the honest score and the epoch that earned it
    last_val         val at the final epoch; >> best_val means the run trained past its peak
    overfit          last_val / best_val - 1. Positive = it got worse after the peak.
    train_gap        last_train / last_val. Far below 1 = memorising (train loss much lower
                     than held-out loss on tracks it has never seen).
A run whose best epoch is the LAST one is not converged — it was still improving when the
epoch budget ran out, and the right response is more epochs, not a verdict.

USAGE
  python3 latch/summarize_val_arms.py latch/val_arm_logs/
  python3 latch/summarize_val_arms.py <dir-or-logs...> --json
Only stdlib.
"""
import argparse
import json
import re
from pathlib import Path

EPOCH_RE = re.compile(r"epoch (\d+)/(\d+)\s+loss=([0-9.]+)")
VAL_RE = re.compile(r"val=([0-9.]+)")
SPLIT_RE = re.compile(r"Val split: (\d+) crops from (\d+) held-out (\S+?)\(s\) / (\d+) total; (\d+)")


def parse(path):
    """One arm -> its curve. Pairs each `epoch N loss=` line with the `val=` line that follows
    it, which is how train_latch.py emits them (val is printed after the epoch line)."""
    rows, split, pending = [], None, None
    for line in Path(path).read_text(errors="replace").splitlines():
        m = SPLIT_RE.search(line)
        if m:
            split = {"val_crops": int(m.group(1)), "val_groups": int(m.group(2)),
                     "group_by": m.group(3), "total_groups": int(m.group(4)),
                     "train_crops": int(m.group(5))}
        m = EPOCH_RE.search(line)
        if m:
            if pending is not None:
                rows.append(pending)                      # epoch with no val line
            pending = {"epoch": int(m.group(1)), "train": float(m.group(3)), "val": None}
            continue
        m = VAL_RE.search(line)
        if m and pending is not None:
            pending["val"] = float(m.group(1))
            rows.append(pending)
            pending = None
    if pending is not None:
        rows.append(pending)
    return {"arm": Path(path).stem, "split": split, "rows": rows}


def analyse(a):
    rows = [r for r in a["rows"] if r["val"] is not None]
    if not rows:
        return None
    best = min(rows, key=lambda r: r["val"])
    last = rows[-1]
    return {
        "arm": a["arm"], "n_epochs": len(rows),
        "best_val": best["val"], "best_ep": best["epoch"],
        "last_val": last["val"], "last_train": last["train"],
        "overfit": last["val"] / best["val"] - 1.0 if best["val"] else 0.0,
        "train_gap": last["train"] / last["val"] if last["val"] else 0.0,
        "still_improving": best["epoch"] == last["epoch"],
        "split": a["split"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="log files, or dirs of *.log")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    logs = []
    for p in a.paths:
        p = Path(p)
        logs.extend(sorted(p.glob("*.log")) if p.is_dir() else [p])
    res = [r for r in (analyse(parse(p)) for p in logs) if r]
    if not res:
        print("no arms with a val curve found (was --val-frac set?)")
        return 1

    if a.json:
        print(json.dumps(res, indent=2))
        return 0

    print(f"{'arm':<32} {'ep':>3} {'best_val':>9} {'@ep':>4} {'last_val':>9} "
          f"{'overfit':>8} {'tr/val':>7}  note")
    print("-" * 96)
    for r in sorted(res, key=lambda r: r["best_val"]):
        note = []
        if r["still_improving"]:
            note.append("STILL-IMPROVING (needs more epochs, not a verdict)")
        elif r["overfit"] > 0.05:
            note.append(f"turned over at ep{r['best_ep']}")
        if r["train_gap"] < 0.7:
            note.append("MEMORISING (train << held-out)")
        print(f"{r['arm']:<32} {r['n_epochs']:>3} {r['best_val']:>9.4f} {r['best_ep']:>4} "
              f"{r['last_val']:>9.4f} {r['overfit']:>+7.1%} {r['train_gap']:>7.2f}  "
              + "; ".join(note))
    s = res[0]["split"]
    if s:
        print(f"\nheld-out: {s['val_crops']} crops from {s['val_groups']}/{s['total_groups']} "
              f"{s['group_by']}s ({s['train_crops']} crops train)")
    print("\nThese are REGRESSION losses on held-out tracks — they say the head predicts f0 it has")
    print("never seen, which is necessary but NOT sufficient. Steering authority and the")
    print("disintegration gate are separate questions, and Kim's ears decide the last one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
