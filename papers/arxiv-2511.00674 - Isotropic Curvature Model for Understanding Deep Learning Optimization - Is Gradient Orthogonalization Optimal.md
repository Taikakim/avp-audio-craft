# Isotropic Curvature Model for Understanding Deep Learning Optimization: Is Gradient Orthogonalization Optimal? (2511.00674v1) — deep-read

Weijie Su (University of Pennsylvania), arXiv math.OC, 1 Nov 2025. PDF beside this note. **Read by C
2026-09-26 (§1–3 and §5 in full; proofs in §4 skimmed).**

## What it shows
- A one-step model of the loss change for a matrix update Q: `min −Tr(Q Gᵀ) + E_{ζ∼sphere} H(‖Qζ‖)`,
  assuming the curvature (Hessian and higher terms) is ISOTROPIC over perturbation directions and depends
  only on the perturbation's size through a function H. Convex, analysable.
- **Theorem 1 (super-quadratic growth of H):** the optimal update keeps G's singular vectors, and its
  singular values (a) keep G's ordering and (b) are MORE HOMOGENEOUS: every ratio σ*_i/σ*_j is at most
  σ_i/σ_j. "Spectrum homogenization", not flattening.
- Worked example H(r) = c r⁴: each optimal singular value solves `σ*³ + D σ* = n(n+2) σ / (8c)` with D
  shared across the spectrum. Large σ are compressed (≈ σ^{1/3}); **small σ stay ≈ proportional to σ,
  i.e. stay small.**
- **Theorem 2:** full orthogonalisation (all σ* equal, Muon) is optimal only when the curvature has a sharp
  phase transition in growth. Measured curvature on GPT-2 small: quadratic at small r, then super-quadratic
  with exponent 2 + α, α ≈ 0.2–0.5 (Fig. 1), not a sharp transition. So orthogonalisation is "directionally
  correct but not strictly optimal".
- Notes that **Newton–Schulz polynomial approximations are generally not monotone**, violating (a), and
  proposes monotone spectrum maps as future work. Cites that rough and exact orthogonalisation perform
  similarly in LLM pretraining.
- Theory plus a curvature measurement; **no optimizer experiments.** Single author.

## FOR US / what stays ours
- **Our `cubic5` map (lmo.py `_CUBIC5_COEFFS`), traced 2026-09-26 on singular values after Frobenius
  normalisation:** 0.001 → 0.12, 0.01 → 1.02, 0.1 → 0.80, 0.3 → 1.11, 1.0 → 0.77, maximum 1.30.
  (1) It lifts weak directions ~100× to full strength; for a rank-128 factor weak directions sit near
  0.01, and those are the most noise-dominated (2602.03001: at low spectral SNR the polar factor is
  effectively random). (2) It is **not monotone**: the strongest direction comes out below weaker ones,
  against Theorem 1(a).
- **A noise-estimate-free lever:** a monotone partial map (e.g. σ → σ^p, p ≈ 0.3–0.5, or a monotone
  polynomial with bounded small-σ gain) keeps weak, noisy directions weak by construction. For rank-128
  LoRA factors the exact spectrum is cheap (128×128 Gram on the rank side). Testable as an LMO variant on
  the goa5k ablation chain against cubic5, with ‖lora_B‖ trajectory, loss and ears.
- Caveats: isotropy is an assumption the author wants justified; rough-vs-exact parity at scale suggests
  the map's details may matter little in practice. A hypothesis to test, not an established fix.
