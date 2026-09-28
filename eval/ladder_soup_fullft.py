#!/usr/bin/env python3
"""ladder_soup_fullft.py — average ONE DoRA/LoRA run's epochs in the space of the real weight
change ΔW_eff and save the result as a MERGED full-model checkpoint (renders as a fullft_* arm).

WHY MERGED (C, 2026-09-28): the mean of five rank-128 changes is up to rank 640, so re-factoring
it into one rank-128 adapter would truncate the thing being tested. Merged W0 + mean(ΔW_eff) is
exact. Output format is the LUMI full-FT one model_matrix_gen already loads:
{"state_dict": {"diffusion.model.model.<...>": bf16}}, every DiT tensor present (the coverage
assert refuses <99%), plus "conditioner.<...>" for any adapted conditioner tensor (DoRA runs adapt
seconds_total's embedder; model_matrix_gen loads those over the base conditioner). bf16 because the renderer casts to the model dtype anyway.

SOUPS
  mean      plain mean over all given epochs
  filtered  Kim's idea: per value, drop AT MOST ONE epoch — the one whose leave-one-out DETRENDED
            residual is largest in units of its epoch-matrix robust scale, if > k — mean the rest
  pair:E1,E2  plain mean over two named epochs
USAGE .venv/bin/python eval/ladder_soup_fullft.py --out-dir DIR [--pair 14,21] <ckpt> ...
"""
import argparse
import json
import os
import sys

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
import torch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.ladder_outlier_probe import epoch_of, loo_residuals, single_outlier_mask  # noqa: E402


def filtered_mean(X, t, k=8.0):
    """X (E, N). Per value, mean over the epochs that are NOT detrended outliers there.
    Returns (mean, fraction of values where at least one epoch was dropped)."""
    keep = ~single_outlier_mask(loo_residuals(X, t), k)
    m = (X * keep).sum(0) / keep.sum(0)
    return m, float((~keep).any(0).double().mean())


def main():
    from eval.task_vector_gram import BASE_ST, base_key_for, dora_delta_eff, load_adapter
    from safetensors import safe_open
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpts", nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--k", type=float, default=8.0)
    ap.add_argument("--pair", default=None, help="E1,E2 — also write the plain mean of these two")
    a = ap.parse_args()
    paths = sorted(a.ckpts, key=epoch_of)
    eps = [epoch_of(p) for p in paths]
    t = torch.tensor(eps, dtype=torch.float64)
    run = os.path.basename(os.path.dirname(os.path.abspath(paths[0])))
    ads = [load_adapter(p, f"ladder__{run}__ep{e}") for p, e in zip(paths, eps)]
    pair = [eps.index(int(x)) for x in a.pair.split(",")] if a.pair else None
    by_base = {}
    with safe_open(BASE_ST[0], framework="pt") as f:
        base_keys = set(f.keys())
        for ki, key in enumerate(ads[0]["keys"]):
            bk = base_key_for(key, base_keys)
            if bk is None or not bk.startswith(("model.model.", "conditioner.")):
                sys.exit(f"adapter {key} maps onto no DiT/conditioner tensor ({bk})")
            by_base[bk] = ki
        soups = {"mean": {}, "filtered": {}}
        if pair:
            soups[f"ep{eps[pair[0]]}_ep{eps[pair[1]]}"] = {}
        stats = {}
        # every DiT tensor (the renderer's coverage assert wants them all), plus only the ADAPTED
        # conditioner tensors (model_matrix_gen loads "conditioner.*" keys over the base ones)
        wanted = sorted(k for k in base_keys if k.startswith("model.model.")) + \
            sorted(k for k in by_base if k.startswith("conditioner."))
        for bk in wanted:
            W = f.get_tensor(bk).float()
            out = ("diffusion." + bk) if bk.startswith("model.model.") else bk
            if bk not in by_base:
                for s in soups.values():
                    s[out] = W.to(torch.bfloat16)
                continue
            ki = by_base[bk]
            W2 = W.reshape(W.shape[0], -1)
            D = []
            for m in range(len(paths)):
                A, B, mag = ads[m]["get"](ki)
                sc = float(ads[m]["cfg"].get("alpha", B.shape[1])) / B.shape[1]
                D.append(dora_delta_eff(W2, A, B, mag, sc).double().reshape(-1))
            X = torch.stack(D)
            fm, frac = filtered_mean(X, t, a.k)
            put = lambda d: (W2.double() + d.reshape(W2.shape)).reshape(W.shape).to(torch.bfloat16)
            soups["mean"][out] = put(X.mean(0))
            soups["filtered"][out] = put(fm)
            if pair:
                soups[f"ep{eps[pair[0]]}_ep{eps[pair[1]]}"][out] = put(X[pair].mean(0))
            stats[bk] = {"filtered_frac": frac, "mean_norm": float(X.mean(0).norm()),
                         "filtered_norm": float(fm.norm()),
                         "epoch_norms": [float(x.norm()) for x in X],
                         "filtered_vs_mean_rel": float((fm - X.mean(0)).norm() / X.mean(0).norm())}
            del X, D
    os.makedirs(a.out_dir, exist_ok=True)
    for name, sd in soups.items():
        p = os.path.join(a.out_dir, f"soup_{name}.ckpt")
        torch.save({"state_dict": sd, "soup": {"run": run, "epochs": eps, "kind": name, "k": a.k,
                                               "sources": [os.path.abspath(x) for x in paths]}}, p)
        print(f"wrote {p} ({len(sd)} tensors)", flush=True)
    json.dump({"run": run, "epochs": eps, "k": a.k, "per_matrix": stats},
              open(os.path.join(a.out_dir, "soup_stats.json"), "w"), indent=1)
    top = sorted(stats.items(), key=lambda kv: -kv[1]["filtered_vs_mean_rel"])[:12]
    print("largest filtered-vs-mean differences (relative to the mean's change):")
    for bk, s in top:
        print(f"  {s['filtered_vs_mean_rel']:.4f}  dropped {s['filtered_frac']:.2e}  {bk}")
    rel = sorted(s["filtered_vs_mean_rel"] for s in stats.values())
    print(f"median filtered-vs-mean rel diff over {len(rel)} matrices: {rel[len(rel)//2]:.2e}")


if __name__ == "__main__":
    main()
