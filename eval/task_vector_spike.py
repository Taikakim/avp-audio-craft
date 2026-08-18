#!/usr/bin/env python3
"""task_vector_spike.py — the top singular directions of each adapted matrix's B·A, per model,
and whether the DEGRADED models' dominant directions agree with each other, with the healthy
models, and across matrices — i.e. is the spike a shared systematic direction (repairable by
projection) or a per-run accident.

CONTEXT (C, 2026-08-18): task_vector_gram.py found the AdamW-sweep arms carry 20-30 % of each
matrix's ΔW energy in ONE singular direction (effective rank ~56 of 128) where every healthy run,
at every epoch and config, is flat (2.1 %, eff-rank ~118). A spike is only actionable if it is
the SAME direction across arms (then it is a systematic effect of the regime, and projecting it
out of a bad checkpoint is a well-posed repair). If each arm's spike points somewhere different,
the spike is a symptom of something else and projection is not the tool.

MEASURES (from the on-disk factor cache task_vector_gram.load_adapter builds; no base needed
because this is about B·A, the trained direction, and DoRA's row-scaling cannot rotate it):
  per matrix, per model:  top-3 σ² fractions, left/right top vectors u1 (out-space) v1 (in-space)
  across models, per matrix: |cos(u1_i,u1_j)| and |cos(v1_i,v1_j)| -> means within bad, within
                             good, bad-vs-good  (chance level ~ 1/sqrt(1536) = 0.026)
  within one model, across matrices sharing an output space (same block, or all 1536-wide):
                             |cos| of u1 -> is there ONE global direction?
  what the direction IS:    participation ratio of u1 (1/Σu⁴; ~1536 = spread, ~1 = one channel),
                             top channels -> is it a channel outlier?
USAGE  .venv/bin/python eval/task_vector_spike.py --out DIR --ckpt bad:name=path ... (same
       label syntax as task_vector_gram.py; reuses its cache)
"""
import argparse
import collections
import json
import math
import os
import sys

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
import torch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.task_vector_gram import load_adapter, parse_models, site_of, block_of  # noqa: E402


def top_dirs(A, B, k=3):
    """σ² fractions and top-k left/right singular vectors of B·A via the r×r problem."""
    Qb, Rb = torch.linalg.qr(B)
    Qa, Ra = torch.linalg.qr(A.T)
    U, s, Vh = torch.linalg.svd(Rb @ Ra.T)
    s2 = s * s
    frac = (s2[:k] / s2.sum()).tolist() if s2.sum() > 0 else [0.0] * k
    return frac, Qb @ U[:, :k], Qa @ Vh.T[:, :k]      # (out, k), (in, k)


def mean_abs_cos(vecs, I, J, same):
    vals = []
    for i in I:
        for j in J:
            if same and j <= i:
                continue
            vals.append(abs(float(vecs[i] @ vecs[j])))
    return sum(vals) / len(vals) if vals else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", action="append"); ap.add_argument("--ladder", action="append")
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=3)
    a = ap.parse_args()
    models = parse_models(a)
    names = [f"{g}:{n}" for g, n, _ in models]
    good = [i for i, (g, _, _) in enumerate(models) if g == "good"]
    bad = [i for i, (g, _, _) in enumerate(models) if g == "bad"]
    ads = [load_adapter(p, f"{g}__{n}") for g, n, p in models]
    keys = ads[0]["keys"]
    K = len(models)

    per_key = []
    # global-direction test: collect u1 per (model, matrix) for matrices with 1536-d output
    u1_by_model = collections.defaultdict(list)
    for ki, key in enumerate(keys):
        fr, U1, V1 = [], [], []
        for m in range(K):
            A, B, _ = ads[m]["get"](ki)
            f, U, V = top_dirs(A, B, a.k)
            fr.append(f); U1.append(U[:, 0]); V1.append(V[:, 0])
            u1_by_model[m].append((key, U[:, 0]))
        row = {"key": key, "site": site_of(key), "block": block_of(key),
               "top1": [f[0] for f in fr], "top3": [sum(f) for f in fr],
               "u_bb": mean_abs_cos(U1, bad, bad, True), "u_gg": mean_abs_cos(U1, good, good, True),
               "u_bg": mean_abs_cos(U1, bad, good, False),
               "v_bb": mean_abs_cos(V1, bad, bad, True), "v_gg": mean_abs_cos(V1, good, good, True),
               "v_bg": mean_abs_cos(V1, bad, good, False),
               "pr_u_bad": [float(1.0 / (U1[i] ** 4).sum()) for i in bad],
               "pr_u_good": [float(1.0 / (U1[i] ** 4).sum()) for i in good],
               "top_ch_bad": [torch.topk(U1[i].abs(), 3).indices.tolist() for i in bad]}
        per_key.append(row)
        if (ki + 1) % 50 == 0:
            print(f"  {ki+1}/{len(keys)}", flush=True)

    os.makedirs(a.out, exist_ok=True)
    L = []; P = L.append
    n_out = len(U1[0]) if U1 else 0
    P(f"spike directions over {K} models ({len(bad)} bad, {len(good)} good), {len(keys)} matrices; "
      f"chance |cos| ~ {1/math.sqrt(1536):.3f}")
    P("")
    P("per model: median top-1 σ² fraction, median top-3 fraction, median participation ratio of u1")
    for m in range(K):
        t1 = sorted(r["top1"][m] for r in per_key); t3 = sorted(r["top3"][m] for r in per_key)
        prs = [float(1.0 / (u ** 4).sum()) for _, u in u1_by_model[m]]
        prs.sort()
        P(f"  {names[m]:<34} top1 {t1[len(t1)//2]:.3f}  top3 {t3[len(t3)//2]:.3f}  PR(u1) {prs[len(prs)//2]:7.1f}")
    P("")
    P("agreement of the TOP direction across models (mean |cos|, per matrix, then median over matrices):")
    for side, lab in (("u", "left / output space"), ("v", "right / input space")):
        bb = sorted(r[f"{side}_bb"] for r in per_key if not math.isnan(r[f"{side}_bb"]))
        gg = sorted(r[f"{side}_gg"] for r in per_key if not math.isnan(r[f"{side}_gg"]))
        bg = sorted(r[f"{side}_bg"] for r in per_key if not math.isnan(r[f"{side}_bg"]))
        med = lambda x: x[len(x)//2] if x else float("nan")
        P(f"  {lab:<22} bad-bad {med(bb):.3f}   good-good {med(gg):.3f}   bad-good {med(bg):.3f}")
    P("  bad-bad >> chance and >> bad-good  -> the bad arms' spikes point the SAME way: systematic.")
    P("  bad-bad ~ chance                    -> each arm's spike is its own accident.")
    P("")
    P("by site (left-space bad-bad |cos| median, bad top1 median):")
    by_site = collections.defaultdict(list)
    for r in per_key:
        by_site[r["site"]].append(r)
    for s, rows in sorted(by_site.items(), key=lambda kv: -len(kv[1])):
        bb = sorted(r["u_bb"] for r in rows if not math.isnan(r["u_bb"]))
        t1 = sorted(sum(r["top1"][i] for i in bad) / max(len(bad), 1) for r in rows)
        P(f"  {s:<9} n={len(rows):>3}  bad-bad |cos| {bb[len(bb)//2] if bb else float('nan'):.3f}   bad top1 {t1[len(t1)//2]:.3f}")
    P("")
    P("is there ONE global output-space direction inside a bad model? (|cos| of u1 across different")
    P("matrices of the same model, 1536-wide outputs only; median over pairs within a block, then over blocks)")
    for m in bad[:4] + good[-2:]:
        by_blk = collections.defaultdict(list)
        for key, u in u1_by_model[m]:
            if u.numel() == 1536:
                by_blk[block_of(key)].append(u)
        meds = []
        for b, us in by_blk.items():
            if len(us) < 2:
                continue
            vals = [abs(float(us[i] @ us[j])) for i in range(len(us)) for j in range(i + 1, len(us))]
            meds.append(sorted(vals)[len(vals)//2])
        meds.sort()
        P(f"  {names[m]:<34} within-block cross-matrix |cos(u1)| median {meds[len(meds)//2] if meds else float('nan'):.3f}")
    P("")
    P("channel concentration of u1 in bad models (participation ratio; 1536 = spread evenly, small = a")
    P("few channels). Top channels listed when PR < 50 for the first bad model, first 8 such matrices:")
    shown = 0
    for r in per_key:
        if r["pr_u_bad"] and r["pr_u_bad"][0] < 50 and shown < 8:
            P(f"  {r['key'][-60:]:<60} PR {r['pr_u_bad'][0]:6.1f} top ch {r['top_ch_bad'][0]}")
            shown += 1
    if shown == 0:
        P("  (none below PR 50 — the spike is not a channel outlier)")
    rep = "\n".join(L)
    print(rep)
    open(os.path.join(a.out, "spike_report.txt"), "w").write(rep + "\n")
    json.dump({"models": names, "per_key": per_key}, open(os.path.join(a.out, "spike.json"), "w"))
    print(f"-> {a.out}/spike_report.txt")


if __name__ == "__main__":
    main()
