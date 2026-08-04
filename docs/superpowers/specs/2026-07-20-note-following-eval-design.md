# Note-Following Authority — the go/no-go eval for the MIDI-frame conditioner

*Design spec, 2026-07-20 (CONTINUITY, at WINTERMUTE's request). The real v1 gate for
`2026-07-20-midi-frame-conditioner-design.md` (§9 step 4). Answers the one question that
decides whether the adapter is worth shipping: **does it FOLLOW the input note-roll, or does it
generate generic pitched goa that ignores the notes?** Companion to — not a replacement for —
Phase 0 (which W correctly demoted to a sanity check).*

---

## 1. The question, stated so it can't be gamed

"Does it follow the notes" has a trap: on tonal goa, *any* output will correlate with *any*
goa-ish roll (the chroma-trap — memory `sa3-riffer-findings`). Absolute agreement between output
and input roll is therefore **meaningless**. The eval must measure the thing a mode-collapsed
"generic goa generator" would FAIL: **differential response** — the output must change *toward the
roll* when the roll changes, and it must do so on rolls the model has never seen.

So the primary metric is not `agree(output, roll)`. It is the **cross-roll gap**:

```
GAP(A,B) = agree(out_A, R_A) − agree(out_A, R_B)
```

Render prompt P with two different rolls R_A, R_B. Transcribe both outputs. If the adapter
follows, `out_A` looks like R_A and *not* like R_B → GAP > 0. If the adapter ignores the roll and
emits the same generic goa either way, `out_A` is equidistant from R_A and R_B → **GAP ≈ 0**. A
deterministic recolor / mode-collapse cannot fake a positive GAP — only genuine roll-following can.
(This is the same discipline that killed the moment-losses in the residual-preservation pass:
match a *distribution/differential*, never an absolute a mode-collapsed model can satisfy.)

## 2. The metrics (per render, then aggregated)

Output transcription uses **MuScriptor on the full mix** (W's pivot — the in-distribution source;
the stem probe below shows why). Agreement is computed in two views so a win must survive both:

- **Chroma view (pitch-class, octave-agnostic):** fold input roll and output transcription to
  per-frame 12-d chroma; `agree = mean-frame cos`. Cheap, robust, but blind to octave.
- **Note view (pitch-exact, octave-aware — the one that matters):** align output notes to roll
  notes (onset within ±1 frame @10.77 Hz), report **pitch-accuracy**, **octave-correctness**
  (the roll's whole claim is that it carries absolute octave — this is where chroma-only methods
  can't compete), **onset-timing F1**, and **note-density ratio** (out notes/s ÷ roll notes/s).

Primary go/no-go number: **GAP in the note view**, on off-distribution rolls (§3). Chroma-view GAP
is the corroborating cheap signal.

**Faithful-but-not-stiff (the §8.3 tension, made measurable):** the roll is discrete; idiomatic
goa has slides/vibrato. So *some* output-vs-roll disagreement is DESIRED expression, not failure.
Separate the two:
- **skeleton-follow** = agreement at note *centers* / on sustained frames (should be HIGH).
- **expression** = pitch-continuity / inter-note glide energy present in the output but absent in
  the discrete roll (should be > 0 — it's the "flesh"). A stiff readout has expression ≈ 0; a
  wandering generator has skeleton-follow ≈ 0. We want both nonzero. This also validates the
  faithfulness-dial: sweeping the dial should trade skeleton-follow ↑ against expression ↓.

## 3. The axis that is the actual test: OFF-distribution rolls

A model that follows only goa-shaped rolls has memorized goa, not learned note-following — and it
will fail the product promise ("drop *any* MIDI"). So GAP must be measured across a rung of rolls
of increasing distance from the training distribution, same seeds/prompt throughout:

| rung | roll source | tests |
|---|---|---|
| D0 | held-out goa transcription | in-distribution positive control (should follow) |
| D1 | transposed goa (±3, ±7 semitones) | pitch-shift invariance — does it track the shift or snap back to the trained key |
| D2 | time-stretched / thinned / thickened goa | rhythm/density generalization |
| D3 | **non-goa melody** (a major scale, a simple tune, a bassline in a foreign key) | the real product case — arbitrary user MIDI |
| D4 | sparse **single held notes** (2–8 s) | the legato/sustain failure directly (does a held note render as a held note, or get chopped — the MuScriptor-fragments-sustains risk) |

**The verdict lives on D3/D4, not D0.** GAP that is positive on D0 but collapses to ≈0 by D3 =
memorization, **v1 fails** (needs the note-space augmentation from spec §4, or the whole approach
is reconsidered). GAP that holds on D3 and D4 = genuine note-following, **v1 passes**.

## 4. Harness (all reuse; no new heavy infra)

- **Rolls:** the rasterizer from the conditioner pipeline (`.MIDIROLL.npz` builder) generates D0–D4
  (D1–D4 are cheap transforms of D0 rolls + a handful of hand-authored non-goa MIDIs).
- **Render:** the adapter's `generate` path (once it exists).
- **Transcribe output:** `eval/muscriptor_stem_probe.py`'s MuScriptor-full-mix call + `note_stats`
  (already written for the gate-#0 probe — reuse the model-load + transcribe).
- **Agreement:** `fold_to_12` / `compute_same_chroma` (mir-same-chroma) for the chroma view; a small
  note-aligner (onset-matched pitch compare) for the note view — ~1 new function.
- **Baseline / Δ discipline:** every GAP is a difference of agreements (no absolute number is
  trusted), so the chroma-trap is structurally excluded.
- Output: `note_following.json` per checkpoint (GAP per rung, skeleton-follow, expression, note-view
  breakdown) + a shared-playhead listening page (the ear is still the final verdict — Kim's rule).

## 5. Go / no-go thresholds (falsifiable, set before the run)

- **PASS:** note-view GAP > 0.15 (well above the seed-noise floor, calibrated on a same-prompt
  different-seed null) on **D3**, and D4 held notes render with sustained-fraction within ~2× of the
  roll's (not chopped to zero). Ship v1; wire the faithfulness dial.
- **CONDITIONAL:** GAP positive through D2 but < 0.15 on D3 → the adapter follows goa-shaped rolls
  only. Add/strengthen note-space augmentation (§4 of the conditioner spec), retrain, re-run. Not a
  ship.
- **FAIL:** GAP ≈ 0 on D1 already, or D4 held notes always chopped → the adapter isn't using the
  roll (mode-collapse toward conditional-mean goa — the residual-preservation failure, in the note
  domain). Stop; the injection mechanism (spec §3 "the crux") or the whole notes-as-conditioning
  premise is wrong, not a tuning problem.

## 6. Negative space / what this eval deliberately does NOT do

- It does **not** measure audio quality (that's Audiobox + Kim's ear on the listening page — kept
  separate so a following-but-ugly result is legible as such).
- It does **not** use Phase-0's chroma agreement as a pass signal — that's a two-extractors-agree
  sanity check on the *representation*, not the *adapter* (spec §6 caveat). This eval is the adapter
  gate.
- It does **not** trust any absolute agreement number — only GAPs and dial-sweeps, by construction.

## 7. The gate-#0 data this rests on (2026-07-20 stem probe, CONTINUITY)

`eval/muscriptor_stem_probe.py`, 10 Goa_Separated tracks, MuScriptor-medium, matched 60 s windows:

| source | median notes | notes/s | sustained>1 s |
|---|---|---|---|
| **full_mix** | **1305** | 21.8 | 0.000 |
| bass stem | 366 | 6.1 | 0.000 |
| other stem | 641 | 11.6 | 0.005 |

**bass < full_mix on 10/10 tracks; other < full_mix on 10/10.** Corpus-wide confirmation of the
task-#41 single-track result: **stems are systematically worse for MuScriptor** (it was validated
on full mixes, and BS-RoFormer/Demucs separation output is out-of-distribution for it). This
validates W's full-mix pivot empirically. **Two caveats that survive the pivot and feed §2/§3:**
(1) `sustained>1 s ≈ 0` on *every* source — the legato/sustain drop is universal, so D4 (held-note
recovery) is a first-class rung, not an afterthought. (2) full-mix MuScriptor collapses to a
near-mono **bassline** with collapsed instrument labels (#41: "one electric-bass track"; other-stem
"all labeled electric bass") — so W's "route the per-instrument output to bass/mid/high tiers" needs
a real check: MuScriptor may not *give* separable per-tier notes even from the full mix. If it
doesn't, the 3-channel roll degrades to "bass channel + label-collapsed rest," and the tier design
(conditioner spec §3) needs rethinking. Flagged to W separately.
