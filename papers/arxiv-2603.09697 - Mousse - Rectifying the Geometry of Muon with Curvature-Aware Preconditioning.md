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
