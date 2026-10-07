"""H4: parameter matrices for the 10 swept Surge knobs, and how much a pairwise (2-D) view misses.

On ladders_v2t (105 train-split presets; each ladder sweeps one knob, the other params are the preset's):
  direction_cos   10x10 cosine between knobs' mean unit latent directions (time-mean SAME-S); diagonal =
                  within-knob consistency. Off-diagonal ~0 = disentangled knobs; high = knobs move the latent
                  the same way (they would be confused by a direction-based UI).
  gating          10 x 23: Spearman between a knob's AUDIBLE effect size (effect_size_<name>.npz) and every
                  other parameter's value in the ladder's context -- 'which settings make this knob audible'.
  prior_corr      23x23 Spearman correlation of the parameters across the 105 presets themselves (what real
                  bass patches pair together; why some contexts are rare in the data).
  beyond_pairwise per knob, 5-fold held-out-archetype R2 of predicting the audible effect from the context with
                  (a) the best single parameter, (b) all parameters, linear and additive, (c) gradient-boosted
                  trees (can use interactions). (c) - (b) = the share a pairwise/additive view cannot explain.
Out: <dir>/param_matrices_<name>.json. Run: SAO/.venv/bin/python eval/h4_param_matrices.py
"""
import argparse
import json
import os

os.environ.setdefault("OMP_NUM_THREADS", "8")
import numpy as np
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import RidgeCV

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate_v2"
NAMES = ["midi_note", "filter_type", "shape", "width", "sub_mix", "sync", "fm_depth", "unison", "unison_detune",
         "cutoff", "resonance", "keytrack", "feg_amount", "feg_decay", "feg_sustain", "aeg_decay", "aeg_sustain",
         "aeg_release", "waveshaper_type", "drive", "chorus_mix", "delay_mix", "delay_fb"]


def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def cv_r2(model, X, y, folds):
    pred = np.zeros_like(y)
    for f in np.unique(folds):
        tr, te = folds != f, folds == f
        pred[te] = model().fit(X[tr], y[tr]).predict(X[te])
    return float(1 - ((pred - y) ** 2).sum() / ((y - y.mean()) ** 2).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--name", default="ladders_v2t")
    a = ap.parse_args()
    d = np.load(f"{a.dir}/{a.name}.npz", mmap_mode="r")
    Z = np.load(f"{a.dir}/{a.name}.latents_same_s.npz")["z"]
    eff = np.load(f"{a.dir}/effect_size_{a.name}.npz")
    knobs = [str(x) for x in d["knobs"]]
    kid, lid, rung, nr, arch, rh = (d[c][:] for c in ("knob_id", "ladder_id", "rung", "n_rungs", "archetype_id",
                                                        "rhythm_id"))
    vecs = d["vecs"][:]
    M = Z.astype(np.float32).mean(-1)
    L = np.unique(lid)
    first = {l: np.where((lid == l) & (rung == 0))[0][0] for l in L}
    last = {l: np.where((lid == l) & (rung == nr[first[l]] - 1))[0][0] for l in L}
    lk = np.array([kid[first[l]] for l in L])
    present = sorted(set(lk.tolist()))              # files like v2s/v2f render only a subset of the knobs
    knobs = [knobs[k] for k in present]
    lk = np.array([present.index(k) for k in lk])
    U = unit(np.stack([M[last[l]] - M[first[l]] for l in L]))
    mean_dir = np.stack([unit(U[lk == k].mean(0)) for k in range(len(knobs))])
    dcos = mean_dir @ mean_dir.T
    for k in range(len(knobs)):
        Uk = U[lk == k]
        C = Uk @ Uk.T
        dcos[k, k] = (C.sum() - len(Uk)) / (len(Uk) * (len(Uk) - 1))

    e_of = dict(zip(eff["ladder_id"].tolist(), eff["audio_effect"].tolist()))
    ctx = np.stack([vecs[first[l]] for l in L])
    eaud = np.array([e_of[int(l)] for l in L])
    ctx_r = np.concatenate([ctx, np.array([rh[first[l]] for l in L])[:, None]], 1)   # + rhythm id
    cnames = NAMES + ["rhythm_id"]
    gating, beyond = {}, {}
    rng = np.random.default_rng(0)
    for k, name in enumerate(knobs):
        m = lk == k
        X, y = np.delete(ctx_r[m], NAMES.index(name), 1), eaud[m]
        xn = [c for c in cnames if c != name]
        row = {}
        for j, c in enumerate(xn):
            row[c] = round(float(spearmanr(X[:, j], y).statistic), 3) if np.ptp(X[:, j]) > 1e-9 else None
        gating[name] = row
        ua = rng.permutation(np.unique(arch[[first[l] for l in L[m]]]))
        fold_of = {x: i % 5 for i, x in enumerate(ua)}
        folds = np.array([fold_of[arch[first[l]]] for l in L[m]])
        live = [j for j in range(X.shape[1]) if np.ptp(X[:, j]) > 1e-9]
        X = X[:, live]
        singles = {xn[live[j]]: cv_r2(lambda: RidgeCV(alphas=np.logspace(-3, 3, 13)), X[:, [j]], y, folds)
                   for j in range(X.shape[1])}
        best = max(singles, key=singles.get)
        beyond[name] = {"best_single": best, "r2_best_single": round(singles[best], 3),
                        "r2_additive_linear": round(cv_r2(lambda: RidgeCV(alphas=np.logspace(-3, 3, 13)), X, y, folds), 3),
                        "r2_trees_with_interactions": round(cv_r2(lambda: HistGradientBoostingRegressor(
                            max_iter=300, learning_rate=0.05, max_leaf_nodes=15, random_state=0), X, y, folds), 3)}
    from importlib import util as _u   # noqa: F401  (keep stdlib-only imports above)
    prior = np.load("/run/media/kim/Mantu/surge_200k_models/h4_gate_v2/" + a.name + ".npz", mmap_mode="r")
    P = np.stack([vecs[first[l]] for l in L])
    pa = np.array([arch[first[l]] for l in L])
    per_preset = np.stack([P[pa == x].mean(0) for x in np.unique(pa)])   # one row per preset (jitter averaged)
    live = [j for j in range(len(NAMES)) if np.ptp(per_preset[:, j]) > 1e-9]
    pc = spearmanr(per_preset[:, live]).statistic
    res = {"file": a.name, "knobs": knobs,
           "direction_cos": [[round(float(x), 3) for x in r] for r in dcos],
           "gating_spearman_audio_effect": gating, "beyond_pairwise": beyond,
           "prior_corr": {"params": [NAMES[j] for j in live], "n_presets": int(len(per_preset)),
                          "matrix": [[round(float(x), 3) for x in r] for r in pc]}}
    json.dump(res, open(f"{a.dir}/param_matrices_{a.name}.json", "w"), indent=1)
    print("direction cosine (diag = within-knob consistency)")
    print(" " * 12 + " ".join(f"{k[:6]:>6s}" for k in knobs))
    for k, r in zip(knobs, dcos):
        print(f"{k:12s}" + " ".join(f"{x:6.2f}" for x in r))
    print("\nbeyond pairwise (held-out-archetype R2 of the audible effect from context)")
    for k, v in beyond.items():
        print(f"  {k:12s} best single {v['best_single']:12s} {v['r2_best_single']:+.2f} | additive {v['r2_additive_linear']:+.2f}"
              f" | trees {v['r2_trees_with_interactions']:+.2f}")
    print("\ngating (top 3 context params by |rho| for each knob's audible effect)")
    for k, row in gating.items():
        top = sorted(((c, v) for c, v in row.items() if v is not None), key=lambda t: -abs(t[1]))[:3]
        print(f"  {k:12s} " + ", ".join(f"{c} {v:+.2f}" for c, v in top))
    strong = [(NAMES[live[i]], NAMES[live[j]], pc[i, j]) for i in range(len(live)) for j in range(i + 1, len(live))
              if abs(pc[i, j]) >= 0.4]
    print("\nprior: preset-level param pairs with |rho| >= 0.4:", ", ".join(f"{x}~{y} {v:+.2f}" for x, y, v in strong))


if __name__ == "__main__":
    main()
