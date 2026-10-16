# Spectral Allocation: Why Muon Outperforms Adam, and How to Improve Muon (SAMuon)

- **arXiv:** 2608.25990v1 (2026-08-26, cs.LG)
- **Authors:** Xiaodong Wu, Wenyi Yu, Chao Zhang, Philip Woodland (Cambridge, Tsinghua)
- **PDF:** `papers/arxiv-2608.25990.pdf` (laptop copy; PDFs are untracked)
- **Read by:** KUANG, 2026-10-17: main text + appendices G (setup, sweeps, NS coefficients, timing) and I (per-module
  alignment) read; convergence proofs (appendix F) skimmed.

## What it contains

- **Out-of-sample spectral probing.** At saved checkpoints, add one gradient batch to the stored momentum, take its SVD,
  and for each rank d build a probe from the d-th singular component of every 2-D matrix (same sign and Scion scaling
  the optimizer would use). On a DISJOINT batch, estimate the loss-optimal step along each probe with a local quadratic
  (gradient + one finite-difference forward pass). 20 held-out batches per point; 0.52% of probes filtered.
- **Finding (64M and 124M modded-nanogpt, Muon and AdamW trajectories):** the profile is stable across batches and
  checkpoints after ~200 iterations. Rank 1 (the "volatile head", most of the gradient energy) tolerates the smallest
  step, and that step equals Muon's actual lr: the head is at the edge of stability. The rest (the "bulk") tolerates
  ~5x more, rising roughly linearly in log rank up to rank ~32 (width 512), then flat. In-sample probing (on the
  gradient batch itself) is far more optimistic about the tail: it measures refitting, not generalisation (appendix D).
- **Account of optimizers:** SGD allocates step in proportion to singular value (wrong way round), Adam damps that,
  Muon flattens it (all directions at the head's limit). That spectral reallocation, not spectral-norm control, is
  their explanation of Muon's speed.
- **SAMuon:** O = gamma * NS(M) - sum_{i<=k} (gamma - s_i) u_i v_i^T: head held at Muon scale, bulk raised to gamma.
  SAMuon-lite = k = 1 via 10-14 power-iteration steps (+0.5% iteration time); full SAMuon = randomised SVD, k =
  32*sqrt(d/512), log-rank-linear ramp (+7.4%). gamma ramped in over the first 30% of training (cosine). gamma = 1 is
  exactly Muon. Best gamma 7.07 (SAMuon) at every batch size.
- **Results:** 124M-1B, batches 1024-4096 sequences (1-4M tokens), trapezoidal schedule, one seed per configuration,
  baseline = unconstrained Scion. Final loss -0.013 to -0.030; 13.3-24.0% fewer tokens (lite 13.3-22.1%). The gain
  GROWS with batch size (their reading: less noisy spectral estimate).
- **Appendix I:** sign agreement of each rank's direction with unseen-batch gradients is poor in the tail, worst for
  attention Q and K. Tail directions deserve the least trust.

## What it does not contain / what remains ours

- Nothing at small batch (our LatCH heads b16, FiLM 1 crop x accumulation 2, DoRA 32), nothing with Schedule-Free, no
  NorMuon interaction, no fine-tuning or adapters, no audio. Single seed per cell.
- In OUR pipeline NorMuon rescales rows after Newton-Schulz, so a uniform gamma applied before it is cancelled (same
  mechanism as the routing radius, TRAINING.md F22): SAMuon would have to be applied after NorMuon.

## For us

- **The probing method is the valuable part**, and it is cheap at LatCH-head scale: build the held-out directional
  probe before any optimizer change (test plan section P).
- It offers a second explanation of our LatCH lr ceiling (1e-2; 3e-2+ diverges): the head at edge of stability,
  versus the over-fast sign group (TRAINING.md F24). Plan section B can discriminate the two.
- Do NOT read it as "orthogonalise less to save time": the gain lives in the bulk.
