# Does Physics Live in the Activations? Localizing Physical Quantities in Video Diffusion Models (2610.03154)

Kneifl, Skalski, Twardowski, Deja (IDEAS Research Institute, Warsaw; CVC Barcelona; Warsaw University of Technology). arXiv v1, October 2, 2026; preprint, no venue. Code and data are promised on publication.
PDF: `arxiv-2610.03154 - Does Physics Live in the Activations - Localizing Physical Quantities in Video Diffusion Models.pdf` (gitignored; added locally on the desktop).
**Read:** the full PDF including the appendices, by a subagent for KUANG on November 4, 2026. Tables B.1, B.2 and C.1 are scrambled in the text extraction, so only cells that could be aligned are quoted.

## What it contains

**Models.** The image-to-video variants of Wan 2.1 14B (40 blocks), CogVideoX-1.5 5B (42 blocks) and Open-Sora 2.0 11B (57 blocks).

**Targets.** 200 Genesis-simulated videos per scenario, so the labels are exact:
- rolling speed and direction;
- for an elastic two-ball collision: momentum, approach angle and per-phase speeds;
- for a projectile: gravity and launch angle.

**Capture.**
- Real latents are forward-noised to six levels, σ ≈ {0.99, 0.909, 0.715, 0.5, 0.285, 0.137} (SNR −40 to +16 dB), and run through one frozen forward pass, with an empty prompt and the clean first frame as the condition.
- Only the residual stream is probed, at about 10 sampled blocks. Attention and MLP outputs are not probed separately, and nothing is done per head.

**Probes.**
- Ridge regression with 5-fold cross-validation, split by video.
- Pooled globally, or over a region of interest (ROI): a disk at 1.5x the object's radius, about 1–2 % of the tokens.

**Controls.**
- Ridge on the noised input latent (the baseline) and on the clean latent.
- A permutation null (mean R² −0.056).
- Mirrored "pinned" and "tracked" decoy regions.
- Temporal cross-reads between collision phases.
- Out-of-distribution (OOD) transfer with a 10-video gain/offset recalibration.
- **Not done:** a random-initialization model, a selectivity (control-task) test, activation patching or ablation.

**Results.**
- **Noise.** At −40 dB the input baseline is at chance, yet the activations already resolve rolling. Gravity and launch angle stay +0.40 to +0.69 R² above the input baseline even at the cleanest level. Wan and CogVideoX peak while the input is still heavily noised; Open-Sora rises only near the midpoint.
- **Depth.** Readable from the first blocks through the last, peaking early-to-middle (a heatmap only, no numbers).
- **Locality.** At 0 dB, projectile gravity reads 0.90–0.92 R² from the ROI (Wan, CogVideoX) against 0.13–0.23 globally. The paper calls this "computed globally, stored locally". For gravity from a single frame, the clean latent gives 0.07–0.12 against 0.41–0.81 from the activations.
- **Time.** The own frame reads best. Anticipation keeps 51–80 % of the own-frame score and memory 10–67 %.
- **Transfer.** Median recalibrated R² of ROI probes: 0.876 / 0.905 / 0.295 (in-scene 0.981 / 0.977 / 0.842). Uncalibrated, the median R² is 0.16 but the median Pearson r is 0.896: the direction transfers, the scale does not. Global probes collapse.
- **Steering** (rolling direction only):
  - Each token is pushed by spherical linear interpolation (SLERP) along a full-resolution probe direction, at one block per model, during the first 10 of 40 steps, at guidance 6.
  - Flip rates: 0.45 / 0.35 / 0.31, against 0.30 / 0.017 / 0.04 for a directed text prompt. The reversed push flips nothing.
  - Pooled directions never steer: they keep about 3 % of the per-token signal norm.
- **Takeaway.** Open-Sora matches the others in distribution but transfers and steers worst. The paper concludes that transfer and steering, not in-distribution decodability, separate the models.

## How far the evidence reaches

- **"Constructed, not inherited" is overstated.** Given z_t and the condition, the model is deterministic, so the information is in the input. Beating a *linear pooled* input probe shows the network makes it linearly accessible, not that it creates it.
- **Statistics.** 200 videos per scenario against probes with d ≥ 3 072 features; no random-initialization or selectivity control; no confidence intervals; 52 seeds for steering.
- **Hand-picked settings.** The steering block, strength and step window are chosen per model.
- **Not necessity.** Sufficiency is shown, necessity is not (no ablation).
- **Off trajectory.** Activations come from forward-noised real video, not the model's own sampling path.

## For us

**DIRECTLY USABLE PROTOCOL: it is our July 8, 2026 layer-by-feature map with the controls we skipped, plus a steering test.** See `docs/layer-feature-map.md` and `latch/extract_layer_activations.py`.
- Our map (150 crops, σ 0.2/0.5/0.8, ridge on all 24 block outputs) found spectral features already in the latent, and rhythm computed mid-stack (beat 0.40 → 0.80 at L14).
- Its only pitch feature was HPCP (0.39 → 0.46 at L19). **No melody or contour feature has been mapped.**

**What to add (inference; untested):**
1. **Melodic targets.**
   - Per-frame f0 or MIDI pitch, contour sign (Δpitch: up, flat or down), interval size, register, chroma, key, beat and bar phase, phrase position.
   - Exact labels need rendered MIDI (the render bank) as the simulator analog. Real audio with extractor labels is kept separate, because those labels are noisy.
   - Folds split by song.
2. **Their six-level σ grid**, which maps directly to our rectified-flow σ, so the SNRs compare.
3. **A nonlinear input baseline: a LatCH head on z_t.** Beating linear z_t is close to guaranteed. The question that matters for us is whether blocks beat what our LatCH heads already read.
4. **Controls:**
   - the permutation null;
   - a random-initialization DiT and control tasks for selectivity;
   - a decoy shifted by one bar (the analog of their pinned disk);
   - **contour residualized on chroma**, because pitch class and f0 are confounded.
5. **OOD transfer** (fit on piano, test on synth lead; with and without accompaniment; transposed; more voices), reporting Pearson r with the 10-clip recalibration.
6. **The 64 memory tokens** probed separately, as a candidate global store for key and tempo. Single-frame readout of global quantities is their "stored locally" test.
7. **Steering.** If a contour direction is decodable in a block band, push a per-frame shared direction there (a full-resolution direction will not fit our data) during the early steps. Use paired seeds, a reversed push and an "ascending melody" prompt as references, scored with an f0 extractor.

**Cost (estimated, untested).**
- 1 000 clips × 6 σ × 24 blocks is about 144 GB of fp16 activations, or about 48 GB at 8 blocks. Subsample frames or store PCA.
- The forward passes take minutes on the desktop GPU. Rendering and labeling is the real work, about 1–2 days.

**Decisions it would settle:**
- **A block/σ band where contour beats the LatCH-on-z_t reading:** inject the melody conditioner there, or read a contour head from that block.
- **Chroma readable at high σ but contour only at low σ:** explains why chroma guidance moves pitch class but not contour; move contour guidance later.
- **Contour readable at the conditioner's injection point but gone downstream:** the model ignores the conditioner (the null E-series result), so fix training rather than the signal.
- **Readable nowhere beyond the input:** no internal contour to steer, so put the effort into input-side control.

The planned melody-contour head on taps L8–15 (`docs/superpowers/specs/2026-07-22-melodic-latch-film.md`) should wait for this map. It should read where the map says contour lives, not L8–15 by analogy with rhythm.

## What stays ours

Model, features and guidance are ours. Spatial ROIs become temporal windows. The image-to-video first-frame anchor has no text-to-music analog (except in continuation and inpainting). AdaLN modulation means activations should be standardized per σ.
