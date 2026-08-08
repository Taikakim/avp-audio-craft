#!/usr/bin/env python3
"""check_render_complete.py — assert a render job produced what its task list specified.

WHY THIS EXISTS (W 2026-08-09): sa3_lenvar_hq (20663606) exited COMPLETED, printed
"DONE. artifacts: 5336 wav", and sat for four days before anyone compared 5336 against the
6690 the task list actually specified. All 110 ptm tasks had died instantly — the
post-trained model was only partially in the HF cache and LUMI compute nodes have no
internet — but a per-task failure doesn't fail the job, and the summary line only counted
what it found. A COMPLETED job with 80% of its output looks exactly like a finished one.

    lumi/check_render_complete.py --tasks lumi/length_variant_tasks.txt \\
                                  --out /scratch/.../renders/length_variant [--code /path]

Exit 0 only if actual >= expected. Prints the per-model shortfall so a partial run tells you
WHICH cells are missing, not just that some are.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path


def expected_from_tasks(tasks: Path, code: Path):
    """Total cells the task list specifies, and per-label expectations."""
    snaps, total, per_label = {}, 0, collections.Counter()
    for line in tasks.read_text().splitlines():
        if not line.strip():
            continue
        m = re.search(r"--prompts\s+(\S+)", line)
        if not m:
            continue
        snap = Path(m.group(1))
        if not snap.exists():                      # rewrite a LUMI path to the local checkout
            snap = code / "lumi" / snap.name
        if snap not in snaps:
            snaps[snap] = json.loads(snap.read_text())
        d = snaps[snap]
        n_prompts = len(d["prompts"])
        cfgs = d["cfgs"]
        only = re.search(r"--only-cfgs\s+(\S+)", line)
        n_cfgs = len(only.group(1).split(",")) if only else len(cfgs)
        st = re.search(r"--strengths\s+(\S+)", line)
        n_str = len(st.group(1).split(",")) if st else 1
        label = re.search(r"--label\s+(\S+)", line).group(1)
        n = n_prompts * n_cfgs * n_str
        total += n
        per_label[label] += n
    return total, per_label


def actual(out: Path):
    per = collections.Counter()
    for f in out.glob("*.wav"):
        per[f.name.split("__")[0]] += 1
    return sum(per.values()), per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--code", type=Path, default=Path(__file__).resolve().parent.parent)
    a = ap.parse_args()

    exp_total, exp_label = expected_from_tasks(a.tasks, a.code)
    act_total, act_label = actual(a.out)
    print(f"[check] expected {exp_total} cells | actual {act_total} wav | delta {act_total-exp_total:+d}")

    short = [(l, exp_label[l], act_label.get(l, 0)) for l in exp_label
             if act_label.get(l, 0) < exp_label[l]]
    if short:
        print(f"[check] {len(short)} of {len(exp_label)} labels short:")
        for l, e, g in sorted(short, key=lambda x: x[2] - x[1])[:25]:
            print(f"    {g:>5}/{e:<5} ({g-e:+d})  {l}")
    if act_total < exp_total:
        print(f"[check] FAIL: {exp_total-act_total} cells missing -- the job is NOT complete "
              f"regardless of its exit status")
        sys.exit(1)
    print("[check] OK: every task's cells are present")


if __name__ == "__main__":
    main()
