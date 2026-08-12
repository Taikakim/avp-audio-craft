# Morphological Space as a Control-Head Target Space

*A design note on Kant & Polansky, "The Structure of Morphological Space" (Perspectives of New Music), and what it gives us for SA3 control heads.*

**Status:** design proposal. The first experiment (E1 / kick-contamination) has **RUN** — see §0. Rest unimplemented.
**Date:** 2026-08-12. **Reviewed + current results folded in:** CONTINUITY, 2026-08-12 (full 57-pp paper re-read; every `[paper]` claim below verified accurate against the PDF).
**Companion docs (paths corrected):** `stable-audio-tools/docs/book/CONTROL_METHODS_SOURCEBOOK-revisit-2026-07-06.md`, `stable-audio-tools/scripts/CHROMA_HANDOFF.md`. *(`SAME_CHROMA_FINDINGS.md`, referenced below, is **not in-repo** — external/planned; its §6 per-band-gain UI design is superseded by §5.4 here.)*

**Confidence conventions used throughout:**

| Tag | Meaning |
|---|---|
| `[paper]` | Stated in Kant & Polansky, verified against the PDF text |
| `[ours]` | Our own measurement (fleet logs, refit runs) |
| `[inferred]` | My extrapolation — the load-bearing risk sits here |

---

## 0. Review & currency (CONTINUITY, 2026-08-12)

I read the full paper independently and **verified every `[paper]`-tagged claim here against the PDF — they are accurate**: dimension collapse to `L−1`, basis space = zeroed-morph space, angle = shape / radius = rank, OCD↔angle / OCM↔magnitude, cosine as the higher-`L` angular distance plus its differentiability remark, the unit-half-circle for cross-length comparison, and `n`-ary rank reduction as a resolution continuum. This note is a strong foundation; my edits are tightening + folding in a fresh result, not disagreement.

**E1 has now RUN** (as the "Version A" stem experiment, 2026-08-12; `eval/musicology/same_chroma_stem_vs_mix_2026-08-12/`). Reused Tier-2's cached head predictions; pairing verified by construction; the baseline row reproduces Tier-2 exactly (bass 0.214 / mid 0.536 / air 0.918). Head-prediction vs three GTs, demeaned-cos12 median, n=1083:

| head-pred vs | bass | mid | air |
|---|---|---|---|
| full-mix GT | 0.181 | 0.526 | 0.918 |
| other-stem (melody) | 0.133 | 0.509 | 0.837 |
| **bass-stem (kick test)** | **0.302** | 0.210 | 0.370 |

- **Kick hypothesis (E1): PARTIALLY CONFIRMED.** Bass rises **0.181 → 0.302 (+67 % rel)** against the clean, kick-free bassline vs the full mix — real (survives a triangle-inequality check against the mix↔bass-stem correlation of 0.894, so it is not just the two GTs resembling each other). **But** bass stays the weakest band even against the clean target → **the kick explains *part*, not all, of the original 0.214**; the residue is a genuine head/representation limit near 55 Hz.
- **A confound the note didn't have — TRAINING-TARGET CIRCULARITY (important, sharpens §5.2).** The tested `same_chroma` head was trained against `W@z+b` = the SAME autoencoder's **full-mix** linear chroma readout (the target key is literally `full_mix`). So "does the head read the *isolated* melody" is not answerable from *this* head — it prefers full-mix *because that is its target*, not because it can't read melody (air is still strong absolutely, 0.837). Our Tier-1/2 numbers therefore come from a head that *predicts full-mix chroma by design*.
- **Actionable (updates §4/§5):** do **not** switch the *melody* target to other-stem (circularity confound); **do** train a *new bass-band* head against the kick-free bass-stem chroma. Still-open E1 pieces: the **percussion-stem** comparison (does band 0 track the *kick* specifically) and **E1b** (encode the bass stem → head — an OOD/GPU step).

**Inline corrections made below:** §3.3 (`n′` wording), §4.1 (monotone-invariance is the *ranking's* property, not "zeroing"'s), §5.2 (the tested LatCH head vs the linear regressor it targets), §7-E1 (marked RUN). Companion-doc paths fixed in the header.

---

## 1. TL;DR

The paper is a formal theory of **contour space**: how to represent, compare, and navigate the space of "musical shapes." Its central construction — **basis space** — turns out to be exactly the target space our control heads have been groping toward all session.

Three results carry the whole note:

1. `[paper]` **Dimension collapse.** Combinatorial contour (CC) nominally needs `(L²−L)/2` values, of which a vanishing fraction are valid. Full-rank CCs form a genuine **vector subspace of dimension L−1**. So a shape over `L` points is `L−1` real numbers, not `L²/2` constrained ternary ones.

2. `[paper]` **Validity by construction.** Every point in basis space is a valid contour; every valid contour is a point. The "impossible contour" problem — which would otherwise make this untrainable — disappears entirely under the change of coordinates.

3. `[paper]` **Polar structure: angle = shape identity, radius = magnitude/resolution.** §7: *"the shape of the contour corresponds to the vector's angle and the rank of the contour corresponds to the vector's magnitude."*

Result 3 is the same statement as CONTINUITY's Tier-2 finding (*"demeaned chroma = melodic IDENTITY; raw chroma = the copyable genre-generic shape"*), arrived at from pure combinatorics rather than from measurement. That convergence is the reason this note exists.

And the authors hand us the ML door themselves — §7.1, on choosing cosine over the music-theoretic OCD metric:

> *"Cosine similarity has useful analytic properties—such as being differentiable—that may be fruitful in solving musical problems in contour theory."*

---

## 2. Reading guide (for Kim)

57 pages, but the payoff is concentrated. Suggested path:

| Pages | Section | Verdict |
|---|---|---|
| 1–5 | §1–2 contour theory background | **Skim.** Useful for vocabulary (morph, LC, CC), skippable otherwise. |
| 5 | §2.4 impossible contours | **Read.** Sets up the whole problem. |
| 6–15 | §3 LC-space | **Skim.** This is ternary Hamming space with Hamming distance; if that's familiar, the results are the standard distance-transitivity facts. The figures are lovely. |
| **16–17** | Example 12/13 — the counts table | **Read.** The 9.09e−22 number is the motivation for everything after. |
| 15–22 | §4 CC as a masked subset of LC | Skim. Good framing ("impossibility mask"), no new machinery. |
| **23–30** | **§5 full rank and n-ary contour** | **Read properly.** Example 20 (p.26), the full-rank plane (Ex. 21, pp.27–28), rank reduction as folding (Ex. 22, p.30). This is the crux. |
| **31–37** | **§6 basis space** | **Read properly.** Ex. 25 (p.34) gives the closed-form basis vectors; Ex. 26 (p.35) shows the 13 radial regions. |
| **38–47** | **§7 angle and magnitude** | **Read properly.** The polar reading, the cosine/OCD comparison (p.43), and the unit-half-circle trick for comparing different lengths (§7.2, p.44). |
| 47–49 | §8 "How many morphs?" | Read the first two pages; the cardinality argument at the end is philosophy. |
| 50–57 | Appendix, notes, references | Reference only. Note 25 (p.54) on rank normalisation is worth a look. |

**Minimum viable read: pp. 23–47.**

---

## 3. What the paper says

### 3.1 Objects

`[paper]`

- **Morph** `M`: a finite ordered list of values. Any measurable musical parameter over time — pitch sequence, duration sequence, a band-energy curve, a chroma column.
- **Linear contour** `LC`: the vector of *adjacent* ternary relations. Length `L−1`. Values in `{−1, 0, 1}` = "less than / equal / greater than."
- **Combinatorial contour** `CC`: the half-matrix of *all pairwise* relations. Length `Lcc = (L²−L)/2`.

For the morph `[3, 4, 5, 1]`:
```
LC = [−1, −1,  1]
CC = [−1, −1,  1, −1,  1,  1]
```

**Note for us:** `[inferred]` CC is a **ternarised self-similarity matrix**. That is the same object as the recurrence/SSM structure in the anti-loop thread — contour metrics are metrics on recurrence structure. Worth remembering when we get to persistent homology.

### 3.2 The impossibility problem

`[paper]` Most ternary vectors of length `Lcc` are **impossible** — they violate transitivity. Impossible contours are "holes" in CC-space, and they dominate:

| L | Lcc | Descriptors (3^Lcc) | Possible CCs | Ratio |
|---|---|---|---|---|
| 3 | 3 | 27 | 13 | 4.81e−1 |
| 4 | 6 | 729 | 75 | 1.03e−1 |
| 5 | 10 | 59,049 | 541 | 9.16e−3 |
| 6 | 15 | 1.43e7 | 4,682 | 3.26e−4 |
| 7 | 21 | 1.05e10 | 47,293 | 4.52e−6 |
| 8 | 28 | 2.29e13 | 545,835 | 2.39e−8 |
| 9 | 36 | 1.50e17 | 7,087,261 | 4.72e−11 |
| 10 | 45 | 2.95e21 | 1.022e8 | 3.46e−14 |
| 12 | 66 | 3.09e31 | 2.809e10 | **9.09e−22** |

**Consequence for us:** `[inferred]` a head that regresses CC vectors directly emits impossible contours essentially always. Any naive implementation of "predict the contour" is dead on arrival. This is the trap the rest of the paper defuses.

**Useful identification** `[inferred]`: the "possible CC" counts — 3, 13, 75, 541, 4683, 47293, 545835, 7087261 — are the **ordered Bell / Fubini numbers**, i.e. the number of *weak orderings* (rankings with ties) on `L` elements. So "possible CC" ≡ "ranking with ties." (Their table lists 4,682 at L=6 where the Fubini number is 4,683 — likely a typo in the paper or an off-by-one convention; doesn't affect anything.) This is the closed-form answer to the "organic construction of CC-space" question Polansky & Bassein posed in 1992, and it is why the rank parameterisation below works.

### 3.3 Full rank and n-ary contour

`[paper]` Ternary contour compresses magnitude: `[0,1,2]` and `[0,1,5]` both give `[−1,−1,−1]`. A contour is **full rank** if its element magnitudes accurately express the inter-element rank deltas without compression.

**n-ary contour** generalises beyond ternary: with resolution `n`, values run `−n … n` (so `2n+1` relations). Ternary is `n=1`. The paper's framing:

- `n = 1` — maximally reductive. "Up / down / equal."
- `n = 2` (quinary) — "a lot less / a little less / equal / a little greater / a lot greater."
- `n → ∞` — the contour approaches the morph itself, one-to-one.

To represent an `n`-ary contour **at full rank**, the required resolution is `n′ = (L−1)·n` (paper Ex. 20: for `L=3`, ternary `n=1` needs `n′=2` / quinary; quinary `n=2` needs `n′=4` / nonary).

**`n` is a continuous-ish dial from "pure shape" to "exact values."** `[paper]` This is the single most useful knob in the paper for us (see §5.4).

### 3.4 Basis space — the payoff

`[paper]` Full-rank n-ary CCs lie on a **vector subspace of dimension `L−1`**, closed under addition and multiplication. Basis vectors have a closed form (Example 25, p.34):

```
b_k = [a_{i,j}  for i in 1..L, j in i..L]

where  a_{i,j} =  1  if i = k+1
                 −1  if j = k+1
                  0  otherwise
```

Worked examples from the paper:
```
L = 3:  b1 = [ 1, 0, −1]
        b2 = [ 0, 1,  1]

L = 4:  b1 = [ 1, 0, 0, −1, −1,  0]
        b2 = [ 0, 1, 0,  1,  0, −1]
        b3 = [ 0, 0, 1,  0,  1,  1]
```

Any full-rank CC is then `[a₁,…,a_{L−1}]_b = a₁·b₁ + … + a_{L−1}·b_{L−1}`.

Properties that matter to us:

- **Dimension `L−1`, real-valued, unbounded.** `[paper]` A clean regression target: no validity mask, no discrete decoding, no combinatorial search.
- **Exactly the possible CCs.** `[paper]` "CCs that are not full rank cannot be expressed as weighted sums of basis vectors and as such have no representation in basis space."
- **Basis space ≅ morph space under transpositional invariance** `[paper]` — "the space of all *zeroed* morphs." It is the first-order signed difference of morph space; only differences are retained, not absolute offset.
- **Rank reduction `R_{n→1}`** maps basis space down to any lower resolution — geometrically a folding of the plane into the unit cube.
- **Basis choice is not unique**; different choices rotate the space. The paper's convention: use morph-space primitives raising the 2nd, 3rd, … elements, discarding the first.

### 3.5 Angle and magnitude

`[paper]` §7, the part that makes this a blueprint:

> *"Contours in basis space are organized radially… the shape of the contour corresponds to the vector's angle and the rank of the contour corresponds to the vector's magnitude, or distance from the origin."*

- **Angle θ = which shape** (contour equivalence class). Ternary CC regions are radial wedges.
- **Radius r = rank / resolution / size.** Increasing `n` fills the space *outward*; the 13 ternary classes sit at the centre as the coarsest "ur" forms.
- `[paper]` **"CC distance in basis space may be measured solely by angle."**
- `[paper]` OCD (Polansky's Ordered Combinatorial Direction metric) corresponds to **angle**; OCM (Ordered Combinatorial Magnitude) corresponds to **magnitude**. At `L=3` OCD is a monotone function of angle. At higher `L` they diverge locally but show "significant correlation and identical symmetries."
- `[paper]` At higher `L`, angular distance is computed **by inner product — i.e. cosine similarity**. And the authors explicitly flag differentiability as its advantage over OCD.
- `[paper]` Angle can also be measured **parametrically**, per dimension, giving a *vector* `[θ₀,…,θ_{L−1}]` which tracks OCD more closely than scalar cosine does.

### 3.6 Comparing different lengths — the multiscale key

`[paper]` §7.2. Contours of *different* morph lengths `L` can be placed in **one common space** — the unit half circle — by measuring angular distance to an origin vector

```
v = [1, 2, …, L−1]_b
```

which takes the same general form at every length. Their convention `β` + `v = [1,2,…,L−1]` "maximises uniqueness, causing the fewest contours to alias."

`[paper]` Caveats they state: contours sharing `(r, θ)` **alias**; contours sharing `θ` with different `r` are **fixed points** across `r`. Which pairs alias depends on the basis and `v`.

`[paper]` §7.3: increasing `L` fills the half circle **outward along radii**; increasing `n` fills it **toward the centre**. Length and resolution are near-independent axes.

**Why we care:** `[inferred]` this is the missing piece for multiscale. A 4-frame gesture and a 64-frame phrase become comparable points in the same space. That is what a hierarchical "dense past" encoding needs and it is not obvious how to get otherwise.

---

## 4. Why this matters: convergence with our own results

`[ours]` CONTINUITY, 2026-08-11, Tier-2 melody-conditioning validation:

- n=1200 audio-GT + n=752 MIDI-GT pairs via MuScriptor.
- Corpus-demeaned cos12 median: **air 0.918 ≫ mid 0.536 ≫ bass 0.214**.
- Matched-vs-null: **air Δ+0.196; bass/mid matched ≈ null.**
- Design finding: *"condition on DEMEANED chroma = track melodic IDENTITY; raw chroma = the copyable genre-generic shape."*

`[paper]` Kant & Polansky: *zeroed morph space = basis space; within it, angle = identity, radius = magnitude.*

`[inferred]` **These are the same statement.** We found the decomposition by measurement; they derived it from combinatorics. That is the strongest evidence that the framing is real rather than an artifact of our pipeline.

Two places where the paper's version is **sharper than ours**, both actionable:

### 4.1 Our demeaning is the weaker operation

`[ours]` Corpus-demeaning subtracts **one global mean** estimated from the corpus — a single affine shift, shared across all frames and tracks.
`[paper] + [inferred]` The genuinely stronger operation is **the ranking itself**: converting each morph to its rank (or basis) coordinates is invariant to **any strictly monotone transform** of the values — this is a property of the *ordinal* representation, not of any subtraction. (Basis-space "zeroing" gives translation invariance and *keeps* the rank magnitudes; the full monotone invariance comes from the rank step. **Correction:** the original attributed the monotone invariance to "zeroing" — it's the ranking's. Practically the recommendation is unchanged.)

`[inferred]` So a **per-window rank-normalise** is strictly stronger than corpus-demean: it survives per-track gain staging, compression, and EQ, none of which a single corpus mean handles. **Prediction: moving from corpus-demean to per-window rank-normalise should help *bass* most**, since bass carries the largest genre-generic magnitude offset. **First evidence is consistent** (§0: the kick-free bass *target* already lifts bass +67 % rel), but the direct test is **E2**. If E2 shows no bass movement, this framing is weaker than claimed and the note should be downgraded.

### 4.2 We should be using the angle explicitly

`[ours]` We already report `cos12` — and cosine *is* the angular metric the paper names for higher `L`. We have been half-doing this by accident.
`[inferred]` Making it explicit means: normalise to the unit sphere `S^{L−2}`, treat radius as a separate, separately-controllable quantity, and consider the **parametric angle vector** `[θ₀,…,θ_{L−1}]` rather than scalar cosine, since the paper reports it tracks OCD more closely.

This lands on the same ℝ × S^k product-manifold structure the earlier geometry sweep converged on. Three independent routes, one answer.

---

## 4.3 The origin paper (2603.04366) — its chroma/pitch failure is GAIN-explained, not fundamental

`[paper 2603.04366]` The low-resource-guidance paper (Novack … **Evans**; the ORIGIN of "LatCH", on
Stable Audio Open) found **1-D low-freq controls succeed, sparse high-dim (pitch/chroma) FAIL across all
methods**, worse at coarser latent rates. It's Zach's own group; taken at face value it cautions this whole
melody/chroma direction.

`[ours] + [Zach direct 2026-08-12]` **But its pessimism is a gain artifact and is superseded by our own
results.** (1) It was an **intern project SA abandoned** — Zach: *"weren't planning on taking it much
further since the initial results on SAO-Small weren't great… awesome to see you're getting some success
with it here. Feel free to put out the code however you would like."* (2) SAME-L's 256-d latent is **~10×
less guidance-gain-sensitive** than their SAO-Small VAE; at their modest TFG gains you get the **"2%
authority mirage"** (near-zero effect, reads as failure), but our **gain-ladder (MASTER §5: operating gain
≈512, monotonic 128→1024; "dead at gain 8" was a mirage)** steers cleanly — Kim's **"1000× weights"** is the
reconciliation. *They didn't fail because chroma control is impossible; they failed because they didn't gain it.*

**Two LatCH families in our tree (terminology fork, settled):**
- **(A) paper-spec GUIDANCE readout heads** — `latch_weights_sa3_medium/` (incl `same_chroma`), trained to
  2603.04366's spec (LatCH-F/B, noise-conditioned), steer via a test-time distance-gradient. **This is where
  the high-gain success lives** (the June LatCH work). Tier-1/2's readout numbers are on THIS family.
- **(B) FiLM CONDITIONING adapters** — `sa3_control` (`melody_contour`), feed the signal IN during training
  (the `morph_head_sweep`). A **mechanism 2603.04366 never tested**; conditioning is generally stronger for
  sparse targets (Zach's own prepend-cond is conditioning).

**Corrected stance (C, retracting a momentary over-deference to the paper):** 2603.04366 is a useful account
of *why* naive low-gain control fails (sparsity/dimensionality) — exactly what the morphological densification
attacks — but it is **not** a governing prior against the direction: our high-gain guidance results already
beat its reported failure, and conditioning is a route it never tried. **Still valid from the earlier read:**
judge the sweep by **control-efficacy + the disintegration gate**, not readout accuracy (readout ≠ control).
**Publish opportunity:** Zach's explicit blessing → a fusion-optimiser-style CC0 release or short paper on the
revived+advanced method (gain-ladder + SAME-L + eval apparatus + morphological loss) is on the table.

## 5. The design

### 5.1 Two ways to slice the morph — two different products

`[inferred]` The paper treats one morph, a finite ordered list. We have a `(3, 128, T)` array, so there are two readings:

**(a) Morph over pitch** — rank the 12 (or 128) chroma bins *within a frame*.
`L = 12` → basis dim **11**. Gives a **monotone-invariant harmonic fingerprint**: "which pitch classes are stronger than which," invariant to gain, compression, EQ, and to the genre-generic magnitude profile. **This is the drop-in fix for the raw-vs-demeaned problem.**

**(b) Morph over time** — rank a scalar stream (band energy, `arg X[5]`, LatCH feature) across a window.
Classic contour. This is the **dense-past encoding**: order-aware, non-human-readable, metric-equipped, `L−1` dimensional, and multiscale-comparable via §3.6.

**Do (a) first.** Smaller, targets a problem we have already measured, and it is a *loss* change rather than a pipeline change.

### 5.2 The cost: ranking is not linear

`[inferred]` **This is the real price and it must not be glossed.**

The DFT/TIV route (see `CHROMA_HANDOFF.md` and the geometry sweep) is a *linear* map, so it inherits the refit R² exactly — SAME trained a `Conv1d(256→128, kernel_size=1)` readout, so chroma is linearly decodable *by construction*.

> **Disambiguation (C, confirmed in §0):** the `[ours]` Tier-1/2 numbers came from the trained **LatCH `same_chroma` head** (depth-4 attention), **not** from this 1×1 conv. The conv is the SAME autoencoder's internal semantic regressor, and it is the **full-mix** chroma *target* (`W@z+b`, key `full_mix`) the LatCH head was trained to match. So "chroma is linearly decodable" is a claim about the *target*, and it is exactly what makes the free-lunch below hold for **chroma but not contour** — and what caused Version A's "prefers full-mix" reading. A from-scratch contour/basis head is a genuinely new object.

**Rank is not linear.** A 1×1 conv cannot emit a rank vector, and SAME's encoder was pressured to make *chroma* linearly decodable, not *contour*. The free-lunch argument does not transfer.

### 5.3 The fix: keep the head linear, change the loss

`[inferred]`

> Leave the head predicting chroma linearly. Make the **loss** a contour/basis-space loss, via differentiable ranking.

Blondel et al., *Fast Differentiable Sorting and Ranking* (ICML 2020, arXiv 2002.08871) gives O(n log n) soft ranks with exact gradients. Pipeline:

```
z_t --[linear head]--> chroma_hat        (unchanged, k=1 or k=3)
chroma_hat --[soft rank]--> basis coords    \
                                              --> angular loss (cosine / parametric θ)
chroma_target --[soft rank]--> basis coords /
```

Head architecture untouched, decodability guarantee untouched, and the *objective* acquires monotone invariance. This is the bridge the 2020 paper could not have anticipated: Polansky's metrics were built for analysis and algorithmic composition; differentiable sorting makes them trainable. The authors' own remark about cosine being differentiable (§7.1) points straight at this door.

**Risk** `[inferred]`: soft-rank losses can train unstably on a low-capacity head — the gradient through the ranking is nonlocal and can fight a 1×1 conv's limited expressivity. If it does not converge, fall back to: predict basis coordinates with a small MLP head (2 layers), accepting the loss of the linear-decodability argument, and measure how much R² that costs.

> **PROTOTYPE STATUS (CONTINUITY, 2026-08-12): the loss core is built + tested.**
> `control/sa3_control/contour_loss.py` — dependency-free differentiable `soft_rank(x, tau, dim)`
> (pairwise-sigmoid, O(n²), fine for n=12/128) + `contour_cosine_loss(pred, target, tau, dim)`
> = `1 − cos(soft_rank(pred), soft_rank(target))` centred along the pitch axis. TDD, **8/8 green**
> (`tests/test_contour_loss.py`): the load-bearing property is proven — a *monotone* transform of
> the input (gain/EQ/compression = the genre-generic offset that trapped raw chroma cosine) leaves
> the loss ~0, while a genuinely different contour raises it; plus ordering, τ-sharpening,
> gradient-flow, batched-dim. Invariance is exact only as τ→0 (finite-τ is approximate; small τ
> ~0.02–0.1 on unit-ish data suffices).
>
> **The one decision left before wiring it in (Kim's call), because sa3_control is a *steering*
> adapter, not a readout head:** the adapter is trained with **RF-MSE + optional meter-in-gradient
> terms** (`cc_probe`/`fp`), not a direct feature-prediction loss. So the contour loss plugs in one
> of two ways —
> 1. **Meter-in-gradient term** (fits the existing `control_consistency_loss`/`fp_consistency_loss`
>    family): decode `z0_hat` → predict chroma via the probe → `contour_cosine_loss` to the target,
>    add `λ·contour` to the RF loss. In-distribution with how onset/genre control already works;
>    needs a differentiable chroma readout in the loop (the probe provides it).
> 2. **Readout-head loss** (the note's §5.3 literal form): a *separate* head predicts chroma linearly,
>    trained with the contour loss — cleaner test of the loss itself, but it's a new head, not the
>    steering adapter.
> Route 1 is the smaller change and matches the sovereign onset-control recipe; Route 2 is the purer
> ablation. I lean **Route 1** (a `--lambda-contour` term) for the first real run. Awaiting the call.

### 5.4 n-ary resolution is the lock-vs-prefer knob

`[ours]` `SAME_CHROMA_FINDINGS.md` §6 currently specifies "lock vs prefer = per-band guidance gain": bass high (constraint), melody moderate (palette preference), air ~0.3 or 0.

`[inferred]` **That is the wrong knob.** Guidance gain changes *how hard you push*, not *how much you specify*. Two problems: pushing harder on an over-specified target causes the off-manifold artifacts we know about, and it conflates "be strict" with "be detailed."

Rank reduction `R_{n→1}` is the right knob:

- Predict basis coordinates **once**.
- Apply rank reduction **at inference**, at whatever `n` the UI asks for.
- Low `n` (ternary) = "this general shape, details free" → melody palette.
- High `n` = "this exact profile" → bass lock.

**Same prediction, different specificity, chosen at runtime, no retraining.** This falls out of the geometry rather than being bolted on, and it is a better match to what the goa/techno use case actually wants (static bass, free melody) than a per-band gain is.

### 5.5 Relationship to the TIV / DFT route

`[inferred]` These are **complementary, not competing**, and they answer different questions:

| | DFT / TIV | Contour / basis space |
|---|---|---|
| Linear? | **Yes** — inherits R² for free | No — needs soft ranking |
| Invariance | Level (via `X[k]/X[0]`), transposition (via `\|X[k]\|`) | **Any monotone transform** |
| Natural axis | Pitch (circle) | Either pitch or time |
| Gives phase/key | **Yes** — `arg X[5]` is circle-of-fifths position | No |
| Resolution knob | No | **Yes** — `n` |
| Multiscale | No | **Yes** — unit half circle |

**Recommended combination:** use TIV to *reduce* the 128-bin chroma to a small tonally-meaningful vector (12–24 real dims, still linear, still free), then apply contour/basis-space treatment **over time** to that reduced stream. That gets the linear-decodability guarantee where it is cheap and the monotone invariance where it is needed, and it keeps the time-axis morph short enough that `L−1` stays small.

---

## 6. How this composes with the rest of the stack

### 6.1 SA3 facts that constrain everything

`[ours]` For anyone picking this up cold:

- SAME latent: 256-dim, 4096× compression, **~10.767 Hz**. Waveform-native, **not** mel+vocoder.
- Chroma extractor: `n_fft=8192` (**185.8 ms window**), hop forced to 4096 (**92.9 ms**) — so **2× overlap**.
- Pitch class `p` sits at bin `(128·(p+3)/12 − 30) mod 128`. **C is at bin 2.0, not 0.** Semitone = 128/12 ≈ 10.667 bins.
- No per-frame normalisation — targets scale with level. This is *why* invariance matters so much.
- Original readout: `Conv1d(256→128, kernel_size=1, bias=True)` per band, L1 loss, band weights `[0.035, 0.05, 0.2]`.
- Post-trained checkpoints are APT-distilled few-step and **CFG-inert**. Anything CFG-based is `-base` only.
- `local_add_cond` (dim 257 = 256 latent + 1 mask) is the frame-aligned additive conditioning port.

### 6.2 Resolution vs precision — a correction worth recording

`[ours]` Two findings that appeared to conflict, and don't:

- The fleet log records a **~186 ms window ceiling** on frame-precise single-note argmax for fast sweeps.
- Earlier synthetic-MIDI work found notes are encoded **sub-frame** — the information slides across overlapping frames.

`[inferred]` Both are true. 186 ms is a **resolution** limit (two events inside one window cannot be *separated*); sub-frame is a **precision** result (one isolated event can be *located* far better than the 93 ms hop, because 2× overlap makes the inter-frame amplitude ratio a smooth monotone function of onset position). Rayleigh vs Cramér–Rao.

Further: the logged ceiling is a limit on **single-note argmax decoding**, not on the representation. Two 16ths 107 ms apart at different pitches collide in time but separate on the chroma axis — one frame, two bumps. Argmax discards that; the representation holds it.

**Practical consequences:**
- MIDI alignment should be **precise**, not slugged to 186 ms. (An earlier version of this advice was wrong.)
- **Do not rasterise MIDI onsets to the 10.767 Hz grid when building targets** — that hard-quantises away the very information we measured. Build targets by rendering to audio and running the extractor, so the window does the graded weighting.
- The head is `kernel_size=1`, i.e. **strictly frame-local**, so it cannot combine neighbours where the sub-frame signal lives. Widening to `k=3` is a one-line change, and since `k=1` is the zero-side-tap special case, **R² can only go up.** `ΔR²(k=3 vs k=1)` is a direct measurement of how much sub-frame content a frame-local head discards.

### 6.3 Contour and the anti-loop thread

`[inferred]` CC is a ternarised self-similarity matrix, so contour metrics are metrics on recurrence structure. That connects directly to the long-form loop-attractor work (`tangential-refinements-longform-continuation.md`), where the blocker has been finding a computable, meaningful `R(z)` for the recurrence statistic in

```
p*(z) ∝ p_θ(z) · exp(−λ · D(R(z), R_data))
```

Basis space offers a candidate: **the angular coordinate of the contour of the latent trajectory**, compared across scales in the unit half circle. It is cheaper than persistent homology and differentiable via soft ranking. Whether it discriminates "pathological loop" from "legitimate chorus" as well as H¹ persistence does is **untested and I would not assume it**.

---

## 7. Experiments, in order

Each has a stated pass/fail so we don't accumulate ambiguous results.

### E1 — What is band 0 actually measuring? *(no new machinery, no MIDI)*

> **STATUS: RUN 2026-08-12 (Version A). Kick hypothesis PARTIALLY CONFIRMED (bass +67 % rel vs the kick-free bassline) + a training-target-circularity confound surfaced. Full result + table in §0. Still open: the percussion-stem comparison and E1b (bass-stem→head).**

`[inferred]` **Hypothesis:** band 0 is centred at **55 Hz**, exactly where a techno/goa kick sits. Band 0 may be measuring the kick, not the bassline — which would explain a high raw cosine with a near-zero demeaned cosine (a kick's pitch class is genre-generic and near-constant within a track).

We have BS-Roformer stems (percussion / bass / other / vocals), so this is directly falsifiable **without MuScriptor** — which removes the synthetic-mix training concern entirely.

**E1a.** Encode the **full mix** → latents → head → predicted band-0 chroma `P`. Compute chroma directly (extractor only, no head) on the **bass stem** → `B` and the **percussion stem** → `D`. Correlate `P` against both.

**E1b.** Encode the **bass stem alone** → latents → head → compare against the bass stem's own chroma. Measures the head's ceiling on isolated bass.

**Disambiguation:**

| | E1a tracks bass | E1a tracks percussion |
|---|---|---|
| **E1b good** | band 0 works; 0.214 is something else | **contamination confirmed** → high-pass, or re-centre band 0 |
| **E1b poor** | head/extractor problem at 55 Hz | band 0 is structurally the wrong band |

Separation artifacts are a non-issue — chroma at 186 ms resolution is robust to BS-Roformer bleed.

### E2 — Per-window zeroing vs corpus demeaning

Recompute the Tier-2 band comparison with per-window zero-and-normalise in place of corpus-demeaning.
**Pass:** bass improves materially (say ≥0.10 on demeaned cos12) and air holds. **Fail:** no movement → §4.1 is wrong, downgrade this note.

### E3 — `ΔR²(k=3 vs k=1)`

Refit the readout at `kernel_size=3`, compare R² to the existing `k=1` refit.
**Pass:** Δ meaningfully > 0 → the frame-local head was discarding sub-frame content; adopt `k=3`. **Null result is still informative:** Δ ≈ 0 means the latent carries the slide frame-locally and `k=1` was fine.

### E4 — Soft-rank contour loss on the pitch-axis morph

Implement §5.3 on slicing (a), `L=12`, basis dim 11. Compare against the current L1/L2 chroma loss on held-out demeaned cos12 and on matched-vs-null gap.
**Pass:** matched-vs-null gap improves on bass and mid (the bands currently at null). **Fail:** unstable training → fall back to the MLP head per §5.3 and record the R² cost.

### E5 — `n`-ary rank reduction as the UI knob

Once E4 trains, expose `n` at inference and A/B against per-band guidance gain on the goa "static bass + free melody" case.
**Pass:** listening test — `n` gives cleaner separation of "locked" from "preferred" than gain does, without the off-manifold artifacts high gain produces.

### E6 — Time-axis contour as dense-past encoding *(research)*

Slicing (b) over TIV-reduced streams, multiscale via the unit half circle. Compare against HiPPO-LegS and truncated log-signature as control-head targets.
No pass/fail yet — this is exploratory and should not block E1–E5.

---

## 8. Honesty ledger

**What is the paper's, exactly:**
- Dimension collapse to `L−1` and the closed-form basis vectors.
- Validity by construction in basis space.
- Angle = shape, radius = rank/resolution.
- OCD ↔ angle, OCM ↔ magnitude; cosine as the higher-`L` angular distance; the differentiability remark.
- The unit-half-circle construction for comparing different `L`, including the aliasing/fixed-point caveats.
- `n`-ary contour and rank reduction as a resolution continuum.

**What is mine, and therefore where the risk is:**
- Everything about applying this to a 10.767 Hz stream. **The paper has no notion of time, sampling, learning, or audio.** It is a static combinatorial theory of a single finite morph.
- The identification of possible-CC counts with the ordered Bell numbers (checked against the sequence, not stated in the paper).
- The claim that basis-space zeroing is strictly stronger than corpus demeaning.
- The soft-ranking bridge, and the claim that it preserves the linear-decodability argument.
- The `n`-as-lock/prefer-knob proposal.
- The kick-contamination hypothesis for band 0.
- The connection to the anti-loop `R(z)`.

**What would falsify the note:** E2 returning no movement on bass. If per-window zeroing does nothing that corpus-demeaning didn't already do, the "monotone invariance is what we were missing" story is wrong, and E4/E5 are probably not worth the effort. *(Update 2026-08-12: E1 has run and gives **directional** support — the kick-free bass **target** lifts bass +67 % rel — but E2 stays decisive: E1 changed the target, E2 changes the operation. And E1 surfaced that "kick contamination" is only part of the bass weakness, so even a clean win on E2 won't fully close the 55 Hz gap.)*

**What this note does *not* claim:** that contour beats TIV. They are complementary (§5.5), and TIV is the cheaper, safer, provably-free one. **If only one thing gets built, build TIV.** Contour is the higher-ceiling, higher-risk option.

---

## 9. References

**Primary**
- David Kant and Larry Polansky, "The Structure of Morphological Space," *Perspectives of New Music*. (PDF in Kim's Downloads; 57 pp.)

**Cited within it that we may want**
- Polansky and Bassein 1992, "Possible and Impossible Melody: Some Formal Aspects of Contour," *Journal of Music Theory* — n-ary contour, the impossibility proof.
- Polansky 1987, "Morphological Metrics: An Introduction to a Theory of Formal Distances," *Proc. ICMC*, 197–205.
- Polansky 1996, "Morphological Metrics," *JNMR* — OCD, OCM, UCD.
- Marvin and Laprade 1987 — CSIM, CEMB, normal form.
- Morris 1987, 1993, 2001 — COM-matrix, contour reduction.

**Ours / adjacent**
- Blondel et al. 2020, *Fast Differentiable Sorting and Ranking*, arXiv 2002.08871 — the differentiable bridge.
- `SAME_CHROMA_FINDINGS.md` — extractor recipe, constants, §6 UI design (now partly contradicted, see §5.4 and E1).
- `CHROMA_HANDOFF.md` — the exact SAME chroma recipe and its seven subtleties.
- `CONTROL_METHODS_SOURCEBOOK.md` — the control-injection taxonomy this slots into (Ch13).
- Fleet dialogue log, 2026-08-11 (CONTINUITY) — Tier-1/Tier-2 melody-conditioning validation.

---

## Appendix — constants worth not re-deriving

```
SAME latent rate        10.767 Hz   (44100 / 4096)
STFT window             185.8 ms    (8192 / 44100)
STFT hop                 92.9 ms    (4096 / 44100)   -> 2x overlap
n_latent_frames         ceil(T / 4096)
chroma shape            (3, 128, T)
band centres            55 / 880 / 14080 Hz   (octave 1 / 5 / 9, A0 = 27.5)
band octwidths          1.0 / 1.5 / 1.0
pitch class p -> bin    (128*(p+3)/12 - 30) mod 128     C = 2.0, A = 98.0
semitone                128/12 ≈ 10.667 bins
original head           Conv1d(256 -> 128, k=1, bias=True), L1, weights [0.035, 0.05, 0.2]

basis space dim         L - 1
CC length               (L^2 - L) / 2
possible CCs            ordered Bell (Fubini) numbers
n-ary full rank min     n' = (L-1) * n
unit half circle origin v = [1, 2, ..., L-1]_b
```
