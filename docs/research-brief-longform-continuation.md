# Long-form continuation past the loop-attractor — Gemini Deep Research brief

*2026-07-14, THE-FINN (Kim's ask: read the day's discussions, formulate a Gemini Deep
Research synopsis for anything worth digging into, plus do our own web research in
parallel). Grounds: WINTERMUTE's `docs/research-synopsis-longform-continuation.md`
(2026-07-14, written at Kim's request — math-first problem formulation + 8 ranked
solution families), `docs/a2a-loop-attractor.md`, `docs/layer-feature-noise-invariance.md`,
C's SaFa result (join-level fix, loopiness untouched). THE-FINN drives the lit survey /
Gemini pass; theory rigor-check is CONTINUITY's lane per W's DM (`continuity.wintermute.log`
2026-07-14 22:32). Not a plan — a research map for Kim's Gemini probes, condensed to
Gemini-sized questions from W's §5 list.</em>*

## The one-paragraph framing (give this to Gemini verbatim as context)

We have a rectified-flow / flow-matching diffusion transformer that generates music as a
**continuous latent sequence** (256-channel VAE-style latents at ~10.8 Hz — no discrete
vocabulary, no token stream, no KV-cache in the LLM sense). Trained on fixed-length crops
(multiples of 256 frames), it degrades badly past that horizon. Long-form generation today
uses sliding windows / audio-to-audio renoise continuation, and reliably collapses into a
**loop attractor**: once the real source audio stops constraining the generation, the model's
only temporal context is its own prior output, and it locks onto the first-formed phrase —
a self-feeding fixed point that persists for minutes and is *beat-locked* (so it sounds
locally coherent, not broken — signal-level meters miss it; only a whitened long-range
recurrence/novelty statistic catches it). We believe this is not a sampler bug but the
faithful behavior of a training loss (per-step local denoising) that has **zero gradient
pressure on any long-range temporal statistic** — so the maximum-likelihood thing to do in
an unconstrained region is to repeat. Our working hypothesis: long-form continuation is
sampling from the base flow prior $p_\theta$ *tilted* by a long-range recurrence statistic
$R$ the base loss never sees:
$$p^*(z) \propto p_\theta(z)\cdot\exp(-\lambda\, D(R(z), R_{\text{data}})).$$
We want literature on how to approximate a draw from $p^*$ — at inference (guidance / SMC),
via a trained auxiliary net (amortized steering), or by changing what the base prior *is*
(diffusion-forcing / self-forcing retraining) — with special attention to whether any of it
has been done for **continuous, non-token, non-video** latent sequences, since almost all of
the adjacent literature (self-forcing, diffusion forcing, token-level KV-cache tricks) was
built for discrete-token autoregressive-video or LLM settings and needs translation, not
transplant, to a continuous-latent audio DiT.

## Questions for Deep Research

1. **Diffusion-Forcing / Rolling-Diffusion / History-Guidance for CONTINUOUS (non-token)
   latent sequences.** The original Diffusion Forcing (Chen et al.), Rolling Diffusion
   (Ruhe et al.), and History-Guided Diffusion Forcing Transformer lines give each
   frame/token an independent noise level so a model learns to denoise conditioned on
   partially-noised history. All known instances are token- or video-latent-based. Has
   anyone run per-frame independent noise scheduling on a *continuous* audio or generic
   continuous-latent sequence model? What would the translation cost (continuous noise
   schedule per frame vs. discrete diffusion timestep per token)?
2. **Exposure-bias / self-forcing correction in continuous diffusion.** "Self-Forcing"
   (train on the model's own rollouts so train ≡ test) has recent autoregressive-video
   instances (Self-Forcing, CausVid). Any continuous-latent-audio or continuous-state
   analogue? What does the training recipe look like without a discrete vocabulary to
   condition on?
3. **Twisted SMC / Feynman-Kac steering of diffusion for statistic-constrained sampling.**
   Twisted Diffusion Sampler / SMC-diffusion lines exist for single-sample conditional
   generation. Maturity, particle-count cost, and — critically — has this been extended to
   *sequential/temporal* rollouts (windowed audio/video) rather than one-shot conditional
   image sampling? Exact vs. asymptotic guarantees?
4. **Amortised guidance / learned correctors.** Training a small net to emit a guidance or
   velocity correction for a frozen diffusion/flow prior, as a cheap substitute for
   per-step classifier guidance or SMC. Anything targeting a *long-horizon / sequence-level*
   property (not just a static per-sample label)? This is the closest prior art to our "small
   steering head riding the frozen backbone" plan (we already have the infrastructure —
   LatCH-style auxiliary heads — so this is our most implementable path if precedent exists).
5. **Koopman-operator / state-space-model (SSM) hybrid priors for long-range structure.**
   Any work modeling the *macro* structure (sections, arrangement, novelty spectrum) of a
   generated sequence with a separate linear-dynamics or state-space "skeleton," while a
   local diffusion/autoregressive model fills in texture? This is our highest-variance,
   highest-upside candidate (a real long-range prior changes the ceiling, not just the
   symptom) — is there real precedent, or would it be a genuinely novel combination for
   continuous-latent music generation?
6. **Is there a general theory of "generation collapsing to a low-entropy attractor /
   limit cycle" during long rollout, across modalities?** We have an internal analogue
   from fiction generation (a finding that AI-generated narrative has lower structural
   novelty/rarity than human writing on some metric) but haven't independently verified
   its source. Is there a dynamical-systems framing of autoregressive/iterative sampling as
   a stochastic map with attractors, and any cross-modality (text-degeneration, RNN dynamics,
   video-rollout collapse) literature that names this phenomenon directly?

## What NOT to re-litigate
Min-SNR / P2 loss reweighting, generic classifier/CFG guidance, and vanilla AdaLoRA-style
PEFT are already known to us from the relevance-routed-DoRA brief — Gemini shouldn't
resurface these as if novel. Same for plain sliding-window crossfade/SDEdit stitching
(that's SaFa's territory, already measured: fixes the seam, not the attractor).

## How the answer gets used
Ranked experimental path already committed (W's synopsis §6): S1 recurrence-guidance
prototype (go/no-go on the whole tilted-sampling thesis, local GPU, days) → S8 breathing
controller (ships regardless, the measurement harness) → S2 learned steering model
(our infra) → S3 diffusion-forcing finetune (flagship LUMI, gated on S1 confirming the
tilt helps) → S5/S6 as parallel research bets. Gemini's answers to Q1–Q2 mainly de-risk
S3; Q3–Q4 de-risk S1/S2 (cheaper, ship sooner); Q5–Q6 are the speculative S6 bet — surface
strong prior art there before committing any LUMI hours to it.

---

## UPDATE 2026-07-14 — our own web research (3 parallel agents, ahead of Kim's Gemini pass)

*THE-FINN. All papers below were fetched/read (abstracts at minimum), not asserted from
memory — per fleet TADA-lesson. Anything not independently confirmed is flagged
explicitly as unverified rather than cited as fact.*

**Headline: the $p^*$ tilted-sampling framing itself (§0) is not literature-established —
no paper found unifies guidance/SMC/amortized-steering/retraining under one explicit
"the loss is statistic-blind, so tilt the sampler" framing.** That's good news (it's a
genuine synthesis, not a rediscovery) but it means nothing below validates the framing
wholesale — each piece below de-risks one *solution family*, not the thesis.

**Q1/Q2 (S3/S4 — diffusion-forcing & self-forcing, continuous latents):** Diffusion
Forcing (arXiv 2407.01392, NeurIPS'24), Rolling Diffusion (2402.09470, ICML'24), and
DFoT (2502.06764, ICML'25) are real, mature, and *do* target continuous (non-discretized)
tokens — but every verified instance is video/robotics, **none audio**. Self-Forcing
(2506.08009, NeurIPS'25 Spotlight) and Rolling Forcing (2509.25161, ICLR'26) are the
video-side self-forcing analogues; OmniForcing (2603.11647) is the nearest audio touch
but couples audio to video generation, not audio-only. **No verified paper does
diffusion-forcing or self-forcing on continuous music/audio latents.** The one directly
actionable find: **FloodDiffusion (2512.03520)** ported vanilla Diffusion Forcing to a
different continuous (non-video) modality — continuous human motion — **and it broke**,
needing three fixes: bidirectional (not causal) training attention, a lower-triangular
(not random) noise-time schedule, and continuous time-varying conditioning. **Read this
before any S3 LUMI spend** — it's the closest evidence for what breaks when DF leaves
video, and a plausible starting fix recipe rather than discovering the same failure mode
the hard way on LUMI hours.

**Q3 (S5 — twisted SMC / Feynman-Kac steering):** TDS (2306.17775, NeurIPS'23) and FK
steering (2501.06848, ICML'25) are the base mechanism (particle resample by an
exp(-λ·potential) weight each denoising step); FK Correctors (2503.02819, ICML'25
Spotlight) derives it from the underlying PDE. **FK-Flow (2509.01543) is the single
most load-bearing find in this whole sweep: it extends twisted-SMC/FK steering to flow
matching, sampling an "energy-tilted posterior" — mathematically the exact $p^*$ form
in §0**, with convergence theorems (tested on molecular data, not audio, but the math
transfers). **TRI-TSMC (2605.25123, May 2026)** directly addresses the practical
blocker — particle-count/weight-degeneracy cost — that would otherwise sink SMC over a
long sequence. Read FK-Flow + TRI-TSMC together before prototyping S5/S1: they give a
principled step-size/particle-count recipe instead of ad hoc tuning. No paper applies
any of this to sequential continuous-latent (video/audio) generation — the only
"sequential" twisted-SMC instances are discrete-token LLM decoding (LLaMPPL, 2306.03081
+ 2404.17546) — real gap, but LLaMPPL's "twist estimates expected future reward from a
partial sequence" is the closest conceptual cousin to windowed recurrence-tilting.

**Q4 (S2 — amortised guidance / learned steering net):** CFG-distillation-into-a-frozen-
adapter is mature and cheap (AGD, 2503.07274: ~2% params, frozen base) but every
verified instance targets a static per-sample condition (class/prompt/CLIP score), never
a sequence-global property. **"Learn to Guide Your Diffusion Model" (2510.00815, Google
DeepMind)** is the closest conceptual match — a general framework for amortizing
guidance toward an arbitrary reward-tilted distribution — read this first when
designing $g_\phi$, even though it's untested at sequence scale. Amortized Latent
Steering (2509.18116) proves the amortization pattern works for sequence-level
properties, but only in language models, not diffusion — a cross-domain existence proof,
not a diffusion result. **Building $g_\phi$ for a long-horizon recurrence tilt on a
frozen flow model is a confirmed-open combination — no paper does this.**

**Q5 (S6 — Koopman/SSM long-range prior):** Koopman-for-diffusion papers (2506.22304,
2512.18837) linearize the *denoising-step* axis, not the *content-time* axis — a
different thing than what we want, don't cite as precedent. **VideoSSM (2512.04519) is
the real template**: an SSM as a global macro-memory of scene dynamics, paired with a
local diffusion window for texture, explicitly built to fight drift/repetition/
"attention-sink collapse" — architecturally the closest thing to S6's design. Stability's
own long-form latent diffusion work (2404.10301, Evans/Parker) and an SSM-based music LM
(2507.06674) use SSMs as generic long-context backbones, not an explicit separate
macro-structure prior. **An SSM/Koopman arrangement-skeleton driving a continuous-latent
music-diffusion texture model is a genuinely novel combination** — VideoSSM is the paper
to adapt from, not just cite.

**Q6 (the attractor-collapse theory question):** we already have this one — StoryScope
is not a new find, it's `papers/knowledge.md`'s existing entry (Kim's 2026-07-08/09
rarity-lite work; PDF on file). My agent re-derived it independently via web search
rather than checking our own archive first (a real process gap, not a citation error —
worth remembering: check `papers/` before Gemini/web for anything that sounds like
prior fleet work). Its arXiv ID is now pinned for the first time: **2604.03136**,
confirmed against the live abstract (title + all 5 authors match exactly) — our existing
knowledge.md row didn't carry one. The 0.71 vs 0.49 rarity figures and Cohen's d=0.83 are
from the paper body (not the abstract), consistent with our existing summary. Holtzman's
"Neural Text Degeneration" (1904.09751, ICLR'20) is the most rigorous existing empirical
anchor (43% vs 0.5% repeated n-grams under greedy/beam decoding) but is decoding-focused,
not a dynamical-systems theory. RNN dynamical-systems work (fixed-point/limit-cycle/
chaos formalizations, e.g. 1612.06212) exists but was **never connected** to generation-
quality collapse. **No unified cross-modality theory exists.** Our own framing — an
autoregressive map $F_\theta$ whose invariant measure should be entropy-rate-mixing
rather than collapsing onto a low-period limit cycle (or, per Q5, a low-dimensional
Koopman eigenmode subspace) — is not present anywhere found. This may be worth writing
up as a real contribution in its own right, not just an engineering framing device.

### Net read for the ranked path (W's §6)
- **S1/S5 (guidance/SMC, cheap-first):** FK-Flow gives exact machinery for the tilt —
  read it before hand-rolling the guidance term; TRI-TSMC solves the cost objection that
  would otherwise rule SMC out at our sequence lengths.
- **S2 (learned steering net):** confirmed open; "Learn to Guide Your Diffusion Model"
  is the design reference.
- **S3 (diffusion-forcing finetune, flagship LUMI):** FloodDiffusion's failure-and-fix
  is a mandatory pre-read — vanilla DF likely breaks on continuous audio the same way it
  broke on continuous motion, and their 3 fixes are a plausible starting recipe.
- **S6 (Koopman/SSM):** VideoSSM is the concrete template; genuinely open for
  continuous-latent music, matches the "doesn't have to be diffusion" framing.
- **Overall:** nothing found de-risks $p^*$ itself — it stays our own synthesis to prove
  or break via S1's go/no-go, exactly as W scoped it.
