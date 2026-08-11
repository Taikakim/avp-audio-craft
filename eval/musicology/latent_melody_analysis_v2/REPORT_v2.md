# SAME melody encoding, v2 — 11x data, CIs, and four new axes (tempo / register / gate / rest) + the BPM-phase probe

**Date:** 2026-07-22 · **Analysis:** CONTINUITY (melody-encoding study v2; extends v1, does not replace it)
**Inputs:** `eval/musicology/test_midis_v2/` — 19 one-bar patterns (6 v1-verbatim + 13 new) × 4 tempos
(two frame-LOCK points 161.499 / 80.7495 BPM + two drift probes 143 / 150) × 10 GM timbres, chromatic
C2→C8 sweeps at both locks × 10 timbres, **plus the BPM-phase addendum** (pat1 + pat5 × 20 BPMs ×
{pure-numpy **sine**, sawlead, piano}) = **900 renders → 900 z0 latents** (`test_midis_v2/latents/`,
fp16 [256,T]; encoder `encode_test_midis_v2.py`, medium-base pretransform only).
**Code:** `analyze_melody_encoding_v2.py` (stages 1–9, each re-runnable: `… <stage>`.)
**Numbers:** `results_v2.json` · intermediates `stage1_pitch_atlas_v2.npz`, `stage3_fifthjump_v2.npz`,
`stage4_subspaces_v2.npz`. v1 outputs untouched in `../latent_melody_analysis/`.
Pipeline validity: v2 re-renders of v1 files give latent corr **0.9997** with v1 latents; locked pat2
E/G d′ = 6.3 (v1 range 6–8). Bootstrap CIs are 95% percentile unless noted; all periodicity analyses
high-passed at 2 Hz (v1 hazard: 0.4–1.3 Hz pitch-independent latent oscillation).

---

## Headline numbers with CIs (and what moved vs v1)

| Quantity | v1 (N small) | **v2 (11x)** | 95% CI | Verdict |
|---|---|---|---|---|
| Interleaving slope (boundary-frame superposition) | 0.91–1.06 (4/5 timbres) | **0.924** (140 cells: 7 patterns × 2 drift tempos × 10 timbres) | [0.881, 0.966] | **HELD.** Linear superposition, no snapping (snap margins > 0 in all 140 cells) |
| LOTO pitch-transfer R² (pooled decoder, held-out timbre) | 0.74 (5 timbres) | **0.679** (10 timbres) | [0.55, 0.78] | HELD but softened — range is huge (0.25 flute … 0.90 synthbrass) |
| Melody-subspace dim (n90, timbre-avg trajectories) | ~15 | **15** (19 patterns; v1-replica also 15) | [9, 17] (boot pats×timbres) | **HELD exactly** |
| Melody variance fraction (renders) | 19.7% | **12.8%** (19 pats × 10 timbres) | [5.1%, 20.5%] (jackknife timbres) | Condition-sensitive: v1-replica (6 pats × 5 timbres) reproduces **19.8%** — the fraction shrinks as timbre diversity grows |
| Corpus melody-subspace share / enrichment | 8.5% / 1.45× (22 files) | **9.3% / 1.61×** (60 files) | share [9.0, 9.6]% · enrich [1.56, 1.68] | **HELD/improved** — RF "hears" melody at ~1/11 of variance budget |
| Fifth-jump LDA detectability (locked) | 100% all 5 timbres | 100% for 9/10, flute 93% | min 0.93 | HELD (flute = slow attack, the known failure mode) |
| Jump-direction cross-timbre cosine | 0.27 | **0.275** (10 timbres, 45 pairs) | [0.244, 0.306] | **HELD precisely** — and the addendum shows it's genuine, not soundfont artifact (below) |

## v1 conclusions that FLIPPED or need rewording with more data

1. **"Zero channels reach R² 0.5" is FALSE for 3 of the 5 new timbres.** Flute has **15**
   channels with single-channel pitch R² > 0.5 (best 0.68), synthbrass 6 (best 0.64),
   epiano 5 (best 0.65). No channel is shared across timbres (consensus channels stay
   weak), so the *architecture* conclusion (full-width linear probe, no channel
   selection) stands — but "no pitch channel exists" must be stated per-timbre.
2. **The sweep-derived pitch atlas does NOT transfer to musical patterns across register**
   (new stage 6): decoding pat1/pat2 transposed to E2/E3/E4 with the pooled sweep decoder
   gives MAE **11–12.5 semitones** and correct E2<E3<E4 ordering in only **40–60%** of
   timbres (E4 separates; E2 vs E3 often collapses or inverts). v1's arp validation
   (corr 0.54–0.68 for sharp attacks) was the optimistic case. **A melodic head must be
   trained on patterns, not sweeps** — isolated-note atlases mis-calibrate on context.
   (v1's related caveat also hardened: sweep-decoder frame-tracking of the pat3 arp now
   *fails* for flute (−0.63), churchorgan (−0.45), and is weak for epiano/vibraphone/strings.)
3. **LOTO 0.74 was a 5-timbre optimism**: with 10 timbres the mean drops to 0.679 and the
   spread [0.25–0.90] shows the "timbre-invariant pitch subspace" carries some timbres
   (synthbass/brass, strings) far better than others (flute, vibraphone).
4. **Melody variance fraction is not a constant of the codec** — it's 19.8% under v1's
   exact conditions (replicated) but 12.8% under 19 patterns × 10 timbres. Quote the
   corpus-projected number instead (9.3%, stable CI): that one *rose* slightly with a
   bigger corpus sample and a better-estimated subspace.

## New axis 1 — TEMPO COVARIANCE (lock 2 fr/16th vs lock 1 fr/16th)

**Verdict: frame-absolute at the frame level, tempo-covariant at the readout level.**
- The 2-frames-per-16th trajectory is **not** a stretched copy of the 1-frame code:
  same-pattern cross-tempo trajectory cosine is only **0.271** CI [0.229, 0.310]
  (crossed-pattern control 0.003 — the similarity is real but weak).
- The two frames of a note are *different microstates*: the **onset half** resembles the
  1-frame code (cos 0.38), the **sustain half** doesn't (cos 0.03). A frame encodes
  "what the audio did in my 93 ms", not "which note am I in".
- BUT the melody **subspace** is shared: lock-1 basis captures **75.6%** of lock-2
  trajectory variance (random basis 5.0%); principal angles first-8 = 13–34°.
- And the pitch **readout** transfers: sweep decoder trained at lock 1 decodes the lock-2
  sweep at **R² 0.796** (reverse 0.783) with no retraining.
**Implication:** melodic-LatCH supervision can share one pitch readout across tempos, but
frame-level targets must be computed from time-overlap (as v1 recommended), never from
"note index"; and 2-frame notes should supervise onset and sustain frames separately.

## New axis 2 — REGISTER (E2/E3/E4)

Covered in flip #2 above: the sweep atlas is register-valid only locally around where the
pattern content sits; absolute pitch level from an isolated-note atlas is off by ~1 octave
on average. Within-register relative structure (E vs G alternation direction) survives.

## New axis 3 — GATE (staccato 50% vs default 80% vs legato 100%, pat1@E3)

Gate is encoded, mostly where you'd expect — in the sustain half:
- At lock 2, second-half-frame norm ratio (vs onset frame): gate50 **0.921** vs gate100
  **0.982** — staccato's silent half-cell is visibly lower-energy but nowhere near zero
  (release + reverbless FluidR3 tails).
- LDA staccato-vs-legato: **0.979** on second frames, 0.937 on onset frames (onset frames
  also differ — a legato context changes the attack's neighborhood via the encoder's
  receptive field).
- At lock 1 (1 fr/16th) the three gates are centroid-separated by only 0.22–0.49 of
  within-class scatter — gate is a *sub-frame* property that mostly washes out at 1
  frame/note. Onset-transient vs sustain content is separable at 2 frames/note, not at 1.

## New axis 4 — REST handling (pat19, 8ths with beat-3 rest)

**Silence is a distinct latent region, not merely low norm.** Rest frames: norm ratio vs
note frames **0.84** (moderately lower, far from 0); LDA rest-vs-note **0.995**; the rest
centroid sits **1.2** scatter-units from the true digital-silence code (estimated from
globally-padded sine tails) vs **2.53** from the note centroid. So rests are encoded as
"near-silence with room tone/release color" — a melody head should treat rest as its own
class, not as a low-energy threshold.

## ADDENDUM — BPM-phase robustness of single-note-change detection (Kim's falsifiability bar)

Setup: pat5 (fifth-jump) + pat1 (pseudo-jump control) at **20 BPMs** (16th/frame ratio
0.924→1.903, low-discrepancy, ratios 1.0 and 1.5 pinned) × {pure sine, sawlead, piano}.
Frame labels from exact time overlap; detectability = balanced LDA accuracy, leave-one-bar-out CV.

```
ratio(fr/16th)  bpm      CV-acc  in-acc  zdist   |bar=CV-acc   (sine)
0.92400        174.78   1.000   1.000   1.79    |########################################
1.00000        161.50   1.000   1.000   12.09   |########################################
1.02894        156.96   0.990   1.000   1.81    |#######################################
1.08741        148.52   1.000   1.000   1.84    |########################################
1.13388        142.43   0.990   0.990   1.86    |#######################################
1.18035        136.82   0.990   0.991   1.87    |#######################################
1.23881        130.37   0.981   0.990   1.89    |######################################
1.28528        125.65   0.981   0.991   1.83    |######################################
1.34375        120.19   1.000   1.000   2.15    |########################################
1.39022        116.17   0.965   0.973   1.86    |#####################################
1.43669        112.41   1.000   1.000   1.89    |########################################
1.50000        107.67   1.000   1.000   4.03    |########################################
1.54163        104.76   0.943   0.991   1.96    |###################################
1.58810        101.69   0.955   0.973   1.88    |####################################
1.64657        98.08    0.954   0.963   1.90    |####################################
1.69304        95.39    0.963   0.981   1.92    |#####################################
1.75150        92.21    0.914   0.914   1.85    |#################################
1.79797        89.82    0.946   0.955   1.92    |####################################
1.84444        87.56    0.972   0.981   1.94    |######################################
1.90291        84.87    0.946   0.946   1.88    |####################################
```

**Verdicts:**
1. **The encoder is NOT the melody bottleneck at any tested phase.** A lone fifth-jump is
   frame-level detectable at **≥ 91% balanced accuracy at all 20 BPMs and all 3 timbres**
   (sine min 0.914, sawlead 0.948, piano 0.931; in-sample ≥ 0.91 everywhere). The pat1
   pseudo-jump control sits at chance (CV ≈ 0.2–0.6). Since every bar contributes 2–4 jump
   frames, *event-level* detection (majority vote per bar) is effectively 100% at every BPM.
2. **But it is not perfectly flat either**: detectability declines gently and consistently
   with more frames per 16th (corr(ratio, CV-acc) = −0.74 sine / −0.59 saw / −0.64 piano;
   worst common point ratio ≈ 1.75). Slower tempo = longer sustained notes = more within-class
   latent drift (the 0.4–1.3 Hz oscillation lives inside the class scatter), not a boundary-
   alignment failure — the minima do not sit at half-integer phase ratios.
3. **Frame-lock is a superpower, not a requirement**: at exactly 1 frame/16th the jump
   z-distance explodes to **12.1** (vs ~1.9 elsewhere; 4.0 at the 1.5 lock, 2.15 at the
   rational 43/32). Locked grids give order-of-magnitude cleaner class statistics — keep
   using 161.499 BPM for probe *training*, but expect the ~1.9 z-dist regime in the wild.
4. **v1's "jump direction is timbre-specific (cos 0.27)" was genuine encoding behavior,
   not a soundfont artifact.** With soundfont confounds removed: within-timbre direction
   is highly stable across BPMs (sine 0.915 CI [0.903, 0.926]; sawlead 0.867; piano 0.771),
   while cross-timbre same-BPM cosine is **0.401** CI [0.361, 0.440] even with the
   mathematically clean sine among the timbres. Direction variability is timbre physics,
   confirming: multi-timbre training is mandatory for any jump/change detector.

## Interleaving details worth keeping (stage 2)

- Slope by interval: octave bounce 0.979, fifth ping 0.969, whole-tone 0.944, pat2-E4
  0.997 vs pat2-E2 0.824, fourth 0.854 — larger intervals/higher registers mix more
  cleanly linearly. By timbre: churchorgan 0.62 (still the outlier), flute 0.81, others 0.90–1.08.
- Boundary-frame mix readout stays noisy (R² 0.379 CI [0.34, 0.41]) — same v1 conclusion:
  superposition unbiased, per-frame witness unreliable.
- High-passing (>2 Hz) before the readout **helps sharp timbres a lot** (piano boundary R²
  0.56→0.75, epiano 0.79, vibraphone 0.62) and **destroys sustained timbres** (strings
  0.02, organ 0.01 — their pitch axis itself is slow). A melody probe should learn its own
  temporal filter, not apply a global high-pass.

## Method notes / caveats

- 150 BPM gets 29 bars (not the sketched 30): 30 bars = 516.8 frames > the 512-frame cap.
- The task sketch said "18 patterns / 12 new" but enumerates 13 new; all 13 are included
  (19 patterns total, 900 renders vs the sketched ~740).
- CV-fold design at drifting tempos is a real trap: bar-start phase precesses, so naive
  even/odd-bar folds put different sub-frame phases in train vs test (false "phase
  failure" at 21.5 fr/bar). Leave-one-bar-out is phase-fair; that's what stage 9 reports.
- fp16 encode; monophonic; FluidR3 GM (5 ms-ramp numpy sine for the clean reference).
- Encode-time gotcha for reuse: all 900 wavs were zero-padded to one global length for
  uniform GPU batching (~1.1 s/file, one lock window) — trailing-silence latent frames in
  files shorter than the max are *genuine silence codes* (stage 8 exploits this).
