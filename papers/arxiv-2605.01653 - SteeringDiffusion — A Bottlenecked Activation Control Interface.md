# SteeringDiffusion — A Bottlenecked Activation Control Interface (2605.01653)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). Tulane (Wu, Summa), preprint.
An existence proof that a **single low-dimensional bottleneck** beats high-dim weight-space control
— independent external support for our LatCH/Head-B low-dim thesis and our {12,13} band.*

**What it contains.** **S-BEC** (Steering via Bottlenecked Explicit Control): the U-Net stays
**frozen**; a small `SteeringInjector` learns a **single low-dim prompt-conditioned code** `v∈ℝᵏ`
(2-layer MLP from pooled CLIP text embedding), projected to **FiLM/AdaGN affine params** that
modulate GroupNorm-normalized activations: `Δ = s·f(t)·(γ(v)⊙GN(h)+β(v))`. The **bottleneck** = all
steering flows through the one shared `v`, dim decoupled from network size. One inference-time scalar
`s∈[0,2]` traverses the content↔style trade-off; a **timestep gate `f(t)`** suppresses steering early,
ramps it late; **zero-init** projections = exact base-model equivalence at `s=0`. Results: strictly
**monotonic** control (Spearman ρ=±1.0, 0 violations); beats LoRA (+33–80% style-shift at matched
fidelity; LoRA "style-collapses" at multiplier ≥1.0); beats ControlNet with **720× fewer params**;
**k≈8–16 suffices** (k>16 no gain, p>0.3). Image, GroupNorm U-Net (SD1.5/SDXL), injects `mid_up`
blocks. Explicitly **NOT a DiT** — notes AdaLN-Zero DiTs need injector adaptation.

**Status vs our work — three independent convergences.** **(1) Bottleneck-as-mechanism confirms
our low-dim thesis:** their central causal claim is that *effective control needs a bottleneck*
(k≈8–16 sufficient, high-dim weight-space LoRA collapses) — direct external support that our LatCH
low-dim feature-heads are the right shape, and that control capacity is an **interface-design**
property, not a parameter-count one. **(2) Injection band ≈ our {12,13}:** they find control robust
in **mid-to-up (mid-network) blocks**, early/uniform injection degrades content — converging with
our finding that a mid-network band ({12,13}) causally controls concepts. **(3) FiLM/AdaGN affine
steering ≈ Head-B:** their `Δ = s·f(t)·(γ(v)⊙GN(h)+β(v))` is a prompt-conditioned affine modulation
injected forward — mechanically parallel to a forward-conditioning Head-B adapter, and the
**zero-init-for-exact-base-equivalence** trick is directly reusable for Head-B. Their **single-scalar
monotonic control surface** (Spearman ρ=±1 with zero violations) is a **ready-made rigor bar** to
test on our activation control: does scaling a Head-B/LatCH intervention give monotonic concept
strength vs fidelity? What needs adaptation / remains ours: their injection targets **GroupNorm
U-Nets** — SA3 is rectified-flow **MM-DiT with AdaLN**, so the *principle* (bottlenecked,
temporally-gated modulation off a shared low-dim code) ports but the **injection site moves to the
DiT's AdaLN conditioning path**; their diffusion-schedule timestep gate needs an RF re-derivation
(the semantic rationale "structure early, texture late" plausibly holds); and audio/SAME + the buzz
gate stay ours.
