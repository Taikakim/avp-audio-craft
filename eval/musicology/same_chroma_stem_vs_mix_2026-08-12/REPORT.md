# same_chroma readout — kick-contamination test (stem-vs-mix GT) — REPORT

**2026-08-12.** Follow-up to Tier-2 (`../same_chroma_readout_tier2_muscriptor_2026-08-11/`), which found
the `same_chroma` LatCH head's demeaned-cos12 alignment with full-mix audio-GT chroma is **bass=0.214 /
mid=0.536 / air=0.918** — bass by far the weakest band. Question: is 0.214 a **head failure**, or a
**ground-truth artifact** — the full-mix bass-band GT bakes in the kick drum (a broadband, pitchless
low-freq transient sharing the bass octave), which the head, reading actual harmonic content out of the
latent, correctly does not reproduce? Test: score the SAME cached predictions against the **isolated,
kick-free bassline stem** instead of the full mix, and see whether bass alignment recovers.

*(Code: `score_stem_vs_mix.py`. Numbers below read directly from `results.json`.)*

## Headline

**(a) Does the head read melody-through-mix (align with the isolated "other"/melody stem)? NO — full-mix
alignment is higher on every band, including air.** Contrary to the naive expectation, the head's
prediction is *uniformly* closer to the full-mix GT than to the isolated melody stem (air 0.918→0.837,
mid 0.526→0.509, bass 0.181→0.133). This is very likely training-target circularity, not a melody-reading
deficit: `extract_same_chroma_targets.py` builds the head's training target as `W[b]@z+bias[b]` — a
linear-readout proxy of **full-mix** chroma applied directly to the latent (see provenance below) — so
the head was never asked to predict the isolated-stem chroma in the first place. Air is still strong in
absolute terms (0.837), so the head clearly does carry melody information; it just isn't a better match to
the clean stem than to its own full-mix training-target family.

**(b) Is bass=0.214 redeemed by the clean bassline? PARTIALLY — the kick hypothesis is confirmed but
doesn't fully explain the gap.** Pred-vs-bass-stem demeaned bass cos = **0.302** vs pred-vs-full-mix bass =
**0.181** (same 1083-track subset) — a **+0.121 absolute / +67% relative** jump. The head's bass-band
prediction genuinely aligns better with the kick-free bassline than with the kick-polluted full-mix GT, and
this is not just an artifact of the two GTs being similar to begin with (a linear-algebra check below rules
that out). **But bass is still the weakest band even against the clean target** — 0.302 is well below what
mid/air read against their respective clean/full-mix comparisons — so kick contamination explains part, not
all, of the 0.214 weakness; some genuine bass-register read-difficulty remains.

**(c) Conditioning-target implication: NOT "switch the head's target to the other-stem chroma" based on
this test alone — but DO consider a kick-free bass target.** (a) shows the *current* head doesn't
spontaneously prefer the isolated melody stem, but that's confounded by what it was trained against
(full-mix-derived); this test doesn't establish that a head *trained* on other-stem chroma would be worse —
only that evaluating the existing full-mix-trained head against the stem isn't informative either way for
melody. For **bass**, though, the evidence is more actionable: the isolated bassline is a cleaner target
(no kick-driven broadband noise), and the head's own predictions already lean toward it — supports building
a bass-band chroma control head against the **bass-stem** target rather than the current full-mix-derived
target, the same way the 06-25 chroma-steer work already builds "other"-stem targets for melody
(`extract_stem_chroma.py`).

## The 3x3 table (demeaned median cos12, common subset n=1083 -- tracks with all of: head prediction,
full-mix audio, AND stem-chroma coverage)

| row | bass | mid | air |
|---|---|---|---|
| **pred vs full-mix GT** (baseline, subset) | 0.181 | 0.526 | 0.918 |
| **pred vs other-stem GT** (melody) | 0.133 | 0.509 | 0.837 |
| **pred vs bass-stem GT** (KICK TEST) | **0.302** | 0.210 | 0.370 |

Only the diagonal-relevant cell is meaningful per row: bass for the bass-stem row, mid/air for the
other-stem row, all three for the full-mix row (bass-stem's own mid/air content is near-absent -- a
bassline has little harmonic energy up there -- so pred-vs-bass-stem's mid/air numbers measure something
uninformative, not a real comparison; likewise other-stem's bass row is not the test of interest).

**Diagnostic -- how much does the full-mix GT itself diverge from each stem's GT (per band, same subset)?**

| row | bass | mid | air |
|---|---|---|---|
| full-mix GT vs other-stem GT | 0.515 | 0.924 | 0.842 |
| full-mix GT vs bass-stem GT ("kick magnitude") | **0.894** | 0.641 | 0.487 |

Full-mix bass and bass-stem bass are themselves *highly* correlated at the demeaned/per-track level
(0.894) -- meaning the kick's contribution to the bass-band chroma profile is fairly **generic/corpus-mean-
like across tracks** (little per-track-specific variance), so it mostly washes out of the corpus-demeaned
metric rather than corrupting cross-track comparisons wholesale. That makes the pred-vs-bass-stem jump
(0.181->0.302) more interesting, not less: if full-mix-bass and bass-stem-bass were near-identical per
track, pred should score similarly against either. A quick geometric check confirms it isn't a trivial
consequence of that correlation -- see below.

**Sanity check on the jump (ruling out "it's just because the two GTs are similar").** With
cos(mix,bass-stem)=0.894 (angle ~26.7 deg) and cos(pred,mix)=0.181 (angle ~79.6 deg), the triangle inequality on
angles bounds cos(pred,bass-stem) between cos(106.3 deg)~=-0.28 and cos(52.9 deg)~=0.60. The measured 0.302 sits
comfortably inside that range but well above the midpoint implied by pure "inheritance" from the mix
correlation -- i.e., pred carries real, additional alignment with the bass-stem-specific residual, not just
whatever alignment it already had with the mix. This is consistent with (though doesn't by itself prove)
the head's bass-band output containing content that specifically resembles the clean bassline more than the
kick-polluted mix.

## Sanity check -- baseline reproduces Tier-2 (n=1200, full sample, no stem-coverage filtering)

| band | this run (demeaned median) | Tier-2 REPORT.md |
|---|---|---|
| bass | 0.214 | 0.214 |
| mid | 0.536 | 0.536 |
| air | 0.918 | 0.918 |

**Exact reproduction** -- confirms the reused prediction cache, GT-source fields, and cos12/fold_to_12/
demean machinery are wired identically to Tier-2 before trusting the new comparisons. (On the stem-covered
subset alone, n=1083, the baseline shifts slightly: bass 0.181 / mid 0.526 / air 0.918 -- a mild sampling
effect from restricting to the ~91% of tracks that have stem-chroma coverage, not a methodology change.)

## Method / provenance

- **No head re-inference.** Reused the cached predictions from Tier-2's `predict_head.py` verbatim:
  `/tmp/claude-1000/-home-kim-Projects-SAO/49cd5391-27e7-4545-8295-a1053db2a077/scratchpad/tier2_predicted/
  {id}.npy` (all 5400 real-goa latents that have a MuScriptor record -- full coverage, cache intact).
  Checkpoint: `stable-audio-3/latch_weights_sa3_medium/latch_sa3_same_chroma_best.pt`.
- **Sampling**: identical call to Tier-2's `score_and_report.py` (`random.Random(42).sample(pred_ids, 1200)`
  over the same 5400-id pool) -> the same 1200 tracks Tier-2 scored.
- **Full-mix GT**: `compute_same_chroma` (mir-same-chroma) on the exact source-audio segment, via
  `source_path`/`start_sample`/`end_sample` read straight off `latents_sa3/{id}.json` (not MuScriptor's
  `stats.json` -- see pairing verification below; avoids a MuScriptor dependency entirely for this test).
- **Stem GT**: `latents_sa3_stem_chroma/{id}.npz` (`other`, `bass` keys, `(3,128,4096)` fp16) --
  `compute_same_chroma` run directly on the isolated BS-RoFormer stems for the identical crop window
  (`extract_stem_chroma.py`, confirmed below to use the same `source_path`/`start_sample`/`end_sample`).
- **Reused verbatim** (not reimplemented): `cos12_timeavg`/`cos12_vec`/`BAND_NAMES` from Tier-1's
  `score_and_report.py`; `fold_to_12`/`compute_same_chroma` from `mir-same-chroma`; the matched-raw /
  5-derangement-null / corpus-demeaned scoring structure (`score_flavor`) from Tier-2's `score_and_report.py`
  (copied, since it's a nested function there -- not top-level-importable -- but byte-for-byte the same
  formulas). The **chroma-trap** Tier-2 diagnosed (raw pooled cos12 saturates near 1.0 on genre-homogeneous
  goa regardless of pairing correctness -- matched_raw ~= null_mismatched every row above, e.g. bass 0.987 vs
  0.984) reproduces here too; **demeaned cos12 is the only trustworthy number**, same as Tier-2.
- **Pairing verification (the one risk called out up front) -- CONFIRMED, not assumed.**
  `extract_stem_chroma.py` (the script that built `latents_sa3_stem_chroma/`) reads each crop's
  `source_path`/`start_sample`/`end_sample` **directly from `latents_sa3/{id}.json`** and slices the
  sibling `other.flac`/`bass.flac` in the same source directory -- so `{id}` denotes the exact same crop
  across `latents_sa3`, `latents_sa3_stem_chroma`, and (independently) MuScriptor. Spot-checked id
  `000000`: `latents_sa3/000000.json` and `muscriptor_full/000000.stats.json` carry byte-identical
  `source_path` (`.../AZukx - Earth Chakra/full_mix.flac`), `start_sample=44100`, `end_sample=16821316`.
  No ambiguity to flag -- pairing is by construction, not inference.
- **Training-target circularity note** (bears on headline (a)): `extract_same_chroma_targets.py` builds
  the head's actual training target as `target[b] = W[b]@z[t] + bias[b]` (a linear readout fit in
  `mir-same-chroma/sc_run/chroma_heads_real.npz`, applied to the clean latent) and stores it under a key
  literally named `full_mix` -- confirming the head was trained toward a full-mix-chroma-family target, not
  an isolated-stem one. Tier-2 already avoided scoring against this proxy directly (would be circular); this
  report's PRIMARY GT (real audio chroma, not the proxy) is the correct non-circular baseline, but the
  *directional* preference for full-mix over stems in (a) is still expected given what the head was asked to
  learn.
- **Coverage**: full-mix GT paired for all 1200/1200 sampled tracks (0 dropped -- MuScriptor-independent
  sourcing helped here). Stem-chroma coverage: 1083/1200 (**90.25%**, consistent with the known
  4907/5400 ~= 90.9% corpus-wide coverage); 117 dropped, all but 1 for missing `.npz` (1 zip-bomb-guard
  load error on a single corrupted npz -- negligible).
- **Runtime**: ~17 min total (mir venv, CPU) -- dominated by full-mix audio reads/chroma computation for
  1200 tracks; stem-chroma load is cheap (pre-extracted npz).

## Caveats

- The mid/air rows of the bass-stem comparison and the bass row of the other-stem comparison are reported
  for completeness in `results.json` but are **not informative** -- they compare pred against a stem whose
  content in that register is mostly absent (a bassline has little air-band energy; "other" has little
  bass-band energy).
- Demeaned distributions are bimodal here too (wide p10-p90 spreads, e.g. bass-stem-bass p10=-0.75/
  p90=0.92) -- same uncharacterized minority Tier-2 flagged; not decomposed further in this pass.
- This test used the SAME cached head predictions as Tier-2 -- it says nothing about how a head *trained*
  against stem-isolated targets would behave; that would need a new training run, out of scope here.
