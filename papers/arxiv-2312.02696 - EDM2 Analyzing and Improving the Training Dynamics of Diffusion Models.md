# EDM2 — Analyzing and Improving the Training Dynamics of Diffusion Models (2312.02696v2) — deep-read

Karras, Aittala, Lehtinen, Hellsten, Aila, Laine (NVIDIA), CVPR 2024. PDF:
`2312.02696 EDM2 - magnitude-preserving diffusion training dynamics (NVIDIA).pdf`.
Read at report level in the 08-11 twelve-paper synthesis (`knowledge.md` row → the drone frame);
**re-read in detail by C 2026-08-19 (pp. 1–12: §2 magnitude standardisation, §3 post-hoc EMA, §4
results, App. A) after Zach @ Stability flagged it to Kim.** The §3 half is the part we had under-read,
and it is the principled version of the soup / EMA thread of 2026-08-18/19.

## §2 — the training-dynamics half (drone frame; confirms what we found the hard way)
- Baseline ADM in EDM: activation AND weight magnitudes **grow without bound**, "no sign of tapering"
  (Fig 3, Config C). Cause named: residual main paths with no normalisation, and normalised weights
  → gradient ⟂ weight → every step lengthens the weight → **effective LR decays uncontrollably and
  unequally per layer**. That is W's 8× ‖ΔW‖ growth and our runaway, in 2024 print.
- Their fix ladder (Table 1, ImageNet-512 FID): 8.00 → tune 7.24 → streamline (remove biases, unify
  init, **cosine attention** for QK growth) 6.96 → **magnitude-preserving learned layers** (divide by
  ‖w_i‖ per output channel = weight-norm w/o learned scale) 3.75 → **forced weight normalisation +
  explicit inverse-sqrt LR decay** α(t)=α_ref/√max(t/t_ref,1) 3.02 → drop group norms (weak
  PixelNorm) 2.71 → MP fixed-function layers 2.56. **Config E is the key sentence for us: once
  weights are normalised "a constant learning rate no longer induces convergence", so they ADD an
  explicit decay.** Exactly the 08-19 finding: a magnitude-blind step (NS5+NorMuon or forced-norm)
  needs a schedule; SF/EMA averaging does not substitute.
- Loss weighting: continuous multi-task (Kendall) — track raw loss per noise level, scale by its
  reciprocal, because EDM's initial per-σ loss standardisation drifts during training (§2.1).
  Relevant to any per-t weighting we add (the R²(t) melody term).

## §3 — post-hoc EMA (the half that matters for soups; NEW for us)
- **Power-function EMA**: `θ̂_γ(t) = ((γ+1)/t^{γ+1}) ∫₀ᵗ τ^γ θ(τ)dτ`, incremental `β_γ(t) = (1−1/t)^{γ+1}`.
  Weight of the init is always 0; profile stretches automatically with training length; parametrised
  by relative width σ_rel (σ_rel 0.10 ⇔ γ≈6.94; 0.05 ⇔ γ≈16.97).
- **Post-hoc synthesis**: maintain TWO power-EMA averages during training (γ₁=16.97, γ₂=6.94),
  snapshot both every ~4096 steps; afterwards, ANY EMA profile (any length, even non-power) is
  reconstructed as the least-squares combination of the stored snapshots — error O(1/n⁴) in the
  number of snapshots, "a few dozen is more than sufficient" (Fig 4). Works, less accurately, from a
  single stored θ̂ per snapshot, so **old runs with plain checkpoint ladders can be revisited**.
- **What it revealed (Fig 5–6, App A.4):** the optimal EMA length depends on the architecture (B:
  flat and insensitive; G: sharp optimum at ~13 %), on training time (drifts longer), on model size
  and data complexity, and — strongly — on **guidance strength** (Fig 6: no-CFG optimum ~10–13 %,
  cfg 1.4 → ~2 %; the sweep is "totally different" under FD_DINOv2 vs FID, App A.5). Per-tensor
  sweeps (Fig 5b): in an unbalanced net individual tensors *disagree* about the best EMA length and
  a per-tensor choice can improve FID 10 %; in the balanced Config G they agree. LR decay and EMA
  length trade off (σ_rel ∝ 1/(α_ref² t_ref)); with post-hoc EMA a wide LR bracket is fine.

## FOR US
- **Soups = post-hoc EMA done by hand.** Our checkpoint ladders are the snapshots; `expasc` /
  `bell_late` / uniform are hand-picked profiles; Kim's "weight by PQ × crest × whitening" is
  post-hoc selection by a metric = precisely their FID-vs-EMA-length sweeps. Two upgrades this
  licenses: (1) **log two power-EMAs in `train_lora.py`** (trivial for adapters: two extra copies of
  the LoRA tensors) so any EMA length is reconstructible after the fact — a strict superset of the
  ladder-soup; (2) their finding that **the right EMA length depends on cfg** means Kim's cfg7 vs
  cfg16 cells plausibly want different soups — a testable claim on our boards.
- **Per-tensor disagreement** = the principled version of "per-layer soup weights"; W's per-block
  delta profiles already show adapters change layers unequally.
- **Config E** = the theory of last night: normalised/orthogonalised steps + constant LR = no
  convergence; add explicit decay. Their inverse-sqrt is a third schedule option next to
  cosine/WSD in `FusionOpt.decay_schedule`.
- **Forced weight normalisation** is the from-scratch structural drone cure (08-11 row stands);
  Hyperball is the fine-tune-safe cousin (pins ‖W‖ at the pretrained value); for an Adam-pretrained
  base the paper 2605.10468 caveat applies — don't reshape pretrained weights.
- **The irony the external note stated is right:** EDM2's unit-norm weights + explicit effective-LR
  control and Muon's spectral constraint are one idea; EDM2 reaches it without an optimizer swap.
