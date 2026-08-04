# Residual Preservation for SA3 DoRA/control — what is lost, the minimal recovering objective, and the experiment that decides it

**Date:** 2026-07-19
**Authors:** CONTINUITY (synthesis), from a 5-lens CPU analysis + adversarial verification pass
**Scope:** CPU analysis of existing artifacts + theory + literature. No GPU training was run. Frozen SAME decoder, SA3 DiT + rank-r DoRA, T=4096 latents at 10.767 Hz.
**Data:** `eval/reverb_bigpicture.md` (10,584 gens vs 1,116 real-goa crops), `eval/reverb_matrix.jsonl`, 9,041 saved `*.z0.npy` output latents in `/run/media/kim/Mantu/sa3_lora_runs/model_matrix/`, 5,401 encoded real-corpus latents in `/home/kim/Projects/latents_sa3/`.

> **One-line takeaway.** The residual deficit is real, loudness-independent, and robustly measured — but it is **base-model-intrinsic, not adapter-induced**, and its "conditional-MEAN" label is **unproven** because the one decisive measurement (within-context / multi-seed variance) does not exist on disk. Every cheap moment-matching loss we proposed was **refuted as gameable**. The correct next action is not to pick a loss but to run the one **CPU-cheap A/B + one tiny GPU fan** that decides whether an adapter-side objective can work at all.

---

## 1. What is lost, and WHERE

### 1.1 The audible artifact (audio domain, `reverb_bigpicture.md` headline, medians, 382 degenerate clips excluded)

The "bathroom reverb" is a **mono spectral haze**, not stereo and not a reverb tail:

| metric | real goa | base | DoRA | reading |
|---|---|---|---|---|
| **spectral_flatness** | **0.0076** | 0.0204 | 0.0163 | **gen 2.1–2.7× real — THE artifact** |
| late/early energy | 1.008 | 0.392 | 0.890 | gen has *less* late energy (no tail) |
| coh_broadband | 0.540 | 0.632 | 0.566 | gen *more* mono-coherent, not decorrelated |
| width_mean | 0.219 | 0.246 | 0.231 | ~equal / gen slightly narrower |
| side_ratio_mean | 0.246 | 0.274 | 0.240 | ~equal (DoRA −2.6% vs real) |

The stereo meter literally cannot see the problem: by every stereo axis gen is as-clean-or-narrower than real. Confirmed independent: per-clip Spearman(flatness, coh_broadband) = **+0.04** (raw and within-cell residualized) — haze and stereo-collapse are **orthogonal**. The only side-axes that touch haze point the *wrong* way (hazier = wider, less L/R-correlated: width ρ+0.15, corr ρ−0.15).

**Two dose-response facts that constrain any mechanism story:**
- Haze **decreases monotonically** with adapter strength (0.018 → 0.009 at 2.0×) and with epochs on well-trained recipes; **base (no adapter) is hazier than DoRA** (0.0204 vs 0.0163). So the haze is a base / low-strength property. Cranking the adapter *sharpens* toward one mode; it does not inject haze.
- Genuine coherence collapse (0.61 → 0.28) appears **only** at strength 2.0 (n≈288, cfg-imbalanced) and moves *opposite* the haze — a distinct, rare failure mode, not the haze.

### 1.2 The latent-domain deficit (loudness-independent, scale-invariant — the clean axis)

Because these are mean-removed / scale-free statistics on pre-decode latents, the loudness confound that corrupts the audio table (rt60/flatness/crest are level-sensitive) **does not apply**. Four independent metrics agree on a monotone **real > base > DoRA** ordering:

| metric (scale-invariant) | real corpus | base DiT | DoRA | note |
|---|---|---|---|---|
| channel-cov participation ratio | 34–37 | ~14.6 | ~10–12 | primary "distribution lost" signal |
| effective rank exp(H(λ)) | 72.9 | 37.9 | 34.8 | halved before any adapter |
| temporal lag-1 autocorr | 0.146–0.149 | 0.302 | ~0.29 | gen ~2× more temporally correlated |
| temporal PSD flatness | 0.461 | 0.378 | 0.34–0.38 | gen less "white" |
| hf_frac (upper-half temporal power) | 0.396 | ~0.30 | 0.30–0.32 | gen HF-deficient |

Truncation controlled: corpus PR/eff-rank is 34.04 at T=4096 vs **33.85** at gen length T=280 — the 34→14.6 gap is real structure, not a short-window covariance artifact.

**The apparent variance-shrinkage collapses under scale control.** Raw per-channel power reads real 1.43 > base 1.08 > DoRA 0.84, and the selective top-32/bottom-32 shrinkage (0.63 vs 0.83) looks like a textbook shrinkage-estimator fingerprint. But normalize by RMS² and it **vanishes**: chvar/rms² = 0.73 (real), 0.795 (base), 0.77 (goa), 0.77 (avp) — essentially equal. And per-channel power is dominated by CFG, not the adapter: dora_cfg1 0.435, cfg7 0.588, **cfg16 0.948**, goa_cfg16 1.005, real 1.038. So the "variance deficit" is a loudness/CFG effect, not an adapter mechanism. Only the **rank / whiteness** metrics are clean signal.

### 1.3 How strongly does the conditional-mean diagnosis hold, after adversarial verification?

Three graded claims:

1. **A latent residual deficit exists — HIGH confidence.** Consistent across four loudness-independent, scale-invariant metrics over thousands of clips; survives loudness, DoRA-rank (16/64/128/256 all cluster in the same deficient band; no rank monotonicity), precision (fp32≈bf16), under-training (T512≈T4096, longer epochs stay pinned near base), and single-cfg (fully present at cfg7 alone) refutations.

2. **It is base-model-intrinsic, NOT adapter-regression — the adapter-causal framing is effectively REFUTED.** The base DiT with *no adapter* already loses ~57% of the effective rank (34 → 14.6); DoRA adds only an incremental ~2–5 units and on some prompts *increases* eff-rank (rb_common_1 12.9 → 15.0, kl_2 15.8 → 15.5). Base is *hazier* than DoRA in audio. An adapter-only objective is aiming at the wrong parameter set: it can, at best, close the minority 14.6 → 10 increment, not the dominant 34 → 14.6 base gap.

3. **The specific "conditional-MEAN" label is NOT PROVEN — MEDIUM-LOW confidence.** The signature (energy → DC/low-freq, reduced innovation, reduced participation ratio, temporal over-smoothing) is *consistent* with regression toward E[z|context], but equally consistent with generic per-sample high-frequency underfitting / ODE over-smoothing / VAE-prior pull. Distinguishing them requires **conditional (within-context, multi-seed) diversity**, and the saved latents have **only 1 seed per prompt** — so the aleatoric quantity the whole diagnosis is about was never measured. The 37→15→11 "collapse" is a per-sample-over-time + marginal statistic, not a conditional variance.

**Confounds that survived (must be respected downstream):** (a) real corpus is un-guided VAE-encoded posterior means at T=4096; gen is cfg7 sampler endpoints at T=280 — posterior-vs-prior + CFG asymmetry inflates part of the real-vs-gen gap. (b) CFG-modulation of the deficit is untested (latents are cfg7-only). (c) The artifact is **not monolithic**: smooth mean-reversion (hi & PR fall together) and noisy channel-collapse (resid rises above real *via* PR collapse, e.g. dora16_avp ep4) both decode to "haze"; lumping them is wrong. (d) The audio haze and the latent temporal-smoothing were **never decode-linked** — they are on orthogonal axes and their causal connection is assumed, not shown.

---

## 2. The minimal recovering objective

### 2.1 Why the cheap moment losses all fail (the shared refutation)

Every scalar / second-moment target we proposed was **refuted on gameability**: a *deterministic* transform on the conditional mean satisfies the metric while adding **zero** per-sample aleatoric entropy — exactly the thing that is lost.

- **Channel-covariance (Gram) matching — REFUTED.** A fixed linear recolor `A = C_tgt^½ C_s^-½` lifts participation ratio **15.4 → 67.4**, matching the target eigenspectrum *exactly* with ~1.7× variance and zero added entropy. Covariance is a second moment; a rank-r DoRA is precisely such an operator, so it can fully satisfy L_cov while staying mode-collapsed. Worse, DoRA's eigenspectrum is soft-decay (e255 ~7e-8 vs real ~1e-5), so hitting the PR target means amplifying near-zero directions (op-norm 32–478) — injecting deterministic/quantization structure that can *add* haze.
- **Per-channel variance matching — REFUTED.** The target quantity is CFG-controlled and **anti-correlated** with the haze: cfg16 already closes the variance gap (0.948 ≈ real) yet is the **haziest** setting (0.0214), while cfg1 (lowest variance 0.435) is the **cleanest** (0.0104). 79.7% of real channel-cov energy is off-diagonal, so a diagonal match leaves ~80% of the structure free and is satisfiable by cross-channel-independent white jitter → decodes to *more* flatness.
- **Mono spectral-flatness / valley-depth matching — REFUTED.** The no-GPU latent→magnitude proxy is empirically dead: channel-wise latent flatness is 0.667/0.666/0.666 for real/base/DoRA (indistinguishable) while decoded-audio flatness differs 2.1× — SA3 latent channels are not frequency bins. It therefore *requires* decode-in-the-loop (barred here), and a per-clip scalar target is satisfiable by a deterministic per-context notch pattern (fully mode-collapsed, target met).
- **Temporal PSD / whiteness matching — CONDITIONAL, but weak lever.** The premise survives cleanly (real lag-1 0.149 vs gen ~0.29 is genuine and loudness-independent), but (i) it is a **whole-pipeline** property — base ≈ DoRA on lag-1 (0.302 vs 0.29), hf_frac (0.304 vs 0.305), psd_flat (0.378 vs 0.34) — so a thin DoRA loss fights the wrong parameters; and (ii) a marginal temporal spectrum is satisfied *identically* by a stationary colored-noise process, i.e. by adding context-independent shaped noise to the mean — the cheapest descent direction, which recovers no conditional residual.

**The pattern:** matching any *marginal or second-order* statistic of the aggregate is orthogonal to restoring *per-sample, within-context* stochastic entropy. Only an objective whose **target is a full distribution** escapes this.

### 2.2 The single best surviving candidate

**A latent-domain, residual-restricted, feature-matched distribution-matching critic (LADD/DMD-style), applied to the residual `r = z0 − m̂(c)` and constrained to residual statistics — with NO i.i.d. variance head.**

This is the only surviving *training* candidate because it is the only one whose target is a distribution rather than a moment, so the gameability that killed §2.1 does not apply in principle: a critic penalizes *plausible-but-wrong* deterministic noise that a moment match accepts. It subsumes covariance, whiteness, and flatness as special cases the critic can learn jointly (feature-matching on D's activations), rather than as separately-gameable scalars.

**Exact form.**
```
L = E_t,c,ε [ ‖v_θ(z_t, t, c) − v_target‖²  ]            (unchanged RF / flow-matching base)
  + λ_adv · softplus(−D_ψ(r̂))                            (adapter fools the critic)
  + λ_fm  · Σ_l ‖ φ_l^D(r̂) − φ_l^D(r_real) ‖²             (feature matching, stabilizer)

  where r̂      = x0_hat(z_t,t,c) − m̂(c),   m̂(c) = EMA / stop-grad mean predictor
        r_real  = z_corpus − m̂(c_corpus)     (real-goa encoded latents, /home/kim/Projects/latents_sa3)
        D_ψ acts on residual statistics ONLY: per-band temporal variance, cross-channel
             covariance (Gram), participation ratio, and temporal PSD/lag-k — a fixed,
             hand-built feature stack the critic scores, NOT raw z0 (so it cannot fight the mean fit).
        t-gate λ_adv, λ_fm toward LOW-noise timesteps (where mean-collapse bites) only.
```

**Why it beats the runners-up.** (1) Distribution target → not satisfiable by a deterministic recolor/notch/colored-noise map (the §2.1 killer). (2) Restricting D to *residual* features (not full z0) keeps it from fighting the well-learned mean fit and prevents the adversary from pushing latents off the frozen-SAME manifold. (3) Feature-matching on hand-built residual statistics tames the classic adversarial instability and the "plausible-but-wrong noise" mode-seeking that a free critic invites.

**What it will NOT fix — state plainly:**
- **It cannot close the dominant base gap.** ~57% of the eff-rank deficit is base-DiT-intrinsic (34 → 14.6 before any adapter). A DoRA-carried critic caps at the ~14.6 → 10 adapter increment. Recovering the base gap needs to touch base weights or the sampler, both out of the thin-adapter premise.
- **It does not fix stereo.** Ground truth shows side/width are already ≈ real (side_ratio 0.240 vs 0.246). There is no stereo deficit to recover; any stereo term is a solution in search of a problem.
- **It does not, by itself, prove the mechanism.** If the deficit is per-sample low-pass rather than conditional-mean collapse (untested — see §3), a residual critic on 1-seed data will match the *marginal* residual and can still leave every sample individually smoothed.
- **It needs GPU.** Not designable-to-completion in this CPU workflow; the corpus feature targets are precomputable now, D is not trainable now.

### 2.3 The free alternative that must be tried first

Because the temporal deficit is satisfiable by stationary shaped noise, the **calibrated-noise / SDE-sampling A/B is strictly dominant as a first move**: inject per-channel noise shaped to the corpus temporal PSD (or switch the sampler ODE→SDE / raise churn at low t) at inference on *existing* checkpoints. Either it recovers the haze **for free** (no training — ship it) or it proves the marginal target insufficient (which also refutes L_psd as a training loss). No candidate should be trained before this runs.

---

## 3. The experiment that decides it

A three-gate sequence, cheapest-decisive-first. **Do not train the critic (§2.2) until Gate A and Gate B pass.**

### Gate A — CPU-only, days-0, the free A/B (decides if any training is needed)
- **Setup.** Take paired base/DoRA `x0` latents already on disk. Synthesize `z0' = z0 + n`, `n` = per-channel Gaussian shaped to the corpus temporal PSD so lag-1 / psd_flat / hf_frac match corpus **by construction**. Also prepare an ODE→SDE / churn-at-low-t variant for the render card when it frees (minutes, no training).
- **Metric.** Decode a handful off-card; measure audio `spectral_flatness_mean`. Confirm/refute: does whiteness-matched latent move flatness toward real **0.0076**, or does it stay ≈0.016 / rise (mean+hiss)?
- **Decision.** Flatness → real ⇒ **stop, ship SDE/noise injection, no training at all.** Flatness unmoved/worse ⇒ marginal targets are insufficient (kills L_psd/L_var/L_cov as training losses) ⇒ proceed to Gate B.

### Gate B — one tiny GPU fan, no training, the load-bearing measurement
- **Setup.** Fix **one** prompt. Sample **~24 seeds** through the base model and one clean DoRA (goa, well-trained). Compute **per-frequency-band inter-seed latent variance**. Compare to inter-crop variance of ~24 content-matched real-goa corpus latents. (Minutes of inference; the render campaign owns the card, so queue behind it.)
- **Metric.** Conditional (within-context) latent diversity, band-resolved — **the quantity the entire 1-seed corpus could not measure.**
- **Decision.** If gen inter-seed spread ≪ real **specifically in the HF band** ⇒ conditional-mean collapse **confirmed**, a residual-recovery objective is warranted ⇒ Gate C. If gen inter-seed spread ≈ real (diversity fine, each sample individually low-pass) ⇒ mechanism is **per-sample oversmoothing, conditional-mean is FALSIFIED**, and *no residual-distribution critic will help* — the fix is sampler/decoder-side, not an adapter loss. Also decompose each of D's proposed features into base-vs-corpus and DoRA-vs-base components: if the adapter component is a minority (expected from §1.2), formally down-scope the critic to the achievable increment.

### Gate C — the smallest training run that decides the critic (only if A+B pass)
- **Dataset.** Real residual target `r_real` from the 5,401 encoded corpus latents (precompute the D-feature stack on CPU now). Train on the existing SA3 DoRA recipe, T=4096, frozen SAME, cfg7, **one well-trained arm** (goa) as the base to avoid the overtrain-instability confound (dora16_avp ep4-style PR-collapse must be excluded).
- **The loss.** §2.2 exactly: RF base + t-gated `λ_adv` residual critic + `λ_fm` feature-matching, D restricted to residual statistics, small `λ_adv` (start 0.01), EMA/stop-grad mean predictor. **Explicitly A/B against an ablation** that swaps the critic for the equivalent deterministic covariance+PSD moment match — the gameability prediction is that the moment ablation matches the metrics but Gate-B inter-seed variance stays collapsed.
- **The confirm/refute metric.** Re-run **Gate B's inter-seed HF-band variance** on the trained checkpoint. **Confirm** iff conditional HF diversity rises toward real *and* participation ratio rises *without* the recolor signature (no op-norm blow-up of near-zero channels) *and* decoded `spectral_flatness` moves toward 0.0076. **Refute** iff PR/whiteness metrics improve but inter-seed variance stays flat (critic gamed) or decoded flatness does not move (latent stat decoupled from audio).
- **Smallest decisive run.** One arm, one prompt-family, ~a few hundred steps to see the inter-seed-variance trend break from the moment-ablation baseline. If the trend does not separate from the ablation within that budget, the critic is not carrying information the RF loss lacks (MASTER §4 scope condition fails) and should be dropped.

---

## 4. Negative space — refuted candidates (do not re-derive)

| candidate | verdict | why it dies (with the number) |
|---|---|---|
| **Channel-covariance (Gram) matching** as *the crux* term | **refuted** | Deterministic recolor `A=C_tgt^½C_s^-½` hits PR 15.4→67.4 and the exact eigenspectrum with **zero** added entropy — a rank-r adapter *is* such an operator. Soft-decay spectrum means the PR target is reached by amplifying near-zero dirs (op-norm 32–478), which can *add* haze. Batch covariance also conflates within/between-context and can't isolate the aleatoric (conditional) variance. Useful only as a *low-weight t-gated auxiliary*, never the crux. |
| **Per-channel variance (L_var) matching** | **refuted** | The target is CFG-controlled and **anti-correlated** with the artifact: cfg16 already closes the variance gap (0.948≈real) but is the *haziest* (0.0214); cfg1 lowest-variance is *cleanest* (0.0104). Under RMS² normalization the whole shrinkage vanishes (0.73/0.795/0.77 ≈ equal). 79.7% off-diagonal structure left unconstrained; satisfiable by white jitter → *more* flatness. |
| **Mono spectral-flatness / valley-depth matching** | **refuted** | No-GPU latent→mag proxy is dead (latent flatness 0.667/0.666/0.666 for real/base/DoRA, indistinguishable, while audio differs 2.1×) → requires barred decode-in-loop. Per-clip scalar target is met by a deterministic per-context notch (mode-collapse intact). Mechanism also contradicted: base hazier than DoRA, haze falls as strength rises. |
| **i.i.d. per-token σ-head** (`z0 = mean + σ·ε`) | **refuted (as a residual generator)** | Real corpus latent temporal flatness is **0.38** (structured, far from white); an i.i.d. σ·ε head is white (flatness→1.0), so it overshoots flatness in the haze direction — it would *reproduce* the bathroom-reverb it aims to cure. A learned-variance head is only viable if it outputs *correlated* (non-white) residual, i.e. effectively the critic/generator of §2.2. |
| **Temporal PSD / whiteness (L_psd)** | **conditional — not the lever** | Premise real and clean (lag-1 real 0.149 vs gen 0.29), but base≈DoRA on every temporal metric ⇒ whole-pipeline, wrong parameter set for a thin adapter. Satisfied identically by stationary colored noise (Gate A). Kept only as: (a) the Gate-A *free* fix to try first, (b) a possible feature *inside* D — never a standalone committed DoRA loss. |
| **"Conditional-MEAN collapse" as the settled diagnosis** | **conditional / label unproven** | Deficit HIGH confidence, but adapter-causal framing refuted (base owns 57% of the eff-rank gap), and mean-vs-low-pass indistinguishable without Gate B (1 seed/prompt on disk). Do not write training objectives premised on "the adapter regresses to E[z\|c]" until Gate B confirms conditional collapse. |
| **DoRA-rank increase** as a fix | **refuted (already, in `reverb_bigpicture.md`)** | Ranks 16/64/128/256 all sit in the same deficient band; an r128-fusion is among the *cleanest*, r64/r128/r256 among the worst. The binding constraint is the objective, not capacity — raising rank alone does nothing. |

**Meta-lesson for the index:** the recurring trap here is proposing a *moment* to fix a *distribution* problem. Any future "match statistic X of the latent" proposal must first pass the gameability check — *can a deterministic map on the conditional mean satisfy X?* If yes (it is for every second-order statistic), it is not a residual-recovery objective. And any objective premised on the adapter must first pass the base-vs-adapter gap decomposition — the base DiT owns the majority of every scale-invariant deficit measured.
