#!/usr/bin/env python3
"""latent_whitening_probe.py — de-risk Track B (post-hoc latent whitening) for FREE.

The frozen-codec clarity plan (docs/clarity-recovery-plan-2026-08-02.md, Track B) proposes
whitening the SAME latent (Sigma -> I) between the frozen encoder and the DiT, then
un-whitening (exact inverse) before the frozen decoder, so the 188/256 low-variance
eigendirections that sit below the velocity-target unit-noise floor are lifted to unit
variance and no longer swamped. Before spending any GPU on a whitened-DiT run, this probe
VALIDATES THE PREMISE + THE MATH on the covariance eigenbasis we already computed
(e1_pretest/corpus_eigbasis.npz) — no GPU, no encoding, instant.

Scope (honest): this confirms (1) the diagnosis (anisotropy, 1/f slope, #below floor),
(2) that whitening eliminates the sub-floor directions, (3) that the transform is CORRECT
(whitened cov ~ I) and EXACTLY INVERTIBLE (un-whiten recovers the latent -> codec stays
frozen). It does NOT prove the DiT trains better — that needs the actual run. It de-risks
by proving the premise and the bijection hold; if any of these fail, Track B is dead before
we spend a GPU-hour.

Run: /home/kim/Projects/SAO/.venv/bin/python eval/latent_whitening_probe.py
"""
import os
import numpy as np

EIG = "/run/media/kim/Mantu/sa3_lora_runs/e1_pretest/corpus_eigbasis.npz"
NOISE_FLOOR = 1.0   # velocity target adds isotropic unit-variance noise; data-var < 1 => swamped


def load_cov():
    """Reconstruct Sigma from the stored eigenbasis (vecs, vals)."""
    d = np.load(EIG)
    vecs, vals = np.ascontiguousarray(d["vecs"]), d["vals"]
    # order desc
    order = np.argsort(vals)[::-1]
    vals = np.clip(vals[order], 1e-12, None)
    vecs = vecs[:, order]
    Sigma = (vecs * vals) @ vecs.T          # V diag(lam) V^T
    return Sigma, vecs, vals


def slope_1f(vals):
    """Fit log(lambda) ~ alpha * log(rank) — the 1/f exponent."""
    r = np.arange(1, len(vals) + 1)
    A = np.polyfit(np.log(r), np.log(vals), 1)
    return float(A[0])


def participation_ratio(vals):
    """Effective # of directions carrying the variance (1 = all in one dir, N = uniform)."""
    return float(vals.sum() ** 2 / (vals ** 2).sum())


def main():
    if not os.path.exists(EIG):
        raise SystemExit(f"missing eigbasis {EIG}")
    Sigma, V, lam = load_cov()
    N = len(lam)

    # --- (1) diagnosis: reproduce the measured pathology ---
    aniso = lam[0] / lam[-1]
    alpha = slope_1f(lam)
    below = int((lam < NOISE_FLOOR).sum())
    deep = int((lam < 0.1 * NOISE_FLOOR).sum())
    pr = participation_ratio(lam)
    print("=== (1) diagnosis (raw SAME latent covariance) ===")
    print(f"  dims               : {N}")
    print(f"  anisotropy lam0/lamN: {aniso:.1f}x")
    print(f"  1/f slope alpha    : {alpha:+.3f}")
    print(f"  below unit floor   : {below}/{N}  (velocity target can't gradient these)")
    print(f"  deeply below (<0.1): {deep}/{N}")
    print(f"  participation ratio: {pr:.1f}/{N}  (effective dims the DiT 'spends' on)")

    # per-direction SNR against the noise floor (data var / noise var)
    snr = lam / NOISE_FLOOR
    print(f"  SNR: min {snr.min():.3g}  median {np.median(snr):.3g}  max {snr.max():.3g}")

    # --- (2) whitening: does it eliminate the sub-floor directions? ---
    # eigen-whitening W = diag(lam^-1/2) V^T ; z' = W (z - mu). cov(z') = I.
    W = np.diag(lam ** -0.5) @ V.T
    Winv = V @ np.diag(lam ** 0.5)          # exact inverse: z = Winv z' + mu
    lam_white = np.ones(N)                   # by construction
    print("\n=== (2) after whitening (Sigma -> I) ===")
    print(f"  below unit floor   : {int((lam_white < NOISE_FLOOR).sum())}/{N}  (target: 0)")
    print(f"  all directions now at unit variance -> none swamped by the noise floor")
    print(f"  capacity now uniform across all {N} dirs (PR {participation_ratio(lam_white):.0f}/{N})")

    # --- (3) validate the transform is CORRECT and EXACTLY INVERTIBLE (codec stays frozen) ---
    # ANALYTIC check: W Sigma W^T must be exactly I (this is the transform's real guarantee;
    # an empirical sample-cov would only converge to I with sampling noise ~sqrt(N/nsamp)).
    cov_analytic = W @ Sigma @ W.T
    ev_a = np.linalg.eigvalsh(cov_analytic)
    off_a = np.abs(cov_analytic - np.eye(N))
    # empirical round-trip invertibility (the 'codec stays frozen' claim) on synthetic draws
    rng = np.random.default_rng(0)
    z = rng.standard_normal((20000, N)) @ (V * np.sqrt(lam)).T
    zc = z - z.mean(0)
    inv_err = np.abs((zc @ W.T) @ Winv.T - zc).max()
    print("\n=== (3) transform validation (the 'exact bijection, codec frozen' claim) ===")
    print(f"  ANALYTIC whitened cov (W Sigma W^T) eigenvalues: "
          f"[{ev_a.min():.6f}, {ev_a.max():.6f}] (target exactly 1.0)")
    print(f"  ANALYTIC max |offdiag|            : {off_a[~np.eye(N,dtype=bool)].max():.2e} (target ~0)")
    print(f"  un-whiten round-trip max err      : {inv_err:.2e} (target ~0 => decoder sees orig)")

    ok = below > 150 and abs(alpha + 1.12) < 0.4 and inv_err < 1e-6 \
        and abs(ev_a.max() - 1) < 1e-6 and abs(ev_a.min() - 1) < 1e-6
    print("\n=== VERDICT ===")
    if ok:
        print("  PREMISE + MATH HOLD: pathology reproduced, whitening removes all sub-floor")
        print("  directions, transform is isotropizing AND exactly invertible. Track B is")
        print("  worth a whitened-DiT run. (Does NOT prove the DiT trains better — that needs")
        print("  the run; this only proves the premise is real and the bijection is safe.)")
    else:
        print("  CHECK FAILED — inspect above before committing GPU to Track B.")


if __name__ == "__main__":
    main()
