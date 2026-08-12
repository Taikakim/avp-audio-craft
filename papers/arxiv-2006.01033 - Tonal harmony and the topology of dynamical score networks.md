# Tonal harmony and the topology of dynamical score networks

**arXiv 2006.01033** · Marco Buongiorno Nardelli (Univ. North Texas — Physics + Composition
Studies, CEMI, iARTA) · read 2026-08-12 (WINTERMUTE), pp.1–6 in detail

> Read under Kim's corrected sweep criterion (2026-08-12): *"the symbolic music papers are
> exactly what interests us now, when we are planning musical controls, IE we need prediction
> targets, conditioners, possible new time series."* Under the old criterion ("does it process
> continuous-latent audio?") this is off-lane. Under the right one it is the strongest
> control-target candidate the sweep has produced.

---

## What it contains

**The construction.** A score becomes a **dynamical score network**: nodes are chords
(pitch-class sets), directed edges join *successive* chords in the progression, edge weight is
the number of traversals. Nothing is assumed about harmony — the graph is just what happened.

**What falls out of the topology, with no music-theoretic priors:**

| property | how it appears in the graph |
|---|---|
| **centricity** (tonal music is governed by a few central chords) | degree distribution; the network is **scale-free**, tonic/dominant are the hubs |
| **referentiality / hierarchy** | **modularity classes** — community detection isolates *tonal regions* |
| **directedness** (progressions are asymmetric) | edge direction + weight asymmetry |

Demonstrated on Bach's chorale BWV 267: average degree 1.9, modularity 0.5, and the modularity
classes **cleanly recover the tonal regions** (G/C major, A minor, D minor) — *"without any a
priori knowledge of the harmonic structure"*.

**The move that matters to us (p.6).** They note the static graph throws away time, then
reinterpret the temporal network **as a time series of a non-stationary signal**, and run
**change-point detection** on it to identify key regions automatically — explicitly *without*
Krumhansl-Schmuckler key-finding templates and *without* corpus-trained ML.

**Tooling.** Open source and Python: `MUSICNTWRK` (the author's) and `music21`.

**Generative tail.** Minimal-length path through the graph via route optimization gives an
abstraction of harmonic sequence that they propose as a basis for generative models of tonal
design.

---

## What stays ours

**This paper answers all three of Kim's asks at once — target, conditioner, timeseries — and
the input side already exists in mir.**

**1 — New timeseries fields, computable from what we already extract.** The expanded whole-track
set already carries **`chords`** and `chroma_linmap` (NNLS) per MASTER §2. A chord sequence is
exactly the input this construction consumes. So without any new extractor we could derive, per
track:
- **tonal-region id over time** (modularity class of the current chord) — a categorical
  timeseries, and the change-point version gives *boundaries*;
- **centricity** — degree/centrality of the currently-sounding chord in that track's own
  network: "how close to the tonal home are we right now", as a continuous per-frame scalar;
- **harmonic mobility** — rate of region change, or path length travelled per bar.

That is three candidate fields, all derived rather than measured, all from an existing column.

**2 — Conditioners Kim would actually ask for by ear.** The three-part test I set: does it name
a quantity you would request more or less of? *"Stay in one key vs modulate"*, *"return to the
tonal home"*, *"harmonically restless vs static"* are all natural listening requests, and none
of our current control dimensions (onset density, brightness, bass weight, rms bands) can
express any of them. This is a genuinely new axis, not a re-parameterisation of an existing one.

**3 — It chains onto C's chroma result rather than competing with it.** C established that
band-chroma is readable from z0, timbre-invariantly, strongly (Tier-2 demeaned air 0.918). The
chain **z0 → chroma → chords → score network → tonal region / centricity** takes something the
model demonstrably encodes and lifts it to a musical control. Each link is separately testable,
and the first link is already measured.

**4 — Corpus caveat, and it may be the most useful thing here.** Their demonstrations are
common-practice tonal (Bach chorale, Beethoven quartet). Goa/psytrance frequently sits on one
chord for eight bars — a score network with one hub and almost no modulation. Two consequences,
and the second is the interesting one: (a) change-point detection may find very little on our
corpus, so anyone testing this should expect near-degenerate graphs and not read that as a bug;
(b) *the degeneracy itself is a measurement*. "How much harmonic movement does this track have"
is precisely a dimension our music is unusual along, and a control for it is a control for
something Kim's genre normally lacks — which is closer to an interesting knob than a broken one.

**Honest risks.** Their chords come from symbolic scores via `music21`; ours would come from
audio chord estimation, which is noisy, and errors compound *into the graph* rather than
averaging out — a wrong chord creates a spurious node and edge. Community detection on small,
noisy graphs is unstable. Both are reasons to prototype on the existing `chords` field and
inspect the graphs by eye before trusting any derived scalar.

---

## Status

Read pp.1–6 in detail (construction, the four tonal properties, the Bach worked example, the
time-series/change-point turn, tooling); §§3–6 skimmed. Nothing implemented. The three proposed
timeseries fields and the z0→chroma→chords→network chain are my inferences under Kim's
criterion, not claims the author makes.

**Concrete next step if this is wanted:** build the score network for a handful of goa tracks
straight from the existing `chords` whole-track field, and look at the modularity structure.
That is a day's work with `MUSICNTWRK`/`networkx` and no GPU, and it answers the corpus
question — degenerate or not — before anyone designs a head around it.

---

## Downgrade for OUR corpus (2026-08-12, after C's Rohrmeier ladder read)

I filed this as the sweep's strongest control-target find. **That claim has to be qualified, and
the qualification is genre-specific rather than technical.**

Two independent results landed after this note was written:

1. **Mukherji** (Perspectives of New Music 62/1) — score networks are a *surface/adjacency*
   model, which cannot capture the non-adjacent relations that constitute tonal-harmonic
   hierarchy. So its modularity classes give a **grouping, not a parse**. Recorded above as a
   caveat on interpretation.
2. **C's read of Rohrmeier 2011/2020** — the hierarchy rung that Mukherji says is required — with
   an explicit empirical verdict: **goa's harmonic tree is near-degenerate**, making the whole
   grammar route "over-powered for goa", and confirming Kim's own decomposition that this music's
   controllable variety lives in **melody, FX and timbre rather than harmony**.

I anticipated the degeneracy in the caveat above — "expect near-degenerate graphs … the
degeneracy IS a measurement" — but framed it as an open question with an interesting answer
either way. C's read closes it in the unfavourable direction, from theory rather than
speculation: goa does not have the harmonic depth for harmonic-structure features to carry much.

**Net position.** The construction is still sound, and tonal-region-id / centricity /
harmonic-mobility remain computable from the existing `chords` field at trivial cost. But for
**our** corpus they should now be expected to be **low-variance and weakly informative**, not a
headline control axis. The honest ranking is:

- **for harmonically-rich material** (tonal, jazz) — a genuine control-target route, and the
  ladder to build it is now fully read (this → Rohrmeier → 2201.02715 for tractability);
- **for goa** — worth the one-afternoon degeneracy check I proposed, precisely because a null
  result is now the *expected* outcome and would cost almost nothing to confirm; but it should
  not displace the melody/FX/repetition work.

Filed as a downgrade rather than a retraction: nothing about the paper changed, our reason to
want it did.
