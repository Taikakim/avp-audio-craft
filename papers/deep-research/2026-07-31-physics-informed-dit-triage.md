# Triage — "Physics-Informed Latent Transformer" (quantum-gravity × DiT PDF)

> **Provenance.** PDF given by Kim 2026-07-31 ~00:40 ("stretch our imagination — maybe the
> best audio model should be organised by reality itself"), stored at
> `papers/deep-research/PhysicsInspired_Architectures_for_Latent_Diffusion_Transformers.pdf`
> (uploaded copy). Deep-research-style synthesis (RQM + Loop Quantum Gravity + fractal
> universe + information geometry → DiT redesign). Triage: CONTINUITY same night.
> **Companion:** F's independently-commissioned 14-agent survey
> `docs/ai-research/relational-weights-theory-survey-2026-07-31.md` (same Kim prompt, deeper
> theory pool, adversarial verdicts). The two CROSS-VALIDATE — see the unified experiment
> spec `docs/superpowers/specs/2026-07-31-reality-structured-model-experiments.md`, which
> supersedes both as the actionable record.

## Pile sort

**Decorative physics (no implementable content):**
- §2 density-matrix tokenization — quadratic per-token storage, no training story; the
  "identity = relations only" intuition is largely what self-attention already computes.
  Independently reached the same collapse verdict as F's survey convergence-8 — two
  syntheses, same warning = deprioritize with confidence.
- §5.1 spinfoam transitions — renames discrete sampler steps "transition amplitudes";
  computationally vacuous. §7 (Riemannian wave-equation "perfect recovery") and §8's
  "physically incapable of hallucination" are overclaim-grade glue.

**Real mechanisms wearing costumes (the smuggled ML):**
1. **x0-vs-velocity target parameterization** (§5.2 ← JLT, arXiv 2605.27102). VERIFIED
   REAL+ACCURATE 2026-07-31 (agent sweep): 130M DiT over frozen FLUX.2 VAE, ImageNet-256,
   FID-50K 2.50 (x0) vs 6.56 (v) matched; mechanism = velocity target covariance carries an
   isotropic +I noise floor that swamps directions with variance ≪ 1. Caveats: x-vs-v only
   (eps analytic, never run), one scale/dataset/VAE, untested in distillation/few-step where
   v historically wins. **PORT GATE PASSED BY MEASUREMENT:** SAME per-dim variance is
   deceptively flat (5.4×, min 0.44) but the covariance EIGENBASIS is 786× anisotropic —
   188/256 eigendirections below the unit floor (min λ 0.05), and the melody subspace lives
   in the suppressed region. → the x0-target arm is measurement-motivated on our stack
   (experiment E1 in the spec).
2. **Quantized/pruned attention** (§4 "spin-attention" minus Penrose): discrete attention-
   weight ladder + hard pruning = a testable anti-oversmoothing mechanism. Toy-scale only
   (E6). F's convergence-1/4 covers the same ground with a better sequencing (learn the
   algebra via PHM before imposing any).
3. **Hyperbolic/hierarchical geometry** (§3 ← HypDiff 2405.03188, real, graphs): for audio
   the honest transplant is POSITION, not the latent — music's positional structure is a
   literal tree (16th→beat→bar→phrase) that RoPE flattens to a line. This became the
   **metrical-tree PE** idea (E3/E5), escalated by F to candidate structural fix for the
   long-range structure-recall gap task #60's null left open.
4. **Fisher-Rao geodesics** (§6 ← "spacetime of diffusion" 2505.17517): tractable geodesics
   between noisy latents → principled interpolation for transitions/bridges (E4; third
   contender in the slerp-vs-SaFa bracket, #27).
5. §2.3's "shape the latent with semantic regularizers, not pure reconstruction" —
   presented as novel; it is literally SAME's own design (chroma/ILD regression +
   contrastive text alignment). The report reinvented our autoencoder.

**Citation base:** real ML papers (JLT verified; HypDiff, PAE 2605.07915, 2505.17517,
Karras 2406.02507 plausible-real, unverified except JLT) glued with Wikipedia/Scribd
physics references. Same failure-class as prior runs: real results + grand-narrative glue;
the glue is where the nonsense lives.

## Verdict
"Organised by reality itself" survives translation as **hierarchy, discreteness, learned
geometry, and phase** — four structural priors music genuinely has and flat Euclidean DiTs
lack. Everything actionable is consolidated in the experiment spec (below); this file is
the provenance record for the PDF specifically.
