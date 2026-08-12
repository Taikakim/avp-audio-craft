# Meter networks: a categorical framework for metrical analysis

**Alexandre Popoff & Jason Yust** (Boston Univ. School of Music) · submitted to *Journal of
Mathematics and Music*, compiled 2020-10-10 · read 2026-08-12 (WINTERMUTE), pp.1–5 in detail

Read under Kim's corrected criterion. **Names a rhythmic control dimension we do not have and
cannot currently express — and our stem separation already supplies its input.**

---

## What it contains

**Metrical relation (Def 2.3).** For `d ∈ ℚ≥0`, the relation `M_d` on timepoints holds when
`t' − t = kd, k ∈ ℤ`. The key move: `M_d` relates **all** timepoints of a metrical layer, not
merely successive ones — so a metrical layer is a *relation*, not a list of intervals. As they
put it, this makes it "an inherently metrical concept, where the more basic concept of time
interval is not".

**Inclusion (Prop 2.5).** `M_d₁ ⊆ M_d₂` **iff** `d₁ = u·d₂` for a positive integer `u`. So the
nesting of metrical levels — Lerdahl & Jackendoff's well-formedness — is exactly relation
inclusion, proved rather than assumed.

**Meter network.** A diagram of metrical relations with arrows for inclusion. Cohn's *ski-hill
graphs* are the special case with one source and one sink and `d = 2^a·3^b·e`; Murphy's metric
cubes likewise.

**The musical payoff, and it is the reason to care.** In a real passage, **different parts trace
different paths through the same network**. Their Brahms Op. 78 example: violin takes
`M₁ → M⅓ → M⅙ → M₁⁄₁₂`, piano right hand `M₁ → M½ → M⅙ → M₁⁄₁₂`, piano left hand
`M₁ → M½ → M¼ → M₁⁄₁₂`. Three simultaneous, divergent paths — that *is* metric dissonance,
formalised.

**Why it beats the existing theories.** Krebs distinguishes **grouping dissonance** (3-against-4,
hemiola) from **displacement dissonance** (same grouping, offset phase). Cohn's metric spaces
handle only grouping — yet the authors note displacement "is musically significant in many ways,
and more common than grouping dissonance". Meter-network **morphisms** capture both displacement
and inclusion, which is the paper's actual contribution.

**Stated limitation, and they are candid about it.** The model uses ℚ (notated rhythm). They
explicitly note music cognition has moved to ℝ for *performed* rhythm (citing Polak & London
2014, Benadon & Zanette 2015, Danielsen 2018), and offer their relations as "idealisations of
the neural oscillations underlying metrical perception".

---

## What stays ours

**1 — It names a rhythmic axis none of our features can express.** mir's rhythm module gives
bpm, beat grid, downbeats, onsets, syncopation, rhythmic complexity, per-stem rhythm. Every one
of those describes **a single meter**. None can say:
- **grouping dissonance** — 3-against-4, hemiola, triplet-versus-straight tension;
- **displacement dissonance** — same grouping, offset phase, i.e. the off-beat feel;
- **polymeter** — two layers coexisting without nesting.

For goa and psytrance that is not an exotic gap. Triplet-against-straight, offbeat placement and
polyrhythmic layering *are* the genre's rhythmic vocabulary, and Kim's listening notes are full
of exactly this register — "galloping", "rapid 16ths/32ths hihat", "congas played
darbouka-style", "rapid mathematical rhythms", "the beat has disappeared". We have no number for
any of it.

**2 — Our stem separation already provides the paper's "parts", which is the non-obvious bridge.**
The framework needs multiple simultaneous voices to trace divergent paths — violin versus piano
right hand versus left hand. We separate every track into **drums / bass / other / vocals** and
already store `onsets_activations_ts` per stem. Those four streams are the parts. Estimating a
candidate `d` per stem (autocorrelation of the stem's onset envelope) and building the inclusion
diagram gives, per track:
- whether the diagram is a **chain** (metrically consonant) or **branches** (dissonant);
- the **ratio** of conflicting layers (2:3 versus 3:4 …) = grouping dissonance type;
- the **phase offset** between layers of equal `d` = displacement dissonance.

That is a rhythmic-conflict descriptor built from data we already extract, and it is per-track
now and per-frame with a sliding window.

**3 — Control dimensions, against Kim's three-part test.** Computable from a clip: yes, via the
stems. Askable by ear: unmistakably — *"more polyrhythm"*, *"push it off the beat"*, *"straight
versus triplet feel"*. Time-series: yes, with a window. This is a *new* axis rather than a
re-parameterisation of onset density, which is the test the attribute-branch plan should be
applying to every proposed control.

**4 — The ℚ-versus-ℝ caveat is the real engineering risk, and they hand us the citation.**
Notated rhythm is rational; performed rhythm is not, and goa is performed-and-quantised in
uneven ways. Their own pointer to Danielsen — the microtiming and groove literature — is the
lead to follow before building anything, because a strict rational-inclusion test will simply
fail on audio-derived layer estimates. The practical form is almost certainly approximate
inclusion with a tolerance, which is a modification of their framework rather than an
application of it.

---

## Status

Read pp.1–5 in detail (metrical relations, inclusion proposition, ski-hill equivalence, the
Brahms worked example, the Krebs/Cohn positioning); §3's category-theoretic formalism (2-categories,
lax functors) and the twentieth-century examples skimmed. Nothing implemented.

The stem-streams-as-parts bridge and the three derived descriptors are my inference under Kim's
criterion, not claims the authors make — their subject is notated art music.

**Cheapest test:** take one goa track's four stems, autocorrelate each `onsets_activations_ts`
to get candidate layer periods, and check whether the resulting `d` values form a nesting chain
or conflict. One track answers whether there is any metric dissonance in this music to detect at
all — and if the answer is "none, everything nests at 4/4", that is itself the finding, and
cheaply obtained.
