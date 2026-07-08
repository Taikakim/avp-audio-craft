# DiT layer × feature map — where musical features live inside SA3 medium

*(CONTINUITY, 2026-07-08. Data: 150 latents_sa3 crops × sigmas {0.2, 0.5, 0.8}, all 24
DiT blocks hooked, 96 frames/crop, ridge R² per (layer, feature) against the crop's
TIMESERIES companions. Extraction: `latch/extract_layer_activations.py`; analysis:
`latch/run_layer_feature_map.py`; results JSON:
`Mantu1/sa3_lora_runs/layer_activations_base/layer_feature_map.json`.)*

## The two regimes

**1. Spectral features are already in the latent (input-space features).**
`spectral_flux` (R²=0.94), `spectral_flatness` (0.93), `spectral_skewness` (0.86) are
near their ceiling **at layer 0** and stay flat through the stack. The DiT doesn't
compute these — SAME already encodes them linearly. Matches W's latent-dim×feature
xcorr, where exactly these features had the strong input-space correlations.

**2. Rhythm features are COMPUTED by the mid-stack (emergent features).**
`beat_activation`: R² 0.46 at L0 → **0.80 at L11–14**. `downbeat_activation`: 0.16 at
L0 → **0.45 at L13–15** (a ~3× emergence — almost absent in the latent, built by the
network). `onset_envelope`: 0.64 → **0.80 at L15–21**. `hpcp`: 0.44 → 0.50 at L12–19.
All decay again toward L23 (the head re-specializes for denoising output).

The pattern is stable across sigma 0.2/0.5/0.8 (emergence shifts ~1–2 layers deeper at
high noise).

## What this explains (retro-diction)

- **W's thin tier / the dead guidance heads.** beat/downbeat/onset LatCH heads trained
  on the *latent* were guidance-dead at every gain (2026-06-28 sweep) while energy
  heads steered. Now mechanistic: rhythm activations are only weakly linear in the
  latent (input R² 0.11–0.33) — the information the head needs doesn't exist at the
  layer it reads. It exists at L11–15.
- **TADA localization.** TADA fingered blocks ~{12,13} as the high-leverage adaptation
  site; our beat/downbeat/hpcp peaks sit exactly there. Independent method, same site.
- **rms_energy_mid is the least-represented feature in the whole map** (peak R² 0.19,
  ~0 at σ0.8). Consistent with the mid-band U-shape / under-constraint attractor: the
  band the model represents most weakly is the band a2a loses first.

## What to do with it (forward)

1. **Rhythm heads should read L11–15 activations, not the latent.** A LatCH-style head
   on block-13 output should make beat/downbeat *guidable* — the info is there (R² 0.80
   vs 0.33). Needs a hook-fed head-training run (extraction infra already does the
   forward).
2. **Layer-restricted control adapters**: concentrate FiLM/cross-attn adapter capacity
   on L11–15 for rhythm control instead of all 24 blocks (TADA-consistent, cheaper).
3. **Mid-band recovery** (task #26) has a measurement hook: if interval-CFG/chroma
   guidance recovers mid-band, does block-side mid representation improve too?

| feature (σ0.5) | L0 | peak (layer) | L23 |
|---|---|---|---|
| spectral_flux | 0.91 | 0.94 (L22) | 0.88 |
| spectral_flatness | 0.91 | 0.91 (L0) | 0.81 |
| spectral_skewness | 0.81 | 0.81 (L0) | 0.56 |
| onset_envelope | 0.57 | 0.78 (L20) | 0.44 |
| onset_envelope_drums | 0.52 | 0.71 (L15) | 0.49 |
| beat_activation | 0.40 | **0.80 (L14)** | 0.49 |
| downbeat_activation | 0.11 | **0.44 (L14)** | 0.16 |
| hpcp | 0.39 | 0.46 (L19) | 0.26 |
| onset_envelope_bass | 0.20 | 0.42 (L15) | 0.16 |
| rms_energy_body | 0.29 | 0.34 (L2) | 0.18 |
| rms_energy_air | 0.27 | 0.31 (L22) | 0.19 |
| rms_energy_bass | 0.13 | 0.27 (L22) | 0.17 |
| rms_energy_mid | 0.15 | 0.16 (L3) | 0.01 |

## Follow-up: noise-invariance sweep (W, 2026-07-08)

`docs/layer-feature-noise-invariance.md` composes this map with a matched-noise input
sweep and sharpens the mechanism: the noised LATENT collapses uniformly (all features
→ R²≈0 by σ0.8), but the DiT **rebuilds beat noise-invariantly** (R² 0.80 at L14 at
every sigma — synthesized from conditioning + coarse periodicity) while **abandoning**
hpcp and rms_mid (barely rebuilt, fading with noise). The a2a recipe implication:
rhythm transfers at any noising level for free; harmony must be re-supplied externally
(chroma guidance) past mid-band.
