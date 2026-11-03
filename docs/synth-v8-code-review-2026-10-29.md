# Review of the Synth Inversion V8 code and first results (2026-10-29)

Reviewer: KUANG.
- **Under review:** audio-tools-avp `feature/v8-asymmetric-tse`, commits 90d9a43 to 9d9d6eb (17 files, about 4 100 lines).
- **Results read** (avp-audio-craft `eval/`): `r1_contested_bin_census_results.json`, `r2_oracle_repair_results.json`,
  `v8_phase1_tse_results.json`, `v8_phase2_dynamic_results.json`.
- **Spec and log read:** the revised spec (6878ba4) and the WORKLOG entries of October 28 and 29, 2026.
- **Read in full:** every script except `build_v8_eval_board.py` (checked for its comparisons and claims) and
  `benchmark_v8_dataloader.py` (skimmed).
- **Not done:** nothing was run. The pedalboard behavior in C1 is checked against pedalboard's current source, not the desktop's
  installed version.

## Verdict

The pipeline runs from mixture to DAW bundle, and that scaffolding is useful. None of the four results can be used as evidence yet:
- Phase 2's training audio is very likely broken by a rendering bug (C1).
- Phase 1 is scored with the answer as the cue, on patches the extractor trained on (C4, C5).
- R2's verdict rests on a difference smaller than its own noise (M1).
- R1's genre split is guessed from folder names, and missing stems count as "no masking" (M2).

The order also needs attention. R2's kill condition fired, R3 was not run as registered, and Phase 1 failed its gate (tax 1.37 against
1.25). Phases 2 and 3 still went ahead and are logged as complete, although the spec's roadmap requires each gate to pass first. That
call belongs to WINTERMUTE, who owns the line, and to the project owner.

The audition board compares V8 with a weakened copy of itself, labeled "V6 C" (M9). Fix it before it is published.

## Critical: results invalid until fixed

- **C1. The Phase 2 renderer resets the synth every 93 ms.**
  - `dynamic_dataset_v8.py:105` calls `plugin.process(...)` once per latent frame without `reset=False`.
  - Pedalboard's default is `reset=True`. Its docstring says: "If calling `process` multiple times while processing the same audio or
    MIDI stream, set `reset` to `False`" (`pedalboard/ExternalPlugin.h`, current master).
  - Each chunk therefore starts from a cleared synth:
    - notes start in 16 of the 43 chunks and are cut off at the chunk's end;
    - the other 27 chunks are silent;
    - no note ever sustains, decays or releases.
  - The training set, the validation set, the end-to-end demo and the board all use this renderer.
  - Fix: call `plugin.reset()` once, then `process(..., reset=False)` for every chunk. Listen to one render before and after the fix.
- **C2. The Phase 2 static targets do not match the audio.**
  - The stored target is the bank vector (`statics.append(v6_vec)`). The render then overrides several of its values
    (`dynamic_dataset_v8.py:188-216`):
    - the filter type, with a random choice;
    - the filter balance, set to 0;
    - cutoff, resonance, drive and FM depth, set by the lanes.

    Six of the 59 static targets therefore describe a sound that was never rendered.
  - The drive and FM-depth lanes are inaudible when the base patch has the waveshaper or FM routing off, but they are still targets.
  - Fixes:
    - store the vector as rendered;
    - mask the loss of inactive lanes;
    - take the four lane parameters out of the static head.
- **C3. The drive lane uses different units from the static vector.**
  - The lane writes 0–0.6 directly as `raw_value`.
  - In the static vector, raw 0.5 is 0 dB (`surge_spec_v5.py:81, 235, 301`).
  - So most of the lane's range is below 0 dB, unlike the static vector's drive, which only covers 0 dB and up. Decide which is meant
    and use one convention.
- **C4. The Phase 1 evaluation gives the extractor the answer.**
  - The cue is the first 1.0 s of the clean target (`eval_v8_phase1_tse.py:135`). The scored slice is the first 0.8 s (line 171), so
    the cue contains the evaluated audio.
  - Training does the same: the cue is cut from the same 4 s clip as the target (`musical_dataset_v8.py:264`).
  - At use time the cue comes from somewhere else in the track. Take it from another region of the same stem (for bank items, another
    note of the same patch), never overlapping the scored window. Do this in training and in evaluation.
- **C5. The test patches are training patches.**
  - Phase 1, R2 and the board all score bank_v6 `main_00000` items 0–19.
  - The extractor trains on random items from that same shard (`musical_dataset_v8.py:191`).
  - The V6-C inverter's trainer reads the whole bank with no held-out range (`render_bank_v4.BankMainDataset`). If V6-C was trained on
    bank_v6 (check its `run_meta`), the "clean ceiling" is a training-set number as well.
  - Fix: use a held-out shard, or fresh renders from the prior's `val` split.
- **C6. The CLAP weights still load with no error when the load fails.**
  - `cgsp_extractor.py` loads the checkpoint with `strict=False` and skips silently when the file is missing. Either way it prints
    "Loaded pretrained CLAP weights". That is the V7 failure mode again.
  - Fix: raise when the file is missing, and check missing and unexpected keys, allowing only `position_ids`.
  - The checkpoint now used (630k-audioset, HTSAT-tiny) is a general-audio model. Point-and-Play used a music CLAP with HTSAT-base.
  - R3 as registered was not run: a rerun of V7 Step 0 with 100 patches at three SNRs and confidence intervals. Only a forward pass was
    checked.

## Major

- **M1. R2's verdict is noise.**
  - Demucs costs 0.0100 MSE over clean (0.0831 to 0.0930). The oracle-repaired stem differs from Demucs by 0.0032, with n = 20 and one
    flow draw per condition.
  - A ratio of two small, noisy differences (−31.8 %) cannot fire a kill condition in either direction.
  - The registered design was not run. The run used single 0.8 s bank notes and one 0.8 s kick slice from one song, with no grooves and
    no BS-RoFormer.
  - The hard-edged STFT splice (no crossfade) adds artifacts of its own.
  - What R2 does show: with only a kick in the mix, Demucs costs +12 %, less than V7's +23 % under a snare.
  - Fix: several draws per item, a paired bootstrap interval, and grooved renders.
- **M2. R1's numbers need cleaning before the genre comparison means anything.**
  - The subgenre comes from keywords in the folder name: "goa" means Old-School Goa, and it is checked before "acid".
  - Masking counts only the acid, leads and pads folders, so arp and key stems are ignored.
  - Songs with none of those stems report 0 % masking (5 songs): missing data is counted as no masking.
  - A silent bass in the measured window is not caught. Two of the three Techno songs have bass RMS 0.0 there, which produces their
    −90 dB and −93 dB entries. One of them still reports 88.3 % masking: "active bass" is set relative to the stem's own peak, so a
    silent stem's noise floor counts as active.
  - The sub-to-kick dB values are averaged across songs, so those entries pull the Techno mean to −66 dB.
  - Each song is measured over one 60 s window.

  The direction agrees with the production description: in Goa, other synths mask the body band (42.9 %) more than the kick masks the
  sub. For the numbers themselves, take the genre labels from the producer, exclude songs with missing stems and report medians.
- **M3. The training data is not the spec's Pillar 1.**
  - Target, drums and accompaniment are random crops from random songs (`musical_dataset_v8.py:188-243`). They share no tempo and no
    grid.
  - There is no self-similar kick swap (spec 2.3) and no groove-preserving re-render (spec 2.2).
  - Surge targets are 0.8 s bank items tiled five times.
  - The stem cache holds only seconds 30–90 of each stem, at most 8 clips (`cache_v8_stems.py:43-44`).
  - The validation cache (`val_*.npy`) has no builder in the repository.
- **M4. The extractor model.**
  - An n_fft of 1024 at 44.1 kHz gives 43 Hz bins: three bins between 40 and 150 Hz. That is too coarse for bass fundamentals (E1 is
    41 Hz).
  - The input is the raw real and imaginary STFT, with no magnitude compression.
  - The WORKLOG records a "4D conv kernel reshape for ModularOptimizer", but the trainer uses AdamW (`train_v8_asymmetric_tse.py:285`).
  - Training was 20 000 samples in 11 minutes. That is a smoke test, not a trained model.
- **M5. The reliability target is a ratio mask, not reliability.**
  - |T| / |M| is the ideal ratio mask. It marks "no target here" as unreliable, and that is the very evidence that a filter is closed.
  - A reliability target should be high wherever the estimate can be trusted, including bins that are reliably empty. One option:
    1 − the interference share, computed only where the mix has energy.
  - Nothing downstream uses W yet.
- **M6. The Phase 2 gate measures the wrong thing.**
  - The registered gate is a centroid-trajectory correlation on audio. The code computes Spearman ρ between predicted and true lane
    values, on the same validation set that picked the checkpoint.
  - Sweeps come from five shape families. Rising, falling and exponential are monotone, so any monotone prediction in the right
    direction scores ρ = 1. Report ρ per family.
  - Compare each lane's MSE with what a constant mid-range guess scores (my estimates from the lane ranges in `dynamic_dataset_v8.py`):

    | Lane | Model MSE | Constant guess | Reading |
    |---|---|---|---|
    | Resonance | 0.032 | about 0.03–0.04 | not learned |
    | Drive | 0.018 | about 0.03 | partly learned |
    | FM depth | 0.009 | about 0.013 | partly learned |
    | Cutoff | 0.022 | about 0.055 | partly learned |

  - The data are 500 training renders for a model of about 6 M parameters (my count). Each render is one repeated note at constant
    velocity, so none of the cases that separate a lane from keytracking, velocity or the envelope are in the data yet.
  - The static MSE of 0.076 is over all 59 values, including categorical indices and the stale entries from C2. It is not comparable
    with V6's 0.083, which covers continuous flow parameters only.
- **M7. The end-to-end demo.**
  - The demo computes its mel with n_fft 2048 (`pipeline_v8_e2e.py:85`). Training used 1024 (the `ExactGpuMel` default), so the
    inverter sees a different input from the one it was trained on.
  - `true_static[0]` is the note, not the filter type its comment names.
  - The cue is 0.5 s long (1.0 s in training) and is cut from the target itself.
  - It is one example with one repeated note.
  - The "Mel L1 0.2637" has nothing to compare against.
- **M8. The DAW export.**
  - CC 74, 71, 1 and 11 control nothing in Surge until each parameter is MIDI-learned by hand. The manifest leaves that routing to the
    user.
  - Store the routing in the patch instead: bind each lane's parameter to a Surge macro and make the macros MIDI-learnable, so that
    the `.fxp` carries it.
  - `test_daw_export_v8.py` has no `test_` function, so pytest collects nothing. It also needs Surge to run. A CPU test of
    `create_daw_automation_midi` would check:
    - the note and CC counts (43 × 4 CCs);
    - the CC values;
    - the last tick.
- **M9. The audition board.**
  - The arm labeled "Best Previous Static Model (V6 C Flow)" is not V6-C. It is V8's own static head with flat lanes
    (`build_v8_eval_board.py:291-305`), and its values for those four parameters were trained on stale targets (C2). The "improvement
    over static" figures compare V8 with a weakened copy of itself.
  - Phrase titles name real songs ("Phrase 1: Acid Alien — …"), but the renders are synthetic, with every patch parameter set to the
    same constant.
  - "Beats Demucs 0.3666" refers to 0.3644 against 0.3666, at n = 20, on a gate that failed.

## Process

- **P1. Gates.** The roadmap in spec section 6 requires each gate to pass before the next phase. As run:
  - R2's kill condition fired;
  - R3 was not run;
  - Phase 1 failed its gate;
  - Phases 2 and 3 still went ahead.
- **P2. The WORKLOG claims more than the numbers show:**
  - "TSE edged out Demucs" in Mel-SSIM: 0.3644 against 0.3666.
  - "surpassing it in cutoff accuracy": 0.2353 against 0.2380, at n = 20 with one draw.
  - "Demucs catastrophically degraded" on patches 8, 15 and 20: three items picked out of 20.
- **P3. Three different Phase 1 gates:**
  - the evaluation's docstring says Mel-SSIM;
  - the code checks the MSE ratio;
  - the spec says Mel-SSIM ≤ 1.25 × clean.

## What to keep

- The song-level holdout list, applied in both the dataset and the cache.
- The NVMe cache, which gives the throughput the trainer needs.
- The Phase 2 architecture:
  - mel input at about 100 frames per second;
  - 43-frame lanes on the latent grid;
  - a static head on pooled features;
  - a curvature penalty.
- R1's direction, which matches the production description.
- The MIDI writer's tick arithmetic, and the `.fxp` export reused from `audio_utils`.

## Order of fixes

1. **Phase 2 data.**
   - Fix C1 and listen to a render. Fix C2 and C3.
   - Rebuild the cache with phrases that vary notes and velocity.
   - Rerun with ρ per family, R² per lane, and a test set separate from checkpoint selection.
2. **Phase 1 evaluation.**
   - Fix C4 and C5: non-overlapping cues and held-out patches, in training and evaluation.
   - Add the registered baselines (BS-RoFormer and the matched two-stem model).
   - Use more than 20 items, with several draws each.
3. **CLAP.** Fix C6, then run R3 as registered.
4. **R2.** Rerun with several draws and confidence intervals, on grooved renders.
5. **Board.** Correct the text and the static arm before publishing.

## Addendum: fixes made on `feature/v8-asymmetric-tse`

KUANG fixed the critical items on the V8 branch the same day.
- **Testing:** the fixes have CPU tests with fakes in `scripts/synth_inversion/test_v8_fixes.py` (14 tests, all pass). Nothing ran on
  Surge, pedalboard or the GPU.
- **The C1 test can fail:** the fake synth follows pedalboard's documented reset behavior. With it, the original renderer leaves
  27 of 43 chunks silent and returns 14 samples too few. The fixed renderer leaves no chunk silent.

**Fixed:**
- **C1, the renderer:**
  - one reset per phrase, then `reset=False`;
  - chunk lengths taken from the plugin's actual output, so the 43 chunks join without gaps.
- **C2, the static targets:**
  - the stored vector is the one rendered;
  - the lane parameters are left out of the static loss;
  - inactive lanes are masked (`lane_active`).
- **C3, lane units:** lanes are stored in the v6 vector's units, with drive raw = 0.5 + 0.5 × drive. The DAW export converts lanes to
  raw values for the plugin and for the CC curves.
- **The Phase 2 cache:**
  - disjoint bank items for train, val and test;
  - phrases that vary pitch, velocity and gate by default;
  - new default directories (`*_v2`), so pre-fix caches are not reused.
- **M6, the Phase 2 evaluation:**
  - the gate is computed on the test split;
  - R² per lane against a constant guess;
  - ρ per sweep family.
- **C4, the training cue:**
  - The dataset takes the cue from another clip of the same stem, so the cache now records stem ids. `cache_v8_stems.py --split val`
    builds the held-out cache.
  - Surge bank items are off by default (`surge_frac = 0`).
  - An old cache without stem ids is refused.
- **C4 and C5, the Phase 1 evaluation:**
  - held-out patches from the prior's `val` split by default, or another bank shard;
  - the cue is the same patch at another note;
  - 4 flow draws per item, a paired bootstrap interval, and per-item rows.
- **C6, CLAP loading:** `load_clap_weights` raises on a missing path, a missing file, or any missing or unexpected key other than
  `position_ids`.
- **M7, the end-to-end demo:** the training mel settings, the correct note field, and a cue at another note.
- **M8, the DAW manifest:** it now says each CC has to be MIDI-learned in Surge.
- **M9, the board:**
  - the comparison arm is V6-C itself, and the board refuses to build without it;
  - neutral titles;
  - a cue at another note;
  - summary cards read from the results JSON files.
- **M4, the trainer's docstring:** it now says AdamW.

**Still open:**
- R1 cleanup (M2), the R2 rerun (M1), and R3 as registered.
- The registered Phase 1 baselines: BS-RoFormer and the matched two-stem model.
- The registered Phase 2 gate: centroid-trajectory correlation on re-rendered audio.
- Extractor frequency resolution and input compression (M4), and the reliability target (M5).
- Groove-aligned mixtures and the self-similar kick swap (M3).
- Surge macro routing stored in the exported patch (M8).

**Rerun order on the desktop** (from `scripts/synth_inversion`):
1. **Listen to one render first:**
   `python -c "import numpy as np, soundfile as sf, surge_spec_v5 as S5, surge_spec_v6 as S6, dynamic_dataset_v8 as dd; p = S5.init_synth(); lanes = np.stack([np.linspace(.1, .9, 43)] + [np.full(43, .3)] * 3).astype(np.float32); sf.write('v8_render_check.wav', dd.render_dynamic_patch(p, S6.vector_to_patch(np.full(59, .5, np.float32)), 40, *lanes), 44100)"`.
   Notes should sound whole, and the cutoff should open over 4 s.
2. **Rebuild the stem caches with stem ids:** `python cache_v8_stems.py --split train`, then `--split val`.
3. **Phase 2:** `python dynamic_dataset_v8.py`, then `train_v8_dynamic_inverter.py`, then `eval_v8_phase2_dynamic.py`.
4. **Phase 1:** retrain the extractor (the cue changed). Then run `eval_v8_phase1_tse.py --bass-manifold … --all-manifold …`, with
   the V6 prior's two manifold files.
5. **The board,** once both results files exist.
