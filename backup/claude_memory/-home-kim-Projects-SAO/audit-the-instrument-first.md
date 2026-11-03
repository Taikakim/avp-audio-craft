---
name: audit-the-instrument-first
description: "Kim's standing method (2026-08-28): a null is not a finding until the MEASUREMENT has been checked — broken meters fail toward 'no effect'."
metadata:
  type: feedback
---

Before reporting a null or a weak effect, audit the tool that produced it. A broken or
ill-chosen measurement almost never invents a result; it routinely **erases** one, so
nulls are systematically biased toward "the model can't do this".

**Why:** three instances in one day (2026-08-28), each already reported as a finding
before the instrument was checked — a metric blind to the question (chroma cosine on a
melody test: +0.022 n.s. → transcription gave +0.100, p=0.016), a broken script
(`z_f0height_probe.py` raised TypeError on every variant; fixed, corr 0.214 → 0.561,
the opposite conclusion), and a saturated metric (0.795–1.000 across every arm including
the negative control).

**How to apply:** (a) does the metric have DYNAMIC RANGE — how far apart do the
known-positive and known-negative arms score? (b) is there a TRIVIAL BASELINE and does
the number beat it? MAE 6.4 semitones means nothing until you know always-guessing-the-mean
scores 8.05. (c) has this tool ever produced a positive result, or is this its first run?
(d) prefer metrics that fail loudly — a saturated one is worse than none, it looks like data.

Tool-level companion to [[negative-result-autopsy]], which covers auditing the machinery
behind a null. Full write-up in `SAO/CLAUDE.md`. See also [[lightweight-tests-first]] —
cheap probes only de-risk if the probe itself works.
