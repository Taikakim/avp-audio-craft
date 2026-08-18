# Training-set metadata: the standing spec

**Status:** binding for every corpus we build metadata for, from 2026-08-18.
**Owner:** WINTERMUTE (Kim's direct routing, 2026-08-18). Corrections welcome — post them.
**Why it exists:** the goa big-set shipped to training with metadata nobody could see was
wrong, and it was the second or third corpus to do so. Full incident:
`docs/goa-captioning-status-2026-08-18.md`.

---

## 0. The one rule

> **Every metadata tier must be checked against a signal derived INDEPENDENTLY of whatever
> produced it, before any GPU-hours are spent on it.**

Everything below is machinery for obeying that rule. If you remember nothing else, remember
that a check which shares a source with the thing it checks cannot fail in the way that
matters. (Framing: CONTINUITY, 2026-08-18.)

---

## 1. Why the obvious checks did not catch it

Three people ran three checks on the same sidecar. **All three passed. The data was wrong.**
They were not sloppy checks — they were answering different questions, and only one of the
three questions can catch a corpus that is uniformly, confidently wrong:

| check | question it answers | caught it? | why |
|---|---|---|---|
| **Consistency** | do the tiers agree about this track? | partly | internal. Sharp — the t2/t3 tempo cross-check exposed a stale build — but two tiers can agree while both are wrong. |
| **Grounding** | does this tag reflect *its own* track's prose? | yes, for one bug | internal. Caught text confabulated from a filename (1.24× ≈ chance). Blind to prose that is well-grounded and factually false. |
| **Correctness** | is the prose TRUE about the world? | only this one | **needs an external reference.** We had one — effnet genre — sitting unused. |

**Consistency and grounding are both internal.** A corpus can be perfectly self-consistent,
perfectly grounded, and describe the wrong genre on 98.8% of tracks. That is exactly what
happened.

---

## 2. The mandatory pre-flight gate

Before a corpus's metadata is used in a training launch, all five must pass and the result
must be recorded (§6). No exceptions for "it's the same pipeline as last time" — see §4.

1. **COVERAGE.** Every training item resolves to a metadata entry, measured on the ACTUAL
   keys the trainer will use, not on counts. `1260 latents / 1260 sidecar entries` is not
   coverage; `1260/1260 keys resolve` is. Assert ≥99% and fail the job on a miss.
2. **GROUNDING.** Each derived tier reflects its own source. Directed containment lift,
   IDF-restricted (`eval/audit_caption_sidecar.py`). **≫1 grounded, ≈1 = generated from
   something other than that track.** Reference points: goa pre-fix 1.24× (broken),
   suomisoundi 16.17×, goa v5 19.24×.
3. **CORRECTNESS against an external signal.** Compare the metadata's claims to a signal
   produced by a *different* system (§3). Report agreement as a number. A large disagreement
   is not automatically an error — it is a mandatory human decision point.
4. **CONSISTENCY across tiers.** Where two tiers describe the same track, they must agree on
   checkable facts. Tempo is the cheapest: same track, same BPM. Read the *distribution* of
   the delta, not a pass/fail — rounding gives small deltas, a fat tail past 20 BPM means
   the tiers are not describing the same audio.
5. **DISTRIBUTION, not just presence.** How many DISTINCT prompts does a tier really carry,
   and what does the sampling ratio actually buy (§5)? `eval/caption_sidecar_audit.py`.

**Both audit tools are mandatory, not alternatives.** They cover different failure modes:
grounding (`audit_caption_sidecar.py`) and distribution/correctness
(`caption_sidecar_audit.py`). The confusingly similar names are a known wart — they were
written hours apart by two instances who were not reading each other. Fixing the names is
fine; dropping one is not.

---

## 3. Where the external reference comes from

The external signal must not descend from the thing being checked. For our corpora:

| metadata being checked | valid external reference | NOT valid |
|---|---|---|
| MF/LLM genre claims | **effnet `genre400`/`moodtheme`** (mir's Essentia suite, per track) | another LLM pass over the same caption |
| any LLM caption's tempo | measured BPM (`.INFO` / madmom / essentia) | the caption's own stated BPM |
| key/chord claims | HPCP / `chroma_linmap` / chord fields | the same model's prose |
| structure claims | beat/downbeat activations, section fields | — |
| a *revision* tier (Granite) | the tier it revised, plus one non-LLM signal | the revision alone |

**mir already extracts every one of these.** The goa failure was not a missing signal; it was
a signal that existed, was verified correct on 2026-08-02, and was never wired into the step
that needed it. When a corpus is captioned, the per-track features are usually already on
disk — use them.

**Corollary, and the specific fix for the incident:** any captioning/labelling step that can
accept a genre or style hint MUST be given one, and it should be derived per track from the
external signal where one exists — not a single global string typed at launch, and never
empty. A global string is the fallback, not the design.

---

## 4. Nothing is portable between corpora until re-derived

Every one of these was inherited from goa onto another corpus and silently meant something
different. Assume there is another one and go looking.

- **Key scheme.** goa live-encodes and keys by audio relpath; suomisoundi is pre-encoded and
  keys by latent-filename stem. Copying one convention onto the other silently drops every
  caption. A key MISS returns `{}` — no reject, no warning — so the run trains on empty
  prompts and you find out from the renders.
- **Tier semantics.** goa's t1 is per-track (effnet); suomisoundi's t1 is ONE corpus-wide
  string. Same field name, different information content.
- **Sampling ratios.** `--caption_probs 0.6,0.3,0.1` was tuned where t1 varies per track. On
  a corpus whose t1 is constant it hands 60% of every epoch an identical prompt.
- **Per-source ratios.** With multiple `--encoded_dir` sources the ratio is now
  semicolon-separated per source, in `--encoded_dir` order. One global tuple across corpora
  of different caption quality can only poison the good or hold it hostage.
- **A missing tier falls back to t1 SILENTLY.** Check the tier you intend to sample actually
  exists: `goa_longform_sidecar.json` has no entries carrying both t2 and t3.

---

## 5. Distribution: what "diverse captions" actually means

**String-uniqueness is not diversity and must never be reported as if it were.** The
contaminated goa tier was 23203/23231 unique strings — and carried almost no per-track
information, because a template slot-filling two adjectives and a BPM emits near-unique
strings forever. Measure instead:

- distinct N-word openings (**scale N with tier length** — at 3 words every prose caption
  reads as "100% identical" because they all begin *"This track is a"*; use ~10 for prose)
- vocabulary size across the tier (goa t2: 898 words pre-fix → 1922 post-fix)
- the share of the corpus taken by the single most common opening
- what the sampling ratio buys: `tier share × distinct prompts in that tier`

---

## 6. Provenance, and the stale-derivative trap

**A sidecar is a DERIVATIVE. Regenerating its source changes nothing until it is rebuilt.**
This bit twice in one incident: an audit run after the Granite re-run reported the identical
contaminated numbers, because the sidecar was still the Aug-4 build and the fixed captions
sat unused beside it.

Therefore:
1. Regenerate the source → **rebuild the derivative** → **re-audit the DERIVATIVE, not the
   source.** The audit must name the artefact and its mtime in its output.
2. Every metadata artefact carries provenance: what produced it, from which inputs, when,
   with which model **and model version** (ours differ by venue — LUMI revisions run
   `ibm-granite/granite-3.3-8b-instruct`, mir's local path runs `granite-4.0-h-tiny-Q8_0`;
   they are not interchangeable and nothing warns you).
3. Record the gate results (§2) beside the artefact, with the numbers, not a checkmark.
4. Existing convention this extends: `run_meta.json` on every output dir (MASTER §4).

---

## 7. Checks that look like diligence and are not

Recorded as negatives so nobody re-derives them:

- **Exact-duplicate rate** — 0.2% dupes on the broken tier. Blind by construction.
- **Symmetric Jaccard** between tag and prose — ~0.026 whether paired or shuffled, because a
  10-word tag against a 100-word paragraph has its union dominated by the paragraph. The
  working metric had to be *directed* (normalised by the short side) and IDF-restricted.
- **File mtime** as evidence a fix applied — a job launched before a fix keeps writing after
  it. Timestamps are circumstantial; **content is dispositive.**
- **Counting files** — `1261 .npy / 1260 .json` looked like a gap and was correct
  (`silence.npy` is the padding latent, filtered by design). Counts need a reason, not a
  match.
- **Spot-reading a few captions** — the broken tier reads perfectly well per sample. Its
  fault was only visible in aggregate, against another signal.

---

## 8. When a check fails

1. **Do not launch.** The gate exists because the cost asymmetry is extreme: minutes to
   check, node-days to discover it in the renders, and an unknown number of results already
   interpreted against bad conditioning.
2. Say which of the three questions failed (§1) — consistency, grounding, or correctness.
   They have different causes and different fixes.
3. **Check whether the failure reaches other corpora**, and post it. Sweep the class, not the
   instance.
4. If a disagreement with the external reference is legitimate — the archive genuinely
   contains adjacent genres — record the number and the reasoning. The hinted goa re-caption
   lands at 89.1% goa, and 89.1% is the *right answer*, not a shortfall.

---

## 9. Checklist (copy into the run's notes)

```
CORPUS: ________  ARTEFACT: ________  BUILT: ________ (mtime)  BY: ________ (script @ commit)
[ ] coverage      ____/____ keys resolve on the trainer's own key scheme (≥99%)
[ ] grounding     ____x directed containment lift (≫1; ~1 = not grounded)
[ ] correctness   ____% agreement vs ____________ (external signal, names the producer)
[ ] consistency   tempo delta distribution: <1 ___%  1-5 ___%  5-20 ___%  20+ ___%
[ ] distribution  tier shares × distinct prompts: t1 ___  t2 ___  t3 ___
[ ] derivative    rebuilt from source AFTER the last source change?   source mtime: ________
[ ] portability   key scheme / tier semantics / ratios re-derived for THIS corpus, not inherited
[ ] provenance    model + version recorded; gate numbers stored beside the artefact
```

---

## 10. Open

- **Timeseries metadata** (whole-track npz: field set, native per-field rates, stem-dependent
  fields, the `--add-fields` backfill asymmetry) needs its own §3 external-reference table.
  Being audited now; this section lands when that audit reports rather than being guessed at.
- Rename one of the two audit tools so they stop being confusable.
- Wire the effnet per-track genre into the captioning hint step, so §3's corollary is
  structural rather than a thing to remember.
