# STAS — Steering Video Diffusion Transformers with Massive Activations (2603.17825)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). MBZUAI / Pinscreen (Cheng, Zheng,
Xie, Liao, Li), preprint. Video, but its **outlier-activations-are-the-control-points** thesis
directly corroborates targeting specific channels/positions for our LatCH/activation steering.*

**What it contains.** **Massive Activations (MAs)** = rare hidden-state spikes where a few feature
dims hit >50× the mean, concentrated on **fixed channels across all layers**, largely invariant to
text conditioning. In video DiTs they carry a *positional* structure: **first-latent-frame tokens**
hold the largest MAs (global temporal anchors) and **chunk-boundary tokens** show elevated MAs
(implicit boundary cues, periodicity = VAE's temporal compression). **STAS** (training-free): during
early denoising, mask-and-replace MA dimensions at first-frame + boundary tokens with a scaled
global-max reference `g=α·max|D|·sign(D)` (polarity-preserving), <0.1% overhead. Small aggregate
VBench gains (near-ceiling), **larger at cross-chunk transitions**. **Causal ablation is the strong
evidence:** steering a true MA dim (~59× peak-to-mean) works; steering non-MA (~1×) or weak-MA (~6×)
does **nothing or hurts**; zeroing MAs degrades quality; amplifying MAs on *all* tokens is harmful —
**selectivity is everything**. Best at early steps (K=20/50), where MAs are largest.

**Status vs our work — external corroboration + concrete diagnostics.** **(1) Outlier channels as
privileged control points** — STAS's core result (only genuine ~59× MA dims are steerable; ordinary
dims do nothing/hurt) is strong external support that our **LatCH feature-heads / activation-steering
should target outlier channels specifically**, with a ready diagnostic: the **peak-to-mean ratio**
identifies which dims are causal. **(2) {12,13} vs their "block 15"** — STAS treats MAs as roughly
layer-invariant and picks a mid block mainly for analysis, whereas ours is a *specific* causal band;
the port question is whether SA3's {12,13} controllability **coincides with where MA structure peaks**
— if MAs are layer-invariant in audio too, our single-band localization is a *contrast* worth
explaining (audio may localize control more than video). **(3) Positional targeting** — steer *where*
(anchor + chunk-boundary tokens), not just *what*; audio analog = VAE temporal-chunk seams or
downbeat/onset-aligned latent positions (candidate steering sites for coherence, the audio version of
their cross-chunk-consistency win — and it dovetails with the loop-collapse-at-seams theme).
**(4) `max·sign` (polarity-preserving, bounded) beats pure scaling, and uniform over-amplification
fails** — maps straight onto our **disintegration/buzz gate**: broadband over-driving is the failure
mode, selective bounded steering the safe regime. **(5) Early-timestep-only steering** = an RF
scheduling prior (structure steering most effective + least destructive at high-noise early steps).
Caveat: STAS's aggregate gains are small/near-ceiling; its causal weight is in the ablations, not the
metrics. What does NOT transfer: video-specific positional structure; audio MA structure must be
measured on SA3. What remains ours: the SA3 MA measurement, the {12,13} reconciliation, the buzz gate.
