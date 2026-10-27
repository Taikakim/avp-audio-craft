## EMA: a slowly updated copy of the weights

<!-- DRAFT for the Muon guide, written by CONTINUITY 2026-10-27 at W's request; W places it. Voice: plain meaning first, numbers in the
section that owns them, textbook / ours / known / guessed marked. No names of people, no paths. Sources are listed at the end for the
editor and are not meant for publication. -->

An EMA (exponential moving average) of the weights is a second copy of the model that follows the training weights with a delay. After
every update it moves a small fraction of the way toward the current weights, so single noisy steps average out. It is the same idea as
momentum, applied to the weights themselves instead of the gradients, and it is the textbook version of it.

**The decay is a timescale in EMA updates.** With a decay of 0.9999 the copy keeps 99.99% of itself at each update. Its half-life is
ln(0.5) / ln(0.9999), about 6,931 updates, and after U updates the weight still sitting on the starting model is 0.9999 to the power U.
Dividing the number of updates a run performs by the half-life gives a ratio, R, which is the number that tells you what you will get:

| R | What the EMA copy is |
|---|---|
| below 1 | mostly the starting model |
| about 2 | conservative |
| 3 to 10 | the useful range for a fine-tune (our rule of thumb, not from the literature) |
| far above 10 | mostly the recent path of the weights |

We aim for a half-life of about 5 to 20% of the total planned training, so that the copy turns over during the run.

**Our trainers update the EMA on every small batch, not on every weight change.** This is a property of the trainers we used (we read
it in the code; it is not universal). A code comment claimed the update runs after the optimizer step, which is wrong whenever gradients
are accumulated over several batches: with accumulation 4, the EMA gets four updates per weight change, so its memory measured in weight
changes is four times shorter than the decay suggests. Three full fine-tunes of ours show what that does:

| Run | Weight changes | Accumulation | EMA updates | Still on the starting model | R |
|---|---|---|---|---|---|
| A | 3,000 | 4 | 12,000 | 30% | 1.7 |
| B | 6,000 | 4 | 24,000 | 9% | 3.5 |
| the same 3,000 steps as A without accumulation | 3,000 | 1 | 3,000 | 74% | 0.4 |

**Moving a decay between batch sizes.** A decay copied from another recipe means little without that recipe's effective batch size (batch
times devices times accumulation). To keep the same horizon in data seen, the new decay is the old one raised to the ratio of the batch
sizes. A decay of 0.9999 at batch 32 becomes 0.9996 at batch 128 (half-life 1,733 updates) and 0.999988 at batch 4 (half-life 55,449). It
looks backwards, but a larger batch sees more data per update, so the decay has to move away from 1 to keep the same span of data.

**What went wrong for us.**

- *Rendering a copy that had barely moved.* Several tools prefer the EMA copy when a checkpoint contains one, silently. In a sweep of
  full fine-tunes the EMA copies still held about 55 to 62% of the starting weights, so what we heard was mostly the starting model, and the
  arms of a comparison came out alike for that reason alone. Check whether your checkpoint has an EMA copy (we count the EMA keys in the file)
  and which copy your render script loads.
- *An unconverged copy can be unusable, not just weak.* Two full fine-tunes whose EMA copies still held 24% and 47% of the starting model at
  epoch 11 rendered non-finite audio; later epochs, at 1.8 to 3.5 half-lives, rendered cleanly. This is two runs, so treat it as a warning, not
  a rule.
- *Averaging can blur what you trained.* For a short fine-tune at a low learning rate, the EMA copy is not automatically better: it can
  blur exactly the behaviour you were after. We save and audition both the live and the EMA weights.

**Where an EMA is and is not used in our setup.** Our Stable Audio 3 trainers keep an EMA only for full fine-tunes; they switch it off for
LoRA and DoRA, so none of our adapter results depend on an EMA copy. The control heads use one: in one feature test an EMA of 0.999 with
gradient accumulation 2 gave about three times the effect of the live weights (one feature, so weak evidence), while for the onset head the
EMA and live weights were indistinguishable at a half-life of half an epoch.

**A short checklist.** Write down R at launch; choose the half-life as a share of the whole run; convert decays with the batch-size rule;
save and audition both copies; and confirm which copy a render script loads before comparing runs.

*Known:* the arithmetic (it is the definition of the average) and the per-batch update in our trainers (code reading, plus the table). *Our
rule of thumb:* the useful range of R and the 5 to 20% rule. *Guessed:* nothing in this section depends on a guess; the non-finite result
rests on two runs.

### Sources (internal, for the editor)
- Skill `sa3-training` section 1 (horizon arithmetic, per-batch updates, batch conversion, the load preference, `SimpleEMA` in `stable_audio_3/training/diffusion.py`).
- `docs/TRAINING.md` D5, D6, F8, F9, F10; `docs/training-findings.md` 2026-09-29 audit (the two non-finite EMA renders).
- Drone-sweep note (THE-FINN, 2026-10-27 DM; training-findings 2026-10-16) for the 55 to 62% figure; it comes from a confounded comparison.
- `EXPERIMENTS.md` onset matrix, EMA against online (2026-10-15).
