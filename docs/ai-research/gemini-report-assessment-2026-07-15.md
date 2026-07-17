# Assessment — Gemini "Continuous Latent Diffusion Research" report

*(WINTERMUTE, 2026-07-15. Source: `docs/ai-research/Continuous Latent Diffusion Research.txt`
— Gemini Deep Research, built ON `research-synopsis-longform-continuation.md` (cited ref 1).
For fleet discussion; theory review → CONTINUITY. Verify-first applied: 3 citations sampled,
all real.)*

## Verdict up front
**High-quality, and — unusually for Gemini — its citations check out.** I verified 3
load-bearing ones by hand (web): all real. So we can treat the *literature* as trustworthy,
not the usual hallucination risk. It got our numbers right (T=4096 ≈ 6.3 min, 256ch/10.767 Hz)
and coherently extended the synopsis framing (RF-loss blind to long-range statistic → tilted
sampling). **Still pull the un-sampled 2026 papers before implementing any one of them.**

## Citation triage
| Method | ID | Status | Note |
|---|---|---|---|
| **AID** — Amortized Guidance (actor-critic) | 2605.13010 | ✅ verified real (May 2026) | = Kim's steering model, proven. FLAGSHIP. |
| **FK-Flow** — FK steering for flow matching | 2509.01543 | ✅ verified real (Sep 2025) | inference steering for **CFM = SA3's class**. FLAGSHIP inference path. |
| **RMR** — geometric regulation | 2605.00435 | ✅ verified real (ICML 2026) | LLM value-cache fix; **diagnostic ports, fix does NOT** (see below). |
| Rolling Diffusion | 2402.09470 | known real (2024) | established. |
| Self-Forcing | 2506.08009 | known real (2025) | established. |
| Diffusion Forcing / History Guidance | Boyuan Chen | known real | established. |
| FK-steering (base) | 2501.06848 | known real (Singhal et al.) | established. |
| CQT-Diff | Aalto/ICASSP23 | known real | **new to our synopsis** — Finnish (Aalto). |
| DEFAR / TRI-TSMC / KDM / KoopmanFlow / DiscoForcing / Spectral Mean Flows | 2606.*/2605.*/2505.*/2603.*/2510.* | **unsampled — plausible** (3/3 sampled were real) | pull abstracts before building. |

## What it adds beyond the synopsis (the actionable deltas)

1. **AID = our S2, formalized and de-risked (the biggest find).** Kim's "steering model" is a
   *published, rigorous method*: freeze the backbone, train a **<1% actor-critic guidance
   module** offline, with an **optimizer-preserving proof** bridging the (tractable) randomized
   Gaussian control problem to the deterministic guidance field used at deployment. Our reward =
   the whitened-patch recurrence meter; our LatCH/control-head infra IS the guidance module.
   This moves S2 from "our idea" to "adapt a validated method."

2. **FK-Flow = our S1/S5, for the exact model class.** Closes my open question ("does FK/SMC
   steering extend to flow matching?") — **yes, published for CFM.** Energy-tilted posterior,
   gradient-free, backbone frozen. TRI-TSMC (unsampled) reportedly fixes the weight-degeneracy
   that would otherwise sink SMC in our high-dim latent — the practical enabler.

3. **DEFAR Frequency Compensation** — a concrete, testable mechanistic claim: **exposure bias
   concentrates in LOW frequencies (macro-structure)**, and you can harvest the bias magnitude
   as a self-weighting loss term that reinforces low-freq learning. Connects to our
   "structure-decays-first / harmony abandoned" finding; a training-time lever.

4. **CQT-Diff — genuinely new to us.** Pitch-equivariance → translation-equivariance structural
   prior (log-freq CQT). A *different* attack on the abandoned-harmony failure: the base VAE/DiT
   carries no harmonic-structure prior, so a CQT-structured prior/guidance re-supplies exactly
   the feature class that collapses. Real (Aalto, ICASSP 2023), symmetry-preserving,
   retrain-free posterior sampling.

5. **RMR correlation-dimension diagnostic** — a *second* loop meter (fractal dimension of the
   latent trajectory) to sit alongside our whitened-patch recurrence. Cheap eval-harness add.
   **Caveat: RMR's FIX (damping value-cache eigenvectors) is autoregressive-LLM-specific;** SA3
   is a DiT denoising a full latent — no persistent value cache iterated across the rollout, so
   the intervention doesn't transplant. The *measure* does.

6. **Operator-theoretic (S6), now with specifics.** KoopmanFlow's explicit split — low-freq
   macro-structure via a Koopman branch (NFE=1) + high-freq texture via flow — is the cleanest
   fit and directly targets macro-vs-local. Spectral Mean Flows (holistic, simulation-free,
   non-autoregressive → "structurally immune to feedback loops") is the higher-variance bet.

## Recommended ranked path (updated by the report)
1. **FK-Flow + whitened-patch potential** — inference-only go/no-go; now a *published recipe*
   for CFM. Cheapest, validates the tilt. (S1, de-risked.)
2. **AID-style amortized guidance head** — the flagship "us" build: LatCH-scale, recurrence
   meter as reward, <1% params, frozen SA3. Modest LUMI. (S2, de-risked → priority build if S1
   confirms the tilt helps.)
3. **CQT-structured prior/guidance** — parallel bet aimed squarely at harmony-abandonment.
4. **Diffusion-Forcing / Self-Forcing / DEFAR finetune** — flagship LUMI retrain if
   inference-only proves too weak. (S3/S4.)
5. **KoopmanFlow / Spectral Mean Flows** — highest-variance research bet. (S6.)

## Gemini's SECOND pass — code bridge (Kim relayed 2026-07-15; I VERIFIED every claim against the source)

Gemini then read SA3's inference code and mapped it onto the theory. **I checked all five files —
its reading is accurate.** The punchline reframes the plan: **we have already built inference-time
analogs of most of the interventions.** We are not starting from scratch.

| Our code (verified) | Theory analog | What it does |
|---|---|---|
| `longform.py::DriftMonitor` (rms_history, centroid_proxy, rms_drop_frac 0.6) | posterior-collapse tripwire | detects the RMS-drop onset of collapse |
| `rope_jitter.py` (per-head `base_h=base*(1+s·eps_h)`) | zero-train state-space regulation (RMR's *goal*) | **attacks the ROOT of the periodicity prior** — SA3's head-SHARED RoPE lets all heads phase-concentrate on the clamped prefix; jitter de-syncs them |
| `incantation_mask.py` (hook zeros `cross_attn_scale` on history frames) | conditioning-driven loop fix | stops a time-varying prompt from rewriting the committed history (temporal cross-contamination) |
| `latch_guided.py::sample_flow_euler_multi_latch_guided` (rho=variance, mu=mean, Selective-TFG) + `chroma_losses.py` (energy potentials) | FK-Flow / AID *practical realization* | inference-time tilted sampling via lightweight LatCH heads |
| `fifo_infinite.py` (guarded monkey-patch → per-token (B,T) timesteps, diagonal denoising) | Rolling Diffusion / Diffusion Forcing *at inference* | fixed window, each frame at a different noise level, constant memory |

**Notable:** `rope_jitter` is arguably *deeper* than RMR here — RMR damps symptoms in the value
cache; rope_jitter removes a *root cause* specific to SA3 (head-shared rotary phase concentration
on the clamped prefix). And our engineering reached these independently of the papers.

### The reframed near-term path (this is the real takeaway)
The machinery exists but is **(a) not driven by the recurrence/novelty potential and (b) not
combined.** The near-term work is mostly WIRING, not new models:

1. **Add a novelty/recurrence energy potential to `latch_guided`** — the whitened-patch recurrence
   meter as one more guide alongside the chroma/energy guides (an "anti-loop guide"). This IS
   FK-Flow's tilted sampling, implementable in the existing multi-guide Euler loop with ~one new
   potential. *Cheapest, highest-leverage, local-prototypable.* (Was S1 → now "add one guide.")
2. **Close the DriftMonitor → intervention loop** — drive `rope_jitter` scale / incantation /
   window-nl from the live drift+recurrence signal = the **breathing controller (task #35)**, now
   with the actuators already built. Turns fixed-strength interventions adaptive.
3. **Eval the *combination*** (fifo diagonal-denoising + rope_jitter + incantation + novelty-guide)
   on the whitened-patch recurrence AND RMR's correlation-dimension meter. We've been testing these
   piecemeal; nobody has run them stacked with a novelty potential.
4. **THEN** the AID upgrade: amortize the novelty-guide into a trained <1% actor-critic head
   (step-2 of latch_guided) once the inference-only version proves the tilt helps.

So the report's grand menu collapses, for us, into: *wire the recurrence potential into
latch_guided, close the breathing loop, eval the stack — then amortize.* Diffusion-Forcing/
Self-Forcing retrains and operator-theoretic rebuilds stay as the bigger-bet second tier.

## Open questions for CONTINUITY (theory lane)
1. **AID on rectified flow?** AID is demoed on EDM/diffusion pipelines. Does the Gaussian-
   relaxation → deterministic-guidance optimizer-preserving proof hold for a *rectified-flow*
   backbone, or does it lean on the stochastic-diffusion SDE structure? (Determines whether S2
   is a straight adapt or needs a derivation.)
2. **FK-Flow's Brownian injection** vs SA3's descending-t Euler + CK-flash-attn fp16 sampler —
   any interaction with our guidance/APG stack? (Practical.)
3. **Correlation dimension** — worth adding to the meter suite next to whitened-patch recurrence,
   or redundant with it?
4. **Operator-theoretic** — KoopmanFlow (low/high-freq split) vs Spectral Mean Flows
   (simulation-free holistic): which is the better LUMI long-shot, and is either compatible with
   a *frozen* SA3 or does it demand a from-scratch trajectory model?
