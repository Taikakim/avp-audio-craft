# Mood LATCH head: plan and run order (October 30, 2026)

**Goal:** a LATCH guidance head that reads mood from noisy SA3 latents. It works first as a meter and then as a steering target. The base model stays frozen and no new conditioner is trained.

**Route.** Route A, a guidance head, was chosen. Route B, an attribute adapter with an in-trained conditioner, waits until A shows that mood can be read and steered. goa_archive is out of scope for now.

## Data that already exists

The whole-track stores (Kosmos `timeseries` for goa, beside each track for avp) carry three mood fields:
- `effnet_moodtheme_ts`: 56 MTG-Jamendo tags, sigmoid scores at about 1 Hz;
- `va_deam_ts` and `va_emomusic_ts`: valence and arousal on a 1–9 scale at about 1.075 Hz. Their stated rate is about 3 % off; the crop resampler derives the true rate.

The crop companions of `latents_sa3` and `latents_avp` do not have these fields yet.

Raw scores are low and badly calibrated. On goa the mean probabilities are melodic 0.23, energetic 0.13, space 0.12, retro 0.06, dark 0.05 and dream 0.05, and most of the other tags sit near 0 (`eval/corpus_reference.json`).

## Targets

| Choice | Rule |
|---|---|
| Vocabulary | Tags with mass (mean probability ≥ 0.01) that differ between songs (between-song standard deviation of the log-odds ≥ 0.35), ranked by that spread, at most 16. Tags that track loudness or onset density (absolute Spearman correlation ≥ 0.8) are kept but flagged. |
| Units | Log-odds of each tag, z-scored per tag with **training-split** statistics. "+2" means two standard deviations above the training corpus. |
| Time | Per-frame curves, smoothed with an 8 s moving average. |
| Valence/arousal | A separate two-channel spec (`va_spec.json`, z-scored), used only if the census shows real spread and the two estimates (DEAM and emoMusic) agree. |
| Named moods | Only as UI presets later: clusters of crop profiles. Not training targets. |

The spec (`mood_spec.json`) carries the tags, transform, statistics, smoothing and the split it was computed on. `train_latch --target-spec` applies it, refuses a run whose training split differs (the statistics would include held-out crops), and saves the spec in the checkpoint so that inference can turn "dark +2" into a target (`mood_targets.target_from_values`).

## Code

| Repo | File | What it does |
|---|---|---|
| stable-audio-3 `feature/sa3-drum-sep` | `scripts/latch/mood_targets.py` | Spec loading, the log-odds/z transform, missing-value fill, smoothing, the split check, constant targets |
| stable-audio-3 `feature/sa3-drum-sep` | `scripts/latch/mood_census.py` | Step 1: per-tag statistics, the vocabulary proposal, `mood_spec.json` and `va_spec.json` |
| stable-audio-3 `feature/sa3-drum-sep` | `scripts/latch/latch_dataset.py` | The `target_spec` parameter; `npz` targets now leave out crops whose companion lacks the field (they used to be silently swapped for the next crop) |
| stable-audio-3 `feature/sa3-drum-sep` | `scripts/latch/train_latch.py` | `--target-spec`, the split check, the spec saved in the checkpoint |
| stable-audio-3 `feature/sa3-drum-sep` | `scripts/sa3_encode_from_manifest.py` | Companion writes are atomic |
| stable-audio-3 `feature/sa3-drum-sep` | `tests/test_latch_mood.py` | 6 CPU tests |
| avp-audio-craft `feature/mood-latch` | `latch/run_mood_prep.sh` | Steps 0–3 below |

**Tested on CPU:** the 6 unit tests (the atomic-write test is skipped off the desktop; the atomic write was checked directly), and a synthetic end-to-end run: census, then a 2-step training run, with the spec stored in the checkpoint and a mismatched split refused.

**Untested:** the real companion run (coverage on the avp variants), the real census numbers, and GPU training.

## Run order

1. **`bash latch/run_mood_prep.sh`** (CPU, on the desktop):
   - It refuses to start while a `train_latch` run is active.
   - It backs up the existing companions (tar to Mantu).
   - It adds the three fields to both corpora (about 7 GB more on Kosmos) and prints coverage.
   - It runs the census with `--val-frac 0.05 --val-seed 0 --val-group-by song`.
2. **Review `census.txt`.**
   - Drop tags that are mood-meaningless for this music or just loudness, by editing `mood_spec.json` and removing a tag from indices, names, mean and std together.
   - Decide whether to add the valence/arousal head.
3. **Train (GPU).** Use the command the driver prints: the chroma C3 recipe with MSE loss, 12 epochs, the same roots and validation settings. Read the per-tag held-out fit at each noise level (`val_by_t`), and drop tags the head cannot predict at mid noise.
4. **Steering evaluation.**
   - Targets: +2 standard deviations of single tags such as dark or energetic, measured on decoded audio with `eval/mood_timeseries.py`.
   - Baselines through the guided sampler at gain 0.
   - A prompt-only comparison (the mood word in the text prompt), plus drift and quality checks.
   - Listening.
5. **Route B** only if guidance works but is too slow or harms the audio.
