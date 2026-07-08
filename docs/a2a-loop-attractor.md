# The a2a loop attractor — and the breathing-noise controller design

*(CONTINUITY + Kim, 2026-07-08. Status: observation CONFIRMED by ear (Kim, full-track
ladders); mechanism THEORized (consistent with measured findings); controller DESIGNED,
not yet built — task #35. Related: `docs/layer-feature-map.md`,
`docs/layer-feature-noise-invariance.md` (W), `papers/knowledge.md` StoryScope entry.)*

## Observation (Kim, listening to the full-track a2a ladders)

On the Kaikki-Alla / Vapausvoima full-track a2a ladders (evr1x r128, nl 0.2→0.7):
at higher noising (~0.55+), **the material that passes through from the original is
fine — but everything the model *generates* falls into repetition**: a short, simple
phrase loops "more or less for minutes on end. It does not really react to what's
underneath."

## Mechanism (theory, composed from measured pieces)

At high nl, source evidence for melody/harmony is destroyed and NOT rebuilt (W's
noise-invariance sweep: hpcp/rms_mid are "degraded-and-abandoned"; beat is rebuilt
noise-invariantly). In regions where the source no longer constrains the sampler, the
model's only temporal context is **its own emerging output**. The DiT's strong
periodicity/repetition prior (goa is highly self-similar; beat R² 0.80 mid-stack)
locks onto whatever phrase first forms → a **self-feeding loop attractor**. Nothing
external ever forces variation, so the loop persists indefinitely.

- Temporal cousin of the corpus-mean melody filler (the U-shape finding): posterior
  averaging fills the melodic slot generically; the repetition prior then freezes it.
- Same family as StoryScope's finding in fiction: generative models cluster into a
  low-rarity region of *structural decision space*; here the structural decision is
  "repeat the phrase."
- Consistent with rhythm surviving: the loop is beat-locked and sounds "coherent,"
  just static — which is why signal-level meters miss it entirely.

## Fix menu (cheapest first)

1. **Breathing noise schedule (Kim's closed-loop design — see below).**
2. **Source-chroma guidance along the whole timeline** — re-supply "what's
   underneath" exactly where generation goes blind (validated chroma LatCH head,
   applied straight rather than morphing).
3. **SaFa reference-swap (task #27)** — inject source-window latents into later
   windows' high-noise steps; this failure mode is what SaFa was built for.
4. **Recurrence-penalized selection steering** — best-of-K renoise picking the
   candidate that adds novelty (hook exists; feature validated by rarity-lite #33).

## The breathing controller (Kim's design, 2026-07-08)

Closed-loop nl control driven by a repetition meter, calibrated by the source itself:

- **Meter (latent-domain, no decode needed) — v3 per W's validation (2026-07-08):**
  patch-level (≈4 s) self-similarity with **per-channel whitening** (z-score each of
  the 256 SAME channels over the rolling window BEFORE cosine, so constant-energy
  content — the steady kick — goes flat and only VARYING content drives similarity).
  Kim's correction was decisive: naive frame-cosine saturates (0.99 on everything),
  chroma is tonality-biased, rhythm is constant — the loop is the whole SPECTRAL
  IMAGE repeating; whitened log-mel validated it on the real ladders (~8x the chroma
  separation; the nl-.70 overshoot regime shows as novelty ABOVE source, so the
  controller correctly disengages there). Drive the hysteresis by the NOVELTY-FLOOR
  signal (1 − max patch-sim to preceding 8–40 s), not raw recurrence. Trigger band
  nl .55–.60 confirmed by two independent meters. Compute the source curve once up
  front. Validated meter: W's scratchpad/recurrence_meter3.py → landing as the #33
  recurrence feature (W owns).
- **Threshold from the source:** `R_src_max` (or p95) — the repetitiveness the
  original never exceeded. Per-track self-calibration, no global constant.
- **Control law (Schmitt trigger / hysteresis):**
  - while `R_out ≤ R_src_max` → run at requested nl;
  - when `R_out > R_src_max` → step nl DOWN (source evidence re-anchors, breaks the
    loop);
  - step nl back UP only when the novelty signal (newest block vs preceding ~30 s
    feature distance) recovers above the source's novelty floor — "only increase
    after new material emerges" = the hysteresis that prevents oscillation.
- **Tier 1 (build first): window-level.** The windowed longform a2a path sets each
  window's nl from the previous window's measured recurrence excess. ~50 lines around
  existing code. Eval artifact: plot the nl trajectory against both recurrence curves
  — the controller visibly "breathes."
- **Tier 2: step-level.** The ping-pong sampler's `renoise_hook` (the selection-
  steering intervention point) sees the evolving z0_hat each step → measure recurrence
  mid-sampling, blend source latent back PER-FRAME only in the looping time regions,
  strength proportional to excess (the sine-mask per-frame machinery, driven by
  feedback instead of a fixed waveform).
- **Known limitation:** a loop is only detectable after ~2 repetitions → controller
  latency ≈ one phrase. It cannot prevent a loop from forming, only from persisting
  for minutes (which is the actual complaint).

## Ear-verdict provenance

Kim's verdicts live in the ladder dirs' `run_meta.json` findings
(`a2a_kaikkialla_evr1x`, `a2a_vapausvoima_evr1x`, + the angelic set) on the eval
drive. Threshold/controller validation ties into rarity-lite (#33), which tests the
recurrence feature against real-corpus statistics.
