# same_chroma readout/ceiling test — REPORT

**2026-08-11.** Question: how well does the trained `same_chroma` LatCH head READ the
384-d 3-band SAME chroma from clean SAME latents (z0) — a readout/ceiling test, forward
the head on t=0 latents and compare its prediction to ground truth. NOT a
steering/guidance test. Framed against the sibling melodic-CONTOUR "Head A", which hit
macro-F1 0.28 (chance 0.125) from raw mix z0 and was ruled representation-limited
(`eval/musicology/head_a_ceiling/REPORT.md`).

## HEADLINE VERDICT

**Yes — `same_chroma` reads bass/mid chroma very well from clean z0, is strongly
timbre-invariant in those bands, and correctly reconstructs the semitone content when
pooled/averaged. The air/treble band is a genuine, separate weak spot — but the failure
is register-content-limited (near-silent target energy), not head-limited: on material
that genuinely occupies the treble register (the chromatic sweep up to C8) the air band
reads strongly too (cos12 0.55-0.99).** A distinct, more surprising negative result:
frame-precise "which single pitch-class is loudest right now" (argmax) tracking under a
fast chromatic run is near/below chance, even where the whole-vector cosine agreement is
excellent -- the head/extractor read the aggregate harmonic content correctly but do not
resolve individual notes at 2-4 frames/note.

**Contrast with Head-A:** bass/mid cos12 ~ 0.79-0.86 (pooled, both time-avg and
per-frame) is a *categorically* different result than Head-A's ceiling. Head-A's 0.28
macro-F1 was compared against a chance floor of 0.125 (2.2x chance). Here the
comparable "chance" cosine between two independent 12-d energy vectors is ~0 (not a
literal classification chance level, but the natural null); pooled bass/mid readings sit
0.79-0.86 against that null -- an enormous, unambiguous effect size. **Chroma
(pitch-class energy, a SAME semantic regression target the encoder was explicitly
trained to make linearly decodable) is a usable latent-space readout where melodic
contour (interval class, not a direct SAME training target) was not.**

## Provenance

- Head: `stable-audio-3/latch_weights_sa3_medium/latch_sa3_same_chroma_best.pt`
  (in_channels=256, out_channels=384, dim=256, depth=4, **t_injection=adaln_zero**,
  loss_type=cosine, noise_schedule=rectified_flow, standardized=False,
  feature_name=same_chroma). Loaded via
  `stable_audio_3.models.latch.load_latch_from_checkpoint`; forwarded at **t=0** (clean
  z0, the RF "clean" convention) on **CPU** (SAO/.venv, no GPU contention).
- Pair sets: `eval/musicology/gm_timbre_pitch/{latents,midis,renders}` (480 pairs: 4
  frame-locked MIDIs [sweep/pat1/pat2/pat5] x 120 pitched GM programs, BPM
  161.4990234375, 16th==1 SAME frame) and
  `eval/musicology/test_midis_v2/{latents,renders}` + 118 root-level `.mid` files (900
  pairs: 19 patterns x {4 tempos, some register/gate/rest variants} x 10 GM timbres, +
  2 chromatic-sweep tempos x 10 timbres). Pairing was done by direct directory listing
  (not by hand-parsing the manifest's `files`/`sweeps` lists, which undercounted --
  118 latent stems matched to 118 root `.mid` files 1:1, 0 unmatched).
- Frame rate: FPS = 10.7666015625 Hz (SAME latent hop 4096 @ 44.1 kHz). Latent T and
  audio-GT T matched exactly (no resampling needed) on every pair checked --
  `compute_same_chroma`'s `align_to_latent=True` default (`ceil(n_samples/4096)`)
  reproduces the encoder's frame count.
- Ground truth: `compute_same_chroma` + `fold_to_12` from
  `mir-same-chroma/src/harmonic/same_chroma.py`, reused verbatim; `cos12`'s formula
  reused verbatim from `eval/chroma384_eval.py` (extended here with a per-frame variant,
  `cos12_perframe_mean`). Predicted 384-d head output reshaped band-major to (3,128,T)
  -- confirmed against `extract_same_chroma_targets.py`'s target construction
  (`np.einsum("bkc,ct->bkt", ...)` -> (3,128,T)) and
  `explorer_render_server.py`'s `compute_same_chroma(...).reshape(384, -1)` convention
  (band-major row-major reshape round-trips correctly).
- MIDI note GT: `mido`-based tick->second conversion (tempo-map aware), notes assigned
  to pitch-class bins per active frame and to a register band by MIDI pitch
  (bass <60/C4, air >=84/C6, else mid).
- Venvs: Stage A predict `SAO/.venv` (torch, CPU); Stage B score+report
  `/home/kim/Projects/mir/mir/bin/python` (librosa/essentia/mido/soundfile).
- Sanity check (guardrail, before the full sweep): `pat1__p000` (Acoustic Grand Piano)
  gave time-avg cos12 [bass 0.864, mid 0.858, air -0.694] -- sensible per the ~0.7-1.0
  bar for bass/mid; the negative air reading on a single piano file foreshadowed the
  register-content-limited pattern confirmed at scale below.
- Scored **1380/1380 pairs, 0 missing/failed.**

## Metric 1 -- Readout fidelity (head vs audio-GT, PRIMARY)

Pooled over all 1380 pairs, per band (time-averaged cos12 / mean per-frame cos12):

| band | time-avg mean (median) | per-frame mean (median) |
|---|---|---|
| bass | **0.815** (0.827) | **0.787** (0.799) |
| mid  | **0.861** (0.909) | **0.726** (0.797) |
| air  | 0.054 (0.009) | 0.003 (-0.030) |

By set: gm_timbre_pitch (n=480) bass 0.834/0.803, mid 0.866/0.629, air -0.028/-0.130.
test_midis_v2 (n=900) bass 0.805/0.778, mid 0.859/0.778, air 0.097/0.074.

**The air band is not uniformly dead -- it is content-starved.** All 19 test_midis_v2
patterns + gm's pat1/pat2/pat5 live in the E2-E4 register (well below the air band's
octave-9/~14 kHz-centered window), so the audio-GT air-band target is itself near-noise
there, and cosine against a near-noise target is unstable (mean pulled toward 0,
occasionally negative). On material that actually reaches the treble register the air
band reads strongly:

| pattern | bass timeavg | mid timeavg | air timeavg | air perframe |
|---|---|---|---|---|
| gm sweep (C2->C8, 120 programs) | 0.995 | 0.949 | 0.571 | 0.157 |
| test_midis_v2 sweep @161.5bpm (10 timbres) | 0.997 | 0.995 | 0.713 | 0.268 |
| test_midis_v2 sweep @80.75bpm (10 timbres) | 0.998 | 0.995 | 0.545 | 0.144 |
| pat14 (pat1 transposed to E4, closer to mid/air boundary) | 0.83-0.85 | 0.75-0.80 | **0.66-0.73** | -- |

Per-program breakdown (gm_timbre_pitch, mid-band time-avg cos12, pooled over
sweep/pat1/pat2/pat5):

- **Worst 10** (mean mid cos12): Reverse Cymbal -0.641, FX 6 (goblins) -0.449, Whistle
  -0.070, Pad 2 (warm) 0.025, Flute 0.635, Recorder 0.648, Contrabass 0.651, Tuba 0.704,
  Oboe 0.775, Drawbar Organ 0.782. **This list overlaps heavily with Head-A's own
  outlier programs** (Whistle, Pad 2 warm, and the FX/percussive-transient family also
  named in Head-A's ceiling report and the sibling gm_timbre_pitch pitch-geometry
  atlas's worst-transfer-programs list) -- narrow-formant sustained winds/strings and
  atonal FX/percussion timbres are the recurring hard cases across *every* melodic/
  harmonic latent-probe test run on this corpus so far.
- **Best 10**: Melodic Tom 0.993, Synth Drum 0.992, Timpani 0.985, Slap Bass 2 0.979,
  Overdriven Guitar 0.977, Orchestra Hit 0.976, Celesta 0.973, Lead 1 (square) 0.973,
  Taiko Drum 0.971, Guitar Harmonics 0.971. **Notably different axis from Head-A/the
  pitch-geometry atlas**, where percussive/transient timbres (Orchestra Hit especially,
  LOPO R^2 -0.57 in the pitch-geometry atlas) were the *worst* performers -- for chroma
  readout their broadband transient content saturates the filterbank cleanly and reads
  well, while it destroys pitch-geometry decoding. Chroma and contour/pitch-geometry
  have different, non-overlapping failure modes.

## Metric 2 -- Timbre invariance (gm_timbre_pitch, fixed pattern x 120 GM programs)

Mean pairwise cos12 of the time-averaged 12-d readout across all `C(120,2)` program
pairs, per band:

| pattern | bass | mid | air |
|---|---|---|---|
| pat1 | 0.998 | 0.833 | 0.199 |
| pat2 | 0.998 | 0.869 | 0.219 |
| pat5 | 0.999 | 0.890 | 0.261 |
| sweep | 1.000 | 0.921 | 0.482 |

**Bass is essentially perfectly timbre-invariant** (0.998-1.000 across every pattern);
mid is strongly invariant (0.83-0.92); air is weak-but-registers-content-limited (same
caveat as Metric 1 -- sweep, which visits the treble register, scores highest at 0.482).
Worst-agreement programs per pattern (mean pairwise sim to the other 119): mid-band --
Whistle, Reverse Cymbal, FX 6 (goblins), Pad 2 (warm) (again matching Head-A's outlier
set); air-band -- Slap Bass 2, Lead 2 (sawtooth), Synth Drum, Melodic Tom, and on the
sweep specifically Bassoon/English Horn/French Horn (narrow-formant orchestral winds).

## Metric 3 -- Pitch/note fidelity (head vs MIDI-derived GT)

Head-vs-MIDI cos12 (a note active in a frame contributes to its pitch-class bin,
register-split bass/mid/air by MIDI pitch), pooled:

| band | time-avg mean | n pairs w/ notes in band | per-frame mean |
|---|---|---|---|
| bass | 0.462 | 1300 | 0.280 |
| mid  | 0.673 | 380 | 0.201 |
| air  | 0.577 | 140 | 0.070 |

Lower than Metric 1 (as expected -- the binary MIDI on/off mask has no envelope/release
shaping and is a structurally harsher ground truth than the audio-derived target the
head was actually trained against), but clearly and consistently above 0 across every
band and both pair sets (gm: bass 0.526/mid 0.949/air 0.568; test_midis_v2: bass
0.425/mid 0.546/air 0.630) -- **the head is reading the actual notes, not just an
extractor artifact correlated with the audio-GT construction.**

## Metric 4 -- Transposition / register (chromatic sweeps)

**Negative/near-chance result, and a genuinely interesting one.** Per-note argmax
pitch-class accuracy (does the single loudest predicted pc match the MIDI note's true
pc) on the chromatic 8th-note sweeps (73 notes, 2-4 frames/note):

| set | n renders | argmax acc (overall bands) | argmax acc (register-matched band) | frame-to-frame shift-step agreement |
|---|---|---|---|---|
| test_midis_v2 sweeps (2 tempos x 10 timbres) | 20 | 0.168 | 0.150 | 0.040 |
| gm_timbre_pitch sweep (120 programs) | 120 | 0.140 | 0.121 | 0.031 |

Chance for a uniform-random 12-class argmax match is ~0.083 -- these numbers are *close
to or below* that floor (shift-step agreement, which asks whether the argmax advances by
exactly +1 semitone/step as the true chromatic run does, is **below** chance,
consistent with the predicted argmax being sticky/autocorrelated across frames rather
than genuinely hunting-and-tracking). This sits in sharp contrast with Metric 1's high
per-frame cosine on the very same sweep clips (bass 0.81-0.89, mid 0.45-0.53 per-frame).
**Diagnosis: the readout is strong at the whole-distribution level (does the full 12-d
energy shape track the note) but weak at single-bin argmax precision when notes change
faster than the extractor's own temporal resolution allows** -- the SAME chroma
extractor's analysis window (n_fft=8192 ~ 186 ms) is comparable to or longer than a
single sweep note's duration at 2 frames/note (~186 ms at bpm 161.5), so genuine
inter-note spectral smearing in the *ground-truth extractor itself* -- not just the
head -- likely caps what any readout could resolve at this rate. This is an
extractor-resolution ceiling, not obviously a head defect; a slower-note transposition
probe (test_midis_v2's non-sweep patterns move at 1 note/frame or slower) would
disambiguate but was out of scope here.

## Bonus -- register-gradient probe (pat1/pat2 vs their E2/E4-transposed siblings)

For 6 (pattern, timbre) probes, the **single dominant band stayed "mid" at all three
registers** (E2/E3/E4) -- expected, since the SAME chroma bands are broad overlapping
Gaussian octave windows (bass ctr=oct1/width1, mid ctr=oct5/width1.5, air
ctr=oct9/width1), not a hard partition, and E2-E4 (MIDI 40-64) sits well inside the
skirt of the mid window regardless. But the **relative cross-band energy gradient
tracks register correctly in every probe**: bass-band energy falls and air-band energy
rises monotonically E2->E3->E4 (e.g. sawlead/pat1: bass 18.4->13.5->10.1, air
15.6->20.8->27.6). The head encodes register as a continuous cross-band tilt, matching
the training target's own construction, rather than a discrete band switch.

## Caveats / things that didn't pair or need a second look

- 0 pairs failed to pair or score (1380/1380 clean).
- Air-band numbers throughout should be read with the register-content caveat above --
  do not quote Metric 1/2's pooled air numbers without the sweep/register-content
  breakdown; they are misleading in isolation.
- Metric 4's near/below-chance argmax result is a temporal-resolution finding, not
  re-tested against the slower non-sweep patterns to confirm the extractor-window
  hypothesis -- flagged, not chased (guardrail: stay in scope).
- Metric 3's MIDI-GT n varies by band (bass always present; mid/air only when a pattern's
  register reaches that band) -- per-band means are not on equal footing, noted in the
  table above.

## Files

- `predict_head.py` -- Stage A (SAO/.venv, CPU): forwards the head at t=0 on every z0
  latent in both pair sets; predicted (3,128,T) chroma cached to
  `/tmp/.../scratchpad/same_chroma_readout/predicted/{set}/{stem}.npy` (session
  scratch, not checked in -- regenerate via this script, ~10 min for 1380 files).
- `score_and_report.py` -- Stage B (mir venv): all four metrics + bonus register probe;
  writes `results.json`.
- `results.json` -- full numbers: provenance, metric1 (pooled/by-set/by-pattern/
  per-program worst10+best10), metric2 (per-pattern per-band, worst10 per band),
  metric3 (pooled/by-set), metric4 (per-pair rows + summaries, both sweep sets),
  bonus register probe.
