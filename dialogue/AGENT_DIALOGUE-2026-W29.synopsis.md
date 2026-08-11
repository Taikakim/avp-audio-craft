# Week 2026-W29 synopsis (Jul 13 – Jul 19)
*115 entries · the week long-form steering stopped being theory and moved a metric*

The fleet spent the week chasing one question from two directions: why do long generations collapse into loops, and can the model be pushed past its own training horizon. The throughline was longform continuation — a run of research-report triages narrowed the field to a single family of "drives" against the loop attractor (prompt-arc, breathing control, tilted sampling, an operator-theoretic skeleton), and by Thursday the first of those actually landed: an anti-loop guide, framed as FK-Flow-style tilted sampling, halved a repetition metric on real audio — the first intervention on the stack to move its target since two earlier nulls. In parallel, the supercomputer path came alive: after a stubborn kernel-cache blocker, the first clean training run on the HPC cluster proved the whole pipeline end-to-end. Not everything won. A stereo-width investigation dissolved a favored "drift" story; a mid/side stereo-loss sweep silently failed twice under masked out-of-memory errors; and the human listening check confirmed long single-window renders sound smeared, exactly the training-length mismatch the campaign was built to fix.

## Headlines
- First successful model training on the HPC cluster — full path proven; root-caused the kernel-cache blocker to a disabled-cache workaround.
- First confirmed anti-loop steering result: a tilted-sampling guide halved a loop metric (line-fraction 0.52→0.28) at measurable but mild quality cost — human ear-check pending.
- SaFa join intervention verdict: real but narrow — it fixes seam energy character, does NOT reduce loopiness; loopiness stays orthogonal to the join method.
- New crop convention: training lengths in frames as multiples of 256 (seconds-based crops tiled badly on the GPU architecture).
- Expanded audio-feature sweep completed corpus-wide (a uniform expanded field set); one embedding dropped for scoring below a raw-spectral baseline; a mislabeled chroma field renamed to what it actually computes.
- Found the training path silently casts fp32 attention to fp16 — no run had ever computed true fp32 attention; fp32/long-context comparison campaign built and launched.
- Steering-head sweeps refuted several stale "dead head" verdicts: only two rhythmic heads are genuinely dead; a 12-d chroma head steers harmony strongly despite its old label.
- Stereo collapse at long context is constant, not progressive — kills the drift-accumulation explanation for that failure mode.
- Shipped public research surfaces: a paper-verdicts "what we actually tested" page (adversarially fact-checked) and a paper-gap audit yielding three cheap, confirmed wins.
- Process hardening: a write-only public-comment boundary, a post-task records protocol, and a standing open-threads ledger that caught a 16-day-old doc contradiction and a wrongly-repeated "single-copy backup" premise.
