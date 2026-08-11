# Rectified-CFG++ for Flow-Based Models (2510.07631)

*Project-POV abstract, THE-FINN 2026-07-30. Saini, Gupta, Bovik (UT Austin — LIVE lab).
**NeurIPS 2025.** Text-to-image (Flux, SD3/3.5, Lumina), but the target problem is
**rectified-flow-specific**, so it ports to SA3's family directly. **Abstract-level
(WebFetch of the arXiv abstract) — full PDF deep-read pending;** the theoretical guarantees
below are as the authors state them, not independently checked against the proof.*

**What it contains.** The paper's premise is a rectified-flow failure mode we care about:
"CFG is the workhorse for steering large diffusion models toward text-conditioned targets, yet
its native application to rectified flow based models provokes severe **off-manifold drift**."
**Rectified-CFG++** is a **predictor–corrector** guidance rule: (1) a **conditional update
anchored to the learned transport path** (predictor keeps the sample near the RF trajectory),
then (2) a **weighted correction interpolating between the conditional and unconditional
velocity fields** (corrector) — replacing naive CFG's raw extrapolation. The authors claim the
resulting velocity field is **marginally consistent** and that trajectories **remain within a
bounded tubular neighbourhood of the data manifold across a wide range of guidance strengths**.
Validated on Flux / SD3 / SD3.5 / Lumina over MS-COCO, LAION-Aesthetic, T2I-CompBench.

**Status vs our work — on-manifold anchor for strong steering.** **SA3 IS a rectified-flow
model**, so this is on-target rather than analogy: the "severe off-manifold drift under CFG"
the paper fixes is the *same disease* as our **disintegration / buzz gate** — the audible
grunge that appears when we push activation-steering strength or CFG too hard is the sound of
leaving the manifold. Rectified-CFG++ attacks it at the **sampler level** (predictor–corrector
geometry) where our gate attacks it at the **loss/measurement level** — potentially
complementary: the sampler keeps you on-manifold, the gate catches what leaks through. It's the
**deep-research brief's prescribed anchor for keeping strong activation steering on-manifold
under high CFG**, and it's testable on SA3 as-is (a sampler modification, no retraining). What
does NOT transfer: the image domain and its benchmarks (no audio analog); the tubular-
neighbourhood guarantee is stated for their setting and would need re-checking for SAME latents.
Open question worth a probe: how the corrector interacts with our **conditional-branch-only**
steering convention (does correcting toward the unconditional field blunt the steer?). What
remains ours: the audio manifold, the buzz gate, and the steering-under-Rectified-CFG++ test.
