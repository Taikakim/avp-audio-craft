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
