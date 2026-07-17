# Research Synopsis — Long-Form Continuation as Constrained Sampling from a Statistic-Blind Flow

*(WINTERMUTE, 2026-07-14, at Kim's request. Grounds: `docs/a2a-loop-attractor.md`,
`docs/layer-feature-noise-invariance.md`, `docs/layer-feature-map.md`, the 2026-07-08
infinite-horizon triage (WORKLOG), `incantation_experiment.py::loopiness`, C's SaFa result.
Status: PROBLEM FORMULATION + solution-family survey for LUMI/Gemini follow-up. Theory
review flagged to CONTINUITY. Not a plan — a map of the space and a ranked probe list.)*

---

## 0. TL;DR — the one-sentence framing

**Long-form continuation is sampling from the base rectified-flow prior *tilted* by a
long-range temporal statistic (novelty / recurrence spectrum) that the flow-matching
training objective is structurally blind to.** The model loops because nothing in its loss
ever penalised looping; every viable fix is a different way to supply that missing
long-range signal — at inference (guidance / SMC / control), via an auxiliary head (a
learned steering model), or by retraining the base so the prior itself carries the
structure (diffusion-forcing / self-forcing).

$$
p^\*(z) \;\propto\; \underbrace{p_\theta(z)}_{\text{SA3 flow prior}}\;\cdot\;
\exp\!\Big(-\lambda\, D\big(R(z),\,R_{\text{data}}\big)\Big),
\qquad R(z)=\text{recurrence/novelty statistic}.
$$

Everything below is a way to approximate a draw from $p^\*$.

---

## 1. What SA3 actually is (the architecture that constrains the solution space)

- **Generative process:** rectified flow / flow-matching. A DiT $v_\theta(z_t,t,c)$ predicts
  a velocity field; sampling integrates the ODE $\dot z = v_\theta$ from Gaussian noise
  ($t{=}1$) to data ($t{=}0$), conditioned on text $c$ (T5-Gemma) and an optional
  257-channel `local_add_cond` (inpaint mask + masked input).
- **State space:** a *continuous* compressed latent sequence $z\in\mathbb{R}^{256\times T}$ —
  256 SAME/VAE channels, one frame per 4096 audio samples ⇒ **10.767 Hz**, so $T{=}4096\approx
  380\,$s, $T{=}512\approx 47.6\,$s. This is the critical difference from LLM/video-token work:
  **no discrete vocabulary, no KV-cache token stream** — the "tokens" are continuous vectors on
  a learned manifold. Solutions that assume discreteness (LMDM-KV, token-level self-forcing)
  need translation, not transplant.
- **Training crop:** fixed $T$ (multiples of 256) for kernel/attention stability. Full-sequence
  attention ⇒ inference beyond the trained horizon degrades and costs $O(T^2)$.
- **What "continuation" means today:** three machined paths —
  (a) **fixed long render** (one-shot $T{=}2048/4096$; limited by train-length generalization +
  attention cost);
  (b) **sliding-window** (`LongFormRenderer`: window + slerp/`CrossfadeStitcher` + prompt
  schedule; FIFO-diffusion variant kept);
  (c) **a2a renoise** (audio-to-audio SDEdit/renoise; the loop-attractor's home turf).

The three known internal facts that any theory must respect:

| Fact (measured) | Source | Consequence |
|---|---|---|
| **Rhythm is a noise-INVARIANT emergent** (beat R² 0.80 @ L14, rebuilt regardless of input noise) | noise-invariance sweep | the beat grid survives everything → loops are beat-locked and sound "coherent" |
| **Harmony/melody are degraded-and-ABANDONED** at mid/high noise (hpcp, rms_mid R²→~0.08) | noise-invariance sweep | where the source stops constraining, the melodic slot is filled by the **corpus mean** (U-shape) then frozen |
| **Loops are the whole spectral image repeating**, not a single feature | recurrence-meter v3 (whitened patch) | naive frame-cosine saturates (0.99 on the steady kick); must whiten per-channel to see it |

---

## 2. The walls, as failure modes (empirical → mechanistic)

1. **The loop-attractor** *(the headline wall).* In regions where source/context no longer
   constrains, the model's only temporal context is its own emerging output. The DiT's strong
   periodicity prior locks onto the first-formed phrase → a **self-feeding fixed point**. It
   persists for minutes; signal-level meters miss it (beat-locked, static-but-coherent).
   *Mechanistically:* a **limit cycle / low-entropy attractor of the autoregressive map**.

2. **Exposure bias / compounding drift.** Training conditions on *clean* (data) context;
   inference conditions on *model-generated* context. The distribution mismatch
   $p_{\text{data}}(\text{ctx})\!\ne\!p_\theta(\text{ctx})$ compounds over the rollout ⇒ the
   chain drifts off-manifold (the "depth / pad-fill" drift signature). Classic autoregressive
   exposure bias, now in a continuous latent.

3. **Posterior-mean collapse of the abandoned features.** RF reconstructs a *global* crop
   property (genre, gross timbre) but the melodic slot, unconstrained, regresses to the corpus
   mean — generic filler — which the repetition prior then freezes into (1).

4. **Seam / HF-variance mismatch** *(SaFa territory).* Window stitching leaves spectral seams;
   C's SaFa reference-swap cut seam HF-variance (~0.818×) but **left loopiness identical** — SaFa
   fixes the *join*, not the *attractor*. (My co-score confirmed: loopiness 0.680 both arms,
   ~0.024 under the 0.704 static-longform baseline — i.e. no worse than a drone, no better.)

5. **Train-length generalization.** Fixed renders past the trained $T$ map badly onto
   kernels and onto a length the model never saw; the $T{=}4096$ crop discipline was a training
   fix, not an inference cure.

**The unifying diagnosis.** Flow-matching loss is a *per-step, local* denoising objective. It
has **zero gradient pressure on any long-range temporal statistic** — recurrence spectrum,
novelty rate, section structure, drift. So the model is free to get them arbitrarily wrong, and
the maximum-likelihood thing to do in an unconstrained region *is* to repeat (lowest-surprise
continuation). Looping is not a bug in the sampler; it is the **faithful behaviour of a prior
that was never told long-range novelty matters.** This is exactly the scope condition where our
own **meter-in-the-gradient** rule says an auxiliary signal helps: RF is blind to it, so adding
it is pure new information (contrast: genre, which RF already captures, where the meter only hurt).

---

## 3. The mathematical problem, four equivalent lenses

**(A) Autoregressive map / dynamical systems.** Factor $z=(z^1,\dots,z^K)$ into blocks;
$z^k\sim p_\theta(\cdot\mid \text{ctx}(z^{<k}))$. Continuation iterates a stochastic map
$F_\theta:\text{ctx}\mapsto\text{next block}$. **The loop is a limit cycle / attractor of
$F_\theta$; drift is divergence of its trajectory off the data manifold.** We want $F_\theta$'s
invariant measure to be *mixing with the data's entropy rate*, not collapsing to a cycle.

**(B) Measure-theoretic / typical-set.** A long real track is a draw from $\mu$ over
$\mathbb{R}^{256\times T_{\text{tot}}}$. We train on the short-window marginal $\mu_W$ and
sample a Markov chain whose stationary law $\nu_\theta\ne\mu$: it concentrates on a
low-entropy set (loops). **Target: a sampler whose invariant measure reproduces the data's
long-range autocorrelation / recurrence spectrum** (real music's self-similarity has
characteristic structure — motifs return, but a bar does not repeat for 3 minutes).

**(C) Optimal control / steering (Kim's framing, formalized).** We *always* hold a receding
window of real-or-generated context. Treat the reverse flow as a controlled ODE
$\dot z = v_\theta(z_t,t,c) + u_t$ and choose the control $u_t$ (equivalently a guidance term)
to minimise a running cost:
$$
J=\int_0^1\!\Big[\underbrace{\|u_t\|^2}_{\text{stay on the flow prior}}
+\alpha\,\ell_{\text{id}}(z_t,\text{ctx})
+\beta\,\ell_{\text{nov}}\big(R(z_t),R_{\text{src}}\big)\Big]dt .
$$
This is **model-predictive control over the latent trajectory** — and it is *not* inpainting.
Inpainting fixes a known region and generates the complement **under the same prior**;
steering-continuation actively bends the generative trajectory with an **auxiliary operator**
and always has fresh context to condition on. The breathing controller (task #35) is the
scalar, window-level special case of exactly this $J$ (the novelty term as a Schmitt trigger on
nl).

**(D) Constrained / tilted sampling.** The $p^\*$ of §0: draw from the prior tilted by a
novelty potential. $R(z)$ = our whitened-patch recurrence statistic (differentiable). Sampling
$p^\*$ is the umbrella that unifies every method below:
- **guidance** ⇒ add $-\lambda\nabla_z D(R,R_{\text{data}})$ to the velocity (gradient of the log-tilt);
- **SMC / Feynman–Kac** ⇒ importance-weight particles by the tilt;
- **learned steering model** ⇒ amortise the tilt into a net $g_\phi$;
- **retrain (diffusion-/self-forcing)** ⇒ move $p_\theta$ itself toward $p^\*$.

---

## 4. Solution families (ranked by fit-to-us × principled-ness; not all audio, not all diffusion)

**S1 — Recurrence-guidance, inference-only (cheapest; validate the tilt first).**
Add the differentiable novelty penalty $-\lambda\nabla_z D(R(z_t),R_{\text{src}})$ as a
guidance term in the reverse flow (Selective-TFG mechanics we already run for LatCH). No
training; reuses `renoise_hook` + the v3 whitened-patch meter. **This is the direct test of
§0's central claim** — if a novelty tilt breaks the loop, the whole framing is validated
before spending GPU-hours. Local-card prototypable.

**S2 — Learned steering model $g_\phi$ (Kim's idea; the most "us").**
A small net (LatCH-scale, rides the frozen SA3 flow) $g_\phi(\text{ctx},z_t,t)\to\Delta v$,
trained with a **long-horizon objective the base RF-loss lacks**: rollout loss + novelty/recurrence
match + identity. Three training routes, in increasing ambition:
(i) **distill** best-of-K recurrence-selected rollouts into $g_\phi$ (cheap, supervised);
(ii) **RL / reward** — reward = novelty − drift (our meters *are* the reward), policy-gradient
on rollouts;
(iii) **supervised on real long tracks** with teacher-forcing-under-noise (diffusion-forcing-style
context corruption).
We have the entire substrate: LatCH/control head infra, the meters, the whole-track latent store
(`latents_sa3` + `.TIMESERIES.npz` with the `relative_position_ts` ramp). Formally $g_\phi$ is an
**amortised sampler for $p^\*$** — this is the publishable version of Kim's "steering model."

**S3 — Diffusion-Forcing / Rolling-Diffusion / History-Guidance finetune (most principled; biggest LUMI spend).**
Train/sample with **independent per-frame noise levels** so the model learns to denoise
conditioned on partially-noised history ⇒ stable long rollouts + built-in exposure-bias
robustness (History-Guided / Diffusion-Forcing Transformer; Rolling Diffusion = a moving window
of future-increasing noise). We *skipped* this in July ("needs arch changes") — with thousands of
LUMI hours a diffusion-forcing **finetune** of SA3 (not from scratch) is now the flagship
candidate. Caveat from §1: adapt for *continuous* latents (per-frame continuous noise schedule),
not token streams.

**S4 — Self-Forcing (train on your own rollouts).**
The textbook exposure-bias cure: during finetune, condition on **model-generated** context so
train≡test. Flagged before as "self-forcing-lite, LUMI candidate." Pairs naturally with a
novelty reward so the model learns to *not* loop, not merely to tolerate its own errors.
(Autoregressive-video precedents: Self-Forcing, CausVid.)

**S5 — Twisted-SMC / Feynman–Kac steering (principled inference-time; no retrain).**
Run $K$ latent particles, resample by a novelty+identity potential ⇒ the population avoids the
attractor while sampling *exactly* $p_\theta\cdot(\text{tilt})$. The SimDPS / SMC-diffusion line
already on the reading list. Heavier than S1 but with correctness guarantees S1 lacks.

**S6 — Explicit long-range prior over the latent path (SSM / Koopman; the non-diffusion import).**
Model the *slow* macro-structure (sections, arrangement) with a state-space model / Koopman
linear-dynamics operator over the frame sequence, and let the diffusion decorate local texture.
Music's genuine long-range dependency lives in the arrangement, not the waveform; an SSM/Koopman
prior gives the novelty spectrum an **eigenstructure** to sample from. Imports S4/Mamba +
Koopman-operator theory for dynamical systems — Kim's "doesn't have to be diffusion" door.

**S7 — Retrieval / reference conditioning (SaFa generalized).**
Inject reference-window latents (earlier-in-track or retrieved-from-corpus) into later windows'
high-noise steps to re-supply the *abandoned* features (§1) and enforce variation-with-identity.
This is literally Kim's "it always has some of the original data to work with" — a
**retrieval-augmented continuation**. SaFa is the seam-level instance; the general version
retrieves to fight the attractor, not just the join.

**S8 — Breathing closed-loop controller (designed, task #35; the control-theoretic baseline).**
Schmitt-trigger nl control driven by the whitened-patch recurrence meter, source-calibrated
($R_{\text{src,p95}}$). Window-level (Tier 1, ~50 lines) then step-level (Tier 2, `renoise_hook`).
The scalar special case of S1/§3-C; the pragmatic first thing to *ship*, and the instrument the
others are measured against.

---

## 5. What to probe on Gemini (open-ended lit digging — verify-first, per fleet rule)

1. Diffusion-Forcing / Rolling-Diffusion / History-Guidance for **continuous** (non-token)
   latent sequences — has anyone done per-frame continuous noise on audio/latent VAEs?
2. Exposure-bias / self-forcing correction in **continuous** diffusion (most self-forcing is
   token/video).
3. **Twisted SMC / Feynman–Kac steering** of diffusion for statistic-constrained sampling —
   maturity, cost, continuous-state variants.
4. **Amortised guidance / learned correctors** — training a small net to emit guidance/velocity
   corrections for a frozen diffusion prior (the S2 prior art).
5. **Koopman / SSM hybrid priors** for long-range structure in generative sequence models.
6. Any formalization of **"generation collapses to low-entropy attractors"** (StoryScope's
   structural-rarity finding is the fiction analogue — is there a general theory?).

## 6. Ranked experimental path (LUMI + local)

1. **S1 recurrence-guidance prototype** — local/1 GPU, days. *Go/no-go on the whole §0 thesis.*
2. **S8 breathing controller Tier 1** — ships regardless; the measurement harness for everything.
3. **S2 steering model, route (i) distillation** — modest LUMI; our infra, our meters.
4. **S3 diffusion-forcing finetune** — flagship LUMI campaign *iff* S1 confirms the tilt helps
   but inference-only proves too weak/slow.
5. **S5 / S6** — research bets to run in parallel on spare hours; S6 is the highest-variance,
   highest-upside (a real long-range prior would change the ceiling, not just the symptom).

---

## 7. The single figure of merit

Everything reduces to one measurable: **does the generated trajectory's recurrence/novelty
spectrum $R(z)$ match real long tracks' $R_{\text{data}}$, while identity and local coherence
hold?** The v3 whitened-patch meter already computes it; the null baselines (static-longform
loopiness ≈ 0.704) and C's SaFa co-score (0.680) are the current floor. A method that moves
$R(z)$ toward $R_{\text{data}}$ *without* wrecking identity is the win — and $R$ is differentiable,
so it can be the guidance term, the reward, and the eval, all at once.
