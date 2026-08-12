# Anatomica: Localized Control over Geometric and Topological Properties for Anatomical Diffusion Models (2511.20587)

*Project-POV abstract, CONTINUITY 2026-08-12 (reading-sweep 4/5; deep-read pp.1-9 + all figures/tables).
Kadry, Abdelwahed, …, Edelman (MIT / BWH / EPFL, Nov 2025). Domain is 3D cardiac/anatomical segmentations,
but the MACHINERY is exactly our **LatCH family-A = inference-time GUIDANCE readout heads** — the closest
paper to our controllable-generation paradigm, told in a different domain.*

## What it contains
An **inference-time** framework (NO conditional retraining) that steers an *unconditional* latent diffusion
model toward target geometry/topology by **guidance**. Per sampling step (the whole loop is the thing to note):
1. Denoise the noisy latent `z_σ` → **clean-latent prediction `ẑ₀ = D_θ(z_σ;σ)`** (Karras x₀).
2. **Parse substructures** `S_k` from `ẑ₀` — differentiably slice out localized regions via cuboidal *control
   domains* (a template grid spatially transformed by affine `R·diag(s)·Xᵀ+t`) + a Boolean tissue-selection
   vector. Key trick = **L-parsing**: a **neural-field decoder** queries *arbitrary* points, so you decode
   only the local region at high res (or the whole thing coarse) — measure properties **straight from latent
   space**, skipping full-volume decode. Two modes: coarse (global, low-res) vs localized (local, high-res).
3. **Differentiable measurement** of each substructure:
   - **Geometry** = voxel *moments*: zeroth=mass `m`, first=centroid `p`, second=covariance `Σ` →
     eigendecompose Σ into **size** (trace), **shape** (normalized eigenvalues), **orientation** (eigenvectors).
   - **Topology** = **persistent homology** (Cubical Ripser) on super-level sets → 0-D components, 1-D loops,
     2-D voids; a birth/death persistence diagram, partitioned by a target Betti prior into preserve/suppress
     sets.
4. **Potential functions** → gradient guidance: `L = λ_geo·L_geo + λ_topo·L_topo`; geometry is MSE to target
   moments, topology maximizes/minimizes persistence of the desired/undesired features. Guided step:
   **`D^w_θ = D_θ − σ²·∇_z L`** (energy-based guidance, à la Epstein diffusion self-guidance).
- **Softmax-temperature tuning:** the PH gradient vanishes where the softmaxed class-prob is ≈0/1 → they
  **raise the decode softmax temperature** so gradient flows back through the topology term. (A reusable
  "keep the guidance gradient alive" trick.)
- **Results:** beats/matches a *retrained* conditional baseline on geometric fidelity (Tab.2) and controls
  Betti numbers where the unconditional model can't (Tab.3: atrial separation B0 7.8%→78.9%); L-parsing at low
  decode res keeps fidelity while ~10× faster (Tab.4). Adaptive mass-weighting handles near-empty substructures.

## What this gives us / what stays ours
- **This IS the LatCH family-A paradigm, validated in another domain.** Our guidance readout heads (paper-spec
  `latch_weights_sa3_medium/`, incl `same_chroma`) do the same move: read a property off the **clean-latent
  prediction** during sampling and push the gradient back. Anatomica = the same skeleton with (a) a *neural-field
  decoder* for cheap partial-decode measurement and (b) *persistent-homology* topological potentials. Direct
  reassurance that our high-gain guidance route is a real, current, SOTA-competitive paradigm — and a concrete
  recipe for the pieces we do differently.
- **`σ²·∇_z L` is the gain knob = our LatCH weight.** Their guidance scale is literally our 512–1000× LatCH
  gain (the "2% authority mirage at low gain" theme, MASTER §5). Same lever, named differently. Reconciles with
  2603.04366's chroma-guidance "failure" the same way Kim called it: they under-scaled.
- **Softmax-temperature-to-keep-gradient-alive** is a transferable trick if we ever guide on a **discretized /
  argmaxed** readout (e.g. a hard chroma-bin or an onset threshold) where the gradient dies — warm the decode
  temperature instead of abandoning the target.
- **Persistent homology as a MUSIC control/eval signal** is the speculative gem. PH is domain-agnostic — over a
  self-similarity matrix or a chroma/onset time-series it measures **loops** (repetition/return, e.g. an ABA
  return-to-theme = a 1-cycle) and **components** (distinct sections). A differentiable PH potential (their
  Cubical-Ripser + softmax-temperature recipe) → a **structural/form control** ("make it return", "N distinct
  sections") that no chroma/onset head captures. Pairs with Tymoczko (chords already live in a topological
  orbifold) — topology of musical *time* is the open direction.
- **L-parsing = decode-from-latent-cheaply** echoes our SAME latent story: we already read chroma linearly off
  the latent (384-d regressors) without decoding audio. Anatomica generalizes "measure the property in latent
  space, not signal space" to arbitrary neural-field-decodable properties — the design pattern behind our whole
  LatCH-on-latent approach.
- **STAYS OURS / caveats:** (1) their objects are **discrete 3D voxel segmentations** with an explicit
  neural-field segmentation decoder; our SAME latent decodes to *audio*, and we have **linear** chroma/onset
  readouts, not a field decoder that emits a labeled voxel map — so the geometric-moment machinery isn't
  directly portable; what ports is the **guidance loop + gain + gradient-liveness** discipline and the
  **PH-as-structure** idea. (2) Inference-time guidance is **slower per sample** (parse+measure+backprop every
  step) — the trade vs our trained FiLM conditioning adapters (sa3_control) is guidance-flexibility (plug-and-play,
  any new target) vs speed (train once, cheap sampling). We already run BOTH families; this sharpens why.
  (3) PH is heavy (they note it limits topological guidance to coarse res) — a music-PH control would be a
  **2nd-wave** research bet, not the current control-head sweep.

**knowledge.md row** (hand to F): *Anatomica (2511.20587, Kadry/MIT-BWH, Nov'25) — inference-time GUIDANCE
(no retraining) steering an unconditional latent diffusion model via differentiable geo-topological potentials:
parse substructures off the clean-latent x₀ prediction with a neural-field decoder (L-parsing, measure in latent
space), measure geometry (voxel moments→size/shape/orientation) + topology (persistent homology→components/loops/
voids), guide by `D^w=D_θ−σ²∇_z L`. Softmax-temperature-tuning keeps the PH gradient alive. FOR US: this IS our
LatCH family-A guidance-readout-head paradigm validated SOTA in another domain — `σ²∇L` scale = our 512–1000×
LatCH gain (reconciles 2603.04366's under-scaled chroma "failure"); persistent-homology-as-differentiable-
structure/form control (loops=repetition/return, components=sections) is the speculative music transfer (pairs
w/ Tymoczko topology); L-parsing = measure-in-latent echoes our linear chroma readouts. Caveat: voxel-segmentation
domain + explicit field decoder (moment machinery not directly portable); guidance is slower-per-sample than our
trained FiLM adapters; PH heavy → 2nd-wave.*
