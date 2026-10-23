#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-23)
"""latch_head_soup.py -- weight-average ("soup") LatCH guidance heads into one checkpoint the renderers load like any head.

Two modes:
  --in A.pt:0.5 --in B.pt:0.5           explicit weights (renormalised to sum 1), e.g. a Muon / KL-SOAP 50/50
  --bell DIR --center 29 --sigma 3      Gaussian weights over the epoch checkpoints in DIR (latch_sa3_<feat>_ep<N>.pt),
                                        centred on an epoch (default: the _best.pt's epoch), cut at 3 sigma
Ingredients must share architecture (same keys/shapes) and target standardisation (std_mean/std_std); the script refuses
otherwise. Heads trained from the same --seed start from the same weights, which is what makes cross-optimizer soups
plausible at all; whether they land in one basin is the question the render answers.
The output keeps the first ingredient's metadata and adds "soup": the ingredients, their weights and epochs/val losses.
RUN (any venv with torch, CPU only):  python eval/latch_head_soup.py --in a.pt:1 --in b.pt:1 --out soup.pt
"""
import argparse
import glob
import math
import os
import re
import sys

import torch


def load(p):
    return torch.load(p, map_location="cpu", weights_only=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="ins", action="append", default=[], help="path.pt[:weight], repeatable")
    ap.add_argument("--bell", default="", help="run dir with per-epoch checkpoints")
    ap.add_argument("--center", type=float, default=None, help="bell centre epoch (default: the _best.pt epoch)")
    ap.add_argument("--sigma", type=float, default=3.0, help="bell width in epochs")
    ap.add_argument("--feature", default="onset_per_beat_ts")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    items = []   # (path, weight)
    if a.bell:
        best = os.path.join(a.bell, f"latch_sa3_{a.feature}_best.pt")
        c = a.center if a.center is not None else load(best)["epoch"]
        eps = {}
        for p in glob.glob(os.path.join(a.bell, f"latch_sa3_{a.feature}_ep*.pt")):
            m = re.search(r"_ep(\d+)\.pt$", p)
            if m:
                eps[int(m.group(1))] = p
        if os.path.exists(best):
            eps.setdefault(load(best)["epoch"], best)   # the best epoch is often between saved epochs
        for e, p in sorted(eps.items()):
            if abs(e - c) <= 3 * a.sigma:
                items.append((p, math.exp(-0.5 * ((e - c) / a.sigma) ** 2)))
        if len(items) < 2:
            sys.exit(f"bell: fewer than 2 epoch checkpoints within 3 sigma of epoch {c} in {a.bell} (have {sorted(eps)})")
    for s in a.ins:
        p, _, w = s.rpartition(":") if re.search(r":[0-9.eE+-]+$", s) else (s, "", "1")
        items.append((p, float(w)))
    if len(items) < 2:
        sys.exit("need at least two ingredients")
    tot = sum(w for _, w in items)
    items = [(p, w / tot) for p, w in items]

    cks = [load(p) for p, _ in items]
    ref = cks[0]
    keys = set(ref["state_dict"])
    for (p, _), c in zip(items, cks):
        if set(c["state_dict"]) != keys or any(c["state_dict"][k].shape != ref["state_dict"][k].shape for k in keys):
            sys.exit(f"architecture differs: {p}")
        for k in ("std_mean", "std_std", "feature_name", "t_injection"):
            if c.get(k) != ref.get(k):
                sys.exit(f"{k} differs: {p} ({c.get(k)} vs {ref.get(k)})")
    sd = {}
    for k in ref["state_dict"]:
        v0 = ref["state_dict"][k]
        if v0.is_floating_point():
            sd[k] = sum(w * c["state_dict"][k].double() for (_, w), c in zip(items, cks)).to(v0.dtype)
        else:
            sd[k] = v0.clone()   # integer buffers (if any) are taken from the first ingredient
    out = {k: v for k, v in ref.items() if k not in ("state_dict", "optimizer_state")}
    out["state_dict"] = sd
    out["val_loss"] = None   # a soup has no measured held-out loss until someone evaluates it
    out["soup"] = [{"path": p, "weight": round(w, 4), "epoch": c.get("epoch"), "val_loss": c.get("val_loss"),
                    "optimizer": c.get("optimizer")} for (p, w), c in zip(items, cks)]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    torch.save(out, a.out)
    for s in out["soup"]:
        print(f"  {s['weight']:.3f}  ep{s['epoch']}  val {s['val_loss']}  {s['optimizer']}  {os.path.basename(os.path.dirname(s['path']))}/{os.path.basename(s['path'])}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
