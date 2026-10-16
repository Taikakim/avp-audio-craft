# PolarAdamW: Disentangling Spectral Control and Schur Gauge-Equivariance in Matrix Optimisation

- **arXiv:** 2605.07067v1 (2026-05-08, cs.LG)
- **Author:** Haozhou Zhang (University of Idaho), single author
- **PDF:** `papers/arxiv-2605.07067.pdf`
- **Read by:** KUANG, 2026-10-17: main text (sections 1-8) read; proofs (appendix C) and audits (A, D, E) skimmed.

## What it contains

- **PolarAdamW** = Newton-Schulz polar map applied to the AdamW-preconditioned direction m_hat / (sqrt(v_hat) + eps)
  instead of to raw momentum; shape scale sqrt(max/min); quintic NS5 in bf16; Muon-like wall time but Adam's full
  second-moment state.
- **Theory:** the polar step is equivariant under orthogonal basis changes of multiplicity spaces (Schur
  gauge-equivariance); AdamW's coordinatewise step is not.
- **Experiments:** DeiT-Tiny on four random 100-class ImageNet subsets, 4 paired seeds: PolarAdamW beats Muon by
  +1.93 pp (100 epochs) and +1.37 pp (300 epochs), both far above AdamW. On an SO(3)-equivariant point-cloud regression
  the order reverses (Muon better, gap growing with capacity; 100 seeds).
- Related designs it cites: Muon2 (Adam second moment before NS, language models), MuonEq (row/column equilibration
  before NS), Mousse (Shampoo whitening before NS).

## What it does not contain / caveats

- Framed by the author as a mechanism separation, not a new default optimizer. Small vision benchmark only.
- **Confound:** in the DeiT runs Muon's matrix step uses weight decay 0 while AdamW and PolarAdamW use 0.05.
- No Schedule-Free, no fine-tuning, no audio.

## For us

- Low priority. Mousse (the Kronecker version of "precondition, then orthogonalise") gave no measurable gain on our
  LatCH heads (EXPERIMENTS E5 Phase B), a weak prior against this family. Revisit only if the held-out probe shows
  coordinate-scale problems.
