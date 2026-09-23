# Triage — "Scale-Aware Optimization of Gain Parameters Under Sign-Type Optimizers" (Gemini deep research)

> **Provenance.** The actual deep-research reply to `briefs/2026-09-23-dora-magnitude-sign-step-brief.md`
> (8 pp., 23 works cited), received 2026-09-24 as `DoRA_Magnitude_Optimization_Research.pdf`. It supersedes
> the earlier reconstruction (`2026-09-24-dora-magnitude-scale-aware-triage.md`). Triage: CONTINUITY.

## Citation check (arXiv abstract pages, 2026-09-24)

| claim | source | verdict |
|---|---|---|
| Muown: row-magnitude as a separate optimizer variable under ℓ∞ geometry, Muon on the direction | 2605.10797 (Lion, Hübler, Li, Orvieto, He) | **verified, accurate** |
| LionVote: Lion ~2× too high for normalization params; per-layer compound LR level | 2607.09266 | **verified** (per parameter TENSOR, not per element; ViT-Tiny/CIFAR-100 only) |
| M+Adam: additive + multiplicative combined (additive handles sign changes/small magnitudes, multiplicative large ones) | 2607.10611 (Liang, Loeschcke, Toftrup, Anandkumar) | **verified at abstract level**; equations not checked |
| Madam (multiplicative Adam) | table cites 2607.10611; the ORIGIN is Bernstein et al., NeurIPS 2020, "Learning compositional functions via multiplicative weight updates" (in its works cited) | method real; **table mis-attributes the id** |
| DoRAN: learnable term in the DoRA **denominator** | 2510.04331 (Diep, Dang, Truong, Dinh, Nguyen, Ho) | paper real, but **§2's claim is wrong**: DoRAN addresses the *direction norm* ‖W0+BA‖ approaching zero, NOT the magnitude m. The abstract never mentions m. Presenting it as "the exact failure mode of DoRA magnitude vectors drifting toward zero" is a conflation. |
| Stable-LoRA, BiDoRA, LoRA+, OP-LoRA, EGU, SymExpLin, LoRMA, MERIT, MuonAll | various | not checked (not load-bearing for our decision) |

§2's opening ("extensive, explicitly documented failure states that identically match") overstates it.
What the sources actually show: sign/normalised optimizers miscalibrate 1-D parameters (LionVote), and
row-magnitudes drive Muon's norm drift (Muown). **No source reports DoRA magnitudes crossing zero.**

## What our own data adds (checked the same day)

In the abort checkpoint, **the magnitudes are all finite**. The NaNs are in `lora_A`/`lora_B` of all
228 adapted modules. At step 6340, the conditioning path already had rows with |m| down to 2.6e-5:
18 rows below 1e-3 in `to_global_embed.0`. So the likely chain is: tiny or zero-crossed magnitudes in
the global-conditioning path, whose output feeds every block's AdaLN; then non-finite activations;
then NaN gradients into every A/B. The magnitudes cause it but don't themselves go NaN. **DoRAN's
point becomes relevant after all, for a different reason than the report gives:** these layers' rows
are tiny to begin with (m at init = ‖W0‖_row ≈ 0.13). So the DoRA normalisation's 1/‖W0+sBA‖ gradient
factor is also large there. That's a second route to the same explosion. *Inference; not verified by
computing ‖W0+sBA‖_row.*

## Verdict

1. **Build the multiplicative magnitude step** (Madam-style, m ← m·exp(−η·sign(momentum))): it's
   scale-relative, and positivity is guaranteed. The report and its predecessor agree on this. M+Adam's caveat (a
   pure multiplicative step can't cross zero when that's optimal) doesn't bite: a DoRA magnitude is a
   row norm and should never be negative.
2. **Muown is the principled version** for the transformer blocks (magnitude under its own geometry), and
   worth a deep-read later. It's also the closest published analogue of our whole modular set-up.
3. **DoRAN's denominator term** is an option to test ONLY if multiplicative magnitudes still NaN.
4. Kim's "free early, then constrained" still has no direct source. Stable-LoRA's early-only shrinkage of A
   (2603.05204, unverified) is the nearest schedule-shaped precedent.
