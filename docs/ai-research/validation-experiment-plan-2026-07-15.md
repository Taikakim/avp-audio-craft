# Longform validation experiment set — plan (WINTERMUTE, 2026-07-15)

*(Delegation: Kim direct via C, 2026-07-15 — "plan the VALIDATION EXPERIMENT SET for
everything the longform research thread surfaced, and pull+READ the full papers first."
Scope = union of `gemini-report-assessment-2026-07-15.md` (W), `gemini-report2-assessment-
2026-07-15.md` (C), `continuity-theory-review-2026-07-15.md` (C). Papers below were read
FULL-TEXT (arXiv PDFs), not abstracts. Companion derivations: C's theory review; the
p\*-tilt framing: `research-synopsis-longform-continuation.md`.)*

---

## 1. What the full papers settle (deltas vs. what we assumed)

### FK-Flow (2509.01543 — Mark, Galustian, Kovar, Heid; TU Wien)
The S1/E2 recipe, now concrete:
- **Stochasticity injection is MANDATORY, not optional.** FK on the deterministic flow
  ODE converges to the tilt but **collapses particle diversity at every resampling step**
  (their Fig. 1 — resampled duplicates never re-diverge on a deterministic path). Theorem 1:
  any CFM admits an SDE family with identical marginals,
  `dY = [v_t(Y) + σ(t)²/2 · ∇log p_t(Y)] dt + σ(t) dB`, and for a **Gaussian prior the score
  is affinely recoverable from the velocity** (their Prop. 2) — no score model needed for SA3.
  (Mapping their α_t/β_t interpolant constants onto SA3's descending-t RF convention is the
  one implementation detail to derive carefully — flagged for C.)
- **The intermediate reward is evaluated at the Euler one-shot endpoint
  `y = x_t + (1−t)·v_θ(x_t)` — which IS our `z0_hat`.** Zero extra model calls (velocity is
  already computed for the step). Our latch_guided machinery evaluates potentials at exactly
  this point. There is an optional second-order endpoint refinement using the previous step's
  velocity (valid only between pure-ODE steps).
- **Potential schedules:** difference `G_i = exp(−λ(r_i − r_{i−1}))`, max, sum; they ship a
  **harmonic-sum schedule** `r_i ∝ U(y_i)/((L+1−ℓ)·H_L)` that up-weights late resampling steps
  where the one-shot approximation is accurate. Practical operating point in the paper:
  **32 particles, 50 steps, resample every 3 steps** (multinomial on weights).
- **Their warning that matches C's lens-B correction:** the standard schedules *optimize into*
  low-potential regions rather than reproducing the full tilted distribution; avoid killing
  low-reward regions early (temper/anneal). Our band-hinge potential (§E1) is already the
  band form.

### AID (2605.13010 — amortized inpainting guidance, EDM/image)
**C's ONE deciding question is answered, in the best possible direction.** The relaxed
dynamics under the Gaussian policy are `ẋ(r) = b(r, x(r)) + ∫ a·π(a|r,x) da` — i.e. the
**backbone enters only as a deterministic drift `b(t,x)`; there is no backbone SDE anywhere
in the bridge.** The Gaussian-relaxation variance is `2λ/(βd)` — λ = auxiliary temperature,
β = control-cost weight, d = dimension — a **fixed, purely policy-side learning device**
(explicitly *not* entropy-optimized; it exists so the policy-gradient score term doesn't
vanish, and training rolls out under the exploratory policy). Deployment **discards the
noise and uses the deterministic mean** (their Alg., step 9).
→ **AID's policy-equivalence bridge (Lemma 3.1 + Thm 3.2/3.3) is backbone-agnostic across
ODE samplers. SA3's rectified-flow sampler qualifies as-is — no stochastic-interpolant
detour, no ε→0 limit to take.** C's route 1 collapses into "port directly"; route 2
(FK-for-the-tilt-semantics + AID-for-the-architecture) remains the cleaner *conceptual*
split, but nothing in the math blocks route 1 anymore.
- Bonus we should copy regardless: the running cost `β/2·∫‖u‖²` is a built-in
  **minimal-intervention regularizer** ("the pretrained reverse dynamics already provide a
  strong model; guidance intervenes only when necessary") — exactly the over-steering guard
  our S2 head wants.
- **C's residual check (2026-07-15) — CLOSED.** The critic's value targets are TD residuals
  `δ_{n,k} = V̂_{k+1} − V̂_k + β/2‖A_k‖²Δt` computed **along rollouts of the relaxed process**
  (their Alg. 1: the sampled action advances the solver step; randomness = policy noise +
  initial `X_0 ~ p_T` only), anchored by a **terminal** target `Ψ(X_K) − λT`. No backbone
  perturbation kernel appears in any update — the backbone enters solely through the solver
  step, which our RF Euler step satisfies. **The port is total; route 2 is unnecessary.**

### LoL (2601.16914 — 12-hour AR video; the rope_jitter source)
The diagnostic we want to replicate has **two parts, one of which needs no GPU**:
- **Analytic:** phase-coherence kernel `C(Δ) = |1/K · Σ_i e^{j·ω_i·Δ}|` over the rotary
  frequencies `ω_i = θ0^(−2i/d)`. Sink-relative concentration of frame g is `R_sink(g) =
  C(g − s)`. **Sink-collapse events coincide with local maxima of R_sink** (their Fig. 2;
  replicated at θ=20000, Fig. 7). This kernel is pure config math — no activations.
- **Empirical:** at collapse, **nearly all heads in a layer** put large attention on the sink
  frames (inter-head homogenization, their Fig. 3) — a collective synchronization, not a
  single head/dim (RIFLEx-style single-component fixes fail; they showed perturbing any one
  RoPE component does nothing).
- Their jitter `θ̂_h = θ0(1 + σθ·ε_h), ε_h ~ U[−1,1]` is exactly our `rope_jitter.py`.
- **Structural caveat (C flagged it; the paper confirms):** LoL's pathology lives in
  *autoregressive* generation with KV-cache attention sinks. SA3 is a bidirectional DiT
  denoising whole windows; our "sink" analog is the clamped a2a prefix. E3 tests whether the
  analogy holds — either answer explains our jitter null.

### TRI-TSMC (2605.25123)
Vanilla SMC ties proposals to the base sampler; reward enters only via reweighting →
weight degeneracy in high-dim. TRI-TSMC **learns twisting functions** by iterated
KL-trust-region updates in path space (closed-form via tempered importance reweighting,
projected back by weighted MLE), and is built for **terminal / noisy / black-box rewards**
(our numpy meter qualifies). It is a *training loop* at inference-prep time — i.e. an
escalation, not the first tool. **Use:** only if E2's ESS collapses at 256×T dims. Deep-read
of their update math is deferred until that trigger.

### LatCH (2603.04366 — Novack et al., Stability AI, ICASSP 2026)
Verified against `latch_guided.py` (signature `rho=1.0, mu=1.0, gamma=0.3, n_iter=4`,
per-guide `weight/start_pct/end_pct/loss_type`): **the TFG design space IS ported** —
ρ/µ (variance/mean guidance), γ noise-convolution on the clean-head eval, N_iter mean-
guidance iteration, selective step windows, multi-guide weighting. What we did **not** port:
1. **LatCH-B — Backwards-Simulated Noise Conditioning** (their best variant on nearly every
   metric): train the head on latents from **generated sampler trajectories** `z_T…z_0`
   instead of forward-noised data latents — closes the train/inference distribution gap at
   exactly the `z0_hat` points where guidance queries the head. **This converges with AID's
   rollout-based training** — two papers independently say: train the head/critic on rollouts.
2. **Sparsity-aware loss + soft teacher logits** for sparse high-D targets. Their finding —
   1-D targets (intensity, beats) guide well, sparse high-D (160-bin pitch) guide poorly —
   **matches our 14-head sweep exactly** (energy heads steer; hpcp/activation heads dead).
   A LatCH-B + sparsity-loss retrain is the concrete resurrection path for the dead heads
   (pool, not longform-critical).
3. `N_recur` time-travel recurrence (minor; we lack it, they set it to 1 anyway).

### RMR (2605.00435 — ICML 2026)
**Finite-time correlation dimension** (Def. 4.1): best-fit slope of `log C_t(ε)` vs `log ε`,
ε log-uniform in `(ε0, ε1)`, with an **O(t) online update** for `C_t(ε)`. Their headline
mirrors C's Q3 rationale: corr-dim stays stable through normal generation and **drops
sharply at geometric collapse, including *implicit* collapse (template repetition) that
content-level meters miss.** Their fix (value-cache eigenvector damping) stays LLM-specific;
the meter ports.

---

## 2. The experiment set

Every render output carries a MANIFEST-v2 `run_meta.json` (hypothesis, args, dataset,
`result`, `kim_feedback` when given). All meters run in **mir venv**; renders local card
unless marked LUMI.

### E0 — Meter validation + corpus reference bands *(prerequisite; CPU-only; ~1 day)*
**Hypothesis:** the whitened-patch recurrence meter and the corr-dim meter separate
known-loopy from known-good material, in BOTH input modes (log-mel audio; SA3 latent).
**Method:**
1. Add finite-time corr-dim to `recurrence_meter.py` — Grassberger–Procaccia slope fit **on
   the pairwise-distance matrix the meter already computes** (whitened patch space; RMR's
   online form + log-uniform ε; block-bootstrap CI; report the scaling-region fit range) —
   **and soft-DET (RQA determinism)** from §6: sigmoid-soften the same recurrence matrix,
   measure diagonal-line mass (sustained orbit-locking vs single re-approach). Three
   statistics total, one distance matrix.
2. Assemble a labeled set from existing renders: loopy (a2a loop-attractor examples,
   breathing-eval clips Kim flagged, meter-extreme picks re-verified by ear) vs good
   (source-goa windows + renders Kim passed). Target n ≥ 20/20.
3. Score both meters, both input modes (latent mode: the paired `.npy`/render latents).
**Go/no-go:** audio-mode AUC ≥ 0.9 on loopy-vs-good; **latent-mode must rank-correlate with
audio-mode (ρ ≥ 0.7)** — the in-loop potential (E1/E2) runs on latents, so if latent-mode
disagrees, the guide steers the wrong statistic and E1 must switch to a decode-in-the-loop
potential (expensive) or fix the latent featurization first.
4. **Corpus reference bands (lens-B):** distributions of patch-recurrence, soft-DET, and
   corr-dim over goa corpus latents (`latents_sa3`, 5401 crops; plus long windows from Mantu
   source latents) → **quantile bands** (e.g. [q25, q90]) that parameterize every
   potential/reward downstream. Point targets are banned per C's lens-B correction
   (moment-constraint pathology: high λ buys novelty with incoherence).
5. **E0-C — the VRRW knee test (C, 2026-07-15; zero renders).** Lens A's rigorous form
   (VRRW localization) predicts loop onset is a **phase transition in prefix-influence
   strength**: loopiness-vs-nl (and vs prefix length) should be **sigmoidal with a sharp
   knee, not gradual**. Compute loopiness curves from clips ALREADY ON DISK (existing
   nl-sweeps + G's bracket renders). Sharp knee → lens A confirmed rigorously AND the
   breathing controller's objective clarifies to **threshold-keeping** (stay below critical
   reinforcement) rather than post-onset escape — Kim's original design intuition, now with
   a theory name. Also the antidote to the same-model-convergence caveat: data arbitrates.

### E1 — Recurrence potential as a latch_guided gradient guide *(S1-TFG go/no-go; local card)*
**Hypothesis:** tilting sampling with a differentiable recurrence potential reduces
loop-attractor behavior at matched quality — the TFG/gradient approximation of p\*.
**Method:** torch port of the meter as a fixed (no-params) "head": whiten → 4 s patches
(stride 1 s) → cosine vs the 8–40 s lookback band → per-patch recurrence curve. New
`loss_type="band_hinge"`: penalize only above the corpus band's upper edge (zero inside the
band — the distributional form). Soft-aggregate over the lookback (logsumexp temperature
sweep) instead of hard max, addressing C's uninformative-gradient concern; **log guide
gradient norms per step** (instrument check: if ‖∇‖ ≈ 0 while FK weights (E2) respond, the
potential is weight-informative but gradient-flat — C's predicted failure mode, and the
tilt hypothesis survives to E2).
**Pre-test before any render grid (C, 2026-07-15; zero renders, ~15 min GPU):** the
σ-resolved **gradient-SNR curve** — at a σ grid, compute ∇_z0hat(potential) over N seeds,
plot ‖mean ∇‖/std(∇); tells us WHERE gradients carry signal and feeds the guide's σ-window
directly. Companions: (a) line-search sanity (does a small step along −∇ reduce the
potential — catches adversarial/non-smooth surfaces); (b) **fraction-of-time-in-band** —
the band-hinge gradient is zero inside the band by design, so if the sampler sits in-band
~90% of the time the gradient guide is mostly dormant and **E2 becomes the primary test,
not the fallback**.
Grid: λ (guide weight) × window (σ∈[0.2,0.7] center vs LatCH-paper-style early-20%) ×
{n_iter 1,4} × nl (re-noise; §6 interaction axis). Arms: band-hinge (default), contrastive-
velocity, DPP-hinge if id verifies (§6). Long-window a2a continuations (the loop-prone
regime), ~50–100 renders.
**Meters:** audio-mode recurrence tail (fraction of patches above band), corr-dim, CE/PQ
(Audiobox) + prompt adherence as quality guards, Kim's ears on the shortlist.
**Go/no-go:** recurrence tail halves (vs unguided seeds) at ≤0.2 CE drop → S1 confirmed,
proceed E2-as-upgrade + E5. Null with healthy gradients → tilt weakened but E2 still owed
(consistency check). Null with flat gradients → E2 is the real test.
**Cost:** ~2 days code (meter port + loss_type patch + eval harness), 1–2 GPU-nights.

### E2 — FK-SMC consistency check *(S1 proper; local small → LUMI scale)*
**Hypothesis:** the weighting form of the same tilt works even where gradients don't
(C's footnote) — FK is the *consistent* sampler of p\*, E1 only its approximation.
**Method:** port FK-Flow onto our Euler loop: (a) SDE-ify via Theorem 1 with the
velocity-recovered score — C's reference form (2026-07-15), in the `z_σ=(1−σ)·data+σ·noise`
convention with `v̂=E[noise−data|z]`: `∇log p_σ(z) = −(z+(1−σ)·v̂)/σ` (**verify the DiT's v
sign in models/diffusion.py first — if v=data−noise all signs flip**; the 1/σ blow-up at
σ→0 is itself an argument for the restricted SMC window);
(b) potentials through **weights only, all gradient guides OFF** (C's attribution rule);
(c) resample multinomially every ~3 steps **inside σ∈[0.2,0.7] only**; (d) difference AND
harmonic-sum schedules on `r = U(z0_hat)` with the band-hinge U (numpy meter as-is —
no differentiability needed); (e) **log ESS every resampling step**; (f) **proposal
variants** (C's SRMC verdict): plain-Brownian vs **self-repellent proposal**
(`exp(−α·θᵀs)` drift tilt, θ = running past-score mean — score is affine in the velocity we
already compute, nearly free) with the SAME explicit FK target — escape pressure in the
proposal, named terminal law in the weights; SRMC's uncharacterized induced tilt never
becomes the estimand.
K=4 particles, T≤2048 local (sequential forwards fit 16 GB); K=8–32, T=4096 on LUMI.
**Go/no-go:** recurrence tail improves at matched quality with ESS staying > K/4 → tilt
confirmed; if ESS collapses → TRI-TSMC escalation (deep-read + learned twist) before any
verdict; if FK also null with healthy ESS → **the tilt hypothesis is dead as formulated**
(the honest outcome C insisted stays reachable) and the exogenous-drive family (breathing/
arc/skeleton) carries the lane alone.
**Cost:** ~2–3 days port, 1 GPU-night local; LUMI arm ~a few node-hours, queued per §3.

### E3 — LoL phase-alignment diagnostic *(explains our jitter null either way)*
**Part A (CPU, hours, no GPU):** compute `C(Δ)` from SA3's rotary config (head-shared base,
d_head, window positions). Extract measured loop periods from E0's loopy set (recurrence-
meter lag histograms). **Test: do loop periods land on local maxima of C(Δ)?** A hit means
the rotary geometry sets the loop period (LoL's mechanism present in bidirectional form);
a miss kills the RoPE-phase explanation for OUR loops.
**Part B (local GPU, few renders):** forward hooks on Q/K-post-RoPE + attention maps during
loopy windowed rollouts; measure (i) per-head attention mass from generated frames onto the
clamped prefix, (ii) inter-head concentration (all-heads-simultaneously statistic, their
homogenization signature) at loop onset vs matched non-loop windows.
**Outcomes (either informative, per C):** no concentration → LoL's AR/sink pathology isn't
ours; jitter null explained; rope_jitter demoted to minor breathing actuator. Concentration
→ our jitter null needs a re-look inside LoL's σθ∈[0.05,0.10] band + eval-metric re-check.
**Cost:** A ~half day; B ~1 day + a GPU-evening.

### E4 — SaFa Reference-Guided Latent Swap port *(cross-window timbre-drift axis; local)*
**Hypothesis:** early-step unidirectional injection of reference-window latents into each
new window's non-overlap region fixes cross-window timbre/acoustics drift — the third axis
(seam-character fixed; loopiness untouched; this targets neither).
**Method:** in `longform.py`'s sequential frame: at early σ steps of each new window,
swap/blend reference-view latent frames into the non-overlap region (inpaint-style clamping
with a σ-schedule — machinery exists). Reference = window 0 (or a rolling anchor — ablate).
**Meters:** cross-window drift = per-window embedding distance to the reference (MERT-mid +
centroid_proxy trajectory), CE/PQ stability across windows; **co-score loopiness** (guard:
a global reference must not INCREASE recurrence — it plausibly could; if it does, that is a
finding about drive-vs-anchor tension, report don't bury).
**Go/no-go:** drift slope vs window index flattens at unchanged recurrence tail.
**Cost:** ~1–2 days + a GPU-evening. Independent of E1/E2 — schedule opportunistically.

### E5 — AID-style amortization spec *(gated on E1/E2 showing the tilt helps; LUMI)*
Not an experiment yet — a build spec to draft NOW so the LUMI queue slot can be claimed
the moment E1/E2 confirm: state (t, z_t, window-context ξ), terminal reward = band-hinge
recurrence (+ corr-dim term), running cost β/2‖u‖² (minimal-intervention), actor/critic =
LatCH-scale (~5–7 M), **trained on guided-rollout trajectories** (AID's exploration = the
LatCH-B lesson), deployed as deterministic mean folded into the Euler drift (<1% overhead,
no particles at inference). Probe-hack guard from the FusionCC playbook (supervise a
statistic subset, monitor held-out dims). RF port is licensed by the §1 AID finding.

---

## 3. Sequencing (around Kim's LUMI fp32/T=4096 campaign + smoke gate)

**Now / zero-GPU (start immediately):** E0 (meter + bands, CPU), E3-A (analytic kernel,
CPU), E5 spec draft. None of these touch the card or LUMI.
**Local GPU nights (coordinate on channel; card is Kim's by day, G renders queued):**
E1 → E3-B → E4 (order: E1 gates the thread; E3-B/E4 are fill-in work while E1 grids run).
E2-local after E1's verdict.
**LUMI lane (updated 2026-07-15): smoke tests STILL RUNNING — dependency issues; every
LUMI date floats on that gate.** When smoke passes: Kim's fp32/T=4096 comparison first,
then task-50 long-context arms. E2-scaled and E5 queue BEHIND those, and each passes the
standard smoke gate (short validation run) before production hours. Mitigation: all my
LUMI items are packaged submit-ready so they enter the queue within a day of gate-clear;
nothing in E0–E4 depends on LUMI. ARC-Forcing/S3 (dataset builder already landed,
WORKLOG #46) stays the flagship-retrain fallback if the inference-time family
under-delivers — decision point after E1+E2.

## 4. Beyond the six (pool, no plans yet)
- **Breathing controller #35 closure:** after E0, the meter is validated + banded — the
  DriftMonitor→{rope_jitter, incantation, nl} loop has all parts; E3's verdict decides
  whether rope_jitter stays in the actuator set.
- **Dead-heads resurrection:** LatCH-B trajectory training + sparsity-aware loss on the
  beat/onset/hpcp heads (paper-matched fix for our exact sweep finding).
- **Koopman skeleton (C's Q4):** frozen-SA3-compatible arrangement-skeleton model on our
  own latents — the LUMI long-shot after E5.
- `N_recur` time-travel knob (minor TFG completeness).

## 5. For C (theory sanity-checks)
1. Verify my AID reading (relaxed dynamics = deterministic drift + policy-mean; §3.1–3.2
   of the paper) — if agreed, route 1 is a direct port and route 2 is optional elegance.
2. Derive/check the Prop.-2 score-from-velocity affine constants in SA3's descending-t RF
   convention before E2's SDE-ification (I'll draft; one-page check).
3. E1's logsumexp-temperature sweep as the gradient-informativeness probe — better design?
4. *(from the tangential-refinements doc)* SRMC-style score-space self-repellency
   (tilt `exp(−α·θᵀs)`, θ = running mean of past scores) claims asymptotic unbiasedness
   under stationary/ergodic premises that a finite-horizon generative path breaks — is a
   finite-horizon analogue recoverable (α-schedule / terminal correction)? Also: the
   VRRW/self-interacting-diffusion framing (positive self-reinforcement localizes = our
   attractor; negative escapes; phase transition) as the rigorous name for lens A.

## 6. Deltas adopted from the isolated-instance refinements doc (2026-07-15, same day)

`tangential-refinements-longform-continuation.md` (isolated Fable instance; saw ONLY the
synopsis + F's brief — none of the Gemini reports, paper reads, or this plan) — assessed,
adoptions below. Its own provenance caveat applies: **starred(\*) ids are 2026 preprints it
light-verified only — re-fetch before any becomes load-bearing.**

- **E0 + meter:** add **soft-DET (RQA determinism)** as a third statistic beside
  max-cosine recurrence and corr-dim — sigmoid-soften the recurrence matrix we already
  compute, measure diagonal-line mass. Rationale: max-cosine fires on any single
  re-approach (legit theme return); DET fires on *sustained orbit-locking* — the statistic
  that names the pathology. Same distance matrix, near-free; pick E1's potential by
  labeled-set AUC among the three.
- **E1 grid, three additions:** (a) an **nl/re-noise interaction axis** — tests the doc's
  "deterministic tilt can't escape a committed basin" claim as data instead of doctrine
  (in our windowed a2a the anchor imports the loop at low effective noise, so tilt×nl is
  the real question); (b) optional potential arms: windowed **DPP log-det hinge**
  (\*2511.20647) and **score-repellency** (\*SRMC 2604.22948 — meter-free in-loop, score
  from velocity); (c) a **contrastive-velocity arm**: `v_guided = v − γ·(v_amateur − v)`
  with the amateur = the SAME ckpt made loop-prone (stronger anchor / crippled context) —
  training-free, velocity-space (immune to D-differentiability), attacks the attractor
  direction rather than prompt adherence (distinct from CFG). Cost: one extra forward.
- **E2:** SVDD noted as the derivative-free sibling already inside the FK-weighting family
  (its posterior-mean value = our z0_hat reward — same myopia, no new capability); **NETS**
  (2410.02711) joins TRI-TSMC in the escalation tier (learned drift minimizing FK weight
  variance; Jarzynski correction keeps the tilt unbiased when restart noise is injected —
  the S5×S8 unifier if we get there).
- **E5:** the doc's §0.1 "cost-to-go, not instantaneous ∇D" correction is right theory —
  and is **auto-satisfied by the AID route: AID's critic IS the value function** (the
  isolated instance couldn't know; it only had the synopsis). Adjoint Matching (2409.08861)
  + SOCM (2312.02027) recorded as alternative training objectives; Explicit-Critic
  (\*2605.27736) as the derivative-free variant if its id verifies.
- **NEW pre-#35 probe (adopt, ~one afternoon, CPU):** **rhythm-subspace probe** — temporal
  FFT + PCA split of SAME latents to test "rhythm ≈ low-frequency/low-variance latent
  directions"; if it holds, breathing's escape kick becomes **variance/frequency-graded
  re-noise** (SAGD\*/blurring/subspace-diffusion family) that dissolves the melodic loop
  while sparing the beat grid — the missing piece between #35's kick and the mush wall.
  Music Boomerang (\*2507.04864) is the negative control (isotropic renoise can't target).
- **#35 breathing design cites:** Restart Sampling (2306.14878, restart-on-R-onset with a
  contraction bound), EDT's exponential law for amplitude, Walk-Jump (hold one elevated σ,
  tilt inside the walk steps) as the three candidate kick shapes.
- **Rejected/corrected from the doc:** §0.2's "S1 only works WITH S8" — overstated for our
  regime (each window denoises from fresh noise; mid-σ guidance selects basins; E2's SDE
  channel exists anyway) → demoted to the E1 grid axis above. §5's Stein-PF motivation
  ("resampling duplicates the attractor phrase") has the **sign backwards for our anti-loop
  potential** — high-weight particles are the non-loopy ones; the real concern is standard
  ESS degeneracy, already instrumented. SimCTG's frame-Gram penalty re-derives what our
  v1 meter already falsified (frame-level saturates on tonal music; patches are the unit).

## 7. Schedule (v1, 2026-07-15 — G's double-check pending; LUMI floats on smoke)

Assumptions: card is Kim's by day + G's render/caption lanes intermittent → my GPU work is
nights, coordinated on channel; CPU (mir venv, 12 cores) free anytime; C confirms no card
contention. LUMI smoke tests still failing on dependencies → **no LUMI dates, only a gated
order**; everything E0–E4 is deliberately LUMI-independent.

### Local — CPU/code track
| When | What |
|---|---|
| Wed 15 | E0-A: corr-dim + soft-DET into `recurrence_meter.py` (same distance matrix) · E0-B: assemble labeled loopy/good set from existing renders + Kim verdicts |
| Thu 16 | E0-B scoring → AUC per statistic × input-mode, pick the potential form · **E0-C VRRW knee test** (loopiness-vs-nl from clips on disk, zero renders) · E0-D corpus bands over `latents_sa3` (CPU-parallel) · E3-A analytic C(Δ) vs measured loop periods |
| Fri 17 | Rhythm-subspace probe (temporal FFT/PCA on SAME latents; gates selective-renoise breathing) · E1 code: torch meter port + `band_hinge` loss_type + harness |
| Sat–Sun 18–19 | E1 scoring harness · E4 SaFa-swap code · **E5 AID-head spec draft** (submit-ready package) · buffer |
| Mon 20+ | E2-local code: SDE-ified sampler + FK weights + proposal variants; **affine-constants draft → C's sign-check** (gates E2 renders, not E2 code) |

### Local — GPU nights
| Night | What | Gate |
|---|---|---|
| Thu 16→17 | E1 **gradient-SNR pre-test** (~15 min) + pilot grid ~30 renders (instrumentation shake-out) | E0 meters validated |
| Fri 17→18 | E1 main grid ~100 renders (band-hinge · contrastive-velocity · DPP-hinge if id verified · nl axis) | pilot clean |
| Sat 18→19 | E3-B attention hooks on loopy rollouts · E4 render pass | — |
| Sun–Mon | E1 scoring (CPU day) → **E1 VERDICT Mon 20** | — |
| Tue–Wed 21→23 | E2-local: K=4, T≤2048, plain-Brownian vs SRMC proposal → **tilt go/no-go ~Thu 23** (with C) | C's sign-check back |

### LUMI (gated order, no dates — smoke tests still running)
1. **Gate L0:** smoke passes (dependency issues; outside this plan's control).
2. Kim's fp32/T=4096 comparison campaign (first in queue, Kim's).
3. Task-50 long-context arms (C's package).
4. **E2-scaled** (K=8–32, T=4096, ~node-hours) — submit only if E1/E2-local is positive or
   scale-ambiguous.
5. **E5 AID head** (~GPU-days class) — gated on E1/E2 confirming the tilt; spec ready
   Fri 18 so it enters the queue same-day when gates clear.
6. Backlog: ARC-Forcing S3 (dataset builder landed), Koopman skeleton.

**Kim-facing checkpoints:** E0 + knee-test report Thu 16 evening · E1 verdict Mon 20 ·
E2-local tilt go/no-go ~Thu 23. Every render output ships MANIFEST-v2.
