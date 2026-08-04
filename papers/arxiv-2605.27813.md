# Residualized Temporal Sparse Autoencoders for Interpreting Diffusion Models (2605.27813)

*Project-POV abstract, THE-FINN 2026-07-30. Yeung, Poduval, Zakeri, Zou, Imani. cs.CV
(preprint). Text-to-image (Stable Diffusion 1.5). **Abstract-level (WebFetch) — full PDF
deep-read pending.** Important honesty flag: the fetched abstract describes the residualized-
temporal-SAE method and "qualitative steering experiments on SD1.5" but does **not** itself
state the conditional-CFG-branch-only detail below — that was extracted from the paper body by
our 2026-07-30 citation audit, so it is audit-level, not abstract-confirmed.*

**What it contains.** SAEs over diffusion activation **trajectories** rather than single
timesteps. The denoising process makes each internal layer produce a *trajectory* of
activations over time; most prior SAE work analyses one timestep or merely conditions on t.
Here: collect activations across denoising time, **fit linear predictors between neighbouring
timesteps**, and represent each trajectory as an **initial activation + the residual components
not explained by those linear dynamics**; train the SAE on this **residualized** representation
so sparse latents capture structure *beyond what is linearly predictable*. Residualized decoder
directions map back into activation space, so **each latent reads as a feature trajectory over
denoising time**. Evaluated via reconstruction + ablation, spatiotemporal feature analysis, and
qualitative steering on SD1.5.

**Status vs our work — a trajectory-aware cousin of our t-conditioned view + a convention
precedent.** The residual-over-linear-dynamics framing is a more sophisticated relative of our
**per-timestep / t-conditioned probe** approach (LatCH `t_injection`; InnerControl 2507.02321):
those *condition on* t, whereas this models the *dynamics between* timesteps and keeps only the
non-linear residual — a candidate **refinement for the SAE lane** if we ever train SAEs on SA3
trajectory dumps (bolt onto existing LatCH activation dumps, per the SAE-music 2505.18186 note).
Its most-cited-by-us reason: per the citation audit it is the **only citable precedent found for
applying activation steering to the CONDITIONAL CFG branch only** (leaving the unconditional
branch untouched) — the exact convention SA3's **Phase-3 concept steering** adopted and
validated empirically (mt_dark 0.018→0.341, 19×). The deep-research brief elevated that one
implementation choice into a general principle; on our stack **the choice is now backed by our
own result rather than the literature**. What does NOT transfer: image domain (SD1.5, DDPM-style
sampler); qualitative-only steering evidence; the linear-predictor step assumes a schedule we'd
have to remap to rectified-flow time. What remains ours: the conditional-branch-only convention
(now self-backed), the RF/SAME domain, an audio SAE if built, and the buzz gate.
