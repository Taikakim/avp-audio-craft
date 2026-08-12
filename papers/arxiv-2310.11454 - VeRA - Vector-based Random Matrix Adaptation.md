# VeRA: Vector-based Random Matrix Adaptation

**arXiv 2310.11454v2** · Kopiczko, Blankevoort, Asano (QUVA Lab / Qualcomm AI Research)
**ICLR 2024** · 21 pp · read 2026-08-12 (WINTERMUTE), pp.1–6 in detail

---

## What it contains

**The method (Eq. 2, p.3).** LoRA trains a per-layer low-rank pair:

```
LoRA:  h = W₀x + BAx            A, B trainable, per layer
VeRA:  h = W₀x + Λ_b B Λ_d A x  A, B FROZEN, RANDOM, SHARED ACROSS ALL LAYERS
                                 Λ_b, Λ_d = trainable DIAGONAL vectors b, d (per layer)
```

So the only trainable quantities are two diagonal scaling vectors per layer, acting on one
globally-shared pair of frozen random matrices. The vectors "scale and disable rows and
columns" of that fixed basis.

**Parameter count (§3.2).** `|Θ| = L_tuned × (d_model + r)` versus LoRA's
`2 × L_tuned × d_model × r`. The dependence on rank is **additive, not multiplicative** — so
the gap widens as rank grows and as the model gets deeper/wider. Table 1: GPT-3 at rank 16,
LoRA 75.5 M params / 288 MB versus VeRA 2.8 M / 10.5 MB.

**The storage trick.** The frozen random matrices regenerate from an **RNG seed**, so a stored
adapter is just `b`, `d`, and a seed.

**Initialization (§3.3).** Kaiming for the shared `A`, `B`; `b` initialized to **zeros** so
ΔW = 0 on the first forward (same role as LoRA's zero-init `B`); `d` initialized to a single
non-zero constant (0.1 in GLUE) — an extra hyperparameter they acknowledge as tunable.

**Results.** On par with LoRA on GLUE with roughly an order of magnitude fewer trainable
parameters (RoBERTa-base 0.043 M vs 0.3 M; RoBERTa-large 0.061 M vs 0.8 M). On E2E it
*outperforms* LoRA at 3–4× fewer parameters (GPT-2 Medium: LoRA 0.35 M → BLEU 68.9;
VeRA 0.098 M → BLEU 70.1). Instruction-tuning Llama 7B/13B with 1.6 M/2.4 M trainable versus
LoRA-rank-64's 159.9 M/250.3 M. **Merges into W₀ like LoRA — no inference latency.**

---

## What stays ours

**Say the unhelpful part first: the headline benefit is not our bottleneck.** VeRA is motivated
by *storing millions of per-user adapters* (their framing: LoRA on GPT-3 at a million users =
275 TB). We train a handful of adapters and have terabytes of drive. Parameter count and
checkpoint size are simply not what hurts us. Anyone pitching VeRA here on the storage number
is solving someone else's problem.

**The property that IS interesting to us is a side effect they barely dwell on: VeRA is
structurally damped.** Its entire hypothesis class is "rescale rows and columns of a fixed
random basis" — a far more constrained update than LoRA, let alone DoRA or full-FT. Our
recurring failure is the opposite of underfitting: Kim on the goa board, *"earlier eps sound
like they are making too large updates, kind of patchwork sound"*; on the r64 board, *"our LR
is massively too large, we should use EMA or increase the batch size"*; and the whole full-FT
drone is an output-scale runaway (C, 08-10). A method that *cannot* make a large or
badly-conditioned update is aimed at our actual disease, even though it was designed for a
different one. That reframing — VeRA as a damping prior rather than a compression trick — is
the only reason it belongs in our reading at all.

**Where it plausibly conflicts with live work, and this is the real caution.** The shared
`A`,`B` means **every layer adapts inside the same random subspace**, differing only by
diagonal scaling. That is in direct tension with the layer-site thread: C's morph sweep is
running `site_L8_15` and `site_L13_15` arms, and the TADA (2602.11910) reading points at
blocks 16–23 as a candidate injection site. If different DiT blocks need *different* update
directions rather than different gains on one shared direction, VeRA's constraint is exactly
wrong. That is testable rather than fatal — but it should be tested before adopting, not
after.

**Domain gap, stated plainly.** All results are NLP (GLUE, E2E, instruction-tuning) plus ViT
image classification. **No generative audio, no diffusion, no flow matching.** Our adapters sit
on a rectified-flow DiT over continuous audio latents, and we have already seen methods
transfer badly across that gap (the genre meter-in-gradient result, MASTER §4). Treat every
number here as out-of-domain.

**Cheapest way to find out.** VeRA is a small change to an existing LoRA/DoRA implementation —
freeze `A`,`B`, share them across layers, train two diagonals — so it slots into the existing
`--dora-rank` sweep machinery as one more arm rather than a new pipeline. If the
damping-prior hypothesis is right, it should show up as *flatter degradation across epochs*
on the boards where Kim currently hears collapse by ep2–ep8, not as a better peak.

---

## Status

Read pp.1–6 in detail (method, parameter count, initialization, GLUE/E2E/instruction results);
skimmed the remainder. Nothing implemented, nothing tested here. The damping-prior reading is
my inference from our failure history, not a claim the authors make.
