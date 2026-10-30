# LATCH chroma work, October 29–30, 2026: review and fixes

Scope: Antigravity's chroma commits from the evening of October 29 to October 30, 2026.

- **stable-audio-3** `feature/sa3-drum-sep`:
  - e9ce2b6: multi-root chroma pairing and the AVP chroma extractor;
  - b46a3c1: `--val-group-by song`.
- **avp-audio-craft** main, 8b6d7072..df682045:
  - the E22 board;
  - the E13 matrix;
  - the AVP retrain drivers and matrix;
  - the gain ladder;
  - the choice clips;
  - the 40-epoch retrain.

Fixes are on `fix/latch-chroma-eval` (this repo) and `feature/sa3-drum-sep` (stable-audio-3). Everything below was checked on CPU. Nothing was rendered or trained.

## What holds

- **Song-level grouping.** `--val-group-by song` keeps every pitch and tempo variant of a song on one side of the split. Variant crops carry `parent_track`, and originals fall back to `source_track`, which the encoder writes as the same folder name. Before a long run, confirm the smoke log's `Val split` line shows roughly one group per real song.
- **Multi-root pairing.** Each latent root gets its own chroma directory, even though both corpora reuse crop names (`000000.npy`).
- **The 40-epoch retrain.** It uses flags the trainer has, and `relpath` grouping is track-level on `latents_sa3`. On `latents_avp`, `relpath` is per crop (`<track>/<idx>`), so it must not be used there.
- **The AVP matrix baselines** already run through the guided sampler at gain 0.

## Findings

### 1. The AVP heads learned a different target from the Goa head (critical)

**What happened.**
- The Goa store `latents_sa3_stem_chroma` holds `compute_same_chroma` of each crop's separated `other` and `bass` stem audio (WORKLOG, June 25, 2026). The E13 head was trained on its `other` key.
- The first `extract_avp_same_chroma.py` instead applied the linear latent readout W·z + b to the **full-mix** latent. It saved that one array under both `other` and `full_mix`. That readout is the July production-head target.

**Consequences.**
- `C3_avp_aug` learned the production-head target. E21c found that head needs gain 8192 before it rotates the output, so this alone predicts the AVP head's weak steering ("half the chroma lift per unit gain").
- `C3_goa_avp_combined` trained on two definitions under one key, with 2 393 of its 7 300 items from the readout.
- The 0.0205 validation loss cannot be compared with E13's. The readout is linear in the clean latent, so it is easy to predict at low noise.
- The song-split rerun as committed kept the same targets, so it could not tell leakage apart from target mismatch.

**Fix.**
- `extract_avp_same_chroma.py` now reads each crop's stem audio. It uses the encoder's window, native-rate read, fp32 resample and pad or trim to the crop length.
- It then runs `compute_same_chroma(align_to_latent=True)` and saves `other` and `bass`.
- Crops whose folder has no stems are skipped and counted, which most likely covers the augmentation variants.
- A `_recipe.json` marker stops readout files and stem files from mixing in one directory.
- `run_chroma_avp_songsplit.sh` builds these targets first (step 0) and trains into a new output directory (`chroma_retrain_avp_stemchroma_20261030`).

**Treat as void:** the October 29 AVP and Goa+AVP heads and every comparison made with them.

### 2. The choice-clips base clips used a different sampler (high)

`render_choice_clips_chroma.py` rendered `base` with no LATCH config, so `generate()` took `sample_diffusion` (CFG rescale and padding mask). Every steered clip took the guided sampler. This is the confound recorded in E13 note 5.

**Fix:** a `base0` condition (the guided sampler at weight 0), which the page now reads. The old `base` files are left untouched.

### 3. Chord progressions were stretched about 1.3× (high; inferred from code, not rendered)

**What happened.**
- `generate()` renders `seconds_total` plus   of padding, rounded up by `_adapt_sample_size`: 282 latent frames for 20.0 .
- model.py then linearly resamples `target_raw` onto that whole window.
- The targets were built for the 216 audible frames. So each chord change landed about 3  later than the meter assumes, and the last chords fell into the trimmed padding.
- Static targets are unaffected.

**Affected:**
- `i-VI-III-VII` and `keylift` in the AVP matrix (`chroma_avp_matrix_render.py`).
- `keylift` in E13 and the E13 matrix (`chroma_e13_render.py`, `chroma_e13_matrix_render.py`). Those two scripts are not changed here.
- Any progression rendered by `chroma_steer_render.py`.

**Unaffected:**
- E21b, E21c and E22, which use static chords or shapes.
- The choice clips, whose targets are built at the 280-frame window. The script now checks this.

**Fix:**
- `latent_frames()` asks the model for its window, and `fit_to_latent()` holds the last target frame over the padding, so the resample becomes the identity.
- Both are used in `chroma_steer_render.py` and the AVP matrix.
- The matrix now records `head_path` and `target_fit` per clip. It reuses a measured clip only if the clip was rendered with the head configured now and, for a progression, with a fitted target.
- The silent fallback from epoch 10 to another epoch is removed, and `--head ID=PATH` picks a checkpoint explicitly.

### 4. Smaller issues

- **Decode glitch.** The choice-clips renderer had neither the warm-up nor the decode-twice guard, and it reloads the model for each of its 29 rows. Both are added, with a warm-up after every load.
- **Two diagnoses for the s5678 noise burst.** E13 (6) blames the untuned base model at 24 steps. The gain-ladder commit blames the first GPU decode. They should be reconciled in EXPERIMENTS.
- **Partial checkpoint loads.** The full-fine-tune loader used `strict=False` without checking coverage. It now refuses a checkpoint that misses DiT weights.
- **Silent data loss in the dataset (`latch_dataset.py`).**
  - One chroma directory for several latent roots paired the second corpus with the first corpus's files, because the crop names collide. This now raises an error.
  - A chroma file without the requested key used to drop that corpus silently, because `__getitem__` skips failed items. This is now checked at startup.
- **Reproducibility.** The choice-clips plan file lived only in the agent's scratch folder. It is now a `--plan` argument and is copied next to the renders.
- **Unrecorded results.** EXPERIMENTS has no entry for the AVP arms, the song-split arms, the 40-epoch retrain or the choice clips. The only number (0.0205) is in a shell comment.
- **LATCH work on two branches.**
  - Today's LATCH commits went to `feature/sa3-drum-sep`.
  - `latch-sa3-phase1` has five LATCH commits that drum-sep lacks: `--train-frac`, `--t-sampling`, fade windows, `--epoch-hook` and `--grad-ckpt`.
  - drum-sep has four LATCH commits that phase1 lacks.
  - Merge them before the next trainer change.
- **Page cleanup before publishing.** The E22 page names checkpoint files in its text. The choice-clips page uses a commercial track as a chroma target; that is fine as a target, but its audio must not be staged.

## Tests

- **stable-audio-3:** new `tests/test_latch_avp_chroma.py`, 6 tests, covering:
  - song grouping;
  - multi-root pairing under name collisions;
  - refusal of a shared chroma directory and of a missing key;
  - the recipe marker;
  - an extractor run on synthetic stems, where the target follows the A in the stem and not the C in the mix.
- **stable-audio-3:** all LATCH test files pass (60 passed, 2 skipped).
- **avp-audio-craft:** new `eval/chroma_target_fit_test.py`, 5 tests, covering:
  - the latent window through the real `_adapt_sample_size`;
  - fitted versus stretched progression timing;
  - the matrix reuse rule;
  - the partial-load refusal;
  - the decode guard.

**Untested:** the extractor on the real AVP folders (stem names, how many variants have stems), all GPU paths and the latent-window size on the real model config. The choice clips raise an error if the window is not 280 frames.

## Rerun order

1. `latch/run_chroma_avp_songsplit.sh`:
   1. Step 0 prints how many crops have stems. If almost none do, stop and decide whether to render variant stems.
   2. It then trains both arms.
2. Pick each head's epoch from `val_by_t`, then run `eval/chroma_avp_matrix_render.py`, adding `--head` if the pick is not `best`. It re-renders the AVP heads and the progression clips and reuses the static Goa clips.
3. Run `eval/render_choice_clips_chroma.py` for the 29 `base0` clips. The steered clips are reused.
4. Rebuild both pages and run the leak check.
5. Listen.
6. Record the results in EXPERIMENTS, including a note that the October 29 AVP heads are void.
