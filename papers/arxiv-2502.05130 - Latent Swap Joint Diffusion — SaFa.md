# Latent Swap Joint Diffusion — SaFa (2502.05130)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). USTC / Tsinghua / iFlytek (Dai,
Wang et al.). A training-free seamless-window scheme validated on MM-DiT — a direct alternative to
our reset-the-clock-per-window seams, with a caveat: 2D-mel + DDPM, not our 1D-SAME + RF.*

**What it contains.** **SaFa ("Swap Forward")** = training-free joint diffusion for length
extrapolation by merging overlapping sliding-window subviews — but it **replaces MultiDiffusion's
step-wise *averaging* of overlaps with binary *swap* operators**. (1) **Self-Loop Latent Swap:** a
frame-level *bidirectional* swap in adjacent-subview overlaps at every step (a binary mask, swap
interval 1) — an adaptive high-frequency-preserving filter instead of smoothing. (2)
**Reference-Guided Latent Swap:** a *unidirectional* swap during only the early `r_guide=0.3`×T
steps, aligning each subview's non-overlap region to one shared reference trajectory for global
consistency *without repetition*. Motivation: a VAE analysis shows averaging over-suppresses
high-frequency content → "spectrum aliasing" (blurry overlap transitions, monotonous tails); swap
tracks the reference high-freq curve. Results: stable 24/48/72 s audio, beats MultiDiffusion/MAD on
all metrics at **2–20× speedup** with **low overlap (0.2)**; **validated on MM-DiT (SD3.5)** for
panoramas; attention-merging (MAD) *degrades* on DiT (position-embedding repetition, self-attn
blow-up) — SaFa avoids attention/RoPE manipulation entirely. DDPM/DDIM (200 steps), **not** RF.

**Status vs our work.** SaFa's thesis is **exactly the seam mechanism SA3 lacks**: seams/aliasing at
window boundaries come from *blending*, and a hard *swap* over jointly-denoised overlaps removes
them — whereas SA3 **resets the clock per window and generates windows independently**. Porting means
running adjacent windows **concurrently with a shared per-step denoise + an overlap region** (a real
departure from our current scheme, but training-free and cheap). Two strong draws: **(a)** the
**reference-guided swap explicitly targets "consistency *without* repetition"** and quantifies a
similarity↔diversity knob (`r_guide`) — loop-collapse is pathological self-similarity, so this is a
principled early-step anchor with the empirical warning that *too much* guidance kills diversity;
**(b)** it's **MM-DiT-validated and touches no attention/RoPE** — attractive because our positional
handling is implicated in loop-collapse, and SaFa sidesteps it. **The porting risk (their own
untested cases):** SaFa's swap is defined on **2D mel latents** with a convolutional-VAE
"connectivity inheritance" + **DDPM** step-wise-differentiated-trajectory argument. SA3 is **1D SAME
(10.77 Hz) under rectified flow** — precisely the two cases the paper flags as unvalidated. Whether
RF's straight-path ODE trajectories retain the step-wise adjacent-window similarity the swap relies
on is **unverified and must be checked before assuming the operator transfers**. What remains ours:
the RF/SAME validation, and the disintegration gate.
