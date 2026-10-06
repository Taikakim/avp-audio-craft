"""H4: envelope knobs fitted CONDITIONED on the knob that gates them, vs one pooled direction.

Context finding (h4_context_dependence.py): a knob's effect, and sometimes its direction, depends on another
knob -- sustain is only audible with a short decay, decay only with low sustain, FEG decay only with a big FEG
amount. So per (knob | gate) pair, split the knob's ladders into terciles of the gate's value and compare, on
HELD-OUT ARCHETYPES (5 folds of whole presets):
  direction  cosine of each held-out ladder's displacement with (a) the pooled direction (all terciles) and
             (b) the conditioned direction (same tercile only), both fitted on the training archetypes
  readout    ridge from latent features to the knob value: trained pooled vs trained within the tercile,
             scored within the tercile (R2 and within-ladder Spearman)
Features: time-mean (256-d) and temporal (per-channel mean, std, last-minus-first-quarter mean; 768-d).
Cutoff | feg_amount is a control: cutoff's direction barely depends on context, so conditioning should not help.
Out: <dir>/conditioned_fit_<name>.json. Run: SAO/.venv/bin/python eval/h4_conditioned_fit.py [--name ladders_v2t]
"""
import argparse
import json
import os

os.environ.setdefault("OMP_NUM_THREADS", "8")
import numpy as np
from scipy.stats import spearmanr

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate_v2"
NAMES = ["midi_note", "filter_type", "shape", "width", "sub_mix", "sync", "fm_depth", "unison", "unison_detune",
         "cutoff", "resonance", "keytrack", "feg_amount", "feg_decay", "feg_sustain", "aeg_decay", "aeg_sustain",
         "aeg_release", "waveshaper_type", "drive", "chorus_mix", "delay_mix", "delay_fb"]
I = {n: i for i, n in enumerate(NAMES)}
PAIRS = [("aeg_sustain", "aeg_decay"), ("aeg_decay", "aeg_sustain"), ("feg_decay", "feg_amount"),
         ("feg_amount", "feg_decay"), ("resonance", "feg_amount"), ("cutoff", "feg_amount")]


def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def features(z, kind):
    z = z.astype(np.float32)
    if kind == "mean":
        return z.mean(-1)
    q = max(1, z.shape[-1] // 4)
    return np.concatenate([z.mean(-1), z.std(-1), z[..., -q:].mean(-1) - z[..., :q].mean(-1)], -1)


def ridge_fit(X, y, alpha=1000.0):
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Xt = (X - mu) / sd
    w = np.linalg.solve(Xt.T @ Xt + alpha * np.eye(X.shape[1]), Xt.T @ (y - y.mean()))
    return lambda Z: ((Z - mu) / sd) @ w + y.mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--name", default="ladders_v2t")
    ap.add_argument("--folds", type=int, default=5)
    a = ap.parse_args()
    d = np.load(f"{a.dir}/{a.name}.npz", mmap_mode="r")
    Z = np.load(f"{a.dir}/{a.name}.latents_same_s.npz")["z"]
    knobs = [str(x) for x in d["knobs"]]
    kid, lid, rung, nr, kv, arch = (d[c][:] for c in ("knob_id", "ladder_id", "rung", "n_rungs", "knob_value",
                                                        "archetype_id"))
    vecs = d["vecs"][:]
    rng = np.random.default_rng(0)
    res = {"file": a.name, "folds": a.folds, "pairs": {}}
    for knob, gate in PAIRS:
        k = knobs.index(knob)
        L = np.unique(lid[kid == k])
        first = {l: np.where((lid == l) & (rung == 0))[0][0] for l in L}
        last = {l: np.where((lid == l) & (rung == nr[first[l]] - 1))[0][0] for l in L}
        g = np.array([vecs[first[l], I[gate]] for l in L])
        q = np.quantile(g, [1 / 3, 2 / 3])
        terc = np.digitize(g, q)                                    # 0 low, 1 mid, 2 high
        ar = np.array([arch[first[l]] for l in L])
        ua = rng.permutation(np.unique(ar))
        fold_of = {x: i % a.folds for i, x in enumerate(ua)}
        fold = np.array([fold_of[x] for x in ar])
        out = {"gate_tercile_edges": [round(float(x), 3) for x in q]}
        for kind in ("mean", "temporal"):
            F = features(Z, kind)
            D = np.stack([F[last[l]] - F[first[l]] for l in L])
            Ud = unit(D)
            dir_pool, dir_cond = [[] for _ in range(3)], [[] for _ in range(3)]
            r2p, r2c, rhop, rhoc = [[] for _ in range(3)], [[] for _ in range(3)], [[] for _ in range(3)], \
                [[] for _ in range(3)]
            for f in range(a.folds):
                tr, te = fold != f, fold == f
                pooled = unit(Ud[tr].mean(0))
                rows_tr = np.concatenate([np.where(lid == l)[0] for l in L[tr]])
                fit_p = ridge_fit(F[rows_tr], kv[rows_tr])
                for t in range(3):
                    trt, tet = tr & (terc == t), te & (terc == t)
                    if trt.sum() < 5 or tet.sum() < 1:
                        continue
                    cond = unit(Ud[trt].mean(0))
                    dir_pool[t] += list(Ud[tet] @ pooled)
                    dir_cond[t] += list(Ud[tet] @ cond)
                    rows_trt = np.concatenate([np.where(lid == l)[0] for l in L[trt]])
                    fit_c = ridge_fit(F[rows_trt], kv[rows_trt])
                    for l in L[tet]:
                        m = lid == l
                        y = kv[m]
                        for fit, R2, RHO in ((fit_p, r2p[t], rhop[t]), (fit_c, r2c[t], rhoc[t])):
                            p = fit(F[m])
                            R2.append(((p - y) ** 2).sum())
                            RHO.append(spearmanr(y, p).statistic)
            per_t = []
            for t in range(3):
                sel = np.concatenate([np.where(lid == l)[0] for l in L[terc == t]])
                sst = ((kv[sel] - kv[sel].mean()) ** 2).sum()
                per_t.append({
                    "n_ladders": int((terc == t).sum()),
                    "heldout_dir_cos_pooled": round(float(np.mean(dir_pool[t])), 3) if dir_pool[t] else None,
                    "heldout_dir_cos_conditioned": round(float(np.mean(dir_cond[t])), 3) if dir_cond[t] else None,
                    "readout_r2_pooled": round(float(1 - np.sum(r2p[t]) / sst), 3) if r2p[t] else None,
                    "readout_r2_conditioned": round(float(1 - np.sum(r2c[t]) / sst), 3) if r2c[t] else None,
                    "readout_rho_pooled": round(float(np.nanmedian(rhop[t])), 3) if rhop[t] else None,
                    "readout_rho_conditioned": round(float(np.nanmedian(rhoc[t])), 3) if rhoc[t] else None})
            out[kind] = per_t
        res["pairs"][f"{knob} | {gate}"] = out
        print(knob, "|", gate, "done", flush=True)
    json.dump(res, open(f"{a.dir}/conditioned_fit_{a.name}.json", "w"), indent=1)
    for p, v in res["pairs"].items():
        print(p, "edges", v["gate_tercile_edges"])
        for kind in ("mean", "temporal"):
            print(f"  {kind:8s}", " | ".join(
                f"T{t}: dir {x['heldout_dir_cos_pooled']}->{x['heldout_dir_cos_conditioned']}  "
                f"R2 {x['readout_r2_pooled']}->{x['readout_r2_conditioned']}" for t, x in enumerate(v[kind])))


if __name__ == "__main__":
    main()
