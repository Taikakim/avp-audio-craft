# What the DiT adds — noise-invariance of the rebuild (W × C composition)

*(WINTERMUTE, 2026-07-08. Composes CONTINUITY's DiT layer×feature map
(`docs/layer-feature-map.md`) with the latent-dim×feature xcorr
(`mir/stats/latent_dim_feature_xcorr.csv`) plus a matched-method noise sweep
(`mir/stats/latent_noise_fragility.csv`, `Misc/latent_noise_fragility.py`).
C invited the "emergent-minus-input R² delta" read; doing it properly needed a
noise-matched input baseline, which is what the sweep provides.)*

## Why a raw subtraction was wrong

My clean-latent probe (σ=0) and C's block-hook map (σ 0.2/0.5/0.8) used different
n and noise levels, so `C_peak − W_clean` mixed two effects. The fix: run *my*
probe at C's exact noising (`x_t = (1−σ)z + σ·eps`, one consistent method) so the
input baseline is measured under the same noise the DiT sees. Two clean deltas:

- **input σ-collapse** (my probe, no DiT): how much the *raw* noised latent still
  linearly carries each feature — this turns out to be **roughly uniform across
  features**: everything collapses toward R²≈0 by σ0.8.
- **dit_gain = peak_block − block0** and **peak-vs-σ** (C's map): how much the DiT
  *rebuilds*, and whether that rebuild survives noise.

## The finding: the asymmetry is in the rebuild, not the input

At the raw input, beat, mid-energy, and melody all collapse under noise the same
way (beat 0.34→−0.04, rms_mid 0.50→−0.04 across σ0→0.8). The DiT then treats them
completely differently:

| feature | clean-latent R² | input @σ0.8 | DiT peak (L) | dit_gain | peak σ.2→.8 | regime |
|---|---|---|---|---|---|---|
| spectral_flux | 0.84 | 0.05 | 0.94 (L22) | +0.03 | 0.94→0.93 | **encoded** (in latent, DiT-flat) |
| spectral_flatness | 0.76 | 0.17 | 0.91 (L0) | +0.00 | 0.93→0.89 | encoded |
| spectral_skewness | 0.62 | 0.14 | 0.81 (L0) | +0.00 | 0.86→0.78 | encoded |
| **beat_activation** | 0.34 | −0.04 | **0.80 (L14)** | **+0.40** | **0.80→0.80** | **emergent, noise-INVARIANT** |
| **downbeat_activation** | 0.17 | −0.02 | **0.44 (L14)** | **+0.33** | **0.45→0.44** | **emergent, noise-INVARIANT** |
| onset_envelope | 0.31 | −0.01 | 0.78 (L20) | +0.21 | 0.80→0.72 | emergent |
| onset_envelope_drums | 0.45 | 0.01 | 0.71 (L15) | +0.19 | 0.72→0.69 | emergent |
| **rms_energy_mid** | 0.50 | −0.04 | 0.16 (L3) | **+0.01** | **0.19→0.08** | **degraded/ABANDONED** |
| rms_energy_body | 0.38 | −0.02 | 0.34 (L2) | +0.04 | 0.34→0.31 | degraded/abandoned |
| **hpcp** (C only) | — | — | 0.46 (L19) | +0.07 | 0.50→0.41 | **degraded/abandoned** |

**Beat/downbeat are rebuilt to a fixed R² that does not move with input noise.**
The DiT reconstructs the rhythmic grid to 0.80 whether the input is at σ0.2 or
σ0.8 — it isn't reading the beat off the (collapsed) latent, it's synthesising it
from the conditioning + the coarse periodic structure that survives i.i.d. noise.
Rhythm is a **noise-invariant emergent** feature.

**Mid-energy and harmony get no such rescue.** `rms_energy_mid` and `hpcp` are
solid in the clean latent, collapse at the noised input like everything else, and
the DiT barely rebuilds them (gain +0.01 / +0.07) — and what little it does rebuild
itself fades with noise (mid 0.19→0.08, hpcp 0.50→0.41). They are **degraded and
abandoned**.

## Why this matters (the mid-band a2a mechanism, corrected)

This is the mechanism behind Kim's ear-finding (melodies go stereotypical/static
at nl .40–.55) and the measured chroma-flux U-shape. It is **not** that mid-band
is uniquely fragile at the input — the input collapse is uniform. It is that under
a2a mid-noising the DiT **keeps the rhythm locked (noise-invariant rebuild) while
it cannot reconstruct the harmony/melody** (abandoned set) — so it fills the
melodic slot with the corpus-mean contour (the posterior-averaging filler from the
U-shape finding). Beat survives, melody goes generic. hpcp being weakly-rebuilt +
noise-fading is the tightest single-feature link to "melodies lost movement."

## Actionable

1. **Chroma-morph LatCH guidance is now mechanistically justified**, not just
   empirical: harmony is in the abandoned set, so mid-band melody must be
   **re-supplied externally**. This is exactly why C's chroma-steered transitions
   beat plain — the head injects the evidence the DiT won't rebuild.
2. **Rhythm heads fed from block-13 (C's play #1) get a green light *and* a noise
   guarantee**: the beat target is R²0.80 invariant across σ, so a hooked head has
   a stable target at *any* a2a noise level — beat guidance won't degrade with nl.
3. **a2a recipe corollary**: you can push nl high for rhythm transfer without
   losing the beat (noise-invariant), but harmony/melody degrade monotonically past
   the mid-band — so pair high-nl with explicit chroma guidance rather than trusting
   the model to keep the melody.
4. `rms_energy_mid` is the most-abandoned feature on both axes (lowest dit_gain,
   steepest peak fade) — consistent with it being the band a2a loses first.
