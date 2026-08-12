# Evaluating Disentangled Representations for Controllable Music Generation

**arXiv 2602.10058v2** (15 Feb 2026) · Ibáñez-Martínez, Nkama, Poltronieri, Serra, Rocamora —
Music Technology Group, UPF Barcelona · 5 pp, ICASSP-format · read 2026-08-12 (WINTERMUTE)

Read in full from the PDF.

---

## What it contains

Three unsupervised **structure/timbre** disentanglement models for music audio — SS-VQ-VAE,
TS-DSAE, AFTER — evaluated with a probing framework adapted from `synesis` (Plachouras et al.,
IJCNN 2025) along **four axes** rather than the usual single one:

| axis | question it asks | how measured |
|---|---|---|
| **Informativeness** | is the property *in* the embedding? | probe accuracy / MSE |
| **Equivariance** | does an input transform produce a *predictable* embedding change? | P-equiv: predict transform params; R-equiv: predict transformed embedding (cos sim) |
| **Invariance** | do irrelevant perturbations leave it alone? | cos sim, clean vs perturbed |
| **Disentanglement** | does the *other* embedding carry residual info? | `Δ = \|Acc(g′(z_t ⊕ z_s)) − Acc(g(z_t))\|` — large Δ = entangled |

Transformations: pitch shift, time stretch, instrument change. Data: Slakh2100 (synthetic
multitrack; **mixes and drums excluded**), SynTheory probing sets, MAESTRO/MusicNet for
multi-pitch. Probes are shallow linear (SLPs) on frozen embeddings.

### The findings worth carrying

1. **Intended semantics ≠ actual semantics, systematically.** The labels "structure" and
   "timbre" do not survive measurement.
2. **Leakage is ASYMMETRIC and architecture-specific.** SS-VQ-VAE leaks little timbre into
   structure, but its *timbre* embedding carries substantial structural information. AFTER is
   the reverse — its *structure* embedding carries notable timbre. So "is it disentangled" has
   no single answer; you must ask per direction.
3. **Tempo is encoded in the TIMBRE embedding of all three models** — concatenation
   consistently improves tempo regression. A property everyone would call structural lives in
   the embedding everyone calls timbral, across three unrelated architectures.
4. **Informativeness trades off against equivariance.** Larger embeddings encode more and
   transform less predictably (SS-VQ-VAE: most informative, least equivariant; TS-DSAE:
   smallest structure embedding, strongest R-equivariance across all transformations).
5. **Disentanglement strategies act on separation, not on capture.** Adversarial losses and
   data augmentations most strongly affect invariance and disentanglement — "influencing how
   well factors are separated rather than how much information is captured".
6. **High reconstruction quality coexists with note-level probe failure**, implying the
   information is there but encoded in a highly complex (non-linearly-readable) way.

### Their own conclusion, which is the part that matters to us

Disentangled representations are **necessary but not sufficient**: "predictable control
requires decoders to preserve factor separation at the signal level". They close by naming
what is missing as future work — *"extending representation-level diagnostics with
output-level evaluations, including controlled generation experiments and perceptual
listening-based assessments of controllability."*

---

## What stays ours

**1 — The four-axis protocol is directly transplantable to our control heads, and we are
currently using one axis out of four.** Every control-head evaluation we run is
*informativeness* (does the measured feature move toward the request — the onset_eval
correlation, the LatCH gain ladders) plus a disintegration floor. We have **no equivariance
and no invariance measure at all**. Equivariance is the precise formalisation of the thing
Kim's gain ladders actually test by ear: not "did it move" but "did it move *predictably*".
Our own 08-06 finding that only `evr1x` tracked the rarity prompt band monotonically, while
base and newstack had mid > rare, is an equivariance failure described in prose because we had
no name for it.

**2 — The tempo-in-timbre result is a specific, cheap warning shot at the attribute-branches
plan.** We are building per-attribute control (onset density, brightness, bass weight…) on the
assumption those attributes are separable. Three unrelated architectures all leak tempo into
timbre. The concatenation-Δ test is cheap — train a probe on one embedding, retrain on the
concatenation, difference the accuracies — and would tell us whether our attribute controls
are actually independent *before* we spend GPU-months discovering they are not.

**3 — A caution to hold beside C's chroma readout, stated carefully.** C's Tier-1/Tier-2 work
establishes that band-chroma is READABLE from clean z0, timbre-invariantly and strongly
(cos12 0.79–0.86 synthetic; demeaned air 0.918 on real goa). This paper's central claim is
that good readout does **not** imply controllable output — the decoder must also preserve the
separation. That is not a criticism of the result; C's own post frames it as a *conditioner
target*, which is right. It is a reason to keep the readout claim and the control claim
separate in the record until a steering experiment closes the gap, and it names the axis the
gap lives on.

**4 — Their missing piece is the piece we happen to have.** They call for "perceptual
listening-based assessments of controllability" as future work. As of 2026-08-11 we have
exactly that: Kim's per-cell listening verdicts filed verbatim in run_meta sidecars across 12+
runs, against clip families with known control settings. That is an unusual asset — it is what
makes our CE-vs-ear finding (CE ranked his two favourites 1st and 8th of 8) a *measurement*
rather than an anecdote. If the four-axis protocol were run on our heads, we could correlate
each axis against his verdicts and find out which axis, if any, predicts his ear. That is the
open question from 08-11 with a concrete method attached.

**Do not transfer the numbers.** Slakh2100 is synthetic, **drums and mixes are excluded**
(fatal for us — our whole corpus is full mixes with dominant drums), probes are shallow linear,
and the transformation set is pitch/stretch/instrument. The *protocol* transfers; the
scoreboard does not.

**Cheap first step if we want it.** mir already generates the two transformations their
equivariance axis needs — we have pitch-shift and time-stretch tooling with scored outputs
(`pitch_shift_scores.csv`, `stretch_scores.csv`, the bungee binding). So an equivariance probe
on our own control embeddings needs no new augmentation machinery, only the probe.

---

## Status

Read + verified against the PDF (5 pp, read in full). Nothing implemented. The concrete
proposal above — run the concatenation-Δ disentanglement test on our attribute controls, and
correlate the four axes against Kim's filed verdicts — is a hypothesis with a clear first
experiment, not a result.
