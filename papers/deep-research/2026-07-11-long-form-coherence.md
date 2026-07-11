# Overcoming Degenerate Repetition and Context Collapse in Long-Form Continuous Audio Diffusion

> **Provenance.** Gemini Deep Research report commissioned by Kim, received 2026-07-11.
> Formatted and stored verbatim (structure cleaned, table reconstructed, references
> renumbered) by WINTERMUTE. Raw synthesis — **not** a fleet position.
> **Citation check:** load-bearing arXiv IDs verified 6/6 (SaFa 2502.05130, InfiniteAudio
> 2506.03020, DiffRhythm 2 2510.22950, LoL 2601.16914, UltraViCo 2511.20123,
> SongBloom 2506.07634). Some inline LaTeX (the RoPE jitter formula, Block Flow Matching
> velocity/loss, EOP constant vector) was **stripped in the source paste** and is marked
> `[formula lost in paste]`.
> **My triage of this report** (what maps to our SA3-medium code + the two experiments to run
> first) lives in `../long-form-coherence-deep-research-2026-07-11.md`. Grounding facts I
> verified against our repo: SA3 DiT uses RoPE (`transformer.py:258`); both failure paths have
> code (`fifo_infinite.py`, `longform.py`). Companion report:
> `2026-07-11-activation-steering-dit-audio.md`.

---

## Introduction and Problem Definition

Generating long-form, structurally coherent audio with fixed-window diffusion models and flow-matching objectives is a major architectural challenge. On a medium-scale Diffusion Transformer (DiT) with a rectified-flow objective in a highly compressed latent space (e.g. a 256-dim space via a semantic-acoustic encoder such as SAME at ~10.77 Hz), the native context window limits sequence length: ~4096 tokens ≈ 380 s of audio. Extending beyond the native training window via inference-time heuristics precipitates a predictable cluster of failure modes.

Continuous extension (FIFO frame staggering, sliding windows of partially denoised frames) routinely yields **temporal drift, tempo locking, and RMS energy collapse** decaying into hiss or silence. Windowed re-generation (clamp the previous window's tail as context, regenerate the remainder) avoids RMS collapse but introduces the **"loop attractor"** — degenerate infinite repetition of a short phrase. Noise-schedule ducking disrupts loops temporarily but hits a ceiling where more noise yields static, not novel material. Conversely, rich time-varying conditioning (a multi-section **"prompt arc"**) sustains structural progression — suggesting **conditioning richness and structural planning are the dominant levers** for long-form coherence.

This report investigates these failure modes and synthesizes SOTA mitigations from commercial architectures (Suno, Udio), advanced flow-matching (Block Flow Matching), streaming diffusion (Live Music Diffusion Models), and cross-modal attention conditioning from audio and long-video diffusion.

## Architectural Paradigms of Commercial Systems

> ⚠️ **Formatter note:** this section is sourced largely from Reddit/blog/marketing, not
> primary literature — treat as background, not evidence. The mechanism sections below are the
> substance.

### Autoregressive Planning and Structural Tokens

Systems like **Suno** historically relied on LLM-optimized architectures: a highly optimized Autoregressive Transformer paired with a discrete Neural Audio Codec (à la EnCodec / SoundStream), performing global compositional planning. The key anti-repetition mechanism is conditioning-data design: textual meta-tags (`[Verse]`, `[Chorus]`, `[Bridge]`, `[Guitar Solo]`) are trained as **structural tokens** that act as steering vectors, shifting the transformer's attention and forcing changes in harmonic density, vocal presence, and energy. Concurrent computation over long sequences yields macro-level temporal maps; the LLM context window resists infinite looping so long as the prompt sequence dictates continuous progression. By v4/v5, Suno combined AR structural planning with **diffusion-based upscaling** for hyper-realism (characteristic 32 kHz artifact + high-frequency "digital haze"). Open-weights **YuE** similarly uses LLaMA-based architectures with track-decoupled next-token prediction and a "lyrics-chain-of-thought" for 5-minute coherence without diffusion in the core.

### Diffusion-Enhanced Transformers and Chunking

**Udio** and similar rely on diffusion + masked-LM frameworks, refining noise into audio in fixed-length windows in a continuous compressed latent space. Long-form generation uses **chunking** — linking blocks modularly (spectral analysis shows periodic patterns aligned to the fixed attention window). They avoid loop attractors via parameter count, curated training distributions, and aggressive text conditioning that forcefully guides each chunk's trajectory rather than relying solely on the previous window's tail. Inpainting and style-reference features give section-by-section control.

### Core Generative Modality Comparison

| Architectural feature | Autoregressive audio (Suno, YuE) | Diffusion transformers (Udio, Stable Audio) |
|---|---|---|
| Data representation | Discrete neural-codec tokens (VQ-VAE/RVQ) | Continuous latent representations (VAE) |
| Generation paradigm | Next-token prediction (causal) | Iterative denoising / flow matching (bidirectional) |
| Structural coherence | Native via long context + CoT | Requires chunking, sliding windows, or block flow |
| Primary failure mode | Token repetition, loss of HF fidelity | Loop attractors, RMS collapse, temporal drift |
| Steering mechanism | Structural text tokens (`[Chorus]`), lyrics | Cross-attention over time, inpainting |
| Spectral fingerprint | 32 kHz upsampling artifacts, HF haze | Periodic patterns matching attention windows |

Takeaway: AR models suit open-ended continuation causally, but the true enabler of long-form coherence is **conditioning richness** — an AR model without structural tokens still degenerates into repetition, like a text LLM at bad temperature.

## The Pathology of Repetition: Loop Attractors and Context Collapse

Two theoretical frameworks characterize the loop attractor under sliding-window inpaint-continuation.

### RoPE and Sink-Collapse

Clamping the previous window's tail (or an anchor frame) as context creates **"attention sink frames."** Sinks mitigate immediate error accumulation but induce **sink-collapse**: generated content abruptly, repeatedly reverts to the sink frame → cyclic motion/audio. The cause is a conflict between multi-head attention and the periodic structure of **Rotary Position Embeddings (RoPE)**. RoPE encodes order by rotating query/key vectors by token index; its trigonometric/periodic nature causes phase re-alignment over long horizons. As the window slides indefinitely, **periodic aliasing** makes newly generated distant frames share nearly identical positional embeddings with the early clamped context. Multiple attention heads then simultaneously reach high phase concentration, assigning maximum weight to the clamped prefix — a catastrophic synchronization that copies the clamped audio across all subspaces → abrupt reset and repeating loop.

**Mitigation — Multi-Head RoPE Jitter (LoL "Longer than Longer").** Instead of a uniform base frequency (typically 10,000) for all heads, perturb it head-wise:

```
[RoPE jitter formula — lost in source paste]
theta_h = theta_base * (1 + jitter_scale * epsilon_h)     # epsilon_h ~ noise, per head h
```

Staggering base frequencies across heads drastically reduces the probability that multiple heads concurrently hit a phase-concentration maximum on the clamped context, disrupting inter-head homogenization and neutralizing the loop attractor during infinite rollouts. **No retraining required.**

### Attention Dispersion and Extrapolation Decay

Complementary view (**UltraViCo**): generating tokens beyond the native window `[T]` makes OOD tokens dilute learned attention patterns; attention mass disperses over an increasingly long positional sequence and, interacting with the harmonics of positional encodings, structures into **periodic attention patterns** — first universal quality degradation (blur/static), then cyclic repetition.

**Mitigation — Attention Concentration via Decay.** An inference-time, plug-and-play constant **decay factor** on attention scores for tokens beyond the training window suppresses distant-history logits, reallocating attention mass to the immediate reliable in-window context. This breaks the periodic harmonic accumulation without touching pretrained weights.

## Mitigating Drift and Over-Smoothing in Sliding Windows

Continuous FIFO-diffusion (a sliding window of partially denoised frames) typically fails via temporal drift and RMS collapse.

### The Failure of Step-Wise Averaging

FIFO overlapping windows often **average** latent states at each diffusion step for smooth boundaries. But (per multi-view joint diffusion research) step-wise averaging **excessively suppresses high-frequency latent components**. Because diffusion relies on precise SNR calibration, suppressing HF variance loses acoustic energy; over successive windows this compounds → drift into a low-energy state decoding as muffled noise, hiss, or silence.

### Latent Swap Joint Diffusion (SaFa)

**Swap Forward (SaFa)** replaces averaging with latent **swapping**:
- **Self-Loop Latent Swap.** Instead of averaging overlapping regions, apply a frame-level bidirectional swap. Because adjacent windows sit at slightly different trajectory steps, the swap adaptively injects **high-frequency variance from the advanced window into the lagging window** — preserving spectral energy and avoiding aliasing without disrupting low-frequency continuity.
- **Reference-Guided Latent Swap.** A unidirectional swap between a centralized reference trajectory and the non-overlapping regions during early denoising anchors global acoustic environment, preventing style/semantic drift over multi-minute rollouts.

### Curved Denoising and QKV Sharing (InfiniteAudio)

**InfiniteAudio** (training-free, arbitrary length) shares the **query/key/value embeddings from the initial anchor frames** across all subsequent windows, a persistent stylistic conditioning signal maintaining speaker identity, reverberation, and timbre. Combined with a **curved denoising** trajectory that selectively prioritizes key steps, it achieves theoretically infinite generation at **constant memory footprint**, preventing acoustic-environment forgetting.

## Modern Streaming and Block-Causal Diffusion Frameworks

### Block Flow Matching (DiffRhythm 2)

For flow-matching models, **DiffRhythm 2** generates 210 s+ via a semi-autoregressive **Block Flow Matching** architecture: the latent is partitioned into fixed-length blocks; each block is generated non-autoregressively via flow matching, but the overall sequence is generated autoregressively, block by block.

```
[Block Flow Matching velocity field + loss — lost in source paste]
For block b: estimate velocity v_b conditioned on all preceding CLEAN blocks z_{<b},
the current noisy block, and an independently sampled timestep t_b;
plus style prompt and lyrics. Loss = flow-matching objective averaged across blocks.
```

- **Attention masking + EOP padding.** Concatenate clean history with the current noisy block; an explicit **autoregressive attention mask** lets the current noisy block attend to all past clean blocks and itself, but past clean blocks cannot attend to the future. Final blocks are padded with **"End-of-Playlist" (EOP)** frames — a constant vector of ones `[formula lost in paste]` — a clean numerical termination signal that's easy to learn without distorting the latent space.
- **Stochastic Block REPA Loss.** Because SSL representations suffer frame-shift from convolutional downsampling, per-block alignment loss is unstable. DiffRhythm 2 randomly samples blocks across the whole sequence and computes REPA loss on the **continuous combination of clean-history + current-noisy hidden states**, grounding localized generation in global musical context — natively preventing degenerate repetition.

### Live Music Diffusion Models (LMDM) and ARC-Forcing

**LMDM** repurposes bidirectional diffusion models into streaming, autoregressive generators under a strict latency budget.

- **Block-Wise KV Caching.** Standard block-AR diffusion concatenates clean context with noisy target using full bidirectional attention, so the clean-context representation changes every diffusion step (uncacheable). LMDM routes clean context and noisy target through **separate projections** with asymmetric attention masks:
  - **Encoder-Decoder LMDM:** clean-context frames attend only to each other; noisy-target frames attend to themselves + clean context → the clean context's K/V can be cached across all diffusion steps.
  - **Block-Causal LMDM:** clean context is partitioned into blocks that cannot attend forward → KV caching over both diffusion steps AND time. Sliding the window forward just appends the new block's cache instead of re-encoding history — performance rivaling discrete AR models.
- **Bypassing the noise-schedule ceiling via ARC-Forcing.** Noise-ducking controllers hit a ceiling because the model was never trained to recover from compounding AR errors. **ARC-Forcing** (Adversarial Relativistic Contrastive + Self-Forcing) is a fully differentiable post-training paradigm: since flow-matching sampling is differentiable, the model generates multi-block rollouts during training (a stochastic step size simulates rapid denoising) and an adversarial discriminator evaluates long-horizon rollouts against real data. Global adversarial supervision on the model's own multi-block predictions trains it to reduce error accumulation and drift — **eliminating heuristic inference-time noise ducking**, maintaining fidelity + novelty natively.

## Formalizing the "Prompt Arc": Hierarchical and Time-Varying Conditioning

Rich time-varying conditioning mitigates repetition collapse because an unconstrained continuous diffusion model defaults to its strongest prior — self-similarity and repetition. A dense unfolding conditioning signal is a structural anchor forcing the trajectory out of the loop attractor.

### Interleaved Autoregressive Sketching (SongBloom)

**SongBloom** gives a DiT an explicit persistent structural plan via an **interleaved patch-wise formulation** (not the cascaded "LM makes full semantic sequence, diffusion renders it" approach):
- **Semantic sketch.** Discrete embeddings from a self-supervised music model (MuQ / MERT) as "sketch tokens" — high-level macro-structure, no acoustic detail.
- **Interleaved generation.** Divide into fixed patches (~0.64 s). For each patch, the AR transformer predicts sketch tokens from the global style prompt + all prior semantic/acoustic history.
- **Chain-of-Thought prompting.** The new sketch patch is immediately passed to the non-AR diffusion transformer as a CoT prompt to synthesize that patch's fine-grained acoustic latents.

The model dynamically generates its own prompt arc patch-by-patch; bidirectional context flow keeps the diffusion model constrained, guaranteeing semantic alignment over long durations.

### Storyboard Planning and Dynamic Motion Prompts (DrawVideo)

Long-video **DrawVideo** decomposes generation into "storyboard shots," each defined by a static appearance prompt (≈ global genre/instrumentation) and a dynamic motion prompt (≈ local musical action / lyrical phrasing). It generates a structure-aligned reference keyframe for the transition, derives subsequent action states, then synthesizes latent transitions between them. Audio analog: generate boundary latents for Verse/Chorus/Bridge first, then **inbetweening diffusion** to fill gaps against a precomputed macro-structural map.

### Modifying Cross-Attention for Temporal Control

- **Segmented Cross-Attention (SCA) — Presto.** Instead of one global text embedding to all cross-attention layers, split the DiT hidden states along the temporal dimension into segments, each cross-attending only to a corresponding sub-caption / sequential prompt. **No additional parameters.** Forces the model to alter acoustic generation as time progresses, denying it a static conditioning signal → directly prevents loop attractors.
- **Progressive Soft-Masked Cross-Attention (PSCA) — Flowley.** Shallow layers apply a broad soft mask (wide text context → global semantic/stylistic environment); deep layers progressively tighten into a hard sliding window (precise alignment of specific audio latents to specific text tokens) → musical events occur exactly when the prompt arc dictates, without rigid external timestamps.
- **Masking Text from Committed History (Incantation).** Critical rule: **text cross-attention must be masked away from committed history.** If a time-varying prompt is injected into a window containing clamped historical frames, letting new text embeddings attend to old frames causes **temporal cross-contamination** — the new prompt pollutes historical context, echoing the past and looping. Limit text cross-attention strictly to the noisy target frames → the model generates novel material instead of echoing the clamped prefix.

## Synthesis and Architectural Recommendations

Naive sliding-window continuation inevitably fails via RoPE periodicity, attention dispersion, and RMS energy collapse. The empirical observation that "conditioning richness is the dominant lever" is mathematically and empirically validated. To extend a ~24-block DiT into a robust multi-minute generator:

1. **Multi-Head RoPE Jitter** — randomized head-wise base-frequency perturbation; disrupts the inter-head homogenization causing sink-collapse. No retraining.
2. **Block-Causal KV Caching (LMDM)** — abandon naive overlapping FIFO; separate clean-context from noisy-target projections, block-causal mask, temporal KV caching → faster inference, no target-noise corruption of clean history.
3. **ARC-Forcing over noise-ducking** — post-train on multi-block rollouts with a learned discriminator; explicitly penalize AR drift instead of capping novelty with noise.
4. **Automate the prompt arc via Segmented Cross-Attention** — pre-generate structural sub-prompts (LLM), map to temporal segments; **strictly mask text cross-attention away from clamped history** to prevent temporal cross-contamination.

Combining block-causal attention masking with dynamic temporally-segmented cross-attention maintains structural momentum, charting novel trajectories and permanently escaping the loop attractor.

## Works Cited

1. Suno vs Udio (Reddit r/udiomusic) — background only
2. Generative AI Decoded: Frameworks for Text/Images/Video/Audio — Medium
3. Neural generative audio — danmackinlay.name notebook
4. Suno vs Udio comparison (2026) — Born To Produce
5. Suno AI Guide 2026 — aitoolsdevpro.com
6. Suno vs Udio detection — Authio
7. YuE: Scaling Open Foundation Models for Long-Form Music Generation — ResearchGate
8. How it Works — Yue AI
9. Udio — Wikipedia
10. Yue AI — free generator
11. **LoL: Longer than Longer, Scaling Video Generation to Hour — arXiv 2601.16914** (Multi-Head RoPE Jitter; CVPR 2026)
12. LoL — ResearchGate 400072086
13. LoL — CVF Open Access (CVPR 2026)
14. **UltraViCo: Breaking Extrapolation Limits in Video Diffusion Transformers — arXiv 2511.20123** (attention decay)
15. UltraViCo — OpenReview (id=fLLCmC53u9)
16. Attention-Space Extrapolation — Emergent Mind
17. UltraViCo — arXiv 2511.20123
18. **Latent Swap Joint Diffusion for Long-Form Audio Generation (SaFa)** — ResearchGate 388847759
19. Latent Swap Joint Diffusion for 2D Long-Form Latent Generation — CVF (ICCV 2025)
20. Leveraging Early-Stage Robustness in Diffusion Models — ResearchGate
21. Latent Swap Joint Diffusion — ICCV 2025 Open Access (html)
22. Latent Swap Joint Diffusion — arXiv 2502.05130 (html)
23. **Latent Swap Joint Diffusion — arXiv 2502.05130** (abs)
24. **InfiniteAudio: Infinite-Length Audio Generation with Consistent Acoustic Attributes** — OpenReview (id=Hp6f6VKAeP)
25. **InfiniteAudio — arXiv 2506.03020**
26. **DiffRhythm 2: Efficient and High Fidelity Song Generation via Block Flow Matching — arXiv 2510.22950** (html v2)
27. DiffRhythm 2 — arXiv 2510.22950 (html v3)
28. DiffRhythm 2 — arXiv 2510.22950 (pdf)
29. DiffRhythm 2 — ResearchGate 396967859
30. DiffRhythm 2 — arXiv 2510.22950 (html)
31. **Live Music Diffusion Models: Efficient Fine-Tuning and Post-Training of Interactive Diffusion Music Generators — arXiv 2605.22717** (html; LMDM + ARC-Forcing; already in papers/)
32. LMDM — arXiv 2605.22717 (pdf)
33. LMDM — arXiv 2605.22717 (abs)
34. LMDM — ResearchGate 405132094
35. **Incantation: Natural Language as the Action Interface for Multi-Entity Video World Models** — matrixteam-ai.github.io
36. **SongBloom: Coherent Song Generation via Interleaved Autoregressive Sketching and Diffusion Refinement — arXiv 2506.07634** (html v4)
37. SongBloom — arXiv 2506.07634 (pdf)
38. SongBloom — themoonlight.io review
39. SongBloom — OpenReview (id=Fa0kehLK6s)
40. DrawVideo: Generating Long Video from Storyboard Keyframe Sketches — arXiv 2605.23508
41. Hugging Face Daily Papers — coherent long-video generation
42. DreamShot: Personalized Storyboard Synthesis with Video Diffusion Prior — arXiv 2604.17195
43. **Long Video Diffusion Generation with Segmented Cross-Attention (Presto) and Content-Rich Video Data Curation — CVF (CVPR 2025)**
44. Precise Video-to-Audio Generation with Cross-Modal Alignment in Latent Space (Flowley/PSCA) — arXiv 2607.06405
45. Precise Video-to-Audio Generation — Sight and Sound, CVPR 2026
