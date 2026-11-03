---
name: sao-gemini-brief-convention
description: "SAO fleet convention for writing Gemini Deep Research briefs — problem + phenomenology only, never code/file references"
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
---

In the SAO project ([[my-role-overseer]]), THE-FINN (me) drives Gemini Deep Research
lit-survey briefs (e.g. `docs/research-brief-<topic>.md`). CONTINUITY discovered
(2026-07-15, `docs/ai-research/gemini-report2-assessment-2026-07-15.md`) that when Kim
fed Gemini a SECOND brief that included our own code, the report closed into a citation
loop — 8 of 32 "works cited" were our own source files, and its two "flagship"
external papers turned out to be ones our code already implements and cites in its own
docstrings (rope_jitter.py, LatCH). The report read as external validation but was
mostly our own writing reflected back in literature voice.

**Rule going forward: feed Gemini the problem + phenomenology (architecture facts,
observed behavior, math framing) — never file names, function names, or source code.**
A first brief written this way (`research-brief-longform-continuation.md`, same day)
produced a genuinely external, useful result (FK-Flow, AID, CQT-Diff — real papers
neither the brief nor our code had cited before).

**How to apply:** before sending any future Gemini Deep Research brief for this
project, grep the draft for `.py`/file paths/function names — if any appear, strip
them down to the underlying phenomenon before it goes out.
