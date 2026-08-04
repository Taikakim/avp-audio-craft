# Melodic LatCH / FiLM — design note (#53 rider arms)

**CONTINUITY 2026-07-22, from Kim: "think about the possibility of a melodic LATCH/FILM
model."** Grounded in the musicology study (eval/musicology/, same day): goa leads are a
same-note 16th pedal (91% of corpus) + a ~7-cell oscillation vocabulary; memorability =
within-file contour repetition (hook decile 56× vs 0×). That gives us, for the first time,
a SMALL, DISCRETE, per-frame melody representation — which is exactly what LatCH heads and
FiLM control streams want.

## 0. The representation (shared by everything below)

Per-frame contour classes at SAME rate (10.766 Hz), resampled from the 16th grid
(~9.5 Hz @143 BPM, nearest-frame): `{rest, pedal, move±1, ±2, ±3, ±5, ±7, ±12}` = 11
classes. Key-invariant by construction (intervals, not pitches — matches the motif mining).
Training targets already exist: **eval/musicology/melodies.jsonl = 2,649 quantized lead
streams id-aligned with latents_sa3 crops** (whose latents we have). Data prep = one CPU
script (grid→frame resample + rest-fill); no new extraction.

Class imbalance is the known trap: pedal dominates. Weighted CE + report per-class F1,
never accuracy.

## 1. Head A — melody-contour LatCH head (cheap, do first)

Per-frame 11-class classifier on DiT activations, **taps L8–15** (five-method layer
landscape: mid-stack = semantic/control bottleneck; single-tap L14 ≈ full adapter),
t-conditioned like every LatCH head (InnerControl lesson). LatCH training loop unchanged —
this is one more head family in the existing sweep harness.

Three uses, in value order:
1. **Latent-space melody eval probe**: score hook_melodic_ratio-style stats from z0
   DIRECTLY (head → contour stream → motif stats), no decode, no muscriptor. Every render
   already saves z0 (standing directive) — the melody-gap metric becomes ~free on the whole
   board. (The wav→muscriptor path being wired today is the calibrator/ground truth for it.)
2. **LatCH guidance toward hookness**: time-varying class-target guidance through the
   existing latch_guided plumbing (ChromaSchedule precedent for scheduled targets). Steering
   TOWARD "pedal + one oscillation cell, repeated" is steering toward the corpus's measured
   hook anatomy. Training-free at inference once the head exists.
3. Probe cartography: which layers/timesteps hold contour info — extends the layer×feature
   map with the first MELODIC feature (all current features are energy/spectral/rhythm).

Risks: skyline-derived targets are noisy (octave-doubling confound is documented in the
report) — accept for v1, the 11-class scheme mostly absorbs it (octave bounce is its own
class). Gate: per-class F1 vs the noise-invariance doc's bar before any guidance use.

## 2. Head B — FiLM melody-conditioning adapter (the product)

sa3_control arm, `control_mode="melody_contour"`: input stream = per-frame class embedding,
FiLM at the usual taps. **Generate FROM a supplied melodic skeleton** — hum/pick a motif
(or take one from motif_catalog.json), the adapter renders it in corpus idiom. This is the
direct attack on "no iconic melodies": don't hope the model invents hooks, HAND it the hook.

Design points:
- Taps: all-24 with zero-init (the #56 lesson: restricting taps at TRAINING time inherits
  blowout anyway; keep install-everywhere/train-mid if we restrict at all).
- **The #56 meter-gaming risk applies with teeth**: onset control learned to fake onsets as
  HF clicks; melody control could fake contour as a ghost sine. Non-negotiable gates:
  disintegration_metrics.gate on every eval render + CE + the planned HF-drift-penalty loss
  arm (#53) as the mitigation experiment.
- Condition dropout: independent per-source (text vs melody) — the StemGen multi-source-CFG
  POOL item lands here for free and enables λ_text vs λ_melody at inference.
- Training pairs: (latent crop, its own lead stream) — teacher-forced reconstruction-style
  conditioning, same recipe as onset-envelope control. The 259-id hooky subset is the
  natural eval-prompt source, not the training filter (train on all 2,649).

## 3. Sequencing + cost

- **Now (CPU)**: targets prep script (melodies.jsonl → per-frame class arrays next to
  latents). ~minutes of compute.
- **#53 campaign riders (LUMI)**: Head A = one more head family in the LatCH sweep
  (GCD-hours). Head B = one sa3_control arm alongside the FiLM arms already planned
  (~same cost as an onset-control run). Both fit the existing #53 sbatch pattern — no new
  infrastructure.
- **Definition of first success**: Head A per-class F1 clears the bar and its z0-side
  hook stats correlate with the wav-side muscriptor metric on the same renders (r>0.7 on
  the pilot set). Head B: renders a catalog motif recognizably (muscriptor transcription
  of the render recovers the input contour ≥60% of frames) without tripping the
  disintegration gate. Kim's ear after both.

## 4. UX (Kim-approved direction, 2026-07-22 — "fold into our existing UI as the models
come available")

Discrete symbol × continuous knobs, matching the corpus structure (a single "melodic shape
continuum" axis is rejected: motif families are categorical; interpolating between them
crosses contours the corpus never produces):
1. **Style family picker** (full-on / sparse-progressive / psydub) — prompt/caption-side,
   ORTHOGONAL to shape; two pickers, never one.
2. **Shape picker: ~32 catalog cells** (top contour families by support), each with an
   audition preview rendered from its motif_catalog.json exemplars — chosen by ear.
3. **2-3 continuous sliders as LatCH targets**: hookness (repetition of best cell),
   pedal↔run balance; optionally range discipline.
4. **Advanced: bring-your-own 16-step contour cell** (Head B takes arbitrary streams).
5. Polish tier: 2-D shape map (PCA of motif features, 32 cells as anchors,
   click→snap/blend within family) — the honest version of "pick a number on the axis".
Sequencing: shape picker + hookness slider first (needs Heads A+B only); map + editor later.
UI planning stream runs ahead of model availability (separate plan doc); integration target
is the existing explorer (steering contract v2, per-slot LatCH config).

## 5. What NOT to do

No absolute-pitch conditioning (key-dependent, data-hungry, and the corpus says identity
lives in the contour); no phrase-level symbolic language model bolted on (the finding is
that repetition of a 1-2 beat cell IS the hook — a per-frame stream carries that); no
melody head on SAO-Small assumptions (SAME probes re-ranked everything before — train on
SA3-medium activations from the start).

## 6. BPM conditioner arm family (Kim direct 2026-07-22, via UX Q2)

Melody BPM becomes its own conditioner; mechanism decided empirically: (a) FiLM scalar
(existing sa3_control lane), (b) LatCH guidance on a tempo-family head, (c) **integer
conditioner fine-tuned into the model** — learned BPM embedding into the global-embed
pathway (SA1 per-second timing embeds are the lineage precedent; DoRA-scale fine-tune,
not full FT). Same eval for all three: rendered-BPM accuracy (madmom on renders) vs
requested, across 90-160 BPM; corpus BPM is tri-modal 135/140/145 so include off-mode
targets to test interpolation. Rider on #53 alongside Heads A/B.

## 7. Does training even HEAR melody? (Kim's question, 2026-07-22) — two mechanisms + probes

**M1 gradient share**: RF loss is MSE (quadratic in energy); leads are a small energy
fraction of the mix — same failure class as the PROVEN stereo-phase invisibility. SAME
represents melody well (chroma regressors trained in) but representation ≠ gradient
salience if chroma lives in low-variance latent directions.
**M2 conditional averaging** (suspected dominant): melody is the highest-entropy content
given a prompt; the velocity field predicts the conditional mean of many valid leads =
pitch smear; CFG amplifies mean-seeking. Pilot evidence: base model no-lead ≈ half of
renders despite 95% of training files having leads — it fails to COMMIT, not to know.
**Probes**: (P1) project corpus RF residuals onto LatCH-chroma directions → melody's
actual gradient fraction (CPU + existing dumps). (P2) hmr vs cfg{1,7,16} from the
stratified pilot — M2 predicts hmr falls with cfg; M1 predicts flat. (P3) Kim's
synthetic-MIDI timbre/latent probe (test_midis/, same day) → where melody lives in the
latent + linearity of encoding (16th-interleaving question).
**Fix map**: M1 → melody-weighted aux loss along contour-head directions (#56
probe-hacking caveat applies). M2 → Head B conditioning removes the averaged-over entropy
entirely — correct fix under EITHER mechanism, raising its priority.

## 8. §7-P3 RESULTS (v2 battery, 900 renders — latent_melody_analysis_v2/REPORT_v2.md)

**Encoder EXONERATED (Kim's falsifiability bar):** lone fifth-jump ≥91% frame-detectable
at ALL 20 BPMs × 3 timbres incl. pure sine (event-level ~100%); gentle decline toward slow
tempi is sustain-drift, not alignment failure. The melody bottleneck is downstream (DiT
training/sampling) — M1/M2 mechanisms stand, encoder is not a third.
**Head-design consequences (binding):** train on PATTERNS, never sweeps (sweep-derived
pitch atlas INVALID across register — MAE 11-12.5 st); supervise frames by TIME-OVERLAP,
never note-index (2fr/16th notes are onset+sustain microstates; readout still transfers
across 2x tempo at R² ~0.79 — one head serves all tempos); multi-timbre mandatory
(direction inconsistency is genuine timbre physics, sine-confirmed, cross-timbre cos 0.40);
REST is a distinct latent class (LDA 0.995) — keep it in the class set; probes should
LEARN their temporal filter (fixed high-pass helps sharp timbres, destroys sustained).
**Numbers that held:** superposition slope 0.924 [0.881,0.966]; melody subspace ~15-dim;
corpus melody share 9.3% [9.0,9.6], enrichment 1.61× — the M1 gradient-share case firmed.
**Softened vs v1:** LOTO pitch transfer 0.679 [0.55,0.78] over 10 timbres.
