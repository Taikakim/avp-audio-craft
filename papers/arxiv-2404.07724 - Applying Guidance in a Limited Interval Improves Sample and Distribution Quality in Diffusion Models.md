# Applying Guidance in a Limited Interval Improves Sample and Distribution Quality in Diffusion Models (2404.07724)

*The source paper for our interval-CFG A/B (exp #26): guidance helps only in a middle noise band — but their band is in EDM sigma, ours must be re-derived in RF timestep t. (Kynkäänniemi, Aittala, Karras et al., NVIDIA; NeurIPS 2024. Subagent deep-read, THE-FINN 2026-08-12.)*

## What it contains

**Core claim.** Classifier-free guidance (CFG) is conventionally applied with a constant weight at *every* sampling step. The paper argues this is sub-optimal because guidance behaves very differently across noise levels: it is *harmful* at high noise (early in the chain — it drags trajectories outside the data distribution and causes mode drop), *largely unnecessary* at low noise (late — fine detail is already determined), and *only beneficial in the middle*. Their fix is to apply guidance only inside a limited noise-level interval and disable it elsewhere, leaving the weight otherwise unchanged.

**Method (Sec 3.1).** They replace the constant guidance weight `w` in the EDM guided-ODE (`dx/dσ = −(w·Dθ(x|c;σ) + (1−w)·Dθ(x;σ) − x)/σ`) with a piecewise-constant schedule:

- `w(σ) = w` if `σ ∈ (σ_lo, σ_hi]`, else `w(σ) = 1` (guidance off, i.e. conditional-only).

Traditional CFG is the special case `σ_lo = 0`, `σ_hi = ∞`. One important practical detail: because a Runge–Kutta/Heun sampler assumes `dx/dσ` is smooth within each step, they snap `σ_lo` and `σ_hi` to actual step boundaries (round to some `σ_i`, `σ_j`) so the weight is constant within every step — which is why the reported bounds carry many seemingly-precise digits that should *not* be read as fine tuning.

**Key quantitative results (all cite-accurate from Table 1 / Sec 4.1, ImageNet-512, 32-step Heun, metrics FID↓ and FD_DINOv2↓):**

| Model | CFG (full) FID / FD_DINOv2 | Interval FID / FD_DINOv2 |
|---|---|---|
| EDM2-S | 2.23 / 52.32 | **1.68** / 46.25 |
| EDM2-XXL | 1.81 / 33.09 | **1.40** / 29.16 |
| DiT-XL/2 (250-step iDDPM) | 3.04 / 51.97 | **2.40** / 43.94 |

- EDM2-XXL: best FID from guidance at **6 of 32 steps**, `w=2.0`, `σ ∈ (0.19, 1.61]`. Best FD_DINOv2 at slightly higher band `σ ∈ (0.60, 5.00]`, `w=2.9`.
- EDM2-S: FID band `σ ∈ (0.28, 2.90]`, `w=2.1`.
- DiT-XL/2: best FID with `w=2.5` in **75 of 250 steps**, `σ ∈ (0.34, 1.02]`.
- SD-XL (32-step Heun, qualitative only, no FID): guidance at ~50% of steps, `σ ∈ (0.28, 5.42]`, `w=16` — a *much* wider/higher band than ImageNet, attributed to the more varied dataset. Note the sampler's `σ_max = 14.61` in their schedule.
- Robustness: the optimal interval is insensitive to step count — with EDM2-S the same interval holds at 16 steps (FID 2.49→1.84) and 64 steps (2.27→1.70).
- Precision/recall (Fig 4): the interval mainly improves **Recall** (diversity) at roughly constant Precision — consistent with the qualitative finding that outputs stay crisp *and* varied.

**Practical tuning recipe (Sec 4.2).** No 2-D search needed. Fix `σ_lo=0`, sweep `σ_hi` to find the optimal upper limit (`σ_hi` sits at middle noise levels; too high truncates the distribution, too low under-guides). Then find `σ_lo` (weak, predictable effect — guidance at low noise adds nothing, so it can be disabled to save compute). Bisection + reducing the FID sample from 50k to 5k gives ~10× faster search. Smooth (non-binary) weighting functions and per-step importance estimates did *not* beat the simple binary inclusion.

## FOR US

This is the direct source of our interval-CFG A/B. The transferable core is model-agnostic and holds up: **guidance is a middle-noise-band tool, not an all-timesteps tool**, and restricting it improves distribution quality (recall/diversity) while keeping the crispness that motivates high `w`. Their tuning recipe ports cleanly to SA3:

- **1-D search, not 2-D.** Fix the low bound at the noise floor, tune the high bound first, then the low bound. This is exactly the cheap-decisive-test posture we favour.
- **Snap bounds to step boundaries.** With our RF sampler, we should round the interval endpoints to actual solver steps so the effective weight is constant within each step — same rationale as their `σ_i`/`σ_j` rounding. Worth checking our A/B harness does this rather than interpolating mid-step.
- **Expose the interval as a hyperparameter**, per their closing recommendation. For SA3 that means `(t_lo, t_hi, w)`.
- **Expect the win to show up as diversity/recall**, i.e. in FAD-type distribution metrics, more than in per-sample sharpness. This is why our FAD run (not yet done) is the load-bearing measurement, not eyeballing single clips.

**The porting caveat we must not skip — sigma vs t.** Their interval is parameterized in **EDM sigma**, a noise *standard deviation* on an unbounded schedule (`σ_max ≈ 14.61`, `σ=0` at the end, log-spaced). Our SA3 is a **rectified-flow** model where the interval is in **timestep t ∈ [0,1]** and `sigma = t ≠ EDM-sigma`. The two are not interchangeable:

- EDM `σ` is unbounded and the useful band sits at *small-to-middle* σ (e.g. `(0.19, 1.61]` out of a `14.61` max — roughly the lowest ~10% of the σ range, applied at 6 of 32 steps near the *end*). Do **not** copy `0.19`/`1.61`/`0.28`/`5.42` as t-values — they are meaningless in our units.
- To port, map their band through the noise-schedule relationship: convert their optimal σ-interval to the corresponding *fraction of the sampling trajectory* (which steps they guide, and where those sit on the coarse-to-fine axis), then express that fraction in our RF t-schedule. Their "6 of 32 steps" / "75 of 250 steps" / "~50% of steps" framing is the schedule-independent quantity worth anchoring to; the raw σ numbers are not.
- Their own SD-XL result already shows the band is *dataset- and model-dependent* (much wider/higher for SD-XL than ImageNet), so even after unit conversion we should re-derive our bounds empirically rather than assume theirs transfer.

Directly usable without caveat: the 1-D search procedure, the reduced-sample-for-speed trick, the binary-inclusion-beats-smooth-weighting finding, and the expectation that the metric that moves is a distribution metric.

## What stays ours

- **Our SA3 interval bounds in t.** Whatever `(t_lo, t_hi)` we land on is re-derived for our RF parameterization and 256-d 10.76 Hz semantically-aligned latent — not inherited from their EDM-σ numbers.
- **Our audio results.** This paper is images (ImageNet-512, SD-XL); FID/FD_DINOv2 are image metrics. Our win/loss is measured in FAD (pending) and audio quality on controllable music generation — a different modality with no counterpart here.
- **Our mid-band-lift finding** from our own interval-CFG A/B (currently partial, FAD not yet run) is ours. The paper predicts a middle-band optimum in general terms but says nothing about where the productive band sits for a 1.4B RF audio DiT, nor about a specific mid-band lift in our units. That empirical characterization — and confirming it with FAD — is the part of exp #26 that is genuinely our own contribution, not a re-derivation.

**Honest non-transfer flags:** their headline numbers are image-only; SD-XL got no quantitative eval (visual inspection only), so the closest large-scale generative-model analogue to us is itself unquantified in the paper; and the entire σ-band geometry assumes EDM's variance-exploding schedule, which our rectified flow does not share.
