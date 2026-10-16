# Free Heavy-Tailed Lunch for Muon: A Theoretical Justification of Empirical Success

- **arXiv:** 2606.14560v1 (2026-06-12, math.OC)
- **Authors:** Florian Hübler, Thomas Pethick (Scion's author), Suvrit Sra (ETH Zurich, TU Munich, MCML)
- **PDF:** `papers/arxiv-2606.14560.pdf`
- **Read by:** KUANG, 2026-10-17: introduction, main results (statements), experiments, appendix F read; proofs
  (appendices A-E) skimmed.

## What it contains

- Normalised steepest descent with momentum under HEAVY-TAILED gradient noise (bounded p-th moment, p in (1, 2]), with
  the noise assumption stated in the optimizer's own geometry. For uniformly smooth dual norms: optimal sample
  complexity for stationarity in that norm. For Muon (nuclear-norm stationarity): O(min(m,n) * ...) samples, absorbing
  heavy-tailed noise without the extra p-dependent dimension factor Euclidean methods pay; a matching first-order
  lower bound (so Muon is optimal for this measure).
- **Experiments:** Pythia-70M on FineWeb-Edu, 1.4B tokens, batch 512, 3 seeds. (a) Measured nuclear-vs-Frobenius noise
  ratio per matrix is well below the worst case and lower at initialisation. (b) Schatten-r steepest descent, r from 1
  to infinity: perplexity 88.9 (r=1), 40.2 (r=2, Euclidean), 34.5 (r=3), 33.5 (r=4), 33.0 (r=8), 33.3 (r=inf, Muon):
  sharp gain up to r~3, then a plateau, consistent with tail index p~1.5. (c) Embedding layers fit an l-infinity
  (sign / Adam-like) geometry better than a Schatten one.
- Authors' own conclusion: intermediate r needs a full SVD; Muon (Newton-Schulz) remains preferable.

## What it does not contain / what remains ours

- No audio, no fine-tuning, one small model and dataset. Idealised updates (exact polar, no Newton-Schulz error).
- No practical recipe for choosing r; the r ~ p/(p-1) link is a consistency argument, not a tuning rule.

## For us

- Supports keeping the spectral geometry for hidden matrices; nothing to build.
- Side note for routing: embeddings may prefer per-element (sign/Adam) updates; our routing sends them to colnorm.
