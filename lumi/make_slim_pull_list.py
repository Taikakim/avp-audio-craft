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


MIN_GAP = 2   # --min-gap: see keep_epochs


def keep_epochs(eps, min_gap=None):
    eps = sorted(set(eps))
    if not eps:
        return set()
    last = eps[-1]
    span = last + 1

    def nearest(t):
        return min(eps, key=lambda e: (abs(e - t), -e))

    # PRIORITY ORDER matters once min_gap is enforced: the terminal epoch is never dropped, then
    # 75%, then 50%, then the ladder. A pick closer than min_gap to an already-kept epoch is
    # DISCARDED -- on a short run 50% and 75% land adjacent (epochs 0..7 -> 4 and 5) and we were
    # pulling two near-identical 4.6 GB full-FT slims for one run. Kim spotted it in the transfer
    # listing 2026-08-22. min_gap=0 restores the old behaviour.
    # SHORT RUNS (span <= 10): {last, mid} ONLY -- Kim 2026-08-22, from the transfer listing:
    # "for runs of 10 and less, take the last and mid checkpoint". {last,50%,75%} bunches on a
    # short run (epochs 0..7 -> 4,5,7: two ADJACENT picks) and at 4.6 GB per full-FT slim that is
    # a wasted copy per run. Kim also recalled an exponential ladder toward the end; measured and
    # REJECTED -- it keeps MORE files on long runs (320ep: 11 vs 7) and leaves a hole between ep0
    # and ep63, which is precisely where the proven cooked-early case lives (bf16cmp_goa peaks
    # ep0-1). Short-run thinning yes; end-weighted curve no.
    if span <= 10:
        return {last, nearest(round(0.50 * last))}
    gap = MIN_GAP if min_gap is None else int(min_gap)
    keep = []

    def add(e):
        if e is None:
            return
        if any(abs(e - k) < gap for k in keep):
            return
        if e not in keep:
            keep.append(e)

    add(last)
    add(nearest(round(0.75 * last)))
    add(nearest(round(0.50 * last)))
    if span > 15:
        step = max(1, math.ceil(0.2 * span))
        e = last - step
        while e > 15:
            add(nearest(e))
            e -= step
    return set(keep)


def main():
    global MIN_GAP
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-gap", type=int, default=MIN_GAP,
                    help="discard a kept epoch that is closer than this many epochs to one already "
                         "kept (terminal wins, then 75%%, then 50%%, then the ladder). 0 = old "
                         "behaviour. Default 2; 3 spreads short runs wider.")
    MIN_GAP = ap.parse_args().min_gap
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
