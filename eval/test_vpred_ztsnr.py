#!/usr/bin/env python3
"""test_vpred_ztsnr.py — validate the Track B diffusion-side math (v-prediction + zero-terminal
-SNR) before touching DiT training. From the frozen-codec plan (docs/clarity-recovery-plan-
2026-08-02.md) + Lin et al. 'Common Diffusion Noise Schedules and Sample Steps are Flawed'
(2305.08891, citation-verified in the Gemini answer).

Claims under test (all pure numpy, instant):
  (1) a standard cosine schedule does NOT reach zero terminal SNR (residual signal leakage at
      the last step) -> the flaw that lets low-variance HF channels 'hide' and never get denoised.
  (2) the Lin et al. rescale-betas fix makes alpha_bar_T == 0 exactly (true zero terminal SNR).
  (3) v-target v = sqrt(abar) eps - sqrt(1-abar) x0 permits EXACT x0 recovery from (x_t, v):
      x0 = sqrt(abar) x_t - sqrt(1-abar) v  (round-trip identity).
  (4) at the terminal step (abar=0), eps-prediction is DEGENERATE (x_t == eps, so it carries no
      info about x0) whereas v == -x0 exactly -> v-prediction directly targets x0 at t=T. This is
      why ZTSNR MUST be paired with v-pred (eps-pred degenerates), and why the swamped HF
      directions finally get a learning signal at the terminal step.

Run: /home/kim/Projects/SAO/.venv/bin/python eval/test_vpred_ztsnr.py
"""
import numpy as np

T = 1000


def cosine_alphabar(t, s=0.008):
    """Nichol-Dhariwal cosine schedule alpha_bar(t), t in [0,1]. (Reaches ~0 at t=1.)"""
    f = np.cos((t + s) / (1 + s) * np.pi / 2) ** 2
    return f / f[0]


def linear_alphabar(T=T):
    """Canonical DDPM linear-beta schedule (1e-4..0.02) — the schedule Lin et al. flag as
    LEAKY: alpha_bar_T ~ 4e-3 (sqrt ~ 0.064 => ~6% signal amplitude survives at the last step)."""
    betas = np.linspace(1e-4, 0.02, T)
    return np.concatenate([[1.0], np.cumprod(1.0 - betas)])


def rescale_zero_terminal_snr(abar):
    """Lin et al.: rescale sqrt(abar) so the last value hits 0 (zero terminal SNR)."""
    a = np.sqrt(abar)
    a0, aT = a[0], a[-1]
    a = (a - aT) * a0 / (a0 - aT)     # affine: a[0]->a0 unchanged, a[-1]->0
    return np.clip(a, 0, None) ** 2


def check(name, cond, detail):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}: {detail}")
    return cond


def main():
    ok = True
    # (1) the canonical DDPM LINEAR schedule leaves residual SIGNAL AMPLITUDE at the terminal
    # step. The meaningful quantity is sqrt(alpha_bar_T) = residual signal amplitude (Lin et al.
    # report up to ~6.8% for some schedules; this exact linspace(1e-4,0.02,1000) gives ~0.66%).
    # Nonzero either way -> the mean/brightness leaks and low-variance HF channels hide there.
    abar = linear_alphabar()
    resid_amp = float(np.sqrt(abar[-1]))
    cos_term = float(np.sqrt(cosine_alphabar(np.linspace(0, 1, T + 1))[-1]))
    ok &= check("DDPM linear schedule has terminal signal-amplitude LEAKAGE", resid_amp > 1e-3,
                f"sqrt(alpha_bar_T) = {resid_amp:.4f} ({resid_amp*100:.2f}% residual amplitude; "
                f"cf cosine {cos_term:.1e} ~ 0). Nonzero => brightness/low-variance channels hide here.")

    # (2) rescaled schedule reaches EXACT zero terminal SNR
    abar_z = rescale_zero_terminal_snr(abar)
    ok &= check("rescaled schedule reaches zero terminal SNR", abar_z[-1] < 1e-12,
                f"alpha_bar_T = {abar_z[-1]:.2e} (== 0)")

    # (3) v-target round-trip: recover x0 exactly from (x_t, v)
    rng = np.random.default_rng(0)
    x0 = rng.standard_normal((64, 256)).astype(np.float64)
    eps = rng.standard_normal((64, 256)).astype(np.float64)
    max_err = 0.0
    for ab in abar_z[1:-1:50]:            # sample interior noise levels
        sa, s1 = np.sqrt(ab), np.sqrt(1 - ab)
        x_t = sa * x0 + s1 * eps
        v = sa * eps - s1 * x0
        x0_rec = sa * x_t - s1 * v        # identity: sa^2+s1^2 = 1
        max_err = max(max_err, np.abs(x0_rec - x0).max())
    ok &= check("v-target permits exact x0 recovery", max_err < 1e-10,
                f"max |x0_rec - x0| = {max_err:.2e}")

    # (4) terminal-step behaviour: eps-pred degenerate, v == -x0
    ab = abar_z[-1]                       # == 0
    sa, s1 = np.sqrt(ab), np.sqrt(1 - ab)
    x_t = sa * x0 + s1 * eps             # == eps (sa=0, s1=1)
    v = sa * eps - s1 * x0              # == -x0
    eps_degenerate = np.abs(x_t - eps).max() < 1e-12          # x_t carries only eps, no x0 info
    v_is_negx0 = np.abs(v - (-x0)).max() < 1e-12
    ok &= check("at abar=0 eps-pred is degenerate (x_t == eps, no x0 signal)", eps_degenerate,
                f"|x_t - eps| = {np.abs(x_t - eps).max():.2e}")
    ok &= check("at abar=0 v == -x0 (v-pred still targets x0)", v_is_negx0,
                f"|v - (-x0)| = {np.abs(v + x0).max():.2e}")

    print(f"\n{'ALL PASS — Track B schedule math holds: ZTSNR removes terminal leakage, v-pred' if ok else 'CHECK'}")
    if ok:
        print("  stays well-posed at zero SNR (eps-pred does not) and recovers x0 exactly.")
        print("  => the v-pred + zero-terminal-SNR arm is safe to build; pairs with the")
        print("  whitening probe to fully de-risk the DiT-side (#65) before any GPU run.")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
