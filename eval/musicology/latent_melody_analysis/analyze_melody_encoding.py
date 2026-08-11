#!/usr/bin/env python
"""analyze_melody_encoding.py -- Phase A of the latent-melody-encoding study.

Where and how linearly is melody encoded in the SAME latent space?
Inputs: eval/musicology/test_midis/latents/*.z0.npy (65 renders, [256,T] fp16),
ground truth from eval/musicology/test_midis/manifest.json (frame-locked grids).

Stages:
  1 pitch atlas (chromatic sweep, 73 notes x 2 frames)
  2 frame-lock autocorrelation + 143BPM drift interleaving test (pat2)
  3 fifth-jump signature (pat5)
  4 melody-vs-timbre variance decomposition + corpus variance share

Outputs: results JSON + npz intermediates in this directory. CPU only.
"""
import json
from pathlib import Path

import numpy as np
from numpy.linalg import lstsq

BASE = Path("/home/kim/Projects/SAO/eval/musicology")
LAT = BASE / "test_midis/latents"
OUT = BASE / "latent_melody_analysis"
TIMBRES = ["sawlead", "squarelead", "piano", "strings", "churchorgan"]
PATS = {
    "pat1": "pat1_const16_1pitch",
    "pat2": "pat2_const16_2pitch",
    "pat3": "pat3_const16_arp4",
    "pat4": "pat4_rise16",
    "pat5": "pat5_const8_fifthjump",
    "pat6": "pat6_pedal_b2trill",
}
FPS = 10.7666015625
BPM_LOCK = 161.4990234375


def zload(stem, nframes):
    z = np.load(LAT / f"{stem}.z0.npy").astype(np.float32)
    assert z.shape[0] == 256 and z.shape[1] >= nframes, (stem, z.shape)
    return z[:, :nframes]


def locked(pat, timbre, n=512):
    return zload(f"{PATS[pat]}_bpm161p5_32bars__{timbre}", n)


def drift(pat, timbre, n=505):
    return zload(f"{PATS[pat]}_bpm143_28bars__{timbre}", n)


def sweep(timbre, n=146):
    return zload(f"sweep_chromatic_8ths_C2toC8_bpm161p5__{timbre}", n)


def r2_linear(x, y):
    # R^2 of y ~ a*x+b == corr^2
    c = np.corrcoef(x, y)[0, 1]
    return c * c


def polyfit_r2(x, y, deg):
    p = np.polyfit(x, y, deg)
    yh = np.polyval(p, x)
    ss = np.sum((y - y.mean()) ** 2)
    return 1 - np.sum((y - yh) ** 2) / ss


def broken_octave_r2(pitch, v):
    # piecewise-linear in pitch with knots at octave boundaries (C3..C7)
    knots = [48, 60, 72, 84, 96]
    X = [np.ones_like(pitch), pitch.astype(float)]
    for k in knots:
        X.append(np.maximum(0, pitch - k).astype(float))
    X = np.stack(X, 1)
    beta, *_ = lstsq(X, v, rcond=None)
    vh = X @ beta
    ss = np.sum((v - v.mean()) ** 2)
    return 1 - np.sum((v - vh) ** 2) / ss, X.shape[1]


def ridge_loo(X, y, lam=10.0):
    # ridge with leave-one-out R^2 via hat-matrix identity; X [n,d]
    n, d = X.shape
    Xm, ym = X.mean(0), y.mean()
    Xc, yc = X - Xm, y - ym
    G = Xc.T @ Xc + lam * np.eye(d)
    W = np.linalg.solve(G, Xc.T)  # [d,n]
    H = Xc @ W  # hat
    yh = H @ yc
    h = np.diag(H)
    loo_res = (yc - yh) / (1 - h)
    r2_loo = 1 - np.sum(loo_res**2) / np.sum(yc**2)
    w = W @ yc
    return w, Xm, ym, r2_loo


def stage1():
    print("=" * 20, "STAGE 1: PITCH ATLAS (sweep)")
    pitches = np.arange(36, 109)  # 73 notes
    res = {"per_timbre": {}}
    slotmats = {}
    weightvecs = {}
    corrvecs = {}
    for tb in TIMBRES:
        z = sweep(tb)  # [256,146]
        # slot vector = 2nd frame of each 2-frame slot
        S = z[:, 1::2].T  # [73,256]
        slotmats[tb] = S
        # per-channel linear R^2 against pitch
        r2 = np.array([r2_linear(pitches, S[:, c]) for c in range(256)])
        top = np.argsort(r2)[::-1][:20]
        # linearity on top channels: linear vs quadratic vs octave-broken
        lin_forms = []
        for c in top[:10]:
            v = S[:, c]
            r2l = r2_linear(pitches, v)
            r2q = polyfit_r2(pitches, v, 2)
            r2b, kparams = broken_octave_r2(pitches, v)
            lin_forms.append({"ch": int(c), "r2_lin": round(float(r2l), 4),
                              "r2_quad": round(float(r2q), 4), "r2_octbroken": round(float(r2b), 4)})
        # multivariate decode
        w, Xm, ym, r2_loo = ridge_loo(S, pitches.astype(float))
        weightvecs[tb] = w
        corrvecs[tb] = np.array([np.corrcoef(S[:, c], pitches)[0, 1] for c in range(256)])
        # PCA of slot vectors
        Sc = S - S.mean(0)
        sv = np.linalg.svd(Sc, compute_uv=False)
        ev = sv**2 / np.sum(sv**2)
        cum = np.cumsum(ev)
        n90 = int(np.searchsorted(cum, 0.90) + 1)
        n95 = int(np.searchsorted(cum, 0.95) + 1)
        res["per_timbre"][tb] = {
            "top20_channels": [int(c) for c in top],
            "top20_r2": [round(float(r2[c]), 4) for c in top],
            "n_channels_r2_gt_0.5": int(np.sum(r2 > 0.5)),
            "n_channels_r2_gt_0.3": int(np.sum(r2 > 0.3)),
            "median_r2": round(float(np.median(r2)), 4),
            "linearity_top10": lin_forms,
            "ridge_loo_r2_decode_pitch": round(float(r2_loo), 4),
            "pca_n90": n90, "pca_n95": n95,
            "pca_top5_ev": [round(float(e), 4) for e in ev[:5]],
        }
        print(f"[{tb}] top-ch r2={r2[top[0]]:.3f} #r2>0.5={np.sum(r2>0.5)} ridgeLOO={r2_loo:.3f} pca90={n90}")

    # cross-timbre consistency
    cos_w = np.zeros((5, 5))
    cos_r = np.zeros((5, 5))
    for i, a in enumerate(TIMBRES):
        for j, b in enumerate(TIMBRES):
            wa, wb = weightvecs[a], weightvecs[b]
            cos_w[i, j] = wa @ wb / (np.linalg.norm(wa) * np.linalg.norm(wb))
            ra, rb = corrvecs[a], corrvecs[b]
            cos_r[i, j] = ra @ rb / (np.linalg.norm(ra) * np.linalg.norm(rb))
    # transfer decode: train on A, test on B
    transfer = np.zeros((5, 5))
    for i, a in enumerate(TIMBRES):
        w, Xm, ym, _ = ridge_loo(slotmats[a], pitches.astype(float))
        for j, b in enumerate(TIMBRES):
            yh = (slotmats[b] - Xm) @ w + ym
            transfer[i, j] = 1 - np.sum((pitches - yh) ** 2) / np.sum((pitches - pitches.mean()) ** 2)
    # pooled decode across timbres (train jointly, LOO by note)
    Sall = np.concatenate([slotmats[t] for t in TIMBRES], 0)
    yall = np.tile(pitches, 5).astype(float)
    _, _, _, r2_pool = ridge_loo(Sall, yall, lam=50.0)
    # leave-one-timbre-out: train pooled on 4 timbres, decode the held-out one
    loto = {}
    for hold in TIMBRES:
        tr = [t for t in TIMBRES if t != hold]
        Xtr = np.concatenate([slotmats[t] for t in tr], 0)
        ytr = np.tile(pitches, 4).astype(float)
        w, Xm, ym, _ = ridge_loo(Xtr, ytr, lam=50.0)
        yh = (slotmats[hold] - Xm) @ w + ym
        loto[hold] = round(float(1 - np.sum((pitches - yh) ** 2) / np.sum((pitches - pitches.mean()) ** 2)), 3)
    print("LOTO transfer R2:", loto)
    # consensus channel ranking across timbres (min per-timbre r2)
    r2_all = np.stack([corrvecs[t] ** 2 for t in TIMBRES])
    consensus = r2_all.min(0)
    ctop = np.argsort(consensus)[::-1][:20]
    res["cross_timbre"] = {
        "cosine_ridge_weights": np.round(cos_w, 3).tolist(),
        "cosine_perchannel_corrvecs": np.round(cos_r, 3).tolist(),
        "mean_offdiag_cos_w": round(float((cos_w.sum() - 5) / 20), 3),
        "mean_offdiag_cos_r": round(float((cos_r.sum() - 5) / 20), 3),
        "transfer_r2_train_row_test_col": np.round(transfer, 3).tolist(),
        "mean_offdiag_transfer_r2": round(float((transfer.sum() - np.trace(transfer)) / 20), 3),
        "pooled_ridge_loo_r2": round(float(r2_pool), 4),
        "leave_one_timbre_out_r2": loto,
        "mean_loto_r2": round(float(np.mean(list(loto.values()))), 3),
        "consensus_top20_channels": [int(c) for c in ctop],
        "consensus_top20_min_r2": [round(float(consensus[c]), 4) for c in ctop],
    }
    print("cross-timbre: mean cos(w)=%.3f cos(r)=%.3f transferR2=%.3f pooledLOO=%.3f" % (
        res["cross_timbre"]["mean_offdiag_cos_w"], res["cross_timbre"]["mean_offdiag_cos_r"],
        res["cross_timbre"]["mean_offdiag_transfer_r2"], r2_pool))
    np.savez(OUT / "stage1_pitch_atlas.npz",
             slot_vectors=np.stack([slotmats[t] for t in TIMBRES]),
             ridge_weights=np.stack([weightvecs[t] for t in TIMBRES]),
             corr_vecs=np.stack([corrvecs[t] for t in TIMBRES]),
             pitches=pitches, timbres=np.array(TIMBRES))

    # validation: decode pat3 arp (E3-G3-B3-E4 per frame) with sweep-trained pooled decoder
    w, Xm, ym, _ = ridge_loo(Sall, yall, lam=50.0)
    arp_truth = np.tile([52, 55, 59, 64], 128)
    val = {}
    for tb in TIMBRES:
        z = locked("pat3", tb)  # [256,512]
        yh = (z.T - Xm) @ w + ym
        # per-position mean predicted pitch
        pos_mean = [float(np.mean(yh[np.arange(512) % 4 == k])) for k in range(4)]
        r = np.corrcoef(yh, arp_truth)[0, 1]
        val[tb] = {"pred_mean_by_arp_pos_E3G3B3E4": [round(v, 2) for v in pos_mean],
                   "corr_with_truth": round(float(r), 3)}
        print(f"[arp-val {tb}] pos means {pos_mean} corr={r:.3f}")
    res["arp_validation_pat3"] = val
    return res


def acf_multivar(z):
    # z [256,T]; pooled-normalized multivariate ACF
    zc = z - z.mean(1, keepdims=True)
    T = z.shape[1]
    denom = np.sum(zc * zc)
    out = []
    for lag in range(1, 21):
        num = np.sum(zc[:, :-lag] * zc[:, lag:]) * (T / (T - lag))
        out.append(float(num / denom))
    return out


def stage2():
    print("=" * 20, "STAGE 2: FRAME-LOCK vs DRIFT")
    res = {"acf_locked": {}, "acf_drift": {}}
    for pat, period in [("pat1", 1), ("pat2", 2), ("pat3", 4)]:
        for tb in TIMBRES:
            a = acf_multivar(locked(pat, tb))
            res["acf_locked"][f"{pat}__{tb}"] = [round(v, 3) for v in a]
            b = acf_multivar(drift(pat, tb))
            res["acf_drift"][f"{pat}__{tb}"] = [round(v, 3) for v in b]
        al = np.mean([res["acf_locked"][f"{pat}__{t}"] for t in TIMBRES], 0)
        ad = np.mean([res["acf_drift"][f"{pat}__{t}"] for t in TIMBRES], 0)
        print(f"[{pat}] locked ACF lags1-8: {np.round(al[:8],3)}")
        print(f"[{pat}] drift  ACF lags1-8: {np.round(ad[:8],3)}")

    # --- interleaving test on pat2 @143 ---
    d16 = (60.0 / 143.0 / 4.0) * FPS  # 16th duration in frames = 1.12931
    interleave = {}
    for tb in TIMBRES:
        z = drift("pat2", tb)  # [256, 505]
        T = z.shape[1]
        n_notes = int(T / d16) - 1
        # coverage: fraction of frame i covered by E3 (even k) notes
        alphaE = np.zeros(T)
        for k in range(n_notes + 2):
            s, e = k * d16, (k + 1) * d16
            i0, i1 = int(np.floor(s)), int(np.ceil(e))
            for i in range(max(0, i0), min(T, i1)):
                ov = max(0.0, min(e, i + 1) - max(s, i))
                if k % 2 == 0:
                    alphaE[i] += ov
        alphaE = np.clip(alphaE, 0, 1)
        valid = np.arange(8, int(n_notes * d16) - 8)  # skip edges
        aE = alphaE[valid]
        Z = z[:, valid].T  # [n,256]
        pureE = aE > 0.95
        pureG = aE < 0.05
        bnd = (aE > 0.2) & (aE < 0.8)
        muE, muG = Z[pureE].mean(0), Z[pureG].mean(0)
        axis = muG - muE
        den = axis @ axis
        # projected G-fraction for every frame
        ghat = (Z - muE) @ axis / den
        gtrue = 1 - aE
        # boundary-frame test
        r2_bnd = r2_linear(gtrue[bnd], ghat[bnd])
        slope = np.polyfit(gtrue[bnd], ghat[bnd], 1)[0]
        # superposition residual: distance to alpha-interpolated point vs class scatter
        interp = np.outer(1 - gtrue, muE) + np.outer(gtrue, muG)
        resid = np.linalg.norm(Z - interp, axis=1)
        scatterE = np.linalg.norm(Z[pureE] - muE, axis=1).mean()
        scatterG = np.linalg.norm(Z[pureG] - muG, axis=1).mean()
        scatter = 0.5 * (scatterE + scatterG)
        # snap test: distance of boundary frames to nearest endpoint vs to interpolated
        dE = np.linalg.norm(Z[bnd] - muE, axis=1)
        dG = np.linalg.norm(Z[bnd] - muG, axis=1)
        dI = resid[bnd]
        dSeg = np.minimum(dE, dG)
        # bimodality of ghat on boundary frames: are values pushed to 0/1?
        gh_b = ghat[bnd]
        frac_middle = float(np.mean((gh_b > 0.25) & (gh_b < 0.75)))
        exp_middle = float(np.mean((gtrue[bnd] > 0.25) & (gtrue[bnd] < 0.75)))
        # discriminative-subspace variant: use only channels that separate E/G
        # (Cohen's d between pure classes), where the melody SNR is high
        sdE, sdG = Z[pureE].std(0), Z[pureG].std(0)
        pooled_sd = np.sqrt(0.5 * (sdE**2 + sdG**2)) + 1e-6
        dch = (muG - muE) / pooled_sd
        sel = np.abs(dch) > 0.5
        Zs, muEs, muGs = Z[:, sel], muE[sel], muG[sel]
        axs = muGs - muEs
        ghs = (Zs - muEs) @ axs / (axs @ axs)
        r2s = r2_linear(gtrue[bnd], ghs[bnd])
        slopes = np.polyfit(gtrue[bnd], ghs[bnd], 1)[0]
        interp_s = np.outer(1 - gtrue, muEs) + np.outer(gtrue, muGs)
        resid_s = np.linalg.norm(Zs - interp_s, axis=1)
        scat_s = 0.5 * (np.linalg.norm(Zs[pureE] - muEs, axis=1).mean()
                        + np.linalg.norm(Zs[pureG] - muGs, axis=1).mean())
        dEs = np.linalg.norm(Zs[bnd] - muEs, axis=1)
        dGs = np.linalg.norm(Zs[bnd] - muGs, axis=1)
        snap_margin = float(np.mean(resid_s[bnd] - np.minimum(dEs, dGs)))
        interleave[tb] = {
            "n_pureE": int(pureE.sum()), "n_pureG": int(pureG.sum()), "n_boundary": int(bnd.sum()),
            "r2_ghat_vs_true_boundary": round(float(r2_bnd), 3),
            "slope_ghat_vs_true": round(float(slope), 3),
            "resid_interp_boundary_mean": round(float(dI.mean()), 3),
            "dist_nearest_endpoint_boundary_mean": round(float(dSeg.mean()), 3),
            "pure_class_scatter": round(float(scatter), 3),
            "resid_over_scatter": round(float(dI.mean() / scatter), 3),
            "frac_ghat_middle": round(frac_middle, 3),
            "frac_true_middle": round(exp_middle, 3),
            "axis_norm_over_scatter": round(float(np.sqrt(den) / scatter), 3),
            "disc_subspace": {
                "n_channels_absd_gt0.5": int(sel.sum()),
                "r2_ghat_vs_true_boundary": round(float(r2s), 3),
                "slope": round(float(slopes), 3),
                "resid_over_scatter": round(float(resid_s[bnd].mean() / scat_s), 3),
                "mean_resid_interp_minus_nearest_endpoint": round(snap_margin, 3),
                "axis_norm_over_scatter": round(float(np.sqrt(axs @ axs) / scat_s), 3),
            },
        }
        print(f"[interleave {tb}] R2={r2_bnd:.3f} slope={slope:.3f} resid/scatter={dI.mean()/scatter:.2f} "
              f"d_endpoint={dSeg.mean():.2f} vs d_interp={dI.mean():.2f} mid {frac_middle:.2f}/{exp_middle:.2f}")
        ds = interleave[tb]["disc_subspace"]
        print(f"   [disc {tb}] nch={ds['n_channels_absd_gt0.5']} R2={ds['r2_ghat_vs_true_boundary']} "
              f"slope={ds['slope']} resid/scat={ds['resid_over_scatter']} snapmargin={ds['mean_resid_interp_minus_nearest_endpoint']}")
    res["interleave_pat2_143"] = interleave

    # control: same projection machinery on the LOCKED pat2 (all pure frames)
    ctl = {}
    for tb in TIMBRES:
        z = locked("pat2", tb)
        Z = z.T
        idx = np.arange(512)
        muE, muG = Z[idx % 2 == 0].mean(0), Z[idx % 2 == 1].mean(0)
        axis = muG - muE
        ghat = (Z - muE) @ axis / (axis @ axis)
        sep = float(np.mean(ghat[idx % 2 == 1]) - np.mean(ghat[idx % 2 == 0]))
        sd = float(0.5 * (ghat[idx % 2 == 0].std() + ghat[idx % 2 == 1].std()))
        ctl[tb] = {"separation": round(sep, 3), "within_sd": round(sd, 3),
                   "dprime": round(sep / sd, 2)}
    res["locked_pat2_control"] = ctl

    # temporal-FFT diagnostic of the slow oscillation seen in locked pat1 ACF
    fftdiag = {}
    for tb in TIMBRES:
        z = locked("pat1", tb)
        zc = z - z.mean(1, keepdims=True)
        F = np.abs(np.fft.rfft(zc, axis=1)) ** 2  # [256, 257]
        pow_f = F.sum(0)
        freqs = np.fft.rfftfreq(512, d=1.0 / FPS)
        lo = freqs < 3.0  # slow modulations only
        pk = int(np.argmax(pow_f[1:][lo[1:]]) + 1)
        # channel concentration of that peak
        chpow = F[:, pk]
        topch = np.argsort(chpow)[::-1][:5]
        fftdiag[tb] = {
            "peak_freq_hz": round(float(freqs[pk]), 4),
            "peak_period_frames": round(float(FPS / freqs[pk]), 2),
            "peak_frac_of_slow_power": round(float(pow_f[pk] / pow_f[1:][lo[1:]].sum()), 3),
            "top5_channels": [int(c) for c in topch],
            "top5_ch_frac": round(float(chpow[topch].sum() / chpow.sum()), 3),
        }
        print(f"[fft {tb}] slow peak {fftdiag[tb]['peak_freq_hz']} Hz "
              f"({fftdiag[tb]['peak_period_frames']} frames), top5ch frac {fftdiag[tb]['top5_ch_frac']}")
    res["pat1_slow_oscillation_fft"] = fftdiag
    return res


def stage3():
    print("=" * 20, "STAGE 3: FIFTH-JUMP (pat5)")
    res = {}
    deltas = {}
    for tb in TIMBRES:
        z = locked("pat5", tb)  # [256,512]
        Z = z.T
        phase = np.arange(512) % 16
        pedal_mask = np.isin(phase, [2, 3, 4, 5, 6, 7])  # clean E3 pedal, pre-jump
        jump_mask = np.isin(phase, [8, 9])  # B3 8th
        mu_p, sd_p = Z[pedal_mask].mean(0), Z[pedal_mask].std(0) + 1e-6
        # z-scored L2 distance per phase
        dist_by_phase = []
        for ph in range(16):
            Zi = (Z[phase == ph] - mu_p) / sd_p
            dist_by_phase.append(float(np.sqrt((Zi**2).mean(1)).mean()))
        # per-channel effect size
        mu_j = Z[jump_mask].mean(0)
        sd_j = Z[jump_mask].std(0)
        pooled = np.sqrt(0.5 * (sd_p**2 + sd_j**2)) + 1e-6
        d = (mu_j - mu_p) / pooled
        delta = mu_j - mu_p
        deltas[tb] = delta
        order = np.argsort(np.abs(d))[::-1]
        energy = np.cumsum(delta[order] ** 2) / np.sum(delta**2)
        k50 = int(np.searchsorted(energy, 0.5) + 1)
        k90 = int(np.searchsorted(energy, 0.9) + 1)
        # detectability: frame-level linear discriminant (mu diff direction)
        w = delta / (pooled**2)
        s_j = Z[jump_mask] @ w
        s_p = Z[pedal_mask] @ w
        thr = 0.5 * (s_j.mean() + s_p.mean())
        acc = 0.5 * (np.mean(s_j > thr) + np.mean(s_p < thr))
        res[tb] = {
            "zdist_by_phase": [round(v, 2) for v in dist_by_phase],
            "zdist_jump_mean": round(float(np.mean([dist_by_phase[8], dist_by_phase[9]])), 2),
            "zdist_pedal_mean": round(float(np.mean([dist_by_phase[p] for p in [2, 3, 4, 5, 6, 7]])), 2),
            "n_channels_absd_gt1": int(np.sum(np.abs(d) > 1)),
            "n_channels_absd_gt2": int(np.sum(np.abs(d) > 2)),
            "top10_channels": [int(c) for c in order[:10]],
            "top10_absd": [round(float(np.abs(d[c])), 2) for c in order[:10]],
            "k_channels_50pct_energy": k50, "k_channels_90pct_energy": k90,
            "lda_balanced_acc": round(float(acc), 4),
        }
        print(f"[{tb}] zdist jump={res[tb]['zdist_jump_mean']} pedal={res[tb]['zdist_pedal_mean']} "
              f"|d|>1:{res[tb]['n_channels_absd_gt1']} k90={k90} acc={acc:.3f}")
    cos = np.zeros((5, 5))
    for i, a in enumerate(TIMBRES):
        for j, b in enumerate(TIMBRES):
            cos[i, j] = deltas[a] @ deltas[b] / (np.linalg.norm(deltas[a]) * np.linalg.norm(deltas[b]))
    res["cross_timbre_delta_cosine"] = np.round(cos, 3).tolist()
    res["mean_offdiag_delta_cosine"] = round(float((cos.sum() - 5) / 20), 3)
    print("cross-timbre jump-direction cos:", res["mean_offdiag_delta_cosine"])
    np.savez(OUT / "stage3_fifthjump.npz", deltas=np.stack([deltas[t] for t in TIMBRES]),
             timbres=np.array(TIMBRES))
    return res


def stage4():
    print("=" * 20, "STAGE 4: MELODY vs TIMBRE VARIANCE")
    # data cube: pattern x timbre x bar x phase x channel
    X = np.zeros((6, 5, 32, 16, 256), dtype=np.float32)
    for pi, pat in enumerate(PATS):
        for ti, tb in enumerate(TIMBRES):
            z = locked(pat, tb)  # [256,512]
            X[pi, ti] = z.T.reshape(32, 16, 256)
    res = {}

    # ---- (a) frame-averaged ANOVA (bar = replicate) ----
    A = X.mean(3)  # [6,5,32,256] bar-mean
    def anova2(A):
        # A [P,T,B,C] -> SS fractions per channel
        gm = A.mean((0, 1, 2))
        pm = A.mean((1, 2)) - gm  # [P,C]
        tm = A.mean((0, 2)) - gm  # [T,C]
        cell = A.mean(2)  # [P,T,C]
        inter = cell - pm[:, None] - tm[None, :] - gm
        P, T, B, C = A.shape
        ss_p = B * T * (pm**2).sum(0)
        ss_t = B * P * (tm**2).sum(0)
        ss_i = B * (inter**2).sum((0, 1))
        ss_r = ((A - cell[:, :, None]) ** 2).sum((0, 1, 2))
        ss_tot = ss_p + ss_t + ss_i + ss_r
        return ss_p, ss_t, ss_i, ss_r, ss_tot
    ss_p, ss_t, ss_i, ss_r, ss_tot = anova2(A)
    fp, ft = ss_p / ss_tot, ss_t / ss_tot
    res["frame_averaged"] = {
        "global_frac_pattern": round(float(ss_p.sum() / ss_tot.sum()), 4),
        "global_frac_timbre": round(float(ss_t.sum() / ss_tot.sum()), 4),
        "global_frac_interaction": round(float(ss_i.sum() / ss_tot.sum()), 4),
        "global_frac_residual": round(float(ss_r.sum() / ss_tot.sum()), 4),
        "n_ch_pattern_dominant": int(np.sum((fp > ft) & (fp > 0.5))),
        "n_ch_timbre_dominant": int(np.sum((ft > fp) & (ft > 0.5))),
        "top10_pattern_ch": [int(c) for c in np.argsort(fp)[::-1][:10]],
        "top10_pattern_frac": [round(float(fp[c]), 3) for c in np.argsort(fp)[::-1][:10]],
        "top10_timbre_ch": [int(c) for c in np.argsort(ft)[::-1][:10]],
        "top10_timbre_frac": [round(float(ft[c]), 3) for c in np.argsort(ft)[::-1][:10]],
    }
    print("frame-avg fractions: pat %.3f timbre %.3f inter %.3f resid %.3f" % (
        res["frame_averaged"]["global_frac_pattern"], res["frame_averaged"]["global_frac_timbre"],
        res["frame_averaged"]["global_frac_interaction"], res["frame_averaged"]["global_frac_residual"]))

    # ---- (b) frame-sequence ANOVA: treat (pattern,phase) as the melody signal ----
    # reshape: sample = (p,t,b), feature = (phase,channel)
    B4 = X.reshape(6, 5, 32, 16 * 256)
    ss_p, ss_t, ss_i, ss_r, ss_tot = anova2(B4)
    res["frame_sequence"] = {
        "global_frac_pattern": round(float(ss_p.sum() / ss_tot.sum()), 4),
        "global_frac_timbre": round(float(ss_t.sum() / ss_tot.sum()), 4),
        "global_frac_interaction": round(float(ss_i.sum() / ss_tot.sum()), 4),
        "global_frac_residual": round(float(ss_r.sum() / ss_tot.sum()), 4),
    }
    # per-channel (aggregate phase features per channel)
    ssp_c = ss_p.reshape(16, 256).sum(0); sst_c = ss_t.reshape(16, 256).sum(0)
    ssi_c = ss_i.reshape(16, 256).sum(0); ssr_c = ss_r.reshape(16, 256).sum(0)
    tot_c = ssp_c + sst_c + ssi_c + ssr_c
    fpc, ftc = ssp_c / tot_c, sst_c / tot_c
    res["frame_sequence"]["n_ch_pattern_dominant"] = int(np.sum((fpc > ftc) & (fpc > 0.5)))
    res["frame_sequence"]["n_ch_timbre_dominant"] = int(np.sum((ftc > fpc) & (ftc > 0.5)))
    res["frame_sequence"]["top10_pattern_ch"] = [int(c) for c in np.argsort(fpc)[::-1][:10]]
    res["frame_sequence"]["top10_timbre_ch"] = [int(c) for c in np.argsort(ftc)[::-1][:10]]
    print("frame-seq fractions: pat %.3f timbre %.3f inter %.3f resid %.3f" % (
        res["frame_sequence"]["global_frac_pattern"], res["frame_sequence"]["global_frac_timbre"],
        res["frame_sequence"]["global_frac_interaction"], res["frame_sequence"]["global_frac_residual"]))

    # ---- (c) melody subspace: timbre-averaged (pattern,phase) trajectories ----
    M = X.mean((1, 2))  # [6,16,256] timbre+bar-averaged mean bar per pattern
    Mc = (M - M.mean((0, 1))).reshape(96, 256)
    sv = np.linalg.svd(Mc, compute_uv=False)
    ev = sv**2 / (sv**2).sum()
    cum = np.cumsum(ev)
    n90 = int(np.searchsorted(cum, 0.90) + 1)
    n95 = int(np.searchsorted(cum, 0.95) + 1)
    res["melody_subspace"] = {"pca_n90": n90, "pca_n95": n95,
                              "top10_ev": [round(float(e), 4) for e in ev[:10]]}
    # basis for projections
    U, S, Vt = np.linalg.svd(Mc, full_matrices=False)
    Vm = Vt[:n90]  # melody basis [n90,256]
    print(f"melody subspace: n90={n90} n95={n95}")

    # timbre subspace for contrast
    Tm = X.mean((0, 2, 3))  # [5,256]
    Tc = Tm - Tm.mean(0)
    svt = np.linalg.svd(Tc, compute_uv=False)
    evt = svt**2 / (svt**2).sum()
    res["timbre_subspace_top4_ev"] = [round(float(e), 4) for e in evt[:4]]

    # ---- (d) melody variance fraction of total (these renders) ----
    Flat = X.reshape(6, 5, 512, 256)  # frame sequence per render
    gm = Flat.mean((0, 1, 2))
    tot_var = float(((Flat - gm) ** 2).sum())
    mel_traj = Flat.mean(1)  # timbre-averaged [6,512,256]
    mel_var = float(5 * ((mel_traj - gm) ** 2).sum())  # weight by timbre count
    timb_mean = Flat.mean((0, 2))  # [5,256]
    timb_var = float(6 * 512 * ((timb_mean - gm) ** 2).sum())
    res["variance_share_renders"] = {
        "melody_frac_of_total": round(mel_var / tot_var, 4),
        "timbre_frac_of_total": round(timb_var / tot_var, 4),
    }
    print("variance share on renders: melody %.3f timbre %.3f" % (mel_var / tot_var, timb_var / tot_var))

    # ---- (e) corpus comparison: project corpus latents onto melody subspace ----
    corpus_dir = Path("/home/kim/Projects/latents_sa3")
    stats = None
    if corpus_dir.is_dir():
        files = sorted(corpus_dir.glob("*.npy"))[::250][:24]
        fr_mel, fr_rand = [], []
        rng = np.random.default_rng(0)
        Q, _ = np.linalg.qr(rng.standard_normal((256, Vm.shape[0])))
        Vr = Q.T
        tot_c_var = []
        for f in files:
            z = np.load(f).astype(np.float32)  # [256,4096] (older dumps [1,256,4096])
            if z.ndim == 3:
                z = z[0]
            zc = z - z.mean(1, keepdims=True)
            v_tot = float((zc**2).sum())
            v_mel = float(((Vm @ zc) ** 2).sum())
            v_rnd = float(((Vr @ zc) ** 2).sum())
            fr_mel.append(v_mel / v_tot)
            fr_rand.append(v_rnd / v_tot)
            tot_c_var.append(v_tot / zc.shape[1] / 256)
        stats = {
            "n_files": len(files), "k_dims": int(Vm.shape[0]),
            "corpus_frac_var_in_melody_subspace_mean": round(float(np.mean(fr_mel)), 4),
            "corpus_frac_var_in_random_subspace_mean": round(float(np.mean(fr_rand)), 4),
            "expected_frac_if_isotropic": round(Vm.shape[0] / 256, 4),
            "corpus_mean_var_per_dim": round(float(np.mean(tot_c_var)), 4),
        }
        print("corpus: melody-subspace frac %.3f vs random %.3f (k=%d)" % (
            np.mean(fr_mel), np.mean(fr_rand), Vm.shape[0]))
    res["corpus_projection"] = stats
    np.savez(OUT / "stage4_subspaces.npz", melody_basis=Vt, melody_ev=ev,
             pattern_frac_per_ch=fpc, timbre_frac_per_ch=ftc)
    return res


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    results["stage1_pitch_atlas"] = stage1()
    results["stage2_framelock_drift"] = stage2()
    results["stage3_fifthjump"] = stage3()
    results["stage4_variance"] = stage4()
    with open(OUT / "results.json", "w") as f:
        json.dump(results, f, indent=1)
    print("saved", OUT / "results.json")


if __name__ == "__main__":
    main()
