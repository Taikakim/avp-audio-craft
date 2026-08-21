#!/usr/bin/env python3
"""make_slim_pull_list.py — build the selective slim-pull list (Kim's retention rule
applied to the PULL, 2026-08-21): per run, keep epochs {last, ~50%, ~75%} plus, for runs
longer than 15 epochs, every ceil(20% of span) epochs walking back while > ep15.

Run ON LUMI (login node, plain python3):
    python3 /project/project_465003186/code/lumi/make_slim_pull_list.py
Writes /scratch/project_465003186/pull_list.txt (paths relative to /scratch/.../runs) and
prints a summary. NOT /tmp: LUMI /tmp is PER LOGIN NODE, so a list written on uan18 is
invisible after the next login lands on uan14 — that is a silent "file not found" on the
--files-from=:PATH remote read. Override with PULL_LIST_OUT=<path>.
Then pull from the LOCAL terminal (--partial-dir, so a blackout mid-file resumes rather
than orphaning a multi-GB .name.XXXXXX temp; plain rsync temps are NOT reused):
    rsync -av --partial-dir=.rsync-partial -e "ssh -i ~/.ssh/id_EFP" \
      --files-from=:/scratch/project_465003186/pull_list.txt \
      akekim@efp.lumi.csc.fi:/scratch/project_465003186/runs/ <local dest>/
(single line in practice; the --files-from=:PATH form reads the list from the REMOTE side)
"""
import glob
import math
import os
import re

ROOT = "/scratch/project_465003186/runs"


def keep_epochs(eps):
    eps = sorted(set(eps))
    if not eps:
        return set()
    last = eps[-1]
    span = last + 1

    def nearest(t):
        return min(eps, key=lambda e: (abs(e - t), -e))

    keep = {last, nearest(round(0.50 * last)), nearest(round(0.75 * last))}
    if span > 15:
        step = max(1, math.ceil(0.2 * span))
        e = last - step
        while e > 15:
            keep.add(nearest(e))
            e -= step
    return keep


def main():
    sel, n_all = [], 0
    dirs = sorted(glob.glob(ROOT + "/*/")) + sorted(glob.glob(ROOT + "/*/*/"))
    for d in dirs:
        cks = sorted(glob.glob(d + "epoch=*.weights.ckpt"))
        if not cks:
            continue
        n_all += len(cks)
        by_ep = {}
        for c in cks:
            m = re.search(r"epoch=(\d+)", os.path.basename(c))
            if m:
                by_ep.setdefault(int(m.group(1)), []).append(c)
        for e in keep_epochs(list(by_ep)):
            for c in by_ep[e]:
                sel.append(os.path.relpath(c, ROOT))
    out = os.environ.get("PULL_LIST_OUT", "/scratch/project_465003186/pull_list.txt")
    with open(out, "w") as f:
        f.write("\n".join(sorted(sel)) + "\n")
    tot = sum(os.path.getsize(os.path.join(ROOT, p)) for p in sel)
    print(f"[pull-list] {len(sel)} of {n_all} slims selected, {tot/1e9:.0f} GB -> {out}")


if __name__ == "__main__":
    main()
