# Computational Topology Techniques for Characterizing Time-Series Data

**arXiv 1708.09359v3** · Sanderson, Shugerman, Molnar, Meiss, Bradley (Univ. Colorado Boulder)
**IDA-17** (13th Int. Symposium on Intelligent Data Analysis) · read 2026-08-12 (WINTERMUTE), pp.1–4

I expected this to be redundant with SW1PerS (1307.6188) and the repetitions paper (2505.10004).
**It is not — it supplies the one thing both of those lack, and its demonstration data is
musical instrument audio.**

---

## What it contains

**The cost fix: the witness complex.** Building a simplicial complex on every sample is
prohibitive. A *witness complex* coarse-grains it using a subset of **landmark** points, and —
given density conditions — recovers the correct topology of the underlying set anyway. Their
Figure 2, same data, same ε = 0.073:

| complex | landmarks | triangles |
|---|---|---|
| Čech (all points) | 2000 | **2,770,627** |
| witness, ℓ = 200 | 1/10th | 3,938 |
| witness, ℓ = 50 | 1/40th | **93** |

Roughly a **700× to 30,000× reduction** in complex size.

**The second practical shortcut, and it is the one that surprised me.** Delay reconstruction
preserves *topology* but not *geometry*, and is only guaranteed to be a true embedding if the
delay τ and dimension `d_E` are chosen properly — parameters they call "subjective and sometimes
quite difficult" to estimate for real, finite-precision data. Their point: you can compute the
coarse-grained topology of a **2-D reconstruction that is not a true embedding at all** and still
get useful discrimination. That sidesteps the parameter-estimation step *and* cuts the cost of
everything downstream.

**What it is for.** Characterising and distinguishing dynamical systems from a single scalar
measurement stream, plus change-point / bifurcation detection. Their demonstration: **telling
apart the same note played on different musical instruments**, from real recordings (Fig. 1 is
middle C on a Yamaha upright, 44.1 kHz).

---

## What stays ours

**1 — It removes the blocker I recorded against the other two papers in this batch.** My SW1PerS
note flagged the cost honestly: Rips is superlinear, so that method is per-clip on a landmarked
cloud, "budget it like Audiobox, not like zcr". The witness complex *is* the landmarking, with a
correctness argument and a measured 700–30,000× reduction. Reading the three together: SW1PerS
gives the periodicity score, 2505.10004 gives per-cycle boundaries with linear complexity, and
this gives the coarse-graining that makes point-cloud methods affordable at corpus scale. That
is a usable stack rather than three separate curiosities — and I would not have seen it had I
skipped this as redundant.

**2 — "The same note on different instruments" is a topological timbre discriminator.** That is
a direct hit on a thread we already have: timbre is currently described by `timbral_models`
(8 features) and Audiobox — all spectral/statistical. A topology-of-delay-reconstruction
descriptor is a structurally different account of timbre, computed from the waveform's own
dynamics rather than its spectrum. Given the session's running theme — that our spectral proxies
are foolable, and that Audiobox CE ranked Kim's two favourite checkpoints 1st and 8th of 8 — a
descriptor from a different family is worth having precisely because it fails differently.

**3 — The don't-need-a-true-embedding result is what makes it practical for us.** Choosing τ and
`d_E` per track across 4461 tracks would be exactly the kind of per-item hyperparameter fitting
we cannot afford and would get wrong silently. Being told a 2-D non-embedding still discriminates
is what turns this from a research technique into something schedulable.

**Scope caveats.** 2017, IDA proceedings, tutorial-flavoured: it explains how to apply the ideas
and defers theory to references. Their audio is a single sustained note at 44.1 kHz — **waveform
scale, not our 100 Hz feature streams** — so the instrument-discrimination result does not
transfer to whole-track timeseries without redoing the question. And "distinguishes systems" is
weaker than "yields a control dimension": on Kim's three-part test this is a **descriptor and an
enabler**, not a knob he would ask for by ear. I am filing it as infrastructure for the other
two rather than as a control candidate in its own right.

---

## Status

Read pp.1–4 in detail (abstract, introduction, delay reconstruction, TDA background, witness
complex with the Fig. 2 counts); the experiments skimmed. Nothing implemented. The
stack-with-the-other-two reading and the timbre-descriptor suggestion are my inferences.

**Note to self and to the record:** I nearly skipped this paper as redundant on the strength of
its title and its neighbours. That would have been the third metadata-driven miss of this sweep,
after a wrong filename hid HiPPO and a wrong relevance criterion hid the whole symbolic cluster.
