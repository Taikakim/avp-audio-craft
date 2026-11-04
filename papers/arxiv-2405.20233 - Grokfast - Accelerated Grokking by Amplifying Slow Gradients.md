# Grokfast: Accelerated Grokking by Amplifying Slow Gradients (2405.20233)

Lee, Kang, Kim, Lee (Seoul National University). arXiv v2, June 5, 2024; "under review" in the PDF, venue not stated.
Code: github.com/ironjr/grokfast (MIT). Reviewed separately in `arxiv-2405.20233 - Grokfast - code (ironjr-grokfast).md`.
PDF: `arxiv-2405.20233 - Grokfast - Accelerated Grokking by Amplifying Slow Gradients.pdf` (gitignored; added locally on the desktop).
**Read:** the whole PDF: main text, appendix A (filter equivalence proof), appendix B (task details) and appendix C (code). Deep-read by KUANG, November 4, 2026; it replaces the abstract-only entry (C, September 22, 2026).

## What it contains

- **Idea.** Treat each parameter's gradient sequence over training steps as a signal. The paper assumes the fast part drives overfitting and the slow part drives generalization, and amplifies the slow part.
- **Grokfast-MA (Algorithm 1).** g_hat = g + lambda * mean(last w gradients). Best on modular arithmetic: w = 100, lambda = 5, from a grid over lambda in {1, 2, 5, 10} and w in {2 ... 200}. It needs w copies of the gradients: 100x the model in memory, and 2.4x the time per iteration.
- **Grokfast-EMA (Algorithm 2, the recommended one).** mu = alpha * mu + (1 - alpha) * g; g_hat = g + lambda * mu. One extra buffer the size of the model. Recommended ranges: lambda in [0.1, 5], alpha in [0.8, 0.99].
- **Where the filter sits.** On the gradient, before any optimizer.
  - Appendix A proves that filtering the gradient equals filtering the update, but only for linear optimizers (SGD, momentum, Nesterov).
  - For Adam and AdamW, which normalize per coordinate and are nonlinear, the claim rests on the experiments alone.
- **Section 5.1** argues it differs from optimizer momentum: the smoothed gradient is added as a residual to the raw gradient, before the optimizer.

## Evidence

| Task | Setup | Result |
|---|---|---|
| x * y mod 97 | 2-layer Transformer, 128 wide, 4 heads; Adam, lr 1e-3, batch 512, 50 % train split | MA alone: 13.57x fewer steps to 95 % validation accuracy. MA with weight decay 0.01: **50.49x**, the headline. EMA (alpha 0.98, lambda 2, weight decay 0.005): 43.84x. |
| MNIST | 3-layer MLP; **1 000 training images, initialization 8x Kaiming**; AdamW; MSE loss | EMA (alpha 0.8, lambda 0.1, weight decay 2.0): grokking delay 22x shorter; final accuracy 89.8 % -> 91.2 %. |
| QM9 | Small graph ConvNet; **first 100 molecules**, 50:50 split; initialization 3x Kaiming | EMA (alpha 0.9, lambda 1.0, weight decay 0.01): validation loss falls faster and lower (figure only). |
| IMDb | 2-layer LSTM; **first 1 000 reviews**; large initialization | EMA (alpha 0.98, lambda 2, weight decay 10.0): best validation accuracy 0.84 -> 0.90; minimum validation loss 0.517 -> 0.412. |

- **Ablations** (section 2.3):
  - The slow component alone, replacing the gradient, is slower and unstable. Both components are needed.
  - Switching the filter on only after overfitting (step 500) gives another 1.53x.
  - Weight decay alone (no filter) made training unstable; together the two are "synergistic".
- **Trajectories** (section 5.2: PCA of all 423k parameters, 5 samples in figure 12b):
  - With Grokfast, the final model is about 16x closer to the initialization.
  - At the overfitting point it is about 8x further from the initialization than the baseline's.
  - The spread of distances across runs is about 100x smaller.
  - The baseline and Grokfast end states are not claimed to be the same solution.
- **Limits stated by the authors.**
  - MA's memory cost.
  - The source of the determinism is left open.
  - Weight decay and the filter's cutoff are task dependent and found by grid search.

## How far the evidence reaches

- **Every task was built to grok.** The datasets are cut to 100–1 000 items, the initializations are 3–8x too large, and the weight decays are as high as 10. Nothing is pretrained and nothing is near our scale.
- **Effect sizes are mostly single runs.** The only spread shown is the 5-sample trajectory plot. The large speedups are on modular arithmetic; on real data the gains are a few points.
- **The "slow = generalizing" premise is a working hypothesis.** It is supported by the speedups, not tested directly.

## For us

**LOW relevance, unchanged from the abstract-level verdict; now on a full read.**

- **Our optimizers remove most of it.**
  - Under Newton–Schulz (Fusion, modular NorMuon), the update's magnitude is normalized away. What remains is a mix of a fast and a slow momentum direction, which our momentum beta already partly spans.
  - Under AdamW, per-coordinate normalization also absorbs much of the (1 + lambda) gain.
  - The paper has no proof for either optimizer.
- **Our regime is not grokking.** We fine-tune a pretrained 1.4B rectified-flow DiT and judge by ear. Diffusion models are argued to generalize first and memorize only later with more training. That reverses grokking's order, so "train longer and wait" is a memorization risk for us, not a generalization payoff.
  - Lead: Bonnaire, Urfin, Biroli, Mézard 2025, "Why Diffusion Models Don't Memorize". Cited from memory, not read, not indexed.
- **If a slow-momentum mix is wanted,** test it as an optimizer in the AdamW arm, not as a gradient hook.
  - Lead: AdEMAMix (2409.03137). Not read, not indexed.
- **One connection worth keeping (our interpretation, not the paper's claim).** Grokfast amplifies the persistent direction of the updates. Scaling a finished fine-tune's change past 1x (base + w * (ft - base), w > 1) is the same move done once, after training.
  - The paper's trajectory result, a solution closer to the initialization, fits our observation that such pushes did not collapse the output.
  - The likely reason on our side is architectural: pre-norm RMSNorm and per-head q/k RMS norm absorb scale, and only the layers that write to the residual stream carry magnitude.
  - It is untested here; a group-restricted w ladder is the test.

## What stays ours

The model, data, objective and optimizers are unchanged by this read. Nothing from the paper is adopted. The pieces worth keeping: the signal-processing view of training (gradients as a time series with a cutoff frequency), which is already how our momentum and EMA horizons are reasoned about; and the trajectory-distance readout (distance from the initialization, spread across runs), which matches our `path_eff` and `step_cos` meters.
