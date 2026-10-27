## DoRA adapters against full fine-tuning: what we can and cannot say

<!-- DRAFT for the Muon guide, written by CONTINUITY 2026-10-27 at W's request; W places it. Voice: plain meaning first, numbers in the
section that owns them, textbook / our variant / known / guessed marked. No names of people, no paths, no run labels beyond arm names.
This is a research summary of our own notes, not a new experiment: sources at the end are for the editor. -->

A full fine-tune changes every weight of the model. A DoRA (or LoRA) adapter freezes the model and trains a small add-on (see the earlier
section on adapters). Both were used on the same base model, and the honest summary is that we have **no controlled comparison**: no
experiment trained both on the same data, for the same budget, with several seeds, and judged them by ear. What we have is the following.

**1. Memory decides what is possible on one 16 GB card.**
A rank-16 DoRA trains about 21.6 million parameters against a frozen base. A full fine-tune with AdamW ran out of memory at 15.13 GiB in
a memory test; a bf16 Lion with stochastic rounding fitted, and so did one of our own Muon-type optimizers with extra components switched on.
"Fitted" is a memory result only: we have not trained a Lion full fine-tune to completion, and every Lion run that trained was an adapter.

**2. By ear, early verdicts favoured full fine-tunes in fp32, but the comparison is mixed up.**
In July, listening judged fp32 full fine-tunes better than bf16 and than adapter-only runs, and said that higher adapter rank helped. That
verdict is preliminary and mixes three differences (precision, adapter against full, and rank), and it comes from the 8-epoch era, whose verdicts our
later notes say should be re-read. It is a lead, not a measurement.

**3. The automatic scores point the other way on one dataset, and nowhere on the other.**
Over a campaign of about 265 runs (810 checkpoints), the scores we use as a stand-in for the ear (a perceptual-quality score that agreed
with 77.6% of 668 A/B votes, and a text-audio similarity score that mostly repeats it) favoured DoRA over full fine-tuning on one
dataset only. After removing 60 mislabelled checkpoints, the advantage on the other dataset disappeared (p = 0.49). Checkpoints from the same
run are not independent, so the first analysis overstated its significance; at the level of whole runs only the dataset, the adapter scaling,
the rank and the optimizer survived. An early reading that "frame length" mattered turned out to be this adapter-against-full difference in disguise.

**4. The two fail in different ways.**

| | Adapter (DoRA) | Full fine-tune |
|---|---|---|
| Typical failure we hit | magnitudes crossing zero, then NaN; whole-model runaway at high rank | weights and output level growing without weight decay (the drone), unconverged EMA copies |
| Rendering | a fault on our GPU stack made live adapters return NaN in 2.6 to 7% of renders after late July (merged adapters were stable); full fine-tunes: none | stable in every period |
| Learning-rate scale | about 5e-4 with our modular optimizer | about 5e-6 with our fusion optimizer, a hundred times smaller |

The last row is the learning-rate scale point again: the numbers are not interchangeable between optimizers, networks or training types.

**5. The optimizer changes the sound, not just the loss.**
Lion fine-tunes were judged fine but stylistically distinct from AdamW and our own optimizer, so a matched loss does not make two models
interchangeable. For full fine-tunes, our own optimizer at a very low learning rate (5e-6) produced the clips we liked best in the one ladder we
ran; a resumed AdamW run at lr 1e-4 developed a discontinuity (the data order was not restored on resume), so we reran it uninterrupted.

**6. Turning a full fine-tune into an adapter did not work.** See the section on adapter extraction: the weight change of our full
fine-tunes is close to full rank, and a rank-128 adapter kept about 26% of it.

### What we do not know
- Whether a DoRA trained at a high rank for as long as a full fine-tune reaches the same sound. (Rank helped in July; the extraction result says
  low rank cannot hold a full fine-tune's change, but a directly trained adapter finds a different, smaller change.)
- Whether the dataset effect (adapters ahead on one dataset only) comes from the data, the captions or the number of epochs.
- Whether Lion's full fine-tune quality matches an adapter's; only its memory and trajectory were recorded.

*Known:* the memory test, the failure profiles, the extraction result. *Preliminary:* the July listening verdicts. *Our reading:* that the
dataset, not the method, explains most of the adapter advantage. *Guessed:* nothing here rests on a guess, but the evidence for every comparison
is weak.

### Sources (internal, for the editor)
- Memory test: GHOST-NOTE journal 2026-09-07 (full fine-tune memory map on 16 GB), via THE-FINN's check 2026-10-27.
- July verdicts: `docs/training-findings.md` (2026-07-20 fp32 against bf16; 2026-07-23 listening verdicts); `docs/TRAINING.md` F11.
- Campaign statistics and the corrections: `EXPERIMENTS.md` (W, 2026-08-21: pseudo-replication, frame length, the 60 mislabelled `xft` checkpoints; PQ against CLAP on 668 votes).
- Failure profiles: `docs/TRAINING.md` F12 (DoRA magnitudes), F15 (live-DoRA render fault), F9 (EMA); drone postmortem in `docs/training-findings.md`.
- Learning-rate scales: `docs/TRAINING.md` D4. Optimizer as style: F6. Fusion ladder and AdamW discontinuity: `Misc/models_index_overrides.json` notes (arms `fusion_autoscale_lr5e-6_full3h`, `adamw_lr1e-4`).
- Extraction: `docs/training-findings.md`/journal 2026-07-24 and `DISCOVERIES.md` "xft distillation: rank limit, not a bug".
- **Not read for this draft:** the contents of the `sa3_lora_runs` directory beyond run names, `clap_dora_aggregate.csv`, and the Lion adapter-arm results; a Lion-against-DoRA table would need them.
