#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-14)
"""latch_probe_r2.py -- is this LatCH target even LINEARLY readable from the SA3 latent? (CPU only, run BEFORE spending GPU on a head)

!! NOT A PREDICTOR OF STEERING (checked 2026-10-14, Kim: "those numbers just aren't very useful"). On 3000 goa crops it scores the heads known to
steer well LOW (rms_energy_bass 0.32, mid 0.23, body 0.14) and a head known dead under guidance HIGHER (beat_activation 0.47), and a head that
moves under guidance (spectral_kurtosis, 07-19) at 0.00. It has no dynamic range between works and doesn't-work. It measures only linear
readability of the target from the latent. Use it to catch a target that is garbage (it did show the madmom half-tempo target: opb 0.07 vs
0.42 once folded), never to decide whether a head is worth training.

WHY (Kim 2026-10-14: "if we were comparing cake recipes it would not help to have sugar, eggs, flour and nails as the training ingredients").
MASTER s5 records that probe R^2 predicts per-head control. latch/latch_probe_encodability.py did this for the retired SAO-Small latents
(points at Lehto/latents); this is the SA3 / bigset version, per FRAME, since the heads are per-frame regressors.

For each target field in the crops' .TIMESERIES.npz (default: onset_per_beat_ts onset_envelope_ts) it fits ridge  z_t (+ window mean) -> target_t
on a track-grouped split (no track in both halves) and reports held-out R^2 and Pearson r. Two controls print next to every number so it can be
audited rather than believed (AUDIT-THE-INSTRUMENT rule):
  * perm : the same fit with the TRAIN targets shuffled across frames -> must be ~0, else the pipeline leaks;
  * mean : R^2 of always guessing the train mean is 0 by construction (so R^2 is already 'gain over the trivial baseline').
Clip-level scalars (bpm_madmom, onset_density, onset_per_beat) are probed from time-pooled mean+std of the latent.

RUN (any venv with numpy; no torch/GPU):
    /home/kim/Projects/SAO/.venv/bin/python eval/latch_probe_r2.py --latent-dir /run/media/kim/Kosmos/latents_goa_bigset --n 1200
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

SCALARS = ("bpm_madmom", "bpm_essentia", "onset_density", "onset_per_beat", "lufs", "syncopation", "rhythmic_complexity")


def ridge_fit(X, y, lam):
    A = X.T @ X
    A[np.diag_indices_from(A)] += lam * len(X)
    return np.linalg.solve(A, X.T @ y)


def r2_r(y, p):
    sst = float(((y - y.mean()) ** 2).sum())
    return (1.0 - float(((y - p) ** 2).sum()) / max(sst, 1e-12), float(np.corrcoef(y, p)[0, 1]) if p.std() > 0 and y.std() > 0 else 0.0)


def window_mean(z, w):
    c = np.cumsum(np.pad(z, ((0, 0), (1, 0))), axis=1)
    T = z.shape[1]
    lo = np.clip(np.arange(T) - w, 0, T)
    hi = np.clip(np.arange(T) + w + 1, 0, T)
    return (c[:, hi] - c[:, lo]) / (hi - lo)


def _discover(npz_path):
    z = np.load(npz_path)
    return [k for k in z.files if k.endswith("_ts") and not k.endswith("_voiced_ts") and k not in ("valid_ts",)
            and z[k].ndim in (1, 2) and z[k].shape[0] > 8]


def _mask(ts, f, T):
    m = (ts["valid_ts"] > 0.5) if "valid_ts" in ts.files else np.ones(T, dtype=bool)
    v = f[:-3] + "_voiced_ts"                              # f0_*_ts: unvoiced frames are 0 Hz -- mask them, 0 Hz is not a low note (MASTER s2)
    if f.startswith("f0_") and v in ts.files:
        m = m & (ts[v] > 0.5)
    return m


def _group(j, base):
    sg = j.get("source_track")
    if sg:
        return sg
    rp = j.get("relpath", os.path.basename(base))
    return rp.rsplit("/", 1)[0] if rp.count("/") and rp.rsplit("/", 1)[1].isdigit() else rp


def load(latent_dir, n, fields, stride, win, seed):
    npys = sorted(glob.glob(os.path.join(latent_dir, "*.npy")))
    rng = np.random.default_rng(seed)
    rng.shuffle(npys)
    rows = {"X": [], "Y": {}, "M": {}, "g": [], "pool": [], "sc": {s: [] for s in SCALARS}, "pg": [], "fields": fields}
    for p in npys:
        base = p[:-4]
        if not (os.path.exists(base + ".TIMESERIES.npz") and os.path.exists(base + ".json")):
            continue
        ts = np.load(base + ".TIMESERIES.npz")
        if rows["fields"] is None:
            rows["fields"] = _discover(base + ".TIMESERIES.npz")
            rows["Y"] = {f: [] for f in rows["fields"]}
            rows["M"] = {f: [] for f in rows["fields"]}
        fields = rows["fields"]
        if not rows["Y"]:
            rows["Y"] = {f: [] for f in fields}
            rows["M"] = {f: [] for f in fields}
        if any(f not in ts.files for f in fields):
            continue
        z = np.load(p).astype(np.float32)                       # (256, T)
        T = z.shape[1]
        j = json.load(open(base + ".json"))
        grp = _group(j, base)
        valid = _mask(ts, "x", T)
        feats = np.concatenate([z, window_mean(z, win)], 0)      # (512, T)
        idx = np.arange(T)[::stride]
        rows["X"].append(feats[:, idx].T)
        for f in fields:
            rows["Y"][f].append(ts[f][idx])
            rows["M"][f].append(_mask(ts, f, T)[idx])
        rows["g"] += [grp] * len(idx)
        vz = z[:, valid] if valid.sum() > 8 else z
        rows["pool"].append(np.concatenate([vz.mean(1), vz.std(1)]))
        for s in SCALARS:
            v = float(ts[s]) if s in ts.files else j.get(s)
            try:
                rows["sc"][s].append(float(v))
            except (TypeError, ValueError):
                rows["sc"][s].append(np.nan)
        rows["pg"].append(grp)
        if len(rows["pool"]) >= n:
            break
    return rows


def split_groups(groups, frac, seed):
    u = sorted(set(groups))
    rng = np.random.default_rng(seed)
    rng.shuffle(u)
    val = set(u[: max(1, int(len(u) * frac))])
    return np.array([g in val for g in groups])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latent-dir", default="/run/media/kim/Kosmos/latents_goa_bigset")
    ap.add_argument("--fields", nargs="+", default=["onset_per_beat_ts", "onset_envelope_ts"], help="or the single word ALL: every 1-D/2-D *_ts field in the first npz")
    ap.add_argument("--n", type=int, default=1200, help="crops to read")
    ap.add_argument("--stride", type=int, default=16, help="frame stride (decorrelates neighbours)")
    ap.add_argument("--win", type=int, default=8, help="half-width (frames) of the context mean (8 ~ 0.75 s)")
    ap.add_argument("--lam", type=float, default=1e-2)
    ap.add_argument("--val-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None, help="write the table as JSON")
    a = ap.parse_args()
    R = load(a.latent_dir, a.n, None if a.fields == ["ALL"] else a.fields, a.stride, a.win, a.seed)
    if not R["X"]:
        sys.exit("no usable crops (is the drive mounted? are .TIMESERIES.npz present?)")
    X = np.concatenate(R["X"])
    isv = split_groups(R["g"], a.val_frac, a.seed)
    mu, sd = X[~isv].mean(0), X[~isv].std(0) + 1e-6
    Xn = (X - mu) / sd
    rng = np.random.default_rng(a.seed + 1)
    out = {"n_crops": len(R["pool"]), "n_frames": int(len(X)), "n_val_frames": int(isv.sum()), "frame": {}, "clip": {}}
    print(f"{out['n_crops']} crops, {out['n_frames']} frames ({out['n_val_frames']} held-out, track-grouped)")
    print(f"{'target':24s} {'R2':>7s} {'r':>7s} {'R2 perm':>8s}")
    for f in R["fields"]:
        y = np.concatenate(R["Y"][f]).astype(np.float64)
        ok = np.concatenate(R["M"][f]) & np.isfinite(y.reshape(len(y), -1)).all(1)
        tr, va = ~isv & ok, isv & ok
        if tr.sum() < 200 or va.sum() < 50:
            print(f"{f:24s}  (too few usable frames: {int(tr.sum())}/{int(va.sum())})")
            continue
        Y2 = y.reshape(len(y), -1)
        ym = Y2[tr].mean(0)
        w = ridge_fit(Xn[tr], Y2[tr] - ym, a.lam)
        wp = ridge_fit(Xn[tr], rng.permutation(Y2[tr]) - ym, a.lam)
        P_, Pp = Xn[va] @ w + ym, Xn[va] @ wp + ym
        per = [r2_r(Y2[va][:, c], P_[:, c]) for c in range(Y2.shape[1])]
        perp = [r2_r(Y2[va][:, c], Pp[:, c])[0] for c in range(Y2.shape[1])]
        r2, r, r2p = float(np.mean([q[0] for q in per])), float(np.mean([q[1] for q in per])), float(np.mean(perp))
        out["frame"][f] = {"r2": r2, "r": r, "r2_perm": r2p, "channels": Y2.shape[1], "n_val": int(va.sum()),
                           "r2_min_ch": float(min(q[0] for q in per)), "r2_max_ch": float(max(q[0] for q in per))}
        extra = f"  ({Y2.shape[1]} ch, R2 {out['frame'][f]['r2_min_ch']:.2f}..{out['frame'][f]['r2_max_ch']:.2f})" if Y2.shape[1] > 1 else ""
        print(f"{f:24s} {r2:7.3f} {r:7.3f} {r2p:8.3f}{extra}")
    P = np.stack(R["pool"])
    pv = split_groups(R["pg"], a.val_frac, a.seed)
    Pm, Ps = P[~pv].mean(0), P[~pv].std(0) + 1e-6
    Pn = (P - Pm) / Ps
    for s in SCALARS:
        y = np.array(R["sc"][s], dtype=np.float64)
        ok = np.isfinite(y)
        if ok.sum() < 30:
            continue
        tr, va = ~pv & ok, pv & ok
        if tr.sum() < 20 or va.sum() < 5:
            continue
        ym = y[tr].mean()
        w = ridge_fit(Pn[tr], y[tr] - ym, 1.0)
        r2, r = r2_r(y[va], Pn[va] @ w + ym)
        wp = ridge_fit(Pn[tr], rng.permutation(y[tr]) - ym, 1.0)
        r2p, _ = r2_r(y[va], Pn[va] @ wp + ym)
        out["clip"][s] = {"r2": r2, "r": r, "r2_perm": r2p, "n_val": int(va.sum())}
        print(f"clip:{s:19s} {r2:7.3f} {r:7.3f} {r2p:8.3f}")
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
