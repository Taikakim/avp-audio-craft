# Perceptual signal > descent geometry — optimizer directions for RF control heads

**Status:** Conceptual plan (2026-07-02), approved direction; #1 in implementation.
**Context:** FusionOpt v1.1 cautious-masking A/B (FiLM onset-density + DoRA r128) and the
landscape-exploration discussion. Companion evidence: the published eval sets under
`https://aavepyora.online/files/sa3-cautious-eval/` and WORKLOG 2026-07-01/02.

## The diagnosis that orders everything

Every measured failure points at the same root: **the RF loss cannot hear what we care
about.** Evidence:

- RF loss flat while control authority peaks then drifts (MASTER §4, spectral_skewness,
  onset_density; EMA/early-stop = 3.1× fix — a *downstream filter* on wandering).
- The **6–9 onsets/s saturation band**: every FiLM head (cautious AND baseline, every
  checkpoint) floors at ~5.6 measured when asked for 3 — the loss never rewarded reaching
  sparse/dense extremes, so the capability never formed.
- The **onset-injection metric cheat**: g1/d3 "ambient drone + low-vol rapid hats" measures
  12.9 onsets/s — high "authority" that is perceptually smear, invisible to RF loss and to
  the correlation metric alike.
- Cautious masking (C-Muon) A/B verdict: a *quality trade* (drier, cleaner separation,
  muted highs, earlier spectral smear when pushed; over-trains — ep5 sweet spot, ep10
  over-injects at low densities). Not a win. Geometry improvements on a blind signal have
  hit diminishing returns — FusionOpt's descent geometry (spectral LMO + SF averaging) was
  already good.

**Conclusion: put meaning into the training signal itself, not more intelligence into the
descent.**

## Mental models → real methods (the translation table)

| Kim's mental model | Real counterpart | Verdict for us |
|---|---|---|
| Ray-trace curved non-Euclidean reflections over the peaks | Natural gradient / Riemannian descent; Fisher metric; geodesics ≠ straight lines | Already have the budget version (KL-Shampoo, Kronecker-factored). Pays off only under adversarial losses (diversity training). |
| Diffuse acoustic reflections to hear a lower spot behind a wall | Gaussian-smoothed loss / graduated optimization: L*N(0,σ) is a **low-pass filter on the landscape**; sampled perturbations (ES) = diffuse echoes; smoothing diffracts around thin ridges | Sound theory; but our failure mode is flat-and-blind, not trapped-behind-walls. Low priority. |
| Throw rocks, listen when they hit bottom, measure distance | Radial loss probes: eval L(θ+t·d) at several t, forward-only; basin radius → trust region | Cheap on 5M heads. Candidate FusionOpt component "`sonar`" (probe along update dir, set γ from measured radius instead of Polyak heuristic). #3. |
| A model of the model's landscape | Trust-region quadratic surrogates (local); GP/BayesOpt (dies >~100 dims); **subspace surrogates** in span of last-k updates (loss-landscape-visualization literature) | Practical in the trajectory subspace; extends `checkpoint_trajectory_stats` with sampled loss grids → actual pictures of the basin. #4. |
| Chasm edge: the floor continues; if no water, there's a lower opening | **Mode connectivity** (Garipov/Draxler): minima connect via low-loss paths at ~constant "water level". Our same-task AdamW+Fusion soups blending cleanly IS this. | Already exploited (soups, SF averaging). The intuition is correct and confirmed in-house. |
| Does the landscape exist before we map it? | Yes — L(θ) fully determined by (arch, data, loss), evaluated or not. BUT: (a) minibatch + RF's sampled (t, ε) → you only ever see noisy sections; the true landscape is their expectation; (b) at 5M dims **walls in 1D/2D slices are slice artifacts** — almost always a way around in the other dimensions (saddles, not minima); (c) that's why chasm intuitions from 3D partly invert. | Framing, not a method. Implication: don't fight walls, change the signal. |

## Ranked directions (expected value for THIS project)

1. **Control-consistency loss term** (IN PROGRESS — the rest of this note).
2. **ES / echo-location for the FiLM conditioner only** (~1M params — small enough for
   evolution strategies). ES needs no gradient → fitness can be the *actual measured*
   onset density (librosa) or even Audiobox PC on a fast proxy render. Hybrid: backprop
   for adapters, ES for the conditioner. Trains directly on what the ear checks.
3. **`sonar` FusionOpt component** — radial probes along the update direction; step size
   from measured basin radius.
4. **Subspace landscape mapping** — loss grids in the last-k-updates plane per run;
   would have shown the drift visually.
5. Gaussian-smoothed/ES gradients on full heads — wrong failure mode for us; parked.

## #1: Control-consistency loss (design sketch)

Add to `sa3_control/train.py` (flag-gated, default off):

```
L = L_RF + λ_cc · L_cc,   applied when t < t_cc_max (ẑ₀ estimates are garbage at high noise)
ẑ₀ = differentiable clean-latent estimate from the model's velocity prediction
     (exact formula per train.py's RF convention — verify in code, don't assume)
L_cc = || probe(ẑ₀) − requested_density ||   (on the normalized scalar scale)
```

**The meter:** a small frozen **latent→onset-envelope probe** (LatCH-style, t=0), trained
offline as supervised regression on `latents_sa3` clean latents vs the `.TIMESERIES.npz`
onset field — the SAME field the training scalar is derived from (verify in dataset.py;
apples-to-apples or the term is miscalibrated). No SAME decoder in the loop (that's the
fallback variant: decode a short ẑ₀ window → differentiable Mel-flux; heavier, keep as
plan B / cross-check).

**Why this attacks all three symptoms:**
- Drift: control-null directions are no longer loss-null — wandering that erodes control
  now costs loss.
- 6–9 band: requests of 3 and 15 now carry gradient toward actually reaching them.
- Smear-cheat: partially — the probe measures envelope density like librosa does, so it
  can be cheated the same way in principle; mitigation is auditioning + (later) a
  spectral-flatness guard term. Do NOT oversell this.

**Risks / cautions:**
- Probe quality ceiling: if the probe is weak, we optimize toward its errors
  (reward hacking a bad meter). Validate probe R² on held-out crops before use.
- ẑ₀ at moderate noise is biased; gate by t and/or weight by SNR.
- λ_cc too high → the head games the probe instead of doing RF; start small (0.1×),
  watch both loss components in telemetry.
- Keep the A/B discipline: same recipe ± the term, canonical 3-prompt eval, audition-first.

## Standing verdicts recorded (so we don't re-litigate)

- **Cautious (C-Muon):** keep as palette option with early-stop ~ep5; not default. The
  keep_frac telemetry stays (drift meter).
- **Metrics:** Audiobox genre-tilted (PC most neutral); onset-authority corr is gameable
  by onset injection. Numbers are instruments; audition is the verdict.
- **Narrow control band is a signal problem, not an optimizer problem** — #1 is the
  attack on it.

---

## Appendix (2026-07-02): research pass + what got adopted

Two web-research sweeps (late-2025→mid-2026 literature) before implementing #2-#4.
Full agent reports in the session; key adoptions:

**#2 ES (`sa3_control/es_conditioner.py` + `control_eval_server.py` job field
`raw_control_tokens_npy`):**
- Consensus recipe confirmed: antithetic pairs + tiny population + shaped fitness
  (ES-at-Scale, arXiv:2509.24372 — N=30 sufficed at 1B params; The Blessing of
  Dimensionality, arXiv:2602.00170 explains why).
- Adopted: per-antithetic-pair **sign shaping** default (EGGROLL, arXiv:2511.16652 —
  most robust to render-noise); **Anchored Weight Decay toward the trained init**
  (arXiv:2605.30148 — THE fix for ES random-walk drift; was a bug in v0 which decayed
  toward zero); per-tensor RMS perturbation scaling; normalized-step update; CRN seeds
  with rotation every N generations (anti seed-overfit); mandatory **--noise-floor**
  measurement before any run (sigma is right when population spread >= 3x floor).
- ES's Gaussian smoothing is itself a reward-hacking mitigation (hacked points rarely
  have good neighborhoods); still keep held-out metrics + audition (GARDO protocol,
  arXiv:2512.24138). DRAGON (arXiv:2504.15217) is the nearest published system (music
  diffusion vs non-differentiable rewards); evolving ADAPTER/conditioner weights via ES
  appears novel. Future: Guided ES (arXiv:1806.10230) using the cc-probe gradient as
  the search subspace.

**#3 sonar (`stable_audio_tools/training/sonar.py` + FusionOpt.gamma_scale):**
- Adopted: probe along the APPLIED post-orthogonalization update at the fast iterate
  (SF-NorMuon paper's WD-on-y finding extends: never probe the averaged x); same batch
  + same RNG across ladder rungs; fp32 loss accumulation; 3-rung ladder (critical
  sharpness, arXiv:2601.16979: <10 forwards); per-event clamp [0.5,2] + log-space EMA
  (SALSA, arXiv:2407.20650: c=0.3, cadence<=10 -> ~3% overhead; we default every=25);
  parabola fit capped to the probed range (EoS bumps break extrapolation).
- Closest published relatives: Distance-Aware Muon (arXiv:2605.18999), Adaptive Polyak
  for Schedule-Free (arXiv:2511.07767) — read before extending.

**#4 mapper (`sa3_control/landscape_map.py`):**
- Adopted: trajectory-PCA with RAW directions (filter-norm is for random planes only);
  **random-walk null is mandatory** (arXiv:1806.08805 — a pure random walk also looks
  low-dim in PCA); grid spec 25x25 @ 1.2x trajectory extent; loss-grid protocol = ONE
  fixed batch + fixed stratified t + fixed noise per grid point (diffusion sampling
  variance otherwise swamps structure), fp32, log-render.
- Mapping the CC-loss field on the RF-loss plane appears unpublished for
  diffusion-control finetuning ("publishable territory" per the sweep). Flat-LoRA
  caveat (arXiv:2409.14396): adapter-plane flatness != full-space flatness.
