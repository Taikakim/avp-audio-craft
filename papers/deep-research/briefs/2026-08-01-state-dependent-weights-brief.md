# Gemini deep-research brief — state-dependent / vocabulary weights for hierarchical audio generation

*(CONTINUITY 2026-08-01, from Kim's design intuition. Fact-dense per convention; anchored
in our measurements so answers stay grounded. Paste whole as query.)*

## The idea being explored (Kim's framing, translated)
A generative audio model whose weights are not a fixed tensor but a **conditionally
accessed vocabulary** — the input selects which units act, biology-style sparse
conditional computation as an anti-entropy mechanism. Goal: a model **reactive to its own
running state**, specifically to solve long-melody continuation, where each new note must
stay consistent with (a) every prior note AND (b) a slow-moving thematic/rhythmic template
being repeated underneath ("two clocks": slow structure + fast surface).

## Our measured context (ground truth — do not re-derive)
- Latent RF Diffusion Transformer, 256-ch audio latent @10.77 Hz, 24 blocks.
- Measured: the latent stores **carrier phase as 2-plane rotations** (sample-shift sweep:
  channels oscillate at stimulus frequency, dim-2 circular trajectories); near-degenerate
  covariance **eigenplanes carry approximate SO(2) symmetry**; 1/f (α≈−1.12) covariance
  spectrum with giant degenerate tail shells.
- Open problem: **long-range structure recall** (motif return, phrase form). A metrical-
  tree FiLM-conditioning retrofit shows a positive but small phrase-return signal.
- Constraint (Stability, reported): latents were kept SMALL deliberately, to stop them
  memorizing discrete waveform detail and to force generalization.

## Questions (literature synthesis; real citations only, gaps are valid answers)

Q1. **Conditional-computation weight vocabularies.** State of the art on input-selected
    weights for GENERATIVE / sequence models: Mixture-of-Experts (routing, granularity,
    stability), learnable key–value **memory layers** (Lample et al. product-key memory
    and successors), hypernetwork-generated weights. Which have been applied to audio or
    music generation, and with what measured effect on long-range structure vs local
    quality? Failure modes (routing collapse, load imbalance).
Q2. **Vocabularies of GENERATORS, not samples.** Dynamic/adaptive convolution (CondConv,
    dynamic convolutions, involution), learned filter/wavelet dictionaries, and codebook/
    VQ *weight* sharing. Evidence these help audio specifically? Does a learned kernel
    dictionary chosen per-input improve high-frequency/transient fidelity (our treble-
    phase question) over static conv stacks?
Q3. **Two-clocks / hierarchical state for melody.** Architectures that explicitly carry a
    SLOW structural state alongside a FAST surface stream: state-space models (Mamba/S4)
    for audio, clockwork/hierarchical RNNs, RWKV, associative-memory / retrieval over the
    model's own generated history. Which have measurably improved motif return, thematic
    consistency, or long-form musical structure — and how was that measured?
Q4. **Complex / phase-native weights.** Given a latent that encodes phase as rotation:
    what results exist for complex-valued or steerable (SO(2)/circular-harmonic) weights
    in audio generation or diffusion? Do they improve phase coherence / reduce the
    metallic-treble artifact class?
Q5. **The memorization/generalization tradeoff for larger or structured latents.** What
    is known about why larger audio latents overfit to waveform detail, and whether
    STRUCTURED capacity (parametric generators, phase planes, hierarchical codes) escapes
    that tradeoff where raw capacity does not? Any successful "large but generalizing"
    audio latent designs?
Q6. **State-dependent diffusion specifically.** MoE or conditional weights INSIDE a
    diffusion/flow transformer (as opposed to autoregressive LMs): does input- or
    timestep-conditioned weight selection exist for DiTs, and what did it buy?

## Anti-play-acting constraints
- Verifiable citations only (arXiv IDs/venues); a confirmed gap is a valuable answer.
- Separate (a) established, (b) contested, (c) synthesis. Do not restate our facts.
- Flag anything that is a known dead-end and WHY — negative literature is wanted.
