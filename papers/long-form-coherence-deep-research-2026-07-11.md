# Long-form coherence on a fixed-window DiT — Gemini Deep Research triage (2026-07-11)

Kim commissioned a Deep Research run on **overcoming loop attractors / RMS collapse /
temporal drift when extending a fixed-window flow-matching DiT beyond its native context**
(our exact SA3-medium problem: 24-block DiT, RF objective, SAME 10.77 Hz, T=4096 ≈ 380 s).
This is the triage — what's real, what maps to OUR code, what to test first. — W

> **Raw reports** (formatted, verbatim, with reconstructed tables + reference lists):
> `deep-research/2026-07-11-long-form-coherence.md` and the companion activation-steering
> report `deep-research/2026-07-11-activation-steering-dit-audio.md`. **PDFs of the
> load-bearing papers are in `papers/`** (LoL 2601.16914, SaFa 2502.05130, InfiniteAudio
> 2506.03020, DiffRhythm 2 2510.22950, UltraViCo 2511.20123, SongBloom 2506.07634,
> LMDM 2605.22717, + the activation-steering set: TADA, AxBench, SHIFT, STAS, TC-LoRA,
> SteeringDiffusion, UniSteer, NA-RFM, Gram-Schmidt disentanglement).

## Grounding checks (done, not assumed)
- **SA3 DiT uses RoPE.** `stable_audio_3/models/transformer.py:258 RotaryEmbedding`,
  base θ=10000, NTK-aware scaling. → **Multi-head RoPE jitter is directly applicable, no retrain.**
- **Both of Kim's observed failure paths have code:**
  - `inference/fifo_infinite.py` — overlapping crossfaded chunks → **RMS collapse → hiss/silence**.
  - `inference/longform.py` — "bounded FIFO" sliding-window inpaint-continuation → **loop attractor**.
- **Citations verified 6/6 on arXiv** (incl. future-dated LoL 2601.16914 and UltraViCo
  2511.20123 — real given today's date). SaFa (2502.05130) and LMDM (2605.22717) PDFs are
  already in `papers/`. This run is unusually well-sourced for Deep Research.
- **Caveat:** the commercial-architecture section (Suno/Udio AR-vs-diffusion, "spectral
  fingerprints") is Reddit/blog/marketing-sourced — ignore as evidence. The mechanism
  papers are the real content.

## Mechanism → our failure mode → our fix

| Kim observed | Report mechanism | Paper | Our code to touch |
|---|---|---|---|
| Loop attractor (windowed regen) | **RoPE sink-collapse**: RoPE periodicity makes distant frames alias onto the clamped prefix's positions; multi-head phase-concentration → all heads copy the prefix | LoL 2601.16914 | `transformer.py` RotaryEmbedding |
| Loop attractor (secondary) | **Attention dispersion**: OOD tokens past T dilute attention into periodic harmonics → looping | UltraViCo 2511.20123 | attention logits (inference hook) |
| RMS collapse → hiss | **Step-wise latent averaging** in overlaps suppresses HF variance → energy bleeds out over windows | SaFa 2502.05130 | `fifo_infinite.py` overlap merge |
| Noise-ducking hits a ceiling (more noise = static, not novelty) | Symptom-patching; model was never trained to recover from AR drift | LMDM/ARC-Forcing 2605.22717 | (training) |
| Prompt-arc **works** | Conditioning richness = the dominant lever; a static prompt lets the model default to its self-similarity prior | SCA/Presto, Incantation, SongBloom | cross-attn / conditioning |

## The ladder — cheapest-now → train-later

**Tier 0 — inference-time, no retrain, days:**
1. **Multi-head RoPE jitter** (LoL). Per-head base-freq perturbation `θ_h = θ·(1+ε_h)`; breaks
   the inter-head phase synchronization that causes sink-collapse. ~10-line change in
   `RotaryEmbedding`, testable on `longform.py` directly. **Highest-value single experiment.**
2. **Mask text cross-attn away from committed history** (Incantation). In a sliding window with
   clamped context, the new prompt must attend ONLY to noisy target frames — never the clamped
   prefix, or it echoes the past and loops. Precise fix for "prompt-arc still sometimes echoes."
3. **Latent SWAP not average** (SaFa self-loop swap) in `fifo_infinite.py` overlaps — inject HF
   variance from the advanced window into the lagging one; preserves RMS, kills the hiss decay.
4. **Attention decay for out-of-window tokens** (UltraViCo) — plug-and-play concentration.
5. **Anchor QKV sharing** (InfiniteAudio 2506.03020) — persistent style/timbre anchor, O(1) memory.

**Tier 1 — formalize the prompt arc (C's hand-written arc → principled):**
6. **Segmented Cross-Attention** (Presto SCA) — auto-generate structural sub-prompts (LLM),
   map each to a temporal latent segment. SCA claims parameter-free. This is the automation of
   what C is doing by hand in breathing/a2a.

**Tier 2 — training-objective redesign, LUMI-scale (the "correct" native answers):**
7. **Block Flow Matching** (DiffRhythm 2, 2510.22950) — semi-AR block-causal mask, EOP padding,
   stochastic block REPA loss. Native long-form on a flow model.
8. **LMDM block-causal KV cache + ARC-Forcing** (2605.22717) — eliminates noise-ducking entirely;
   streaming, constant memory, adversarial post-training on multi-block rollouts. Biggest lift,
   best endgame for an interactive/streaming riffer.

## Recommendation — two experiments first
Both this-week, both on current SA3-medium, both no-retrain, each a cheap test of one central
mechanism claim against the exact failure C is fighting:
- **(a) RoPE jitter on `longform.py`** → does it break the loop attractor?
- **(b) Incantation mask (text cross-attn ⊥ clamped history)** → does the prompt-arc stop echoing?
If they work: a real result for GPU-hours, not GPU-days. If not: mechanism falsified on our stack
before the LUMI-scale Tier-2 spend. Connects to: C's breathing/a2a prompt-arc, F's melody-similarity
survey, the windowed-descriptor conditioning work.
