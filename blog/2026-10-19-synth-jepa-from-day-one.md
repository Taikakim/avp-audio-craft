<!-- REVISED DRAFT 2026-10-19 (THE-FINN, revising the earlier draft at Kim's request). Review: Kim (final fact review
still to do). Original text kept outside the repo; ask THE-FINN for it. Every number below was traced to a result file,
log or document on 2026-10-19; items still to confirm before publishing:
  1. No blind listening verdict on the V6 models was found in the project records. The text says so; update if one exists.
  2. The "oscillators 2 and 3 default to muted" point rests on the code defaults (probe_activity.py). The original draft's
     story of failing detune calibration checks on the desktop plugin could not be sourced and is left out.
  3. Optimiser section: settings come from the V6 training logs and commit messages (2026-10-17); no V6 optimiser ablation exists.
  4. Synth-JEPA citation: arXiv 2609.31024 (Hayes, Tian, Lattner), as cited in the project README.
  5. Track and artist names are left out on purpose; stems are described by sound only.
Source locations (not for publication): ~/sao_runs/audio_eval_v6_foundation, stems_v6_foundation_occam, audio_eval_dpo,
v6_A/B/C; stable-audio-tools/scripts/synth_inversion/*.md; EXPERIMENTS.md section H. -->

# Rebuilding a Synth Patch from Audio: Notes from the First Weeks with Surge XT

Since October 1 we have been working on one problem: given a short clip of a bass sound and the notes it plays, can a
model recover the synthesizer settings that produced it?

If you make electronic music, you know why anyone would want this. You hear a bass in a track and you want the patch,
not a sample of it: a sound you can open up in your DAW, with the cutoff, the decay and the oscillators still adjustable.

Our target synthesizer is Surge XT 1.3.4, an open-source synth with up to three oscillators, wavetables, two filters,
waveshapers, effects and a modulation matrix. A "patch" here means one complete set of its knob and switch settings.
A "stem" means a bass part isolated from a finished track. The 24 real stems we test on were separated with
tools such as Demucs and BS-RoFormer, and their notes were transcribed with MuScriptor, so the clips are short and the notes are
estimates, not the original MIDI.

This post is a record of what we tried, in order, what each step did to the numbers, and what we had to patch around
along the way. One of the main methods changed partway through, and the ordering matters for reading the results.

## How we score a result

We cannot compare knob positions directly, because different settings can sound the same. So we render the predicted
patch in Surge, play the same notes the stem plays, and measure the distance to the original audio. The measures
used below:

- **Phrase MSS** (multi-scale spectrogram distance): how far apart the two spectrograms are, at several time
  resolutions, over the whole phrase. Lower is better.
- **Mel-SSIM**: how similar the shapes in the two mel spectrograms are (envelopes, filter sweeps). Higher is better.
- **Spectral centroid error**: the difference in average brightness, in Hz. Lower is better.
- **Wins**: on how many of the 24 stems a model has the lowest distance.
- **Best-of-8**: the model proposes 8 patches, we render all 8, and keep the one closest to the target audio.
  **1-draw** means we keep the first and do not look.

All of these measure audio distance. None of them is a listening test.

## 1. Predicting the knob values directly (October 1 to about October 17)

The first approach was direct regression. Render many random patches from Surge, then train a network to take the audio
and predict the settings, with a loss that compares predicted knob values to the true ones.

The first dataset was 200,000 patches over 23 parameters, rendered through the plugin in 3,496 seconds on 12 CPU
workers (57 renders per second). We trained two models on it: a residual MLP that gives one answer, and a
flow-matching model (explained below) that gives a distribution of answers. Each trained in about 33 to 34 minutes.

Our first comparison of the two turned out to be invalid. The MLP was scored on its single best guess and the flow model
on one random draw, so the numbers could not be compared. We rewrote the evaluation to render each patch and compare
the audio, added two reference arms (an oracle, and a "mean patch" baseline that any useful model must beat), and set
out to use that comparison from then on.

We also had concerns about this kind of loss that came from how synthesizers work, though we measured none of them
directly at this stage:

- **Silent parameters.** If an oscillator's volume is zero, its pitch and waveform settings change nothing, but a
  loss on knob values penalizes errors on them anyway.
- **Switches.** A filter type or a waveform is a choice, not a dial. A model trained to minimize average error can
  land between two choices.
- **Knob distance is not sound distance.** A small move of a filter cutoff can change a bass completely, while a
  large move of an unconnected LFO changes nothing.

Two things came out of the next runs.

First, a bug in our render path. Surge keeps hidden chorus and delay state between renders in one plugin instance,
and 5% of the training patches carried effects, so the audio in the earlier training run was corrupted. With effects
disabled in training renders, held-out retrieval (picking a patch out of 512 from its audio) rose from 3% in the old run
to 65.6% at step 23,000 of the rerun, and to 79% audio-to-patch at the end.

Second, a result we did not expect. The rerun finished on October 7 with a held-out synthetic flow loss of 0.235.
On the 24 real stems, though, it did worse than the older models trained before the fix. In the first comparison, the
older October 5 model scored a phrase MSS of 7.31 and won on 13 stems, against 7.84 and 7 wins for the rerun. In the
five-model comparison that followed, the two older runs still led on real stems. Fitting the synthetic distribution
better did not make real stems sound closer, and it may have made them worse. We read this as a gap between synthetic
and real audio, not a problem with the fix.

## 2. Adding an embedding space: Synth-JEPA

To get a distance that tracks sound, we adopted the method from the Synth-JEPA paper (Hayes, Tian and Lattner,
arXiv 2609.31024). JEPA stands for Joint-Embedding Predictive Architecture. In plain terms:

1. One network listens to audio and produces 512 numbers describing it.
2. A second network reads a patch (the knob settings) and produces 512 numbers describing it.
3. Both are trained so that a patch's numbers and the numbers of its own audio line up, with each side learning to
   predict the other.
4. A regularizer (the paper's SIGReg, from the LeJEPA work) keeps the numbers spread out, so the networks cannot take
   the shortcut of mapping everything to the same point.

We measure whether it works by retrieval. Given the audio of a held-out preset, can the model pick out the right patch
from a pool of 512? For the three V6 models described below, the top-1 hit rate was 72 to 74% from audio to patch and
78 to 80% from patch to audio, against 0.2% by chance. We also use "ladder" checks, where a single knob is swept in
steps and the embedding distance should rise steadily with the sweep.

The paper trains for one million steps on freshly rendered audio with 139 parameters. We have a smaller setup, so our
version is an approximation, and the README says where it differs.

## 3. Generating patches with flow matching

For the generator we use conditional flow matching. It starts from random numbers and moves them in 25 small steps,
guided by the audio, until they land on a patch. Because it starts from different random numbers each time, it gives a
different patch on each draw. That is what makes best-of-8 possible.

For comparison, we also ran a search that tunes a patch directly against the target. Differential evolution over all
filter types takes about 10 minutes per note at roughly 40 ms per render in the plugin.

## 4. Adding acoustic matching (V5 and V6)

Up to here the model learned only from knob values. Our V4 plan dropped any loss computed on rendered audio,
because Surge is not differentiable: you cannot pass a gradient back through a C++ synthesizer.

The workaround is the JEPA itself. Its parameter encoder, followed by its patch-to-audio predictor, is a
differentiable stand-in for "what would this patch sound like". During training we pass the flow model's predicted
patch through that stand-in, compare the result to the embedding of the real audio, and send the gradient back into
the flow model. The model is now trained on both knob values and predicted sound. The audio that gets compared is
the JEPA's description of it, not a render.

V5 (October 13 to 19) tried this with soft category values at every step. V6 changed two things. The categorical
parameters (filter types, waveforms) are passed through as hard choices with a straight-through gradient, so the
JEPA only sees valid inputs. And the acoustic loss is applied only in the second half of the flow, where the patch
is already close, with weight 0.08.

## 5. Problems found on real stems

Testing on real stems turned up a series of faults, some in the model and some in our own pipeline. These are the ones
we have documented:

- **Wrong root note from a drum channel.** In some transcriptions a closed hi-hat on MIDI channel 9 hit every 16th
  note, and the script picked it as the root. Rendering at the wrong pitch made every bright candidate lose. Fix: strip
  channel 9 and take the root from channel 0.
- **Wrong note given to the model.** The real-stem evaluation scaled the note with a range of 12 to 96, but every
  layout was trained on notes 28 to 50. The model was told a note up to an octave off, and could only match the stem
  by changing its oscillator octave. This is a plausible cause of much of the octave drift we saw.
- **A parameter encoder that ignored half the parameters.** In every run of the V3 trainer, the JEPA's parameter
  encoder was built for the original small parameter set and silently ignored oscillator octaves, oscillator 2 and 3
  volumes, ring modulation, noise, the second filter and some routing. A shape check added in October found it.
- **An auxiliary head with no labels.** The inharmonicity head (it predicts how far a sound's partials are from a clean
  harmonic series) needs labels. The bank used for the V5 runs stored none, and the trainer's default weight for the
  head was zero. The training logs show `Aux 0.0000 (v=0.00)`, meaning no valid labels. Whether earlier runs also
  trained on empty labels is not recorded.
- **Muted oscillators.** In our code, oscillators 2 and 3 are muted unless a patch turns them on.

Take the inharmonicity head. In our controlled 2x2 test (aux head on or off, crossed with a
temporal pooling encoder on or off), the head's effect on retrieval was not distinguishable from run-to-run noise
(no retrieval measure reached significance). The pooling encoder did show measurable gains on some measures, such as categorical accuracy
(+0.5 points) and one of the ladder checks. In V6, the model with the head (B) and without it (A) are
statistically the same on every measure. So fixing the missing labels did not, by itself, improve any measure we track.

## 6. V6: simpler patches and a note input

Our checks suggested that part of the problem was what the training patches looked like. Random draws often
switch on features that make no audible difference, and a model trained on them learns to switch on features too. V6
changed the layout and the training distribution:

- The model is given the note it should play, instead of inferring the pitch.
- Oscillator 1 is locked to octave 0. Oscillators 2 and 3 are set relative to it, from two octaves down to two up.
- Fine detune is limited to plus or minus 0.2 semitones.
- The training patches come from a prior weighted toward simple sounds: 70% sparse patches (mostly one oscillator,
  with extras switched on at set rates), 20% drawn from real presets, 10% fully random.
- The encoding of a patch is 110 numbers.

We rendered a bank of 100,000 patches and trained three arms from scratch, 12,000 steps each, on one AMD Radeon
RX 9070 XT:

| Arm | What it adds | Training time |
|---|---|---|
| A | V6 layout, simple-patch prior, temporal pooling encoder | 1.72 h |
| B | A plus the inharmonicity head | 1.91 h |
| C | B plus the acoustic loss from section 4 | 1.97 h |

### Synthetic held-out notes (256 notes)

| Model | Log-mel L1 | Phrase MSS | Modulation-spectrum distance | Bass-energy distance |
|---|---|---|---|---|
| A, 1-draw | 0.1723 | 7.03 | 0.618 | 0.481 |
| B, 1-draw | 0.1724 | 7.05 | 0.614 | 0.480 |
| C, 1-draw | 0.1485 | 6.07 | 0.589 | 0.465 |
| A, best-of-8 | 0.0820 | 3.56 | 0.489 | 0.426 |
| B, best-of-8 | 0.0822 | 3.54 | 0.491 | 0.434 |
| C, best-of-8 | 0.0753 | 3.30 | 0.471 | 0.416 |

In paired tests, C is lower than A and B on log-mel, MSS and modulation spectrum for single draws (all p below
0.01). The bass-energy difference is within noise for single draws (p about 0.4). For best-of-8, C is lower on log-mel
and MSS; the modulation-spectrum and bass-energy differences are not significant at the 0.05 level.

### Real stems (24)

| Model | Training | Wins (MSS) | Mean MSS | Mel-SSIM | Centroid error | Features pruned |
|---|---|---|---|---|---|---|
| S5 (previous model, V5) | 16.5 h | 8 | 6.087 | 0.278 | 778 Hz | 5.00 |
| S5 plus DPO (see section 9) | 16.5 h plus DPO | 7 | 5.985 | 0.260 | 803 Hz | 4.54 |
| V6 A | 1.7 h | 3 | 6.599 | 0.256 | 637 Hz | 4.75 |
| V6 B | 1.9 h | 4 | 6.581 | 0.260 | 637 Hz | 4.25 |
| V6 C | 2.0 h | 3 | 6.533 | 0.284 | 583 Hz | 3.83 |

One stem is a tie, so the win counts add up to 25. "Features pruned" is the number of switched-on features,
on average, that a final cleanup step (section 7) removes because turning it off changes the phrase MSS by 0.02 or less.

On the metric the previous models were tuned on, phrase MSS, S5 and S5 plus DPO still have the lowest scores. V6 C has
the highest Mel-SSIM among these five (0.284 against 0.278 for S5, which is a small gap; it is higher than S5 on 14 of
the 24 stems), the smallest centroid error, and the fewest pruned features. The comparison is one seed, 24 stems, one
evaluation run. The training times are not a controlled comparison: V6 used a pre-rendered bank and a different
layout. We have not yet run a blind listening test on the V6 models.

## 7. What we patch around at inference time

Several of the steps that produce the final patch for a real stem exist because of shortcomings we have not fixed in
the model. They are part of every real-stem score above, so we list them:

- **Release ceiling.** The model sometimes predicts a release time long enough to leave a note hanging past the next
  one. The amplitude and filter releases are capped at one 32nd note at the stem's tempo (about 52 ms at 145 BPM),
  and the cap is kept between about 8 and 90 ms.
- **Octave folding.** The models are trained on notes 28 to 50. A stem with notes outside that range is folded
  into it by whole octaves for the model, and the oscillator octaves are shifted back afterwards.
- **Cleaning the transcription.** Overlapping notes (a sign of a transcription error on a one-voice bass) are
  discarded, and notes shorter than 70 ms are ignored.
- **Consensus over several notes.** We take up to six representative notes from each stem, draw two patches per note, and
  combine them: the median for continuous parameters and the most common choice for switches. The consensus patch
  and every individual candidate then compete.
- **Re-ranking on the full phrase.** The candidates are rendered in Surge across the whole phrase at the stem's tempo,
  with the envelope retriggering on and off, and the closest to the original wins.
- **Occam pruning.** For the winner, we try switching off each extra feature (waveshaper, oscillator 2 or 3, unison,
  detune, feedback). If the phrase MSS gets worse by 0.02 or less, the feature stays off.
- **Second note.** For stems with one usable note, the earlier default was to pitch-shift a copy of the clip up
  an octave to make a second sample. The default now uses a real second note when there is one.

These steps change the score. Quoting a model's number without them would be a different result.

## 8. Optimiser and training setup

The optimiser changed several times, and it is part of the story.

- **First version (Muon with schedule-free AdamW).** Hidden 2D matrices were trained with a Muon-style update (Newton-
  Schulz orthogonalization) with a "radial brake" that limits how fast weight norms grow, and the rest with schedule-free
  AdamW. We first called this NorMuon. It lacked NorMuon's per-neuron normalization, so we renamed it to what it is,
  and added an AdamW baseline with cosine decay to compare.
- **ModularOptimizer.** The V4 A-series runs (three 5-hour runs, batch 64, 12,000 steps, a schedule that decays the
  learning rate over the last 30%) used our modular optimizer with Shampoo-style preconditioning. The launch script
  for the modular Shampoo runs lists the other switches: role-based update rules per layer type, a cubic Newton-Schulz polynomial,
  radial brake 0.8, variance-aware dampening 1.15, schedule-free averaging with a 1,000-step warmup, and weight decay
  that depends on how long a run has trained.
- **Changes on October 17.** The defaults for the modular optimizer and FusionOpt were changed to turn off whitening and
  one other component at batch size 32, and the gradient clipping and scalar optimizer were exposed as options.
  The V6 arms ran with whitening off, clipping at 1.2, radial brake 0.8 and schedule-free averaging.
- **Averaged weights against live weights.** In one comparison, the exponential moving average and the live weights gave
  the same held-out flow loss (0.236 against 0.235). The schedule-free average had the highest loss (0.283), but scored
  better on real stems in that run.

We have not run an optimizer ablation at the V6 stage: A, B and C share one setup, so differences between them
come from the model and loss changes in section 6. Details of the optimizer are in the FusionOpt manual.

## 9. Speed

- **Rendering a training set.** 200,000 patches in 58.3 minutes through the plugin host on 12 CPU workers (57 per
  second). The native Surge Python bindings were measured at 439 renders per second on one CPU core.
- **Rendering for search.** About 40 ms per render in the plugin.
- **Inference.** The MLP answers in under 2 ms. The flow model uses 25 steps. A full real-stem run (consensus,
  re-ranking and pruning) takes 4 to 21 seconds per stem (median 12).
- **Training.** The V4 runs took about 5 hours for 12,000 steps at batch 64 with patches rendered live. The V6 arms took
  1.7 to 2.0 hours for the same 12,000 steps and batch size, at 104 to 126 samples per second with the data loader
  idle, using the pre-rendered bank. The model and layout also differ, so this is not a controlled speedup measurement.
  An earlier estimate of 42 samples per second turned out to be a time budget, not a measurement.

## 10. Flow-DPO: not decided

Direct Preference Optimization (DPO) is a way to improve a model from rankings of its own outputs. We drew several patches
per stem, scored each by MSS, bass-energy distance and modulation-spectrum distance, and trained the flow to
prefer the best over the worst. Three runs used different preference strengths (beta 30, 100 and 300) on the S5 model.

The results are mixed. On the 24 real stems, beta 300 lowered mean phrase MSS from 6.087 to 5.985, the metric it was
rewarded on. It lowered Mel-SSIM from 0.278 to 0.260 and raised centroid error from 778 to 803 Hz. On synthetic
held-out notes, 1-draw MSS went from 5.69 to 5.71, best-of-8 from 3.38 to 4.24, and 1-draw bass-energy distance from 0.50 to
0.64. Against V6 C on real stems, DPO is ahead on phrase MSS and behind on Mel-SSIM, centroid error and pruned
features.

DPO has not been run on top of V6. We have a pipeline for it, but no results, and we have not decided whether it is
worth the time.

## 11. What the evidence supports

- Training on knob values alone raised held-out synthetic scores and left real-stem scores where they were (section 1).
- Adding the acoustic term (arm C against arm B) lowered the audio distances on synthetic notes and gave the highest
  Mel-SSIM and lowest centroid error on real stems, with the caveats in section 6.
- The inharmonicity head has not shown an effect in any controlled comparison we ran, before or after the labels were
  fixed.
- A good share of the early real-stem errors came from our own pipeline: wrong root notes, a wrong note scale and an
  encoder that ignored parameters, not from the model idea itself.
- We do not yet know how any of this sounds. The next step is a blind listening comparison between S5, V6 C and the
  DPO model on the same stems.

We also expect the same pieces (the JEPA embedding, flow matching and the acoustic term) to be usable for other
instruments, such as drum machines. That is untested.
