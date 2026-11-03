---
name: negative-result-autopsy
description: "Kim's standing method — a null may be an implementation artifact; after any failure, audit the machinery, enumerate failure points, and run Deep Research on candidate explanations"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
  modified: 2026-08-01T05:08:31.708Z
---

Kim direct (2026-08-01): "negative results can seem such because we lacked knowledge of a
specific bit of implementation. We should always look after the machinery after a failure,
recognise the possible failure points and run Deep Research runs for possible answers."

**Why:** a null conflates "the effect doesn't exist" with "our probe couldn't see it."
Proving case: G2 phase probe (linear slow-modulation readout) returned CLOSED; Kim's G2b
shift-sweep (different machinery, same question) reversed it within a day — carrier phase
was in the code all along as 2-plane rotations.

**How to apply:** every null/failed experiment gets a MACHINERY AUTOPSY before its verdict
is recorded as final: (1) list the implementation choices that could mask the effect
(operationalization proxy, thresholds, basis, readout capacity, scope of comparison);
(2) rate each as plausible-mask vs unlikely; (3) for plausible masks, either run the
cheap alternative probe or draft a fact-dense Deep Research brief asking how others
measured the same quantity. Record nulls with scope qualifiers ("null under proxy X"),
never as bare closure. Related: [[lightweight-tests-first]].

Tool-level companion: [[audit-the-instrument-first]] — audit the METER before the machinery. Three 2026-08-28 nulls were artefacts of the measurement, not the model.
