# Review of Antigravity's walkthrough.md and the revised implementation_plan.md (2026-10-27)

Reviewer: CONTINUITY, at Kim's request ("review these again"). Files: `~/.gemini/antigravity/brain/62fc5213-.../walkthrough.md` (08:19) and
`implementation_plan.md` (08:12). The plan file is no longer the V7 synth plan I reviewed earlier: it is now a different plan (SA3 drum
separation from scratch, rank 64/128, optimizer shootout). The walkthrough covers V7 (sections 1-5, 7) and drum separation (6, 8).
Checked against: `lumi/vendor/stable_audio_tools/training/fusion_groups.py`, `stable-audio-3/scripts/train_lora.py`, our sidecars for
arXiv 2609.07226 and 2609.29320, `docs/drum-separation-benchmarks-2026-10-22.md`, OWNERSHIP.md, EXPERIMENTS.md. Not re-run: any experiment.

## Verdict
The V7 section is a more careful write-up than before but still states a failed replication as a physical law. The drum-separation
claims ("decisive winner") are not supported by the numbers in the same table. The new plan's central comparison (optimizer effect) is
confounded in at least four ways, one of which I verified in the code. Do not launch Arms 0-3 as written.

## A. Walkthrough, V7 sections
1. **My earlier audit points are not addressed.** Still n = 20, 0 dB only, one generative draw each; top-1 retrieval never computed; "+23% to
   +40%" still printed, and only +23.3% (parameter MSE) and +11% (cutoff) follow from the table. The spec said 100 patches x 3 SNRs.
2. **The new pitch probe weakens the Step 1 model, not the idea.** Ridge R^2 for MIDI pitch: clean 0.5231, raw mixture 0.4132, cue-gated
   0.4747. The cue-gated code carries more pitch than the raw mixture (the walkthrough's own "-14.9% suppression"). The paper's extractor cut
   pitch R^2 from 0.783 to 0.263. Add that the selectivity loss ended at 0.0001 (a hinge that is almost never active) and the oracle cue gave no
   gain (0.1451 against 0.1416): the trained gate probably does not do what the paper's does. The null tests this implementation.
3. **Section 4 "root cause" is stated as fact and is a hypothesis.** "A scalar temporal gate cannot separate a kick and a bass on the same
   sixteenth" and "5 dB of residual kick forces the cutoff open" have no measurement behind them. It also misdescribes the paper's data:
   NSynth is single notes and Slakh is rendered from MIDI, not "acoustic instruments with natural solo moments". The full CLAP + LoRA method
   was never run.
4. **Section 7 (Sony briefing) disagrees with our own paper notes on both papers.**
   - 2609.07226 (Ikemiya/Liao/Mitsufuji): our sidecar (THE-FINN, read in full) says it extends an existing separator (BS-RoFormer, SCNet) so
     it takes all K stem estimates as input, refines them over a few iterations, and projects them to sum to the mix after each one. The
     walkthrough describes "a joint MIMO flow ... via Softmax or complex-valued unitary constraint". That is not what the note says.
   - 2609.29320 (Hayes, Sony CSL): the title is "joint distribution flow matching", a rectified flow over parameters and audio with two time
     variables, trainable on unlabelled audio. The walkthrough calls it "Joint Differentiable Flow Inversion", a "differentiable surrogate
     synthesizer" with a contrastive representation, and says it confirms that pooling fails under polyphony. I found nothing like that in the
     sidecar's summary. (I read the sidecar openings, not the paper.) Fix or remove section 7 and re-read the sidecars before citing.
5. **The decision to terminate** belongs to the line's owner (WINTERMUTE, OWNERSHIP.md) and Kim. W has not yet answered my earlier note.

## B. Walkthrough, section 6: the LR brackets
1. **No control.** Both brackets continue from step 6000 for 3000 more steps, against a baseline with no extra training. Missing arm: 3000
   more steps at the original 1e-4. Without it, "LR 2e-4 is the winner" and "the 33M inlet had under-converged at 1e-4" are untested; the data
   show only that more training helped.
2. **Selective reading of the table.** For the 2e-4 bracket mean LSD gets worse (21.38 to 23.78 dB), snare LSD much worse (10.61 to 14.68),
   mean onset F1 flat (0.575 to 0.573), snare SI-SDR flat. The gains are in SI-SDR for kick and hi-hat.
3. **Hi-hat at -35.6 dB SI-SDR is a failed separation, not a leap.** An estimate at -35 to -47 dB SI-SDR has almost no relation to the
   reference, and SI-SDR is a poor meter in that range. Add a measure that fails loudly there: envelope correlation or onset F1 per stem.
4. **On the real studio tracks it is not the winner.** Kick SI-SDR 4.72 (2e-4) against 4.88 (baseline) on Acid Alien and 0.84 against
   0.96 on Black Moon, and BS-RoFormer is at +18.13 and +17.22 dB on two of the three tracks against -6.6 dB for the model. The validation
   crops are paired synthetic mixes; the real task is far below the existing separator (see also the 2026-10-22 benchmark doc).
5. n = 16 crops, one run per arm, no noise estimate.

## C. The new implementation plan (from-scratch rank and optimizer shootout)
1. **The optimizer comparison is confounded.** Arm 1 against Arm 0 differs in (a) optimizer on the 33M inlet, (b) optimizer on the LoRA
   (Schedule-Free AdamW against plain AdamW), (c) schedule (500 warmup then constant, against WSD decay), (d) weight decay, below. The plan
   says this "directly measure[s] the optimizer effect at constant rank"; it does not. Arm 2 against Arm 1 changes NorMuon, Schedule-Free
   and the learning rate together. A minimal fix: add an arm with AdamW on the inlet plus Schedule-Free, and one with NorMuon but WSD.
2. **Weight decay differs between arms (verified in code).** With `--optimizer fusion`, `--weight_decay` sets only `spectral_wd`, the decay
   on the 33M inlet matrices (`train_lora.py:613-625`); `scalar_wd` stays 0.0 (`fusion_groups.py:79`). So in Arms 1-3 the 84.6M to
   169.2M LoRA parameters get no decay, while Arm 0 (plain AdamW, 0.01) decays everything. Given that missing weight decay was a root cause
   of our drone runaway, log the weight norm per group in every arm and set the decays equal on purpose.
3. **Budget mismatch.** Four-thousand-step from-scratch arms are compared with a rank-32 baseline at 6000 steps (plus 3000). Rank must be
   isolated with a rank-32 from-scratch arm at 4000 steps.
4. **Untuned learning rates.** Three learning rates (1e-3, 3e-4, 2e-4) are picked once. The guide itself says learning rates do not carry
   between optimizers, and TRAINING D4 says the same for control adapters. Arm 0's 2e-4 came from a continuation run, not from scratch. A
   three-point bracket per optimizer, as in E12, is the minimum for a fair shootout.
5. **Wrong attribution to the guide.** The plan says the guide's section 7 identifies a "low-rank Muon row-freeze". Section 7 reports that
   LoRA A barely moves (99.2% of its row space unchanged in one run) and says it has no AdamW control. The 128 cut-off is the code constant
   `MIN_SPECTRAL_DIM = 128`, not a finding. The routing is right (rank 64 goes to the scalar path, rank 128 needs `--force-scalar`).
6. **Single seed per arm.** We measured about 0.01 run-to-run noise on the heads; no noise estimate exists for SI-SDR here. Repeat Arm 0
   with a second seed.
7. **Housekeeping.** Stem separation is "unclaimed" in OWNERSHIP.md and I found no EXPERIMENTS.md entry for this line (only the
   2026-10-22 benchmark doc). Register it with a purpose, a hypothesis and a kill rule, name an owner, and say whether the VRAM and speed
   numbers (9.8 GB, 11.5 GB, 0.88 and 0.72 it/s) were measured. The listening consoles are a good idea; the ear should be the decision.

## What is sound
The parameter counts check out (1536x256 + 1536x1536 per block over 12 blocks = 33,030,144, plus 36,864 biases = 33,067,008). The routing
logic matches the code. Using Misc/gpu_guard.sh and putting the cheap tests first are right. Wiener reconciliation adding SI-SDR is
plausible and consistent with the MIMO paper's mixture-consistency idea, but "guarantees exact bounding" overstates it.
