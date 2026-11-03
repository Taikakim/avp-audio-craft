<!--
help-pane: on
DRAFT 2026-11-03, round 1 (CONTINUITY, directing). "Melody in Stable Audio 3: a field guide". Same shape as the Muon guide: neutral tone, every number from a
record, what we know and do not know kept apart.
Inputs: evidence dossiers docs/melody-hunt/A-substrate.md, B-guidance.md, C-conditioners.md, D-meters.md, E-literature.md (research agents, with file:line sources), and
F-team-notes.md (WINTERMUTE, THE-FINN). docs/melody-hunt/README.md maps each section of this guide to its dossier and experiment ids. The public text carries no ids, paths or corpus names.
Open before publishing:
  1. Round 1 fact check applied (docs/melody-hunt/G-factcheck.md: 14 wrong, 25 imprecise, 4 unsourced, against about 195 OK). Project review should decide whether the post may disclose what it implies about training on commercial genre music. A strength grid (eval/d15_strength.py) runs tonight, about 21:30, then W runs invented melodies with the stream in both branches, a second seed and EMA. Section 7 and these section 10 rows may close: re-read before publishing. WINTERMUTE's review of its own results applied (F-team-notes.md); it did not check other sections or the literature. Awaiting GHOST-NOTE.
  2. Nobody has listened to most of what this reports. Section 7's result in particular needs ears before it is presented as more than a measurement.
  3. Figures and audio: none yet. Candidates: gain ladder, speed limit, the pianoroll arms, the before and after of the CFG fix.
  4. Review by WINTERMUTE and GHOST-NOTE, whose results these mostly are.
Do not publish without project review.
-->

# Melody in Stable Audio 3: a field guide

For most of 2026 we have been trying to find melody in Stable Audio 3 (SA3) and to get a grip on it. The work has come to resemble cryptozoology: many sightings, blurred footage, a few famous pictures later shown to be a log, and a recent one that may be the animal. This guide lists every method we used to look, what each one found, which sightings were later debunked and by what, and what we still cannot see. It covers the latent, inference-time guidance with chroma and pitch heads, and trained conditioners (morph, contour and pianoroll).

Our evidence comes from one genre (goa trance and neighbours), mostly one 16 GB GPU, and meters that have often been wrong. We say where it is thin. **MEASURED** means a meter said so. **HEARD** means a person listened. Most recent results are measured only.

## Summary

- **The melody is in the latent.** Pitch is linearly readable from SAME latents, and a one-semitone change is a large event there. That rests on synthetic notes and one real mix, but section 7 shows the system can express notes when told to, so the autoencoder is not the main obstacle (section 2).
- **We do not know how much melody our models produce.** A headline number here, 32% to 84% of renders with "no lead" against 5% in the corpus, turned out while writing this guide to be mostly a meter artefact: the threshold is 40 notes, on 20 s renders and on 380 s corpus crops. Cut to 20 s, about 60% of the corpus also reads "no lead" (section 3).
- **Guidance moves harmony and slow pitch direction, not notes.** A retrained chroma head reaches at gain 512 what the production head reaches at 6144 to 8192, and follows transposition. A pitch head can make a whole clip rise or fall. It does not follow a contour faster than about a 10 s period (sections 4 and 5).
- **The morph conditioner, as trained, does not follow its contour,** under a meter that passes its own positive control (section 6).
- **A pianoroll conditioner does follow notes.** An unchanged checkpoint from August plays melodies invented for the test, with the top line on the fed pitch 67% of the time, once classifier-free guidance (CFG) scales the note stream. Two independent meters agree on those clips. Nobody has listened yet (section 7).
- **That fix is close to textbook.** The ControlNet paper discusses the choice in 2023. We had a control stream in both CFG branches, and evaluations through that inlet almost certainly understated the control until November (sections 7 and 9).
- **Several headline nulls were instrument failures, so a null here is not a finding until the meter is audited.** Others survived the audit. Section 3 lists our main instruments and what fooled us, in both directions.
- **There is no melody verdict from ears in the loop.** Our rating interface has no melody question, and no blind listening test on melody exists (section 10).

## 1. What we are looking for

"Melody" turned out to be several things, and most of our confusion came from a meter that could see one while we claimed another. Any claim should say which it means:

1. **Key:** the render adopts the pitch classes. Chroma sees this.
2. **Pitch set:** which notes occur, regardless of when.
3. **Placement:** those notes at those moments. Transcription sees this.
4. **Contour:** the shape of the line, up and down, regardless of absolute pitch.

Our corpus adds its own twist. In a transcription study of goa tracks, a rolling 16th-note pedal on one note appears in 91% of files, and the "melody" is typically that pedal plus short cells of 1 to 3 notes from about six interval families. What makes a track hooky is repetition: in the top decile of a repetition measure the best motif repeats 56 times per crop (median), and in the bottom decile, zero. Length does not seem to matter. This rests on a skyline (highest note per slot) taken from full-mix transcription, so it is an estimate. If the identity of a goa riff is largely repetition, accents and filter movement, then pitch-based measures can only ever see part of it.

## 2. Is it in the latent?

**Yes, in a specific sense.** MEASURED, mostly on synthetic notes.

| What | Result | Note |
|---|---|---|
| Pitch from the latent, linear (ridge), synthetic | R² 0.86 to 0.97 at full width; 0.679 [0.55, 0.78] leaving one timbre out | About 15 dimensions; no single pitch channel |
| Native chroma readout | 384 values: three bands around 55 Hz, 880 Hz and 14 kHz, 128 bins each | Trained into SAME by design |
| One semitone in a real mix | 12.7 times the size of the change from MP3 at 256 kbps | One pop vocal, one song |
| Size of the change by interval, single notes | A semitone is 0.94 of a fifth | The size says "a note changed", not by how much |
| Register | Correlation 0.51 (linear), 0.56 (MLP); error 6.7 and 6.4 semitones. Our notes put guessing the mean at 8.05, a figure we could not regenerate | Coarse. First reading was a broken script |
| Melody subspace share of latent variance | 9.3% [9.0, 9.6], 1.61 times its share of dimensions | A variance share, not a gradient share |
| Contour, per frame, from a mix latent | Balanced accuracy 0.28, chance 0.125; DiT activations do not lift it | Labels are noisy transcription skylines |

What this does not show: the "melody band" reading. The air band scored a matched-track chroma of 0.918 after demeaning, and it was called the melody band. A frame shuffle, on a per-window version of the metric, later showed that 0.52 of the air band's matched-over-null gap is a static fingerprint of the track rather than a line moving in time (0.55 mid, 0.60 bass). It is the strongest of the three bands, and that is as far as it goes.

The autoencoder does cost something: SAME-decoded audio transcribes at a median F1 of 0.738 against the original. That frames every F1 below.

Two further facts shaped the thinking. The latent is highly anisotropic (786 times between its directions), with the melody subspace in the quiet part, and the base model under-recovers low-variance directions by 8.3 times at sigma 0.2 (one measurement each: 220 files, 48 crops). Secondly, melody and rhythm do not separate by noise level on the base model: in an SDEdit test all features, including phase, chroma and rhythm, fell together between start noise 0.4 and 0.6 (240 clips, one prompt).

### When and where does it form?

Less is known here than our documents suggest.

- **By noise level:** we have a curve of how recoverable the melody subspace is at each noise level, but two versions disagree at t = 0.95: 0.011 (2 crops) and 0.207 (48 crops). The 48-crop curve has no "window". It also describes what the model could recover, not when its own sampling settles on a melody. That has not been measured.
- **By update size:** melody does not form in a few decisive steps, as far as we can tell. Sampling updates are heavy-tailed everywhere, and the melody subspace (excess kurtosis 24.5, interval 15.9 to 35.8) looks like a random subspace of the same size (23.0, interval 16.8 to 27.3), higher in 23 of 42 clips. Without that null it would have read as a discovery.
- **By depth:** nothing in our records places melody at a particular DiT block. The only per-block profile is for contour labels. It peaks mid-stack at 0.27 from 0.19 at the input, and never beats the latent's 0.28.

### Does fine-tuning change it?

We do not know in any controlled way. The closest evidence is by ear. A training loss that puts extra weight on the melody subspace (K = 5, the third-generation basis) was liked: "the subspace stuff really seems to work", with "the most distinct melody" on one arm, at a cost in kick and bass. Meters only faintly agree (generated melody energy 0.029 vs 0.023 to 0.025, spread 0.011, though the higher figure comes from a run eight times longer), and the best K changes between readouts. CFG may also matter: repetition falls from cfg 7 to 16 in 8 of 10 model families while pedal occupancy rises, though this comparison is partly unpaired and the measure is empty on renders it reads as having no lead (see section 3).

## 3. The meters

Every section below depends on one of these, so they come first. "Positive" and "negative" are the scores of a known-good and a known-bad arm. The gap between them is the meter's dynamic range.

| Meter | Sees | Blind to | Positive | Negative | Trust |
|---|---|---|---|---|---|
| Raw chroma cosine | Key and harmonic bed | Tune vs key, timing | None on goa | Matched 0.997, null 0.995 | Do not use alone |
| Demeaned chroma with nulls | Track-specific chroma | Timing, fingerprint | Air 0.526 per-window (0.918 demeaned) | Shuffled 0.401, null 0.266 | Identity yes, melody no |
| Change in chroma vs unguided | Steering strength | Melody; bugs in target or sampler | Transposed audio 84/84 | Unsteered baseline, 0 by construction | Good, relative |
| MuScriptor transcription, F1 | Notes in time | Legato, stems; it may have made the targets; no goa ground truth | F1 0.653 fed, 0.609 source crop | 0.045 no stream (0.094 foreign, August run) | Highest, with arms; we have not read its paper closely |
| Melodia pitch tracking | Dominant line | Notes; depends on input length (52% frame agreement) | r 0.999 synthetic | -0.15 to 0 other line | Good for slow shape |
| Pitch-curve correlation | Whole-line shape | Note detail | Own +0.431 | Foreign -0.066 | Medium |
| K&P contour symbols, exact | Rank-order shape | Survives no extractor error | Own 0.13 to 0.146 | Wrong stem 0.08; renders at 0.151 beat the positive | Not usable exactly |
| MERIT melody similarity | Learned similarity | Goa vs goa saturates | Self 1.000 | Different refs 0.611 | Low |
| Pitch-blind onset timing | Onset alignment | Pitch, content | 0.795 to 1.000 for all arms | The same | Do not use |
| Audiobox PQ and CE | Production, enjoyment | Melody (lead vs no lead: d -0.10 and +0.22) | n/a | n/a | Quality only |
| Hook metrics | Motif repetition of a lead | Short clips: "no lead" is a fixed 40 notes | Top decile 56 repeats | n/a | Descriptive; not comparable across lengths |
| Disintegration gate | Buzz, drift | Melody | n/a | n/a | Necessary, not sufficient |
| Essentia `melodic` tag | A mood label | Notes | n/a | n/a | Low |
| Synthetic MIDI and bungee shifts | Known answers | Real arrangements | r 0.999; 84/84 | n/a | High, as a ceiling |

### How we were fooled

These are the turnarounds, in order. Nulls were often meter failures, and we learned to distrust them. But about a third of this list went the other way: a meter that agreed with us when it should not have.

| When | What it said | What it turned out to be |
|---|---|---|
| June | Reference adapter "works", twice, by chroma correlation | A collapsed adapter still scored about 0.9 |
| June | Two best energy heads "dead" | Wrong MERT layer. The same proxy called the `hpcp` chroma head dead; it is blind to harmony |
| July | An ambient drone with low-volume hats scored 12.9 onsets per second | An ear caught it in seconds. The rule since: numbers are instruments, audition is the verdict |
| July | Chroma guidance cannot turn a melody (0 of 12) | Real, but with a much weaker head than a later one; see section 4 |
| August | Air band 0.918 taken as melody | About half is a static fingerprint |
| August | Pianoroll: true minus shuffled +0.022, "follows pitch, loose on timing" | Shuffling keeps the key, so chroma could not see it. Transcription gave +0.100, 6 of 6 |
| August | Register is not in the latent (0.214, error 66 semitones) | The script raised an error on every variant. Fixed: 0.51 to 0.56, error 6.4 to 6.7 |
| August | "Timing does not transfer" | The timing meter read 0.795 to 1.000 on every arm, foreign included |
| September | Morph follows at gain 2, MERIT +0.0247, p = 7.7e-05 | The foreign arm rose more. A style shift |
| September | PQ and CE should separate melodic from non-melodic renders | Lead vs no lead makes almost no difference to either |
| October | Steering follows the key but lands off target, for one head | Bin 0 of the target is A, not C: off by 9 semitones |
| October | Baselines at gain 0 scored CE about 3, blamed on a different sampler path | November: mostly the allocator setting below. The two samplers correlate 0.96 to 0.999. Same-path baselines remain the cleaner design |
| November | Melody stream weak, +0.151 | The stream was in both CFG branches. Fixed: +0.467 |
| November | True minus shuffled about 0 | Each arm was scored on its own stream. If both follow, that cancels. Caught on first read of one table. Check any older number built this way; none is known |
| November | Dead-audio checks clean | A setting (`expandable_segments`, on ROCm) could produce wrong audio that is still finite. Section 8 |
| November, found while writing this | 32% to 84% of renders have no lead, vs 5% in the corpus | "No lead" means under 40 notes, on 20 s renders and on 380 s crops. Over random 20 s windows, about 60% of the corpus also fails. The gap is mostly the meter, and it is still in several of our documents |

## 4. Steering harmony with chroma heads

LatCH guidance needs no fine-tune: a small head predicts a feature from the noisy latent, and sampling follows its gradient. The questions are how far it moves the output, at what cost, and what it moves.

**How far.** Change in mid-band chroma cosine against an unguided render through the same sampler, 48 clips per gain:

| Gain | 512 | 1024 | 2048 | 4096 | 8192 |
|---|---:|---:|---:|---:|---:|
| Production head | +0.014 | +0.033 | +0.075 | +0.133 | +0.189 |
| Retrained head | +0.152 | +0.232 | +0.300 | +0.354 | +0.384 |

This is the base model at 24 steps; the transposition tests below use a fine-tune at 50 steps, so do not compare numbers across them. At gain 512 the same retrained head reads +0.152 here and +0.080 there. In gain terms, 512 on the retrained head is about 6144 to 8192 on the production head. The gate passes the production head at every gain and the retrained head through 3072, then fails 1 to 2 of 48 on enjoyment drift. Both are usable to 8192 by the gate. Better validation loss did not predict more steering. The best-validation head steered less than one with worse loss, and a head trained only on our own music has a validation number that leaked. **Keep steering separate from validation loss when choosing a head.** Sharper targets land more frames on the strongest note (0.25 to 0.45 at gain 32768, with frame cosine falling, 12 clips per cell).

**Does it follow transposition.** Asking for the same chord in four keys, on 14 prompts, against a bungee-shifted control that scored 84/84 and 42/42:

| Head | Gain 2048 | Note |
|---|---:|---|
| `hpcp`, target corrected | 42/42 | Earlier labelled dead |
| Retrained `same_chroma` | 42/42 | 14/42 at gain 512 |
| Production `same_chroma` | 0/42 | 9/42 at gain 8192 |

This is the mid band, and chance is 3.5 of 42. The bass band stays weak, at 9 of 42 or below. "Follows" here means the chroma profile rotates with the key, not that it lands on a named chord; specificity is about +0.25 to +0.28.

**Chord colour in the model's own key.** A loss that takes the best of 12 rotations, or a target placed on the render's own root, keeps the root in about 91 to 93% of clips with the retrained head (51 and 52 of 56) and moves colour by +0.079 to +0.105. A plain major-on-C target keeps it in 8 of 14, 4 of which were on C anyway. Not gated, not heard.

**What this does not show.** The chroma meter is the same representation the head learned to predict, and the independent check planned in July (key detection against the target) has no recorded result. The change in strongest-note hit rate is +0.003 and +0.030 for the production head and +0.090 and +0.208 for the retrained one, at gains 512 and 2048, so these are tints of probability, not note control. An early listening pass called the retrained head's chord following "beautiful and transparent". Those clips came from flagged renders on the raw base model at 24 steps (section 8), and the same pass noted noise bursts, attributed at the time to those settings.

**The verdict we may have closed too early.** Our records say the guidance route for melody is closed. That rests on one July probe, 0 of 12 turns with 26 renders, with the weak production head, and with `hpcp` dropped as dead when its target was off by 9 semitones. Everything that made chroma guidance stronger came later, and none of it has gone through that test. It costs about one GPU evening.

## 5. Steering pitch with f0 heads

Heads trained on a pitch curve were tested on the base model with Melodia on the mix.

**Direction works.** Rising minus falling target, in semitones per clip: +7.4 at gain 512, +11.0 at 2048, +22.1 at 8192, positive on 10, 10 and 12 of 12. Shapes follow too, on a follow score where chance is 0 and the maximum is 2: up and down +0.81, +1.12, +1.28, arch and valley +0.63, +0.94, +1.14, at gains 8192 to 32768. Above 8192 the gate starts failing (5 of 48 at 16384, 13 of 48 at 32768, mostly at latent level).

**Speed does not.** Following a triangle wave, in phase minus antiphase (chance 0, maximum 2):

| Period | 10 s | 5 s | 2.5 s | 1.25 s | 0.625 s |
|---|---:|---:|---:|---:|---:|
| Follow score | +0.155 | -0.080 | -0.073 | -0.044 | -0.019 |
| Unsteered clips' chance correlation with the target (absolute r, a different scale) | 0.52 | 0.36 | 0.13 | 0.14 | 0.08 |

Melodia on known synthetic lines over drums and bass reads 0.993 at a 5 s wave and 0.97 to 0.98 at 2 s, so this is not a blind meter, at least not without pads and leads competing. Even the 10 s result barely clears zero (interval lower bound 0.021).

**Limits.** A voice getting louder would score here as well: spectral centroid also follows, +0.15 to +0.35. The bass head has no effect up to gain 8192, though a known octave ambiguity could hide one. Retraining with our modular optimizer gave no gain, tested at epoch 12 only. Not heard.

**A slow pulse is not a melody.** A 0.30 Hz pulse transfers through an onset head (+0.492 vs -0.031), and it was long quoted as the upper limit of what guidance can do: arrangement, not bars. It is one seed, one prompt and one head, and the "not bar-level" half of that reading came partly from the pianoroll verdict in section 7, which is now void.

## 6. The morph conditioner

The idea was to train in contour, not notes: Melodia on the `other` stem of each track, encoded as K&P rank symbols, fed by cross-attention. It deserved its chance, since the contour is pitch-invariant and exactly what you might want to steer.

Sixteen arms and a 384-cell audition produced four meters that failed their own gates, and nothing usable. An early bracket had steered at cfg 16 (+0.227) and been inert at cfg 1, which nobody has explained. That was the reason for one later run with more capacity. It had training trouble (median gradient norm rising from 0.104 to 5.07, no working warmup) and was the run tested below. A single unattributed note records one possible audible correspondence in it, which no measurement has found. In October we built a meter that passes its positive control: pitch-curve correlation against Melodia reads the source audio at +0.431 against -0.066 for a foreign one.

| Test | Result |
|---|---|
| Own contour minus foreign, renders | +0.0001, higher in 74 of 144 pairs |
| Conditioned minus null | +0.023 |
| Deconvolved weights instead of EMA | No better |
| Clean synthetic contours, 132 clips | Fed vs mirrored -0.08 to +0.08, inside the spread of nulls |

The meter's limit is that it can only exclude following above about 12% of a perfect copy. A partial bend could hide below that. This was not the CFG fault: these adapters already nulled the unconditional branch.

Why it fails is not settled. Melodia on a separated stem of goa is a noisy source; the symbols may be too coarse; or the signal may be too weak in training. Clean symbols from transcribed notes, through the better inlet of section 7, also did no better than centred pitch on their own measure (+0.020 vs +0.028, against +0.209 for the decoded source). That hints at the symbols themselves, on a short run. All 16 original arms, and a later full retrain with a stable schedule, have never been through the working meter. We have parked this path, and we have not closed it.

## 7. The pianoroll conditioner, and the fix

A per-frame note roll from MuScriptor enters blocks 12 to 23 of the DiT through a zero-initialised projection, on a full fine-tune of 32 epochs.

**August.** First read by chroma, true minus shuffled was +0.022, not significant. Listening noted that "true & shuffle have very identical notes; foreign seems to be in a different key". That was the clue: shuffling preserves the key, so chroma could not separate them. Transcription gave +0.100, 6 of 6, p = 0.016 (F1 0.534, the six densest windows). So the first verdict was a meter artefact, already corrected in August, though our documents kept quoting it. The weak signal stayed, and in-training control gain was about 0.2% of the loss (0.8135 vs 0.8153). That gain turned out to be a poor predictor: the pitch-invariant arm below follows strongly with a loss gap of only 0.00017. **What the misses are:** of 5,871 played notes in August, 69.5% were exact, 30.4% in the roll's pitch-class set and 0.2% outside it, which is why chroma saw so little.

**November.** The stream was in both branches of CFG. CFG output is uncond + s(cond - uncond). With the stream in both branches, its main effect sits in both terms and acts at weight 1, while text acts at weight s. So it read as weak and not as absent. With zeros in uncond, stream and text are scaled together. This account is inferred from the code and the before-and-after numbers, not measured term by term. Putting zeros in the unconditional branch, with the same checkpoints and seeds:

| | Stream in both branches | Zeros in uncond |
|---|---:|---:|
| Centred pitch, DoRA r128, follow score | +0.151 | +0.467 [+0.392, +0.543], 46 of 48 |
| Absolute notes, August full fine-tune, follow score | +0.212 | +0.636 |
| Same, note F1, fed minus other | +0.045 | +0.203 [+0.181, +0.226], 48 of 48 |

**What it can now do,** on the unchanged August checkpoint, online weights, MEASURED:

| Test | Result |
|---|---|
| Training crops, F1 | 0.653 fed; 0.609 for the decoded source crop; 0.045 no stream |
| Same, played frames on a fed note | 84% (52% with the stream in both branches, 8% with none) |
| Invented melodies, 36 clips on 12 prompts | Fed pitch sounds on 73% of frames (2.5% on a render with no stream); top line on the fed pitch 67%. The same clip scored against its melody's shuffled blocks reads 40%, which is partly shared pitches (one melody overlaps its own shuffle on 52% of frames by construction); fed minus that +0.33 [+0.29, +0.37], 36 of 36 |
| Same clips, Melodia, within a semitone with octaves folded | 74% against the fed melody; 43% against its shuffled blocks and 17% against another melody (same clip, not renders fed those); 18% for no stream; fed minus other +0.58 [+0.50, +0.65], 34 of 36. A real test with renders fed a shuffled stream exists only on training crops |
| Transposed crops | F1 0.63 vs 0.05; 24 of 24 |
| Gate | Invented 2 of 36; transposed 0 of 24; training crops 6 of 48, all enjoyment drift (13 of 48 with the stream in both branches) |
| Quality | Audiobox rises on training crops (PQ 7.78 vs 7.67, CE 6.80 vs 6.30), is flat on invented melodies, and drops on transposed crops (PQ 7.17 vs 7.68, with a lower spectral centroid) |

**What it does not show yet.** It has not been heard. It is one checkpoint, with a second seed never evaluated. Recall ranges from 21% to 100% by clip, and from 42% to 83% averaged by prompt. The invented lines (scale walks, arpeggios) were not checked for overlap with training rolls. MuScriptor made the rolls and scores the renders, so the model may have learned what MuScriptor reads as a note; Melodia agreeing on the invented clips argues against that, but a thin lead on top of the track would pass both. Melodia was not run on the training or transposed crops. Invented lines are one voice at 0.8% roll density against about 2.5% over whole training rolls, and more on selected crops. The F1 on training crops is above the source crop. That could mean memorising, or a decode that is a poor reference, or differing context: rolls were transcribed over 380 s, and the source reading is on a 24 s decode, of which only 16 of 24 crops read 0.5 or above. The source is a weak ceiling. Nobody has compared both-branches and null on the invented melodies, only on training crops, so how far generalisation depends on the fix is an inference. Untested so far: truly held-out transcriptions, notes under 2 frames (0.19 s), longer than 256 frames, cfg other than 7, EMA weights, a stream scale separate from text CFG.

**Absolute notes and centred pitch.** A pitch-invariant version follows over seconds at +0.467 but barely at note scale (+0.103; within a semitone 14% vs 12% for no stream). The absolute-note version scores +0.263 at note scale. It is tempting to read that as input, but one is a DoRA at 2,400 steps and the other a full fine-tune at 32 epochs. Both ran on the same crops, selected to be voiced with a moving top line, so neither is a corpus average.

## 8. Results to hold more loosely now

| Result | Why |
|---|---|
| Chroma strength table (section 4) and related retrained-head evaluations, two chroma boards | Rendered with `expandable_segments` set, which can give wrong but finite audio on ROCm. A 1,980-clip run without it was clean. For the strength table, baselines and 68 suspect clips were re-rendered, 1 changed, and the means stand; most steered clips and the two boards were not re-rendered. The transposition, chord-colour, f0 and pianoroll runs did not set it |
| "Guidance is closed for melody" | One head, weak; see section 4 |
| "Slow structure transfers, notes do not" | The note half came from a conditioner under the CFG fault and a voided first verdict. The guidance speed limit stands on its own |
| "Absolute notes beat centred pitch" | Model size and training length differ |
| "32% to 84% of renders have no lead" | Mostly a length artefact in the detector, section 3. Anything built on it, including how much fine-tuning changes lead presence, needs a length-fair detector |
| "Air is the melody band" | About half fingerprint |
| "Air is the only band with a real matched-vs-null gap" (+0.196) | On 386 of 752 tracks with air notes, on one metric. Bass and mid have a temporal part on another metric (0.075, 0.104, vs air 0.125) |
| True-minus-shuffled numbers built by scoring each arm on its own stream | That cancels when both follow. One table is known affected, and it was caught the same day. August's +0.100 scored both against the source roll, which is valid. Check any others |
| Any verdict on a stream through this inlet before 3 November | Under the CFG fault, including other per-frame conditioners built on it |

The `hpcp` "dead" verdict and the note-level null both measured our evaluation rather than the model. Other nulls have survived an audit: melody bursts, the morph result, the f0 speed limit. Any melody null remaining in our records should get a stated instrument check before anyone repeats it.

## 9. What the field knows

Working melody systems train the condition in: MusicGen, JASCO, MuseControlLite, MuseTimbre. Training-free gradient guidance is a known hard case. The paper our heads descend from says pitch controls "pose challenges", on monophonic pitch with CREPE. Our notes had summarised that as failure, which overstates it. Our result here is consistent with the field, not a surprise.

**The CFG fault is known in general form.** ControlNet (2023, section 3.4) notes that a condition can go in both branches or the conditional only: in challenging cases such as no prompt, both "will completely remove CFG guidance", and conditional-only "will make the guidance very strong", for which it adds a weighting. Our case has a prompt, so CFG was not removed, only not applied to the stream, and our fix is the option they warn is strong. JASCO and MuseControlLite use a separate guidance scale per condition, and StemGen does too. We did not find a paper naming it for a melody stream in audio, and a few searches do not prove absence. Our own next step, a stream-only scale, is standard practice.

**Things they do that we have not:**

- **Information bottleneck.** MusicGen quantises chroma to the dominant bin because raw chroma "often led to reconstructing" the source. Our rolls carry full detail, and a held-out test would show whether that hurts.
- **Reference points.** MusicGen reports chroma cosine 0.66 with control vs 0.10 text-only; MuseControlLite reports melody accuracy of 61.1% against 56.6% for a Stable Audio Open ControlNet and, on a style-transfer split, 0.09 text-only and 0.60 with melody, with CLAP falling from 0.42 to 0.28; MuseTimbre reports frame F1 0.316 against a source ceiling of 0.540. We have never computed the common accuracy measure. It shares chroma's blindness to key, so it would be for comparison only, and note that MusicGen's protocol has no shuffled arm, which is what exposed our meter.
- **Human ratings of melody match.** MusicGen ran a rating on 40 samples of 10 s. We have one listener and no protocol.
- **Input channels** rather than additive injection (a hypothesis in JASCO), and top-k CQT rather than chroma, which keeps octave.

## 10. What we know, what we don't, and what we don't know we don't

### Known

Confidence in brackets. These are measurements unless marked, and some carry interpretation.

- The SAME latent encodes pitch linearly and a semitone is a large change (high on synthetic, medium in mixes).
- Melody is a small part of latent variance, in a quiet direction (medium).
- Chroma guidance moves harmony toward a target and rises with gain (high), the retrained head reaching at gain 512 what the production head reaches at 6144 to 8192 (high as a ratio; partly provisional, section 8).
- It follows transposition in the mid band at gain 2048 (medium-high).
- Pitch guidance sets slow direction (medium) and does not follow 5 s or faster (medium).
- The morph conditioner does not follow above about 12% of a perfect copy (medium-high).
- A note stream with CFG on it is followed, including sparse single-voice lines invented for the test (medium; two meters on those clips).
- A control stream in both CFG branches is under-driven (high; reproduced on two checkpoints, and known in the literature).
- PQ and CE do not see melody (medium).
- Sampling updates do not show melody-specific bursts (medium).
- HEARD: subspace loss sounds more melodic at some cost in bass (one listener, not blind).

### Known unknowns

Roughly cheapest first.

| Question | What would answer it | Cost |
|---|---|---|
| Does the pianoroll result sound like a melody? | Listen to the eval page | Minutes |
| How often do renders really lack a lead? | A length-fair detector, such as notes per second over the same window length | CPU |
| Does the chroma result survive an independent meter? | Key detection and transcription on existing clips | CPU |
| Is the air band lead or pad? | Join band results with lead detection | CPU, minutes |
| Do subspace arms change hooks? | Transcribe clips already rendered | CPU |
| Do ratings know about melody? | Join ratings with melody features; add a melody question | CPU, plus a UI change |
| Is generalisation down to the fix? | Invented melodies with stream in both branches vs null | About 24 min GPU |
| Does a second seed agree? EMA vs online? | Render and score | Short GPU |
| Does the stronger chroma head turn a melody? | Re-run the July test with it | One GPU evening |
| What stream scale is best, and is the quality cost separable? | Separate scale, ladder of 1 to 12 | Code plus GPU |
| Does it hold on real unseen notes? | Transcribe tracks outside the corpus | GPU |
| Do the untested morph arms follow? | Run the meter on them | About an hour each |
| When does sampling settle on a melody? | Track per-step melody across unguided sampling | An afternoon |
| Where in depth does it form? | Per-block probe with a pitch column | Hours |
| Is there a melody gradient deficit? | Log gradient share during a run | Small |
| Does fine-tuning raise melodic content? | Paired renders, same prompts, seeds and cfg | GPU-hours |
| Does a pitch-invariant stream at full scale follow notes? | One long training | Long |
| What ground truth do we have for melody in goa? | None human-annotated. A small hand-checked set | Hours of ears |

### Unknown unknowns

These are questions we found we had never asked, while assembling this. They are inferences, not findings, and absence from our records is weak evidence of anything. Roughly by how much they could change the picture.

1. **Is "follows the notes" the same as "plays the tune"?** A transcriber and a listener may disagree in dense music, where identity lives in filter, accent and rhythm. F1 0.65 may still not sound like the same riff. Nothing tests this.
2. **Are we seeing a lead added on top rather than the music changing?** Both meters would pass.
3. **Which other nulls share a hidden coordinate?** The CFG fault was invisible for months. One unexplained case: a conditioner that steers at cfg 16 and is inert at cfg 1.
4. **How much melodic variety exists in the corpus?** Nobody has counted distinct riffs, so "follows" and "reproduces" are hard to separate.
5. **Rhythm as part of melodic identity.** We tested transposition but never time-stretching a stream, nor a melody at the wrong tempo.
6. **Text as a competitor.** No test of how far a prompt naming notes or an arpeggio can go. Our captions also carry almost no melody information, so the model may have no text handle at all.
7. **Prompts and melodies as gatekeepers.** Recall varies about as much within a prompt (mean spread 0.37) as between prompts (range 0.41), and we do not know why.
8. **Does the frame grid set a limit?** At 10.77 Hz a 16th at 145 BPM is about one frame, near Nyquist. Some limits above may be this.
9. **Selection effects.** A score over clips the detector accepts is conditioned on the model having produced something readable. We just found the detector's own threshold depended on clip length. What else depends on it?
10. **Does the demeaning erase the thing?** Removing "generic goa" may remove the shared motifs a listener hears as the melody of the genre.
11. **The post-trained model runs at cfg 1.** The fix relies on CFG, so it needs a stream-only scale there. Not tested.
12. **Whole tracks.** Training crops are about 24 s. The use case is 6 minutes.

## 11. A minimum test for the next sighting

Each rule exists because something in section 3 got past us.

1. **Say which of key, pitch set, placement or contour you claim,** and use a meter that can see it.
2. **Run four arms:** fed, shuffled in time, foreign, no stream. Report differences. Score each clip against both streams, not only its own.
3. **Pass known answers through the same path first:** source audio, synthetic lines, bungee shifts. Make failure fatal, not a printed line.
4. **State a trivial baseline** beside the number: no stream, mean guess, a random subspace.
5. **Render baselines through the same sampler.**
6. **Put any per-frame stream in the conditional branch only.**
7. **Use several prompts, seeds and windows,** with intervals and sign counts.
8. **Report coverage and drops.**
9. **Check for fingerprint** with a frame shuffle.
10. **Gate the output,** and check it is a new line and not an existing voice getting louder.
11. **Use a second meter** when the scorer also made the targets.
12. **Label it MEASURED or HEARD.** Only ears close it.
13. **Write down the instrument audit before calling a null.**

## Papers

- Stable Audio 3, arXiv 2605.17991; SAME, arXiv 2605.18613
- ControlNet, arXiv 2302.05543
- MusicGen, arXiv 2306.05284
- JASCO, arXiv 2406.10970
- MuseControlLite, arXiv 2506.18729
- StemGen, arXiv 2312.08723
- MuseTimbre, arXiv 2609.30548
- Low-Resource Guidance (LatCH), arXiv 2603.04366
- MuScriptor, arXiv 2607.08168 (our main note meter; we have not read this closely)
- Hou et al., Stable Audio Open ControlNet, arXiv 2410.05151 (not fully read)
- Kant and Polansky, morphological space of contour
