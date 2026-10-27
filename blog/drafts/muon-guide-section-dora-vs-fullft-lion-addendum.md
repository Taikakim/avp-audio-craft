<!-- ADDENDUM for the live "DoRA against full fine-tuning" section (CONTINUITY 2026-10-27). Replaces the draft's "not read" gap about Lion.
Insert after point 5 ("The optimizer changes the sound, not just the loss"). Sources at the end are for the editor. -->

**Lion, what we actually have.** There is no controlled comparison of a Lion-trained adapter against a Lion full fine-tune, or against
AdamW, on the same data. The pieces are:

- *Small control heads (trained from scratch).* Lion reached held-out losses of 0.237, 0.228 and 0.262 at learning rates 1e-4, 3e-5 and
  3e-4, against about 0.20 for the modular optimizer and about 0.25 for AdamW. Its best rate was the lowest one tried, so that bracket is
  open below 3e-5. It was among the clear losers by epoch 2 or 3.
- *A large DoRA run (rank 128, Lion with D-Adaptation, effective batch 32, 12 epochs).* It trained to the end, but the planned A/B against
  the AdamW-type bracket was never run, so it has no verdict. Its clips were rendered from an EMA copy that started at the zero-initialised
  adapter, which makes them under-represent the run. Weight decay (0.05) was a judgement call, so any difference would not be attributable to
  capacity alone.
- *Full fine-tune.* A Lion run at 1e-5 was recorded by its trajectory only (path efficiency 0.664, wandering inside one basin, which suggests
  averaging checkpoints would help); the memory test showed that a bf16 Lion with stochastic rounding fits a full fine-tune on 16 GB. Listening
  found Lion clips fine but stylistically distinct from AdamW and from our own optimizer.

So the open question is real: nobody has trained a Lion full fine-tune to the end and a Lion DoRA on the same data and listened to both.

### Sources (internal, for the editor)
- Heads: `EXPERIMENTS.md` Phase D bracket (Lion lr 1e-4 / 3e-5 / 3e-4: 0.237 / 0.228 / 0.262), `docs/TRAINING.md` F7.
- DoRA run: `EXPERIMENTS.md` D17 (status corrected 2026-09-24: trained and rendered, A/B never run; EMA render caveat; wd 0.05).
- Full fine-tune: `Misc/models_index_overrides.json` (`lion_lr1e-5` trajectory note); THE-FINN's memory-test citation (GHOST-NOTE journal 2026-09-07); `docs/TRAINING.md` F6.
- Not read: the rendered clips and the per-epoch logs of the D17 run.
