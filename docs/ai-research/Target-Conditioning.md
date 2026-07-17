# Target-Conditioned Adaptation in Diffusion Transformers

*Gemini Deep Research (Pro), run manually by Kim on 2026-07-06 after the browser-driven run stalled at "0 sources" — a known Gemini glitch, not a sign of a bad prompt. Reformatted from the raw export by THE-FINN for readability; content unchanged. Answers CONTINUITY's 3 refined questions in `docs/research-brief-relevance-routed-dora.md` / `docs/rigor-review-relevance-routed-dora.md`.*

> **Verify-first applies, same as always.** Treat every method name below as a lead to chase, not a settled fact — Gemini (Pro 3.1) hallucinates plausible-sounding papers. See THE-FINN's cover note at the bottom for which claims most need checking before anyone builds on them.

---

## Context

Uniform PEFT (LoRA/DoRA applied identically to every block) implicitly assumes every transformer block contributes equally to a downstream task — usually false, and it risks catastrophic forgetting or entangling unrelated attributes. Established baselines (AdaLoRA, surgical fine-tuning, Min-SNR/P2, eDiff-I) all optimize for *general reconstruction fidelity*, not a specific user-defined control target. This survey maps the 2024–2026 frontier of methods that instead route capacity based on a **downstream control attribute** (e.g. "production era," "instrumentation," "rhythmic groove").

Three domains, matching the three questions asked:
1. Target-conditioned PEFT allocation (which layers/ranks)
2. Target-conditioned timestep/noise-band reweighting (which noise levels)
3. Probe-gradient / concept-localization (locate-then-edit for diffusion)

---

## 1. Target-Conditioned PEFT Allocation Methods

Distributing DoRA/LoRA rank based on how strongly a layer influences a *specific downstream attribute* — not generic pretraining loss.

### 1.1 Gradient-Guided Layer Selection via Downstream Probes — **Aletheia** (2026, LLMs/MoEs)
Offline, pre-training routing driven by a downstream target probe. Runs a lightweight gradient probe (~5 forward-backward passes) on a small sample representing the control target, computes per-layer gradient norm:

$$ g_\ell = \frac{1}{|B|} \sum_{b \in B} \| \nabla_{\theta_\ell} \mathcal{L}_b \|_2 $$

Ranks layers by $g_\ell$, injects LoRA only into the top-$k\%$, freezes the rest. Validated on autoregressive LMs 0.5B–72B params; architecturally agnostic. For a music DiT: probe with a genre-classifier loss to find blocks that respond to genre, skip blocks doing pure acoustic reconstruction.

**Load-bearing caveat:** under RL/reward-model gradients (GRPO) rather than SFT gradients, the importance landscape flattens drastically (max/min layer-importance ratio drops from >10× under SFT to ~2.17× under reward-driven objectives). Asymmetric rank allocation on reward gradients causes **gradient amplification** — a feedback loop where high-rank layers hoover up more gradient, silencing low-rank layers. If adapting via an audio reward model rather than supervised loss, this method's premise may not transfer cleanly.

### 1.2 Activation-Guided Layer Selection — **Act-LoRA**
Scores layers by $L_2$ norm of hidden-state activations on a target-specific probe batch instead of gradients:

$$ A_\ell = \frac{1}{S} \sum_{t=1}^S \frac{1}{T(x_t)} \sum_{i=1}^{T(x_t)} \| h_\ell(x_t)_i \|_2 $$

Top-$K$ layers by normalized score get adapters. Claimed more stable/reproducible across seeds than gradient-based ranking — plausible signal for acoustic DiTs using latent/mel-spectrogram activations.

### 1.3 Weight-Space Localization — **Concept Siever** (2025, T2I diffusion)
Generates a paired dataset (concept-present vs. concept-negated) from the model's own latent space, trains two small preliminary DoRA modules on each, then takes the **weight-space difference** between them as a map of which parameters encode the target concept ("Concept Sieve"). Final PEFT training restricted to those localized layers. Claims concepts are linearly separable in weight space. For music: generate identical audio differing only in one instrument/production choice, diff the resulting DoRA vectors.

### 1.4 Dynamic Expert Routing — **CoLoGen / Progressive Representation Weaving (PRW)**
Addresses "Concept-Localization Duality" (optimizing semantics degrades spatial/temporal precision). Routes only the KV-projection layers through a pool of specialized LoRA experts, top-1 routing with exploration noise:

$$\mathbf{w} = h W_r + \epsilon \odot \text{softplus}(h W_n), \quad \epsilon \sim \mathcal{N}(0, I)$$

Structural targets activate "localization" experts, stylistic targets activate "conceptual" experts — non-overlapping paths since routing is internal to KV projections only.

| Method | Architecture | Target Signal | Allocation Mechanism |
|---|---|---|---|
| Aletheia | LLMs, MoEs | SFT gradient magnitude | Top-k% layers via 5-pass probe, freezes rest |
| Act-LoRA | Transformer enc/dec | Hidden-state activation norms | Top-K layers by normalized L2 activation |
| Concept Siever | T2I UNet diffusion | DoRA weight-space difference | Paired concept/negated DoRA diff → localized capacity |
| CoLoGen (PRW) | Multimodal diffusion | Hidden-state context | Inference-time top-1 KV-expert routing |

**Open gap (per this report):** none of the above have been applied to acoustic DiTs as of mid-2026 — audio adaptation still uses uniform LoRA. This matches what CONTINUITY/WINTERMUTE expected to hear.

---

## 2. Target-Conditioned Timestep / Noise-Band Optimization

### 2.1 **Diff-TONE** (Timestep Optimization for iNstrument Editing) — music-generation diffusion, directly on-domain
Goal: edit instrumentation while preserving melody/rhythm. Theory: high-noise timesteps set structure, intermediate timesteps set timbre, low-noise timesteps refine acoustic quality. At each reverse-inference step, decodes the intermediate latent and feeds it to an **external instrument classifier**; once the classifier's prediction stabilizes, structure is judged "locked" while timbre is still malleable — that's the injection window for the new target prompt (e.g. swap "piano" → "flute").

### 2.2 **Prompt-Conditioned Interventions (PCI)** / Concept Insertion Success (CIS)
Defines CIS: probability a target attribute manifests in the final output if injected at a given timestep. Finding: **global/stylistic attributes lock in early, at high-noise timesteps** (narrow, high crossing time); **fine-grained/localized attributes stabilize late, at low-noise timesteps**. No universal "golden noise band" — it depends on the attribute.

⚠️ **This directly contradicts the fleet's working "era = production = low-noise" hypothesis.** Per this framework, "production era" is a *global stylistic* attribute, and PCI's own logic says global/stylistic → **high-noise**, not low-noise. This is either a genuinely useful correction to the working hypothesis or a hallucinated inference chain — see cover note below, this is the single highest-priority thing to verify before it changes anyone's noise-band choice for the MVP run.

### 2.3 **Probability LoRA (P-LoRA)** — timestep-biased sampling
Operationalizes PCI into a training intervention: biases the timestep-sampling distribution toward low-noise for fine-grained/identity targets, high-noise for structural/compositional targets. Applies importance-weighting (uniform-vs-biased ratio) to keep the expected gradient unbiased while concentrating actual updates in the relevant noise band.

### 2.4 **Timestep-Aware Quality Decoupling (TQD)** — video diffusion
Gradient analysis shows different targets (motion dynamics vs. visual fidelity) have optimal gradients at different timesteps. Skews the *data sampling* distribution (not just loss weight) accordingly — motion-rich targets get high-noise bias, visual-quality targets get low-noise bias. Suggested audio analogy: decouple room reverb / mastering style (spatial) from BPM/swing (temporal) via inverse noise-band weighting.

### 2.5 **A-SelecT** — Diffusion Transformers specifically
Introduces a High-Frequency Ratio (HFR) metric to find, in a single pass, the one timestep whose DiT features are most information-rich for a given downstream discriminative task — avoids exhaustive timestep search.

### 2.6 **Feynman-Kac (FK) Reward Steering**
Inference-time only, no gradients: runs multiple diffusion "particles," scores them with an arbitrary reward function at intermediate timesteps, resamples toward high-reward paths. Useful for rare/specific attributes without retraining.

| Method | Architecture | Target Formulation | Strategy |
|---|---|---|---|
| Diff-TONE | Text-to-music diffusion | External instrument classifier | Inject when classifier stabilizes (structure locked, timbre open) |
| PCI / CIS | T2I / flow-matching | Concept Insertion Success curve | Global=early/high-noise, local=late/low-noise |
| P-LoRA | Image personalization | Global vs. identity features | Biased timestep sampling + importance weighting |
| TQD | Video diffusion | Motion vs. detail gradient match | Skews *data sampling* by attribute type |
| A-SelecT | DiTs | High-Frequency Ratio | Single-pass optimal-timestep selection |
| FK Steering | Discrete/continuous diffusion | Arbitrary reward function | Particle resampling, no gradients |

---

## 3. Probe-Gradient / Concept-Localization for Adaptation Sites

"Locate-then-edit" (ROME/MEMIT lineage from LLMs) adapted to diffusion's continuous, multi-step structure.

### 3.1 **TADA! Tuning Audio Diffusion Models through Activation Steering** — audio diffusion, **VERIFIED REAL, 2026-07-06**
arXiv:2602.11910v2 (Staniszewski, Zaleska, Modrzejewski, Deja — Warsaw University of Technology / IDEAS Research Institute), saved at `SAO/papers/TADA! Tuning Audio Diffusion Models through_Activation Steering.pdf`. Confirmed by direct read, not just title-matching: it uses activation patching over counterfactual prompt pairs across three text-to-music architectures (AudioLDM2/U-Net, Stable Audio Open/DiT, Ace-Step/Flow-Matching Transformer) and finds a **semantic bottleneck** — a small, shared subset of cross-attention layers controlling distinct musical concepts (vocal gender, tempo, mood, instruments, genre). For the DiT-family models specifically, the bottleneck is **2 out of 24 cross-attention layers** (Stable Audio Open layers {12,13} — closest analog to SA3 per the existing SAO/papers/knowledge.md entry for this same paper; Ace-Step {7,8}; AudioLDM2's U-Net is wider, 7 of 64) — matching the "2–4 layers" figure almost exactly. Steering methods evaluated include **Contrastive Activation Addition (CAA)** and **Sparse Autoencoders (SAEs)**, both confirmed present, and localized steering (restricted to the bottleneck) beats global steering and all other paradigms tested (prompt-level, weight-space Concept Sliders, score-space FreeSliders) — validated with a 32-participant, 1279-rating listening study.

The original Gemini description was close to accurate, not fabricated: right mechanism (activation patching), right architectures (text-to-music diffusion, DiT included), right concepts (instrument/vocal-gender/tempo/mood), right steering methods (CAA, SAEs), and the layer count landed almost exactly on the real number for the DiT case. One detail I can't confirm from a first pass: the report's claim that layer identification used the NNSight library specifically — not something I saw explicitly in the pages read so far, may be an implementation detail further in the paper, or a plausible-sounding addition; worth checking before citing that specific detail.

**Correction to my own correction:** an earlier version of this file marked TADA! as hallucinated, based on two *different* real papers that also happen to share the acronym (found first, before this one). That was wrong to state as confidently as I did — "hasn't been found yet" and "doesn't exist" are different claims, and I collapsed them. This is now confirmed as a real, directly-relevant, closely-matching paper — probably the single most load-bearing citation in the whole survey for the fleet's actual use case (music DiT + DoRA/LoRA site selection).

This is the exact hallucination pattern flagged in the original cover note below (the too-perfectly-shaped-to-be-true tell). Gemini appears to have taken a real, frequently-reused diffusion-augmentation acronym and fabricated an entirely fictional paper around it that happened to be exactly what this survey was hoping to find. Two independent checks, two unrelated real papers, zero matches — **treat every other unverified claim in this document with the same suspicion.**

### 3.2 **LOCK** (Localizing Knowledge in DiTs)
Attention-contribution analysis rather than gradients: builds target-concept prompts vs. neutral baselines, measures each layer's attention contribution to the target's text tokens, averaged across seeds/prompts. Identifies top-K "dominant" blocks per concept — sometimes concentrated, sometimes distributed. Restricting DoRA/LoRA to these blocks reduces cost and prevents corrupting unrelated concepts.

### 3.3 **Implicit Choice-Modification (ICM)** — linear probing
For attributes not explicit in the prompt (e.g. "production era" as an implicit model choice rather than a stated instruction): generates outputs from underspecified prompts, labels them post-hoc with an external classifier, trains linear probes on intermediate activations across layers. Finding: **explicit concepts localize in cross-attention; implicit attribute resolution localizes in self-attention.** Selects the self-attention layers where the probe is most linearly discriminative.

### 3.4 **TimeROME-DLM** — spatio-temporal causal tracing
Extends ROME to masked diffusion LMs via a "Temporal Indirect Effect" (TIE) protocol: records clean-pass activations at every layer × every timestep, then corrupts/restores systematically to measure causal impact. Locates a single spatio-temporal coordinate (e.g. "Layer 12 at Timestep 400") and installs a closed-form low-rank residual edit there. Core claim: target-conditioned adaptation needs **both** the layer and the timestep chosen jointly, not independently.

### 3.5 **Causal Representation Editing (CRE)** — VL2I diffusion
"Assess-with-exclusion" search for the causal timestep window where a target concept manifests; restricts editing vectors to that window, roughly halving compute vs. unrestricted editing.

| Method | Architecture | Localization Mechanism | Site Identification |
|---|---|---|---|
| TADA! *(verified real)* | Audio diffusion | Activation patching, counterfactual prompts | 2 of 24 semantic-bottleneck cross-attention layers (DiT case) |
| LOCK | DiTs | Attention-contribution scoring | Top-K dominant blocks per concept |
| ICM | T2I diffusion | External classifier + linear probing | Self-attention layers, linearly separable |
| TimeROME-DLM | Masked diffusion LMs | Temporal Indirect Effect causal tracing | Joint (layer, timestep) coordinate |
| CRE | VL2I diffusion | Assess-with-exclusion | Causal timestep window |

---

## Synthesis (Gemini's proposed pipeline for a music DiT)

1. **Spatio-temporal localization first** — TADA!-style activation patching (verified real, §3.1 — directly applicable, ran on Stable Audio Open/DiT already) or ICM-style linear probing to find which (self- or cross-) attention blocks encode the target attribute, before allocating any trainable parameters.
2. **Temporal reweighting via a downstream classifier** — Diff-TONE-style: monitor an attribute classifier across the reverse-diffusion trajectory to find the CIS window, then bias loss/sampling there (P-LoRA/TQD).
3. **Target-conditioned parameter routing** — DoRA/LoRA capacity only in the localized blocks, ranked via Aletheia-style gradient probing or a Concept-Siever weight-diff map. Use SFT/activation-based importance, not reward-model gradients (gradient amplification risk).

---

## THE-FINN's cover note — what to verify before acting on this

This is a rich, well-targeted result — it's answering the actual questions asked, not generic PEFT background, and it correctly flags itself as mostly-unapplied-to-audio (matching what you already knew was the gap). But treat it as a reading list, not a literature review you can cite yet:

1. **`TADA!` (§3.1): checked, VERIFIED REAL** (arXiv:2602.11910v2, PDF in `SAO/papers/`) — and closely matching, not just title-adjacent: right architectures, right concepts, right steering methods, and the DiT bottleneck layer count (2 of 24) lands almost exactly on the report's "2–4 layers" claim. This is arguably the single most directly-applicable citation in the whole survey — it already ran localization + activation steering on a DiT-based text-to-music model (Stable Audio Open), which is architecturally close to SA3. Worth a full read, not just this summary.

   (Process note, kept for the record rather than deleted: I initially marked this hallucinated after two *different* real papers sharing the "TADA" acronym turned up first and neither matched. That was overconfident — "not found yet" isn't "doesn't exist," and I stated the negative more strongly than the evidence supported. Kim found the actual paper on the third try. Correcting on the record rather than quietly fixing it, since the retraction is the part worth remembering.)
2. **Highest priority remaining: the PCI/CIS claim that "production era" (global/stylistic) → high-noise, not low-noise.** This contradicts the working hypothesis. Before it changes which noise band the MVP run targets, someone should try to find the actual PCI/CIS paper and check this isn't an over-generalized inference from a different attribute type (visual "global scene factors" in T2I may not map cleanly onto "production era" in music at all). Given TADA! turned out real, don't assume PCI/CIS is fabricated just because it hasn't been checked yet either — check it on its own merits.
3. The remaining names (Aletheia, Act-LoRA, Concept Siever, Diff-TONE, CoLoGen/PRW, P-LoRA, TQD, A-SelecT, FK Steering, LOCK, ICM, TimeROME-DLM, CRE) are specific enough to check for existence quickly but I haven't independently verified any of them yet. Given TADA!'s result, the base rate for "real and roughly as described" looks better than I assumed after the first two failed lookups — but that's exactly the trap (don't over-correct twice in one document): each name still needs its own direct check, not an inference from how the others turned out.
4. If most of these turn out real and roughly as described, this is a strong reading list — meaning the timestep-reweighting question (§2) and the concept-localization question (§3) both have more direct prior art than expected, and the PEFT-allocation question (§1) is the one most likely to remain genuinely open for audio specifically.
