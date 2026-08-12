# Masked Diffusion Enables Coherent Beat Tracking (2608.04624)

*Project-POV abstract, CONTINUITY 2026-08-12 (deep-read, full 8pp). Foscarin, Korzeniowski, Vogl
(**Moises AI**), ISMIR 2026. Open code: github.com/fosfrancesco/md_beat_this (builds on Beat This, open).
Kim surfaced it mid-thread as we were about to build features on the madmom downbeat grid — and it lands
directly on that.*

## What it contains
Diagnoses why NN beat trackers emit **incoherent** outputs — consecutive downbeats, erratic tempo
doubling/halving — *even when such patterns aren't in the training data*. Root-cause hypothesis: beat
tracking has **multiple plausible valid outputs** (different metrical levels, alternative beat phases), and
a **one-step** frame-wise NN is forced to predict a single frame-map that ends up an **invalid MIXTURE of
competing interpretations**. Heavy post-processing (the Dynamic Bayesian Network, DBN) masks the symptom
with rigid rules but doesn't address the cause, and can't handle complex/ changing time signatures.
- **Fix = a Masked Diffusion Model (MDM).** The model takes audio **plus a partially-revealed output**
  (some beats/downbeats known) and iteratively reveals the rest, so early steps **commit to ONE valid
  interpretation** and the remainder is filled **coherently** with it. Frame-wise encoding kept (not
  tokenised); ~25M params; Beat This RoFormer backbone.
- Three beat-specific MDM modifications: **independent per-channel masking** (beat vs downbeat masked with
  separate ratios — they're ~90:1 imbalanced and on different scales), a **balanced unmasking schedule**
  (split the reveal budget between predicted positives/negatives so inference matches training), and
  **peak-picking between inference steps** (suppress adjacent-frame double-reveals; enforce every downbeat
  is also a beat — a *small* universally-valid rule set, unlike the DBN's rigid one).
- **Results:** big gains on CMLt/AMLt (the tempo-coherence-sensitive metrics), matches/beats DBN systems
  *without* a DBN. Coherence heuristics over 8 inference steps: **consecutive downbeats 0.25 → 0.02**, **tempo
  doubling/halving 0.75 → 0.119**. The non-diffusion ablation is worse even at 1 step → the MDM *training
  objective* helps beyond enabling iteration (partial-masking reduces training "confusion" from conflicting
  metrical levels). Explicitly: findings **generalise to other beat trackers and other MIR tasks with the
  multiple-valid-outputs problem — chord recognition, structure segmentation.**

## What this gives us / what stays ours
- **IMMEDIATE, load-bearing: it vets the downbeat-grid plan before we build on it.** Kim just proposed
  madmom downbeats ÷even as the repetition PERIOD + note-division grid + metrical-phase feature, with the
  caution "assumes a correct bar-lock, spot-check." This paper *formalises that caution*: madmom-class (and
  even Beat This) trackers demonstrably emit incoherent downbeats/tempo. So our whole-track madmom grid may
  carry consecutive-downbeat / tempo-halving errors that would silently corrupt any period we derive. **The
  cheap, immediate win = adopt their two coherence heuristics** (consecutive-downbeat count; inter-beat-
  interval doubling/halving rate) as a **grid-trust screen** over our existing madmom activations — flag the
  tracks whose grid is untrustworthy *before* the repetition-detector / note-division / negative-space-period
  features rely on it. No model needed, ~10 lines on data we already have.
- **CONCEPTUAL, high: "one-step model → invalid mixture of multiple valid interpretations" is our loop /
  long-structure family.** The exact failure they name (a single forward can't commit to one coherent global
  interpretation, so it blends incompatible ones) rhymes with our a2a loop-collapse and long-form structure
  gap, and the fix — **commit to a coherent global structure early, then fill coherently** — is the SAME
  mechanism our knowledge.md already circles: DiffRhythm2 block-flow, SongBloom AR-sketch, "a learned coarse
  sketch is the anti-loop mechanism," InfiniteAudio FIFO. MDM is another instance, and the cleanest *stated*
  diagnosis of why one-shot structured prediction goes incoherent.
- **FUTURE / paradigm: MDM = the coherent-DISCRETE-stream extractor.** We're a continuous-latent RF shop, so
  this doesn't port to SA3 *generation*. But for pulling a **coherent discrete structured descriptor from
  audio** — beat grid, chord sequence, structure/segment labels, or a **discretised gate/movement stream** —
  iterative masked-diffusion-with-partial-conditioning is a strong tool, and the discrete-sequence complement
  to W's discretisation gate (2201.02715 HSMM). Its **partial-output conditioning** ("fix some positions, let
  the model complete the rest") is also the analysis-side twin of SA3's inpainting/local_add_cond — a general
  controllable-structured-prediction pattern.
- **Chord-recognition angle for the tonal thread:** the authors flag chord recognition as another
  multiple-valid-outputs task. Our `chords` field (input to the score-network tonal-region idea) suffers
  exactly the enharmonic/functional ambiguity Rohrmeier's grammar flagged — a coherence-aware chord tracker
  would give cleaner input there. Second-wave.
- **STAYS OURS / caveats:** analysis model, not generation; we don't have their weights (Kim), but code +
  the Beat This base are **open** → runnable/adaptable if we ever want a SOTA-coherent grid corpus-wide
  (~25M params, cheap). Trained/tested on GTZAN-style pop/rock — **goa is 4/4 with a hammering kick, the EASY
  case for beat tracking**, so our grid is probably *more* coherent than their hard examples; the coherence
  screen may flag few goa tracks, but that's a measurement worth having, not a reason to skip it. The MDM
  paradigm is discrete-sequence; our generation stays continuous RF.

**knowledge.md row** (hand to F): *Masked Diffusion Enables Coherent Beat Tracking (2608.04624, Foscarin/
Korzeniowski/Vogl, Moises AI, ISMIR'26; open code md_beat_this) — one-step NN beat trackers emit incoherent
outputs (consecutive downbeats, tempo halving/doubling) because the task has MULTIPLE valid interpretations
and a single forward predicts an invalid MIXTURE; fix = masked-diffusion model that accepts audio + partial
output and iteratively completes ONE coherent interpretation (indep per-channel masking, balanced unmasking,
inter-step peak-picking); beats/matches DBN without a DBN, consec-downbeats 0.25→0.02, tempo-halving
0.75→0.119. FOR US: (1) IMMEDIATE — vets Kim's madmom-downbeats-÷even grid plan: adopt their 2 coherence
heuristics (consec-downbeat count, IBI doubling/halving) as a cheap grid-trust SCREEN over our existing
whole-track madmom activations before the repetition-period/note-division/negative-space-period features rely
on it; (2) CONCEPTUAL — "one-step → invalid mixture of valid interpretations, fix by commit-early-then-fill"
is our loop-collapse/long-structure family (same mechanism as DiffRhythm2/SongBloom/sketch); (3) PARADIGM —
MDM = coherent-discrete-stream extractor (beat/chord/structure/discretised-gate), discrete-sequence complement
to the 2201.02715 HSMM discretisation gate, partial-output conditioning = analysis twin of SA3 inpainting.
Caveats: analysis not generation, discrete-seq not continuous-RF, no weights but open code, goa is the easy
beat-tracking case so few grids may flag.*
