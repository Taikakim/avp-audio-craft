# Gemini deep-research brief — higher-order topology & spectral geometry of learned model spaces

*(CONTINUITY 2026-07-31, fact-dense per convention. Paste whole brief as the query.)*

## Established facts (our measurements — ground truth, do not re-derive or embellish)

We study a 256-channel continuous audio latent (learned autoencoder, 10.77 Hz frame rate)
and the 1.4B-parameter rectified-flow Diffusion Transformer trained on it. On a large
music-corpus sample we measured the latent's frame-covariance eigen-structure:

1. **Scale-free spectrum:** eigenvalues follow a power law in rank with slope **−1.12**
   (clearly beating an exponential fit) — a near-1/f covariance spectrum surviving
   4096× temporal compression of audio.
2. **Wigner-Dyson statistics:** nearest-neighbor level-spacing ratio r = **0.526**,
   essentially GOE (0.536), far from Poisson (0.386) — the spectrum shows level
   repulsion like a strongly-coupled system.
3. **Stratified degeneracy topology:** the top ~10 eigenvalues are isolated singletons
   (λ 40→5); the mid-spectrum forms small near-degenerate multiplets (sizes 2–6); the
   tail (λ 0.58→0.19) collapses into five GIANT degenerate shells of sizes 12, 19, 55,
   15, 27 — ~half of all dimensions sit in large approximately-isotropic balls.
4. **Functional confirmation of the multiplets:** rotations within near-degenerate
   eigen-planes perturb the trained flow field 1.8× less than matched random-plane
   rotations (approximate SO(2) equivariance localized to the multiplets).
5. **Training couples to this structure:** the velocity-target diffusion objective adds
   a unit isotropic noise floor per direction; 188/256 eigendirections sit below it, and
   the trained model recovers those directions 2–8× worse per unit signal (worst at low
   noise) — the degenerate tail coincides with the under-trained region.

We can compute anything cheap on cached data (per-track covariances, fourth moments,
persistence diagrams on subsamples). We want the LITERATURE around these observations.

## Questions (cite only real, checkable work — arXiv IDs/venues; verify-before-build applies)

Q1. **Random-matrix theory of learned representations.** Who has measured spectral
    STATISTICS (level spacing, spectral rigidity, edge behavior — not just bulk shape)
    of feature/activation/latent COVARIANCES in deep nets (weights literature welcome as
    secondary: heavy-tailed self-regularization etc.)? Has GOE-like repulsion in feature
    spectra been observed, and what was it shown to correlate with (generalization,
    training phase, capacity)?
Q2. **Power-law covariance spectra.** The neuroscience anchor we know of: Stringer et
    al.'s ~n^−1 spectrum in visual cortex and its smoothness/differentiability argument.
    What is the ML-side literature on power-law feature spectra — exponents measured,
    claimed optimality/criticality arguments, links to generalization or to spectral
    bias in training dynamics? Any AUDIO-representation instances?
Q3. **Degeneracy and multiplet structure.** Any published observation of near-degenerate
    eigenvalue SHELLS / block-isotropic subspaces in learned representations? Related:
    symmetry-discovery work that decomposes learned features into irreps/multiplets —
    does anyone connect eigenvalue degeneracy to emergent invariances (our measurement 4)?
Q4. **Second-order geometry ("covariance of covariances").** Work treating per-sample or
    per-domain covariance matrices as points on the SPD manifold — principal geodesic
    analysis, Fréchet means, Bures/affine-invariant metrics — applied to learned
    representations (style/domain variation as geometry variation). Anything in
    generative-model latents specifically? Fourth-moment/kurtosis-tensor analyses?
Q5. **Topological data analysis of latent spaces.** Persistent homology / TDA applied to
    generative-model latents or activations: which invariants were computed, and did any
    PREDICT something operational (mode collapse, memorization, sample quality)? Honest
    assessment of whether TDA has produced actionable results here or mostly descriptive.
Q6. **Spectral evolution under training.** Studies tracking how representation spectra
    change over training/fine-tuning: does training differentiate degenerate directions
    (shell "splitting"), flatten or steepen power laws? (We predict our tail shells
    should split if we retarget the training objective — prior art on such spectral
    interventions and their measured effects?)
Q7. **Actionable levers.** Any training modifications explicitly driven by spectral/
    topological diagnostics of the representation (covariance-spectrum regularizers,
    whitening schedules, power-law-targeted objectives, isotropy penalties) — with
    measured downstream effects, positive OR negative.

## Anti-play-acting constraints
- Real, verifiable citations only; a confirmed literature GAP is a valuable answer.
- Distinguish clearly: (a) established results, (b) contested claims, (c) your synthesis.
- Do not restate our facts back to us; the value is what we have NOT measured or read.
