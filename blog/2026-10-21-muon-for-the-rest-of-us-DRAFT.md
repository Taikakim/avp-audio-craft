<!-- DRAFT 2026-10-21 (WINTERMUTE). Team review requested in the chat the same day:
  - CONTINUITY: theory sections (what Muon does, units, the probe reading, fine-tuning mismatch).
  - THE-FINN: fact audit of every number against its record, and the paper links.
  - GHOST-NOTE: the fine-tuning / DoRA practical points and the starter checklist, from the hands-on side. (Reviewed 2026-10-21 by GHOST-NOTE: checklist item 8 reworded, item 9 added, one sentence in section 5; numbers in sections 5/9 NOT re-verified by me, THE-FINN's audit covers them.)
Every number was taken on 2026-10-21 from: docs/TRAINING.md F1-F30, docs/training-findings.md, EXPERIMENTS.md E5/E6,
DISCOVERIES.md 2026-08-10, papers/knowledge.md, and the test plan B/P sidecars of 2026-10-21 (kuang_plan_B_20261021,
kuang_plan_P_20261017, unit_matched_20261021). Open items before publishing:
  1. The batch-size sweep (effective 64/128/256) is running tonight; section 7 says "pending" and should get its result.
  2. The unit-matched recipe (section 3's fix) is being tested today on two heads; the checklist marks it as our current
     best guess, not a validated default. Update when the onset/air arms read out.
  3. SA3's own pre-training optimizer is not stated in its report (only the post-training one); the text says so.
No checkpoint names, paths or infrastructure below; arm labels (B2, B3) are kept because they are how the results are filed. -->

# Training with Muon, for the Rest of Us: What Five Months of Small Runs Taught Us

Muon is the optimizer everybody started talking about in 2025. It trains language models faster than AdamW, it shows
up in new model releases (Stable Audio 3 uses a Muon and AdamW mix for its post-training), and it is now one flag away in
several trainers. So it is natural to switch it on for your own LoRA or fine-tune and expect things to get better.

We have been doing exactly that since May, on much smaller jobs than the papers: small "control heads" trained from scratch
on music latents, LoRA and DoRA adapters on Stable Audio 3, and a few full fine-tunes, all on one 16 GB consumer GPU
with batch sizes between 1 and 16. Muon helped. It also produced the strangest failures we have had: runs that look
fine on the loss curve and then turn to buzz, runs that never learn at all, and runs that are "cooked" by epoch 7.

This post collects what we know so far, written for people who fine-tune models as a hobby and want to know what to
watch for. It links the papers we used and says where our evidence is thin.

## 1. What Muon does, in one paragraph

A normal optimizer like AdamW moves each weight by an amount that depends on that weight's own gradient history. Muon
works on whole weight matrices. It takes the momentum (a running average of recent gradients) for a matrix and replaces
it with the nearest "orthogonal" matrix, using a few cheap iterations called Newton-Schulz. In plain terms: every
direction in which the matrix could change gets the same step size, big or small, whatever the gradient said about how
important it was. How far the matrix moves is then set almost entirely by the learning rate, not by the gradient. That is
the source of both its speed and most of the trouble below. The original write-up is
[Keller Jordan's Muon post](https://kellerjordan.github.io/posts/muon/).

Muon is only used for 2-D weight matrices. Everything else (biases, norm gains, small output layers, embeddings) is
handed to a second optimizer, usually AdamW, or in some implementations to a simple sign-based step. Keep that split in
mind; it matters more than anything else in this post.

## 2. How much it helps, honestly

A careful comparison of ten optimizers at four model sizes ([Fantastic Optimizers I](https://arxiv.org/abs/2509.02046))
found that matrix optimizers like Muon do beat AdamW, but by about 1.4x in training speed at 0.1B parameters and 1.1x at
1.2B, once AdamW is tuned as carefully as Muon. Earlier claims of 2x came from under-tuned AdamW baselines.

On our small from-scratch heads the gain was larger. Our Muon-based optimizer reached a held-out loss of 0.357 against
AdamW's 0.408 in the same 10 epochs. But when we took it apart, the part doing the work was not the orthogonalisation: it
was Schedule-Free averaging (section 6). With Schedule-Free on, 0.203; with it off, 0.255. A matrix preconditioner
(Shampoo) on top added nothing we could measure.

So: worth having, not magic, and the ingredient that helps may not be the one in the name.

## 3. Lesson one: one learning rate, three different meanings

This is the one that cost us the most time. In our optimizer one learning rate drives three kinds of parameters, and they
move at very different speeds:

| Parameter kind | How far it moves per step, per weight | At lr 1e-2 |
|---|---|---|
| Weight matrices (Muon), width 256 | about lr divided by 16 | about 6e-4 |
| Biases and norm gains (sign step) | about the full lr | about 1e-2 |
| The tiny 256-to-1 output layer | about lr divided by 16 | about 6e-4 |

The matrices moving at lr/16 is why Muon's learning rate looks so high next to AdamW's: our best head setting was lr 1e-2
where AdamW wanted about 3e-4, roughly 30x. For the matrices that is mostly a change of units. For the biases and gains it
is not: at lr 1e-2 they move about 30 times further per step than AdamW would move them.

**What that does.** In one test we ran the same head at lr 3e-2 twice. In run B2 the biases and gains had their own,
lower learning rate (2e-3); in run B3 they shared the 3e-2. B2 trained cleanly (held-out loss 0.189). B3 never learned:
its held-out loss started at 0.57 against B2's 0.37 and rose until the loss turned into NaN in epoch 13. The per-group logs
put the whole failure in the biases and gains: their typical size went from 0.13 (where B2's sat) to 1.8 by step 600 and
69 by step 8,400, while the weight matrices looked the same in both runs.

And the opposite failure, from the same cause: when we lowered the learning rate to keep the biases calm (3e-4), the head
barely learned, because the output layer was now moving 1/16 of an already small step.

**The fix the literature uses.** The [SF-NorMuon paper](https://arxiv.org/abs/2605.23061) rescales the Muon update so
that each weight moves about 0.2 x lr, the same size as an Adam step, and runs biases, gains and small layers on their own
Adam. Then one learning rate means roughly the same thing everywhere, and your AdamW intuition (1e-4 to 1e-3 for a
fine-tune) carries over. We are testing exactly this today.

**For your trainer:** find out which optimizer handles the non-matrix parameters and at what learning rate. If the answer
is "the same lr as Muon", give them their own, lower one.

## 4. Lesson two: watch the size of the weights, not just the loss

Muon's step size is set by the learning rate, not by the gradient, so a weight matrix can keep growing every step while
the loss looks normal. Several of our failures were exactly that, and in every one the weight size ran away before the
loss showed anything:

- The B3 run above: by step 8,400 its biases and gains were about 170 times the size they had in the healthy run at
  the same step, and the loss had not yet gone NaN.
- A small "air band" head at lr 5e-2: its weight matrices grew 15 times in under three epochs, then NaN. Capping the
  biases did not save this one; here the matrices themselves were stepping too far.
- Full fine-tunes of Stable Audio 3: the weights grew steadily until the model's output latents were five times their
  normal size (standard deviation 5.6 instead of about 1.1). By ear: a buzzing, droning sound under everything. The cause
  was weight decay too weak for a Muon-type optimizer to hold the weight size steady.

On that last point, [Muon-SW](https://arxiv.org/abs/2607.23777) shows that with the right constant weight decay Muon's
weight norm settles instead of drifting, and [Hyperball](https://arxiv.org/abs/2606.16899) goes further and fixes the
norm outright. Older background on why weight decay sets the effective step size:
[Rotational Equilibrium](https://arxiv.org/abs/2305.17212) and
[Weight Decay matters more than muP for LR transfer](https://arxiv.org/abs/2510.19093).

**For your trainer:** log the typical size (RMS) of each parameter group every few hundred steps. A group that doubles
within an epoch after warmup is on its way somewhere bad. Our trainer now halves that group's learning rate automatically
when that happens, and stops a run whose held-out loss stays well above its best.

## 5. Lesson three: fine-tuning a model that was pre-trained with Adam

[Can Muon Fine-tune Adam-Pretrained Models?](https://arxiv.org/abs/2605.10468) answers: not as well as Adam, and the reverse
is also true. A model pre-trained with one optimizer ends up in a solution shaped by it; fine-tuning with the other one is
more sensitive to the learning rate, moves the weights 5-7 times further and forgets more, even when its final score is
worse. Two things in that paper matter for hobbyists:

- **LoRA mostly fixes it.** With LoRA the gap shrank by 78%, and LoRA with Muon matched or beat LoRA with Adam. At ranks
  of 128 and above, in their harder cases, it started to degrade again.
- **They never used a constant learning rate:** cosine decay with 3% warmup everywhere.

Our own data agrees in a quieter way. In our LoRA runs under Muon-type steps, the LoRA "A" matrices hardly moved: about
99% of A was unchanged between early and late checkpoints, and A received about 7% of the step. The adapter mostly kept
reading the random slice of its input it started with. Nothing audible went wrong, but it is worth knowing that the two
LoRA factors do not learn evenly under Muon. In practice, if you pick a DoRA or LoRA checkpoint by ear, pick it from the first few epochs and compare it against the next two before trusting the last one.

Which optimizer pre-trained Stable Audio 3 is not stated in its report; the post-training stage used Muon (lr 1e-5) on the
attention and feed-forward matrices and AdamW (lr 1e-6) on the rest, with a decaying schedule
([Stable Audio 3 report](https://arxiv.org/abs/2605.17991)).

## 6. Lesson four: Schedule-Free helps, and does not save you from a high learning rate

Schedule-Free ([Defazio et al.](https://arxiv.org/abs/2405.15682), and the
[ScheduleFree+](https://arxiv.org/abs/2605.19095) version we ported) replaces the learning-rate schedule with an average
of the weights along the way. It was the largest single improvement in our head training (section 2). Two cautions:

- It needs weight decay applied in the right place (on the fast-moving copy of the weights); without it, long runs
  diverge in the SF-NorMuon paper.
- Combined with too high a learning rate it is still too high. Our air-band head diverged at every learning rate above
  1e-2 that we tried (3e-2 to 1e-1), with gradient clipping, earlier damping, an early cosine decay or a doubled batch;
  lr 1e-2 was the ceiling.

A look inside one of our runs explains part of this. We probed the run's own momentum directions at epochs 5, 10 and 20
(the method is from the [SAMuon paper](https://arxiv.org/abs/2608.25990)): would a bigger step along them have lowered the
held-out loss? At no checkpoint did it, in any direction. At epochs 5 and 20 the fresh gradients pointed against the
strongest momentum directions: the run had already overshot and the momentum was lagging. At epoch 10 they agreed again.
The leading directions were swinging back and forth, which is what a step that is slightly too large looks like.

## 7. Lesson five: small batches and Muon

Because Muon gives every direction the same step, it also gives the noisy directions a full step. With a large batch the
noise in the gradient averages out before Muon sees it; with a batch of 1-16, which is what most of us can afford, the
weaker directions are mostly noise. The SAMuon paper found its improvement over Muon grows with batch size, and
[a paper on noise scales for sign and spectral descent](https://arxiv.org/abs/2602.03001) gives the right way to measure
how much batch you need (the classic version for SGD is [McCandlish et al.](https://arxiv.org/abs/1812.06162)).

Our first try at that measurement on a batch-16 run could not separate signal from noise. We are now testing effective
batches of 64, 128 and 256 (built from smaller batches with gradient accumulation, so they fit in 16 GB) at the same
number of epochs. **Result pending; this section will be updated.**

**For your trainer:** gradient accumulation costs no extra memory. If you use Muon at batch 1-4, try accumulating to 16
or more before deciding Muon does not suit your job.

## 8. Lesson six: precision

- **Keep the weights and the optimizer state in fp32 if you can.** If the trained parameters are stored in bf16, a small
  step gets rounded away. In a test on one matrix, bf16 kept only 29% of the weight change at lr 3e-4, 64% at 1e-3 and
  about 92% at 3e-3. That alone can make a high learning rate look "better" for the wrong reason. Schedule-Free's average
  is hit hardest, because it moves by a shrinking fraction each step. Keeping the optimizer state in fp32 cost us 13-21 ms
  per step.
- **Newton-Schulz itself is fine in bf16.** Rounding matters when small numbers are added to big ones (weight updates,
  averages), not inside the orthogonalisation. On our card bf16 Newton-Schulz cut the optimizer step from 323 ms to 101 ms.

## 9. Gadgets that did not help at small batch

Several add-ons are designed around large, clean gradients. At batch 1-16 they turned into something else:

- **Signal-to-noise gates** sat at their own pure-noise level and acted as a fixed cut of the learning rate to about 0.2x.
- **Momentum look-ahead terms** that use the difference between consecutive gradients (MONA) mostly add noise at small
  batch. They come from huge-batch pre-training.
- **Automatic step-size finders** (D-Adaptation) made our DoRA rank-128 runs run away (weight norm 10-17 times its healthy
  value); the same run without it stayed healthy for all 22,000 steps.
- **"Escape velocity"**, a Prodigy-style multiplier that grows the step size over time, kept growing it while a run was
  diverging.
- **A matrix preconditioner** (Shampoo, in the [Mousse](https://arxiv.org/abs/2603.09697) form) measured no gain on our heads;
  Newton-Schulz already equalises most of what it would.
- **Cautious masking** (skip update elements whose sign disagrees with the gradient) with a rescale of the survivors
  inflated the update by about 37% and turned one of our DoRA runs NaN, while the same run without it trained cleanly.
  The rescale is fixed in our optimizer.

One more, specific to DoRA: its per-row "magnitude" parameters started between 0.13 and 0.45 and a fixed-size step (sign
descent) pushed hundreds of them through zero before the run went NaN. Anything that steps by a fixed amount regardless of
a parameter's size is dangerous for small positive scalars.

## 10. How to tell whether a change helped

- **Know your noise floor.** Running the same recipe twice gave held-out losses 0.004 apart for us (changing only the
  number of data-loading workers). Any difference smaller than that is not a result.
- **Compare at equal steps, or say you did not.** Halving the batch at a fixed number of epochs doubles the steps; our
  first "batch 8 is as good as 16" was bought with twice the updates.
- **Early epochs can rule out losers but cannot pick winners.** In one sweep the eventual best setting led only from epoch 8
  of 10; the clear failures were obvious by epoch 2-3.
- **The loss does not hear.** Several of our runs had normal losses and sounded wrong. Listen to checkpoints along the run,
  not only the last one; for one head the last clean-sounding epoch was the third.

## 11. A starter checklist

Our current best guess for a small Muon fine-tune, with the parts we have not yet validated marked:

1. Muon (or NorMuon) on the 2-D weight matrices only; biases, norms, embeddings and small output layers on AdamW with
   their own learning rate.
2. Make the learning rates comparable: scale the Muon update to Adam size (update RMS 0.2 x lr) so that one lr in the
   1e-4 to 1e-3 range works for both groups. *(Being tested.)*
3. Weight decay on the matrices, around 0.05 in the SF-NorMuon recipe; zero on gains and biases.
4. A warmup of a few percent of the run, gradient clipping at 1.0, and either Schedule-Free or a decaying schedule. Never
   a constant learning rate without one of those.
5. fp32 weights and optimizer state; bf16 for the forward pass and Newton-Schulz is fine.
6. Log the weight size per group, and stop or cool down a group that doubles within an epoch.
7. Effective batch of at least 16 via accumulation. *(Bigger batches being tested.)*
8. Keep a checkpoint per epoch and choose by listening (or the equivalent for your data), not by the final step and not by held-out loss alone. In our hands-on runs the held-out loss and our glitch meters both missed the artefacts we heard, and the early epochs or the short low-learning-rate runs often sounded best; an optimizer that moves the weights fast early (Schedule-Free did this to us) can make epoch 2 to 4 the good one and everything later a slow drift into over-trained buzz.
9. If your trainer keeps a smoothed (EMA) copy of the weights, check which set your render script loads. We have rendered a run's starting point by accident because the loader silently preferred the smoothed copy.

## 12. What we do not know yet

- Whether the unit-matched recipe (point 2) removes both of our failure modes at once. Tests are running.
- How large a batch Muon really wants for our jobs. Tests are running.
- Whether these lessons hold for full fine-tunes of large models; most of our clean comparisons are on small heads.
- Why one change of the data-loader worker count moved a result by 0.004.

## Papers

- Keller Jordan, [Muon: An optimizer for hidden layers in neural networks](https://kellerjordan.github.io/posts/muon/) (blog post)
- [Fantastic Optimizers and Where to Find Them, Part I](https://arxiv.org/abs/2509.02046), matrix vs scalar optimizers, fairly tuned
- [Anytime Training with Schedule-Free Spectral Optimization (SF-NorMuon)](https://arxiv.org/abs/2605.23061)
- [Spectral Allocation: Why Muon Outperforms Adam and How to Improve Muon (SAMuon)](https://arxiv.org/abs/2608.25990)
- [Can Muon Fine-tune Adam-Pretrained Models?](https://arxiv.org/abs/2605.10468)
- [Muon-SW: scale weight decay](https://arxiv.org/abs/2607.23777)
- [Hyperball: fixed-norm weight and update constraint for Muon](https://arxiv.org/abs/2606.16899)
- [Adaptive Batch Sizes Using Non-Euclidean Gradient Noise Scales for Stochastic Sign and Spectral Descent](https://arxiv.org/abs/2602.03001)
- McCandlish et al., [An Empirical Model of Large-Batch Training](https://arxiv.org/abs/1812.06162)
- Defazio et al., [The Road Less Scheduled (Schedule-Free)](https://arxiv.org/abs/2405.15682)
- [ScheduleFree+](https://arxiv.org/abs/2605.19095)
- [Mousse: curvature-aware preconditioning for Muon](https://arxiv.org/abs/2603.09697)
- [Rotational Equilibrium: weight decay as effective learning rate](https://arxiv.org/abs/2305.17212)
- [Weight Decay matters more than muP for learning-rate transfer](https://arxiv.org/abs/2510.19093)
- [Stable Audio 3 technical report](https://arxiv.org/abs/2605.17991)
