---
name: steering-improvement-criteria
description: "What Kim counts as an improvement when LatCH/control heads fix a render (coarseness, missing bass, rounder balance); loudness/dynamics changes are NOT improvements"
metadata:
  node_type: memory
  type: feedback
  originSessionId: cd7a9ba8-7c77-4763-a269-4b41c0eb857d
  modified: 2026-10-14T11:51:02.936Z
---

When judging steered vs unsteered renders (bass/body RMS heads on the punch DoRA clips, 2026-10-14), Kim's criteria:

- The real improvement was **less coarseness/grain and the missing bass restored**; he describes it as "rounding of the sound to a more balanced whole".
- The **loss of dynamics was an accepted side effect, not an improvement**. A louder, more compressed/saturated result must not be scored as better.
- **Punchiness comes from snappy envelopes and good spectral separation**, not loudness.
- A control that **keeps dynamics stable** (crest factor / envelope) would force the model to make real edits instead of just raising volume and squashing.
- Outcomes differ strongly between seeds, so one seed proves nothing; he wants many seeds and his own 1-5 ratings (1 worsening, 3 neutral, 5 marked improvement of overall sound quality).

**Why:** my first reading counted Audiobox/CLAP/loudness/crest shifts as "better"; those shifts partly come from the steered clips simply being ~50% louder and more compressed.

**How to apply:** compare steered vs baseline at MATCHED loudness; treat crest factor / loudness-envelope changes as costs, not gains; never present a meter gain as "better" without his ratings; any retraining with "new controls" should include a dynamics-preserving term or a loudness-matched evaluation. See [[fleet-handle-identity]] for who I am in this tree.
