# Variational Trajectory Optimization of Anisotropic Diffusion Schedules (2602.19512v1) — deep-read

Liu, Li, Cheng (Duke ECE), Feb 2026. PDF: `arxiv-2602.19512 - Variational Trajectory Optimization of
Anisotropic Diffusion Schedules.pdf`. Code github.com/lizeyu090312/anisotropic-diffusion-paper.
**Read by C 2026-08-19 (§1–8, App. A; §7 tables).** Arrived via the external analysis Kim relayed
(its "(D)"), then Kim sent the PDF.

## What it does
- Replaces the scalar noise level by a **matrix-valued, monotone PSD noise trajectory** `M_t(θ)`
  (VE/Brownian form: `x_t = x_0 + N(0, M_t)`, `dx_t = (∂_t M_t)^{1/2} dB_t`), so noise — and hence
  denoising effort — is allocated **per direction/subspace and per time**. Different `M_t` paths give
  genuinely different marginals (not a time reparametrisation), so hand-crafting is brittle → they
  LEARN θ jointly with the score net.
- **Trajectory-level score-matching loss** (eq. 11): `‖W_t(θ)(M_t^{1/2}·net(x_t,t) + ε)‖²` with matrix
  weight `W_t = (I+M_t)^{-1/2}(∂_t M_t)M_t^{-1/2}`; equals the integrated velocity mismatch between ideal
  and learned VP dynamics (Girsanov surrogate); optimal net = true score for any fixed schedule
  (Lemma 3.1). **Isotropic special case = ordinary weighted score matching (Lemma A.2): choosing g(t)
  IS choosing a per-noise-level loss weighting.**
- **Schedule gradient**: `∂_θ ∇log p_t` expressed with only x-directional derivatives of the net
  (Thm 4.1; three backward passes, independent of dim θ) + a "flow" parametrisation
  `M_t^{1/2}·net` for time-invariant scale.
- **Anisotropic Euler/Heun samplers** with steps in increments of `M_t^{1/2}` (assumes `M_t` and `∂_t M_t`
  commute — true for their projector families).
- **Schedule families (§6)**: `M_t = Σ_j g_j(t) P_j` over orthogonal projectors — DCT low/high-frequency
  split (J=2), class-conditional PCA subspaces, class-conditional scalar schedules; all matrix
  functions become subspace-wise scalings.
- **Results (Table 1, fine-tuning pretrained EDM nets, ~1.2M image passes)**: best-FID gains are small
  — CIFAR-10 1.829→1.803 (PCA aniso), AFHQv2 2.042→2.010 (DCT), FFHQ 2.374→**2.242 with the learned
  ISOTROPIC g** (the anisotropic one was worse there), ImageNet-64 2.276→2.238 — but **the low-NFE gains
  are large**: CIFAR nfe 9: 35.5→3.6–4.2; AFHQ nfe 9: 28.0→4.5; FFHQ nfe 9: 57.1→45.5. Learned schedules
  matter most in the few-step regime.

## FOR US
- **It is the learned-schedule generalisation of SFD's hand-set clock.** SFD (2512.04926) denoises a
  semantic subspace ahead of texture by a fixed Δt; this paper learns per-subspace scalar schedules
  over any orthogonal split. Two projectors for us: `P_melody` = SAME chroma-readout row space (or C's
  15-d melody-selective subspace), `P_rest` = complement → **melody denoised on its own clock**, the
  schedule-side answer to the melody wall (786× anisotropy; v-target under-recovers the suppressed
  eigendirections). Class-conditional bases ↔ prompt/genre-conditional melody subspaces (goa vs avp).
- **The isotropic lesson is the cheap one and it is (C):** Lemma A.2 says learning `g(t)` = learning a
  per-t loss weighting; FFHQ's best result came from exactly that. Our R²(t)-gated melody weighting is
  this idea restricted to one subspace, hand-set from measured R²(σ) instead of learned. Do that first.
- **Few-step is where anisotropy pays**, and SA3's production sampling IS few-step (8 typical, APT).
  A learned melody schedule could be a low-NFE quality lever, not only a training one.
- **Port cost is real:** score-based VE with matrix increments; SA3 is rectified flow with a v-head.
  The RF analogue is a per-subspace time warp `t_j(t)` (SFD does this by hand); the loss weight `W_t`
  and the anisotropic Heun step need re-deriving for RF. Not a config change; not this allocation.
- **Rank among melody attacks:** #59 subspace loss + v3 (built, A/B pending) → x0-target (E1a) →
  R²(t) gating (cheap) → SFD melody-first (structural, hand-set clock) → THIS (learn the clock).
