# Persistent homology of featured time series data and its applications

**arXiv 2405.04796v1** (8 May 2024) · Eunwoo Heo, Jae-Hun Jung (POSTECH, Dept. of Mathematics)
preprint under review · read 2026-08-12 (WINTERMUTE), pp.1–4 in detail

**This is the formal answer to the question Kim asked about meter networks** — how to put our
own descriptors into a graph-of-music construction — and it comes with a stability proof.

---

## What it contains

**Frequency-based graph construction (§2.1).** For a time series `T : 𝕋 → 𝒳`:
- **nodes** = the distinct observed values `{T(t)}`;
- **edges** = pairs of *successive* values `{T(tᵢ), T(tᵢ₊₁)}`, when they differ;
- **edge weight** `f_e` = how often that adjacency occurs (co-occurrence count).

**Distance (Def 2.1).** `d(v,w) = min over paths of Σ (W_E(e))⁻¹` — the **reciprocal** of edge
weight, so two values that frequently follow one another are *close*. Then a Vietoris–Rips
filtration on that metric space gives the persistence diagram.

**The contribution: featured time series + influence vectors.** A *featured time series* is the
series augmented with **domain-knowledge features**; an **influence vector** assigns a weight to
each feature, adjusting the graph representation so it suits the domain. And §4 proves a
**stability theorem**: adjusting the influence vectors preserves stability of the PH calculation
— i.e. the tuning knob cannot make the output arbitrarily sensitive.

**Applications shown:** anomaly detection in stock data, and **topological analysis of music
data**. Their related work is dense with music precedents — PH on music networks for classifying
**Turkish makam**, analysis of traditional **Korean** music, **Tonnetz**-based classification,
and **intervallic transition graphs** for musical style.

---

## What stays ours

**1 — It is the same construction as the score-networks paper, generalised off symbols.**
2006.01033 builds nodes = chords, edges = successive progressions, weight = traversal count.
This is identical in shape but with nodes = *any observed value* and weight = co-occurrence
frequency. So the score-network idea is not restricted to chords: **it is a general recipe for
turning any sequence of discrete states into a weighted graph whose topology is analysable.**
That closes a gap I left open when filing 2006.01033.

**2 — Influence vectors are the principled version of Kim's "use whatever descriptors we have".**
His meter-network question was: can we swap note numbers for chroma, or multi-d vectors, or
anything we derive? For *that* framework the answer was "the formalism never used the values at
all". Here the values *are* used — and the featured-time-series construction is precisely a
mechanism for deciding **which descriptors influence the graph and by how much**, with a proof
that the weighting stays stable. That is better than ad-hoc fusion of our 46 fields: it is a
weighting with a guarantee rather than a hyperparameter with a hope.

**3 — The catch, and it is the same one twice over.** Nodes are *distinct values*, so the series
must be **discrete**. Chords are naturally discrete; `rms_energy_air_ts` is not. Applying this to
continuous fields requires binning, and both the graph size and its topology depend on that
binning — an unforced choice that will quietly dominate the result. This is the third paper in
my batch to bottom out in the same place: 2505.10004 needs a surrogate `v(t)`, meter networks
need an articulation set, and this needs a discretisation. **All three reduce to "turn our
continuous multi-field timeseries into the right discrete/scalar stream", and that single piece
of work is the gate on all of them.**

**4 — Where it sits against the others.** As a *control-target* source it is weaker than
2006.01033 (which names tonal regions, centricity, mobility) — it supplies machinery rather than
musical quantities. Its value is that the machinery is domain-tunable and proven stable, which
the others are not.

---

## Status

Read pp.1–4 in detail (abstract, introduction and its music-precedent survey, frequency-based
graph construction, distance definition, Rips filtration setup); the stability theorem §4 and
the applications §5 skimmed — **I have not verified the stability proof, only that it is
claimed and stated**. Nothing implemented.

The connection to 2006.01033 and the reading of influence vectors as the answer to Kim's
descriptor question are my inferences.
