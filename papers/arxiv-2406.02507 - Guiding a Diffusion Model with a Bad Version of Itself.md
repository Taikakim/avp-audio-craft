# Guiding a Diffusion Model with a Bad Version of Itself (2406.02507)

*Karras et al. (NVIDIA/Aalto, NeurIPS 2024): guide the model with a smaller/less-trained copy of itself instead of the unconditional model — a possible drop-in for CFG that buys quality WITHOUT the recall/diversity hit we track in exp #26. (Subagent deep-read, THE-FINN 2026-08-12.)*

## What it contains

**The problem with CFG.** Classifier-free guidance extrapolates between a conditional denoiser D₁ and an unconditional denoiser D₀ via `D_w = w·D₁ + (1−w)·D₀` (Eq. 3), with w>1 over-emphasizing D₁. The paper argues CFG entangles two effects — prompt alignment and image-quality improvement — and has structural drawbacks: (1) it only works for conditional generation; (2) D₀ and D₁ are trained on *different tasks* (unconditional vs conditional), so their disagreement is not purely a quality signal. This "task discrepancy" makes the sampling trajectory overshoot, producing skewed/over-simplified compositions, exaggerated truncation, mode dropping, and over-saturated color. A 2D fractal toy (Figs. 1–2) shows CFG (w=4) eliminating outliers but collapsing diversity by over-emphasizing the class.

**The method — autoguidance.** Guide the good model D₁ with a *deliberately worse version of itself* D₀: same task, same conditioning, same data distribution, but degraded by **lower capacity and/or less training**. Intuition: a weaker copy of the same model makes broadly the *same* errors as D₁, only stronger; where the two disagree points toward better samples, and where they agree the perturbation is negligible. Crucially there is no task discrepancy — both target the same distribution — so the correction is "clean." A controlled synthetic-degradation study confirms the key condition: the degradations of D₀ and D₁ must be *compatible/of the same kind*. **Mismatched** degradations (D₁ corrupted by dropout, D₀ by input noise) give no improvement — best FID is at w=1, guidance off.

**Quantitative results** (EDM2 backbone; ImageNet-512 latent diffusion, ImageNet-64 pixels; 32 deterministic Heun steps; weight + EMA grid-searched):
- **ImageNet-512, EDM2-S:** FID **2.56 → 1.34** with an XS-sized guiding model trained for 1/16 of the main model's iterations. Beats concurrent CFG + Guidance Interval (1.68).
- **ImageNet-512, EDM2-XXL:** record FID **1.25** (guide M-sized, T/3.5).
- **FD_DINOv2:** EDM2-S **68.64 → 36.67**; EDM2-XXL **42.84 → 24.18**.
- **ImageNet-64:** new record FID **1.01**, FD_DINOv2 **31.85**.
- **Unconditional** EDM2-S (where CFG cannot be applied at all): FID **11.67 → 3.86** — headline, since autoguidance works without any conditioning.

**Ablations.** Both degradations help and are ~orthogonal; forcing shared EMA gives 1.53, reduce-training-only 1.51, reduce-capacity-only 2.13 — so the *majority* of the gain comes from under-training the guide. Best guide ≈ one size smaller + ~1/16 training; results fairly insensitive to guidance weight but sensitive to EMA length. Deriving the guide post-hoc (e.g. quantization) did **not** work — it must independently exhibit the same degradations. Extra training cost is modest: **+3.6%** for the S/XS pair.

**Diversity angle (central for us).** Where CFG concentrates onto a limited set of "canonical" images, autoguidance concentrates onto high-probability regions *without dropping branches of the distribution* (Fig. 1e); the lower FID is explicitly attributed to **better coverage of the training data**. On DeepFloyd IF it produces a wider gamut than CFG. The discussion notes autoguidance should be free of the high-noise failure that motivates noise-dependent CFG schedules (interval guidance), because both models target the same distribution at every σ. They compared only against the interval method and did **not** find combining the two beneficial.

**Stated limitation.** You must train a *separate* guiding model. An early snapshot of a smaller model is easy in principle but not available for large-scale generators trained in successive stages where the data changes mid-training — that shift can violate the "same distribution" assumption.

## FOR US

- **Direct alternative to our CFG axis.** The cleanest published case that guidance's quality gain can be decoupled from its diversity loss. Our interval-CFG A/B (exp #26) tries to *limit CFG's damage* by restricting it to a middle band; autoguidance instead attacks the root cause (task discrepancy) and claims to keep recall. These are the two live strategies for the same problem — treat as competing arms, not one experiment. *(Cross-ref `arxiv-2404.07724 - Applying Guidance in a Limited Interval…`.)*
- **Usable on SA3? Principle transfers; mechanism is parameterization-agnostic.** Autoguidance operates on the denoiser/score *difference* between a strong and a weak model — nothing EDM-specific. RF velocity is an affine reparameterization of the same score, so `v_w = w·v₁ + (1−w)·v₀` with a weaker v₀ is the natural analogue. The barrier is **artifacts**: you need a genuine "bad version" of SA3 — smaller and/or under-trained on the *same latent, conditioning, data*. Cheapest decisive test (lightweight-first): we likely already have early/under-trained SA3 fine-tune checkpoints or a smaller ablation model — take one, run `v_w = v_full + (w−1)(v_full − v_weak)`, A/B vs CFG at matched quality, check whether diversity/recall holds. No new training if a suitable weak checkpoint exists.
- **The "same degradation" law is the load-bearing caveat for us.** Mismatched corruptions give zero benefit. For SA3 the weak guide must be *same architecture/recipe, just smaller or earlier* — not a differently-conditioned model, different-data checkpoint, or quantized version (quantization explicitly failed). Our fine-tuning complicates this: if the weak guide is a base-model checkpoint but D₁ is our controllable-music fine-tune, their distributions differ — exactly the mismatch that kills the method. **Safest = a weak checkpoint from *our own* fine-tuning run.**
- **Diversity-vs-quality is the whole reason to care.** Our stated concern is CFG's mode-drop / recall loss. Autoguidance's headline is "quality without the diversity loss," grounded in FID-as-coverage. If it holds on audio, it lets us push guidance strength for perceptual quality without the timbral/structural collapse CFG causes — what interval-CFG only partially mitigates.
- **Complements, doesn't obviously stack.** The authors did not find autoguidance + interval guidance jointly beneficial → likely an *either/or* against exp #26, not an add-on. If autoguidance wins, it also removes the need to tune a noise band.

**Honest non-transfer / risks:**
- All evidence is **EDM (VE, σ-parameterized, Heun) and images.** Zero audio, zero RF, zero music. RF's straighter trajectories may change how a weak guide misbehaves; the "same distribution at every noise level" argument should still hold under RF but is untested.
- Requires an extra model + a guidance-weight (and EDM: EMA-length) grid search; we have no post-hoc EMA-length knob, so their cheapest-tuning trick doesn't directly carry.
- The distribution-shift limitation bites our fine-tuning workflow harder than their from-scratch setup — the most likely reason a naive port fails.

## What stays ours

- **Our interval-CFG A/B (exp #26)** remains the incumbent to beat; autoguidance is a challenger arm, not a replacement for that data.
- Any **SA3-RF audio result** — whether autoguidance preserves musical diversity, at what weight, with which weak checkpoint — is entirely ours to measure. The paper offers no audio, no RF, no music-diversity numbers.
- Our **CFG mode-drop / diversity(recall) characterization on audio latents** stays ours; the paper's coverage story is image-FID-based.

*(Confidence: numbers read from Table 1/results text; method/ablation logic direct from the paper. The RF-transfer reasoning is the reader's inference, flagged as such.)*
