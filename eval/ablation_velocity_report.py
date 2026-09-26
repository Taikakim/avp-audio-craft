#!/usr/bin/env python3
"""Report for eval/ablation_goa5k_chain.py: how far each arm moved by step 1011, and its loss.

DoRA initialises lora_B to ZERO, so ||lora_B|| at step 1011 is exactly the distance B travelled --
a clean per-arm velocity that needs no step-0 checkpoint. Also reported: ||lora_A||, the norm of
the DoRA magnitude vectors, and the mean train loss over the last 100 logged steps (CSV logger).
The reference run's own step=1011.ckpt is included as 'ref' (W&B-logged, so no loss column).

Run (CPU is fine): .venv/bin/python eval/ablation_velocity_report.py [--out report.md]
"""
import argparse
import csv
import math
from pathlib import Path

import torch

ROOT = Path("/run/media/kim/Mantu/sa3_lora_runs")
OUT = ROOT / "ablation_goa5k_2026-09-26"
REF = ROOT / "goa5k_r128_shampoo_subloss_k5_2026-09-26" / "step=1011.ckpt"


def norms(ckpt):
    sd = torch.load(ckpt, map_location="cpu", mmap=True, weights_only=False)["state_dict"]
    acc = {"lora_B": 0.0, "lora_A": 0.0, "magnitude": 0.0}
    for k, v in sd.items():
        for kind in acc:
            if kind in k:
                acc[kind] += float(v.float().pow(2).sum())
    return {k: math.sqrt(v) for k, v in acc.items()}


def last_loss(run_dir, n=100):
    f = next(iter(sorted(run_dir.rglob("metrics.csv"))), None)
    if not f:
        return None
    rows = list(csv.DictReader(open(f)))
    col = next((c for c in (rows[0] if rows else {}) if c in ("train/loss", "train_loss", "loss")), None)
    vals = [float(r[col]) for r in rows if col and r.get(col)] if col else []
    return sum(vals[-n:]) / len(vals[-n:]) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT / "REPORT.md")
    a = ap.parse_args()
    entries = [("ref (overnight run @1011)", REF, None)]
    for d in sorted(OUT.glob("ablation_goa5k_a*")):
        entries.append((d.name.removeprefix("ablation_goa5k_"), d / "step=1011.ckpt", d))
    lines = ["| arm | ‖lora_B‖ (= distance moved) | ‖lora_A‖ | ‖magnitude‖ | loss, last 100 |",
             "|---|---|---|---|---|"]
    for name, ck, d in entries:
        if not ck.exists():
            lines.append(f"| {name} | (no checkpoint) | | | |")
            continue
        n = norms(ck)
        lo = last_loss(d) if d else None
        lines.append(f"| {name} | {n['lora_B']:.2f} | {n['lora_A']:.2f} | {n['magnitude']:.2f} | "
                     f"{'' if lo is None else f'{lo:.4f}'} |")
    txt = ("# Shampoo-recipe ablation: distance moved by step 1011\n\n"
           "Cumulative: each arm drops one more component than the one above it "
           "(see eval/ablation_goa5k_chain.py). a10 is the FULL recipe at lr 5e-4.\n\n"
           + "\n".join(lines) + "\n")
    a.out.write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
