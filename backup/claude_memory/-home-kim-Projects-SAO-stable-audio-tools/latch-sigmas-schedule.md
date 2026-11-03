---
name: latch-sigmas-schedule
description: "KEY — sigma trajectories, the s_t time-weighting, where LatCH guidance actually has power, and why the window must be set per-sampler"
metadata: 
  node_type: memory
  type: project
  originSessionId: ccd33273-2ad9-4e1a-a571-5a74da061b46
---

This is the hard-won analysis behind why LatCH guidance was inaudible and how to make it work. Tool to regenerate the numbers: `scripts/latch_trajectory_probe.py` (CPU-only, dumps σ/α/s_t per objective).

## How the guidance sampler schedules noise
`sample_euler_latch_guided` builds its own schedule (matching `sample_rf`):
- **rectified_flow (Small):** `t = sigmoid(-linspace(logsnr_max, 2, steps+1))`, then `t[0]=sigma_max(≈1)`, `t[-1]=0`. So **`t` IS σ**, and `alpha = 1 − t`. The sigmoid is *flat near 1* early: at step 10/50, σ≈0.99 (α≈0.01), NOT a linear 0.8.
- **v-objective:** `t = linspace(sigma_max,0)`, `alpha,sigma = cos(πt/2), sin(πt/2)`.

## The s_t weighting kills early steps
Per-step guidance strength is scaled by **`s_t = alpha / Σalpha`**, so `rho_t = rho·s_t`, `mu_t = mu·s_t`. At high-noise steps (α≈0), `s_t ≈ 1e-4` → guidance ≈ 0.

**Where guidance power lives (cumulative s_t), 50 steps:**
- RF (Small): ~0.5% of total power in the first 20% of steps (the **dead zone**); **90% of power is in steps ~48%–98%** (back half, low σ / high α).
- v (no dist_shift): power spread ~20%–96%.
- v + dist_shift: ~24%–96%.

**Consequence:** the SAME `start_pct`/`end_pct` (which are *step-index* fractions in the code) mean totally different things per objective/sampler. The default "first 20% of steps" lands in the RF dead zone → near-zero guidance regardless of head/target/weight (this is the original "every selection sounds identical" bug). Guidance belongs in the **back half / high-α / low-σ** region.

## Operating points (empirical, RF/Small)
- Window `[0.5,1.0]` is most potent; `[0.8,1.0]` gentler. Put the window in the back half.
- Gain `rho=mu`: the paper's **0.03 is essentially inaudible here**; need ~1 (subtle) → 3 (clear) → 10 ("interesting madness"). No signal disintegration observed up to gain 10.
- KNOWN LIMITATION: window is still step-index based, not σ-relative — so it won't transfer cleanly between RF and v models. A σ-relative window is the proper fix.

## Timestep correctness (now fixed)
- **Variance guidance** must query the head at `t_curr` (the latent's actual noise level), because the head was trained with `t` = the schedule time of the noised latent. A linear step fraction is grossly wrong for the nonlinear RF sigmoid.
- **Mean guidance** queries the head at `t=0` (the clean Tweedie estimate `z_{0|t}`) — schedule-agnostic at the clean end, so correct for both RF and v.

See [[latch-overview]], [[latch-paper]].
