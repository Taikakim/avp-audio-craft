# Towards a Generative Syntax of Tonal Harmony — Rohrmeier (J. Math & Music 5(1) 35–53, 2011)

*Project-POV abstract, CONTINUITY 2026-08-12 (deep-read, full PDF; Kim surfaced it as the missing
"hierarchy" rung). DOI 10.1080/17459737.2011.573676 (verified on p.1). The PCFG-for-harmony that
Mukherji's "Rules and Representations" critiques, and the middle rung between chord-adjacency score
networks (2006.01033) and low-rank structured inference (2201.02715).*

## What it contains
A **context-free (phrase-structure) grammar for tonal harmony** — explicit, computationally
implementable rules that recursively generate/parse chord sequences. Four levels: **phrase → functional
→ scale-degree → surface**. Two core principles:
- **Dependency principle:** every chord is head/dependent-linked to a neighbouring chord or chord-group,
  recursively, forming a **planar (non-crossing) dependency tree** with a single head per phrase. This is
  where **long-distance, NON-ADJACENT dependencies** live: `C A⁷ Dm G C` parses as `C ((A⁷ Dm) G) C` — the
  `A⁷` is justified by `Dm` (its consequent), not by the preceding `C`; surface-adjacent chords can sit on
  *different* branches and share no parent.
- **Functional heads:** chords group into abstract functions **tonic/dominant/predominant (TR/DR/SR)**,
  realizable by many surface chords — so structurally-identical progressions with different scale-degree
  realizations share one tree.
- **Rules:** functional expansion (`TR→DR t` dominant-prepares-tonic, `DR→SR d`, `TR→TR DR` prolongation,
  `XR→XR XR`), substitution (relatives/parallels `t→tp` etc.), **secondary dominants** (`X→D(X) X`) and
  descending-fifth `Δ(X)`, surface `X→chord|key`. The keystone is the **MODULATION rule**
  `X_key=y → TR_key=ψ(X,y)`: *any functional region can become a local tonic* → modulation IS recursion
  (key-relative re-entry into the functional domain). Validated by parses of Bach chorales, "Autumn Leaves",
  Bortniansky, the Waldstein opening.
- **Explicit anti-Markov argument (Discussion):** transition-matrix / n-gram models "do not embody
  sufficient complexity to express the formal structure of harmonic tonality, modulation, or overarching
  formal processes." A Markov chord model has **no structural memory** → "Brownian harmonic motion" that
  only randomly returns to its key; a prolongation `A x y A` (return-to-departure) would need exponential
  n-gram data. A CFG embodies that memory via left/right-expanding non-local dependency.
- **Honest limits:** harmony-ONLY subsystem — no voice-leading, melody, bass motion, or rhythm (a separate
  system). Some sequences (Monte `F-D⁷-G-E⁷`, Waldstein) need **context-SENSITIVE** rules or violate the
  dependency principle. Heavy **ambiguity** (many parses/sequence) → needs preference + metrical constraints
  (unimplemented; "future work"). Cognitive reality of long-distance dependencies empirically undecided.

## What this gives us / what stays ours
- **It is the theoretical justification for why our score-networks give a GROUPING, not a PARSE.** 2006.01033
  builds edges between *successive* chords — the exact Markovian family Rohrmeier's Discussion argues cannot
  capture non-adjacent structure (return-to-key, prolongation, modulation-as-recursion). So this paper *names*
  what the score-network ceiling (W's correction) is missing and what a parse would add: **long-distance
  closure** (does a chord resolve its earlier departure?), **prolongation depth** (tree depth = structural
  complexity), and **modulation-as-recursion** (does the harmony establish new local tonics?).
- **Control-TARGET candidates under Kim's criterion — but 3rd-wave (needs a PARSER).** Askable-by-ear: "does
  it return home" (long-distance closure), "harmonically deep vs static" (tree depth), "modulate vs stay"
  (recursion depth) — all real, and derivable as per-chord time series (open-dependency count, depth,
  distance-to-closure) FROM a running parse. But extraction needs (a) clean chord labels — ours are noisy
  audio estimates, errors compound into the tree — and (b) a **parser with preference rules**, which the paper
  leaves as future work. Much heavier than the score-network (which just needs the chord graph). REUSE NOTE:
  the parser is NOT from-scratch — de Haas & Rohrmeier's tree-matching harmonic-similarity work (ref 34, ISMIR
  2009) and the later HarmTrace lineage have implementations; a Haskell/functional parser exists in that world.
- **The sharpest bridge is to the REPETITION-DETECTOR thread: tree-matching harmonic similarity.** The paper
  flags that two instances of a standard have similar TREE structure → "partial tree-matching" gives a
  **structural harmonic-similarity metric ABOVE surface repetition**. For the anti-loop-collapse detector this
  is a harmonic-level variety signal: does the harmonic *tree* evolve, or is one function repeated forever? —
  complementary to the melody/FX-residual SSM variety we're validating first.
- **The honest, slightly deflating goa verdict (the most useful thing here).** The whole grammar is built on
  harmony as *elaboration of cadential/tonic-prolongational structure* — dominant-prepares-tonic, modulation,
  return. **Goa sits on one chord for 8 bars**: its harmonic tree is near-degenerate/flat (like the
  score-network degeneracy W flagged), so the hierarchy rung has **low value for goa specifically**. And that
  degeneracy is itself the measurement — it CONFIRMS Kim's own decomposition: goa's controllable variety does
  NOT live in harmonic syntax; it lives in **melody / FX / timbre** (the 88-key movement roll + the melody-FX-
  residual repetition detector). So the ladder's top two rungs (hierarchy, tractability) are for
  harmonically-rich material (tonal/jazz); for goa they're "know it exists, revisit if we ever work tonal
  corpora," not a near-term build.
- **STAYS OURS / caveats:** symbolic + parser-dependent + ambiguity-laden + harmony-only (orthogonal to the
  88-key melody thread, not a substitute); noisy audio chords compound into parse errors; CF-incomplete even
  for harmony (the sequence problem). Its value to us is (1) the *why* behind the score-network ceiling, (2)
  tree-matching harmonic similarity as a 2nd-wave repetition signal IF we ever hit harmonically-rich material,
  (3) modulation-as-recursion as the crisp definition of "harmonic movement."

## The ladder, now complete (why Kim surfaced it)
- **SURFACE** = chord-adjacency graph (2006.01033) — cheap, consumes mir `chords`, gives grouping / centricity
  / harmonic-mobility. Degenerate on goa (a measurement, not a bug).
- **HIERARCHY** = this PCFG (Rohrmeier 2011) — recursive non-adjacent parse: depth / closure / modulation-
  recursion + tree-matching harmonic similarity. Needs a parser; heavier; the paper itself proves adjacency/
  Markov can't reach it.
- **TRACTABILITY** = low-rank structured inference (2201.02715) — makes a PCFG affordable at real state sizes.
**Verdict:** the ladder is real and elegant, and for *tonal/jazz* material it's the right escalation. For
**goa it's over-powered** — harmonic syntax is shallow there by genre, so near-term effort belongs on the
melody-movement + melody/FX-variety threads, with this grammar banked as the harmonically-rich-corpus route.

**knowledge.md row** (hand to F): *Rohrmeier, Towards a Generative Syntax of Tonal Harmony (JMM 5(1) 2011,
DOI 10.1080/17459737.2011.573676) — a CONTEXT-FREE grammar for tonal harmony over 4 levels (phrase/functional/
scale-degree/surface); dependency principle (planar head-dependent tree w/ long-distance non-adjacent
dependencies) + functional heads (TR/DR/SR) + modulation-as-recursion (any region → local tonic). Explicit
Discussion argument that Markov/n-gram chord models CANNOT capture this. FOR US: the theoretical justification
for why our score-networks (2006.01033) give a harmonic GROUPING not a PARSE — the missing HIERARCHY rung
between surface-adjacency (2006.01033) and tractability (2201.02715); control targets (closure/depth/modulation
= harmonic movement) are real but 3rd-wave (need a parser — reuse de Haas/HarmTrace ISMIR'09 ref 34, not
from-scratch); best near-term bridge = tree-matching harmonic similarity for the repetition detector. HONEST
GOA VERDICT: goa's harmonic tree is near-degenerate (one chord/8 bars), so the hierarchy rung is over-powered
for goa — confirms Kim's decomposition that goa's variety lives in melody/FX not harmony; bank for tonal/jazz
corpora. Symbolic, parser+preference-rule-dependent, ambiguity-laden, harmony-only (orthogonal to the melody
thread).*
