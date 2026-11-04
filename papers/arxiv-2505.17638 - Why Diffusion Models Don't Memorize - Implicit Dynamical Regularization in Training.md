# Why Diffusion Models Don't Memorize: The Role of Implicit Dynamical Regularization in Training (2505.17638)

Bonnaire and Urfin (equal contribution), Biroli (LPENS, Université PSL, Paris); Mézard (Bocconi University, Milan). arXiv v2, October 28, 2025; NeurIPS 2025 (per the PDF footer).
PDF: `arxiv-2505.17638 - Why Diffusion Models Don't Memorize - Implicit Dynamical Regularization in Training.pdf` (gitignored; added locally on the desktop).
**Read:** the full PDF, including supplementary sections A–D, by a subagent for KUANG on November 4, 2026. The replica and random-matrix proofs were skimmed, not checked.

## What it contains

**Two timescales.**
- **τ_gen**, the step at which the Fréchet Inception Distance (FID) is at its minimum, does not depend on the training-set size n.
- **τ_mem**, the step at which the memorized fraction starts to rise, grows linearly with n.
- Early stopping anywhere in [τ_gen, τ_mem] gives good samples that are not copies, and this window widens linearly with n.
- Above a model-dependent size n\*(p), the network cannot memorize even with unlimited training. The paper calls this "architectural regularization."

**Width.**
- Both timescales scale as 1/W, where W is the U-Net's base channel width, not its parameter count.
- So the crossover where τ_mem = τ_gen is roughly independent of model size for W > 8.
- With SGD at W = 32, memorization curves collapse onto one another when plotted against τ/n, and start rising at about τ/n ≈ 300 steps (read off a plot).

**Metrics.**
- **Memorized fraction.** A sample counts as memorized if (distance to its nearest training image) / (distance to the second nearest) < 1/3, measured in pixel L2. The thresholds 1/2 and 1/4 give the same scaling.
- **FID:** 10 000 generated images against 10 000 test images, averaged over 5 test sets.
- **Losses:** train and test denoising loss at a fixed t = 0.01.

**Setup.**
- CelebA, 32×32 grayscale, n from 128 to 32 768, no augmentation.
- A DDPM U-Net at widths 8–64 (about 0.26–16 M parameters).
- SGD with momentum 0.95, learning rate 0.01, batch min(n, 512), no EMA, no warm-up; 2–11 M steps, DDIM sampling with 200 steps.
- **Checks:** full batch (τ_mem ∝ n still holds, so it is not about repetition); Adam (same picture, reached in far fewer steps); a 2-component Gaussian mixture (d = 8) with a toy classifier-free-guidance (CFG) check (the τ/n collapse still holds).

**Theory.**
- A random-features score model (only the readout is trained), at one fixed diffusion time, in the limit d, p, n → ∞.
- The timescales are inverse eigenvalues of a feature Gram matrix whose spectrum has two bulks:
  - an n-independent population bulk, which sets τ_gen;
  - an n-scaled bulk, which sets τ_mem ~ ψ_n/Δ_t, where train and test loss separate.
- In that model, n\* = p.
- Derived by the replica method (non-rigorous); "Theorem 3.2" is labeled informal.

## How far the evidence reaches

- **Scale and domain.** Tiny grayscale images, pixel-space nearest neighbors, training from scratch, models up to 16 M parameters.
- **Not covered:** fine-tuning, LoRA, EMA, learning-rate schedules, latent diffusion, transformers, audio.
- **Theory.** It trains at one fixed noise level, while real models train across all levels.
- **Scaling claims** rest on curves collapsing visually, not on exponents fitted with uncertainties.
- **Internal inconsistencies:**
  - the channel multipliers differ between the main text and appendix A.1;
  - one model's memorized fraction is 34.1 % in a figure caption and 47.2 % in the appendix text.

## For us

**USEFUL AS A METER, not as numbers.** Generalizing first and memorizing later is the opposite order to grokking, so "train longer and wait" is a memorization risk for our fine-tunes (see the Grokfast sidecar). None of the constants transfer: our optimizers are Adam- and Muon-like, our model is about 100x larger and much wider, and we fine-tune.

**Two metrics we can compute (inference; untested):**
1. **Train vs held-out flow-matching loss at a fixed low noise level, per checkpoint.** In the paper this gap opens before copies appear, so it is the cheap early warning. Our held-out split is song-grouped, as in the LatCH census.
2. **Nearest-neighbor ratio d₁/d₂ < 1/3** for renders against training crops, in latent space (windowed, so that shifted crops still match) and in an embedding such as CLAP or MERT.
   - Take d₂ from a **different track**, or loops and repeats inside one song will hide copies.
   - Calibrate the threshold on held-out real clips.

**Epochs.**
- If τ_mem ∝ n holds in steps at a fixed batch size, the epoch count to memorization is roughly constant across dataset sizes.
- τ_gen costs more epochs on small sets.
- Whether either applies to fine-tuning a pretrained model is untested. The base model plausibly starts past τ_gen, and adapter rank may act as the capacity limit p.

**The experiment:**
- Measure our own τ_mem on one run family at two dataset sizes (for example avp vs bigset), from the loss gap plus the nearest-neighbor ratio across its epoch checkpoints.
- If the gap never opens within 150 epochs, our runs sit in the "architectural regularization" regime, and the epoch count is not the risk.

## What stays ours

Model, data, objective and training are unchanged. What we take is the two-timescale frame and the two meters. The "n" for cropped windows (tracks or windows) is ours to settle empirically.
