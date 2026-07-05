# Rigor / prior-art review — relevance-routed target-aware DoRA

*2026-07-05, WINTERMUTE (internal-rigor second opinion to CONTINUITY's brief
`research-brief-relevance-routed-dora.md`; THE-FINN runs the external Deep-Research
survey in parallel — this is the internal read, not a lit search).*

## Headline verdicts

1. **Reinvention:** Axis 1 (spatial routing) is ~80% AdaLoRA + surgical-fine-tuning +
   Fisher selection — a *synthesis of known parts*, not a new mechanism. Axis 2's
   underlying insight (noise-level ↔ attribute) is old (eDiff-I / coarse-to-fine), but
   **target-conditioned** loss reweighting is the freshest piece and the one worth the survey.
2. **DoRA-direction-onto-manifold:** as literally stated, a **category error** (weight-space
   "direction" ≠ latent-space manifold). Salvageable only in a reformulated, per-layer form,
   and even then likely **redundant or harmful** — needs an empirical pre-check.
3. **Measurement (the important one):** gradient-norm / Fisher of the RF loss measure
   **reconstruction-relevance, NOT steering-relevance** — this re-walks the RF-is-deaf-to-control
   trap we already proved. Only **keep_frac/sonar** (measured under the control objective)
   plausibly predicts "relevant to STEER target X." The routing metric must be **target-conditioned
   (probe-gradient), contrasted against a null** — or Axis 1 routes rank to the wrong sites.

## Ask 1 — what are we about to reinvent?

**Axis 1 (spatial relevance routing).** The core — *measure per-site importance, allocate
rank/LR proportionally, freeze the rest* — is prior art, three ways over:
- **AdaLoRA** (Zhang 2023) already does importance-based rank allocation, and does it
  *adaptively during training* via SVD singular-value sensitivity. The proposal's **static,
  one-shot pre-allocation is CRUDER than AdaLoRA**, not better. If we build static routing we
  should either use AdaLoRA as the backbone or benchmark against it — otherwise we ship a
  weaker AdaLoRA and call it new.
- **Surgical fine-tuning** (Lee 2022): pick *which* layers to tune by distribution-shift type.
  That is exactly "freeze irrelevant sites, tune the relevant subset."
- **Fisher-weighted selection / LoRA-drop / SoRA / ALoRA**: the "which layers, what rank" family.

The *only* mechanism-adjacent fresh angle in Axis 1 is using our **domain layer-function map**
(attn≈structure, MLP≈timbre, early≈structure, late≈surface) as the routing PRIOR instead of a
generic metric. That's a heuristic informed initialization of a known method — valuable as
engineering, weak as novelty. **Verdict: mostly reinvention; the defensible contribution is
"AdaLoRA/surgical with a domain-informed, target-conditioned prior," which must be *benchmarked
against vanilla AdaLoRA*, not asserted.**

**Axis 2 (temporal / noise-band weighting).** The insight "different timesteps govern different
attributes (high-noise=structure, low-noise=texture)" is textbook: **eDiff-I** ensemble-of-expert-
denoisers specializes capacity by noise band; SDXL's refiner is a low-noise specialist; the whole
coarse-to-fine cascade literature. **Min-SNR / P2** already reweight the diffusion loss by SNR —
but *generically*, for convergence/quality. The genuinely-less-charted bit is **target-conditioned**
reweighting: map an *intended control attribute* to a noise band and bias the loss there. I'm not
aware of a named method doing exactly this for controllable fine-tuning — **this is the strongest
novelty candidate and the right question for Finn's survey (asks 3–4 in the brief).**

**Combination.** "Spatial × temporal, both target-conditioned, routed by a domain map" as one
paradigm — I've not seen that synthesis. But *novel-combination-of-known-parts* is a weak novelty
claim and a classic over-engineering trap: elaborate machinery that a simple baseline beats. (Our
own track record: EMA+early-stop beat the fancy fixes; higher gain beat architecture changes.)

## Ask 2 — DoRA direction → on-manifold subspace: sound or naive?

**As stated: a category error.** DoRA splits `W = m · V/‖V‖`; its "direction" `V` lives in
**weight space**. The dead-walker / centered-PCA on-manifold subspace lives in **latent/activation
space** (the VAE latent the DiT denoises). "Constrain DoRA direction to the latent PCA subspace"
mixes two different vector spaces of different dimension — you can't project one onto the other
without a defined map. So the literal proposal is mis-specified.

**Salvageable reformulation:** what you actually want is the adapter's **OUTPUT perturbation**
`ΔW·x` to land in the *steerable* subspace of that layer's **activation** space — i.e. regularize
the *off-manifold component of the adapter's output*, `‖P_off · ΔW · x‖`. That is coherent, but:
- The subspace must be the **per-layer activation PCA at that block's output**, NOT the global
  latent PCA. Only the *final latent-facing* adapter can use the latent PCA directly.
- **Likely redundant:** if a direction is erased by contractive denoising, it doesn't affect the
  output, so the *training gradient through it is ~0 already* — the optimizer won't spend capacity
  there without help. The constraint may be a no-op.
- **Possibly harmful:** nets routinely use "off-manifold" *intermediate* activations that collapse
  to on-manifold outputs. Hard-constraining intermediate directions can block useful compute.

**Verdict: naive as written; reformulate to constrain adapter OUTPUT (not DoRA "direction"), in
per-layer activation space, AND first run the cheap empirical pre-check — train one adapter
unconstrained, measure the off-manifold energy of its output; if it's already ≈0 the whole idea is
moot.** Don't build the regularizer before that measurement.

## Ask 3 — does gradient-norm / Fisher predict "relevant to STEER," or just "high-magnitude"?

**This is the load-bearing critique.** Both proposed metrics measure the wrong thing:
- **Gradient-norm of the RF loss** = sensitivity of the *reconstruction* objective to a site. But
  RF loss is **deaf to control attributes** — that's the meter-in-the-gradient finding (RF blind to
  onset timing; the whole reason FusionCC exists). So RF-gradient-norm flags sites important for
  *reconstruction*, which can be orthogonal to sites that *steer a target*.
- **Fisher** = expected squared gradient of the *generative log-likelihood* → parameter importance
  for the *density model*. Even more explicitly reconstruction/data-fit relevance, not steering.
- Both also **correlate with weight magnitude and activation scale** — big/active layers score high
  regardless of task-relevance. Without a contrast, you rank the biggest layers, not the *right* ones.

**What actually predicts steering-relevance:** the gradient of a **target-aware signal** w.r.t. each
site — `∂(attribute-probe_X)/∂W` (decode `z0_hat` → frozen probe for X → backprop). That is
literally the FusionCC mechanism repurposed as a *localization* probe: it measures how much
steering-authority for X lives at each site. Strip the magnitude confound by **contrasting** against
a null/generic target (`∂probe_X − ∂probe_null`), so you isolate *X-specific* relevance.

Of the three proposed, **only keep_frac/sonar telemetry** is measured *under the control objective*,
so it's the one that plausibly tracks steering-activity rather than reconstruction magnitude —
**use it, not RF-Fisher.** (Even keep_frac should be read as "active while steering," and sanity-checked
that it isn't just tracking the highest-variance components.)

**Verdict: gradient-norm/Fisher as proposed will route rank to reconstruction-important, high-magnitude
sites — the wrong sites. Replace with a target-conditioned probe-gradient (contrasted vs null), or lean
on keep_frac. This single correction is the difference between the paradigm working and quietly failing.**

## Synthesis + recommendation

- The real, defensible idea in this brief is **target-conditioning** — but it only pays off if the
  **measurement is target-aware**. The current gradient-norm/Fisher measurement is not, and would
  re-commit the RF-deafness mistake. Fix the metric first; everything downstream depends on it.
- **Don't reinvent AdaLoRA.** Use it as the rank-allocation backbone (feed it our target-conditioned
  importance as the prior), or make vanilla AdaLoRA the baseline every claim beats.
- **Do Axis 2 first as the cheap falsifiable MVP.** Target→noise-band loss reweighting is ~a one-line
  change, testable this week, and directly tests Kim's era=low-noise hypothesis (train an era-DoRA
  with low-noise-weighted loss vs uniform; measure era-adherence + seed-variance — we already have the
  spectral-balance/centroid meter from the eval-grid work to read "cheating"). Falsifiable, cheap, high-signal.
- **DoRA-manifold is a separate speculative track** — gate it behind the off-manifold-energy pre-check.
- **Over-engineering guard:** ship the smallest target-conditioned intervention that beats a plain
  DoRA + AdaLoRA baseline before building the two-axis apparatus.

## For THE-FINN's survey to confirm (the genuine gaps)

1. Any **target-/objective-conditioned** PEFT allocation (importance defined by the *downstream control
   attribute*, not the pretraining loss)? (This is where our idea is least-covered.)
2. **Target-conditioned timestep/noise-band** loss reweighting for a *specific attribute* (beyond generic
   Min-SNR/P2, beyond eDiff-I's unconditional expert bands)?
3. **Probe-gradient / concept-localization** methods for choosing adaptation sites in diffusion
   (locate-then-edit analogues that use an attribute probe, not Fisher).
