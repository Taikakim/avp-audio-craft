# Measuring the numerical precision a diffusion transformer needs to represent + LEARN a sub-dominant signal

*Draft for Kim to send to Gemini. CONTINUITY 2026-08-04. Goal: find EXISTING methods/tools (verify they're
real, rank for our case) — not invent. Grounded in our measured setup; the question is unusual enough that
standard "fp16 attention is fine" evidence may not cover it.*

## Context (our system, measured)
- **Model:** Stable Audio 3 *medium* — a 1.4 B rectified-flow **diffusion transformer (DiT)** operating in the
  latent space of a frozen **SAME** autoencoder (256-d latent @ 10.77 Hz, 4096× compression).
- **The signal we care about is SUB-DOMINANT.** We've measured that **melody** in the SAME latent is a
  **distributed ~15-dim subspace holding only ~9.3% of corpus variance** (1.6× enrichment over random);
  the latent covariance is **786× anisotropic** with **188/256 eigendirections below the unit (flow-target
  noise) floor**; participation ratio ≈ 37/256. So melody lives in low-variance directions that the training
  objective under-weights (spectral bias, τ∝1/λ, arXiv 2503.03206).
- **Precision situation in training:** with `--base_precision fp32` the master weights, gradients, optimizer,
  linears, and (explicitly-upcast) norms are fp32 — but the **attention core casts fp32→fp16** (flash-attn
  kernel; softmax is fp32-accumulated on-chip, the QK and P·V matmuls are fp16). bf16 training would also
  round weight *updates*.
- **A concrete forward handle we already own:** a **synthetic-MIDI battery** (frame-locked patterns × tempos ×
  timbres, incl. controlled single-note deviants e.g. a lone fifth-jump that's frame-detectable ≥91%),
  encoded to SAME latents. So we can measure **Δlatent per single-note change** = the forward magnitude of
  "one note" in latent space.

## The question
**What numerical precision does the DiT need to (a) REPRESENT and (b) LEARN a signal this small, and how do
we measure that — especially when the required Δ may sit below our measurement floor, in an interconnected
network where per-weight precision is ill-defined?**

Three sub-questions, likely different tools each:
1. **Forward representation.** Given Δlatent-per-note (measurable), does fp16/bf16 forward precision preserve
   it? (signal-to-quantization-noise at that magnitude + dynamic range per tensor). This we can compute; we
   want the *right* metric + any standard framing.
2. **Gradient / weight learning.** Does the gradient signal that would train the melody subspace exceed the
   bf16/fp16 **rounding noise** on the weight update? This is the crux (the melody-wall is a *training* under-
   investment problem) and it's dynamic, not a single forward.
3. **The two hard confounds:** (i) the DiT is **interconnected** — a single weight's "required precision" isn't
   well-defined; we need system/per-layer/per-tensor sensitivity, not per-scalar. (ii) **below-measurement-
   floor:** if the precision-sensitive Δ is smaller than our measurement noise, a naïve forward diff won't see
   it — we need a detection design (controlled injection / differential recoverability) that surfaces it.

## Candidate method families — verify (real? which papers/tools?) + assess for OUR case
For each: is it real + primary refs; does it target a *sub-dominant* signal (not just overall accuracy); does
it work at *system/per-layer* granularity (interconnected net); does it address *below-floor* detection; what
data/compute it needs; tractability ranking for us.
1. **Hessian/Fisher-based mixed-precision bit-allocation** — HAWQ / HAWQ-V2/V3, Q-BERT, and Fisher-information
   sensitivity: allocate bits per layer by curvature/sensitivity. Does the sensitivity metric expose a
   *direction-specific* (sub-dominant-subspace) precision need, or only per-layer-average?
2. **Signal-to-Quantization-Noise-Ratio (SQNR) per tensor** — the classic quant-sensitivity screen. Right
   framing for sub-question 1? Any variant that projects onto a *target subspace* (our melody eigenbasis)
   rather than whole-tensor?
3. **Mixed-precision *training* sensitivity** — the "which layers/ops must stay fp32" literature (AMP,
   loss-scaling, GradScaler, bf16-vs-fp16 training studies). Is there work specifically on **small-gradient /
   low-variance-direction loss under low precision** (the update-rounding question)?
4. **Gradient-noise / critical-precision** — gradient-noise-scale (McCandlish), and any work relating the
   *quantization* noise floor on the update to a *directional* gradient SNR (does bf16 rounding exceed the
   melody-direction gradient?). Ties to the spectral-bias τ∝1/λ result.
5. **Information-theoretic / rate-distortion of the representation** — effective rank, participation ratio (we
   compute these), and quantization as an added-noise channel on the low-variance directions; any tool that
   gives "bits needed to preserve the k-th eigendirection."
6. **Controlled-signal-injection / differential testing** — inject a *known* note-scale perturbation and
   measure recoverability at fp32 vs bf16 vs fp16 (forward AND after-a-training-step), to beat the
   below-measurement-floor problem. Any established protocol for this (ablation-of-precision, precision
   bisection)?
7. **Diffusion/flow-specific precision** — any precision-sensitivity work on the velocity/score field,
   especially at **low σ** where fine detail resolves (is the melody-scale detail resolved in the low-noise
   steps, and is that where precision bites)?

## What we can run immediately (so Gemini can say which is highest-value first)
- Δlatent-per-single-note from the synthetic-MIDI latents (forward signal size) vs fp16/bf16 quantization step
  → sub-question 1, cheap.
- Project the quantization noise onto our measured **melody eigenbasis** (we have the SVD) → per-direction SQNR.
- A precision-ablation A/B: `SA3_FP32_ATTN` flag (fp32 attention) vs default, T256 finetune, scored on our
  melody-recurrence metric — the crude empirical version of the whole question.

## Ask
Rank the families above by (value for settling sub-questions 1–3) × (tractability given what we already own),
name the specific tools/papers to reach for, and flag any that specifically handle **sub-dominant-signal**
precision + the **below-measurement-floor** detection problem. If the honest answer is "no established tool
targets sub-dominant-direction precision requirements," say so — that's a finding too (and points at the
injection/differential design as the DIY path).
