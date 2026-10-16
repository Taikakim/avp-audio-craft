# The Spike, the Sparse and the Sink: Anatomy of Massive Activations and Attention Sinks

- **arXiv:** 2603.05498v1 (2026-03-05, cs.AI)
- **Authors:** Shangwen Sun, Alfredo Canziani, Yann LeCun, Jiachen Zhu (NYU)
- **PDF:** `papers/arxiv-2603.05498.pdf`
- **Read by:** KUANG, 2026-10-16: main text read in full; appendices (training settings, per-model mechanism details)
  skimmed.

## What it contains

- Pre-norm LLMs (Llama 2/3, Qwen 2.5/3). **Massive activations** are injected by one or two early "step-up" blocks
  (the SwiGLU FFN as a directional quadratic amplifier along one shared trigger direction), carried by the residual
  stream, and cancelled by late "step-down" blocks. RMSNorm turns spike tokens into sparse, near-constant vectors: in
  effect implicit, input-independent parameters.
- **Attention sinks** form where those near-constant keys sit in a separable subspace; they act as a learned per-head
  gate, biasing heads toward short-range dependencies.
- **Ablations (7B from scratch, 100B tokens):** sandwich norm / QK-norm / DynamicTanh suppress the spikes without loss
  cost while sinks survive; conditional per-channel or per-head gating removes sinks almost entirely; head dimension
  drives sink formation; long-context-only training collapses sinks. The sink ratio tracks optimisation health (lr,
  beta2); weight decay 0 makes spikes much larger (12,275 vs 3,818) with no perplexity gain.
- It links massive activations to the mid-layer "compression valley" measured by Skean et al. 2025 (Layer by Layer,
  `C:\dev\private\information_flow` on the laptop).

## What it does not contain / what remains ours

- Language models only; nothing on diffusion transformers, AdaLN, FiLM or audio.

## For us

- Hypothesis (untested): a FiLM adapter is a conditional per-channel gate, the mechanism that can take over the sink
  and spike machinery. If FiLM writes mostly into the global spike channels, it would act as a global bias, i.e. a
  style change rather than local control (our FiLM style leak). Test: FiLM scale/shift on spike vs other channels,
  then disable FiLM on spike channels only and compare density range and CLAP drift (test plan section E).
- Any entropy measurement on SA3 DiT blocks must handle spike channels first, or they dominate an uncentered Gram.
