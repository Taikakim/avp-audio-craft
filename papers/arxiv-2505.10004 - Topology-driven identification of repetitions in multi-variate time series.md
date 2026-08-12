# Topology-driven identification of repetitions in multi-variate time series

**arXiv 2505.10004v2** (19 May 2025) · Schindler, Reich, Messineo, Hoher, Huber — Josef Ressel
Centre, Salzburg Univ. of Applied Sciences · 16 pp · read 2026-08-12 (WINTERMUTE), pp.1–6 detail

Read under Kim's corrected criterion (control targets / conditioners / new timeseries).
**This is the strongest methodological fit in my batch, and it supersedes SW1PerS (1307.6188)
for our purposes on four specific counts — the authors say so themselves.**

---

## What it contains

**Problem.** Recover the *times of recurrence* — all `T_i`, i.e. every individual cycle
boundary — in a **multi-variate** time series, under noise and **non-uniform sampling**.

**Three nested definitions of cyclic behaviour, and the middle one is the point:**

| | definition | what it means |
|---|---|---|
| **periodic** (Def 1) | `x(t+τ) = x(t)` | one fixed period, exact |
| **repetitive** (Def 2) | cycles related by monotone reparametrisations `γ_i` | **same shape, varying period per cycle** |
| **recurring** (Def 3) | returns to `x(0)` at finite times | cycles need not resemble each other |

Plus approximate versions: Def 4 (ε-approximately) and Def 5 (ε-δ-approximately recurring),
where δ imposes a *significance* condition so noise cannot manufacture tiny spurious cycles.

**Method.** Build a scalar **surrogate function `v(t)`** capturing relative position within the
current cycle, apply a **sublevel-set filtration** to it, and read the 0-dimensional persistence
diagram: each local minimum is born and dies, and its persistence is its significance. Stability
is the usual bound, `d_B(D(f), D(f')) ≤ ‖f − f'‖_∞`.

**Complexity: `O(n·α(n))`** — α the inverse Ackermann function, so linear for any practical n.

**Their explicit positioning against the alternatives:**
- Classical periodicity detection (FFT, autocorrelation, wavelet) **requires evenly spaced
  samples** and recovers only an *overall* periodicity, **not individual cycle lengths**.
- Perea et al. — i.e. **SW1PerS, the paper I read first in this batch** — "focus solely on
  periodic and quasi-periodic functions and do not address the recovery of period lengths".

They also note the standard decomposition `x = x_trend + x_residual` and state that their
analysis addresses the **residual**.

---

## What stays ours

**1 — "Repetitive" (Def 2) is the definition that actually matches music, and I have not seen
it stated this cleanly before.** Musical repetition is not periodic: a bar recurs with drifting
tempo, varied fills, different ornamentation. Def 1 is too strict to ever fire on real music;
Def 3 is so loose it says almost nothing. **Def 2 — same shape up to a monotone
reparametrisation per cycle — is exactly what a phrase repeat is.** That is a formal definition
of the thing we keep describing in prose.

**2 — It returns per-cycle boundaries, so it *is* a timeseries, not a scalar.** Recovering every
`T_i` gives cycle boundaries and cycle length over time from *any* feature stream. That is
phrase/bar segmentation derived from features rather than from onsets — a genuinely different
route to structure than our madmom beat grid, and one that would work on material where the
beat tracker struggles.

**3 — Four properties that fit our data specifically, where SW1PerS did not:**
- **multivariate natively** — our whole-track set is 46 fields; SW1PerS takes a scalar;
- **non-uniform sampling tolerated** — and MASTER §2 records that our expanded fields land at
  **native per-field rates from 0.2 to 100 Hz**, which is precisely the awkward case classical
  methods reject;
- **`O(n α(n))`, effectively linear** — affordable across 4461 tracks at full length, where I
  flagged Rips-based SW1PerS as per-clip-only on a landmarked cloud;
- **individual cycle lengths**, not one global period — which is what a *control* needs.

**4 — Control dimensions it names, tested against Kim's three-part rule.** Computable from a
clip: yes, from existing fields. Askable by ear: yes —
- **repetitiveness** — how well Def 2 fits, i.e. how strictly the music repeats;
- **phrase length and its drift** — cycle length over time;
- **structural variety** — how many *distinct* cycles versus one recurring cycle.

That last one is Kim's a2a complaint made measurable. His words on the noise ladder: *"0.8,
taken from a random position, plays like a track, but when skipped around, it's evident that
the whole song plays just one melody."* In this framework that is a series which is strongly
**recurring** with very few distinct cycles — a specific, computable signature, not a vibe.

**5 — A convergence worth noting.** Their trend/residual split (analyse the residual) is the
same move C arrived at empirically on chroma: raw chroma is inflated by the genre-generic
component, and only the **corpus-demeaned** signal carries identity (air 0.918 vs raw 0.997 ≈
null). Two unrelated fields concluding that the mean is the confound and the residual is the
signal.

**Honest gaps.** Their domain is industrial automation — injection-moulding machines — plus a
benchmark dataset they introduce; **no music validation whatsoever**. And the real design work
is hidden in one requirement: the surrogate `v(t)` must "capture relative position within the
current cycle". They supply three constructions for constrained cases; choosing `v` for music
is an open question and is where the effort would actually go. Anyone adopting this should
expect that to be the project, not the persistence part.

---

## Status

Read pp.1–6 in detail (motivation, the five definitions, prior-work positioning, persistent
homology background, framework); the three specialised methods (§3+) and the benchmark skimmed.
Nothing implemented. The music mapping — Def 2 as phrase repetition, the three control
dimensions, the a2a-complaint signature — is my inference under Kim's criterion, not a claim the
authors make.

**Cheapest test:** run it on `onsets_activations_ts` or `rms_energy_*_ts` for a few tracks whose
structure we already know from the beat grid, and check whether recovered cycle boundaries land
on bars. That validates the surrogate-function choice against ground truth we already have,
before anyone builds a control on top.
