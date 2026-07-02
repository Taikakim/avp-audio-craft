# Research brief: novelty check on five findings from a music-diffusion control study

**Instruction to the research assistant:** We are an independent lab working on
controllable music generation. Below are our setup, methods, and results. For each of
the five numbered claims, please search the literature (through mid-2026) and assess:
(a) is the specific method or finding already published, (b) what is the closest prior
work, (c) is our framing distinguishable from it. We want an honest assessment, not
validation — "already done in [X]" is a useful answer.

## Setup

- Base model: a 1.4B-parameter latent diffusion transformer (DiT) for music generation
  (Stable Audio 3 "medium"), trained with a rectified-flow objective
  (`noised = clean·(1−t) + noise·t`, velocity target `v = noise − clean`). Audio is
  represented as 256-dim VAE latents at ~10.8 Hz.
- Control mechanism: lightweight decoupled cross-attention adapters (~24 blocks, base
  frozen) + a FiLM conditioner that maps a scalar control value (target onset density,
  onsets/sec) to control tokens. Trained on ~5,400 pre-encoded music segments with
  per-segment onset-density labels extracted by an MIR pipeline (librosa).
- Known problem we measured: the rectified-flow loss is nearly blind to control quality
  — it varies <1% across configurations whose measured control authority differs 3×;
  control authority peaks mid-training then degrades while the loss stays flat.
- Evaluation: render audio via the trained adapter across a request grid (3 prompts ×
  gains × requested densities), measure realized onset density with librosa, report the
  correlation between requested and measured (control authority). Human listening is
  the final arbiter; we've documented that the onset metric can be gamed (a model can
  emit quiet rapid transients that inflate counts while sounding wrong).

## Claim 1 — "Control-consistency loss": a frozen learned meter inside the diffusion training objective

Method: train a small (~0.5M param) regressor ("probe") from clean latents to the
scalar control label (held-out R² ≈ 0.6); freeze it. During adapter training, form the
differentiable clean-latent estimate `ẑ₀ = noised − t·v_pred`, apply the frozen probe,
and add `λ·MSE(probe(ẑ₀), requested_value)` for low-noise timesteps only (t < 0.5),
λ=0.1. Result: control-authority correlation rose from .584 to .880 at operating gain
(paired bootstrap over grid cells: Δ=+0.295, 95% CI [+0.04, +0.83]); the "sparse floor"
broke — requests below the corpus-typical density were finally honored (baseline floor
~6.0–6.9 onsets/s on request-3; ours renders 5.7) and mid-range tracking became
near-exact (request-6 → 6.1–6.6 vs baseline 8.5–9.3). The high-density ceiling did not
move (probe trained only on corpus-range densities).

Important distinction to preserve when searching: we ALREADY use the same family of
predictor networks for inference-time guidance (classifier-guidance / training-free
guidance style: backprop through a feature-prediction head to steer the sampling
trajectory per generation — well-published, not claimed as novel). Claim 1 is
specifically about moving that meter INTO THE TRAINING LOSS of a conditioning adapter:
gradient flows into the WEIGHTS once, inference is unchanged and costs nothing extra.
The objective is also not reward MAXIMIZATION (DRaFT/ReFL-style "make it score higher")
but CYCLE-CONSISTENCY over the conditioning channel: requested value in → generation →
meter reads the output → must MATCH the requested value. So the search should cover:
(a) reward-gradient finetuning of diffusion (DRaFT, AlignProp, ReFL, DPOK; DRAGON in
music — non-differentiable, no gradient flow); (b) cycle-consistency losses for
diffusion/flow CONDITIONING (condition-reconstruction losses, "condition cycle" or
"attribute consistency" training for controllable generation, in any modality);
(c) ControlNet/adapter training with auxiliary perceptual or attribute losses on the
denoised estimate; (d) audio-domain instances of any of these. The narrow question:
has anyone trained a diffusion CONTROL ADAPTER with a frozen latent-space attribute
regressor applied to the one-step denoised estimate, as a consistency (not reward)
term?

## Claim 2 — Orthogonalized (Muon/Newton-Schulz) updates destroy per-coordinate gradient sign structure; consequences for "cautious" masking

Finding: with a Muon-family optimizer (Newton-Schulz orthogonalization of the momentum
on 2-D weight matrices), the fraction of update coordinates whose sign agrees with the
raw gradient sits at ≈0.53 — barely above chance — and is FLAT for an entire 54k-step
run. Consequences we verified: (a) "cautious optimizer" masking (Liang et al. 2024
style: zero coordinates where update·grad ≤ 0) becomes a near-random ~50% sparsification
on such paths — we measured no significant control-authority effect and no trajectory-
geometry effect vs baseline; (b) the standard cautious rescale (divide survivors by the
keep-fraction) silently inflates the update NORM by 1/√keep ≈ 1.37× at keep≈0.53
(vs ~1.05× at the keep≈0.9 typical for Adam-style updates, where the convention is
safe) — this hidden +37% effective learning rate NaN'd a rank-128 DoRA finetune that
was stable without masking. Fix: norm-preserving rescale.

Check against: the cautious-optimizer literature (C-AdamW/C-Lion and follow-ups),
Muon/NorMuon/orthogonalized-update papers, any published combination of cautious
masking with orthogonalized updates or any statement of the sign-agreement statistic.

## Claim 3 — Gradient-free evolution of an exported conditioner with real rendered-audio fitness

Method: the FiLM conditioner runs host-side in numpy on a CPU ONNX inference path, so
we evolve its weights (~37k params: tokens + biases; matrices frozen) with OpenAI-style
ES (antithetic pairs, sign shaping, anchored weight decay toward the trained init),
fitness = −|measured − requested| onset density on ACTUAL rendered audio (deterministic
common-random-numbers rendering; repeat noise floor std 0.009). Two failure modes we
diagnosed en route seem practically instructive: (i) with CRN determinism a discrete
measurement (onset counts) makes the fitness a step function — σ must be calibrated to
move the MEASUREMENT (population spread ≥ 3× the repeat floor), not the weights;
(ii) globally L2-normalized ES steps at 37k dims move each coordinate ~1/√N of the
exploration scale (600:1 explore/exploit) — per-coordinate normalization fixed it.
Final result: modest but real fresh-seed transfer (+0.28 onsets/s mean error, P≈0.96,
concentrated at low requests +0.55).

Check against: evolution strategies for fine-tuning generative models (ES-at-scale
LLM work, 2025-26), black-box/evolutionary optimization of diffusion CONDITIONING or
adapter WEIGHTS specifically (we found sample-space methods — e.g., Diffusion-ES,
EvoSeed, DRAGON — but not weight-space evolution of a conditioning module against a
rendered-output measurement), and any statement of the CRN/discrete-fitness or
step-normalization pitfalls.

## Claim 4 — Rendering the measured-output fitness field on a 2-D plane of conditioner weight space; "field-guided jump"

Method: taking the ES run's [init → final] direction as one axis and a random
orthogonal direction as the other (per-tensor-RMS scaled basis), we rendered a 9×9 grid
where EVERY point is the actual pipeline output: render audio at that weight setting,
measure onset density, score. Findings: the "heard landscape" is smooth and walkable;
descent continued past where the ES stopped; a systematically better off-axis direction
existed; behind the init it was uphill. We then took the field's best grid point as a
candidate ("field-guided jump") and validated on fresh seeds: it TIED the ES endpoint —
i.e., the walk direction transfers across render seeds but the fine terrain is
seed-specific.

Check against: loss-landscape visualization literature (Li et al. and successors — they
render the TRAINING loss; we render an external measurement of generated output);
RL "reward surface" visualization (e.g., "Cliff Diving", arXiv 2205.07015 — closest we
know); any work using such a rendered field to propose the next optimization step for
a generative model's conditioning weights, or any statement of the seed-specific-relief
/ transferable-direction decomposition.

## Claim 5 — Geometric signature of control drift invisible to the training loss

Finding: on a 119.6M-parameter adapter finetune (10 checkpoints), trajectory PCA (Gram
trick; validated against the random-walk null of Antognini & Sohl-Dickstein) shows
top-2 explained variance 0.969 vs 0.776 for the null — genuinely planar motion, 88% in
one persistent direction — and the SECOND component traces an arc whose turnover
coincides with (a) the checkpoint-averaging centroid and (b) the human-audition
"sweet spot" before over-training degrades control (epoch ~5 of 10), while the training
loss is flat throughout. I.e., a regime change (control-forming → drift) that the loss
cannot see is visible in trajectory geometry and confirmed by listening.

Check against: low-dimensional training-trajectory literature (tiny-subspaces line),
any published link between trajectory-PCA geometry and task-quality regime changes
that are invisible to the training loss, especially for diffusion/adapter finetuning.

## Context the assistant may want

All experiments single-GPU (RDNA4 16GB) + CPU ONNX inference; evaluations use fixed
prompts/seeds with paired bootstrap statistics; negative results above (cautious null,
two ES failures) were retained deliberately. We are NOT claiming the general ideas
(reward finetuning, cautious optimizers, ES, loss landscapes) are new — the question
is whether these five *specific* methods/findings have been published.
