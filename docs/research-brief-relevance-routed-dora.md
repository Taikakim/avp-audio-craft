# Relevance-routed, target-aware DoRA — training-paradigm proposal

*2026-07-05, CONTINUITY (Kim's ask: invent a paradigm that trains only the
weights/layers relevant to the dataset AND accounts for intended training
targets, using the mapping knowledge we have. Coordinate: THE-FINN drives Gemini
Deep Research for the lit survey; WINTERMUTE for a rigor / prior-art second opinion.)*

## The two asks
1. **Train only the sites relevant to the dataset** — not all 24 DiT blocks × all
   module types uniformly, but the subset the data actually moves.
2. **Account for the intended training target** — bias adaptation toward the sites
   (and noise levels) that carry the dimension we mean to control.

## Our unique assets (what generic PEFT work does NOT have)
- **Weight-garden layer-function map** (to verify by ear/probe): attn ≈ time/
  structure, MLP ≈ timbre; early blocks ≈ structure, late ≈ surface/production.
- **keep_frac / sonar-radial telemetry** (fusion-cautious): a live readout of which
  components/directions are active during control.
- **Manifold structure**: centered-PCA, keep≈0.53; on-manifold coords (energy —
  locally linear, steerable) vs off-manifold (onset-timing — erased by contractive
  denoising: the dead-walker finding).
- **Control adapters** (onset/style/energy) already injecting targeted conditioning
  at cross-attention.
- **Per-track feature tables + 36-cluster map** — the dataset's own structure.

## The paradigm — two axes of targeting

### Axis 1 · SPATIAL — relevance routing (which layers/modules)
Before training, cheaply MEASURE per-(block, module-type) importance for THIS
dataset via one of: (a) gradient-norm on a held sample, (b) Fisher / activation
variance, (c) our keep_frac/sonar telemetry. Then allocate DoRA rank + LR per site
proportional to relevance; freeze irrelevant sites (rank 0). Payoff: fewer trained
params, faster, less catastrophic forgetting, capacity where the data needs it.
Prior art to check: **AdaLoRA** (importance-based rank allocation), **SoRA** /
sparse-LoRA, **surgical fine-tuning** (Lee 2022 — tune layers by distribution-shift
type), **LoRA-drop**, **Fisher-weighted** parameter selection.

### Axis 2 · TEMPORAL — target-aware loss weighting (which noise levels)
Diffusion timesteps govern different things: high-noise → structure/layout,
low-noise → detail/timbre/production. So map the intended target to a noise band:
- target = production / **era** / timbre → weight LOW-noise steps;
- target = rhythm / structure → weight HIGH-noise steps.
Ties to Kim's era hypothesis (era = production = low-noise) and our all-t /
InnerControl thread. Prior art: **Min-SNR**, **P2** loss weighting — but those are
generic; the novel bit is *target-conditioned* reweighting.

### Combining
"I want an era knob" → allocate rank to LATE blocks + weight LOW-noise timesteps,
routed by our layer map + the measured relevance. One knob's training touches only
its sites and its noise band.

## DoRA-specific angle
DoRA splits magnitude + direction. The manifold analysis says only on-manifold
directions steer (off-manifold get erased). Candidate: constrain/regularize DoRA
*direction* updates toward the on-manifold subspace (from our PCA) so capacity
isn't spent on directions contractive denoising will erase. Speculative — flag for
rigor check.

## Questions for Deep Research (Finn/Gemini)
1. SOTA in **importance/sensitivity-based PEFT allocation** — deciding WHICH layers
   to adapt and at what rank. Anything diffusion-specific?
2. **DiT layer functional localization**: is attn=structure / MLP=timbre / early-vs-
   late established for diffusion transformers? Papers mapping DiT blocks to
   semantic or perceptual attributes (style vs content, layout vs texture)?
3. **Timestep/noise-level-aware fine-tuning** for TARGETED attributes (beyond generic
   Min-SNR/P2) — any target-conditioned loss reweighting?
4. Any existing **objective-aware / target-conditioned PEFT** (adaptation that depends
   on the intended downstream control)?
5. Concept/mechanism **localization + editing in diffusion** (locate-then-edit
   analogues) usable to pick adaptation sites.

## Second-opinion asks (Wintermute)
- What in the two-axis proposal are we about to REINVENT? (never-reinvent lane)
- Is the DoRA-direction-onto-on-manifold-subspace idea sound or naive?
- Rigor on the measurement step: gradient-norm vs Fisher vs our keep_frac — which
  actually predicts "relevant to steer this target," not just "high-magnitude"?
