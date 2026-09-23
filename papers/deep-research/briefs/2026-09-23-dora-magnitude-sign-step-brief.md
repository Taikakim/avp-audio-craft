# Deep-research brief — scale-aware optimisation of DoRA magnitude / gain parameters under sign-type (fixed-step) optimizers

*CONTINUITY, 2026-09-23, from a failed run (`goa3_avp_r256_2026-09-23`). For Gemini Deep Research. Paste
everything below the line.*

---

## Context (facts, measured — do not re-derive or question them)

We fine-tune a 1.4B-parameter diffusion transformer (rectified flow, audio) with **DoRA** adapters,
rank 128, on 229 linear layers. DoRA reparameterises each adapted weight as
`W' = m ⊙ (W0 + s·B·A) / ‖W0 + s·B·A‖_row`, with one magnitude scalar `m_i` per output row,
initialised to the row norms of the frozen `W0` (all positive).

The optimizer routes parameters by shape. 2-D factors (A, B) get an orthogonalised (Muon-type) update
with per-row normalisation. **1-D parameters, including every DoRA magnitude vector, get a sign
update:** `m ← m − η·sign(momentum)`. That is a fixed step of size η per element per step, independent
of the gradient's size and of `m`'s own size. There is no weight decay on this group. Schedule-Free
averaging is applied on top (the deployed weights are a running average of the iterates), with a
constant η = 6e-4 after a 75-step warmup. Batch 32, ~6,900 steps.

**What happened.** The training loss was stable (epoch means ~0.74) for 9 epochs and then went NaN.
The magnitude vectors of the small **global-conditioning** layers (timestep embedding, global
conditioning embedder, its projection) drifted through zero, while the transformer blocks' magnitudes
stayed well-behaved:

| layer | mean \|m\| at init | worst per-row relative change, steps 1268→6340 | rows with m ≤ 0 at step 6340 |
|---|---|---|---|
| to_global_embed.0 | 0.13 | 40,000× | 592 |
| to_global_embed.2 | 0.18 | 562× | 78 |
| global_cond_embedder.0 | 0.45 | 289× | 77 |
| to_timestep_embed.2 | 0.14 | 12× | 18 |
| transformer attention/FFN layers | ~2.4 | ≤ 1× | ~0 |

The accumulated sign steps (up to η × steps ≈ 3.6) dwarf a 0.13 scalar, and a non-positive DoRA
magnitude breaks the layer. Our working hypothesis: **fixed-size (sign-type) steps are scale-blind,
so small-valued gain parameters random-walk or march through zero, while large ones are unaffected.**

## What we want — the research question

> **How do published methods keep multiplicative gain / magnitude / scale parameters (DoRA magnitude
> vectors, weight-normalisation `g`, LayerNorm/RMSNorm gains, AdaLN scales, LoRA-style scaling
> vectors) well-behaved when the optimizer takes fixed-size or normalised steps (signSGD, Lion,
> Signum, Muon-with-sign-for-1D, normalised/LMO-based updates)? And specifically: what methods let
> such scalars move freely EARLY in training, then constrain or anneal them, so they can find their
> level without drifting for the rest of the run?**

Deliver:

1. **Methods that make the step for a scale parameter relative to its own value.** For example
   log-space / exponential reparameterisation, multiplicative updates, per-parameter trust ratios
   (LARS/LAMB-style) applied to 1-D gains, or projection onto a positive set. For each, state the
   update rule as an equation from the source.
2. **Methods that give gain/magnitude parameters their own schedule:** a separate LR, warm-up then
   freeze, early-only training, decoupled decay toward the INITIAL value rather than toward zero.
   Especially in DoRA follow-up work and in Muon/Lion/sign-optimizer papers that discuss which
   optimizer the 1-D parameters should use.
3. **Reported failures of this kind:** gains or magnitudes collapsing, changing sign, or diverging
   under sign/normalised optimizers, and what the authors did about it.
4. For each method: **was it evaluated on DoRA magnitudes, on diffusion models, or on sign/normalised
   optimizers?** Say which of the three, or none.

## Evidence standard (strict)

- **Every method must come from a named source**: paper (arXiv id or DOI), official code repository
  (file and line), or a documented framework default (e.g. an optimizer's documented param-group
  rule). Give the exact equation or quote (≤ 2 sentences) and where it is (section / equation number
  / file:line).
- **Label every claim** as *stated in source* or *your inference*. Keep inferences short and
  separate. Do not present an inference as a finding.
- **If you cannot find a source for something, say "not found".** Do not fill the gap with a
  plausible mechanism. An empty section is an acceptable answer.
- Prefer 2023–2026 work. Include older sources only where they are the origin of a method still in
  use (e.g. weight normalisation, LARS).
- No invented benchmark numbers. Report numbers only if you quote them from a source, with the source.

## Exclude — we already know these; do not report them as solutions

- Lower the global learning rate. Stop training earlier. Generic gradient-norm clipping (any
  gradient-size clipping is discarded by a sign step anyway). Standard weight decay toward zero.
- "Use AdamW for the 1-D parameters" **without further mechanism**: Adam's step is also ≈ ±η per
  element for a consistent gradient, so it is equally scale-blind. Include AdamW-based answers only if
  they add something scale-relative.
- Freezing or excluding the affected layers. (We know that works. We want to keep them trainable.)
- Adaptive Gradient Clipping (NFNets) as such. We have it; it acts on the gradient, which a sign step
  throws away. Include it only where a source applies the same ratio idea to the UPDATE.
- PsiLogic (arXiv 2607.16268: chaos-gated damping for Adam) and SoftSignum/SoftMuon (arXiv
  2605.31371: temperature-smoothed sign). We have read both. Mention them only if another source
  builds on them for scale parameters.
- General explanations of what DoRA, Muon, sign descent or weight normalisation are.

## Output format

1. A table: *method | source (id + location) | update rule / quote | evaluated on DoRA? diffusion?
   sign-type optimizer? | stated vs inferred*.
2. Under 3: failure reports found (or "not found").
3. At most five sentences of your own synthesis, clearly labelled as inference: which one or two
   methods best fit the table above, and what their known cost or risk is.
4. The search terms and venues you used, so we can check coverage.
