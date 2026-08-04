# Triage — "Deciphering Melody in Continuous Semantic Latent Spaces" (Gemini deep research)

> **Provenance.** Gemini Deep Research received 2026-07-30 (Kim), raw text stored as
> `Decoding Semantic Latent Features.txt` in this folder. Triage by CONTINUITY same day.
> **Composition:** this run follows the brief-Gemini-with-phenomenology convention — its
> entire empirical core is OUR OWN melody-encoding probe v1+v2 (CONTINUITY 2026-07-22,
> WORKLOG + `eval/musicology/latent_melody_analysis_v2/REPORT_v2.md`) reflected back:
> 15-dim melody subspace, 9.3% [9.0,9.6] corpus variance share / 1.61x enrichment,
> interleave slope 0.924 [0.881,0.966] over 140 cells, LOTO 0.679 [0.55,0.78], flute
> 15-channel exception, sweep→pattern register MAE 11-12.5 st, onset/sustain tempo
> microstates (cos 0.38/0.03) with readout transfer R² 0.796, rest-as-a-class geometry,
> frame-lock 161.499 BPM / z-dist 12.09. **None of that is external evidence — do not
> cite the report as independent confirmation of our own numbers.** Gemini's added value
> is the LITERATURE FRAME around them.
> **Citation verification (2026-07-30, web-checked): 9/11 REAL+ACCURATE.** Anchors all
> hold: spectral-bias 2503.03206 (NeurIPS'25 Spotlight, inverse-variance law verbatim),
> HFS 2503.13695 (minor drift: HFS lives INSIDE the neural operator; the diffusion
> post-corrector is companion work Proc.Roy.Soc.A 481:20240819 — both real), CASteer,
> Neurodyne, MeloBottleneck 2607.10233, MG² (retitled "Melody-Guided Music Generation"),
> CSL-L2M, LEACE. Two flags: (a) SPREAD 2603.08763 is REAL but MISATTRIBUTED — it's
> single-agent lifelong imitation on LIBERO, not cross-embodiment transfer; the report's
> robotics-parallel paragraph overreaches. (b) "Linguistic Inertia" (ResearchGate) is
> UNVERIFIED — zero search footprint, likely a conflation into an invented title; the
> underlying claim (late steering fails vs a committed trajectory) has genuine support
> in adjacent literature (arXiv 2602.04896 "autoregressive inertia"), so the mechanism
> stands, the citation doesn't.
> **Errors spotted:** "2.7B parameter DiT in Stable Audio 3" — our medium DiT is 1.4B.
> "HFS ... can be transposed to audio latent spaces" is Gemini's proposal, not a result
> of the HFS paper (fluid-dynamics neural operators).

## What the literature frame gives us (ranked by actionability)

1. **The inverse-variance spectral law (2503.03206) is the missing THEORY for our
   central phenomenon.** τ_k ∝ 1/λ_k: convergence time on an eigenmode scales inversely
   with its variance. Our probe measured melody at 9.3% of latent variance → the RF/MSE
   gradient "hears" melody at ~1/12 budget → fine-tunes master timbre/texture and
   under-train melody at any feasible epoch count. This is Kim's "adapters never learn
   iconic melodies" complaint, derived instead of observed. Also post-hoc validates:
   Head-B conditioning (bypass the statistical inference entirely), delta_upweight arm,
   and the layer-update-weights experiments.

2. **Subspace-weighted RF loss (my safer port of the report's HFS proposal).** The
   report suggests variance-inflating the melody subspace in the LATENT (HFS style,
   inverse-scale at inference). Direct latent scaling shifts the input distribution off
   the frozen base's manifold — risky for adapter training. The equivalent-but-safe port:
   **upweight the RF loss along the 15-dim melody projection** (we HAVE the PCA basis
   from the probe). Implementation: project the flow-matching error onto the subspace,
   scale that component's loss by k (sweep k ∈ {2, 5, 12 ≈ 1/share}). One flag in
   train_lora + the stored basis. CHEAP ARM, candidate for the next campaign slot.

3. **Local-additive melody conditioning ("Head-C" candidate).** Report notes SA3's
   inpaint pathway (local_add_cond, 257-ch mask+masked-latent concat added to the
   residual stream) is a deterministic, time-aligned structural prior — co-opt it for a
   melody skeleton instead of routing through FiLM taps (Head-B) or cross-attn. This is
   a real architectural alternative: rigid localized prior vs Head-B's soft global
   modulation. Head-B's verdict (soft, cfg16-only) makes this worth an arm when the
   melody lane reopens.

4. **MeloBottleneck (2607.10233, verify pending)** — self-supervised melody-skeleton
   extractor (order-preserving latent subsequences). If real: candidate replacement /
   complement for our muscriptor-derived contour streams (Head-B's `.melody8.npy`
   sidecars), and the extractor half of a cycle-consistency loss.

5. **Cycle-consistency (Neurodyne, 2505.15368) + reverse-cycle melody loss** — generate
   → extract skeleton → penalize distance to the conditioning skeleton. Conceptually
   sound, but it's meter-in-the-gradient with a learned meter: our scope condition
   applies (helps only where RF is blind — melody qualifies), and it needs backprop
   through decode + extractor. HEAVY; park behind 2/3.

6. **CASteer / steering-with-inertia** — nothing new for us (we steer conditional-branch
   with σ-matched directions; "apply early at high noise" matches our σ-invariance and
   the STAS/SHIFT picture). The "linguistic inertia" framing is a nice name for why late
   steering fails.

## Verdict

The report is a competent literature wrap around our own data, with two genuinely
actionable transplants (subspace-weighted loss; local-additive melody conditioning) and
one theory anchor (spectral bias) that upgrades "we observed adapters don't learn
melody" to "the math says they can't at this variance share — here is the lever."
No new empirical claims of its own; treat all numbers as ours, all proposals as
unvalidated until armed.
