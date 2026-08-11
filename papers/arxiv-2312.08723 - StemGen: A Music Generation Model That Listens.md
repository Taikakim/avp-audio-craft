# StemGen: A Music Generation Model That Listens (arXiv 2312.08723v2)

**Parker, Spijkervet, Kosta, Yesiler, Kuznetsov, Wang, Avent, Chen, Le — SAMI / ByteDance,
ICASSP 2024.** (Julian Parker later co-authors Stable Audio 2 — 2404.10301.) Read via
subagent deep-read pass 2026-07-21 (CONTINUITY triage of Kim's prospective-unchecked batch).

## What it contains

- Task: **context-aware stem generation** — model hears a context submix (N of a song's M
  stems) and generates one musically-appropriate target stem. Conditional p(t|a), 20 s
  segments, no text.
- Data combinatorics as augmentation: a song with N stems yields (N/2)(2^N − 2)
  submix/target pairs. Slakh (145 h synthetic) + 500 h internal human-played stems; 18 GM
  instrument categories as the only semantic conditioning.
- **Wrong paradigm for us on both hard filters**: non-AR **masked-LM** (SoundStorm/VampNet
  family, LLaMA-style backbone, ~250M) over **discrete Encodec RVQ tokens** (32 kHz, 50 Hz,
  4 levels) — not RF, not a continuous latent.
- Architecture trick (token-space-specific): context-mix and target-stem embeddings (sum of
  per-RVQ-level codebook embeds, shared codebooks) concatenated along embedding dim into one
  sequence element; conditioning summed in.
- Novelty 1 — causally-biased iterative decoding: confidence ranking + small left-to-right
  position bias (w_s = 0.1 best: FAD 3.12/MIRDD 0.14 vs 3.18/0.32 without). Masked-LM-only;
  no RF analogue worth chasing.
- **Novelty 2 — multi-source CFG (the portable bit):** independent guidance scale λ_i PER
  conditioning source (audio context, instrument category), log p(t)·∏p(c_i|t)^λ_i,
  requiring **independent dropout per source during training**. Ablation: both sources
  guided at λ=3.0 → FAD 3.17/MIRDD 0.25 vs 4.30/0.41 unguided — guiding on the *audio
  context* source matters as much as the semantic one.
- **Novelty 3 — MIRDD eval metric:** averaged KL over distributions of MIR descriptors (key,
  pitch range/classes, note density, beats/bar, chord variety, tonality alteration,
  structure labels), computed on generated-stem + context mixes so **musical misalignment is
  penalized**, complementing FAD on isolated stems.
- Listening test (10 trained raters): real 3.64, best config 3.46, naive 2.89 — near-real.

## Project-POV

Adjacent-paradigm accompaniment paper; nothing here supersedes longform/LatCH/layer-landscape
work and the model itself cannot port to SA3. Two genuine exports:

1. **Multi-source CFG for sa3_control** — we juggle text + control-signal conditions; RF
   guidance composes the same way (Bayes on the velocity). Actionable check: does
   sa3_control training drop conditions *independently per source*? If not, that's a cheap
   change enabling per-source guidance scales at inference.
2. **MIRDD-style descriptor-KL** — conceptually adjacent to our Essentia sweeps; a
   population-level musical-coherence metric for control-adapter eval pages (their
   implementation leans on ByteDance transcription/beat/chord models; ours would use the
   Essentia stack).

Not covered: text conditioning at scale, long-form, latent diffusion/RF, adapters, layers.

*Provenance: subagent full-read (5 pp), reviewed by CONTINUITY, 2026-07-21.*
