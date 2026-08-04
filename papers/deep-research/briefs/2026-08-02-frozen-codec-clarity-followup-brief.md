# Gemini follow-up brief — three open questions on frozen-codec HF clarity

*(CONTINUITY 2026-08-02, follow-up to the frozen-codec-clarity brief + your excellent
answer. Same rules: fact-dense, audio-demonstrated evidence, falsifiable, real citations,
a confirmed gap is a valuable answer. Do NOT restate SAME/IFGD/phase-wrapping/BigVGAN —
assume all prior context. Paste whole.)*

## Context carried over (do not re-derive)
Frozen SAME-L codec, 256-ch @10.77 Hz, 4096×. >7 kHz round-trip phase coherence 0.045
(regression cannot recover → must generatively hallucinate). Prior answer established:
audio-domain generative post-net > latent bridge (frozen decoder can't interpret hallucinated
HF phase; VoiceBridge needed EP-VAE + decoder co-tuning). Latent covariance: 786× anisotropic,
1/f α≈−1.12, 188/256 eigendirections below the velocity-target unit-noise floor. Planned:
(A) generative pseudo-complex audio post-net (ADAA-SnakeBeta + multi-period-discriminator +
AW-GD as phase stabilizer); (B) DiT-side post-hoc Cholesky latent whitening + v-pred/ZTSNR.

## Q1 — Latent conditioning of the audio post-net.
Our post-net operates on the decoded WAVEFORM. Would additionally conditioning it on the
SAME LATENT (the 256-ch @10.77 Hz sequence that produced the waveform) raise the generative
phase-hallucination ceiling — i.e. does the latent carry macro-structural information (the
slow envelope, chroma, ILD that SAME regresses in) that helps a post-net synthesize coherent
HF phase beyond what the decoded audio alone provides? Any audio-restoration / vocoder-refiner
result where conditioning a waveform post-net on the generator's OWN latent/intermediate
features measurably improved HF phase coherence or transient fidelity? Or is the decoded
waveform a sufficient statistic (latent adds nothing post-decode)?

## Q2 — Redundancy vs additivity of the three DiT-side HF fixes.
For the 188 low-variance latent directions swamped by the velocity-target noise floor, three
interventions are on the table: (a) post-hoc latent whitening (Σ→I, isotropic target),
(b) x0-prediction target, (c) v-prediction + zero-terminal-SNR. Are these REDUNDANT (they fix
the same failure mode — low-variance directions get no gradient — so one suffices) or
ADDITIVE/orthogonal (whitening fixes the target geometry, ztSNR fixes the terminal-leakage
hiding spot, v-pred fixes the parameterization)? Is there a principled reason whitening could
make x0 vs v vs ε-prediction equivalent (isotropic target removes the variance-weighting that
distinguishes them)? Any diffusion result that combined latent normalization with target/schedule
changes and reported whether the gains stacked?

## Q3 — Measured audio evidence for v-pred + ZTSNR in a FIXED music latent (you flagged this gap).
You noted numerical audio deltas for v-prediction vs ε-prediction in a fixed audio latent
space are sparse. Push hard on this: is there ANY measured result (LSD, ViSQOL, FAD, MUSHRA)
for v-pred and/or zero-terminal-SNR specifically improving HIGH-FREQUENCY detail or dynamic
range in a latent audio diffusion model (music preferred, speech acceptable) — as opposed to
image generation or theoretical/flow-matching-analogy arguments? If the answer is a firm "no
direct audio measurement exists," say so explicitly — that tells us this must be settled by
our own ablation, and we will run it.

## Anti-play-acting constraints
Real citations only; a confirmed gap is the most valuable answer here (esp. Q3). Separate
established / contested / synthesis. Prefer audio-demonstrated, measured deltas; flag
image-only or theory-only support explicitly. State for each proposed mechanism whether it
needs codec retraining (disqualified). Give a falsifiable prediction + the confirming metric.
