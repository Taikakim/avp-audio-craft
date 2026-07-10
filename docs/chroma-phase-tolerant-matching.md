# Phase-tolerant chroma matching — design note for chroma-constrained a2a

*2026-07-10, WINTERMUTE. From Kim's breathing-a2a listening verdict (voice, chat):
frame-by-frame chroma matching "doesn't allow for any phase differences… as long as
the output is in general in the same pitch class of the input and the movement is
around the same shape," the match should count. This note gives the candidate
formulations, their gradient-friendliness, and a recommended ladder. Companion to
the breathing-controller v2 spec (C) and THE-FINN's Gemini survey on
temporal-tolerant melodic similarity.*

## The failure being fixed

Frame-rigid chroma loss `L = Σ_t d(c_out(t), c_src(t))` punishes an output that
plays the *same melody* displaced by half a beat, or answers a fundamental with a
fifth a frame later. Result: the optimizer prefers smeared, phase-locked pitch mush
over a *rephrased* correct melody — exactly the "loses the melodies, loses the
bassline" mid-band collapse Kim hears. A control that only accepts phase-identity
also constricts timbre/creativity (his standing worry about hard controls).

## Candidate formulations

Let `c(t) ∈ R^d` be per-frame chroma (12-d pitch-class or the 384-d chroma-model
embedding), sequences `C_out`, `C_src`, window length `W` (≈1–2 beats).

1. **Windowed target smoothing (the cheap one).** Convolve BOTH chroma sequences
   with a Hann kernel of width `W`, then frame-wise distance:
   `L = Σ_t d(K*C_out(t), K*C_src(t))`.
   Any rearrangement *within* the window is free; ordering within the window is
   forgotten. Fully differentiable, O(T), drop-in for LatCH-style guidance (it's a
   1-line change to the target + prediction pipeline). Risk: too loose — a held
   chord matches an arpeggio of the same pitch classes.

2. **Soft nearest-frame matching.** `L = Σ_t softmin_{|τ|≤W} d(c_out(t), c_src(t+τ))`.
   Differentiable, order-free like (1) but sharper (matches actual frames, not the
   local mean). One-sided → degenerate solutions (every output frame matching one
   source frame); needs the symmetric term
   `+ Σ_t softmin_τ d(c_src(t), c_out(t+τ))` (a windowed soft-Chamfer distance) so
   the output must also COVER the source content.

3. **Soft-DTW on windows.** Differentiable dynamic time warping (Cuturi & Blondel)
   on ~4 s chroma windows. Allows monotonic local time-warp — preserves note ORDER
   (what (1)/(2) lose) while forgiving phase. O(T·W) per window, heavier but fine
   at 10–50 Hz chroma rates. The principled middle: same melody, breathable timing.

4. **Contour/movement matching (Kim's "2-D note vectors").** Match the *derivative*
   sequence: `Δc(t) = c(t+1) − c(t)` (chroma flux vectors), or a windowed histogram
   of (Δt, Δpitch) note transitions. Captures "movement of the same shape"
   independent of absolute position; combine with a coarse pitch-class-content term
   so the contour isn't transposed arbitrarily (unless transposition-invariance is
   wanted — make it a switch).

5. **Lag-max cross-correlation.** Per window, `max_τ NCC(C_out, C_src shifted τ)`.
   Phase-invariant and shape-sensitive; `max` → use logsumexp for gradients.
   Essentially (2) applied to whole windows instead of frames — rigid within the
   window, free across it.

## Recommendation (the ladder)

- **Guidance loss, step 1:** (1) Hann-smoothed chroma matching at beat scale.
  Cheapest, differentiable, already phase-free; ship it in the first chroma-
  constrained a2a test and let Kim's ear judge whether within-window order matters.
- **Guidance loss, step 2 (if (1) sounds order-mushy):** (3) soft-DTW on 4 s
  windows, or (1)+(4) — smoothed content + contour shape. (4) directly encodes
  Kim's intuition and is cheap; try before full soft-DTW.
- **Evaluation meters (not in the gradient):** soft-DTW distance + MERT-pitch
  similarity between output and source (Kim's ask: verify output pitch actually
  tracks source), reported per window alongside the novelty curve. Meter-in-the-
  gradient scope rule applies (MASTER §4): chroma timing/content is exactly the
  kind of signal RF loss can't see, so a chroma meter in the gradient is justified;
  MERT stays evaluation-only.
- **Looseness knob:** window width `W` IS the phase-tolerance dial (W→0 = rigid
  frame matching, W→∞ = bag-of-pitch-classes). Expose it; Kim will want to hear
  ~1 beat vs ~2 beats.

## Open questions for the Gemini survey (THE-FINN)

1. State of the art in **melodic similarity tolerant to temporal displacement**
   (soft-DTW variants, EMD/optimal-transport over piano-roll or chroma, Mongeau-
   Sankoff descendants) — anything designed as a *differentiable training loss*,
   not just retrieval?
2. **Chroma/pitch-content guidance in diffusion/flow audio models** — prior art on
   phase/onset-tolerant formulations (vs MuseControlLite-style frame conditioning)?
3. Contour representations ((Δt, Δpitch) vector sequences, Parsons code, interval
   histograms) used as *losses* — transposition-invariant variants?
