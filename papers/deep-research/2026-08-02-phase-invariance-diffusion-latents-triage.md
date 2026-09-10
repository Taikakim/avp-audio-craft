# Triage — "Advanced Phase Modeling and Sub-Frame Invariance in Generative Audio Latents" (Gemini)

> **Provenance.** Gemini deep-research, RTF uploaded by Kim 2026-08-02, on the live
> phase-invariance / SAME-latent thread. Triage: CONTINUITY same day.
> **Verdict: HIGHEST-fidelity Gemini report we've triaged.** The SAME-architecture and
> IFGD-phase-loss sections were cross-checked NOT against the report's own citations but
> against (a) our own deep-read `papers/arxiv-2605.18613 - SAME - A Semantically-Aligned Music Autoencoder.md` and (b) the source PDF
> `stable-audio-3/SAME- ...2605.18613v1.pdf` directly. Both corroborate. Minimal costume.

## Verified against our own materials
- **SAME arch (faithful, line-by-line):** patching P=256→256× (stereo interleaved 512-d),
  TRB S=16→4096×, differential-attn/QK-norm/RoPE/DyT, SAME-L 852M (sliding-window) /
  SAME-S 108M (chunked+midpoint-shift), soft-norm bottleneck (learnable affine+running-std,
  NOT a VAE), 4-layer/768-d generative-alignment DiT (grads→encoder), chroma+ILD via single
  1×1 conv, T5Gemma contrastive triplet, relativistic GAN. All match `arxiv-2605.18613 - SAME - A Semantically-Aligned Music Autoencoder.md`.
- **IFGD phase loss confirmed in the PDF:** grep hits — `group delay`, `IFGD`×3, `K-weight`,
  `mid/side`, `multi-resolution`×6, `multi-scale STFT`, `FFT size`, `75%`. So the "decoder
  hallucinates sub-frame phase via IF+GD, multi-res STFT, K-weighting, per-channel + M/S"
  narrative is ACCURATE, not imported from APCodec/Ear-VAE.
- Primary cites [5] 2605.17991 (SA3) + [12] 2605.18613 (SAME) real, on disk. Load-bearing
  refs verified directly; ~15 secondary refs (Ear-VAE 2509.14912, APCodec 2402.10533,
  Listens-like-Mel, CVCNN 2510.09926, Torem ICCVW23, NC-CDM MICCAI25) field-consistent,
  NOT each fetched — high confidence by primary-source fidelity + prior-run base rate.

## The one analytical error (our correction back)
The section "Phase Shift Invariance" CONFLATES two symmetries:
- **Global absolute-phase rotation** (constant θ ∀ freq; preserves envelope + IF) — the
  report's actual, plausibly-TRUE claim about SAME.
- **Time-shift / translation** (a delay; MOVES the envelope) — what our sample-shift sweep
  + circular-roll `phase_invariance_probe` tested. SAME is NOT invariant (212/256 dims
  move) — and correctly so, it must encode timing.
→ **No contradiction with our probe** (different operations), but the terminology misleads.
KEY: SAME's "phase invariance" (global-phase) ≠ AFLDM/TIPS/LPS "shift equivariance"
(translation). DIFFERENT AXES — do not cross the threads.

## Actionables
1. **IFGD phase-derivative loss on the HF-repair net** (task #62 second arm). SAME's decoder
   uses IF+GD; we measured >7kHz phase-coherence 0.045 (near-random). The repair net uses
   magnitude-weighted L1 — wrong quantity for CLARITY (sharp transients = phase-coherence /
   GD→0, not magnitude). Add IF+GD term; composes with ADAA-Snake. Arguably more on-target
   for treble than the activation swap.
2. **Global-phase-rotation probe arm** (task #63). Hilbert-rotate by θ, re-encode, compare
   latent-delta vs the time-shift delta. Decisive test of the report's core claim, which we
   have never actually run. If report right: global-phase Δ << time-shift Δ.

## Corroborating, non-actionable
- **Channel-span masking / power-law ("Listens like Mel", 2–4× faster DiT):** connects to
  our measured 1/f latent (α≈−1.12). SAME paper does NOT mention span-masking → our 1/f is
  either intrinsic (music+soft-norm) or induced by the semantic losses; report doesn't
  settle it. [35] is the read if we want the mechanism.
- **CVCNN / complex-valued continuous latents → complex-plane diffusion → intrinsic group
  delay, lower compression:** same idea already in our relational-weights survey (Harmonic
  Nets, complex-steerable). Reference-level.
- Image-domain sections (phase congruency, LSR manifold-deviation, VAE fingerprints,
  Fourier Ptychography, MRI k-space) accurate but tangential general-knowledge padding.

## Follow-up report — "Audio Synthesis Artifacts and Quality Limitations" (Gemini, same day)
Companion PDF (11pp), same fidelity tier. SAME facts (MRSTFT 7-res FFT 32–2048, IFGD,
mid/side + L/R, patching 256×/TRB 16×, chroma+ILD 1×1, T5Gemma contrastive) restated and
self-consistent with the verified first report → high confidence, no re-derivation needed.
**Verdict: CONFIRMATORY, not net-new — no new actionable beyond tasks #62/#63.** Its real value:
1. **Corroborates the global-phase claim #63 will test** — states outright the ear is
   "sensitive to temporal alignment of envelopes (group delay) but relatively insensitive to
   global, uniform phase shifts." This is the classic result AND it aligns with Kim's earlier
   correction (ear DOES decode airy-region HF detail): global-phase-offset insensitivity ≠
   HF-content insensitivity. Report gets the nuance right.
2. **Manifold-deviation ↔ our covariance finding (the one genuine synthesis).** Report: HF
   crackle/spatial-smear partly = diffusion model placing latents slightly OFF-manifold,
   magnified by the deterministic decoder. Our measurement: 188/256 eigendirections lie below
   the velocity-target unit noise floor + giant degenerate tail shells → those are exactly the
   low-variance (HF/detail) directions the DiT cannot resolve → off-manifold in the HF corner.
   Our journal already has the mechanism ("contractive denoising erases off-manifold
   perturbations"). → REINFORCES the E1 x0-target rationale (x0-target restores gradient to the
   low-variance directions the velocity target swamps). No new task; E1a already on LUMI.
3. Menu of anti-aliasing fixes (FA-GAN twin-deconvolution overlap-normalization [shen24b
   INTERSPEECH'24]; BigVGAN AMP; APCodec ConvNeXt-v2+GRN; CVCNN Cardioid activation) — all
   RESAMPLING/vocoder fixes → NOT applicable to our full-resolution repair net (no transposed
   conv), consistent with the LPS assessment. Plausible but not individually citation-verified.
