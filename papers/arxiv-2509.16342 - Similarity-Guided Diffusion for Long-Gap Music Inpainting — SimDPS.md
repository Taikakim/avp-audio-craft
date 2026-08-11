# Similarity-Guided Diffusion for Long-Gap Music Inpainting — SimDPS (2509.16342)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). Aalto Acoustics Lab (Turland,
Moliner, Välimäki). Retrieval-as-conditioning + boundary-continuity — relevant to our inpaint
channel, transitions, and loop-collapse, though it's waveform not latent.*

**What it contains.** **SimDPS** = diffusion posterior sampling (DPS) + corpus similarity search.
Plain DPS conditions only on observed regions, weakly constraining the missing null-space over long
gaps → drifts to locally-smooth-but-implausible content. Fix: **retrieve an auxiliary signal `x̃`**
(a gap-length segment from a source corpus, by STFT+chromagram feature similarity, coarse-to-fine,
refined for waveform continuity at the gap boundaries) and add a **second auxiliary likelihood term**
pulling the null-space toward `x̃`, with a tunable uncertainty weight `ω_x̃` (ω_x̃=0 recovers plain
DPS). Results: on 2 s gaps in piano, **SimDPS beats plain DPS and beats pure similarity-search when
the retrieved match is only Fair/Poor** (p≈0.02); no benefit when the match is Poor. **Waveform-domain
diffusion** (MR-CQTdiff, invertible CQT, 44.1 kHz) — explicitly rejects latent diffusion for
fidelity; 50-step probability-flow ODE.

**Status vs our work.** The **conceptual guidance ports; the waveform splicing does not** (our SAME
is a compressed 10.77 Hz latent; retrieval/continuity would need to act in latent space). What's
useful: **(1) The failure diagnosis matches loop-collapse** — plain observation-conditioning
under-constrains the null-space over long spans → generic/smooth collapse; their remedy (a second
term steering toward a *retrieved reference*) is an **inference-time complement to our learned
inpaint-conditioning channel**. **(2) Retrieval-as-conditioning within a track** — retrieving the
guide from the *same song's other sections* exploits music's self-similarity; for our long-form
generation, retrieving from already-generated earlier sections could **enforce motivic consistency
and fight loop-collapse** (turns repetition from hazard into signal). **(3) Boundary-continuity
refinement** (minimize discontinuity at both gap edges + short cross-fade) is a concrete recipe for
our **transition/join seam** problem, independent of the diffusion core. **(4) Uncertainty-weighted
dual conditioning** (`ω_y` vs `ω_x̃`, with `ω_x̃` critical and match-quality-dependent) argues for
**confidence-gated conditioning strength** — don't weight a weak inpaint/reference condition too
hard. What remains ours: latent-domain re-derivation of retrieval+continuity, the RF sampler, the
SAME domain, and the disintegration gate.
