# TADA! Tuning Audio Diffusion Models through Activation Steering (2602.11910v2) — deep-read

Staniszewski, Zaleska, Modrzejewski, Deja (Warsaw UT / IDEAS), May 2026.
PDF: `TADA! Tuning Audio Diffusion Models through_Activation Steering.pdf`.
*(Provenance note: initially mis-flagged as fabricated — two unrelated real papers share
the acronym; Kim found the real one on the third search. FINN retraction on record.)*

## What it contains

**1. Localization (the "where"):** activation patching over **cross-attention layers**
with counterfactual prompt pairs (concept vs counterpart, e.g. male/female vocal,
fast/slow tempo, happy/sad, instrument swaps, genre swaps; 256 MusicCaps-derived prompts
per concept, GPT-4 counterparts, 8 seeds). Patch layer *l*'s cached K,V from the concept
run into the counterfactual run; impact score I(l,c) = normalized audio-text similarity
gain (MuQ; CLAP for vocal gender). Result — a **semantic bottleneck** in all three
architectures tested: cross-attn layers **{12,13} of 24 in Stable Audio Open** (closest
analog to SA3), {7,8}/24 in Ace-Step, 45–51/64 in AudioLDM2. The SAME few layers govern
all nine concepts; ablating everything *except* those layers ≈ no concept gain (true
bottleneck, causally verified).

**2. Steering (the "how"):** h′ = h + α·v_c at the functional layers only.
v_c built by **CAA** (mean paired-run activation difference, time-averaged), **AUSteer**
(sparse sign-agreement top-s dims), or **TopK SAE** trained on cross-attn activations
(steer = sum of top-scoring decoder columns). Benchmarked against prompt-level (PCI,
text/token embeddings), score-space (FreeSliders), weight-space (Concept Sliders = LoRA
sliders).

**3. The interaction that matters:** localization is NOT uniformly good.
- Activation steering: **+46–49% AUC for CAA** when restricted to functional layers;
  localized SAE = best overall AUC; localized CAA = best human "Seamless Edit" (3.32/5,
  1279 ratings, 32 listeners).
- **Weight-space steering DEGRADES under localization: Concept Sliders −21% AUC,
  −75% smoothness** when trained only on functional layers. Their explanation: weight
  adapters *add new mechanisms* rather than leveraging intrinsic ones — the bottleneck
  is where *existing* semantics concentrate, not where new capacity belongs.
- Multi-concept: summing CAA vectors across ALL layers destroys steering semantics;
  restricted to functional layers it composes (2–3 concepts, incl. negation).

**4. Eval protocol worth stealing:** alignment–preservation **AUC** (LPAPS preservation
vs sign-corrected MuQ/CLAP alignment delta, trapezoid over preservation), **Smoothness**
(std of consecutive alignment gaps along the α scale), Audiobox Aesthetics for quality;
all methods calibrated to the same max perceptual distortion (PCI's) for fairness.

## What it does NOT contain (what remains ours)
- Nothing on **numeric/continuous conditioning lanes** (our LatCH heads, FiLM year lane)
  — their knobs are text-concept-derived vectors, strength α only.
- Nothing on **training-time routing** (rank allocation, noise-band loss reweighting) —
  the relevance-routed-DoRA Axis-2 idea is untouched. But their Table 2 is direct
  EVIDENCE for the brief's caution: don't hard-restrict weight adapters to the bottleneck.
- Localization is **cross-attention only** — self-attn and MLP unmapped. Our
  layer×feature encodability map (probe R², correlational) covers all module types;
  their patching (causal) covers cross-attn. Complementary, not overlapping.
- No **timestep dimension** in the localization (they patch all steps); the
  crispness/last-25% question stays open.
- Concepts are categorical; **era/production-style** (Kim's axis) untested.
