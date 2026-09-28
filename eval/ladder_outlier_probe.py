#!/usr/bin/env python3
"""ladder_outlier_probe.py — are one run's epoch-to-epoch differences made of a FEW blown-up
values (then a per-value "drop the odd epoch out" average can remove them) or of spread-out
noise (then plain averaging does the same job), and does any epoch carry one dominant direction?

WHY (Kim 2026-09-28, fp32cmp_avp_t4096_bs1_lr1e4): every epoch has glitches and good outputs;
proposed to average the epochs per neuron, skipping an epoch wherever its value is far from the
others. Two traps this probe is built around (C):
  1. The run DRIFTS (||lora_B|| 319 -> 887 over ep3..ep35), so "far from the others" must be far
     from the TREND. Each epoch is compared to a straight line in epoch number fitted through the
     OTHER epochs (leave-one-out) — per element of the real weight change ΔW_eff, not per adapter
     factor (B and A only mean something as a product; mixing their elements across epochs builds
     a change nobody trained).
  2. A glitch can be a thin DIRECTION over thousands of values, invisible per value (the 08-18 goa
     finding). So the top singular-value share of each epoch's B·A is reported too.
Scale is per epoch per matrix (1.4826·median|residual|), so the far-extrapolated ends (ep3, ep35)
are not flagged just for being ends: the question is heavy tails WITHIN an epoch.

USAGE (CPU; reuses task_vector_gram's NVMe factor cache):
  .venv/bin/python eval/ladder_outlier_probe.py --out DIR <ckpt> <ckpt> ...   (>=4, one run)
"""
import argparse
import collections
import json
import os
import re
import sys

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
import torch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def loo_residuals(X, t):
    """X (E, N) values at epochs t (E,). Row e of the result = X[e] minus the least-squares line
    through the OTHER E-1 epochs, evaluated at t[e]."""
    E = X.shape[0]
    R = torch.empty_like(X)
    for e in range(E):
        o = [i for i in range(E) if i != e]
        to, xo = t[o], X[o]
        tm = to.mean()
        xm = xo.mean(0)
        b = ((to - tm)[:, None] * (xo - xm)).sum(0) / ((to - tm) ** 2).sum()
        R[e] = X[e] - (xm + b * (t[e] - tm))
    return R


def single_outlier_mask(R, k=8.0):
    """R (E, N) LOO residuals. Per value, flag AT MOST ONE epoch: the one with the largest
    |residual| in units of its own epoch-matrix robust scale, and only if that exceeds k.
    One spike also bends the LOO lines used to judge the OTHER epochs, so an any-epoch-over-k
    rule flags innocent epochs alongside it (and a mean over the survivors keeps the spike)."""
    s = 1.4826 * R.abs().median(dim=1, keepdim=True).values
    z = R.abs() / s.clamp_min(1e-30)
    zmax, arg = z.max(0)
    M = torch.zeros_like(R, dtype=torch.bool)
    hit = zmax > k
    M[arg[hit], hit.nonzero().flatten()] = True
    return M


def tail_stats(r, k=8.0):
    """Heavy-tail summary of a residual vector: robust scale s = 1.4826·median|r|; outliers are
    |r| > k·s (k=8 is ~never for Gaussian noise). energy = outliers' share of Σr²."""
    a = r.abs().flatten()
    s = 1.4826 * a.median()
    out = a > k * s
    n = int(out.sum())
    tot = float((a * a).sum())
    return {"n_out": n, "frac_out": n / a.numel(),
            "energy_out": float((a[out] ** 2).sum()) / tot if tot > 0 else 0.0}


def epoch_of(p):
    m = re.search(r"epoch=(\d+)", os.path.basename(p))
    return int(m.group(1))


def main():
    from eval.task_vector_gram import (BASE_ST, base_key_for, block_of, dora_delta_eff,
                                       load_adapter, site_of)
    from safetensors import safe_open
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpts", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=float, default=8.0)
    ap.add_argument("--row-k", type=float, default=4.0,
                    help="a channel is an outlier when its residual row norm > row-k x the median row")
    a = ap.parse_args()
    paths = sorted(a.ckpts, key=epoch_of)
    eps = [epoch_of(p) for p in paths]
    if len(paths) < 4:
        sys.exit("need >= 4 epochs of ONE run")
    t = torch.tensor(eps, dtype=torch.float64)
    run = os.path.basename(os.path.dirname(os.path.abspath(paths[0])))
    ads = [load_adapter(p, f"ladder__{run}__ep{e}") for p, e in zip(paths, eps)]
    keys = ads[0]["keys"]
    E = len(paths)
    rows = []
    with safe_open(BASE_ST[0], framework="pt") as f:
        base_keys = set(f.keys())
        for ki, key in enumerate(keys):
            bk = base_key_for(key, base_keys)
            if bk is None:
                continue
            W = f.get_tensor(bk).float()
            W2 = W.reshape(W.shape[0], -1)
            D, top1 = [], []
            for m in range(E):
                A, B, mag = ads[m]["get"](ki)
                sc = float(ads[m]["cfg"].get("alpha", B.shape[1])) / B.shape[1]
                D.append(dora_delta_eff(W2, A, B, mag, sc).double())
                _, Rb = torch.linalg.qr(B)
                _, Ra = torch.linalg.qr(A.T)
                s2 = torch.linalg.svdvals(Rb @ Ra.T) ** 2
                top1.append(float(s2[0] / s2.sum()) if s2.sum() > 0 else 0.0)
            X = torch.stack([d.reshape(-1) for d in D])
            R = loo_residuals(X, t)
            nout = W2.shape[0]
            rec = {"key": key, "site": site_of(key), "block": block_of(key), "top1": top1,
                   "el": [], "row": [], "filter_drop": 0.0}
            flags = single_outlier_mask(R, a.k)
            for e in range(E):
                rn_all = (R[e] ** 2).sum()
                fe = flags[e]
                rec["el"].append({"n_out": int(fe.sum()), "frac_out": float(fe.double().mean()),
                                  "energy_out": float((R[e][fe] ** 2).sum() / rn_all) if rn_all > 0 else 0.0})
                rn = R[e].reshape(nout, -1).norm(dim=1)
                ro = rn > a.row_k * rn.median()
                rec["row"].append({"n_out": int(ro.sum()), "of": nout,
                                   "energy_out": float((rn[ro] ** 2).sum() / (rn ** 2).sum())})
            rec["filter_drop"] = float(flags.any(0).double().mean())
            rows.append(rec)
            if (ki + 1) % 25 == 0:
                print(f"  {ki+1}/{len(keys)}", flush=True)
            del D, X, R, flags

    os.makedirs(a.out, exist_ok=True)
    json.dump({"run": run, "epochs": eps, "k": a.k, "row_k": a.row_k, "rows": rows},
              open(os.path.join(a.out, "ladder_outlier_probe.json"), "w"))
    med = lambda v: sorted(v)[len(v) // 2]
    L = [f"# Ladder outlier probe: {run}", "",
         f"epochs {eps}; {len(rows)} adapted matrices; value outlier = the ONE epoch per value whose |LOO-detrended residual| is largest, if > "
         f"{a.k:g}x robust scale of that epoch's matrix; channel outlier = residual row norm > "
         f"{a.row_k:g}x median row.", "",
         "| epoch | value outliers (median frac / matrix) | total value outliers | outliers' share of residual energy (median) | "
         "channel outliers (total) | channels' share of residual energy (median) | top-1 σ² share of B·A (median) |",
         "|---|---|---|---|---|---|---|"]
    for e in range(E):
        L.append(f"| ep{eps[e]} | {med([r['el'][e]['frac_out'] for r in rows]):.2e} | "
                 f"{sum(r['el'][e]['n_out'] for r in rows):,} | "
                 f"{med([r['el'][e]['energy_out'] for r in rows]):.3f} | "
                 f"{sum(r['row'][e]['n_out'] for r in rows):,} | "
                 f"{med([r['row'][e]['energy_out'] for r in rows]):.3f} | "
                 f"{med([r['top1'][e] for r in rows]):.3f} |")
    L += ["", f"Kim's filter preview: fraction of values where at least one epoch would be dropped "
          f"(median over matrices): {med([r['filter_drop'] for r in rows]):.2e}", "",
          "Top 12 matrices by the largest single-epoch value-outlier energy share:", ""]
    worst = sorted(((max(r['el'][e]['energy_out'] for e in range(E)),
                     eps[max(range(E), key=lambda e: r['el'][e]['energy_out'])], r) for r in rows),
                   key=lambda x: -x[0])[:12]
    for en, ep, r in worst:
        L.append(f"- ep{ep} {en:.3f}  {r['site']} L{r['block']}  `{r['key']}`")
    by_site = collections.defaultdict(list)
    for r in rows:
        by_site[r["site"]].append(r)
    L += ["", "Per site, median top-1 σ² share per epoch:", ""]
    for s, rs in sorted(by_site.items()):
        L.append(f"- {s} (n={len(rs)}): " + ", ".join(
            f"ep{eps[e]} {med([r['top1'][e] for r in rs]):.3f}" for e in range(E)))
    open(os.path.join(a.out, "REPORT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
