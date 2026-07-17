# Tangential Refinements — sharpening the long-form loop-attractor plan

*Compiled 2026-07-15 (Claude Code, at Kim's request). Grounds: `research-synopsis-longform-continuation.md`
(WINTERMUTE's 8-family `p*` formulation) + `research-brief-longform-continuation.md` (THE-FINN's
Gemini brief + fleet web pass). Method: a 7-lane parallel web sweep of **adjacent** fields, deliberately
NOT re-litigating the fleet's own core methods (diffusion-/self-forcing, twisted-SMC/FK, amortized
guidance, Koopman/SSM) or its excluded list (min-SNR, generic CFG, PEFT, sliding-window stitching).
Status: idea-scouting, not vetted plan.*

**⚠ Provenance / confidence.** Every arXiv id below came from the sweep with only *light* fetch
confirmation — this pass ran **no adversarial verify stage** (a budget choice). Treat ids/venues as
search-level, especially the 2025-26 preprints and anything marked *paper-only/theory*. Per the fleet's
own TADA rule: **re-fetch before citing anything load-bearing.** What is solid is the *mechanism→knob*
mapping; the metadata is the soft part.

---

## 0. The two findings that are corrections, not additions

Before the catalogue: two results below don't just add options, they **change how S1 as written should work**.

1. **The correct tilt is the cost-to-go gradient, not the instantaneous `∇D`.** Path-integral / KL control
   (Kappen 2005, Todorov 2009; Path Integral Sampler [2111.15141](https://arxiv.org/abs/2111.15141)) shows
   that for an `exp(−cost)` tilt the optimal control is `u_t = σ²·∇log h_t`, where `h_t = E[exp(−D) | z_t]`
   is the **soft value / cost-to-go under the remaining flow** — not `−λ∇D(z_t)`. Since `D(R(z),R_data)`
   is a *terminal, whole-sequence* cost, `∇D` at an intermediate `t` is ill-defined and, where defined,
   under-steers. **S1 as stated is the myopic approximation to a value-function guidance.** Adjoint
   Matching ([2409.08861](https://arxiv.org/abs/2409.08861)) is the RF-native way to get the right target,
   and its *memoryless-noise* condition makes the tilt **unbiased** (removes a value-function bias that
   plain S1 silently carries).

2. **S1 and S8 are not independent — deterministic guidance cannot erase a locked-in phrase.** Restart
   Sampling's contraction analysis ([2306.14878](https://arxiv.org/abs/2306.14878)) plus the LLM/decoding
   evidence (EDT, [2403.14541](https://arxiv.org/abs/2403.14541)) both say the same thing: **stochastic
   re-injection is what dissolves an attractor; a deterministic velocity nudge is not.** A latent already
   in the loop basin will not be pushed out by `−λ∇D` alone — you need to kick `t` back up (add forward
   noise) and re-descend. So the breathing controller (S8) isn't an optional add-on to S1; **S1 probably
   only works *with* an S8 restart.**

Everything else is a menu for the individual knobs.

---

## 1. R(z) — the statistic itself (the richest lane)

You now have **≥5 distinct differentiable, latent-native (no-decode) forms** of the recurrence statistic.
Pick by what "recurrence" should *mean*:

| R form | Method | id | note |
|---|---|---|---|
| **dynamical orbit-locking** | **Soft-RQA determinism / trapping-time** | [1703.01541](https://arxiv.org/abs/1703.01541) (soft-min) + RQA (Marwan 2007) | **The only stat that names the pathology**: a loop *maximizes* recurrence-plot diagonal length. Relax the ε-Heaviside to a temperature sigmoid → smooth DET; D pushes DET *down toward* R_data, not to 0. Theory-stage; assemble from the soft-min primitive on latent delay-vectors. |
| **raw self-similarity** | **SimCTG cosine degeneration penalty** | [2202.06417](https://arxiv.org/abs/2202.06417) | Off-diagonal max cosine on the frame Gram matrix = ready-made R, closed differentiable form, shipping in HF. **Exclude the diagonal band** or you punish legitimate local continuity. |
| **MIR novelty** | **Differentiable SSM + Foote checkerboard** (SSM-Net) | [2309.02243](https://arxiv.org/abs/2309.02243) | Cosine SSM on latent frames + Gaussian checkerboard = differentiable novelty curve; canonical MIR measure, latent-native. Fixed kernel works out-of-box; learned kernel needs a short pretrain. |
| **rank / diversity** | **Windowed-DPP log-det energy** | [2511.20647](https://arxiv.org/abs/2511.20647) | `−log det` of a window-embedding Gram matrix → −∞ exactly as rows coincide, i.e. **purpose-built anti-loop D**. Differentiable tilt for S1 or a plain reward for S5. O(k³), k small. |
| **coverage / entropy** | **k-NN window state-entropy (APT / RE3 / SMM)** | [2102.09430](https://arxiv.org/abs/2102.09430) | Mean log-distance to k nearest neighbours in an embedding = differentiable window entropy; low = collapsed. RE3's fixed random projection gives a **training-free** R. SMM is literally the `p*` tilt in RL form. |
| **cross-scale** | **Scattering covariance** (Morel-Zhang-Mallat) | [2204.10177](https://arxiv.org/abs/2204.10177) | Max-entropy generative summary stats of a path; captures long-range cross-scale dependence a windowed SSM misses. Heavier, but a principled R_data. |
| **cheap scalar** | **1/f slope / DFA (Hurst)** | [physics/0703179](https://arxiv.org/pdf/physics/0703179) | A loop collapses the ~1/f slope into a spike → `(β−β_data)²` is a light auxiliary term or S8 onset signal. Necessary-not-sufficient; pair with the above, don't use alone. Avoid box-DFA (non-smooth); use FFT-slope. |
| **learned perceptual** | **SongFormer / multi-level structure SSL** | [2510.02797](https://arxiv.org/abs/2510.02797) | A frozen structure-encoder's feature-SSM as R_data upgrades the hand-cosine SSM to a perceptual target. Operates on audio → needs a latent→feature adaptor or periodic decode; better as an S5 reward or S2 signal than an inner-loop velocity term. |

**Take:** default to **soft-RQA** (names the loop) or **DPP log-det** (purpose-built, cheap) for the tilt;
**k-NN/RE3** if you want training-free; **scattering** if the windowed forms miss slow structure.

---

## 2. S1 — applying R as a velocity (the tilt)

- **SPELL / Sparse Repellency** — [2410.06025](https://arxiv.org/abs/2410.06025) — *research-code, continuous-latent native.*
  The concrete **repel-from-your-own-past** primitive: a repellency term that fires only when a trajectory
  re-approaches a **dynamic reference set**. Set reference = sliding window of emitted phrases → repels at
  loop onset, inactive elsewhere. Rewrite the SDE-drift as an RF velocity term (trivial — it's already a
  log-repellency gradient). **The standout for S1's "repel from its own past."**
- **Contrastive Decoding (expert−amateur)** — [2210.15097](https://arxiv.org/abs/2210.15097) — *research-code.*
  Tilt = `v_expert − γ·v_amateur`, amateur = a deliberately loop-prone SA3 (short-context / cropped /
  low-capacity). The amateur locks into the attractor *faster*, so subtracting its velocity pushes away
  from the loop basin. **Distinct from the excluded CFG** — CFG contrasts conditional-vs-unconditional of
  one model; CD contrasts capacity/context, so it attacks the attractor, not prompt adherence. Cost: one
  cheap 2nd pass; the plausibility floor = a trust region on the tilt.
- **Particle Guidance** — [2310.13102](https://arxiv.org/abs/2310.13102) — *research-code.*
  Proves a repulsion kernel **is** an FK potential/twist — so anti-repetition folds straight into the S5
  twist rather than bolting on a 2nd mechanism. The transfer twist: replace "repel from sibling particles"
  with "repel from **lagged self-copies**" (spatial→temporal). Open risk: lagged copies are correlated, so
  the exact-reweighting guarantee weakens to an approximation.
- **Training-Free Stein / SVGD Guidance** — [2507.05482](https://arxiv.org/abs/2507.05482) — *paper-only.*
  Its stated objective — "push **beyond high-density regions**" — is a near-literal description of the
  attractor (a spurious high-density mode). A kernelized, principled alternative to raw `−λ∇D`. Needs
  score→velocity mapping for RF.

---

## 3. S8 — the controller (when, and how hard, to kick)

- **Restart Sampling** — [2306.14878](https://arxiv.org/abs/2306.14878) — *shipping.* The principled form of
  "breathing": ODE descent + periodic forward-noise re-injection, with a **contraction bound** S8 currently
  lacks. Fire the restart on `R(z)` loop-onset instead of the paper's fixed FID-tuned intervals. (See §0.2 —
  this is *the* escape mechanism.)
- **EDT: entropy-triggered temperature** — [2403.14541](https://arxiv.org/abs/2403.14541) — *shipping (decoding).*
  The exact control law S8's Schmitt trigger approximates by hand: raise stochasticity when a collapse
  signal fires. Redefine the categorical-entropy signal as a continuous-latent proxy (R-drop / velocity-norm
  / per-step predictive variance) and modulate breathing amplitude with EDT's exponential law.
- **Walk-Jump Sampling** — [2306.12360](https://arxiv.org/abs/2306.12360) — *research-code.* Hold the latent at
  **one** elevated σ, run several Langevin walk steps to diffuse *out* of the phrase basin, then one-step
  jump back to clean. Key: **the S1 tilt belongs inside the walk-step drift**, where it mixes over many
  steps instead of acting once per denoise. Needs the RF→score conversion at one noise level.
- **SMiRL surprise setpoint** — [1912.05510](https://arxiv.org/abs/1912.05510) — *research-code, non-diff (fine
  for a controller input).* Running-density NLL of the current latent as the S8 sensor: collapse = surprise
  driven too low (raise pressure), incoherent drift = too high (lower it). Gives the bang-bang controller a
  principled setpoint.

---

## 4. S2 / SOC — the steering net and its math (most principled lane)

`p* ∝ p_θ·exp(−λD)` **is** a KL/path-integral control tilt, so the SOC toolbox applies directly.

- **Path-integral / KL control + PIS** — Kappen'05 / Todorov'09 (anchor); PIS [2111.15141](https://arxiv.org/abs/2111.15141) — *theory.* The `u_t = σ²·∇log h_t` result of §0.1. The RF flow is deterministic, so you need a stochastic (memoryless-SDE) sampler to open a control channel.
- **Adjoint Matching** — [2409.08861](https://arxiv.org/abs/2409.08861) — *research-code, RF-native.* The exact
  ODE→controlled-SDE conversion + the memoryless-noise condition for an **unbiased** tilt. Needs a
  differentiable terminal reward (smooth-surrogate a hard R). It's a finetune (S4-adjacent), not inference.
- **SVDD (soft value-based decoding)** — [2408.08252](https://arxiv.org/abs/2408.08252) — *research-code.*
  **Derivative-free** look-ahead: estimate `V(z_t,t)=E[exp(−λD)|z_t]` and reweight/select denoising steps.
  Solves two things at once: the intermediate-`t` `∇D`-undefined problem, and steering with a
  **non-differentiable R** (a hard self-similarity stat your gradient route can't touch). Needs value
  estimates via short rollouts or a learned critic.
- **MPPI ↔ diffusion** — [2502.20476](https://arxiv.org/abs/2502.20476) — *paper-only (MPPI code very mature).*
  The reverse-flow update **is** an MPPI step; the tilt is a derivative-free reward-weighted average over
  noise-perturbed rollouts — no resample-collapse. Also yields a receding-horizon MPC loop that could drive S8.
- **SOCM** — [2312.02027](https://arxiv.org/abs/2312.02027) — *research-code.* A low-variance least-squares
  target for g_φ (better than naive adjoint/IDO regression when the reward is weak). Offline training, needs
  a differentiable terminal cost.
- **Novelty-reward feeds for g_φ:** **ICM** [1705.05363](https://arxiv.org/abs/1705.05363) — "a loop is
  maximally self-predictable, so surprise → 0 inside the attractor" (complementary to distance-based R);
  **DRND anti-exploration** [2401.09750](https://arxiv.org/abs/2401.09750) — a calibrated "have I seen this
  state" detector (pseudo-count), ports cleanly (state-only, no actions).

---

## 5. S5 — twisted-SMC / particle refinements

- **Stein Particle Filter (resampling-free)** — [2202.04213](https://arxiv.org/abs/2202.04213) — *research-code.*
  Resampling **duplicates the highest-weight particle**, which in a loop regime *is* the attractor phrase —
  reinforcing collapse. Swap resample for repulsive RKHS attraction-repulsion coupling. Substantial recast
  (it's a state-estimation filter; must become an SMC over the latent sequence with the flow prior as dynamics).
- **NETS (non-equilibrium transport)** — [2410.02711](https://arxiv.org/abs/2410.02711) — *research-code.*
  A learned drift trained to **minimize FK weight variance** = your g_φ with an explicit objective; its
  Jarzynski correction keeps S5 *unbiased* when S8 injects escape noise (breaks detailed balance safely).
  Nice S5×S8 unifier. Needs a training pass.
- **Particle Guidance** (see §2) — the FK-twist identity is what lets repulsion serve S1 and S5 with one mechanism.

---

## 6. S6 — structure prior (cheaper cousins of Koopman/SSM)

- **SemanticAudio** — [2601.21402](https://arxiv.org/abs/2601.21402) — *paper-only, RF + continuous-latent.*
  Already a **two-stage rectified-flow planner** in a compact 64-dim continuous semantic space → nearest to
  drop-in for S6, and its planner trajectory is a ready **R_data**. Work: a semantic encoder over SA3's
  256-d latent + a low-rate planner flow + cross-attn/concat into the frozen DiT. **Lowest-risk match in the lane.**
- **MusiCoT** — [2503.19611](https://arxiv.org/abs/2503.19611) — *paper-only.* A CLAP-embedding "chain of
  musical thoughts" = a low-rate long-range descriptor; use as R_data and/or the plan g_φ conditions on.
  Port the concept (its backbone is AR); needs a CLAP→latent conditioning bridge.
- **MusicWeaver** — [2509.21714](https://arxiv.org/abs/2509.21714) — *paper-only.* Plan + **motif-memory
  retrieval** — couples S6×S7 and fights the loop by re-surfacing *planned* motifs on a schedule rather than
  a blind novelty penalty (a targeted alternative to §1's tilt).
- **SongBloom** — [2506.07634](https://arxiv.org/abs/2506.07634) — *shipping code.* Interleaved sketch→refine
  cascade carrying long-range context forward; an alternative to S3/S4 forcing finetunes. Adopt the schedule
  (sketch=low-rate latent, refine=full-rate flow), not the AR backbone.
- **Whole-Song Cascaded Diffusion** — [2405.09901](https://arxiv.org/abs/2405.09901) — *research-code, anchor.*
  The canonical form-level-latent-conditions-fine-stage pattern; symbolic, so pattern-only.

---

## 7. Honest dead-ends (so nobody re-digs)

- **min-p / typical / eta / no-repeat-ngram / frequency penalties** ([2407.01082](https://arxiv.org/abs/2407.01082)
  et al.) — categorical, non-differentiable; **cannot become the latent tilt** (this answers the brief's
  explicit sub-question). Salvage only the confidence-adaptive *schedule* idea for the S8 controller.
- **DoLa layer-contrast** ([2309.03883](https://arxiv.org/abs/2309.03883)) — no latent analogue without first
  building an auxiliary block→velocity readout head; most speculative. Worth a *probe* only (is the shallow
  layer predicting the repeat while the deep layer predicts the novel continuation? — a testable attractor signature).
- **Look-back decoding** ([2305.13477](https://arxiv.org/abs/2305.13477)) — the KL-to-history idea is sound but
  is subsumed by the differentiable R forms in §1 (it's a discrete-distribution special case).
- **Neural-transport parallel tempering** ([2502.10328](https://arxiv.org/abs/2502.10328)) — genuinely orthogonal
  escape (hot/cold replica exchange with a learned transport map), but costliest: two long chains + a trained
  transport. Research bet; direct evidence it breaks a *rollout* attractor specifically is thin.

---

## 8. Suggested read order (if picking up 3-4)

1. **Restart Sampling** + **Adjoint Matching** — the §0 corrections; read before touching S1 code.
2. **SPELL** + one R from §1 (**soft-RQA** or **DPP log-det**) — the cheapest concrete S1 upgrade to prototype.
3. **SVDD** — unlocks a non-differentiable R and fixes the intermediate-`t` gradient problem, derivative-free.
4. **SemanticAudio** — if S6 gets greenlit, this is the RF-native template, not just a cite.

Ranked against the fleet's committed path (synopsis §6): these sharpen the **S1 go/no-go** (better R + the
SOC/restart corrections make the cheap test actually fair), de-risk **S2** (SOCM/Adjoint-Matching give a
well-posed loss), and hand **S5/S8** principled machinery. None displaces the `p*` thesis — they refine how
each family draws from it.

---

# Addendum — three deep digs on the open questions this raised

*Follow-up 2026-07-15, same session: three focused agents on the three most decision-relevant open
questions the refinements surfaced. Same provenance caveat — light-fetch, per-item verification flags
noted; re-fetch before load-bearing use.*

## A. Can you estimate the cost-to-go `h_t` cheaply? (does §0.1 become buildable)

**Verdict: partial — solved-ish IF you'll train a small value head; the exact corner you want is open.**
The 2025-26 flow-alignment literature now gives a one-forward-pass `∇log h_t` on noisy latents, but every
option collides with **D's non-differentiability**, and they split on which side they pay:

| Method | id / code | what it gives | the catch |
|---|---|---|---|
| **VGG-Flow** (Value Gradient Guidance) | [2512.05116](https://arxiv.org/abs/2512.05116) | HJB-derived value-gradient net; optimal residual velocity = `∇V` — *exactly* the `u_t=σ²∇log h_t` identity, RF-native | a **finetune**; boundary loss needs `∇r` → smooth surrogate of D |
| **StitchVM** | [2605.19804](https://arxiv.org/abs/2605.19804) | graft a truncated clean-reward model onto the **frozen** backbone → correct value on noisy latents, ~10 GPU-h | needs a **differentiable** clean reward to truncate |
| **Explicit Critic Guidance** | [2605.27736](https://arxiv.org/abs/2605.27736) | reuse the DiT itself as `V(z_t,t)`, trajectory-PPO; one critic pass/step, **derivative-free in D** (terminal reward via the return) | an RL training loop — but the best fit for a non-diff recurrence stat |
| **FMRG** (Flow Map Reward Guidance) | [2604.27147](https://arxiv.org/abs/2604.27147) · [code](https://github.com/jrrhuang/fmrg) | **training-free**: use the distilled few-step flow map as an *exact* lookahead to t=1 and guide at the true endpoint — literally the fix to "naive x̂₀ under-steers," no value net, no SMC | needs a **distilled flow map** of SA3 + differentiable `r` |
| **Diffusion Tree Sampling** | [2506.20701](https://arxiv.org/abs/2506.20701) | MCTS-style: propagate terminal rewards up a cached tree, reuse compute; asymptotically exact, handles non-diff D | it *is* rollout/particle-adjacent (what you wanted to avoid) — just the best-amortizing member |
| **ACSSM** (amortized h-transform) | [2410.05602](https://arxiv.org/abs/2410.05602) · [code](https://github.com/bw-park/ACSSM) | ICLR'25 oral; amortizes **Doob's h-transform** (= the exact soft value) with a learned control net instead of SMC | wrong domain (time-series SSM inference); port the objective, swap terminal potential for `exp(−λD)` |

The clean fork: **(a)** train a small critic — VGG-Flow / StitchVM (frozen prior) / **Explicit-Critic (derivative-free in D, the standout for a hard recurrence stat)** → one pass at inference; or **(b)** training-free **FMRG**'s exact-endpoint lookahead if you distill a flow map and give D a smooth surrogate. A *free, training-free, exact `h_t` for an arbitrary non-differentiable terminal statistic on a frozen prior* does not exist — that precise corner is genuinely open. (Anchor for the control-variate route you asked about: DReG, [1810.04152](https://arxiv.org/abs/1810.04152).)

## B. Is there real theory for "repel your own past"? (the exactness gap in §2's repulsion)

**Verdict: yes — one principled, target-preserving construction, with a partial guarantee for your setting.**
- **Score-Repellent Monte Carlo (SRMC)** — [2604.22948](https://arxiv.org/abs/2604.22948) — keep a running average `θ_n` of past **score** evaluations and tilt the target to `π·exp(−α·θᵀs)`; since `E_π[s]=0`, a nonzero `θ` means "over-explored these directions." **Normalization-free drop-in** to any reverse SDE, proven **asymptotically unbiased** (`θ_n→0`), with a **CLT** and **O(1/α) variance reduction**. The right thing to adapt.
- **Self-Repellent Random Walks (SRRW)** — [2305.05097](https://arxiv.org/abs/2305.05097) (ICML'23 oral) — the rigorous discrete parent: empirical measure → the *exact* target, CLT, O(1/α). The "repel your past AND still land on the right measure" theorem, on finite graphs.
- **Backbone theory (continuous):** self-interacting diffusions (Benaïm–Ledoux–Raimond) — self-repelling regime converges a.s. to a well-defined invariant measure, stronger repulsion ⇒ faster; and the true self-avoiding walk / self-repelling Brownian polymer (Tóth–Valkó; Horváth–Tóth–Vető [0912.5174]) — the exact "flow down the gradient of your own local time" drift, diffusive scaling in d≥3.
- **The diagnosis, sharpened:** reinforced random walks (VRRW / Pemantle–Volkov) — **positive** self-reinforcement *localizes* (**= your loop attractor**), **negative** reinforcement escapes, with a studied phase transition. This is the cleanest dynamical-systems name for the bug.

The catch: SRMC/SRRW exactness assumes a *fixed stationary target reached by ergodic time-averaging with the history statistic self-averaging to 0* — a finite-horizon generative trajectory (you *want* to keep moving, not converge) breaks those premises. So the **construction transfers cleanly; the exactness theorem does not, verbatim.** New sub-question worth a theory pass: is a finite-horizon analogue of the unbiasedness recoverable via an `α`-schedule or a terminal correction? (CONTINUITY's lane.)

## C. Does the escape kick turn the loop into mush? (the S1×S8 headline risk)

**Verdict: needs adaptation, not a wall — and it reduces to one testable hypothesis.** Every non-isotropic
re-noise operator you'd need already exists and is Gaussian-clean; the *only* missing piece is a validated
basis in the learned latent that separates melody from the beat grid:
- **SAGD** (spectrally anisotropic Gaussian diffusion) — [2510.09660](https://arxiv.org/abs/2510.09660) — frequency-diagonal forward covariance, band-selective noise, score relation derived. Closest to "noise only a band."
- **Subspace Diffusion** — [2205.01490](https://arxiv.org/abs/2205.01490) ([code](https://github.com/bjing2016/subspace-diffusion)) — noise a subspace, hold its complement; needs a known melody subspace.
- **Blurring / Heat-Dissipation + Cold Diffusion** — [2209.05557](https://arxiv.org/abs/2209.05557) / [2208.09392](https://arxiv.org/abs/2208.09392) — noise diagonalized in the frequency (DCT) basis, high-freq dissolves first: a coarse/fine handle with a **strong prior that rhythm ≈ low-frequency**.
- **Non-Isotropic Gaussian Diffusion** — [2210.12254](https://arxiv.org/abs/2210.12254) — the general arbitrary-Σ forward math under all of the above (you still must *choose* Σ).
- **The negative control:** **Music Boomerang** — [2507.04864](https://arxiv.org/abs/2507.04864) — applies isotropic renoise to audio latents and explicitly reports it "is not possible to ask for changing a particular voice." Confirms the gap: plain restart spares rhythm *only* because it barely perturbs anything.
- **The basis-finding step:** latent-disentanglement / directional editing on DiTs — [2411.08196](https://arxiv.org/abs/2411.08196) — locate the melody direction, edit along it, project out the rest.

**The testable hypothesis (cheap, do first):** because rhythm is your *noise-invariant* emergent, it almost
certainly occupies the low-frequency / low-variance latent directions — so a **frequency- or variance-graded
renoise** (SAGD / blurring) may *already* spare the beat grid. Probe it with a PCA/FFT split of the latent
before investing in learned disentanglement.

## D. How the three interlock (the actually-new thread)

They share one blocker and one unification:

1. **The recurring blocker is D's non-differentiability.** A's gradient value-nets need a smooth surrogate;
   A's critic/tree methods are derivative-free but pay training/search; C's operators are all "given a Σ."
2. **B dissolves that blocker.** SRMC repels in **score space** (`∇log π`, which the flow gives you directly),
   not reward space — so a **score-repellent tilt is a differentiable D by construction**, sidestepping exactly
   what blocks A's cleanest methods.
3. **A + B unify cleanly.** SRMC's `π·exp(−α θᵀs)` *is* a value/SOC exp-tilt, so its cost-to-go is amortizable
   by A's critic (Explicit-Critic / VGG-Flow). C then makes the application non-destructive.

**Assembled candidate recipe (S1+S2+S8 in one):** use a **score-repellent tilt** (B, differentiable in score
space) as the anti-loop `D`; amortize its cost-to-go with a **derivative-free critic** (A, Explicit-Critic) so
you get the right `∇log h_t` in one pass rather than the myopic `∇D`; and apply it via a **feature-selective /
variance-graded restart** (C) so escaping the melodic loop doesn't erase the beat. Each piece has a paper; the
novelty is the composition and two portability gaps (SRMC's finite-horizon premise, the melody-vs-beat basis).

**Two new open sub-questions to bank:** (1) a finite-horizon unbiasedness analogue for SRMC (§B); (2) does
"rhythm = low-freq/low-variance latent directions" actually hold on SAME latents (§C — a one-afternoon PCA/FFT
probe that gates the whole selective-renoise plan).
