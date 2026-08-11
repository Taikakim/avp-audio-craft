#!/usr/bin/env python
"""analyze_melody_encoding_v2.py -- v2 (11x data) of the SAME latent-melody-encoding study.

Inputs: eval/musicology/test_midis_v2/latents/*.z0.npy (900 renders: 19 patterns x 4
tempos x 10 timbres + 2 sweeps x 10 timbres + BPM-phase addendum 2 pats x 20 BPMs x
{sine,sawlead,piano}), ground truth in test_midis_v2/manifest.json.

Reuses v1 helper math (../latent_melody_analysis/analyze_melody_encoding.py imported as
a module; v1 outputs untouched). All periodicity analyses are HIGH-PASSED at 2 Hz first
(v1 hazard: pitch-independent 0.4-1.3 Hz latent oscillation dominates raw ACF).

Stages:
  1  pitch atlas, 10 timbres, both lock-tempo sweeps; LOTO transfer + bootstrap CI
  2  ACF combs (high-passed) + interleaving over 7 alternating patterns x 2 drift
     tempos x 10 timbres; slope bootstrap CI
  3  fifth-jump x 10 timbres; delta-direction cosine CI
  4  melody-vs-timbre variance + melody subspace dim + corpus share, bootstrap CIs
  5  TEMPO-COVARIANCE: lock1 (1 fr/16th) vs lock2 (2 fr/16th) -- same subspace
     stretched, or frame-absolute?
  6  REGISTER: sweep-derived decoder validity on E2/E3/E4 pattern transpositions
  7  GATE: staccato (50%) vs default (80%) vs legato (100%) -- onset vs sustain content
  8  REST: silence handling (rest frames vs note frames vs true digital-silence code)
  9  BPM-PHASE addendum: fifth-jump detectability vs 20 BPMs, sine + fluid timbres

Outputs: results_v2.json + npz intermediates here. CPU only. Re-runnable.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

BASE = Path("/home/kim/Projects/SAO/eval/musicology")
LAT = BASE / "test_midis_v2/latents"
OUT = BASE / "latent_melody_analysis_v2"
sys.path.insert(0, str(BASE / "latent_melody_analysis"))
import analyze_melody_encoding as v1  # noqa: E402  (helpers only; v1 main() not run)

MAN = json.load(open(BASE / "test_midis_v2/manifest.json"))
FPS = MAN["same_fps"]
BPM_L1 = MAN["bpm_lock_exact"]        # 161.499..., 16th == 1 frame
BPM_L2 = MAN["bpm_lock2_exact"]       # 80.749..., 16th == 2 frames
TIMBRES = list(MAN["timbres_gm_program"])          # 10
V1_TIMBRES = MAN["v1_timbres"]
PATS = list(MAN["patterns"])                        # 19 pattern names
V1_PATS = PATS[:6]
TEMPO_TAG = {BPM_L1: ("bpm161p5", 32), BPM_L2: ("bpm80p75", 16), 143.0: ("bpm143", 28), 150.0: ("bpm150", 29)}
ALT_PATS = {  # strict A/B 16th alternations usable for the interleaving test
    "pat2_const16_2pitch": (52, 55), "pat7_wholetone_rock": (52, 50),
    "pat8_fifth_ping": (52, 59), "pat9_octave_bounce": (52, 64),
    "pat10_fourth_seesaw": (52, 57), "pat15_pat2_e2": (40, 43), "pat16_pat2_e4": (64, 67),
}
RNG = np.random.default_rng(7)
NBOOT = 2000


def zv2(stem, nframes=None):
    z = np.load(LAT / f"{stem}.z0.npy").astype(np.float32)
    assert z.shape[0] == 256, (stem, z.shape)
    if nframes is not None:
        assert z.shape[1] >= nframes, (stem, z.shape, nframes)
        z = z[:, :nframes]
    return z


def load(pat, bpm, timbre, nframes=None):
    tag, bars = TEMPO_TAG[bpm]
    return zv2(f"{pat}_{tag}_{bars}bars__{timbre}", nframes)


def highpass(z, fc=2.0):
    """4th-order Butterworth high-pass along time, fs = SAME frame rate."""
    b, a = butter(4, fc / (FPS / 2), btype="high")
    return filtfilt(b, a, z, axis=1).astype(np.float32)


def boot_ci(vals, stat=np.mean, n=NBOOT):
    vals = np.asarray(vals, dtype=float)
    bs = np.array([stat(RNG.choice(vals, size=len(vals), replace=True)) for _ in range(n)])
    return [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]


def d16_frames(bpm):
    return (60.0 / bpm / 4.0) * FPS


# ================================================================ stage 1: pitch atlas
def sweep_slots(timbre, bpm):
    if bpm == BPM_L1:
        z = zv2(f"sweep_chromatic_8ths_C2toC8_bpm161p5__{timbre}", 146)
        return z[:, 1::2].T                     # [73,256] 2nd frame of 2
    z = zv2(f"sweep_chromatic_8ths_C2toC8_bpm80p75__{timbre}", 292)
    return z.T.reshape(73, 4, 256)[:, 2:4].mean(1)  # [73,256] 2nd half of 4


def stage1():
    print("=" * 20, "STAGE 1: PITCH ATLAS (10 timbres)")
    pitches = np.arange(36, 109)
    res = {"per_timbre": {}}
    slot = {tb: sweep_slots(tb, BPM_L1) for tb in TIMBRES}
    weight, corrv = {}, {}
    for tb in TIMBRES:
        S = slot[tb]
        r2 = np.array([v1.r2_linear(pitches, S[:, c]) for c in range(256)])
        top = np.argsort(r2)[::-1][:20]
        lin = []
        for c in top[:10]:
            v = S[:, c]
            lin.append({"ch": int(c), "r2_lin": round(float(v1.r2_linear(pitches, v)), 4),
                        "r2_quad": round(float(v1.polyfit_r2(pitches, v, 2)), 4),
                        "r2_octbroken": round(float(v1.broken_octave_r2(pitches, v)[0]), 4)})
        w, Xm, ym, r2_loo = v1.ridge_loo(S, pitches.astype(float))
        weight[tb] = w
        corrv[tb] = np.array([np.corrcoef(S[:, c], pitches)[0, 1] for c in range(256)])
        sv = np.linalg.svd(S - S.mean(0), compute_uv=False)
        ev = sv ** 2 / (sv ** 2).sum()
        cum = np.cumsum(ev)
        res["per_timbre"][tb] = {
            "top20_channels": [int(c) for c in top],
            "top1_r2": round(float(r2[top[0]]), 4),
            "n_channels_r2_gt_0.5": int((r2 > 0.5).sum()),
            "median_r2": round(float(np.median(r2)), 4),
            "linearity_top10": lin,
            "ridge_loo_r2_decode_pitch": round(float(r2_loo), 4),
            "pca_n90": int(np.searchsorted(cum, 0.90) + 1),
        }
        print(f"[{tb}] top r2={r2[top[0]]:.3f} ridgeLOO={r2_loo:.3f}")
    n = len(TIMBRES)
    transfer = np.zeros((n, n))
    for i, a in enumerate(TIMBRES):
        w, Xm, ym, _ = v1.ridge_loo(slot[a], pitches.astype(float))
        for j, b in enumerate(TIMBRES):
            yh = (slot[b] - Xm) @ w + ym
            transfer[i, j] = 1 - np.sum((pitches - yh) ** 2) / np.sum((pitches - pitches.mean()) ** 2)
    cos_w = np.zeros((n, n))
    for i, a in enumerate(TIMBRES):
        for j, b in enumerate(TIMBRES):
            cos_w[i, j] = weight[a] @ weight[b] / (np.linalg.norm(weight[a]) * np.linalg.norm(weight[b]))
    Sall = np.concatenate([slot[t] for t in TIMBRES], 0)
    yall = np.tile(pitches, n).astype(float)
    _, _, _, r2_pool = v1.ridge_loo(Sall, yall, lam=50.0)
    loto = {}
    for hold in TIMBRES:
        tr = [t for t in TIMBRES if t != hold]
        w, Xm, ym, _ = v1.ridge_loo(np.concatenate([slot[t] for t in tr], 0),
                                    np.tile(pitches, n - 1).astype(float), lam=50.0)
        yh = (slot[hold] - Xm) @ w + ym
        loto[hold] = round(float(1 - np.sum((pitches - yh) ** 2) / np.sum((pitches - pitches.mean()) ** 2)), 3)
    loto_v1sub = {h: loto[h] for h in V1_TIMBRES}
    res["cross_timbre"] = {
        "mean_offdiag_transfer_r2": round(float((transfer.sum() - np.trace(transfer)) / (n * n - n)), 3),
        "mean_offdiag_cos_w": round(float((cos_w.sum() - n) / (n * n - n)), 3),
        "pooled_ridge_loo_r2": round(float(r2_pool), 4),
        "leave_one_timbre_out_r2": loto,
        "mean_loto_r2": round(float(np.mean(list(loto.values()))), 3),
        "loto_r2_ci95_boot_timbres": boot_ci(list(loto.values())),
        "mean_loto_r2_v1_5timbres_only": round(float(np.mean(list(loto_v1sub.values()))), 3),
        "transfer_matrix": np.round(transfer, 3).tolist(),
    }
    print("LOTO:", loto, "\nmean", res["cross_timbre"]["mean_loto_r2"], "CI", res["cross_timbre"]["loto_r2_ci95_boot_timbres"])
    # arp validation (pat3 @ lock1) with the pooled sweep decoder
    w, Xm, ym, _ = v1.ridge_loo(Sall, yall, lam=50.0)
    arp_truth = np.tile([52, 55, 59, 64], 128)
    val = {}
    for tb in TIMBRES:
        z = load("pat3_const16_arp4", BPM_L1, tb, 512)
        yh = (z.T - Xm) @ w + ym
        val[tb] = {"pred_mean_by_pos": [round(float(np.mean(yh[np.arange(512) % 4 == k])), 2) for k in range(4)],
                   "corr_with_truth": round(float(np.corrcoef(yh, arp_truth)[0, 1]), 3)}
    res["arp_validation_pat3"] = val
    np.savez(OUT / "stage1_pitch_atlas_v2.npz",
             slot_vectors=np.stack([slot[t] for t in TIMBRES]),
             ridge_weights=np.stack([weight[t] for t in TIMBRES]),
             pitches=pitches, timbres=np.array(TIMBRES),
             pooled_w=w, pooled_Xm=Xm, pooled_ym=np.array(ym))
    return res


# ================================================================ stage 2: ACF + interleave
def interleave_one(z, bpm, hp=False):
    """v1 stage-2 interleave machinery on any A/B 16th alternation. Returns metrics."""
    if hp:
        z = highpass(z)
    d16 = d16_frames(bpm)
    T = z.shape[1]
    n_notes = int(T / d16) - 1
    alphaA = np.zeros(T)
    for k in range(n_notes + 2):
        s, e = k * d16, (k + 1) * d16
        for i in range(max(0, int(np.floor(s))), min(T, int(np.ceil(e)))):
            ov = max(0.0, min(e, i + 1) - max(s, i))
            if k % 2 == 0:
                alphaA[i] += ov
    alphaA = np.clip(alphaA, 0, 1)
    valid = np.arange(8, int(n_notes * d16) - 8)
    aA = alphaA[valid]
    Z = z[:, valid].T
    pureA, pureB = aA > 0.95, aA < 0.05
    bnd = (aA > 0.2) & (aA < 0.8)
    if pureA.sum() < 10 or pureB.sum() < 10 or bnd.sum() < 10:
        return None
    muA, muB = Z[pureA].mean(0), Z[pureB].mean(0)
    axis = muB - muA
    ghat = (Z - muA) @ axis / (axis @ axis)
    gtrue = 1 - aA
    r2 = v1.r2_linear(gtrue[bnd], ghat[bnd])
    slope = float(np.polyfit(gtrue[bnd], ghat[bnd], 1)[0])
    interp = np.outer(1 - gtrue, muA) + np.outer(gtrue, muB)
    resid = np.linalg.norm(Z - interp, axis=1)
    scatter = 0.5 * (np.linalg.norm(Z[pureA] - muA, axis=1).mean()
                     + np.linalg.norm(Z[pureB] - muB, axis=1).mean())
    dA = np.linalg.norm(Z[bnd] - muA, axis=1)
    dB = np.linalg.norm(Z[bnd] - muB, axis=1)
    snap = float(np.mean(resid[bnd] - np.minimum(dA, dB)))  # <0 would mean snapped
    return {"slope": round(slope, 3), "r2": round(float(r2), 3),
            "resid_over_scatter": round(float(resid[bnd].mean() / scatter), 3),
            "snap_margin": round(snap, 3), "n_boundary": int(bnd.sum())}


def stage2():
    print("=" * 20, "STAGE 2: ACF (high-passed) + INTERLEAVING (7 pats x 2 drifts x 10 timbres)")
    res = {}
    # ACF combs on locked files, raw vs high-passed
    acf = {}
    for pat, period in [("pat2_const16_2pitch", 2), ("pat3_const16_arp4", 4)]:
        raw = np.mean([v1.acf_multivar(load(pat, BPM_L1, tb, 512)) for tb in TIMBRES], 0)
        hp = np.mean([v1.acf_multivar(highpass(load(pat, BPM_L1, tb, 512))) for tb in TIMBRES], 0)
        acf[pat] = {"period_truth": period, "raw_lags1_8": np.round(raw[:8], 3).tolist(),
                    "hp_lags1_8": np.round(hp[:8], 3).tolist()}
        print(f"[{pat}] hp ACF lags1-8: {np.round(hp[:8],3)}")
    res["acf_locked_lock1"] = acf

    cells = {}
    slopes, r2s = [], []
    for pat in ALT_PATS:
        for bpm in (143.0, 150.0):
            nfr = 505 if bpm == 143.0 else 499
            for tb in TIMBRES:
                m = interleave_one(load(pat, bpm, tb, nfr), bpm)
                if m is None:
                    continue
                cells[f"{pat}__{TEMPO_TAG[bpm][0]}__{tb}"] = m
                slopes.append(m["slope"])
                r2s.append(m["r2"])
    slopes, r2s = np.array(slopes), np.array(r2s)
    # high-passed variant on the v1 cell for comparison
    hp_v1cell = {tb: interleave_one(load("pat2_const16_2pitch", 143.0, tb, 505), 143.0, hp=True)
                 for tb in TIMBRES}
    res["interleave"] = {
        "n_cells": len(slopes),
        "slope_mean": round(float(slopes.mean()), 3),
        "slope_ci95_boot_cells": boot_ci(slopes),
        "slope_median": round(float(np.median(slopes)), 3),
        "r2_mean": round(float(r2s.mean()), 3), "r2_ci95": boot_ci(r2s),
        "per_cell": cells,
        "hp_variant_pat2_143": {t: m for t, m in hp_v1cell.items() if m},
    }
    # per-pattern and per-timbre means (interval-size dependence!)
    bypat = {p: round(float(np.mean([v["slope"] for k, v in cells.items() if k.startswith(p + "__")])), 3)
             for p in ALT_PATS}
    bytb = {t: round(float(np.mean([v["slope"] for k, v in cells.items() if k.endswith("__" + t)])), 3)
            for t in TIMBRES}
    res["interleave"]["slope_by_pattern"] = bypat
    res["interleave"]["slope_by_timbre"] = bytb
    print(f"interleave: {len(slopes)} cells slope={slopes.mean():.3f} CI{res['interleave']['slope_ci95_boot_cells']} R2={r2s.mean():.3f}")
    print(" by pattern:", bypat)
    return res


# ================================================================ stage 3: fifth-jump
def jump_metrics(Z, phase, pedal_ph, jump_ph):
    pedal_mask = np.isin(phase, pedal_ph)
    jump_mask = np.isin(phase, jump_ph)
    mu_p, sd_p = Z[pedal_mask].mean(0), Z[pedal_mask].std(0) + 1e-6
    mu_j, sd_j = Z[jump_mask].mean(0), Z[jump_mask].std(0)
    pooled = np.sqrt(0.5 * (sd_p ** 2 + sd_j ** 2)) + 1e-6
    delta = mu_j - mu_p
    w = delta / (pooled ** 2)
    s_j, s_p = Z[jump_mask] @ w, Z[pedal_mask] @ w
    thr = 0.5 * (s_j.mean() + s_p.mean())
    acc = 0.5 * (np.mean(s_j > thr) + np.mean(s_p < thr))
    zdist_j = float(np.sqrt((((Z[jump_mask] - mu_p) / sd_p) ** 2).mean(1)).mean())
    zdist_p = float(np.sqrt((((Z[pedal_mask] - mu_p) / sd_p) ** 2).mean(1)).mean())
    return delta, float(acc), zdist_j, zdist_p


def stage3():
    print("=" * 20, "STAGE 3: FIFTH-JUMP (10 timbres)")
    res = {}
    deltas = {}
    phase = np.arange(512) % 16
    for tb in TIMBRES:
        Z = load("pat5_const8_fifthjump", BPM_L1, tb, 512).T
        delta, acc, zj, zp = jump_metrics(Z, phase, [2, 3, 4, 5, 6, 7], [8, 9])
        deltas[tb] = delta
        d = delta / (np.sqrt(0.5 * (Z[np.isin(phase, [2, 3, 4, 5, 6, 7])].std(0) ** 2
                                    + Z[np.isin(phase, [8, 9])].std(0) ** 2)) + 1e-6)
        res[tb] = {"lda_balanced_acc": round(acc, 4), "zdist_jump": round(zj, 2),
                   "zdist_pedal": round(zp, 2), "n_channels_absd_gt1": int((np.abs(d) > 1).sum())}
        print(f"[{tb}] acc={acc:.3f} zdist j/p={zj:.2f}/{zp:.2f}")
    n = len(TIMBRES)
    cos = np.zeros((n, n))
    for i, a in enumerate(TIMBRES):
        for j, b in enumerate(TIMBRES):
            cos[i, j] = deltas[a] @ deltas[b] / (np.linalg.norm(deltas[a]) * np.linalg.norm(deltas[b]))
    off = cos[~np.eye(n, dtype=bool)]
    res["mean_offdiag_delta_cosine"] = round(float(off.mean()), 3)
    res["delta_cosine_ci95_boot_pairs"] = boot_ci(off)
    res["min_lda_acc"] = round(float(min(res[t]["lda_balanced_acc"] for t in TIMBRES)), 4)
    print("jump-direction cos:", res["mean_offdiag_delta_cosine"], "CI", res["delta_cosine_ci95_boot_pairs"])
    np.savez(OUT / "stage3_fifthjump_v2.npz", deltas=np.stack([deltas[t] for t in TIMBRES]),
             timbres=np.array(TIMBRES))
    return res


# ================================================================ stage 4: variance / subspace
def melody_subspace_dim(X, timbre_idx=None, pat_idx=None):
    """X [P,T,B,phase,C] -> n90 of timbre+bar-averaged pattern trajectories."""
    P, Tn, B, PH, C = X.shape
    ti = np.arange(Tn) if timbre_idx is None else timbre_idx
    pi = np.arange(P) if pat_idx is None else pat_idx
    M = X[pi][:, ti].mean((1, 2))                       # [p,phase,C]
    Mc = (M - M.mean((0, 1))).reshape(-1, C)
    sv = np.linalg.svd(Mc, compute_uv=False)
    cum = np.cumsum(sv ** 2 / (sv ** 2).sum())
    return int(np.searchsorted(cum, 0.90) + 1)


def stage4():
    print("=" * 20, "STAGE 4: VARIANCE / MELODY SUBSPACE (19 pats x 10 timbres)")
    res = {}
    nP, nT = len(PATS), len(TIMBRES)
    X = np.zeros((nP, nT, 32, 16, 256), dtype=np.float32)
    for pi, pat in enumerate(PATS):
        for ti, tb in enumerate(TIMBRES):
            X[pi, ti] = load(pat, BPM_L1, tb, 512).T.reshape(32, 16, 256)

    def anova2(A):
        gm = A.mean((0, 1, 2))
        pm = A.mean((1, 2)) - gm
        tm = A.mean((0, 2)) - gm
        cell = A.mean(2)
        inter = cell - pm[:, None] - tm[None, :] - gm
        P, T, B, C = A.shape
        ss_p = B * T * (pm ** 2).sum(0)
        ss_t = B * P * (tm ** 2).sum(0)
        ss_i = B * (inter ** 2).sum((0, 1))
        ss_r = ((A - cell[:, :, None]) ** 2).sum((0, 1, 2))
        return ss_p, ss_t, ss_i, ss_r

    for name, pidx in [("full_19pats", np.arange(nP)), ("v1_6pats", np.arange(6))]:
        A = X[pidx].mean(3)
        ss = anova2(A)
        tot = sum(s.sum() for s in ss)
        fp = ss[0] / (ss[0] + ss[1] + ss[2] + ss[3])
        ft = ss[1] / (ss[0] + ss[1] + ss[2] + ss[3])
        res[f"frame_averaged_{name}"] = {
            "frac_pattern": round(float(ss[0].sum() / tot), 4),
            "frac_timbre": round(float(ss[1].sum() / tot), 4),
            "n_ch_pattern_dominant": int(((fp > ft) & (fp > 0.5)).sum()),
            "n_ch_timbre_dominant": int(((ft > fp) & (ft > 0.5)).sum()),
        }
    # melody subspace dim + bootstrap CI over timbres and patterns
    n90 = melody_subspace_dim(X)
    n90_v1sub = melody_subspace_dim(X, timbre_idx=np.array([TIMBRES.index(t) for t in V1_TIMBRES]),
                                    pat_idx=np.arange(6))
    bs = []
    for _ in range(400):  # SVD-heavy, keep 400
        ti = RNG.choice(nT, nT, replace=True)
        pi = np.unique(RNG.choice(nP, nP, replace=True))  # unique: duplicates add no rank
        bs.append(melody_subspace_dim(X, ti, pi))
    res["melody_subspace"] = {
        "pca_n90_full": n90, "pca_n90_v1_replica": n90_v1sub,
        "n90_ci95_boot_pat_timbre": [int(np.percentile(bs, 2.5)), int(np.percentile(bs, 97.5))],
    }
    M = X.mean((1, 2))
    Mc = (M - M.mean((0, 1))).reshape(-1, 256)
    U, S, Vt = np.linalg.svd(Mc, full_matrices=False)
    ev = S ** 2 / (S ** 2).sum()
    Vm = Vt[:n90]
    print(f"melody subspace n90={n90} (v1-replica {n90_v1sub}) CI {res['melody_subspace']['n90_ci95_boot_pat_timbre']}")

    # variance shares (v1 formula) + bootstrap over timbres
    def var_share(Flat):
        gm = Flat.mean((0, 1, 2))
        tot = float(((Flat - gm) ** 2).sum())
        mel = float(Flat.shape[1] * ((Flat.mean(1) - gm) ** 2).sum())
        timb = float(Flat.shape[0] * Flat.shape[2] * ((Flat.mean((0, 2)) - gm) ** 2).sum())
        return mel / tot, timb / tot
    Flat = X.reshape(nP, nT, 512, 256)
    mel_f, timb_f = var_share(Flat)
    # jackknife over timbres (bootstrap-with-replacement is biased here: duplicated
    # timbres shrink timbre diversity and inflate the timbre-averaged melody share)
    jk = np.array([var_share(Flat[:, [i for i in range(nT) if i != h]])[0] for h in range(nT)])
    se = float(np.sqrt((nT - 1) / nT * ((jk - jk.mean()) ** 2).sum()))
    res["variance_share_renders"] = {
        "melody_frac": round(mel_f, 4), "timbre_frac": round(timb_f, 4),
        "melody_frac_ci95_jackknife_timbres": [round(mel_f - 1.96 * se, 4), round(mel_f + 1.96 * se, 4)],
        "v1_6pats_melody_frac": round(var_share(Flat[:6])[0], 4),
        "v1_replica_6pats_5timbres_melody_frac": round(
            var_share(Flat[:6][:, [TIMBRES.index(t) for t in V1_TIMBRES]])[0], 4),
    }
    print("melody var frac %.3f CI %s (v1-replica %.3f)" % (
        mel_f, res["variance_share_renders"]["melody_frac_ci95_jackknife_timbres"],
        res["variance_share_renders"]["v1_replica_6pats_5timbres_melody_frac"]))

    # corpus projection + CI over files
    corpus_dir = Path("/home/kim/Projects/latents_sa3")
    if corpus_dir.is_dir():
        files = sorted(corpus_dir.glob("*.npy"))[::100][:60]
        Q, _ = np.linalg.qr(RNG.standard_normal((256, Vm.shape[0])))
        Vr = Q.T
        fr_mel, fr_rand = [], []
        for f in files:
            z = np.load(f).astype(np.float32)
            if z.ndim == 3:
                z = z[0]
            zc = z - z.mean(1, keepdims=True)
            v_tot = float((zc ** 2).sum())
            fr_mel.append(float(((Vm @ zc) ** 2).sum()) / v_tot)
            fr_rand.append(float(((Vr @ zc) ** 2).sum()) / v_tot)
        enrich = np.array(fr_mel) / np.array(fr_rand)
        res["corpus_projection"] = {
            "n_files": len(files), "k_dims": int(Vm.shape[0]),
            "melody_frac_mean": round(float(np.mean(fr_mel)), 4),
            "melody_frac_ci95_boot_files": boot_ci(fr_mel),
            "random_frac_mean": round(float(np.mean(fr_rand)), 4),
            "enrichment_mean": round(float(np.mean(enrich)), 3),
            "enrichment_ci95_boot_files": boot_ci(enrich),
        }
        print("corpus: mel frac %.4f CI %s enrich %.2fx CI %s" % (
            np.mean(fr_mel), res["corpus_projection"]["melody_frac_ci95_boot_files"],
            np.mean(enrich), res["corpus_projection"]["enrichment_ci95_boot_files"]))
    np.savez(OUT / "stage4_subspaces_v2.npz", melody_basis=Vt, melody_ev=ev)
    return res


# ================================================================ stage 5: tempo covariance
def stage5():
    print("=" * 20, "STAGE 5: TEMPO COVARIANCE (lock1 1fr/16th vs lock2 2fr/16th)")
    res = {}
    # mean-bar trajectories
    T1, T2d, T2 = {}, {}, {}
    for pat in PATS:
        for tb in TIMBRES:
            t1 = load(pat, BPM_L1, tb, 512).T.reshape(32, 16, 256).mean(0)     # [16,256]
            t2 = load(pat, BPM_L2, tb, 512).T.reshape(16, 32, 256).mean(0)     # [32,256]
            T1[(pat, tb)] = t1
            T2[(pat, tb)] = t2
            T2d[(pat, tb)] = t2.reshape(16, 2, 256).mean(1)                     # [16,256]
    def ccos(a, b):
        a = (a - a.mean(0)).ravel()
        b = (b - b.mean(0)).ravel()
        return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    same, cross = [], []
    for tb in TIMBRES:
        for p in PATS:
            same.append(ccos(T1[(p, tb)], T2d[(p, tb)]))
            q = PATS[(PATS.index(p) + 7) % len(PATS)]
            cross.append(ccos(T1[(p, tb)], T2d[(q, tb)]))
    res["traj_cos_same_pattern_mean"] = round(float(np.mean(same)), 3)
    res["traj_cos_same_ci95"] = boot_ci(same)
    res["traj_cos_crossed_pattern_mean"] = round(float(np.mean(cross)), 3)
    print(f"traj cos same={np.mean(same):.3f} CI {res['traj_cos_same_ci95']} vs crossed={np.mean(cross):.3f}")

    # onset-half vs sustain-half of the 2-frame notes vs the 1-frame code
    on_cos = [ccos(T1[(p, tb)], T2[(p, tb)][0::2]) for p in PATS for tb in TIMBRES]
    su_cos = [ccos(T1[(p, tb)], T2[(p, tb)][1::2]) for p in PATS for tb in TIMBRES]
    res["cos_lock1_vs_lock2_onset_frames"] = round(float(np.mean(on_cos)), 3)
    res["cos_lock1_vs_lock2_sustain_frames"] = round(float(np.mean(su_cos)), 3)

    # subspace principal angles + cross-capture
    def basis(Td):
        M = np.stack([np.mean([Td[(p, tb)] for tb in TIMBRES], 0) for p in PATS])
        Mc = (M - M.mean((0, 1))).reshape(-1, 256)
        U, S, Vt = np.linalg.svd(Mc, full_matrices=False)
        cum = np.cumsum(S ** 2 / (S ** 2).sum())
        k = int(np.searchsorted(cum, 0.90) + 1)
        return Vt[:k], Mc
    V1b, M1c = basis(T1)
    V2b, M2c = basis(T2d)
    k = min(V1b.shape[0], V2b.shape[0])
    sv = np.linalg.svd(V1b[:k] @ V2b[:k].T, compute_uv=False)
    angles = np.degrees(np.arccos(np.clip(sv, -1, 1)))
    cap12 = float(((V1b @ M2c.T) ** 2).sum() / (M2c ** 2).sum())
    Q, _ = np.linalg.qr(RNG.standard_normal((256, V1b.shape[0])))
    cap_rand = float(((Q.T @ M2c.T) ** 2).sum() / (M2c ** 2).sum())
    res["subspace"] = {
        "k1": int(V1b.shape[0]), "k2": int(V2b.shape[0]),
        "principal_angles_deg_first8": np.round(angles[:8], 1).tolist(),
        "median_principal_angle_deg": round(float(np.median(angles)), 1),
        "lock2_traj_var_captured_by_lock1_basis": round(cap12, 3),
        "captured_by_random_basis": round(cap_rand, 3),
    }
    print(f"subspace: angles(first8)={np.round(angles[:8],1)} capture={cap12:.3f} (rand {cap_rand:.3f})")

    # pitch-decoder transfer across lock tempos (sweep-trained)
    pitches = np.arange(36, 109).astype(float)
    r2ct = {}
    for (a, b), tag in [((BPM_L1, BPM_L2), "lock1_to_lock2"), ((BPM_L2, BPM_L1), "lock2_to_lock1")]:
        Sa = np.concatenate([sweep_slots(t, a) for t in TIMBRES], 0)
        Sb = np.concatenate([sweep_slots(t, b) for t in TIMBRES], 0)
        ya = np.tile(pitches, len(TIMBRES))
        w, Xm, ym, _ = v1.ridge_loo(Sa, ya, lam=50.0)
        yh = (Sb - Xm) @ w + ym
        r2ct[tag] = round(float(1 - np.sum((ya - yh) ** 2) / np.sum((ya - ya.mean()) ** 2)), 3)
    res["sweep_decoder_cross_tempo_r2"] = r2ct
    print("decoder cross-tempo:", r2ct)
    return res


# ================================================================ stage 6: register
def stage6():
    print("=" * 20, "STAGE 6: REGISTER (E2/E3/E4 transpositions)")
    d = np.load(OUT / "stage1_pitch_atlas_v2.npz")
    w, Xm, ym = d["pooled_w"], d["pooled_Xm"], float(d["pooled_ym"])
    res = {}
    triples = {"pat1_family": [("pat13_pat1_e2", 40.0), ("pat1_const16_1pitch", 52.0), ("pat14_pat1_e4", 64.0)],
               "pat2_family": [("pat15_pat2_e2", 41.5), ("pat2_const16_2pitch", 53.5), ("pat16_pat2_e4", 65.5)]}
    for fam, trip in triples.items():
        per_tb = {}
        errs, orders = [], []
        for tb in TIMBRES:
            preds = []
            for pat, truth in trip:
                z = load(pat, BPM_L1, tb, 512)
                yh = (z.T - Xm) @ w + ym
                preds.append(float(yh.mean()))
            truths = [t for _, t in trip]
            order_ok = bool(preds[0] < preds[1] < preds[2])
            mae = float(np.mean(np.abs(np.array(preds) - np.array(truths))))
            per_tb[tb] = {"pred_E2_E3_E4": [round(p, 2) for p in preds],
                          "truth": truths, "order_correct": order_ok,
                          "mae_semitones": round(mae, 2)}
            errs.append(mae)
            orders.append(order_ok)
        res[fam] = {"per_timbre": per_tb,
                    "frac_order_correct": round(float(np.mean(orders)), 3),
                    "mae_semitones_mean": round(float(np.mean(errs)), 2),
                    "mae_ci95_boot_timbres": boot_ci(errs)}
        print(f"[{fam}] order-correct {np.mean(orders):.2f} MAE {np.mean(errs):.2f} st CI {res[fam]['mae_ci95_boot_timbres']}")
    return res


# ================================================================ stage 7: gate
def stage7():
    print("=" * 20, "STAGE 7: GATE (staccato 50% vs 80% vs legato 100%)")
    res = {}
    gates = {"gate50": "pat17_pat1_gate50", "gate80": "pat1_const16_1pitch", "gate100": "pat18_pat1_gate100"}
    # lock2: 16th = 2 frames -> parity 0 = onset half, parity 1 = second half
    per = {}
    for tb in TIMBRES:
        Z = {g: load(p, BPM_L2, tb, 512).T for g, p in gates.items()}
        idx = np.arange(512)
        r = {}
        for g, z in Z.items():
            n0 = float(np.linalg.norm(z[idx % 2 == 0], axis=1).mean())
            n1 = float(np.linalg.norm(z[idx % 2 == 1], axis=1).mean())
            r[g] = {"norm_onset_frames": round(n0, 1), "norm_second_frames": round(n1, 1),
                    "sustain_over_onset_norm": round(n1 / n0, 3)}
        # LDA gate50 vs gate100 on each parity
        for par, name in [(0, "onset"), (1, "second")]:
            A, B = Z["gate50"][idx % 2 == par], Z["gate100"][idx % 2 == par]
            mu_a, mu_b = A.mean(0), B.mean(0)
            pooled = np.sqrt(0.5 * (A.std(0) ** 2 + B.std(0) ** 2)) + 1e-6
            wv = (mu_b - mu_a) / pooled ** 2
            sa, sb = A @ wv, B @ wv
            thr = 0.5 * (sa.mean() + sb.mean())
            r[f"lda_50v100_{name}_frames"] = round(float(0.5 * (np.mean(sb > thr) + np.mean(sa < thr))), 3)
        per[tb] = r
    res["lock2_per_timbre"] = per
    s2o_50 = np.array([per[t]["gate50"]["sustain_over_onset_norm"] for t in TIMBRES])
    s2o_100 = np.array([per[t]["gate100"]["sustain_over_onset_norm"] for t in TIMBRES])
    res["summary"] = {
        "sustain_over_onset_norm_gate50_mean": round(float(s2o_50.mean()), 3),
        "sustain_over_onset_norm_gate100_mean": round(float(s2o_100.mean()), 3),
        "lda_50v100_onset_mean": round(float(np.mean([per[t]["lda_50v100_onset_frames"] for t in TIMBRES])), 3),
        "lda_50v100_second_mean": round(float(np.mean([per[t]["lda_50v100_second_frames"] for t in TIMBRES])), 3),
    }
    # lock1 (1 fr/16th): whole-frame separability of the three gates
    sep = {}
    for tb in TIMBRES:
        Zs = {g: load(p, BPM_L1, tb, 512).T for g, p in gates.items()}
        mu = {g: z.mean(0) for g, z in Zs.items()}
        scat = np.mean([np.linalg.norm(z - mu[g], axis=1).mean() for g, z in Zs.items()])
        sep[tb] = {"d_50_100_over_scatter": round(float(np.linalg.norm(mu["gate50"] - mu["gate100"]) / scat), 3),
                   "d_50_80_over_scatter": round(float(np.linalg.norm(mu["gate50"] - mu["gate80"]) / scat), 3),
                   "d_80_100_over_scatter": round(float(np.linalg.norm(mu["gate80"] - mu["gate100"]) / scat), 3)}
    res["lock1_centroid_sep"] = sep
    print("summary:", res["summary"])
    return res


# ================================================================ stage 8: rest / silence
def stage8():
    print("=" * 20, "STAGE 8: REST HANDLING (pat19, rest on beat 3)")
    res = {}
    # true-silence reference: tails of globally-padded SINE bpm-phase latents (sine has a
    # 5 ms release ramp + 0.5 s in-file pad, then global zero-pad -> pure digital silence;
    # only files padded to the global length T>=550 qualify)
    sil_parts = []
    for p in MAN["bpm_phase_probe"]["points"]:
        stem = f"pat1_const16_1pitch_bpm{p['bpm']:07.3f}".replace(".", "p") + f"_{p['bars']}bars__sine"
        z = zv2(stem)
        music_end = int(np.ceil(p["bars"] * 16 * d16_frames(p["bpm"]) + 0.5 * FPS))
        if z.shape[1] >= music_end + 20:
            sil_parts.append(z[:, music_end + 8:z.shape[1] - 2].T)
    sil = np.concatenate(sil_parts, 0)
    assert len(sil) > 100, f"only {len(sil)} silence frames found"
    mu_sil = sil.mean(0)
    res["silence_ref"] = {"norm_mean": round(float(np.linalg.norm(sil, axis=1).mean()), 1),
                          "scatter": round(float(np.linalg.norm(sil - mu_sil, axis=1).mean()), 1)}
    per = {}
    for tb in TIMBRES:
        Z = load("pat19_rest8_beat3", BPM_L1, tb, 512).T
        ph = np.arange(512) % 16
        note_m = np.isin(ph, [0, 1, 2, 3, 4, 5, 6, 12, 13, 14])   # interior sounding frames
        rest_m = np.isin(ph, [9, 10, 11])                          # skip 8 (release bleed)
        mu_n, mu_r = Z[note_m].mean(0), Z[rest_m].mean(0)
        scat_n = float(np.linalg.norm(Z[note_m] - mu_n, axis=1).mean())
        scat_r = float(np.linalg.norm(Z[rest_m] - mu_r, axis=1).mean())
        # LDA rest vs note
        pooled = np.sqrt(0.5 * (Z[note_m].std(0) ** 2 + Z[rest_m].std(0) ** 2)) + 1e-6
        wv = (mu_r - mu_n) / pooled ** 2
        sn, sr_ = Z[note_m] @ wv, Z[rest_m] @ wv
        thr = 0.5 * (sn.mean() + sr_.mean())
        acc = 0.5 * (np.mean(sr_ > thr) + np.mean(sn < thr))
        per[tb] = {
            "norm_note": round(float(np.linalg.norm(Z[note_m], axis=1).mean()), 1),
            "norm_rest": round(float(np.linalg.norm(Z[rest_m], axis=1).mean()), 1),
            "rest_scatter_over_note_scatter": round(scat_r / scat_n, 3),
            "d_rest_to_silence_over_scatter": round(float(np.linalg.norm(mu_r - mu_sil)) / scat_r, 2),
            "d_rest_to_note_over_scatter": round(float(np.linalg.norm(mu_r - mu_n)) / scat_r, 2),
            "lda_rest_vs_note_acc": round(float(acc), 4),
        }
    res["per_timbre"] = per
    res["summary"] = {
        "norm_rest_over_note_mean": round(float(np.mean([per[t]["norm_rest"] / per[t]["norm_note"] for t in TIMBRES])), 3),
        "d_rest_silence_mean": round(float(np.mean([per[t]["d_rest_to_silence_over_scatter"] for t in TIMBRES])), 2),
        "d_rest_note_mean": round(float(np.mean([per[t]["d_rest_to_note_over_scatter"] for t in TIMBRES])), 2),
        "lda_rest_vs_note_mean": round(float(np.mean([per[t]["lda_rest_vs_note_acc"] for t in TIMBRES])), 3),
    }
    print("rest summary:", res["summary"])
    return res


# ================================================================ stage 9: BPM-phase addendum
def stage9():
    print("=" * 20, "STAGE 9: BPM-PHASE PROBE (fifth-jump detectability vs 20 BPMs)")
    bp = MAN["bpm_phase_probe"]
    pts = bp["points"]
    res = {"points": pts, "curve": {}, "sine_direction": {}}
    timbres = ["sine", "sawlead", "piano"]
    deltas = {tb: {} for tb in timbres}  # tb -> k -> delta vector (pat5 jump direction)
    curve = []
    for p in pts:
        bpm, ratio, bars = p["bpm"], p["ratio_frames_per_16th"], p["bars"]
        d16 = d16_frames(bpm)
        stem5 = f"pat5_const8_fifthjump_bpm{bpm:07.3f}".replace(".", "p") + f"_{bars}bars"
        stem1 = f"pat1_const16_1pitch_bpm{bpm:07.3f}".replace(".", "p") + f"_{bars}bars"
        nfr = int(bars * 16 * d16) - 1
        row = {"k": p["k"], "bpm": round(bpm, 3), "ratio": round(ratio, 5), "bars": bars}
        for tb in timbres:
            for stem, key in [(stem5, tb), (stem1, tb + "_ctl")]:
                z = zv2(f"{stem}__{tb}", nfr)
                Z = z.T
                T = Z.shape[0]
                # frame masks by exact time overlap
                jump_cov = np.zeros(T)
                pedal_cov = np.zeros(T)
                for b in range(bars):
                    j0, j1 = (16 * b + 8) * d16, (16 * b + 10) * d16
                    p0, p1 = (16 * b + 2) * d16, (16 * b + 8) * d16
                    for i in range(int(j0) - 1, min(T, int(np.ceil(j1)) + 1)):
                        if i >= 0:
                            jump_cov[i] += max(0.0, min(j1, i + 1) - max(j0, i))
                    for i in range(int(p0), min(T, int(np.ceil(p1)))):
                        pedal_cov[i] += max(0.0, min(p1, i + 1) - max(p0, i))
                jm = jump_cov >= 0.7
                pm = (pedal_cov >= 0.999) & (jump_cov == 0)
                if jm.sum() < 8 or pm.sum() < 16:
                    continue
                # in-sample LDA (v1-style)
                mu_p, sd_p = Z[pm].mean(0), Z[pm].std(0) + 1e-6
                mu_j = Z[jm].mean(0)
                pooled = np.sqrt(0.5 * (sd_p ** 2 + Z[jm].std(0) ** 2)) + 1e-6
                delta = mu_j - mu_p
                wv = delta / pooled ** 2
                sj, sp = Z[jm] @ wv, Z[pm] @ wv
                thr = 0.5 * (sj.mean() + sp.mean())
                acc_in = 0.5 * (np.mean(sj > thr) + np.mean(sp < thr))
                # leave-one-bar-out CV: 2-fold splits proved fold-scheme-sensitive
                # (bar start phase precesses, and with 16-34 bars a threshold fit on
                # half the bars is unstable); LOBO trains on all-but-one bar, is
                # phase-fair by construction, and gives a stable per-file estimate.
                barid = (np.arange(T) / (16 * d16)).astype(int)
                nb = barid.max() + 1
                hitj, hitp, ntj, ntp = 0, 0, 0, 0
                for hb in range(nb):
                    te = barid == hb
                    tr = ~te
                    if (jm & te).sum() == 0 and (pm & te).sum() == 0:
                        continue
                    if (jm & tr).sum() < 3 or (pm & tr).sum() < 6:
                        continue
                    mu_pt = Z[pm & tr].mean(0)
                    pooled_t = np.sqrt(0.5 * (Z[pm & tr].std(0) ** 2 + Z[jm & tr].std(0) ** 2)) + 1e-6
                    wt = (Z[jm & tr].mean(0) - mu_pt) / pooled_t ** 2
                    thr_t = 0.5 * (float((Z[jm & tr] @ wt).mean()) + float((Z[pm & tr] @ wt).mean()))
                    hitj += int((Z[jm & te] @ wt > thr_t).sum()); ntj += int((jm & te).sum())
                    hitp += int((Z[pm & te] @ wt < thr_t).sum()); ntp += int((pm & te).sum())
                acc_cv = 0.5 * (hitj / max(ntj, 1) + hitp / max(ntp, 1)) if (ntj and ntp) else float("nan")
                zdist = float(np.sqrt((((Z[jm] - mu_p) / sd_p) ** 2).mean(1)).mean())
                row[key] = {"acc_in": round(float(acc_in), 3), "acc_cv": round(acc_cv, 3),
                            "zdist_jump": round(zdist, 2), "n_jump_frames": int(jm.sum())}
                if stem == stem5:
                    deltas[tb][p["k"]] = delta
        curve.append(row)
    res["curve"] = curve

    # jump-direction consistency ACROSS BPMs, per timbre (vs v1 cross-timbre 0.27)
    for tb in timbres:
        ks = sorted(deltas[tb])
        D = np.stack([deltas[tb][k] / np.linalg.norm(deltas[tb][k]) for k in ks])
        C = D @ D.T
        off = C[~np.eye(len(ks), dtype=bool)]
        res["sine_direction"][f"{tb}_cos_across_bpms"] = {
            "n_bpms": len(ks), "mean": round(float(off.mean()), 3),
            "ci95": boot_ci(off), "min": round(float(off.min()), 3)}
        print(f"[{tb}] delta cos across {len(ks)} BPMs: {off.mean():.3f}")
    # per-BPM CROSS-TIMBRE cosine (same BPM, sine vs sawlead vs piano): isolates
    # timbre-driven direction change with phase held fixed
    xt = []
    for p in pts:
        k = p["k"]
        if all(k in deltas[tb] for tb in timbres):
            for i in range(3):
                for j in range(i + 1, 3):
                    a, b = deltas[timbres[i]][k], deltas[timbres[j]][k]
                    xt.append(float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b))))
    res["sine_direction"]["cross_timbre_same_bpm_cos"] = {
        "mean": round(float(np.mean(xt)), 3), "ci95": boot_ci(xt), "n_pairs": len(xt)}
    print(f"cross-timbre same-BPM delta cos: {np.mean(xt):.3f} (v1 cross-timbre was 0.27)")

    # text plot
    lines = ["ratio(fr/16th)  bpm      CV-acc  in-acc  zdist   |bar=CV-acc"]
    for row in curve:
        if "sine" not in row:
            continue
        m = row["sine"]
        bar = "#" * int(round((m["acc_cv"] - 0.5) * 80)) if np.isfinite(m["acc_cv"]) else ""
        lines.append(f"{row['ratio']:<15.5f}{row['bpm']:<9.2f}{m['acc_cv']:<8.3f}{m['acc_in']:<8.3f}{m['zdist_jump']:<8.2f}|{bar}")
    res["sine_curve_txt"] = lines
    print("\n".join(lines))
    # trend: does detectability degrade with ratio (frames per 16th)?
    for tb in timbres:
        rs = [(row["ratio"], row[tb]["acc_cv"]) for row in curve
              if tb in row and np.isfinite(row[tb]["acc_cv"])]
        r, a = np.array([x[0] for x in rs]), np.array([x[1] for x in rs])
        res[f"trend_{tb}"] = {"corr_ratio_vs_cvacc": round(float(np.corrcoef(r, a)[0, 1]), 3),
                              "min_cvacc": round(float(a.min()), 3),
                              "min_cvacc_ratio": round(float(r[np.argmin(a)]), 5),
                              "mean_cvacc": round(float(a.mean()), 3)}
        print(f"trend[{tb}]: corr(ratio,acc)={res[f'trend_{tb}']['corr_ratio_vs_cvacc']} min={res[f'trend_{tb}']['min_cvacc']} @ratio {res[f'trend_{tb}']['min_cvacc_ratio']}")
    return res


STAGES = {"1": stage1, "2": stage2, "3": stage3, "4": stage4,
          "5": stage5, "6": stage6, "7": stage7, "8": stage8, "9": stage9}


def main(which=None):
    OUT.mkdir(parents=True, exist_ok=True)
    rp = OUT / "results_v2.json"
    results = json.load(open(rp)) if rp.exists() else {}
    for k, fn in STAGES.items():
        if which and k not in which:
            continue
        results[f"stage{k}"] = fn()
        with open(rp, "w") as f:
            json.dump(results, f, indent=1)
    print("saved", rp)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
