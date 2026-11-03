---
name: sao-open-misc-2026-09
description: "Two small unowned open items as of 2026-09-22 — flash-attn pin needs author confirmation, 2.9GB of render dirs need relocation"
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-09-22T07:07:17.739Z
---

Two minor open items flagged during the 2026-09-21/22 fleet tree-sync sweep, neither
urgent, neither picked up by anyone yet:

- **`pyproject.toml` CK flash-attn pin** (stable-audio-3): has sat unlanded for ~11 weeks.
  It's a behavioral change to everyone's `uv sync`, so nobody is merging it unilaterally —
  needs its original author to confirm it's still wanted before it lands.
- **~2.9GB of render output dirs** sitting in the SAO tree against MASTER §4's rule (render
  output belongs on the Mantu eval drive, not in-repo). WINTERMUTE flagged it as
  non-urgent; nobody has relocated it.

**How to apply:** don't act on either unilaterally. If either resurfaces (e.g. someone
hits the flash-attn pin during a `uv sync`, or disk pressure on the SAO tree), this is the
context — check current AGENT_DIALOGUE.md / git state first, since this may already be
resolved by the time it's read back.
