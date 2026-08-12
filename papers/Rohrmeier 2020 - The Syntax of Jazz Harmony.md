# The Syntax of Jazz Harmony: Diatonic Tonality, Phrase Structure, and Form — Rohrmeier (Music Theory & Analysis 7(1) 1–62, 2020)

*Project-POV note, CONTINUITY 2026-08-12. DOI 10.11116/MTA.7.1.1. Kim surfaced it as the fuller successor to
Rohrmeier 2011. **SCOPE HONESTY: this is a TARGETED read of the intro/positioning (pp.1–8), NOT a full deep-read
of the 62-page article** — the phrase-structure/form analyses (§5) and the Blues case study (§5.5) are unread.
Read specifically to answer: does the fuller version change the "over-powered for goa" verdict on 2011? It does
not — it sharpens it — but it surfaces the real computational tooling.*

## What it adds over 2011 (from the intro)
Same framework — the **Generative Syntax Model (GSM)**, functional symbols amended with key features, two core
dependency types (**preparation** and **prolongation**) — extended in two directions:
- **Phrase structure + FORM.** 2011 modeled core phrases; 2020 argues the grammar also models **relations
  between phrases** and "the syntactic structures underlying the main forms of Jazz standards" (AABA etc.).
  **Blues form** = a special case built on **plagal derivation from the tonic**, analyzed against Steedman's and
  Katz's Blues grammars.
- **Extended tonality** (19th-c.→jazz): embedded modulation, borrowing, substitution unified in one grammar;
  cadence taxonomy (perfect/imperfect/evaded/deceptive, with Neuwirth). Notes some phenomena ("interruption")
  suggest **mildly context-SENSITIVE** complexity beyond CFG — barely explored.
- **The computational tooling is named** (footnotes 35–37) — the reusable part for us: **Harasim, O'Donnell &
  Rohrmeier, "A Generalized Parsing Framework for Generative Models of Harmonic Syntax" (ISMIR 2018)**;
  **Harasim et al., "Harmonic Syntax in Time: Rhythm Improves Grammatical Models of Harmony" (ISMIR 2019)**;
  **de Haas et al., "Modeling Harmonic Similarity Using a Generative Grammar of Tonal Harmony" (ISMIR 2009)**.
  So parsers + a tree-matching similarity metric + a rhythm-integrated version already exist.

## What this gives us / what stays ours
- **The goa verdict sharpens, doesn't flip.** 2020's headline addition is *jazz-standard form* (AABA
  turnarounds, cadential phrase grammar, Blues). Goa is groove-based and harmonically static — even *less* like
  a jazz standard than 2011's common-practice examples. So the fuller, form-aware grammar is **even more
  over-powered for goa** than the 2011 core. Confirms the same conclusion twice: goa's controllable variety
  lives in **melody / FX / timbre**, not harmonic-form syntax.
- **Two genuinely useful pointers, though:**
  1. **"Rhythm Improves Grammatical Models of Harmony" (Harasim ISMIR 2019)** directly validates Kim's
     downbeat-grid instinct at the harmonic level — metrical position improves harmonic parsing. If we ever do
     the parse route, the metrical grid (madmom downbeats ÷ even) is a first-class input, not an afterthought.
  2. **Tree-matching harmonic similarity (de Haas ISMIR 2009)** — the concrete structural-harmonic-similarity
     tool for the repetition-detector's harmonic layer, and the **generalized parsing framework (Harasim ISMIR
     2018)** is the ready parser. Reuse targets IF the harmonic-form route is ever pursued (tonal/jazz corpora).
- **STAYS OURS / recommendation.** I do **not** recommend a full 62-page deep-read now — marginal value for goa
  is low by the verdict above, and I've extracted the delta + the tooling refs. Bank Rohrmeier 2020 as the
  **jazz/tonal-corpus route** alongside 2011; the near-term goa build stays on the melody-movement (88-key) +
  melody/FX-variety (repetition detector) threads. Revisit + full-read IF we ever target harmonically-rich
  material, at which point Harasim's parsers (ISMIR 2018/2019) + de Haas similarity (2009) are the entry points.

**knowledge.md row** (hand to F): *Rohrmeier 2020, The Syntax of Jazz Harmony (MTA 7(1), DOI 10.11116/MTA.7.1.1)
— TARGETED read (intro pp.1–8; §5 form/Blues unread). Fuller successor to Rohrmeier 2011: same GSM extended to
jazz PHRASE STRUCTURE + FORM (AABA, Blues=plagal-from-tonic) + extended tonality/cadence taxonomy; flags mildly
context-sensitive phenomena. FOR US: SHARPENS the "over-powered for goa" verdict (jazz-standard form is even
less goa-like than 2011's common-practice) — bank as the tonal/jazz-corpus route. Useful pointers: the
computational tooling exists — Harasim ISMIR'18 generalized parsing framework, Harasim ISMIR'19 "Rhythm Improves
Harmony" (validates Kim's downbeat-grid instinct for harmonic parsing), de Haas ISMIR'09 tree-matching harmonic
similarity (the repetition-detector harmonic-layer tool). Near-term goa effort stays on melody/FX threads.*
