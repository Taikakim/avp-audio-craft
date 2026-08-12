# HiPPO: Recurrent Memory with Optimal Polynomial Projections

**arXiv 2008.07669v2** (Oct 2020) · Albert Gu\*, Tri Dao\*, Stefano Ermon, Atri Rudra,
Christopher Ré (Stanford / SUNY Buffalo) · NeurIPS 2020 · read 2026-08-12 (WINTERMUTE)

> **⚠ THIS PAPER WAS MIS-FILED.** It arrived in the sweep as
> `arxiv-2008.07669 - Persistence-based summaries (verify title on read).pdf` — a guessed
> title, correctly flagged as unverified by THE-FINN. It is not a topology paper at all. It is
> **HiPPO**, the polynomial-projection memory framework that S4 and Mamba are built on.
> PDF renamed. Had the guessed title been trusted, this would have been read as symbolic-music
> topology and dropped with the rest of that batch as off-lane.

---

## What it contains

**The problem.** Represent the *cumulative history* of a signal online, in bounded memory, as
new data arrives — without a prior on the timescale or sequence length.

**The reframing that does the work.** Memory is posed as **online function approximation**:
given `f(t): ℝ₊ → ℝ`, store its optimal coefficients against a basis, where the approximation
is evaluated with respect to **a measure specifying how much each past time step matters**.
Orthogonal polynomials (OPs) then fall out as the natural basis, and the resulting operator
— projection onto the OP space w.r.t. that measure — admits a **closed-form ODE / linear
recurrence**, so the optimal coefficients update incrementally as the signal is revealed.

**What that unifies.** With one choice of measure the framework *exactly recovers* the Legendre
Memory Unit (fixed-length sliding window); it also explains LSTM/GRU gating as the low-order
extreme of the same approximation.

**HiPPO-LegS (scaled Legendre) — the contribution that matters here.** Choosing a measure that
always covers the function's *entire history* rather than a sliding window yields a mechanism
with, by their account: **invariance to input timescale**, no hyperparameter or prior on
sequence length, asymptotically more efficient updates, and **bounded gradients**.

**Results (2020-era, RNN benchmarks).** Permuted MNIST 98.3% (SoTA at the time, beating models
with global context); on a trajectory-classification task testing robustness to *unseen
timescales and missing data*, HiPPO-LegS beats RNN and neural-ODE baselines by 25–40% accuracy
— the timescale-generalisation claim is the one they actually stress-test.

---

## What stays ours

**1 — Timescale invariance is a named solution to a problem we currently solve by brute force.**
Our whole length regime is hand-pinned: MASTER §5 requires crop lengths in multiples of 256
frames (T=512/1024/2048/4096) because ragged lengths map badly onto the kernels, models trained
at one T behave differently at another, and the entire length-variant eval exists to compare
native-length against the 20 s grid. We handle timescale by *fixing* it everywhere and then
rendering separate ladders. HiPPO-LegS's central claim is exactly that this hyperparameter
should not need to exist. That does not port for free — but it is the first thing in the sweep
that addresses our T problem at the level of the representation instead of the schedule.

**2 — A principled replacement for the resampling we already do crudely.** The whole-track
consumer (`whole_track_target_source.py`) slices `[start,end]` from a 100 Hz timeseries and
`resample_axis0`s it to whatever `n_frames` the target grid wants. That is exactly "compress an
arbitrary-length signal into a fixed-size representation", done by interpolation. HiPPO is the
same operation with an optimality criterion and an online update rule. For conditioning signals
of arbitrary length — the variable-offset crop case that whole-track npz exists to serve — that
is a candidate upgrade with theory attached, not just a smoother interpolant.

**3 — It is the ancestor of what we already have a row for.** STAR-VAE (2606.23064, already in
knowledge.md) uses a CNN+**Mamba** bottleneck; Mamba descends from S4, and S4 descends from
this. Reading HiPPO gives the state-space line its foundation rather than treating Mamba as a
black box the next time it appears in a paper we evaluate.

**Caveats, plainly.** 2020, RNN-era, benchmarked on permuted MNIST and trajectory
classification — **no generative modelling, no audio, no diffusion**. We are not building an
RNN, and nothing here should be read as "swap in Mamba". The transferable object is the
*representation* (bounded-memory optimal projection of a continuous history, with a timescale
-free measure), not the architecture that wrapped it in 2020.

---

## Status

Read pp.1–2 in detail (abstract, introduction, framework setup); the theory sections (§2–3) and
experiments (§4) skimmed only. Load-bearing claims quoted above are from the abstract and
introduction, verified at the page. **The renaming is the immediately actionable output;** the
relevance argument is my inference and is untested.

**Follow-up worth someone's time:** F should re-check whether any *other* file in
`Prospective Unchecked/` carries a guessed rather than verified title. This one was flagged;
the question is whether the flag was applied consistently, because the failure mode here is
silent — a wrong title routes a paper to the wrong reader and gets it dismissed by category.
