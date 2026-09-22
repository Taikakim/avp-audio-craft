# Mousse: Rectifying the Geometry of Muon with Curvature-Aware Preconditioning

- **arXiv:** 2603.09697v2 (2026-03-11, cs.LG)
- **Authors:** Yechen Zhang, Shuhao Xing, Junhao Huang, Kai Lv, Yunhua Zhou, Xipeng Qiu, Qipeng Guo, Kai Chen — Shanghai Jiao Tong University, Shanghai AI Laboratory, Fudan University
- **Official code:** https://github.com/Anti-Entrophic/Mousse (cloned locally to `/home/kim/Projects/Mousse`)
- **PDF:** `papers/Prospective Unchecked/2603.09697v2.pdf`
- **Read by:** CONTINUITY, 2026-09-22 (Algorithm 1 and §3.2 verified against the PDF directly)

## What it contains

**Mousse = Muon Optimization Utilizing Shampoo's Structural Estimation.**

The claim: Muon imposes an *isotropic* trust region — Newton-Schulz forces every singular
value to 1, enforcing a uniform spectral norm across all eigen-directions. Real network
curvature is heavy-tailed and ill-conditioned, so this "egalitarian" constraint amplifies
instability in high-curvature directions while under-stepping flat ones. Mousse changes
basis first: whiten with Shampoo's Kronecker factors, run Newton-Schulz in the whitened
frame, then unwhiten.

Closed form (p5):

    dW = -L^(-1/4) msign( L^(-1/4) G R^(-1/4) ) R^(-1/4)

**Results:** ~12% fewer steps to a target loss than Muon at ~3% wall-clock overhead, on
GPT-2 decoder-only models 160M-800M over 20B FineWeb tokens, beating AdamW, Muon and SOAP
across a peak-LR grid at every scale.

### Algorithm 1, the parts that matter

1. `M <- beta*M + G`
2. `L <- b_pc*L + (1-b_pc)*G G^T`,  `R <- b_pc*R + (1-b_pc)*G^T G`
3. every `T` steps only:
4.   **Trace Normalization**: `Lbar <- dim(L)/(Tr(L)+eps) * L` (likewise R)
5.   `Q,Lambda <- Eigh(Lbar + eps*I)`
6.   **Spectral Tempering**: `S <- Lambda^(-alpha)`, alpha a TUNABLE curvature exponent
7. Whitening: `M_eig <- Q_L^T M Q_R`, `Mtilde <- S_L M_eig S_R`
8. `Mbar <- NewtonSchulz(Mtilde)`, **`gamma <- ||Mbar||_F`**
9. Unwhitening: `U_eig <- S_L Mbar S_R`, `U <- Q_L U_eig Q_R^T`
10. **`U <- gamma * U/||U||_F`**
11. `theta <- theta - eta*U`

## Three details that are easy to get wrong

**The "unwhitening" uses the SAME negative powers, not their inverses.** Line 9 applies
`S_L`/`S_R` a second time, and the p5 closed form confirms `L^(-1/4) ... R^(-1/4)` on both
sides. It reads like a bug and is not one. Our `KLShampooPreconditioner.inverse_transform`
returning `P_L @ M @ P_R` is CORRECT per the paper.

**The gamma renormalization is load-bearing.** Because the double whitening distorts
magnitude, line 8 saves the Frobenius norm that Newton-Schulz produced and line 10 restores
it. Without it the update magnitude is whatever the whitening leaves behind. This is the
most likely reason naive whitening blows up.

**Trace Normalization and Spectral Tempering are named by the paper as its two critical
stability techniques** (§1, "Robust Engineering Insights"), not as incidental details.
Bias correction is not a substitute for trace normalization, and a hardcoded alpha=0.25 is
not spectral tempering.

## Section 5.3 and Figure 7 — the ablations, read directly

**Single-sided IS validated (section 5.3).** "We investigate a variant of Mousse that employs a
single-sided preconditioner substituting the full Kronecker product R (x) L with only one
factor... achieves comparable performance to the Mousse baseline, yielding a negligible
decline or even slight improvements." Halves both eigendecomposition cost and preconditioner
memory. So one-sided is a validated variant, not a cost dodge.

**But the paper has a PREFERRED side, and it is not the one we can afford.** "Using the
left-sided preconditioner (L) is consistently slightly better than the right-sided
preconditioner (R). We hypothesize that this advantage stems from the presence of the
preceding LayerNorm, which typically standardizes the input activations (whose statistics are
captured by L)." We choose by SIZE, so on a (12288, 128) LoRA factor we take the side the
paper found slightly worse -- the better one is the 12288x12288 we cannot build.

**alpha = 0.125, NOT 0.25 (Figure 7a).** "Trace Normalization is essential for stability.
Furthermore, Spectral Tempering (alpha = 0.125) consistently outperforms the aggressive
curvature correction (alpha = 0.25), yielding the lowest final loss." Our default is now
0.125. The same figure independently confirms trace normalization was worth fixing.

**Their own implementation is a proof of concept (section 6.2):** "significant headroom for
system-level optimizations, such as adopting power iteration with QR decomposition or
Newton-Schulz iteration for spectral decomposition instead of naive torch.linalg.eigh."
That is the same opening DASH exploits, and the same one our batching measurement points at.

## A degeneracy to watch for under one-sided whitening

KL-Shampoo (2509.03378) proves two things that bear on our configuration:

- **Claim 1**: the KL-optimal ONE-SIDED preconditioner is exactly `S_a* = E[G G^T]` -- the plain
  covariance. So in one-sided mode, plain Shampoo IS KL-Shampoo. The distinction only returns
  if the bottleneck is turned off.
- **Short-sided KL-Shampoo recovers scaled Muon when momentum is disabled** (d_a < d_b).

The second is worth taking seriously. With `G = U D V^T`, left-whitening gives
`(G G^T)^(-alpha) G = U D^(1-2alpha) V^T`, and Newton-Schulz maps that to `U V^T` -- identical
to `msign(G)` for ANY alpha. The forward whitening is annihilated by the orthogonalization.
What survives is the UNWHITENING, which yields `U D^(-2alpha) V^T` renormalized by gamma: a
spectral reweighting, i.e. a softened Muon.

That algebra is exact only when the preconditioner shares eigenvectors with what it multiplies
-- no momentum, no EMA on the covariance. We use both, which is why the paper's equivalence
carries the "when momentum is disabled" qualifier. But it means one-sided whitening can quietly
collapse toward plain Muon, and that is a thing to MEASURE rather than assume.

## Mousse vs SOAP — the paper's own argument (p6)

> SOAP relies on running a complete AdamW optimizer within the rotated frame, necessitating
> an additional second-momentum state v. Mousse ... eliminates the need for the redundant
> second-momentum state, effectively synthesizing curvature-awareness with the memory
> efficiency of Muon.

FOR US this is decisive: our checkpoints are already 3.1 GiB with four full-size optimizer
buffers per parameter on a 16 GB card. Mousse composes with the Newton-Schulz path we
already have instead of replacing it with AdamW, and adds no per-parameter state beyond the
Kronecker factors.

## FOR US / what stays ours

- Mousse operates on full weight matrices of an LLM. **Our shapes are LoRA/DoRA factors**
  where one side is the rank (128) and the other is up to 12288. Forming `L = G G^T` on the
  wide side is a 12288x12288 covariance; measured on our card a single such eigh takes
  **7.23 s**, so the paper's Algorithm 1 applied naively to our 24 tensors of that shape is
  173 s per step. Restricting the preconditioner to the rank-128 side takes the whole set
  from 27.9 GiB to 28.6 MiB. That restriction is ours to make; the paper does not need it.
- Trace normalization, spectral tempering and the gamma restore transfer unchanged.
- The isotropy critique is interesting for audio specifically: our own measurements show
  NorMuon row scaling ACTIVE (max deviation 0.246) while several other mechanisms sit at
  identity, which is consistent with per-neuron scale heterogeneity being real in the DiT.

## Related, read alongside

- `2509.03378v10` KL-Shampoo — the coupled `S_a <- (1-b)S_a + (b/d_b) G S_b^-1 G^T` estimator.
  Inherently TWO-sided, so it does not apply under one-sided bottleneck preconditioning.
- `2602.02016v2` DASH — batched block preconditioning. Measured on our shapes: batching 458
  128x128 eigendecompositions into one call is **52.8x** faster than looping them.
