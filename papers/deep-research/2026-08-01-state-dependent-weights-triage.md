# Triage — "State-Dependent Weights and Hierarchical Vocabularies in Generative Audio" (Gemini)

> **Provenance.** Gemini run on the state-dependent-weights brief
> (`briefs/2026-08-01-state-dependent-weights-brief.md`, from Kim's reactive-weights riff),
> PDF received 2026-08-01. Triage: CONTINUITY same day.
> **Citation verification: 11/11 REAL** (strongest base of the four runs). Corrections:
> DeMa (2601.05527) is MULTIVARIATE TIME-SERIES, not audio (architecture accurate, domain
> misattributed); "slow/fast-clock" (SMDIM) and "conditionally triggers" (UniVerse-1) are
> the report's interpretive glosses; FewSound lightly conflated with its KAN sister paper
> (2503.02585). All load-bearing claims real+accurate.

## HEADLINE — the finding that connects to the LIVE treble investigation
The report's Snake-activation insight (§4.1: ReLU/Tanh/Swish cannot extrapolate periodic
functions / sustain HF carrier-phase circular trajectories) was checked against OUR model:
- **DiT generator uses SiLU/SwiGLU — NO periodic bias** (config `sinusoidal` unset,
  `ff_kwargs` empty). `transformer.py:490` = `nn.SiLU() if not sinusoidal else Sin()` —
  the periodic option EXISTS and is switched OFF. → literature-backed generation-side
  mechanism for the 2-7 kHz clarity collapse; the fix is a flag we already have.
- SAME encoder `use_snake=False`; decoder `use_snake=False` but `sinusoidal_blocks=[8]`
  (periodic activation at the last/HF-synthesis upsampling stage). Codec is reasonably
  designed for HF; the >7 kHz phase discard (measured: mag 0.93, phase-coh 0.045 on
  round-trip) is the deliberate small-latent tradeoff, not a bug.
→ **Split-fix, along the measured boundary:** >7 kHz = codec/latent ceiling →
reconstruction filter (Snake-activated postnet = the right form, per BigVGAN/DAC lineage);
2-7 kHz = DiT generation collapse → **sinusoidal-FFN adapter** (the disabled flag),
COMPLEMENTARY to E1a/E1c (reweight-to-give-gradient + periodic-bias-to-represent).
NEW EXPERIMENT registered; gated on the phase-invariance probe confirming generation-side.

## Actionables (ranked, all real+verified)
1. **Sinusoidal/Snake-FFN adapter on the DiT** (above) — the treble lever, code-supported.
2. **Diff-MoE timestep-conditioned routing** (2505.xxxx / ICML'25, real): experts by
   diffusion timestep = the "two clocks" on the noise axis (structure early, texture late).
   Real tier-2 architecture direction; dovetails with the x0/timestep (E1) work.
3. **Auxiliary-Loss-Free Balancing** (2408.15664, DeepSeek, real): aux load-balance loss is
   DETRIMENTAL (interference gradients); bias-term-outside-gradient wins. → design law for
   E2 and any MoE we build (don't add a load-balance loss).
4. **PEER / PKM / UltraMemV2** (all real): the concrete form of Kim's "weight vocabulary
   indexed by input" — million single-neuron experts / product-key memory. Tier-2 toy.
5. **SMDIM** (2507.20128, real): Mamba-FeedForward-Attention = slow-SSM + fast-diffusion
   hybrid, the "two clocks" architecture for long melody. Tier-2, connects to E3/structure.
6. **HyperSound/FewSound** (real): hypernetwork→INR(+KAN) audio; the "generators not
   samples" vocabulary. Reference.

## Assessment
Least costume, most directly actionable of the four runs. The Snake→DiT-activation finding
is the standout — an independently-prescribed fix that our own codebase already half-
implements, targeting the exact problem we're actively measuring. Diff-MoE + loss-free
balancing are real design inputs for the state-dependent-model tier-2 direction.
