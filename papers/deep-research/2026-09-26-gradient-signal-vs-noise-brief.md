# Research brief: separating gradient signal from noise in a spectral-optimizer LoRA/DoRA fine-tune of a diffusion transformer

*Written 2026-09-26 (CONTINUITY) for an external deep-research agent. Paste everything below the line.*

---

## Context

We fine-tune a 1.4 B-parameter **rectified-flow diffusion transformer** (latent audio model, bf16 base)
with a **DoRA adapter** (rank 128, weight-decomposed LoRA; magnitude vector per output row, LoRA `B`
initialised to zero). Batch size 16, ~24 s latent crops, conditioning by text (cross-attention) plus
global/timing embeddings.

Optimizer (custom, "modular"):
- **Spectral steps** on 2-D matrices: the momentum matrix is orthogonalised by a Newton–Schulz-style
  polynomial (a cubic variant, same family as Muon's NS5), so the step size is fixed by the learning
  rate and layer shape, not by the gradient's magnitude.
- **Shampoo-style whitening** on the spectral group; **NorMuon** row normalisation; **sign steps** for
  1-D parameters (DoRA magnitudes, biases); column-norm steps for embeddings.
- **Schedule-Free averaging** (deployable weights are the averaged iterate), momentum β1 = 0.9.

## What we measured

1. **Our "SNR gate" is uncalibrated.** It multiplies the step size by
   mean over elements of |EMA_β(g)| / sqrt(EMA_β(g²)), β = 0.9, EMAs zero-initialised, no bias
   correction. For zero-mean i.i.d. noise this settles at sqrt(2/π)·sqrt((1−β)/(1+β)) ≈ 0.183, not 0.
   Per-element gradient SNR in our DiT is tiny, so the gate sits at ~0.2 permanently: in effect a
   constant ×0.2 learning-rate cut. Removing only the gate made ‖lora_B‖ grow 4.4× faster over 1011
   steps with marginally lower loss.
2. **Gradient spikes are localised.** A per-tensor raw-gradient monitor (robust z-score of the log
   pre-clip norm vs a rolling median) caught 5 lone spikes in ~3800 steps, up to 42× the rolling median,
   with normal batch loss and no non-finite values. Every one sat in the **conditioning-input layers**
   (timestep/global-conditioning embedders, the input projection), in LoRA `B`. The same layer family is
   where an earlier run's DoRA magnitudes crossed zero and the run went NaN. The final weights show no
   visible mark of the spikes; with a normalised step, a spike acts through momentum, not step size.
3. **Cautious masking** (zero coordinates where update and gradient disagree in sign, rescale survivors)
   kept ~53% of coordinates, i.e. noise-driven random masking; its survivor rescale inflated the update
   norm (~+37% effective lr) and one run NaN'd. We consider it unsuitable with orthogonalised updates.

## Our current plan (please critique, don't just confirm)

- **Measure** per-tensor signal and noise with the **two-half-batch cross product**: split the batch
  into two independent micro-batches, gradients G_A and G_B; signal ≈ ⟨G_A, G_B⟩ (unbiased for
  ‖E[G]‖²), noise of the full-batch mean ≈ ¼‖G_A − G_B‖²; average over steps because single-step
  estimates are noisy and often negative. Log only, act on nothing, at first.
- **Spike guard on momentum's input**: clip each tensor's gradient to k× its own rolling median before
  it enters the momentum buffer, leaving the orthogonalised step unmasked.
- Replace the SNR gate by an explicit lower learning rate and A/B them.

## Questions (answer each separately, with sources)

1. **Established estimators of gradient signal vs noise per layer/tensor** during training: gradient
   noise scale (McCandlish et al. 2018) and successors, per-example-gradient-free estimators, variance
   of micro-batch gradients, "B_simple"/critical batch size methods. Which are unbiased, which work per
   tensor, what do they cost, and what are their known failure modes at very low SNR?
2. **Has anyone used such an estimate to control the step, the momentum input, or per-layer learning
   rates**, and did it beat a tuned constant/scheduled learning rate? We want negative results as much
   as positive ones.
3. **Spectral / orthogonalised optimizers (Muon, NS5, Shampoo, SOAP, PolarGrad, NorMuon, Dion, …) and
   noise**: how do they interact with gradient noise and single-step spikes? Any published spike
   protection designed for them (momentum-input clipping, per-tensor clipping, trust ratios, "update
   clipping" as in Adafactor, anything acting before orthogonalisation)?
4. **Diffusion-specific gradient noise**: the objective injects its own noise (random timestep t and
   noise ε per sample). Is there work on separating t/ε-induced variance from data-diversity variance,
   importance-sampling t to cut gradient variance, antithetic or paired noise draws, or
   variance-reduced diffusion training losses? Does any of it apply to fine-tuning adapters?
5. **Conditioning/embedding layers as the unstable part** of diffusion-transformer fine-tunes
   (timestep embedders, AdaLN/global-conditioning MLPs, input projections): reported instabilities,
   and the fixes used (lower lr, freezing, excluding from the adapter, normalisation, gradient clipping).
6. **LoRA / DoRA specifics**: gradient clipping or adaptive clipping with zero-initialised `B` (the AGC
   divide-by-zero trap), DoRA magnitude-vector instability under sign or normalised optimizers, and
   whether rank-128 adapters on DiTs need per-module learning rates (LoRA+, etc.).
7. **Is our plan sound?** Specifically: the ¼ factor, averaging the unbiased cross product over steps,
   whether "scale the gradient by its SNR before momentum" has any theoretical or empirical support,
   and simpler alternatives we have missed.

## Constraints and what to leave out

- Single consumer GPU (16 GB, AMD), so no method needing per-example gradients for all 16 samples
  or a second full forward/backward pass every step, unless used as a one-off diagnostic.
- We are not asking about Adam-family tuning, loss-scaling, or mixed-precision overflow; the base
  optimizer choice is fixed.
- Prefer primary sources (papers, official repos). Flag preprints vs peer-reviewed, and mark anything
  you could not verify from the source itself. Do not invent citations; say "not found" instead.

## Output format

For each question: a 3–6 sentence answer, then a list of sources as `arXiv id or URL — one line on what
it shows — how directly it applies to our setup (direct / partial / analogy)`. End with a ranked list
of the 3 most promising things for us to try, each with its expected cost and the result that would
tell us it failed.
