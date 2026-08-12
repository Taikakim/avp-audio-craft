# Elucidating the Design Space of Diffusion-Based Generative Models (2206.00364)

*EDM (Karras et al., NVIDIA, NeurIPS 2022) — the reference decomposition of diffusion into independent design axes; for us it is the canonical map of the σ-schedule + preconditioning + sampling space our interval-CFG σ-vs-t port has to translate out of. (Subagent deep-read, THE-FINN 2026-08-12.)*

## What it contains

The paper's thesis is that diffusion models are "unnecessarily convoluted" because theory-first derivations tangle components that are actually independent. It re-expresses VP (DDPM/Song), VE (NCSN) and iDDPM/DDIM in one common framework (Table 1) where every model is just a choice on four orthogonal axes, and shows each axis can be swapped without breaking the others.

The unifying object is a **denoiser** `D_θ(x;σ) = c_skip(σ)·x + c_out(σ)·F_θ(c_in(σ)·x; c_noise(σ))` (Eq. 7), trained by denoising score matching; the score is recovered as `∇_x log p(x;σ) = (D_θ(x;σ) − x)/σ²` (Eq. 3). The sampling ODE is written for arbitrary schedule σ(t) and scaling s(t) (Eq. 4), so the solver is decoupled from the schedule.

The four axes and EDM's concrete choices:

1. **Sampling (Sec. 3–4).** Deterministic sampler is **Heun 2nd-order** (Algorithm 1: Euler step + trapezoidal correction, reverting to Euler at σ=0 to avoid divide-by-zero). Time steps use a parameterized noise grid (Eq. 5): `σ_i = (σ_max^{1/ρ} + i/(N−1)·(σ_min^{1/ρ} − σ_max^{1/ρ}))^ρ`, with **ρ=7, σ_min=0.002, σ_max=80**. They advocate **σ(t)=t, s(t)=1** (same as DDIM), which makes σ and t interchangeable, straightens ODE trajectories (Fig. 3), and confines curvature to a narrow σ band. A **stochastic sampler** (Algorithm 2) adds explicit Langevin-style "churn" — noise-up by γ_i then ODE step back down — controlled by `{S_churn, S_min, S_max, S_noise}`, tuned by grid search. Stochasticity corrects earlier-step errors but oversaturates/loses detail if overused; its benefit is empirical and dataset-dependent.

2. **Preconditioning (Sec. 5).** Rather than have the network predict noise scaled by σ (which amplifies errors at large σ), they derive c-coefficients from a unit-variance-inputs/outputs first principle (Appendix B.6): **c_skip = σ_data²/(σ²+σ_data²)**, **c_out = σ·σ_data/√(σ²+σ_data²)**, **c_in = 1/√(σ²+σ_data²)**, **c_noise = ¼·ln(σ)**, with **σ_data=0.5**. Main benefit stated is *training robustness*, not FID per se — it makes the loss redesign safe.

3. **Training (Sec. 5).** Noise levels sampled as **log-normal**: `ln(σ) ~ N(P_mean=−1.2, P_std=1.2²)`, concentrating effort on the intermediate σ where learning is both possible and useful. Loss weighting **λ(σ) = (σ²+σ_data²)/(σ·σ_data)² = 1/c_out(σ)²**, which equalizes the effective per-σ loss magnitude (Eq. 8, Fig. 5a). Plus **non-leaking augmentation** (augment conditioning fed to F_θ, zeroed at inference) borrowed from GANs.

4. **Architecture** is deliberately left as a black box (they reuse DDPM++/NCSN++/ADM unchanged).

**Key results.** New SOTA CIFAR-10 FID **1.79** (class-conditional) / **1.97** (unconditional) at NFE=35; ImageNet-64 **1.36** retrained (NFE=79). Sampler-only, dropped into a pretrained ADM model, they take ImageNet-64 from FID 2.07 → **1.55** with no retraining. Deterministic sampler cuts NFE vs originals by 7.3× (VP), 300× (VE), 3.2× (DDIM). Table 2 ablates the training stack (configs A→F) showing preconditioning + loss + p_train + augmentation each contribute.

## FOR US

Our live caveat is "their interval-CFG band is in EDM σ, ours is in RF timestep t." EDM is exactly the document that pins down what that σ *is*, so the port is a reparameterization, not a mystery.

**The σ↔t mapping (load-bearing).** EDM is **variance-exploding**: the noisy sample is `x = y + n`, `n ~ N(0, σ²I)` at unit signal scale, σ sweeping [0.002, 80], high→low over sampling. Our SA3 is **rectified flow**: `x_t = (1−t)·x_0 + t·ε`, t∈[0,1], 1→0 over sampling. Cast RF into EDM's `x = s(t)·x̂` form and RF is a VE process with **scale s(t) = 1−t** and **noise level σ(t) = t/(1−t)**. So:

- **σ = t/(1−t)** and inversely **t = σ/(1+σ)**.

A CFG band expressed in EDM σ maps to an RF-t band by `t = σ/(1+σ)` (and the reverse for our own bands). The map is monotonic, so noisy↔clean ordering is preserved — a "high-σ" guidance region is a "high-t" region — but it is strongly nonlinear (σ=1 ↔ t=0.5; σ=80 ↔ t≈0.988; σ=0.002 ↔ t≈0.002). Applying an EDM σ-interval to RF t-values *without* this transform, or vice versa, silently misplaces the band. That is precisely the trap the caveat is guarding. *(Cross-ref the interval-CFG deep-read: `arxiv-2404.07724 - Applying Guidance in a Limited Interval…`.)*

**EDM-σ-specific — do NOT transfer to our RF model:**
- The Eq. 5 noise grid and its constants **ρ=7, σ_min=0.002, σ_max=80** — these are VE σ-grid points; RF has its own path and timestep spacing.
- **σ(t)=t, s(t)=1** — a choice *inside* EDM's schedule family; RF's schedule is fixed by construction (s=1−t, σ=t/(1−t)).
- **c_noise = ¼ln(σ)** conditioning and the exact **c_skip/c_out/c_in** forms — derived for additive `x=y+n`; our DiT conditions on t directly and its velocity target is a different (though analogous) parameterization. **σ_data=0.5** is a data-statistics constant that would only matter if we ever adopted EDM preconditioning on our latent (we don't).
- **P_mean=−1.2, P_std=1.2** log-normal-over-ln(σ) and the churn params `{S_churn,S_min,S_max,S_noise}` — all live in σ-space.

**Schedule-agnostic — the framing that DOES transfer:**
- The **design-axes decomposition itself** (sampling / preconditioning / training / architecture as independent modules). This is the paper's real contribution and applies to RF unchanged — it's the mental model for reasoning about where interval-CFG lives (a sampling-axis intervention) independent of training.
- The **preconditioning principle** — parameterize so network inputs/outputs stay unit-variance and σ-errors aren't amplified. RF's velocity (v-)prediction is one instance of the same idea; useful as the lens for why RF's target is "already preconditioned."
- **Loss-weighting to equalize per-noise-level magnitude** and **concentrating training on the relevant middle noise levels** — schedule-agnostic; the RF port of EDM's log-normal-over-σ is logit-normal-over-t (what SD3 already uses). This is the clean conceptual bridge: our timestep sampling *is* EDM's p_train idea, reparameterized.
- **Higher-order deterministic sampling + empirical stochasticity tuning** — Algorithm 1 is written for arbitrary σ(t)/s(t), so the solver framing survives; only the default (Euler on the linear RF path) differs. Their finding that stochasticity helps more on diverse data is a transferable empirical prior for audio.

## What stays ours

The substrate is entirely ours and unchanged by this read: **SA3 is a ~1.4B rectified-flow audio DiT**, not a VE/EDM denoiser — linear interpolant path, velocity objective, t∈[0,1], on our own audio latent (not EDM's σ_data=0.5 image statistics). We do **not** adopt EDM's noise schedule, preconditioning coefficients, or σ-grid. What we take from EDM is (a) the concrete **σ = t/(1−t) / t = σ/(1+σ)** dictionary that makes the interval-CFG σ-vs-t port a mechanical reparameterization rather than a guess, and (b) the design-axes framing for reasoning about interval-CFG as a sampling-axis knob decoupled from training. Everything below the interface — model, latent, objective, fine-tuning — remains RF/SA3.

**Honest non-transfer note:** none of EDM's headline numbers or recipes (ρ=7 grid, log-normal σ sampling, churn schedule, preconditioning c-terms) are drop-in for us; they are VE-σ artifacts. The single durable, directly-usable export is the σ↔t change of variables plus the modular framing.
