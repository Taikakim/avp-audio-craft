#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""punch_seed_latent_stats.py -- what does seed 764's latent have that 3050's does not?

WHY (project direction 2026-10-15): seed 764 of the punch DoRA render is "the originally degraded one" (grainy), and with
FiLM + the A2 air head on top it goes distorted/saturated while seed 3050 stays good. Hypothesis: the post-trained-like
DoRA has a narrower output range and homes toward a few modes, one of them grainy; 764's latent sits in it. Look for
statistical deviations or a direction that separates 764 from the other seeds and that also predicts lower quality
across the 64-seed punch set.

Data: the render server's kept latents (sa3_render_out/<job>/out_00.z0.npy, matched by params_echo) for the punch
rating set (GHOST-NOTE, punch_rating_20261014): DoRA 0.45, 30 steps, 48 s, the punch prompt; arm "dora" = no LatCH,
arm "cleanest" = bass + body LatCH. Labels: G's per-clip metrics (Audiobox PQ, flatness, zcr, hf_ratio, crest) of the
same renders, and the ear (764 bad, 3050 good). CPU only. Writes a JSON report next to the rating set.
RUN: SAO/.venv/bin/python eval/punch_seed_latent_stats.py
"""
import glob
import json
import os

import numpy as np

RENDER_OUT = "/home/kim/Projects/sa3_render_out"
RATING = "/run/media/kim/Mantu/sa3_control_runs/punch_rating_20261014"
OUT = f"{RATING}/seed_latent_stats_20261015.json"
NODORA = "/run/media/kim/Mantu/sa3_control_runs/punch_nodora_seeds_20261015"   # eval/punch_nodora_seeds.py


def arm_of(pe):
    heads = sorted(s.get("head", "") for s in (pe.get("latch") or []))
    if not heads:
        return "dora"
    if heads == ["rms_energy_bass", "rms_energy_body"]:
        return "cleanest"
    return None


def collect():
    lat = {}
    for d in sorted(glob.glob(f"{RENDER_OUT}/2026101[45]-*")):
        try:
            r = json.load(open(f"{d}/result.json"))
        except Exception:
            continue
        pe = (r.get("meta") or {}).get("params_echo") or {}
        if (pe.get("dora") or {}).get("strength") != 0.45 or pe.get("steps") != 30 or pe.get("film"):
            continue
        if not str(pe.get("prompt", "")).startswith("90s psytrance, mystical"):
            continue
        arm = arm_of(pe)
        zs = r.get("latents") or []
        if arm and zs and os.path.exists(zs[0]):
            lat.setdefault((arm, int(pe["seed"])), zs[0])     # first render per seed wins (re-renders are identical configs)
    return lat


def features(z):
    z = z.astype(np.float64)
    if z.ndim == 3:
        z = z[0]
    c, t = z.shape
    f = {}
    f["std"] = float(z.std())
    f["mean_abs_ch_mean"] = float(np.abs(z.mean(1)).mean())
    zc = (z - z.mean()) / (z.std() + 1e-9)
    f["kurtosis"] = float((zc ** 4).mean() - 3)
    f["max_abs"] = float(np.abs(z).max())
    d1 = np.diff(z, axis=1)
    f["temporal_roughness"] = float(d1.std() / (z.std() + 1e-9))          # frame-to-frame jitter relative to level
    spec = np.abs(np.fft.rfft(z - z.mean(1, keepdims=True), axis=1)) ** 2
    hi = spec[:, spec.shape[1] // 2:].sum()
    f["hf_time_energy"] = float(hi / (spec.sum() + 1e-12))                # share of energy in the fastest half of the modulation band
    lag1 = [(np.corrcoef(row[:-1], row[1:])[0, 1]) for row in z if row.std() > 1e-9]
    f["lag1_autocorr"] = float(np.mean(lag1))
    ev = np.linalg.eigvalsh(np.cov(z))[::-1]
    p = ev / ev.sum()
    f["top1_eig_share"] = float(p[0])
    f["eff_rank"] = float(np.exp(-(p * np.log(p + 1e-12)).sum()))
    return f, z.mean(1), z.std(1)


def main():
    lat = collect()
    met = json.load(open(f"{RATING}/metrics.json"))
    man = {e["id"]: e for e in json.load(open(f"{RATING}/manifest.json"))["entries"]}
    # G's metrics: key "<seed>_cleanest_x1_d0.45_n30" holds {"base": DoRA-only clip metrics, "matched": steered (level-matched)}
    lab = {}
    for k, v in met.items():
        e = man.get(k)
        if e and e.get("preset") == "cleanest" and e.get("latch_scale") == 1 and e.get("dora_strength") == 0.45 and e.get("steps") == 30:
            lab[e["seed"]] = v
    report = {"n_latents": {a: sum(1 for (x, _) in lat if x == a) for a in ("dora", "cleanest")}}
    for arm in ("dora", "cleanest"):
        seeds = sorted(s for (a, s) in lat if a == arm)
        F, MU, SD = {}, [], []
        for s in seeds:
            f, mu, sd = features(np.load(lat[(arm, s)]))
            F[s] = f
            MU.append(mu)
            SD.append(sd)
        names = list(next(iter(F.values())))
        X = np.array([[F[s][n] for n in names] for s in seeds])
        Z = (X - X.mean(0)) / (X.std(0) + 1e-12)
        idx = {s: i for i, s in enumerate(seeds)}
        out = {"seeds": len(seeds), "features": names}
        for s in (764, 3050):
            if s in idx:
                out[f"z_{s}"] = {n: round(float(Z[idx[s], j]), 2) for j, n in enumerate(names)}
                out[f"raw_{s}"] = {n: round(F[s][n], 4) for n in names}
        # which features track clip quality across seeds (Spearman vs G's metrics of the DoRA-only clip)
        key = "base" if arm == "dora" else "matched"
        corr = {}
        for lname in ("ab_production_quality", "flatness", "zcr", "hf_ratio", "crest"):
            y = np.array([lab.get(s, {}).get(key, {}).get(lname, np.nan) for s in seeds], float)
            ok = np.isfinite(y)
            if ok.sum() < 10:
                continue
            ry = np.argsort(np.argsort(y[ok]))
            corr[lname] = {n: round(float(np.corrcoef(np.argsort(np.argsort(X[ok, j])), ry)[0, 1]), 2) for j, n in enumerate(names)}
        out["spearman_feature_vs_clip_metric"] = corr
        # a direction: 764's channel-mean/std profile minus the others'; does projecting on it predict PQ across seeds?
        P = np.hstack([np.array(MU), np.array(SD)])
        Pz = (P - P.mean(0)) / (P.std(0) + 1e-9)
        if 764 in idx:
            others = [i for s, i in idx.items() if s != 764]
            u = Pz[idx[764]] - Pz[others].mean(0)
            u /= np.linalg.norm(u) + 1e-12
            proj = Pz @ u
            out["proj_764_direction"] = {"764": round(float(proj[idx[764]]), 2), "3050": round(float(proj[idx[3050]]), 2) if 3050 in idx else None,
                                         "others_mean": round(float(proj[others].mean()), 2), "others_std": round(float(proj[others].std()), 2)}
            # leave-764-out: does the 764 direction rank the OTHER seeds' PQ? (not circular: 764 excluded)
            y = np.array([lab.get(s, {}).get(key, {}).get("ab_production_quality", np.nan) for s in seeds], float)
            ok = np.isfinite(y) & (np.arange(len(seeds)) != idx[764])
            if ok.sum() >= 10:
                out["proj_vs_pq_spearman_excl764"] = round(float(np.corrcoef(np.argsort(np.argsort(proj[ok])), np.argsort(np.argsort(y[ok])))[0, 1]), 2)
        # PCA of channel profiles: where 764 / 3050 sit
        U, S, Vt = np.linalg.svd(Pz - Pz.mean(0), full_matrices=False)
        sc = U * S
        out["pca_var_share"] = [round(float(v), 3) for v in (S ** 2 / (S ** 2).sum())[:5]]
        for s in (764, 3050):
            if s in idx:
                out[f"pca_{s}"] = [round(float(v), 2) for v in sc[idx[s], :5]]
        out["pca_score_std"] = [round(float(v), 2) for v in sc[:, :5].std(0)]
        report[arm] = out
    # --- the DoRA's own shift per seed: same seeds rendered without the DoRA (eval/punch_nodora_seeds.py) ---
    nd = NODORA if os.path.isdir(NODORA) else None
    if nd:
        seeds = sorted(s for (a, s) in lat if a == "dora" and os.path.exists(f"{nd}/nodora_s{s}.z0.npy"))
        names = None
        A, Bm, DMU = [], [], []
        for s in seeds:
            fa, mua, _ = features(np.load(lat[("dora", s)]))
            fb, mub, _ = features(np.load(f"{nd}/nodora_s{s}.z0.npy"))
            names = names or list(fa)
            A.append([fa[n] for n in names])
            Bm.append([fb[n] for n in names])
            DMU.append(mua - mub)
        A, Bm, DMU = np.array(A), np.array(Bm), np.array(DMU)
        D = A - Bm
        idx = {s: i for i, s in enumerate(seeds)}
        sh = {"seeds": len(seeds), "features": names,
              "mean_nodora": {n: round(float(Bm[:, j].mean()), 4) for j, n in enumerate(names)},
              "mean_dora": {n: round(float(A[:, j].mean()), 4) for j, n in enumerate(names)},
              "spread_nodora": {n: round(float(Bm[:, j].std()), 4) for j, n in enumerate(names)},
              "spread_dora": {n: round(float(A[:, j].std()), 4) for j, n in enumerate(names)},
              "shift_z": {n: round(float(D[:, j].mean() / (D[:, j].std() + 1e-12)), 2) for j, n in enumerate(names)}}
        for s in (764, 3050):
            if s in idx:
                sh[f"nodora_z_{s}"] = {n: round(float((Bm[idx[s], j] - Bm[:, j].mean()) / (Bm[:, j].std() + 1e-12)), 2) for j, n in enumerate(names)}
                sh[f"shift_z_{s}"] = {n: round(float((D[idx[s], j] - D[:, j].mean()) / (D[:, j].std() + 1e-12)), 2) for j, n in enumerate(names)}
        # is 764's channel-offset shift unusual? norm of the per-channel mean shift, z across seeds
        nrm = np.linalg.norm(DMU, axis=1)
        sh["channel_mean_shift_norm_z"] = {str(s): round(float((nrm[idx[s]] - nrm.mean()) / (nrm.std() + 1e-12)), 2) for s in (764, 3050) if s in idx}
        # does the DoRA pull every seed the same way? cosine of each seed's shift with the mean shift
        u = DMU.mean(0)
        cos = DMU @ u / (np.linalg.norm(DMU, axis=1) * np.linalg.norm(u) + 1e-12)
        sh["shift_alignment_with_mean"] = {"mean": round(float(cos.mean()), 3), "min": round(float(cos.min()), 3),
                                           **{str(s): round(float(cos[idx[s]]), 3) for s in (764, 3050) if s in idx}}
        report["dora_shift"] = sh
    json.dump(report, open(OUT, "w"), indent=1)
    print(json.dumps(report, indent=1)[:6000])
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
