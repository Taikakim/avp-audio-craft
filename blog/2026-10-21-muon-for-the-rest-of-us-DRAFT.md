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
No checkpoint names, paths or infrastructure below; arm labels (B2, B3) are kept because they are how the results are filed.
Fact audit by THE-FINN 2026-10-21 (W's version is commit 65c5e98; the changes are listed below):
  - Papers: all 14 arXiv ids resolve to the cited papers; titles in the list now match the arXiv titles. Hyperball is "Fantastic
    Pretraining Optimizers ... II"; Muon-SW is "Scale Weight Decay and Train Better".
  - Fixed: Muon-SW was described as showing a constant decay makes the norm settle; the paper says constant decay makes the norm
    SHRINK and its scaled decay settles it. Section 2 mixed two datasets (0.357/0.408 is the 5,401-crop set; 0.203/0.255 is the
    larger set). Section 3: B2 at lr 3e-2 (0.189) is not better than the same head at 1e-2 (0.182); B3's loss wandered 0.57-0.95
    before the NaN; matrices stayed within ~a third of B2's, not "the same". Section 4: SA3 full-fine-tune drone came from weight
    decay of ZERO, not "too weak". Section 6: P1 at epoch 10 had one of three held-out sets improve, so "no checkpoint" was
    too strong; the 1e-2 "ceiling" has no tests between 1e-2 and 3e-2. Section 11 item 2 lr range is a guess, not from the paper.
    The watchdog is optional and new; batch sizes were 1-64, not 1-16. Newton-Schulz bf16: we measured speed, not quality.
  - Checked and correct: 1.4x/1.1x, 0.357/0.408, 0.203/0.255, lr/16 and 30x, B2/B3 sizes (1.8, 69, 170x), air-head 15x growth and
    NaN in epoch 3, bf16 29/64/92%, 323->101 ms, 13-21 ms, noise floor 0.004, LoRA-A 99%/7%, cautious +37%, D-Adaptation 10-17x and
    22,000 steps, SNR gate ~0.2x, SA3 post-training Muon 1e-5 / AdamW 1e-6, SF-NorMuon 0.2 x lr and wd 0.05, 78% and 5.6-7.4x.
  - Not checked by THE-FINN: SAMuon "gain grows with batch" (from papers/knowledge.md only); the "13-21 ms" and "323 -> 101 ms"
    figures (from WINTERMUTE's journal, not re-measured); anything in sections 7 and 12 that is a plan. -->

# Training with Muon, for the Rest of Us: What Five Months of Small Runs Taught Us

Muon is the optimizer everybody started talking about in 2025. It trains language models faster than AdamW, it shows
up in new model releases (Stable Audio 3 uses a Muon and AdamW mix for its post-training), and it is now one flag away in
several trainers. So it is natural to switch it on for your own LoRA or fine-tune and expect things to get better.

We have been doing exactly that since May, on much smaller jobs than the papers: small "control heads" trained from scratch
on music latents, LoRA and DoRA adapters on Stable Audio 3, and a few full fine-tunes, all on one 16 GB consumer GPU
with batch sizes from 1 to 64 (the head runs mostly 16 to 32). Muon helped. It also produced the strangest failures we have had: runs that look
fine on the loss curve and then turn to buzz, runs that never learn at all, and runs that are "cooked" by epoch 7.

This post collects what we know so far, written for people who fine-tune models as a hobby and want to know what to
watch for. It links the papers we used and says where our evidence is thin.

## 1. What Muon does, in one paragraph

A normal optimizer like AdamW moves each weight by an amount that depends on that weight's own gradient history. Muon
works on whole weight matrices. It takes the momentum (a running average of recent gradients) for a matrix and replaces
it with (approximately) the nearest "orthogonal" matrix, using a few cheap iterations called Newton-Schulz. In plain
terms: the gradient still decides which directions the matrix changes in, but every one of those directions gets about
the same step size, however strong or weak the gradient was along it. How far the matrix moves is then set almost entirely
by the learning rate, not by the size of the gradient. That is
the source of both its speed and most of the trouble below. The original write-up is
[Keller Jordan's Muon post](https://kellerjordan.github.io/posts/muon/).

Muon is only used for 2-D weight matrices. Everything else (biases, norm gains, small output layers, embeddings) is
handed to a second optimizer, usually AdamW, or in some implementations to a simple sign-based step. Keep that split in
mind; it matters more than anything else in this post.

## 2. How much it helps, honestly

A careful comparison of ten optimizers at four model sizes ([Fantastic Pretraining Optimizers and Where to Find Them](https://arxiv.org/abs/2509.02046))
found that matrix optimizers like Muon do beat AdamW, but by about 1.4x in training speed at 0.1B parameters and 1.1x at
1.2B, once AdamW is tuned as carefully as Muon. Earlier claims of 1.4x to 2x came from baselines that were tuned less
carefully.

On our small from-scratch heads the gain was larger. On a first set of 5,401 music-latent crops (10 epochs, one seed), our
Muon-based optimizer reached a held-out loss of 0.357 against AdamW's 0.408. But when we took it apart on a larger set
(11 settings, 10 epochs), the part doing the work was not the orthogonalisation: it was Schedule-Free averaging
(section 6). With Schedule-Free on, the held-out loss was 0.20 to 0.21. With it off it was 0.255, the same as AdamW's
0.25 to 0.26. A matrix preconditioner (Shampoo) on top added nothing we could measure. All of these are single runs
with a noise floor of about 0.004 (section 10).

So: worth having, not magic, and the ingredient that helps may not be the one in the name.

## 3. Lesson one: one learning rate, three different meanings

This is the one that cost us the most time. In our optimizer one learning rate drives three kinds of parameters, and they
move at very different speeds:

| Parameter kind | How far it moves per step, per weight | At lr 1e-2 |
|---|---|---|
| Weight matrices (Muon), width 256 | about lr divided by 16 | about 6e-4 |
| Biases and norm gains (sign step) | about the full lr | about 1e-2 |
| The tiny 256-to-1 output layer (our routing; the usual split hands it to the second optimizer) | about lr divided by 16 | about 6e-4 |

The matrices moving at lr/16 is why Muon's learning rate looks so high next to AdamW's: our best head setting was lr 1e-2
where AdamW wanted about 3e-4, roughly 30x. For the matrices that is mostly a change of units. For the biases and gains it
is not: at lr 1e-2 they move about 30 times further per step than AdamW would move them.

These numbers are for small heads trained from scratch with an unscaled Muon update, where "lr divided by 16" holds. Other implementations (the Moonlight variant, for one) already rescale the update to Adam's size; there the matrices move more per step at the same lr (about 3x at width 256), and AdamW-like learning rates carry over. And do not copy lr 1e-2 to a LoRA or a fine-tune: Stable Audio 3's own post-training used 1e-5 for its Muon matrices.

**What that does.** In one test we ran the same head at lr 3e-2 twice. In run B2 the biases and gains had their own,
lower learning rate (2e-3); in run B3 they shared the 3e-2. B2 trained cleanly (held-out loss 0.189 at the end; the same head at lr 1e-2 reached 0.182, so the higher
rate bought nothing). B3 never got below 0.57: its held-out loss started at 0.57 against B2's 0.37, wandered between 0.57
and 0.95, and turned into NaN in epoch 13. The per-group logs put the failure in the biases and gains: their typical size
(RMS) went from 0.13 (where B2's sat) to 1.8 by step 600 and 69 by step 8,400, while the weight matrices stayed within
about a third of B2's size. Each arm is one run, so this is a clear failure of one setting, not a measured effect size.

And the opposite failure, from the same cause: when we lowered the learning rate to keep the biases calm (3e-4), the head
barely learned, because the matrices and the output layer were now each moving about 2e-5 per weight per step.

**The fix the literature uses.** The [SF-NorMuon paper](https://arxiv.org/abs/2605.23061) rescales the Muon update so
that each weight moves about 0.2 x lr, the same size as an Adam step, and runs biases, gains and small layers on their own
Adam. The aim is that one learning rate means roughly the same thing everywhere, so AdamW-style learning rates carry over. (The
paper's own best setting was lr 0.01, for language-model pretraining at 125M and 772M parameters; what range suits a
fine-tune is our guess.)

First result, on the small head that used to diverge at every learning rate above 1e-2: with the update rescaled this way
and the biases and gains on Adam, it trained cleanly for all 25 epochs at lr 3e-3 and matched the best loss of the old
recipe (0.0207 against 0.0206). Read the units before reading anything more into that: at lr 3e-3 the rescaled update moves
the matrices 0.2 x 3e-3 = 6e-4 per weight, the same as the old recipe at lr 1e-2 (1e-2 / 16). So this is the old best
setting expressed in new units, with the biases and gains now on Adam at 3e-3 instead of a sign step at 1e-2. It shows
the conversion works, not that the usable range got wider. Its weight matrices grew from 0.026 to about 0.107 RMS and then
levelled off (weight decay, the late cosine decay and Schedule-Free averaging all act there; we have not separated them).
The run also had the learning-rate watchdog (it never fired), gradient clipping at 1.0 and escape velocity switched off. One
run, one head; the same test on a second head is running.

**For your trainer:** find out which optimizer handles the non-matrix parameters and at what learning rate. If the answer
is "the same lr as Muon", give them their own, lower one.

## 4. Lesson two: watch the size of the weights, not just the loss

Muon's step size is set by the learning rate, not by the gradient, so a weight matrix can keep growing every step while
the loss looks normal. Several of our failures were exactly that, and in every one the weight size ran away before the
loss showed anything:

- The B3 run above: by step 8,400 its biases and gains were about 170 times the size they had in the healthy run at
  the same step, and the loss had not yet gone NaN.
- A small "air band" head at lr 5e-2: in a rerun with the bias group capped, its weight matrices grew 15 times in about
  three epochs (460 steps), then NaN in epoch 3. Capping the biases did not save this one; the matrices themselves were
  stepping too far.
- Full fine-tunes of Stable Audio 3: the model's output latents grew to five times their normal size (standard
  deviation 5.6 instead of about 1.1). By ear: a buzzing, droning sound under everything. The cause was weight decay of
  zero: the optimizer's default was 0, our full fine-tune path never set it, and nothing else held the weight size
  steady.

On that last point: weight decay is what holds the weight size in place, and with a Muon-type optimizer nothing else
does. [Muon-SW](https://arxiv.org/abs/2607.23777) works out where the weight norm settles under decay and scales the
decay with the learning rate so that it settles at a constant (their tests are language-model pretraining).
[Hyperball](https://arxiv.org/abs/2606.16899) goes further and fixes the norm outright; on our adapters we measured that
it does not work as a drop-in, because a zero-initialised adapter matrix has norm zero and so never moves. Older
background on why weight decay sets the effective step size:
[Rotational Equilibrium](https://arxiv.org/abs/2305.17212) and
[Weight Decay may matter more than muP for LR transfer](https://arxiv.org/abs/2510.19093).

**For your trainer:** log the typical size (RMS) of each parameter group every few hundred steps. A group that doubles
within an epoch after warmup is on its way somewhere bad. Our head trainer has an option (off by default, added on 2026-10-21 and not yet used in a
reported result) that halves a group's learning rate when its weight size grows by a set factor within an epoch. It also
stops a run by default when its held-out loss stays above 1.5 times its best for two epochs.

## 5. Lesson three: fine-tuning a model that was pre-trained with Adam

[Can Muon Fine-tune Adam-Pretrained Models?](https://arxiv.org/abs/2605.10468) answers: not as well as Adam, and the reverse
is also true. A model pre-trained with one optimizer ends up in a solution shaped by it; fine-tuning with the other one is
more sensitive to the learning rate, forgets more, and on the math and code tasks Muon's full fine-tuning moves the weights 5.6 to 7.4 times further from the pretrained ones (cosine distance) than Adam's does. Under LoRA this reverses: Muon moves them only 0.2 to 0.8 times as far, and where the mismatch is mild (commonsense) it moves them less even in full fine-tuning. The paper's Muon is the Moonlight variant, whose update is already rescaled to Adam's size, so its learning rates are in Adam-like units (the unit change section 3 describes). Two things in that paper matter for hobbyists:

- **LoRA mostly fixes it.** With LoRA the perplexity gap shrank by 78% for Adam-pretrained models (39% for Muon-pretrained
  ones). In their strongest-mismatch case LoRA with Muon beat LoRA with Adam at low and moderate ranks, and degraded at
  high ranks as the update starts to look like full fine-tuning.
- **They never used a constant learning rate:** cosine decay with 3% warmup everywhere.

Our own data agrees in a quieter way. In our LoRA runs under Muon-type steps, the LoRA "A" matrices hardly moved: about
99% of A was unchanged between early and late checkpoints, and A received about 7% of the step's energy. The adapter mostly kept
reading the random slice of its input it started with. Nothing audible went wrong, but it is worth knowing that the two
LoRA factors do not learn evenly under Muon. We have no Adam control for this, and the same imbalance is known from plain-Adam LoRA (the LoRA+ line of work: A acts as a fixed random projection and B does most of the learning), so do not read it as a Muon-specific effect. It does fit the paper's finding that Muon moves LoRA weights less than Adam does. In practice, if you pick a DoRA or LoRA checkpoint by ear, pick it from the first few epochs and compare it against the next two before trusting the last one.

Which optimizer pre-trained Stable Audio 3 is not stated in its report; the post-training stage used Muon (lr 1e-5) on the
attention and feed-forward matrices and AdamW (lr 1e-6) on the rest, with a decaying schedule
([Stable Audio 3 report](https://arxiv.org/abs/2605.17991)).

## 6. Lesson four: Schedule-Free helps, and does not save you from a high learning rate

Schedule-Free ([Defazio et al.](https://arxiv.org/abs/2405.15682), and the
[ScheduleFree+](https://arxiv.org/abs/2605.19095) version we ported) replaces the learning-rate schedule with an average
of the weights along the way. It was the largest single improvement in our head training (section 2). Two cautions:

- It needs weight decay applied in the right place (on the fast-moving copy of the weights); the SF-NorMuon paper finds
  this essential for stability over long runs.
- Combined with too high a learning rate it is still too high. Our air-band head diverged at every learning rate above
  1e-2 that we tried (5e-2 and 1e-1 at batch 32, 3e-2 at batch 64), with gradient clipping, earlier damping, an early
  cosine decay or a doubled batch; these delayed the blow-up but did not stop it. Giving the biases and gains their own
  low learning rate (the fix from section 3) did not stop it either: there the weight matrices ran away (section 4). We never tried values between 1e-2 and
  3e-2, so 1e-2 is the highest setting that worked, not a measured ceiling.

We also looked inside one run, with a probe from the [SAMuon paper](https://arxiv.org/abs/2608.25990): at epochs 5, 10
and 20, would a bigger step along the run's own momentum directions have lowered the held-out loss? At epochs 5 and 20,
no: every direction we tried raised the held-out loss from the smallest step on, on all three held-out sets. At epoch 10,
one of three held-out sets (64 crops each) improved and the other two got worse. And at epochs 5 and 20 the fresh
gradients pointed against the strongest momentum directions, while at epoch 10 they agreed with them.

We first read that as a step that is too large. It is weaker evidence than it looks. We probed at the point where
Schedule-Free evaluates its gradient, which sits close to the averaged weights, and Schedule-Free is built so that its fast
copy of the weights swings across the valley while the average sits near the bottom. "No bigger step helps from near the
average" and "the gradient keeps changing sides" are what a working Schedule-Free run should look like, so this probe
cannot tell "too large a step" from "the averaging doing its job". It also differs from the SAMuon paper, which found
that only the strongest direction sits at its limit and the rest would tolerate about five times more; on our run no group
of directions did. A probe from the fast copy of the weights would separate the two readings; we have not run it.

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
  per step in the same test.
- **Newton-Schulz in bf16 is probably fine.** Rounding matters when small numbers are added to big ones (weight updates,
  averages), not inside the orthogonalisation, and other Muon implementations (Dion, the SF-NorMuon reference code) run
  it in bf16. On our card, switching Newton-Schulz to bf16 cut the optimizer update from 323 ms to 101 ms per step in a
  400-step test; we measured the speed there, not the effect on quality.

## 9. Gadgets that did not help at small batch

Several add-ons are designed around large, clean gradients. At batch 1-16 they turned into something else:

- **Signal-to-noise gates** sat at their own pure-noise level and acted as a fixed cut of the learning rate to about 0.2x.
- **Momentum look-ahead terms** that use the difference between consecutive gradients (MONA). Our reading is that at
  small batch the difference is mostly noise; they come from huge-batch pre-training, and our one comparison was worse than
  AdamW, but we never ran a clean test.
- **Automatic step-size finders** (D-Adaptation) made our DoRA rank-128 runs run away (global norm 10-17 times its healthy
  value, in three of four attempts); the one run without it stayed healthy for all 22,000 steps.
- **"Escape velocity"**, a Prodigy-style multiplier that grows the step size over time, raised the
  step by a factor of 1.0 to 1.6 in B3 while that run was diverging.
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
3. Weight decay on the matrices, around 0.05 in the SF-NorMuon recipe (applied to the fast copy of the weights); we use zero on gains and biases.
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
- [Fantastic Pretraining Optimizers and Where to Find Them](https://arxiv.org/abs/2509.02046), matrix vs scalar optimizers, fairly tuned
- [Anytime Training with Schedule-Free Spectral Optimization (SF-NorMuon)](https://arxiv.org/abs/2605.23061)
- [Spectral Allocation: Why Muon Outperforms Adam and How to Improve Muon (SAMuon)](https://arxiv.org/abs/2608.25990)
- [Can Muon Fine-tune Adam-Pretrained Models?](https://arxiv.org/abs/2605.10468)
- [Scale Weight Decay and Train Better (Muon-SW)](https://arxiv.org/abs/2607.23777)
- [Fantastic Pretraining Optimizers and Where to Find Them II: Hyperball Optimization](https://arxiv.org/abs/2606.16899), fixed-norm weight and update constraint for Muon
- [Adaptive Batch Sizes Using Non-Euclidean Gradient Noise Scales for Stochastic Sign and Spectral Descent](https://arxiv.org/abs/2602.03001)
- McCandlish et al., [An Empirical Model of Large-Batch Training](https://arxiv.org/abs/1812.06162)
- Defazio et al., [The Road Less Scheduled (Schedule-Free)](https://arxiv.org/abs/2405.15682)
- [ScheduleFree+](https://arxiv.org/abs/2605.19095)
- [Mousse: Rectifying the Geometry of Muon with Curvature-Aware Preconditioning](https://arxiv.org/abs/2603.09697)
- [Rotational Equilibrium: weight decay as effective learning rate](https://arxiv.org/abs/2305.17212)
- [Weight Decay may matter more than muP for Learning Rate Transfer in Practice](https://arxiv.org/abs/2510.19093)
- [Stable Audio 3 technical report](https://arxiv.org/abs/2605.17991)
