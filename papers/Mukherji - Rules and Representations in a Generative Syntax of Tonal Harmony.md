# Rules and Representations in a Generative Syntax of Tonal Harmony

**Somangshu Mukherji** · *Perspectives of New Music* 62(1), Winter 2024, pp. 157–202
read 2026-08-12 (WINTERMUTE), pp. 157–160 in detail (of 46 journal pages)

> **CORRECTION TO MY OWN CLAIM.** I told the channel this was "Rohrmeier's PCFG". It is not.
> It is **Mukherji's critique-and-alternative essay** *about* Rohrmeier's (2011) generative
> syntax, arguing for an alternative built on Chomsky's Minimalist Program. I inferred the
> author from the title without checking — the fourth metadata-driven error of this sweep, and
> the first one that was mine rather than the corpus's.

---

## What it contains

A review and critique of **Rohrmeier's "generative syntax of tonal harmony" (2011)**, situated
in the Lerdahl–Jackendoff (1983) and Keiler (1977) lineage, leading to a proposal to
operationalise ideas from the **Minimalist Program** as an alternative model of musical syntax.

**The core argument, and it is the part that matters to us.** Mukherji distinguishes two
families:

- **Surface / Markovian models** (Piston 1978; Tymoczko 2003; Gjerdingen's schemata) — model
  harmony as **transition probabilities between adjacent chords**. Empiricist: structure is
  *learned* from statistics of the musical surface.
- **Hierarchical / rule-based models** (Rohrmeier, Lerdahl–Jackendoff, Keiler) — model
  **non-adjacent** relations, recursively.

**Why adjacency is claimed to be insufficient.** Tonal-harmonic relationships hold not only
between neighbouring chords but between chords separated by intervening material: two inversions
of the same harmony connected through passing chords (I–VII⁶–I⁶), pre-dominant harmonies
(IV⁶–I⁶₄–II⁶), the "chromatic wedge"/"omnibus" progressions. These are relations between
constituents at **deeper, sub-surface levels**, and — his claim — "cannot be modeled by means of
a learning mechanism that only tracks immediate chord-to-chord relationships".

Rule-based grammars are additionally **recursive**, so a finite grammar generates infinitely
many structures — which is the standard argument for generative over statistical accounts.

---

## What stays ours

**1 — This is a named limitation of the control target I ranked strongest, and I would not have
found it otherwise.** I filed 2006.01033 (dynamical score networks) as the sweep's best
control-target find: nodes = chords, **edges = successive chords**, tonal regions from modularity.
That is, by Mukherji's taxonomy, a **surface/adjacency model** — precisely the family he argues
cannot capture tonal-harmonic hierarchy. So:
- the tonal-region and centricity features remain computable and probably still useful — the
  Bach demonstration does recover real regions;
- but any claim that they capture *harmonic syntax* or hierarchy is unsupported, and this
  literature says explicitly that it will not.

Recorded as a caveat against that row rather than a retraction of it: a modularity class over an
adjacency graph is a **grouping**, not a **parse**.

**2 — It sharpens where 2201.02715 fits.** The chain is now legible: chord-adjacency graph =
surface structure; **PCFG = the hierarchical, non-adjacent structure this essay says you need**;
low-rank structured inference (2201.02715) = what makes such a PCFG affordable at scale. Three
papers from three different corners of this sweep forming one progression — and only the middle
term is missing from our reading, since Rohrmeier's own 2011 paper is not in the folder.

**3 — A caution about ambition, stated plainly.** This is music theory of the strongly
rationalist kind — innateness, Minimalism, explanatory adequacy. Nothing here is computable from
a clip, and it names no quantity Kim could ask for by ear. **It fails two of the three parts of
his test.** Its value to us is purely as a *check on interpretation*: it tells us what our
cheap adjacency-based features will and will not mean. That is worth having, and it is not a
control candidate.

---

## Status

Read pp.157–160 in detail (introduction, the two-goals summary of Rohrmeier, the
surface-versus-hierarchy argument, the empiricist/rationalist framing); **the remaining ~40
journal pages — the Keiler discussion, the Minimalist proposal, and the concluding
operationalisation — are unread.** The core critique is established in what I read; the
alternative model Mukherji proposes is not, and I make no claim about it.

Filed at this depth deliberately: the argument I needed for our purposes is complete, and the
Minimalist-Program construction is C's lane if anyone's.
