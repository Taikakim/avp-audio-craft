# CoFrGeNet — Continued Fraction Architectures for Language Generation (2601.21766v4) — read

Dhurandhar, Chenthamarakashan, Wei, Pedapati, Ramamurthy, Nair (IBM Research), May 2026.
Preprint, under review. PDF: `reviewed-low-relevance/2601.21766v4-CoFrGeNet-Continued-Fraction-Architectures-for-Language-Generation.pdf`.
*Read + filed by WINTERMUTE 2026-08-03 (Kim's drop into prospective-unchecked). Verdict:
**interesting function class, NOT actionable for the SA3 pipeline** — filed low-relevance,
with two takeaways worth remembering below.*

## What it contains

**Function class.** Replaces transformer FFNs (and optionally attention) with ensembles of
learned **continued fractions** ("CoFrNet ladders"): `w₀x + 1/(w₁x + 1/(w₂x + …))`, partial
denominators affine in the input, depth d ≤ 7, L ladders wide with a linear layer on top.
That is a *rational-function* (Padé-flavored) approximator instead of piecewise-linear MLPs —
universal when ensembled (their NeurIPS'21 CoFrNet lineage, supervised setting; this paper is
the generative extension).

**1. The continuants trick (the engineering meat).** A continued fraction is a ratio of
continuants K_{d+1}/K_d (tridiagonal-determinant recursion K_k = a_{d−k+1}K_{k−1} + K_{k−2}),
and they prove the gradient is ALSO a ratio of continuants:
∂f̃/∂a_k = (−1)^k (K_{d−k}/K_d)². So forward AND backward need exactly **one division per
ladder** instead of d — implemented as a custom `torch.autograd.Function` that caches the
continuants + one reciprocal from the forward pass. Their naive-vs-continuants benchmark:
5898 → 628 µs inference (~9×). Divisions being ~10× multiplies on GPU hardware is the whole
point; they have no Triton kernels yet (future work; FPGA division offload mentioned — tells
you where the hardware story stands).

**2. Dyadic depth-unfreezing schedule (load-bearing, not cosmetic).** Train the linear part
from iteration 1; unfreeze depth-i ladder params for the last t/2^i iterations. Table 5:
PTB perplexity 29.9 with it vs 33.7 without. Rational layers train unstably from scratch;
progressive depth-freezing + a pole guard (denominator → sgn(K_d)·max(|K_d|, ε), ε=0.01,
applied once at K_d) + train-time range clipping per ladder is the stabilization recipe.

**3. Results (honest read).** CoFrGeNet-F (FFN replaced, 985M) beats GPT2-xl 1.5B on most
GLUE + perplexity rows at ~2/3 params; on Llama-3.2B/2T-token pretrain the 2.1B -F variant
wins the majority of zero-shot QA/reasoning tasks, ~34% higher token throughput, ~2 days
less train time. **Caveats:** the attention replacements (CAttnU/CAttnM) are the weak half —
the FFN-only (-F) variant consistently wins, so "replace attention" is aspirational;
GPT2-xl/nanoGPT is a soft baseline; the Llama comparison is the credible one.

## Status vs our work

**Not actionable.** We fine-tune SA3 (LoRA/DoRA/control adapters) — we don't pretrain
backbones, so the headline use (DiT FFN replacement) is not our lane, and grafting a new
FFN class into a frozen pretrained DiT is a from-scratch retrain by another name. The one
plausible local touchpoint: our **small heads** (LatCH heads, cc_probe, FusionCC
conditioners) are exactly the "small ensemble + linear layer" scale where a Cffn-style
rational block is a drop-in — but our heads are **signal-bound, not capacity-bound** (the
dead beat/downbeat heads did not fail for lack of expressivity), so no authority gain
expected; a curiosity run at best.

**Worth remembering (the never-reinvent nuggets):** (a) the **continuants closed-form
gradient** — if we ever build a layer with division/rational nonlinearities, one division
per forward+backward instead of d, plus better numerical stability from dividing once;
(b) the **dyadic unfreezing schedule** as a stabilizer for hard-to-train nonlinear layers.
