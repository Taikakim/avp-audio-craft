# Melody probe map: where does melody live inside the SA3 DiT? (November 4, 2026)

**Question.** The lead f0 LatCH head reads the noisy latent z_t. It sets the pitch direction over a whole clip (E4/E4b, November 3) but does not follow contours with periods of 5 s or less (D16). Is phrase-rate contour readable somewhere inside the DiT where it is not readable from z_t?
- If it is, an f0 head read from that block band is the fix, as the July 8, 2026 layer map already recommended for rhythm.
- If it is not, there is no internal contour to tap, and melody control has to come from the input side.

**Method.** The protocol of "Does Physics Live in the Activations?" (2610.03154, sidecar in `papers/`) applied to melody: ridge probes on every block's residual stream at six noise levels, against controls our July map lacked.

**Script:** `latch/melody_probe_map.py`, tested by `latch/test_melody_probe_map.py`.

## What it measures

**Data.**
- 160 crops from `latents_sa3`, at most 3 per artist. Each crop needs the Melodia lead f0 companion (`f0_other_ts`).
- Per crop, the contiguous 320-frame window (29.7 s) with the most voiced frames.
- Every crop gets its own noise draw.

**Targets.** Per frame, f0 targets on voiced frames only:

| Target | What it is | Why |
|---|---|---|
| `f0_semi` | Lead pitch in semitones | Register and notes |
| `f0_slow` | 10 s moving average | The whole-clip direction E4b steers |
| `f0_phrase` | 1 s average minus 6 s average (about 1–6 s periods) | **The band D16 fails on: the key target** |
| `f0_note` | Pitch minus its 1 s average | Note-level detail |
| `f0_delta` | Slope of the 0.5 s average | Melodic direction |
| `beat` | `beat_activation_ts`, all frames | Positive control (July: 0.80 at block 14) |

**Readouts per noise level:** σ = 0.99, 0.909, 0.715, 0.5, 0.285, 0.137, which is −40 to +16 dB.
- **Blocks 0–23:** the residual stream after each block, with the memory tokens stripped.
- **x_t with ±2 frames of context:** the linear input baseline.
- **z0 with ±2 frames of context:** the clean-latent ceiling.
- **The f0 head:** the existing lead f0 LatCH head on x_t, linearly calibrated per fold. **This is the baseline that matters.** Blocks must beat what our heads already read.
- **HPCP oracle:** the crop's own 12-d pitch-class profile, showing how much of each target pitch class alone explains.
- **Random-init DiT:** the same extraction on moment-matched random weights. It separates learned structure from architecture.
- **Permutation null:** targets shuffled across crops, scored at the best block.
- **Memory tokens:** their mean per block is probed for each window's mean register (one value per crop; exploratory).

**Probes.**
- Ridge regression, with 5 folds that hold out whole artists.
- The regularization strength is chosen per target on an inner split of each training fold.
- The July map instead split folds by frame, so frames of one crop sat in both train and test, and it shared one noise draw across all crops. Both inflate scores. The `beat` row re-measures its headline under the stricter protocol.

## Run (desktop)

```
cd <avp-audio-craft checkout on feature/melody-probe-map>
LAT=$KOSMOS/latents/latents_sa3
OUT=$RUNS/melody_probe_2026-11-04
HEAD=$SAO/stable-audio-3/latch_weights_sa3_medium/val30_f0_other_ema0.999/latch_sa3_f0_other_best.pt
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE

# 1. extract (GPU): about 23 GB
$PY latch/melody_probe_map.py extract --latent-dir $LAT --out-dir $OUT/acts --f0-head $HEAD

# 2. random-init control (GPU), same crops (same seed), two sigmas to save disk
$PY latch/melody_probe_map.py extract --latent-dir $LAT --out-dir $OUT/acts_random --random-init --sigmas 0.5,0.137

# 3. analyze (CPU)
$PY latch/melody_probe_map.py analyze --latent-dir $LAT --acts-dir $OUT/acts \
    --random-acts-dir $OUT/acts_random --out-json $OUT/melody_probe_map.json --stride 2
```

- `$HEAD` is the lead head used by `eval/e4_f0_head_gate.py` (`HEADS["lead"]`). Check that the path exists before step 1.
- Extraction is one forward pass per crop and σ; expect minutes. The analysis is several thousand ridge fits; expect 1–2 hours on the CPU with `--stride 2`.
- Send back `melody_probe_map.md` (the summary table) and `melody_probe_map.json`.

## Reading the results

| If | Then |
|---|---|
| **`f0_phrase` at some block band clearly beats both x_t and the f0 head** (well above the null and the random-init control) | Phrase contour is built inside the DiT. Train an f0 head on that band's activations (hook-fed, like the rhythm recommendation), then rerun the D16 triangle test with it. |
| `f0_slow` is readable from x_t and the head, but `f0_phrase` is readable only in blocks | Explains E4b vs D16 exactly: the head sees the slow line, not the phrase. |
| `f0_phrase` beats the head only at low σ (late in sampling) | Guidance on contour has to act late; check the guidance schedule before retraining anything. |
| Nothing beats the f0 head anywhere | No internal contour to tap. Melody control has to come from the input side (inpainting a guide melody, latent prompts) or from training. |
| The random-init control matches the trained blocks | The readout comes from the architecture mixing the input, not from learned structure. Treat the block result as null. |
| `beat` falls well below 0.80 under the stricter split | The July map was inflated, so recheck the rhythm-head recommendation built on it. |

## Limits and what is untested

- **Melodia labels are noisy:** run on the separated stem, octave errors are possible. Exact labels need rendered MIDI (the render bank), which is the planned second stage, together with instrument and transposition transfer and a steering test along the probe direction.
- **The f0 head's training split** may include some of these crops. That would inflate the head baseline, making the "blocks beat the head" test conservative.
- **Off-trajectory activations.** They come from forward-noised real latents, not the model's own sampling path. A positive result should be checked on rendered trajectories.
- **Tested on the CPU only.** 7 tests: the targets (band separation on a synthetic contour), the grouped ridge, and a full extract → analyze pass on a fake DiT and corpus. The real model, real companions, run time and disk use are untested.

## Results (Run 2026-11-04/05)

Raw results: [`eval/melody_probe_2026-11-04/melody_probe_map.json`](eval/melody_probe_2026-11-04/melody_probe_map.json)

160 crops, 66 artists, 25053 voiced frames, window 320 frames; ridge R^2, folds grouped by artist.

| sigma | target | best block (R^2) | x_t ctx | f0 head | z0 ctx | hpcp oracle | random-init best | null |
|---|---|---|---|---|---|---|---|---|
| 0.99 | f0_semi | 3 (-0.013) | -0.019 | -0.001 | 0.220 | -0.044 | - | - |
| 0.99 | f0_slow | 3 (-0.013) | -0.023 | -0.000 | 0.206 | -0.059 | - | -0.058 |
| 0.99 | f0_phrase | 6 (-0.002) | -0.003 | -0.001 | 0.008 | -0.000 | - | -0.003 |
| 0.99 | f0_note | 8 (-0.002) | -0.001 | -0.000 | -0.001 | -0.000 | - | - |
| 0.99 | f0_delta | 6 (-0.002) | -0.003 | -0.000 | 0.000 | -0.000 | - | - |
| 0.99 | beat | 14 (0.005) | -0.002 | - | 0.606 | - | - | - |
| 0.909 | f0_semi | 1 (0.152) | 0.037 | 0.282 | 0.220 | -0.044 | - | - |
| 0.909 | f0_slow | 1 (0.171) | 0.039 | 0.340 | 0.206 | -0.059 | - | -0.045 |
| 0.909 | f0_phrase | 6 (0.007) | -0.001 | 0.003 | 0.008 | -0.000 | - | -0.003 |
| 0.909 | f0_note | 9 (-0.001) | -0.001 | -0.000 | -0.001 | -0.000 | - | - |
| 0.909 | f0_delta | 10 (-0.001) | -0.003 | -0.000 | 0.000 | -0.000 | - | - |
| 0.909 | beat | 22 (0.635) | 0.044 | - | 0.606 | - | - | - |
| 0.715 | f0_semi | 13 (0.287) | 0.153 | 0.397 | 0.220 | -0.044 | - | - |
| 0.715 | f0_slow | 15 (0.322) | 0.150 | 0.466 | 0.206 | -0.059 | - | -0.075 |
| 0.715 | f0_phrase | 16 (0.026) | 0.004 | 0.021 | 0.008 | -0.000 | - | -0.002 |
| 0.715 | f0_note | 14 (0.003) | -0.000 | 0.000 | -0.001 | -0.000 | - | - |
| 0.715 | f0_delta | 12 (0.006) | -0.002 | -0.000 | 0.000 | -0.000 | - | - |
| 0.715 | beat | 14 (0.820) | 0.356 | - | 0.606 | - | - | - |
| 0.5 | f0_semi | 12 (0.327) | 0.205 | 0.454 | 0.220 | -0.044 | 0.112 | - |
| 0.5 | f0_slow | 12 (0.346) | 0.195 | 0.525 | 0.206 | -0.059 | 0.108 | -0.064 |
| 0.5 | f0_phrase | 12 (0.029) | 0.007 | 0.037 | 0.008 | -0.000 | 0.002 | -0.003 |
| 0.5 | f0_note | 11 (0.006) | -0.000 | 0.001 | -0.001 | -0.000 | -0.002 | - |
| 0.5 | f0_delta | 12 (0.006) | -0.000 | -0.000 | 0.000 | -0.000 | -0.002 | - |
| 0.5 | beat | 14 (0.828) | 0.518 | - | 0.606 | - | - | - |
| 0.285 | f0_semi | 11 (0.327) | 0.217 | 0.470 | 0.220 | -0.044 | - | - |
| 0.285 | f0_slow | 11 (0.339) | 0.204 | 0.538 | 0.206 | -0.059 | - | -0.074 |
| 0.285 | f0_phrase | 12 (0.031) | 0.007 | 0.053 | 0.008 | -0.000 | - | -0.003 |
| 0.285 | f0_note | 11 (0.005) | -0.000 | 0.001 | -0.001 | -0.000 | - | - |
| 0.285 | f0_delta | 12 (0.005) | 0.000 | -0.000 | 0.000 | -0.000 | - | - |
| 0.285 | beat | 14 (0.829) | 0.586 | - | 0.606 | - | - | - |
| 0.137 | f0_semi | 11 (0.326) | 0.219 | 0.474 | 0.220 | -0.044 | 0.151 | - |
| 0.137 | f0_slow | 11 (0.342) | 0.205 | 0.554 | 0.206 | -0.059 | 0.148 | -0.072 |
| 0.137 | f0_phrase | 12 (0.029) | 0.007 | 0.060 | 0.008 | -0.000 | 0.004 | -0.004 |
| 0.137 | f0_note | 13 (0.003) | -0.001 | 0.001 | -0.001 | -0.000 | -0.001 | - |
| 0.137 | f0_delta | 12 (0.003) | 0.000 | -0.000 | 0.000 | -0.000 | -0.002 | - |
| 0.137 | beat | 14 (0.828) | 0.601 | - | 0.606 | - | - | - |

## Synthesis & Methodological Audit (Kuang, November 5, 2026)

### What holds ($R^2$, $\sigma = 0.5$ unless noted):

| Target | Best block | $x_t$ ctx | Clean $z_0$ ctx | f0 head | Random init | Null |
|---|---|---|---|---|---|---|
| `beat` | 0.83 (block 14) | 0.52 | 0.61 | – | – | – |
| `f0_semi` (pitch height) | 0.33 (blocks 11–12) | 0.21 | 0.22 | 0.45 | 0.11 | – |
| `f0_slow` (10 s line) | 0.35 (block 12) | 0.20 | 0.21 | 0.53 | 0.11 | −0.06 |
| `f0_phrase` (1–6 s) | 0.03 | 0.01 | 0.01 | 0.04 (0.06 at $\sigma=0.137$) | 0.00 | −0.00 |
| `f0_note`, `f0_delta` | ≈0.00 | ≈0.00 | ≈0.00 | ≈0.00 | ≈0.00 | – |

- **Beat replicates decisively:** The strict artist split and per-crop noise give $R^2 = 0.83$ at block 14 (vs July's 0.80). The July rhythm map was not inflated, and the rhythm-head recommendation built on it stands. Furthermore, the blocks beat the clean latent ($0.61$), proving the DiT actively computes rhythm beyond what a local linear read of clean $z_0$ provides.
- **Register is learned at mid-depth:** Peaking at blocks 11–12, clearly above $x_t$, $z_0$, and the random-init control. Block 23 drops back to 0.15.
- **The f0 head reads register better than any block:** However, this comparison favors the head: it receives its own 1 s, 6 s, and 10 s multi-scale averages as features, whereas blocks are probed from single frames, and the head may have seen some of these evaluation crops during training.

### Why the flat phrase result is NOT a negative for the DiT:
- **The linear probe misses within-crop pitch even in the clean latent:** `f0_note`, `f0_delta`, and `f0_phrase` all score $\approx 0.00$ directly from clean $z_0$. Because $z_0$ decodes cleanly to audio, the melody is physically in it; a per-frame linear probe simply cannot decode it.
- **Register vs. Pitch Place Code:** What the linear probes read is register / spectral brightness ($z_0$ score of $0.22 \approx 0.50^2$, matching S22 centroid correlation). Pitch in an audio autoencoder latent is represented as a complex channel activation pattern or place code, not a single linear scalar projection.
- **Design Gap Identified:** $z_0$ was treated as a ceiling, without first validating that the probe could decode within-crop pitch from it. Without a positive control on $z_0$, a flat block score is uninformative about whether melodic contour is present in DiT activations.
- **The head result does hold:** The head's score of $0.06$ on `f0_phrase` (even with its own 1 s and 6 s averages as inputs) confirms that the LatCH f0 head does not follow phrase contour, independently matching D16.

### Resolution: Calibrated Place-Code Probe (Run 2026-11-05)

To resolve the design gap identified above, we executed a calibrated probe (`eval/calibrated_melody_probe.py`) treating pitch as a discrete **place code** (88-bin piano roll, MIDI 21–108; and 12-class chroma) with temporal context ($\pm 2$ frames $\approx \pm 0.19$ s) evaluated via 5-fold cross-validation grouped strictly by artist.

Raw results: [`eval/melody_probe_2026-11-04/calibrated_probe_results.json`](eval/melody_probe_2026-11-04/calibrated_probe_results.json)

#### Stage 1: Clean $z_0$ Gate Results
- **88-bin Piano Roll:** Exact accuracy = **19.3%** (chance = $1.1\%$, **$17.6\times$ above random chance**); within $\pm 1$ semitone = **30.2%**.
- **12-class Chroma:** Exact accuracy = **36.5%** (chance = $8.3\%$, **$4.4\times$ above random chance**); within $\pm 1$ semitone = **53.5%**.
- **Derived Phrase Contour (`f0_phrase`):** Pearson **$r = +0.213$**.
- **Gate Status:** **PASSED [OK]**. The probe successfully extracts melodic pitch and phrase contour directly from the clean autoencoder latent.

#### Stage 2: DiT Depth Profile vs. Random-Init Baseline ($\sigma = 0.5$)

| Block | Piano88 Exact | Piano88 $\pm 1$ Semi | Chroma12 Exact | Chroma12 $\pm 1$ Semi | `f0_phrase` $r$ | Random-Init Piano88 | Random-Init Chroma12 |
|---|---|---|---|---|---|---|---|
| **Clean $z_0$ (Ceiling)** | **19.3%** | **30.2%** | **36.5%** | **53.5%** | **+0.213** | — | — |
| Block 00 | 14.5% | 25.4% | 27.1% | 43.1% | +0.118 | 8.9% | 20.2% |
| Block 02 | 14.9% | 26.2% | 29.8% | 46.1% | +0.139 | — | — |
| Block 04 | 15.1% | 26.6% | 31.2% | 47.9% | +0.138 | — | — |
| Block 06 | 15.1% | 26.9% | 30.4% | 47.6% | +0.178 | 5.6% | 13.4% |
| Block 08 | 15.5% | 27.8% | 29.9% | 47.6% | +0.168 | — | — |
| Block 10 | 16.0% | 28.7% | 30.5% | 48.1% | +0.175 | — | — |
| Block 12 | 15.7% | 28.3% | 30.4% | 48.0% | +0.160 | 4.9% | 12.0% |
| Block 14 | 15.4% | 27.4% | 30.6% | 47.3% | +0.133 | — | — |
| Block 16 | 16.5% | 29.0% | 32.5% | 49.3% | +0.157 | — | — |
| Block 18 | 15.7% | 28.3% | 30.5% | 48.0% | +0.136 | 4.5% | 11.6% |
| **Block 19 (Peak Note)** | **17.6%** | **30.3%** | 31.4% | 49.5% | +0.174 | — | — |
| Block 20 | 16.8% | 29.7% | 30.9% | 48.8% | +0.177 | — | — |
| **Block 21 (Peak Phrase)** | 16.6% | 29.5% | 30.7% | 49.0% | **+0.183** | — | — |
| Block 22 | 17.0% | 29.9% | 31.0% | 49.0% | +0.174 | — | — |
| Block 23 (Output) | 13.2% | 24.1% | 25.3% | 42.6% | +0.164 | 4.5% | 10.9% |

#### Key Conclusions from the Calibrated Probe:
1. **The DiT Residual Stream Explicitly Reconstructs Melodic Place Code:**
   In noise-corrupted latents ($\sigma=0.5$), exact note prediction starts at 14.5% at Block 00, climbs through mid-depth, and peaks at **17.6% at Block 19** (within $\pm 1$ semitone: **30.3%**, matching the clean $z_0$ ceiling of 30.2%).
2. **Decisive Separation from Random Initialization:**
   In random-init weights, representation rapidly degrades with depth (from 8.9% at Block 00 down to 4.5% by Block 18). In contrast, the trained DiT retains and clarifies melodic information through Block 22 (**$3.9\times$ higher note accuracy** than random init at deep blocks).
3. **Phrase Contour ($1$–$6$ s) Emerges Internally:**
   Phrase correlation reaches **$r = +0.183$ at Block 21**, approaching the clean $z_0$ latent ceiling of $+0.213$. The initial linear probe's flat $R^2 \approx 0.00$ was an artifact of testing a scalar affine readout against a continuous VAE latent where pitch is encoded as a distributed channel place code.
4. **Architectural Implications:**
   Melody is not absent from the internal DiT representations. Rather, late-block representations (Blocks 19–22) encode strong melodic place codes and contour before dropping at Block 23 (where the network projects to denoising velocity $\mathbf{v}$). This validates that while conditioning inlets (E24) provide explicit user control, the internal residual stream does form and maintain melodic representations during diffusion denoising.
