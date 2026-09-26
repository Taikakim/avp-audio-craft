#!/usr/bin/env python3
"""Per-arm statistics of rendered z0 latents at the operating point, incl. melody-subspace energy.

For each board label matching --pattern (plus the un-adapted medium-base reference 'base__base'),
over its standard 20 s cfg7/w100 cells on the 12 canonical prompts:
  - global z0 std (the publish gate's statistic; healthy ~1.0),
  - per-channel std spread: max and median channel std, and max/median,
  - melody-subspace energy share: ||P z||^2 / ||z||^2 with P the orthonormal 15-row v3 basis
    (lumi/melody_subspace15_selective_v3.npz) -- the subspace the subloss arms upweight in training,
    so this asks whether that training shows up in what the model GENERATES.
Written for the 2026-09-26 goa5k ablation (W); CPU only, reads *.z0.npy beside the board clips.

Run: python3 eval/latent_stats_by_arm.py --pattern ablation_goa5k_ --pattern goa5k_r128 [--out f.md]
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

RD = Path("/run/media/kim/Mantu/sa3_lora_runs/model_matrix")
BASIS = Path(__file__).resolve().parents[1] / "lumi/melody_subspace15_selective_v3.npz"
CANON = {"rb_common_0", "rb_common_1", "rb_common_2", "rb_mid_3", "rb_mid_4", "rb_mid_5",
         "rb_rare_6", "rb_rare_7", "rb_rare_8", "kl_0", "kl_1", "kl_2"}
RX = re.compile(r"^(?P<label>.+?)__(?P<ckpt>[^_]+(?:=\d+)?)__cfg7__w100__(?P<pid>[a-z_0-9]+)__s\d+\.z0\.npy$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", action="append", required=True, help="label prefix (repeatable)")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    P = np.load(BASIS)["basis15"].astype(np.float64)                       # [15, 256]
    groups = defaultdict(list)
    for f in RD.glob("*__cfg7__w100__*.z0.npy"):
        m = RX.match(f.name)
        if not m or m["pid"] not in CANON:
            continue
        lab = m["label"]
        if lab == "base" or any(lab.startswith(p) for p in a.pattern):
            groups[lab].append(f)
    rows = []
    for lab in sorted(groups, key=lambda s: (s != "base", s)):
        g_std, ch_max, ch_med, sub = [], [], [], []
        for f in groups[lab]:
            z = np.load(f).astype(np.float64)[0]                               # [256, T]
            if not np.isfinite(z).all():
                continue
            g_std.append(z.std())
            cs = z.std(axis=1)
            ch_max.append(cs.max()); ch_med.append(np.median(cs))
            sub.append(float((P @ z).__pow__(2).sum() / (z ** 2).sum()))
        if not g_std:
            continue
        rows.append((lab, len(g_std), np.mean(g_std), np.mean(ch_max), np.mean(ch_med),
                     np.mean(ch_max) / np.mean(ch_med), np.mean(sub), np.std(sub)))
    lines = ["| label | n | z0 std | max chan std | median chan std | max/median | melody-subspace share (±sd) |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r[0]} | {r[1]} | {r[2]:.3f} | {r[3]:.3f} | {r[4]:.3f} | {r[5]:.2f} | {r[6]:.4f} ± {r[7]:.4f} |")
    txt = "\n".join(lines) + "\n"
    print(txt)
    if a.out:
        a.out.write_text(txt)


if __name__ == "__main__":
    main()
