# Gemini Deep-Research Brief — Encoding *musical movement* as a conditioning signal for generative audio

**Author:** CONTINUITY, 2026-08-11 · **For:** Kim to run as a Gemini deep-research prompt.
**How to use:** paste the "BRIEF FOR GEMINI" block below. The framing above it is for us, not Gemini.
**Briefing discipline (house rule):** the block gives Gemini *problem + phenomenology + external
anchor terms to verify and exceed* — it deliberately contains **none of our own code, docstrings,
or internal findings**, so the report can't close the loop and cite our own notes back as if they
were external literature. Anchor names are labelled "starting points to verify," not conclusions.

---

## Why we're asking (context for us)

Two motivations converge:

1. **Zach Evans' suggestion (SA3 author):** instead of chasing a "melodic dataset," try *prepend-cond
   conditioning on melodies* with **CFG dropout**, trained on a large dataset so it learns the
   melody→audio mapping rather than memorising. Our model already exposes a native prepend-conditioning
   path and a lightweight per-frame adapter mechanism, so this is buildable — the open question is
   **what the melodic/movement signal should be.**
2. **Kim's deeper question:** the identity of a piece — what makes a restyle still *recognisable* — lives
   in its **movement**: the melody's shape, the harmonic trajectory, the way the present moment depends
   on what came before. He wants descriptors that (a) capture that movement, (b) ideally **don't change
   under transposition or time-shift**, and (c) can come from **any field** (music theory, MIR,
   musicology, mathematics — not just AI), because *any* metric can serve as a conditioner, possibly even
   as a small adapter target.

The end use: condition a music diffusion model on such a signal during training (with CFG dropout), then
at inference **hold the movement signal fixed while varying style via text** — a disentangled
"same tune / harmonic journey, new sound" control that plain audio-to-audio (noise-init/SDEdit) cannot
give (it either changes too little, collapses to a drone or a short repeating loop, or loses the
original entirely).

## Deliverable we want back

A **survey + a ranked, conditioner-oriented shortlist**, not a generic overview. The single most valuable
artifact is a **comparison table** of candidate descriptors scored on conditioning suitability (defined in
Q5), backed by **primary references** for every non-obvious claim.

---

## ================= BRIEF FOR GEMINI (paste from here) =================

**Task:** A rigorous, reference-backed research survey on **representations of "musical movement" that could
serve as conditioning signals for a generative music model.** I care about representations from *any*
discipline — music information retrieval, music theory, musicology, mathematics, signal processing — not
only machine learning. For every substantive claim, cite a **primary source** (paper, book, or thesis) and
distinguish *established results* from *proposals/single-paper claims*.

**Setting (so you can judge relevance):** I train a latent-diffusion music generator and can feed it an
extra per-frame (streaming) or per-segment conditioning vector, trained with classifier-free-guidance
dropout, so at generation time I can hold that vector fixed while changing timbre/style by text prompt. The
goal is to preserve the *identity-bearing movement* of a piece (its melody shape and harmonic trajectory)
while restyling everything else. The conditioning vector can be any well-defined musical metric; it does
not need to be learned. Cheap-to-compute, low-dimensional, and with useful **invariances** is ideal.

Answer the following, in order.

**Q1 — Melody / structure conditioning in generative music models (state of the art).**
How have generative audio or symbolic-music models been conditioned on a melody or structural signal such
that the output follows the signal while style is set separately? Cover: (a) the **signal representations**
used (e.g. chromagram, extracted dominant-melody f0 contour, MIDI/piano-roll, learned melody embeddings,
self-similarity/structure) — *starting points to verify and go beyond, not a closed list*; (b) the
**injection mechanisms** (cross-attention, sequence/prepend conditioning, additive/FiLM, ControlNet-style
side networks); (c) how **CFG dropout** is applied to such conditioning, and what dropout rates or curricula
are reported; (d) what is known about **overfitting / memorisation** when melody-conditioning on small vs
large corpora, and mitigations (data scale, augmentation, deliberately *invariant or bottlenecked*
conditioning signals that prevent the model copying the source); (e) documented **failure modes** (e.g.
degenerate repetition/looping, drone-like collapse, ignoring the condition) and what fixed them.

**Q2 — Transposition- AND time-shift-invariant encodings of melody/movement.**
I want a vector (or per-frame vector sequence) capturing the *shape* of musical movement that is **invariant
(or equivariant in a usable way) to pitch transposition and to time translation.** Survey representations
with these properties across MIR, music theory, and mathematics, including at least: melodic **contour**
encodings (step/leap, Parsons code, gradient/derivative-of-pitch); **interval-based / relative-pitch**
encodings and interval histograms; the **Fourier/DFT analysis of pitch-class distributions** (transposition
acts as a phase rotation, so coefficient *magnitudes* are transposition-invariant) and the associated
**tonal-interval / tonal-centroid** vectors; **self-similarity / recurrence-matrix** descriptors (invariant
to transposition and tempo); **time–frequency scattering** transforms and **joint time–frequency
scattering** (translation-invariance plus stability to time-warping/deformation); and any **group-theoretic
/ equivariant** formulations treating pitch-class as the cyclic group Z₁₂ and time as translation. For each:
state precisely **what it is invariant to and what movement it preserves**, its natural **distance metric**,
its **dimensionality**, its **compute cost**, and whether it is **per-frame/streamable or per-segment**.

**Q3 — "Memoryful" harmonic descriptors: where the present carries the past.**
I'm specifically interested in descriptors where the value *now* depends on prior context — e.g. the current
chord or key means something different depending on what preceded it (a dominant chord resolves an
expectation set up earlier). Survey: **context-dependent key/tonality tracking** (key-finding with
memory/decay, Bayesian or HMM key trackers); **tonal tension** models that integrate a harmonic trajectory
(spiral-array tension ribbons, tonal-pitch-space distance, tonal attraction/voice-leading tension);
**expectation / surprisal / information-content** models of melody and harmony (statistical or predictive
models that assign each event an information content *given its context*); **harmonic-rhythm and cadence**
descriptors; and **functional-harmony n-gram / grammar** features. For each: what "memory" it encodes and
how far back, whether it is **causal/streamable**, and how it might reduce to a **low-dimensional per-frame
signal** suitable for conditioning.

**Q4 — The broader theory of "encoding musical movement" (need not be computational).**
Survey the music-theoretic, musicological, and mathematical frameworks that formalise musical *motion*,
with an eye to what could be turned into a numeric descriptor: **Schenkerian** reduction and voice-leading;
**Lerdahl–Jackendoff GTTM** (time-span / prolongational reduction, tension); **Narmour's
implication-realisation** model and melodic-expectation theory; **melodic archetype / contour typologies**;
**neo-Riemannian theory and the Tonnetz** (parsimonious voice-leading as movement on a pitch lattice); the
**geometric theory of voice-leading** (music as motion through quotient/orbifold spaces); and **mathematical
music theory** (DFT of pitch-class sets and maximal evenness; transformational theory / Generalized Interval
Systems). For each framework: what notion of "movement" it captures, and whether it yields a **computable
vector or distance** (and if so, how).

**Q5 — Conditioner-feasibility synthesis (the payoff — please make this the centrepiece).**
Pull Q1–Q4 into a **ranked shortlist** of descriptors that would make good conditioning signals for a music
diffusion model, scored on: (a) **extractable per-frame or short-window directly from audio** at modest
cost; (b) **useful invariances** (transposition and/or time-shift) so the model learns movement, not
absolute pitch; (c) **low, fixed dimensionality** suitable for a prepend/cross-attention/FiLM conditioner
*or* as a lightweight per-frame regression (adapter) target; (d) **differentiable or cheaply measurable**
(for a guidance or evaluation loop); (e) **empirical evidence** it captures musical identity/recognisability
or has been used successfully as a control. Present this as a table:

| Descriptor | Movement it captures | Invariances | Per-frame? Causal? | Dim | Compute | Conditioner suitability (1–5 + why) | Primary refs |

Then a short prose synthesis and a **"top 3 to prototype first"** recommendation with justification.

**Ground rules for the answer.** (1) Cite **primary sources**; separate established from single-paper/proposed.
(2) If a promising result appears only at a double-blind venue or a submission-stage preprint with **no public
link**, say so and flag it for manual retrieval — treat *absence of a web footprint as "unverified," not
"nonexistent."* (3) Do **not** pad with generic diffusion-conditioning or prompt-engineering material —
stay on *representations of musical movement*. (4) Prefer concrete invariance properties, dimensionalities,
and compute costs over vibes; where a descriptor's invariance is only approximate, say in what regime it
breaks.

## ================= END BRIEF FOR GEMINI =================

---

## Notes for us (do not paste)

- **Why the invariance angle is the crux.** A raw chromagram is transposition-*equivariant* (transpose the
  music → the chroma vector rotates), so a chroma-conditioned model can learn to copy absolute pitch and
  overfit. The DFT-magnitude / tonal-interval and contour/interval families are transposition-*invariant* —
  which is exactly the "bottlenecked conditioning that prevents copying" that Q1(d) asks about, and likely
  the real answer to Zach's overfitting caveat. Scattering gives the time-shift/deformation-invariant analogue.
- **The "memoryful" family (Q3)** is Kim's "current key carries information from past measures" made precise:
  expectation/surprisal and tension-integration models are *literally* descriptors whose present value is a
  function of the preceding context — a natural fit for a sequence conditioner, and cheap enough to be a LatCH
  adapter target.
- **Landing the result:** the Q5 table maps directly onto our two build paths — (i) a native prepend/cross-attn
  conditioner trained with CFG dropout (Zach's route), and (ii) a lightweight per-frame adapter that regresses
  the descriptor. When the report lands, verify every cited paper from its PDF before it earns an index row.
- **⭐ We already have a strong concrete instantiation in-house (SAME paper, 2605.18613, §3.3.2).** Our
  autoencoder was trained with **three octave-band chroma regressors** (octave centres 1/5/9, widths
  1.0/1.5/1.0, 128 bins each = **384-d**), each a **single 1×1 conv** → chroma is a *linear* readout of the
  latent, trained in (and reinforced by 3 matching chroma discriminators). This pre-answers much of Q1/Q5 for
  our specific case: (i) the movement signal is native and in-distribution — conditioning on it is aligned with
  the latent's own geometry; (ii) the 3 bands are a **register decomposition** — oct1≈bass, oct5≈harmony,
  oct9≈melody — so "keep the melody / keep the bassline" are separate channels for free; (iii) the
  transposition-**invariant** reduction is per-band (DFT-magnitude of each 128-bin band) → register-resolved
  key-invariant movement = the anti-overfit bottleneck; (iv) we can likely **lift the trained 1×1 conv weights**
  as the extractor, so the LatCH-adapter path is nearly free. The Gemini survey's job is then to (a) place this
  register-band-chroma choice against the broader movement-encoding literature, and (b) surface *better* or
  *complementary* invariant/memoryful descriptors we're missing — not to reinvent what SAME already gives us.
