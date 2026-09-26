# DP-aware AdaLN-Zero: Taming Conditioning-Induced Heavy-Tailed Gradients in Differentially Private Diffusion (2602.22610v1) — deep-read

Huang, Meng, Yang, Hou, Chen. arXiv preprint, Feb 2026. PDF beside this note. **Read by C 2026-09-26
(method, Fig. 1, setup, ablation headings; proofs skimmed).**

## What it shows
- In conditional diffusion transformers with **AdaLN-Zero** modulation, the conditioning pathway (the
  projections mapping condition c to (γ, β, α), plus parameters on the injection path) acts as a gain
  control and produces **rare, extreme per-example gradients**.
- **This holds without differential privacy too (Fig. 1, normal training):** ‖g_cond‖ is comparable to
  ‖g_other‖ at typical quantiles but has a much heavier high tail. With their bounds, p99 of ‖g_cond‖ drops
  **~3.5×** vs ~1.2× for ‖g_other‖: targeted tail suppression, not uniform shrinkage.
- **Fix ("DP-aware AdaLN-Zero"):** per block, ℓ2-project the condition (‖c‖ ≤ c_max), then bound each
  modulation coordinate with `B_M(x) = M·tanh(x/M)` (|γ| ≤ γ_max, |β| ≤ β_max, |α| ≤ α_max). A forward-pass
  constraint, applied before gradients; DP-SGD itself is unchanged. Gives a worst-case per-example gradient
  bound (Prop. 3.1).
- Motivation is DP: one global clip threshold means conditioning outliers force aggressive clipping of the
  whole gradient.
- **Scale/setting:** time-series diffusion (interpolation, imputation, forecasting); a Transformer with
  **8 layers, hidden size 256**, trained from scratch; PrivatePower + two ETT benchmarks. Extending to
  pretrain-then-finetune is listed as future work.

## FOR US / what stays ours
- **Independent support for our observation**: all five flight-recorder spikes on the shampoo run
  (2026-09-25) sat in the conditioning-input layers (`to_cond_embed`, `global_cond_embedder`,
  `project_in`), in LoRA `B`, with normal loss — and r256's DoRA magnitudes crossed zero in the same
  family. It also joins the 2026-08-11 drone-cluster convergence (output projection + AdaLN modulation as
  the unstable part; knowledge.md "Training-stability / optimizers").
- **Their fix changes the forward function.** On a pretrained 1.4B DiT, tanh-bounding the modulation or
  projecting c alters outputs unless the bounds sit above the pretrained operating range, so it is a
  last-resort architectural change for us, not a drop-in. A fine-tuning-safe analogue would bound only
  the adapter's contribution on those layers.
- **Their per-partition gradient diagnostic is the one to copy**: log ‖g_cond‖ vs ‖g_other‖ quantiles
  (p90/p95/p99). The flight recorder already has per-tensor norms; add a conditioning/other split.
- Small, from-scratch, time-series, one group: evidence of mechanism, not of a fix at our scale.
