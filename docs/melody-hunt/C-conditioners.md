# Melody hunt, track C: trained melody conditioners (morph, pianoroll, contour)

Evidence dossier, not prose. Compiled 2026-11-03 (afternoon) from EXPERIMENTS.md, DISCOVERIES.md, journals, WORKLOG.md, MASTER.md,
docs/training-findings.md, run_meta.json files, and the result files under ~/evals_aac/control_runs/. The track was still moving
while I read: the newest item I saw is the Melodia check on the invented melodies (melodia.json written 15:35, not yet in
EXPERIMENTS.md). Numbers are copied, not rounded. "MEASURED" = a meter said so. "HEARD" = a person listened. Unless stated, nothing
below was listened to by anyone.

Conventions: `EXP:n` = line n of /home/kim/Projects/SAO/EXPERIMENTS.md as of today. `CR/` = /home/kim/evals_aac/control_runs/.
Eval pages live in /home/kim/evals_aac/ (public path `files/evals/`, as cited in EXPERIMENTS).

Vocabulary used throughout (so the guide does not mix them up):
- **Morph conditioner / Head-B / melody_contour**: `sa3_control.train --control-mode melody_contour`. A small encoder turns a
  Kant & Polansky (K&P) "morphological space" rank-contour stream (L2/L3/L4 = 3/13/75 symbols, vocab 5/15/77 with specials) into
  tokens that a cross-attention adapter (plus DoRA on the backbone) reads. Stream source: whole-track Melodia f0 of the separated
  `other` stem. Checkpoints are named `riffer_step*.pt` (riffer = the sa3_control trainer's file naming, not a melody term).
  Zero tokens are the trained null; the uncond branch gets zeros (control/sa3_control/generate.py:110; lumi/render_morph.py:224-226;
  eval/e23b_morph_synth.py:125; all only when cfg != 1).
- **Pianoroll / mir_ctrl inlet**: a (128, T) float16 roll (velocity/64 while a note is held) at the latent rate (10.7666 fps), added
  per frame inside DiT blocks 12-23 through the "modular local cond" path; trained with a 0.2 dropout to zeros. Goes through
  `dit.py` `modular_local_cond`, which by default is duplicated into BOTH CFG branches (`torch.cat([v, v])`, MASTER:1021).
  `modular_cfg_null` (dit.py:516-517, default off, added 2026-11-03) puts zeros in the uncond branch.
- **CFG-stream gotcha** = the line above. With the default, text is scaled by cfg (7) and the stream by 1.

---------------------------------------------------------------------------------------------------------------------------------

## 1. Experiment log (chronological)

### 1.0 Substrate facts this track depends on (other tracks own them)
- **07-22 synthetic battery** (EXP:1899, `eval/musicology/latent_melody_analysis_v2/`): 900 fluidsynth renders, 19 patterns x 4 tempos
  x 10 timbres. Pitch is linearly readable from the SAME latent (ridge R2 0.86-0.97, ~15-dim subspace) but a contour-token head on z0
  (Head-A) scored macro-F1 0.28, near chance. same_chroma reads chroma timbre-invariantly on the same pairs (08-11). Meter: probe on
  z0; positive control = the ridge R2. MEASURED. Relevance: the latent carries pitch, but contour TOKENS were never decodable from it.
- **Melodia is input-length dependent** (C, 2026-10-29; EXP:1293, continuity.journal.md 2804+): whole-track Melodia on a stem
  reproduced exactly (1.000); over a 47 s window the same stem agrees with the whole-track reading on 52% of frames, 19% octave-off.
  Hence no render can reproduce the fed K&P symbols. MEASURED.

### 1.1 Head-B melody-contour bracket (C, 2026-07-24 to 07-29)
- Question: does the FiLM `melody_contour` conditioner (Head B, train job 20190732) steer melody?
- Method: 8 checkpoints past step 5280 x cfg {1, 7, 16} x gain {1, 1.5} = 48 cells rendered on LUMI (job 20336044), transcribed with
  MuScriptor, own-vs-wrong-contour "confusion" metric (`adopt_active` minus the mean of the 3 non-requested streams).
- Number: cfg1 INERT (conf about -0.1, z0_cos 0.99); cfg7 weak/mixed; cfg16 positive and growing; peak step9240 cfg16 g1.5 conf
  +0.227 (adopt .464 vs wrong .237). Disintegration gate 4/4 clean on all 48 cells. GHOST-NOTE's separate rollup (WORKLOG:370-380):
  only 14/48 cells clear 1.5x the null floor, best 0.123 adopt vs 0.044 null, 100% gate-clean.
- Meter/control: the first null-floor metric was inconclusive at high cfg, so C added the confusion metric; no external positive
  control stated. MEASURED, not heard. Source: continuity.journal.md:1135 (the 2026-07-29 entry), WORKLOG.md:370-380.
- Why it matters: this is the "weak but real control" that D17 was built on (EXP:1291+). D17's own text says to re-check what meter
  that rested on (EXP:1293). Note the two documents disagree on what Head-B is (FiLM vs cross-attention), see section 5.

### 1.2 D12 contour-token stack and the morph-space design (C + external drafts, 2026-08-12 to 08-21)
- `mir/src/conditioners/{morph_grids,contour_codes,contour_streams,contour_stats}.py`, mir commit 42c3a83: monotone-invariant K&P
  dense-rank tokens over frame/event grids; redundancy judged by conditional entropy (nested L: H(L2|L3)=0 reproduced in tests).
  Source: EXP:1352-1360. Design note: papers/deep-research/MORPHOLOGICAL_SPACE_DESIGN_NOTE.md (continuity.journal.md:1555-1561: Kim
  surfaced Kant & Polansky "The Structure of Morphological Space").
- Streams: `eval/build_morph_streams.py`, 5390 crops per alphabet, voiced-stride-4 grid, tolerance 0.5 st; IOI streams p95-gated
  onsets, log-IOI, tol 15% (EXP:806-ish, D13 block).
- EXP:1352 status line still reads "READY (code) / PLANNED (Q1)". Q1 (IOI/duration stream on the note-onset grid) is described as
  "do next"; the IOI arms were nevertheless trained on 08-21 (D13 block), so the header is stale.
- Not measured: Q2-Q7 (their `measure_contour_codes.py` was not in the zip).

### 1.3 D13/Q1 burn-day wave: pianoroll notes lane and the 16-arm morph bracket (C/W/Kim, 2026-08-21 to 08-22)
- Pianoroll: `lumi/sbatch/pianoroll_fullft.sbatch`, jobs 21439467/68 (duplicate pair), then 21445517/18 EPOCHS=32 seeds 1/2.
  Full fine-tune, T256, AdamW lr 1e-4 + WSD knee 25%, bf16, 8 GPUs, batch 4 x accum 2 x 8 = effective 64, EMA, mir_ctrl pack
  `pianoroll`, 128 channels, blocks 12-23, dropout 0.2; dataset goa `latents_sa3` with muscriptor ids, captions
  `goa_longform_sidecar 0.6,0.3,0.1`. Run dir `.../lumi_runs/pianoroll_fullft/proll_fullft_t256_bf16_s1` (also s2), terminal
  `epoch=31-step=2688.ckpt`. Source: run_meta.json of both; EXP:823-850. Purpose line: "Kim direct 2026-08-21: NOTES LANE".
- In-training meter: `control_ablation.jsonl`, RF loss with true / shuffled / zero roll. At the 16-epoch landing (C, 08-21 23:30):
  control_gain +0.0000 (step 0), +0.0079 (600), +0.0116 (1200), ordering true < zero < shuffled (EXP:801-803). Final rows of s1: step 2600
  loss_true 0.8135, loss_shuffled 0.8182, loss_zero 0.8153 (file read by me). So the DiT uses the roll in training, by about 0.2%
  of loss. MEASURED. (Contrast: at inference the roll turned out to be strongly followed, see 1.13.)
- Morph: 16 arms = vocab L2/L3/L4/IOI3 x medium-base / full-FT backbones x seeds, Head-B path (jobs 21439456, 21439457), rendered by
  `lumi/render_morph.py` (21445586): 16 arms x 8 contour crops x {g1, g2, null} = 384 cells.
- Seed 2 of the pianoroll run is not evaluated anywhere I could find.

### 1.4 D15 first run (C, 2026-08-26): pianoroll steers at inference?  [FIRST VERDICT RETRACTED 08-28]
- Question: does the trained roll steer a render? Method: `proll_fullft_t256_bf16_s1`, inlet re-installed on blocks 12-23, state dict
  loaded clean (1045 tensors, 0 missing); six tracks x their DENSEST 256-frame window (about 5% density), 1 seed/prompt, 24 steps, T256;
  arms true / shuffled / foreign / zero. Roll in both CFG branches (the default; see 1.13).
- First number (EXP:778-790): true - foreign +0.110 chroma cosine, 6/6, p 0.016; true - shuffled +0.022, 5/6, p 0.109, n.s.;
  true - zero about +0.10. Conclusion at the time: "harmonic/pitch-set conditioner more than a rhythmic one", note-level timing does NOT
  transfer. Meter: per-frame chroma cosine, no positive control for placement. MEASURED. This number was later retracted (1.5).
- A single-track first pass gave true - shuffled +0.12 on 20 note-bearing frames (0.24% dense) and would have been reported as
  "follows the roll"; across six tracks it fell to +0.022 (EXP:791). Do not screen on one window.
- Weights used: not stated in the original text (EMA vs online is not recorded; see section 3).

### 1.5 D15 revision (C, 2026-08-28 after Kim's ear): placement DOES transfer
- Trigger: Kim listened and said (as quoted EXP:749) "true & shuffle have very identical notes; foreign seems to be in a different
  key." HEARD (Kim, short remark on the six-track set, not a formal rating). The six rolls have mean pairwise pitch-class cosine
  0.29, so every foreign pairing is a different key; chroma cosine cannot separate "adopted the key" from "followed the melody".
- Method: MuScriptor transcription of the renders, decomposed per arm against the source roll. Table (EXP:751-763):
  key (pitch-class profile cos) true 0.952 / shuffled 0.955 / foreign 0.169; content (pitch-set Jaccard) 0.875 / 0.857 / 0.533;
  melody ((pitch, frame) F1) 0.534 / 0.435 / 0.094. **True - shuffled F1 = +0.100, 6/6 positive, sd 0.044, sign test p = 0.016.**
  True - foreign +0.441.
- Consonance-weighted (Kim 08-28, EXP:765): of 5871 played notes vs the requested roll, 69.5% exact, 30.4% a different note inside the
  roll's own pitch-class set, 0.2% outside it; by interval class to the nearest requested note 87.0% unison/3rd/4th/5th class, 13.0%
  m2/M2/tritone. Caveat from the source: in-key is generous if the pitch-class set is dense.
- Positive control: key and melody F1 against the roll are only meaningful because shuffled holds key/content and drops F1. Also
  flagged: the pitch-blind onset "timing" measure SATURATED (0.795-1.000 across every arm including foreign), do not quote it.
- Caveats in the source: MuScriptor under-transcribes legato (07-11 finding), melody F1 0.534 is partial, n=6, 24 steps, T256.
  MEASURED + one HEARD remark. Source EXP:733-800.
- Propagation: D16's premise still quoted the retracted +0.022 until C corrected it on 09-03 (EXP:711, WORKLOG:2419). MASTER:679
  still quotes it with a pointer (section 5).

### 1.6 D12 morph audition page (C, 2026-09-03)
- The 384 morph cells already existed on disk (never auditioned); transcoded 392 clips to AAC 192k and built `eval/build_morph_page.py`
  -> `~/evals_aac/morph_conditioner/index.html` (same-playhead, one table per stem with its reference clip and a control-off column; the
  projection is zero-init so off = the plain model). WORKLOG:2419. HEARD: nobody is recorded as having listened to the full grid.
  EXP:1353 says "Kim's ears are the next gate" and "no objective adherence metric has been run".

### 1.7 Morph measurement attempts, four meters, four failed gates (C, 2026-09-04)
- MERIT (AMAAI-Lab, wrapper control/sa3_control/merit_eval.py): self-check exact 1.000; S_mel SATURATED on same-corpus material (two
  different references score 0.611 mean / 0.861 max while a cell scores 0.49-0.69 against its own). At gain 2.0 conditioning raised
  FOREIGN similarity more (+0.041) than own (+0.025), diff -0.017, p 0.71; the +0.025 was "a generic style shift".
- D15's transcription measure on the morph grid: own-vs-foreign melody +0.022, 80/192, p=1; it failed its own dynamic-range gate.
- Structural reason (C): K&P dense rank is monotone-invariant, so it discards absolute pitch by design; MERT embeddings, pitch-class
  cosine, Jaccard and note-cell F1 all measure what the conditioner throws away.
- Contour-to-contour test `eval/morph_contour_ab.py`: FAILED its positive control: re-extracting from the reference audio scored 0.146,
  lower than the renders (0.151). Encoder control against ground-truth f0 reached only 0.755 / 0.550 / 0.337 for L2 / L3 / L4.
- Also: on the Pattern-2 full-FT backbone, conditioning degrades 60/64 cells with S_tim collapsing 0.373 to 0.169 "(matches Kim's ear)"
  (HEARD claim, unspecified when). Source WORKLOG:2420 (the 09-04 entry), continuity.journal.md:2446-2470.
- Verdict then: none. Result class: instrument failure, not a negative.

### 1.8 D17 morph conditioner at capacity: training (C/W, 2026-09-09)
- Run `morph_L3_lion_r128_bs32_2026-09-09`: `--control-mode melody_contour`, L3 vocab 15, medium-base, Lion 4e-5 + D-Adaptation
  autoscale, r128 dora-rows joint, effective batch 32 (4 x accum 8), bf16, crop 512, EMA 0.999, 12 epochs, seed 1. Corpus goa
  `latents_sa3` + AVP non-aug = 5678 crops (5390 goa + 288 AVP, 2814 tracks); AVP f0 backfilled with `eval/backfill_crop_f0.py`.
- Training instability: median gnorm 0.104 -> 0.415 -> 2.700 over the first 2.8 epochs, 5.067 at about 9.9 epochs (run_meta purpose).
- Four silent bugs found while scoping (all fail toward a null): `--dora-rank` a NO-OP under fusion optimizers; `--smoke` printed OK on
  zero evidence; multi-root sidecars read one corpus's contours for both; hyperball freezes zero-init adapters (EXP:1330-1346).
  Later audit added `--val-frac`/`--early-stop-patience` inert outside fingerprint mode, `--warmup-steps` inert off adamw (D17 ran with
  NO warmup), `--cautious` inert under lion (EXP:1261-1268). So D17's run_meta kill criterion ("val loss diverging") never had a
  val set. Clips rendered 2026-09-10 03:39 (418 files) from EMA weights whose shadow started at the zero-init adapter.
- HEARD (unattributed): "Listening put the only audible contour correspondence at step2000, gain 2" (EXP:1231). I could not find who
  listened or any note of it outside that sentence: UNSOURCED beyond EXPERIMENTS.

### 1.9 D18 same recipe with warmup-hold-cosine (W, 2026-09-10): trained, NEVER EVALUATED
- `morph_L3_lion_r128_cos_2026-09-10`: autoscale off, warmup 1000, hold 1000, cosine 10000 micro-batches, save-every 500, 24 ckpts +
  `riffer_final.pt`. Result: gnorm max 0.268 over 600 samples, never above 2 (D17 worst bin 2.718): the instability is fixed.
- Adherence: UNTESTED. run_meta result says "Adherence untested: no renders yet". The 10-29 A/B was run on D17 only; E23b used D17
  deconvolved checkpoints; D18 appears in no meter run. (EXP:1227-1259, run_meta.json.)

### 1.10 D17 A/B (C, 2026-10-29): no detectable contour following
- Question: does a render follow ITS fed contour more than another stem's, and more than the unconditioned render?
- Method: `eval/morph_f0_contour_ab.py`; 200 clips (6 EMA ckpts steps 2000-12000, deconvolved and deconvolved+clamped steps
  4000-10000; 4 stems; null / g1 / g2; gain ladder 3-8 at steps 2000/4000). Meter: Demucs htdemucs `other` -> Melodia (mir settings)
  -> sentinel pool -> Pearson r of the semitone curve against the fed stem's store curve. Transposition- and scale-invariant, which
  fits a rank-contour conditioner.
- Positive control (a gate in the script, GATE_R 0.30, GATE_GAP 0.20): reference clips through the same path, r own +0.431 vs foreign
  -0.066 (gap +0.496); the true stem window reads +0.84. PASSED. A local 48-frame variant had weaker range (0.125 vs 0.034).
- Numbers: pooled own - foreign **+0.0001** (74/144 positive, p 0.80); conditioned - null **+0.023** (73/144, p 0.93); 2 SE = 0.05,
  "any effect is below about 12% of a perfect copy's 0.43". Deconvolved weights no better than EMA (-0.08 / +0.04 vs +0.02), so EMA
  dilution was NOT hiding a working conditioner. Local-window r: +0.002, 75/144. The one clean cell (deconvclamp step8000 g2.0, 4/4)
  is described as the expected noise hit among about 36 cells. MEASURED, not heard in this run.
- Open failure points listed by C: (1) never learned the contour (no adherence meter during training), (2) learned but the prompt at
  cfg 7 swamps it, (3) the meter sees only the whole-line shape, ceiling 0.43. Source EXP:1293, run_meta result, KIM-TASKLIST:541.
- The meter's own weakness: ceiling 0.43 on a perfect copy, and the fed stream cannot be reproduced even in principle (1.0).

### 1.11 D16 temporal ceiling of trajectory guidance (W, 2026-11-03) -- guidance, not a conditioner; listed for the boundary
- `eval/d16_contour_ceiling.py`, lead f0 LatCH head, gain 16384, triangle waves in phase vs antiphase, 6 prompts x 2 seeds, 120 clips.
  Follow (corr with target minus corr with antiphase, chance 0, max 2): 10 s +0.155 [0.021, 0.285] 16/24; 5 s -0.080; 2.5 s -0.073;
  1.25 s -0.044; 0.625 s -0.019 [-0.042, -0.0] 10/24 (CR/d16_contour_ceiling_20261103/report.txt). Null baselines correlate with slow
  targets by chance (0.521 at 10 s), so slow-period numbers are noisy. Conclusion: ceiling above a 10 s period, arrangement level.
- NOT affected by the CFG-stream finding (gradient guidance, no stream inlet). Other tracks own guidance heads. Included because the
  pianoroll result (1.13) contradicts the blanket sentence "note-level timing does not transfer" that MASTER draws from D15 + D16.

### 1.12 E23 synthetic-MIDI contour battery (W, 2026-11-03)
- (a) meter: `eval/e23a_contour_meter.py`, CPU, 8 known melodies x 3 soundfonts x 3 programs, alone and at 0 dB over goa drums + bass.
  Melodia reads them: corr with the true line 0.999 up/down, 0.998 arch/valley, 0.993 at a 5 s wave, 0.984 at 2 s (EXP says 0.97-0.98),
  foreign about -0.15 to 0; within a semitone (octave-folded) on 98% of voiced frames; follow score 1.996 of 2. Not lower over backing
  (own 0.858 vs 0.829 alone, aggregate). `steps_big` low (own -0.096) because voiced coverage is 0.46 on two-level lines; `arp_fast` 0.756.
  Orpheus soundfont would not load. Positive control: this IS the positive control for the f0 meter. MEASURED.
- (b) conditioner: `eval/e23b_morph_synth.py`, D17 deconvolved steps 4000 and 10000, gains 1/2/4, 6 clean streams (repeating phrases,
  because K&P reads under 0.5 st per 0.37 s as flat) + shuffled + null, 3 seeds, T=512, 132 clips. Meter: Melodia on the generated
  MIX, follow = corr with fed line minus corr with its mirror. Result: step4000 fed -0.009 / -0.083 / +0.075 (positive 9, 7, 10 of 18)
  at gains 1/2/4; step10000 +0.047 / +0.037 / -0.003 (11, 9, 13 of 18). Shuffled |follow| 0.109-0.212, null 0.070-0.209, so fed is
  inside chance. Verdict (W): meter works, conditioner learned nothing about contour; "park the morph lane".
- W's own scope limit (EXP:1903): this covers the Head-B cross-attention path with Melodia-trained checkpoints, nothing else. D12's
  16 arms and D18 were not tested. A `generate.build_conditioner` bug that ignored the checkpoint's melody vocabulary was fixed on the way.
- Worth noting: (a) validates Melodia on clean synthetic mixes, but (b) scores Melodia on model-generated mixes; there is no known-positive
  conditioner for (b), so its power is only what the shuffled/null spread implies (about 0.1-0.2 noise on a scale of max 2).

### 1.13 E24 pitch-invariant conditioner, arms C and B, and D15 re-read (W, 2026-11-03)
Order of events, all 2026-11-03, from WORKLOG:2905-2917 and the journal:
- **07:32 packs + arm C training.** `eval/e24_build_contour_packs.py`: skyline of the non-drum MIDI from `Kosmos/muscriptor_full`
  (5400 crops, voiced 77.5%, 3 empty). Arm C = pitch centred on the crop median, (2, T); arm A (interval one-hot + onset/hold, (26, T))
  built, never trained. Train: DoRA r128, modular, T=256, batch 16, 2,400 steps (7 epochs), `latch/run_e24_contourC.sh`, run
  `e24_contourC_r128_2026-11-03`. In-training RF loss at step 2201: true .57988, shuffled .58005, zero .58103 (EXP:1911).
- **10:23 arm C first eval: UNINFORMATIVE, not a negative** (`eval/e24_eval.py`, steps 800/1600/2400, 6 crops). One prompt + one seed
  for all clips => every fed render read as the same held E4 (voiced 0.84), foreign arm duplicated the true arm, flat lines dropped.
  Positive control: decoded crops 0.42 vs own stream, 0.10 vs others, 4/6 usable. Gate 0/54. Found the CFG-stream gotcha while debugging.
- **11:01 arm C RESULT** (`eval/e24_eval2.py`, step 2400, 24 crops with their own prompt + seed, arms true / shuffled / true_null /
  shuf_null / zero = 144 clips). Meter: MuScriptor on the render -> skyline -> Pearson r with the fed stream's centred pitch over
  jointly sounding frames; flat lines score 0 and are counted; follow = r with the stream it was FED minus r with the other stream
  (eval/e24_eval2.py:219-221). n=48 = 24 crops x {true, shuffled}. Numbers (CR/e24_contourC_eval2_20261103/report.txt):
  null uncond **+0.467 [+0.392, +0.543], 46/48**; both branches +0.151 [+0.050, +0.249], 30/48. Absolute r_fed: true_null +0.565,
  shuf_null +0.568, true +0.194, shuffled +0.087, zero +0.045. Positive control: decoded source crops 0.542 (16/24 at least 0.5). Gate 0/24
  in all four arms. With a 16-frame (1.5 s) running mean removed: null +0.103 [+0.059, +0.147] 34/48; both +0.023 [-0.030, +0.065] 29/48;
  decoded crops +0.19 (rl_fed +0.344 vs other +0.151). Within a semitone of the fed line 14% vs 12% with no stream vs 39% for decoded crops.
  Scaled CFG cost: PQ -0.25, CE +0.4 (EXP:1913). MEASURED, not heard. Page ~/evals_aac/e24_contour.html.
- **14:34 arm B RESULT** (same recipe/length; `latch/run_e24_contourB.sh`; pack `latents_sa3_contourB` (15, T): 13 L3 shapes + note-on +
  sounding, on the note grid, 5400 crops, 0 errors). Centred-pitch measure +0.055 [-0.011, +0.120] 33/48; on L3 shape agreement
  +0.020 [+0.006, +0.037] 31/48 vs arm C +0.028 [+0.014, +0.041] 33/48; decoded crops +0.209; gate 0/48. RF loss step 2201 true .58002,
  shuffled .58003. Verdict: neither the inlet route nor the note source rescues K&P L3 symbols. MEASURED. Arm A not trained
  (W: same local information, low priority).
- **15:04 to 15:17 D15 re-read, training crops** (`eval/e24_eval2.py --pack P`, same meter, CR/pianoroll_cfgnull_goa_t256_step2688_20261103/
  report.txt): null uncond fed-minus-other +0.636 [+0.562, +0.710] 47/48; both branches +0.212 [+0.117, +0.308] 30/48; (pitch, frame) F1
  fed minus other null +0.203 [+0.181, +0.226] 48/48, both +0.045 [+0.034, +0.058] 42/48; F1 with the fed roll 0.653 (null) vs 0.324
  (both branches true arm); source (decoded) crop 0.609; no stream 0.045. Share of played frames on a fed note: 0.837 null / 0.525 both
  / 0.084 none. Note scale +0.263 [+0.225, +0.301] 46/48 (both +0.033 [0.000, +0.065] 23/48). Gate: 6/48 fail, all CE drift (both
  branches 13/48 incl. hf-blowout, whitening, noise-zcr). Weights: ONLINE (the run's EMA has under one half-life).
- **15:17 D15 invented melodies** (`eval/d15_new_melodies.py`, 12 prompts x 3 invented single-voice melodies (scale walks, arpeggios,
  random keys, notes of 2-6 frames) = 36 clips, zero-stream baseline, plus 24 transposed crops (+5 / -7 semitones of real rolls)).
  Fed pitch sounds on 73% of frames (no stream 2.5%, another melody 3.2%); top line on the fed pitch 67%; 36/36; shuffled 3 s blocks 40%
  (shared pitches), fed minus shuffled +0.33 [+0.29, +0.37]; recall 21% to 100% by prompt; gate 2/36 (CE drift). Transposed crops: F1
  0.63 with the transposed roll vs 0.05 with the roll as it was, 24/24, gate 0/24, PQ 7.17 vs 7.68 and "duller". Page
  ~/evals_aac/pianoroll_melody.html. MEASURED by MuScriptor, not heard.
- **15:35 (not yet in EXPERIMENTS) independent meter on the invented melodies** (`eval/d15_melodia_check.py`, untracked file;
  CR/pianoroll_newmelody_goa_t256_step2688_20261103/melodia.json). Melodia (no part in training) share of voiced frames within one
  semitone, octave folded. My means from the file: fed 0.744, shuffled blocks 0.431, other melody 0.167, no stream 0.18 (n_new=36,
  zero=12); fed > shuffled in 34/36 and fed > other in 34/36. The page text (published) states 74% vs 43% / 17% / 18%, fed minus other
  +0.58 [+0.50, +0.65], 34/36. Closes the circularity that MuScriptor made the training rolls and also scored the renders. Still not heard.
- Next steps named by W (EXP:735): stream-only guidance scale apart from text cfg; EMA vs online; held-out crops; render server/Forge;
  retrain on the AVP set for release (weights trained on commercial music stay private).

### 1.14 Data pipeline (reference)
- `eval/build_pianoroll_ctrl.py`: each `latents_sa3` crop id has a MuScriptor `.mid` transcribing exactly its 380.4 s / 4096-frame segment
  (time 0 = crop start); rendered to (128, 4096) float16 at 10.7666 fps, velocity/64 while held; saved as
  `Lehto/latents-all-backup/latents_sa3_proll/<stem>.ctrl.npy`; train_lora's mir_ctrl slices windows (T256 etc.). Input MIDIs
  `/run/media/kim/Kosmos/muscriptor_full` (5400 mid + stats, "sole copy", MASTER:177). Pack list: MASTER:145.
- E24 packs: `latents_sa3_contourC` (2, T), `..._contourA` (26, T), `..._contourB` (15, T), same 5400 crops.
- Morph streams: `eval/build_morph_streams.py`, 5390 crops per alphabet from Melodia f0 of the `other` stem (whole track), sidecars per
  crop; D17 corpus 5678 crops (AVP backfilled by `eval/backfill_crop_f0.py`).
- Bigset (12524 crops) has no f0 at all; morph conditioning on it needs a Melodia pass over `goa_archive_stems` (23129 tracks x 4 stems,
  about 190 GB, 48 GB for `other` alone) (EXP:1347-1350 region, D17 text).
- Where run data lives now: `/run/media/kim/Mantu/sa3_control_runs/__riffer/` (unlabelled `riffer_200trk_*` runs, no purpose in their
  run_meta; their melody relevance is UNSOURCED), D17/D18 and E24 runs are on the UUID drive
  (`.../sa3_control_runs/morph_L3_lion_r128_*`, `.../sa3_lora_runs/e24_contour{B,C}_r128_2026-11-03`); pianoroll runs under
  `.../lumi_runs/pianoroll_fullft/`; morph grid under `.../lumi_runs/morphcond`. Rendered evidence: CR/*_20261103/.

---------------------------------------------------------------------------------------------------------------------------------

## 2. What we KNOW

| Claim | Conf. | Why |
|---|---|---|
| A per-frame note roll through the mir_ctrl inlet is followed at inference by the August full fine-tune once CFG scales the stream: training crops F1 0.653 vs source crop 0.609 vs no stream 0.045; fed minus other (pitch, frame) F1 +0.203 [+0.181, +0.226] 48/48. | High on the meter, one checkpoint | Two independent runs of the eval give the same picture (E24 eval2 pack P; d15_new_melodies); positive control (decoded crop 0.609) and floor (no stream 0.045). Same checkpoint also read +0.100 6/6 in August. |
| It plays melodies it never trained on: fed pitch on 73% of frames vs 2.5% with no stream, 36/36; transposed crops F1 0.63 vs 0.05, 24/24. | Medium-high | Second meter (Melodia, 34/36 for both fed>shuffled and fed>other). Still one checkpoint, one seed per prompt, 12 prompts, not heard. A thin lead on top of the track would also score. |
| The CFG-stream gotcha is real and large: same checkpoint and seeds move +0.151 -> +0.467 (E24 arm C) and +0.212 -> +0.636 (D15 ckpt), F1 fed-minus-other +0.045 -> +0.203. | High | Reproduced on two checkpoints (a DoRA r128 and a full FT) with the same eval, paired by crop. Mechanism read off dit.py. |
| Scaling the stream costs quality: PQ -0.25, CE +0.4 (arm C); PQ 7.17 vs 7.68 on transposed crops. | Medium | Audiobox on the same clips; gate otherwise passes (0/48, 2/36). |
| The June-August "does not transfer" reading of D15 was a meter problem, not a model fact: chroma cosine +0.022 became F1 +0.100 6/6 once transcription replaced it. | High | EXP:749-791: shuffled holds key 0.955 and content 0.857, so only placement differs; Kim's ear agreed on the foreign arm. |
| The D17 morph conditioner (Head-B, Melodia L3 stream) shows no detectable contour following under a meter that passes its own positive control (+0.431 vs -0.066). | Medium-high | Bound 2 SE = 0.05, about 12% of the perfect-copy score; 144 pairs; EMA and deconvolved weights; E23b (clean synthetic contours, 132 clips) agrees. Bound is limited to what this meter can see (whole-line shape). |
| Melodia on clean synthetic lines is accurate (0.998-0.999 on up/down/arch/valley, within a semitone on 98% of voiced frames), also over drums and bass. | High | CPU test with known melodies, 3 soundfonts. Does not cover real arrangements. |
| The cross-attention adapters do already null the uncond branch, so the CFG-stream gotcha does not explain the morph result. | Medium | generate.py:110, render_morph.py:224-226, e23b_morph_synth.py:125 all put zeros in the uncond when cfg != 1. I read the three call sites; I did not trace which script produced the D17 clips beyond file names (`...__g1.0__cfg7`). |
| K&P L3 symbols from clean MuScriptor notes through the better inlet do no better than centred pitch (arm B +0.020 vs arm C +0.028 on L3 agreement). | Medium | One run each, 2,400 steps, small effect sizes with overlapping intervals. Says nothing about longer training. |
| Centred (pitch-invariant) pitch is followed at shape scale only: +0.467 over seconds, +0.103 at note scale (1.5 s mean removed), within a semitone 14% vs 12%. | Medium | Same eval; but see the training-length/model-size confound in section 4. |
| Absolute-note rolls beat centred pitch on the same meter: F1 0.653 and note scale +0.263 (full FT, 32 ep) vs note scale +0.103 (DoRA r128, 7 ep). | Low-medium | Model size, training length and data pass differ; this is a comparison across arms, not an ablation. |
| MuScriptor makes the training rolls AND scores renders (circularity), but Melodia (independent) agrees on the invented melodies (0.744 vs 0.431 / 0.167). | Medium | Melodia numbers read by me from melodia.json; not yet written into EXPERIMENTS. |

---------------------------------------------------------------------------------------------------------------------------------

## 3. What we know we DON'T know

1. **Does it sound like music following a line?** Nothing in D15's re-read, E24 arm C or arm B has been heard. Cost: Kim listening to
   the two pages (36 invented melodies + 24 transposed crops + a cfg ladder). Hours of ears, no compute.
2. **Was the August eval wrong because of CFG, or because of the chroma meter?** The August chroma verdict was already superseded on
   08-28 by transcription (F1 +0.100, 6/6, with the roll in both branches). So the CFG finding explains why the effect was 4-5x weaker than
   it could be, not why it looked null. Nobody ran a paired both-branches vs null comparison on the INVENTED melodies and transposed
   crops, only on training crops (E24 eval2 pack P). Would answer: is generalisation to unseen notes a product of the CFG fix?
   Cost: ~24 min of GPU, one script change (d15_new_melodies with `modular_cfg_null` off). Risk: none.
3. **What cfg does the stream need?** The null-uncond run scales the stream by the TEXT cfg (7). A separate stream-only guidance scale
   is W's own "next". Cost: add a second scale to dit.py plus a ladder (cfg_stream 1/2/4/7/12). PQ/CE cost per step is unknown.
4. **EMA vs online weights.** D15 results are online weights; the run's EMA "has under one half-life". Whether the August eval used
   EMA or online is not recorded (EXP:733-800). Would answer: was part of the August weakness the EMA? Cost: one render of the existing
   ckpt both ways.
5. **Why is the in-training control_gain tiny?** About 0.2% of loss (0.8135 true vs 0.8153 zero), while inference follows the roll
   strongly. Is control_ablation a poor proxy (it zeroes the stream in BOTH branches at one t sample)? Cost: check how it is sampled;
   cheap, CPU reading of the trainer.
6. **Is the morph result a real negative for contour tokens, or a result of Melodia noise + Head-B?** E23b says it did not follow clean
   synthetic contours, which argues for the former, but: only D17 deconvolved ckpts at 4000/10000 were tested; D12's 16 arms (including
   IOI3, full-FT backbones) and D18 were never measured. Cost: run `morph_f0_contour_ab.py` / `e23b` on D18 `riffer_final.pt` and 1-2
   D12 arms; renders only, about an hour of GPU each.
7. **Does an L3 stream trained through the per-block inlet from CLEAN notes follow if trained at D15's scale (full FT, 32 epochs)?**
   Arm B was only DoRA r128, 2,400 steps. Cost: one local training (about 2.5 h for the DoRA scale, much more for full FT) + the
   existing eval.
8. **Arm A (interval one-hot, onset/hold flag)** was built and not trained. It is the only variant that gives an explicit onset signal
   in a pitch-invariant encoding. Cost: one 2.5 h training + eval.
9. **Seed 2 of the pianoroll fine-tune** (`proll_fullft_t256_bf16_s2`) has never been evaluated. Would give a second checkpoint for the
   one-checkpoint caveat. Cost: one render + score.
10. **Held-out crops.** D15's "unseen" melodies are synthetic; real held-out transcriptions from tracks outside the 5400 were not used.
    The training crops may be memorised (F1 0.653 > source crop 0.609 on training crops is itself a sign of fitting, or of the decode
    being a lossy reference). Cost: transcribe a few non-corpus tracks (MuScriptor) and feed their rolls.
11. **Head-B 07-29 "steers at cfg16, inert at cfg1"**: nobody explained why cfg1 (cond branch only, no doubling at cfg 1 in
    render_morph.py) gives z0_cos 0.99. Could mean the gain was too small to enter without extrapolation. Cost: unknown; a render at
    cfg1 with larger gain.
12. **Whether the D17 "audible correspondence at step2000 gain 2" was real.** Unattributed (EXP:1231). The objective A/B finds none.

---------------------------------------------------------------------------------------------------------------------------------

## 4. Things that LOOK settled but rest on thin evidence

- **"The pianoroll conditioner was fine all along."** The August checkpoint already showed F1 +0.100 true-shuffled 6/6 in August with the
  roll in both branches; the November re-read shows a 4-5x stronger effect with a scaled stream. Both rest on ONE checkpoint, one
  seed per prompt, 12 prompts for the new melodies, and a transcriber that trained the rolls. The statement "the failure was in how
  inference fed the stream" is half true: the first retracted verdict was the meter (08-28); the CFG feed only throttled the
  effect. Nobody has run the one-line controlled comparison on unseen melodies.
- **"Park the morph lane" (E23).** Reasonable, but: D18 is untested; D12's other 15 arms untested; E23b used streams that are repeating
  phrases of at most 6 shapes; the K&P encoding treats under 0.5 st per 0.37 s as flat; the score has a null spread of 0.07-0.21 on a
  max-2 scale; there is no known-positive conditioner to show E23b could see a working Head-B (the only positive control is the f0
  meter). E23's own scope note says it covers only Head-B + Melodia checkpoints.
- **D17's meter ceiling.** The positive control passes at +0.431, which is 43% of a perfect score; the null result is "below 12% of a
  perfect copy", not "zero". A conditioner that bends pitch curves partially (say r 0.1) is within noise.
- **"Contour not notes" for arm C.** Within a semitone 14% vs 12% with no stream, but arm C trained 2,400 steps as DoRA with a centred
  pitch input; D15's absolute-note full FT gets 84% of played frames on a fed note. The two arms differ in input (absolute vs centred),
  adapter (full FT vs DoRA r128), training length (32 epochs vs 7), and the comparison is reported as input-driven in
  docs/training-findings.md ("Absolute notes beat centred pitch ... though model size and training length differ too").
- **MASTER's "slow structure transfers, note-level does not"** (MASTER:670-683) rests on D15's retracted +0.022 and on D16's 10 s
  ceiling; the latter is a guidance-head fact, the former is superseded. Only the pointer in parentheses was updated.
- **F1 0.653 vs source crop 0.609.** The model's render scores above the decoded original crop on the same meter. Either the render
  overshoots the roll's note density (precision) or the MuScriptor-on-decode reference is a ceiling that is not tight. The
  source document does not say which.
- **Gate counts.** "Gate 2/36" and "0/48" come from the standard disintegration gate against the zero arm of the SAME crop; they do not
  mean clean audio, only no disintegration signature. PQ/CE costs are real and the clips are called "duller".
- **The 08-26 six tracks gave F1 0.534 (true); the November training-crop run gives 0.324 (true, both branches, 24 random crops).** The
  August set was the six DENSEST windows. These are different samples, not a regression, but nobody has said so in the documents.

---------------------------------------------------------------------------------------------------------------------------------

## 5. Contradictions between documents, and which earlier results the CFG finding reopens

### 5.1 Contradictions
1. **MASTER.md:679-680 vs EXP:749-791 (D15).** MASTER cites "true-shuffled +0.022, n.s." for the pianoroll and says it was "superseded
   2026-11-03 ... with CFG scaling the stream, that same fine-tune follows notes". EXPERIMENTS shows the +0.022 was already retracted on
   2026-08-28 (transcription: +0.100, 6/6, p 0.016). docs/training-findings.md (the "melody control exists" entry) calls D15's first
   verdict "melody does not transfer" "measured with control unscaled": the first verdict was a chroma-meter artefact AND unscaled; the
   August revision already contradicted it. The attribution of the null to CFG alone is therefore an over-simplification.
2. **E24 arm C description of the follow score.** EXP:1913 says "fed stream minus with the same notes in shuffled 3 s blocks"; the code
   (eval/e24_eval2.py:219-221) and the WORKLOG/journal say "fed minus other": each render against the stream it was fed minus the other
   arm's stream (for shuffled arms the fed stream is the shuffled one). Same number, different words.
3. **EXP:1914/1913 "first melody conditioner to follow its input at this scale"** (written for arm C) vs the D15 re-read the same day that
   follows better (+0.636, F1 0.653) with an older checkpoint. The sentence was true when written (11:01) and is stale now.
4. **Head-B described as FiLM vs cross-attention.** continuity.journal.md:1135 and WORKLOG:370 call Head B a "FiLM melody-conditioning
   adapter"; EXP:1293 and E23 call it a "Head-B cross-attention adapter". Unresolved whether these are the same module through the
   project; a reader of the final guide will need one description.
5. **EXP:1352 D12 status "READY (code) / PLANNED (Q1)"** vs the body and D13 block, which show the 16 arms trained 08-21 and rendered.
6. **EXP:1910 vs EXP:1903.** W's first note that arm B was "skipped: E23 found the L3 lane does not follow" was corrected the same day;
   both statements exist in different places (the correction is inside the E24 line, the original in the journal's first entry).
7. **WORKLOG 2026-09-03 says D16's premise quoted the retracted +0.022;** D16's header was marked corrected, but D16's own "Why it
   exists" paragraph and Kill criterion still say "D15 found note-level timing does NOT transfer".
8. **Morph audition (EXP:1353) says "no objective adherence metric has been run"; WORKLOG 09-04 says four were run and all failed gates.**
   Not a contradiction in fact: the sentence predates the 09-04 entry and was not updated.
9. **D17 header "A/B DONE: NO DETECTABLE CONTOUR FOLLOWING"** vs EXP:1231 "Listening put the only audible contour correspondence at step2000,
   gain 2": measured null vs unattributed heard positive; the documents do not reconcile them.

### 5.2 Does the CFG-stream finding reopen it?

| Earlier result | Stream path at the time | Reopened by the CFG-stream finding? |
|---|---|---|
| D13 in-training control_gain (pianoroll) | train-time ablation, not CFG | No. Different measurement. |
| D15 first run 08-26 chroma +0.022 n.s. / +0.110 foreign | mir_ctrl both branches | Already superseded by the meter fix on 08-28. The CFG finding adds that every number from that eval was throttled (F1 +0.045 vs +0.203). The "timing does not transfer" reading is dead on two grounds. |
| D15 revision 08-28 (F1 0.534 true, +0.100 vs shuffled) | both branches | Understates control; re-read with null uncond is on training crops (E24 eval2 P) and invented melodies; not on the original six densest windows. |
| D16 temporal ceiling (lead f0 head) | gradient guidance (LatCH) | No. No stream inlet. |
| E23a meter on synthetic lines | meter test | No. |
| E23b synthetic contours into morph checkpoints | cross-attn adapter, zeros in uncond (e23b_morph_synth.py:125) | No (W's claim; I read the call site). The uncond was already null. |
| D17 A/B, morph conditioner | cross-attn adapter, zeros in uncond (render_morph.py:224-226) | No, per W (EXP:1913: "morph runs' adapter already used a null uncond"). Caveat: the D17 gain-ladder clips came from a later render script I did not trace. The open failure point (2) "the prompt swamps it at cfg 7" is not the same as the both-branches bug. |
| D18 | not evaluated | Not applicable yet. |
| D12 morph grid (384 cells, cfg7) | `render_morph.py`, null uncond | No. |
| Head-B bracket 07-29 (steers at cfg16, inert at cfg1) | FiLM/Head-B adapter, render loader fixed | Unclear. cfg dependence is the same shape as the CFG finding but the mechanism claimed here is different (null uncond already in force). Flag as UNRESOLVED. |
| E24 arm C first eval 10:23 | both branches, one prompt/seed | Superseded by eval 2 the same day. |
| E24 arm C (before-after) | both -> null | This is the finding. +0.151 -> +0.467. |
| E24 arm B | null uncond | Done correctly, negative stands. |
| B7 mir_ctrl "resurrection x8" and any other mir_ctrl eval (MIR-timeseries conditioner, notegrid88, metrical, etc.) | both branches | YES: MASTER:1021 says every mir_ctrl eval before 2026-11-03 understates control; a "weak conditioner" verdict through this inlet is not a verdict (training-findings.md 2026-11-03 entry). I did not find a list of which other evals that covers: that is the other tracks' to enumerate. |
| D14 pianoroll a2a (cross-prompt a2a with MIDI crop as control, spec EXP:~830) | likely both branches | Probably affected; whether it was run for the pianoroll lane is not shown in what I read. UNSOURCED. |

---------------------------------------------------------------------------------------------------------------------------------

## 6. Possible blind spots (my SPECULATION, not findings)

1. **Cross-attention adapters and the sign of "null uncond".** For a cross-attention conditioner, CFG = uncond + s(cond - uncond) scales
   the CONTROL effect by s too; the morph result was at cfg 7 with gain 1-8. A stream that the model only learned a tiny effect for
   (the 0.2%-of-loss scale seen for the pianoroll) could still be below the noise floor of the meter without a bug. A matched check would
   be the pianoroll's in-training control_gain curve for the morph runs (RF loss true vs shuffled vs zero), which I saw only for arms B and C
   (arm B .58002 vs .58003, no gap at all; arm C .57988 vs .58005, a gap of 0.00017, yet C followed at +0.467). I would not read a flat RF-loss gap as proof of an inert conditioner.
2. **RF-loss ablation as a meter.** Arm B's loss gap is 0.00001 and arm C's 0.00017 (true vs shuffled at step 2201), yet C follows. So the
   training-time control_gain is a very weak predictor of inference following; nobody has asked whether D17's training logs would have
   missed a working conditioner for the same reason (D17 had NO val set, per the inert-flag audit).
3. **Which t does the control matter at?** The rectified-flow stream adds at every denoising step; the stream may matter mostly at high
   noise (global melody) and not late. No t-schedule ablation (stream active only for t > x) exists; this is also a cheap way to cut the PQ/CE cost.
4. **The dead-decode fault.** MASTER:1021 / W's 11-03 journal: `expandable_segments` caused NaN/wrong-first-decode audio in this
   process family, and a "dead check passes wrong audio" silent-damage case. The E24/D15 render scripts set other env flags; I did not
   verify that these runs were free of `expandable_segments`. Gate 0/48 and 2/36 and the positive controls suggest not, but it is the
   kind of instrument fault that fails toward "no effect". Quick check: grep the run logs / process env.
5. **MuScriptor's own bias.** "Not ruled out: the transcriber favouring whatever the stream made loudest" (EXP:1913). A stream that adds
   a lead timbre would raise MuScriptor's skyline regardless of pitch. The Melodia cross-check and the shuffled/other controls mitigate
   but do not remove it. A cheap null: feed a roll in the wrong octave/transposed and see whether MuScriptor's line moves (the transposed-crop
   test already does: 0.63 vs 0.05).
6. **Prompt/genre confound for recall.** Recall ran 21% to 100% by prompt, with several of the lowest on the "2010s psy-trance, progressive trance" (21%, 23%) and
   "intense Psytrance pie..." (30%) prompts, but also "mid 90s goa trance, 148 bpm" (32%). Possibly prompt-dependent mixing level rather than conditioner weakness. Not tested: same melody,
   all 12 prompts, vary stream gain.
7. **Training distribution of the roll.** Training rolls are polyphonic MuScriptor transcriptions of full mixes (bass, pads, leads); the
   "invented melody" is single voice. It works, but does it play the line as a LEAD or buried in the mix? The "top line" statistic
   (67%) answers part of this; nobody has looked at whether the render adds the other voices of the roll's polyphony.
8. **Is the morph null a K&P-alphabet fact or a Melodia-quality fact?** Arm B routes the same alphabet from clean notes; it shows +0.020
   vs C's +0.028 on L3 agreement. The two results (D17 null, arm B ~null) together hint that L3 symbols themselves are the weak
   link, but arm B is a different route, 7 epochs, and has never been checked against a known-positive L3 conditioner. A stronger test
   would pre-train arm C and fine-tune the head toward L3.
9. **Whole-track vs window Melodia for training.** Training streams were whole-track Melodia (stable), but any inference-side stream built
   from a short reference window (as the UI would do) is a different Melodia output (52% frame agreement). This is a deployment trap for
   the morph lane that does not apply to the pianoroll (MIDI is exact).
10. **Single-chain data.** All three conditioners (pianoroll, arm C/B, morph) draw from the same ~5400 goa crops; the Melodia and
   MuScriptor features share their source mixes. Nothing here tests cross-genre transfer; the invented melodies are tested against 12
   goa/techno/jazz-fusion prompts, but the weights saw only goa.

---------------------------------------------------------------------------------------------------------------------------------

## 7. Good numbers, figure-worthy data files, eval pages

### Numbers for the guide (as quoted in the sources)
- CFG stream, same checkpoint + seeds, fed-minus-other r: both branches +0.151 [+0.050, +0.249] 30/48 -> null uncond +0.467 [+0.392,
  +0.543] 46/48 (arm C); D15 ckpt +0.212 [+0.117, +0.308] 30/48 -> +0.636 [+0.562, +0.710] 47/48; (pitch, frame) F1 +0.045 [+0.034, +0.058]
  42/48 -> +0.203 [+0.181, +0.226] 48/48; share of played frames on a fed note 0.084 / 0.525 / 0.837 (none / both / null).
- Invented melodies (36): fed pitch on 73% of frames vs 2.5% none vs 3.2% another melody; top line 67%; 36/36; Melodia within a semitone
  0.744 vs 0.431 shuffled vs 0.167 other vs 0.18 none (34/36 each).
- Transposed crops (24): F1 0.63 with the transposed roll vs 0.05 untransposed; PQ 7.17 vs 7.68, CE 6.10 vs 6.42.
- The meter story (for the AUDIT-THE-INSTRUMENT section): chroma cosine true-shuffled +0.022 n.s. vs MuScriptor F1 +0.100 6/6 p 0.016
  (same six renders); key 0.952/0.955/0.169, content 0.875/0.857/0.533, melody F1 0.534/0.435/0.094 (true/shuffled/foreign); 69.5% exact notes,
  30.4% in-set, 0.2% outside.
- Morph null: D17 own-foreign +0.0001 (74/144), conditioned-null +0.023 (73/144), positive control r +0.431 vs -0.066; E23b fed follow -0.083
  to +0.075 inside shuffled |0.109-0.212| / null |0.070-0.209|; E23a Melodia 0.999/0.998/0.993/0.984 on synthetic lines.
- Training-time control gain: pianoroll RF loss true 0.8135 / shuffled 0.8182 / zero 0.8153 at step 2600 (but at inference the roll is
  followed strongly), arm B .58002 vs .58003, arm C .57988 vs .58005 (step 2201).
- Four-meters-failed table (09-04): MERIT self 1.000 but own +0.025 vs foreign +0.041; contour re-extraction positive control 0.146 vs
  renders 0.151; encoder control 0.755 / 0.550 / 0.337 for L2/L3/L4.
- D16: follow +0.155 (10 s), -0.080 (5 s), -0.073 (2.5 s), -0.044, -0.019 (0.625 s); null 0.521 -> 0.079 shows why slow periods are noisy.

### Data files (CPU-readable)
- CR/pianoroll_cfgnull_goa_t256_step2688_20261103/{cells.jsonl, scores.json, report.txt, run_meta.json, midi/} (training crops, 24 x 5 arms)
- CR/pianoroll_newmelody_goa_t256_step2688_20261103/{cells.jsonl, melodia.json, midi/, *.wav|.m4a} (invented melodies + transposed crops,
  melodia.json = the independent meter; wavs per clip)
- CR/e24_contourC_eval2_20261103/{scores.json (144 rows), report.txt, report_first.txt, run_meta.json, crops.json, midi/}
- CR/e24_contourB_eval2_20261103/ (arm B, same layout)
- CR/e24_contourC_eval_20261103/ (the uninformative first eval; keep as a worked example of a test design failure)
- CR/e23a_contour_meter_20261103/{results.json, report.txt}; CR/e23b_morph_synth_20261103/{per_clip.json, report.json, report.txt, cells.jsonl}
- CR/d16_contour_ceiling_20261103/{per_clip.json, report.json, report.txt}
- D17 A/B JSON: `<UUID>/sa3_control_runs/morph_L3_lion_r128_bs32_2026-09-09/morph_f0_contour_ab.json`; older meters in eval/morph_contour_ab*.json,
  eval/morph_merit.json, eval/morph_note_ab.json, eval/morph_direction_ab.json (the four failed 09-04 meters)
- In-training ablation: `.../lumi_runs/pianoroll_fullft/proll_fullft_t256_bf16_s1/control_ablation.jsonl` (21 rows); E24 runs'
  `control_ablation.jsonl` under the run dirs.
- Scripts: eval/build_pianoroll_ctrl.py, e24_build_contour_packs.py, e24_build_l3_pack.py, e24_eval.py, e24_eval2.py, d15_new_melodies.py,
  d15_melodia_check.py (untracked), run_d15_cfg_null.sh, e23a_contour_meter.py, e23b_morph_synth.py, d16_contour_ceiling.py,
  morph_f0_contour_ab.py, morph_contour_ab.py, build_morph_streams.py; dit.py:516-517 (`modular_cfg_null`).

### Eval pages (local ~/evals_aac/, public path files/evals/)
- `files/evals/pianoroll_melody.html` (invented melodies + transposed crops, includes the Melodia check; plain-language explainer present)
- `files/evals/e24_contour.html` (arm C follow test, arm B)
- `files/evals/f0_contour.html` (D16)
- `~/evals_aac/morph_conditioner/index.html` (D12 384-cell same-playhead audition, with reference clips) and `~/evals_aac/headb_bracket.html`
  (07-28 Head-B bracket, 48 cells)
- Not listened to by anyone for the first three. For a guide with audio, the "melody alone / generated / no stream" rows of
  pianoroll_melody.html are the natural clips (cells 0, 4, 10 and 34 have recall 98%, 89%, 80%, 100% on the page, while 6, 22, 23 and 35 are the
  weak ones at 32%, 21%, 23%, 30%): choose both ends so the guide is honest, but pick only after someone listens.
- Related papers: papers/deep-research/MORPHOLOGICAL_SPACE_DESIGN_NOTE.md (K&P), MERIT (AMAAI-Lab, ~/Projects/MERIT), MuScriptor (transcriber).
