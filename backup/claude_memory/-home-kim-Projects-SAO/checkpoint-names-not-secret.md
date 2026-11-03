---
name: checkpoint-names-not-secret
description: Checkpoint filenames may appear on public eval pages; no redaction needed (Kim 2026-10-29)
metadata:
  node_type: memory
  type: feedback
  originSessionId: 6d4a930a-7d27-4f73-9569-3056349b8b0d
  modified: 2026-10-29T08:06:44.922Z
---

Checkpoint names (e.g. `latch_sa3_hpcp_best.pt`, run labels) are NOT secret and do not need to be redacted from eval pages or recipes.

**Why:** Kim direct 2026-10-29, after W hand-redacted head filenames from the published E21 page: "there's nothing secret in them".

**How to apply:** page builders can print checkpoint names in recipe/repro lines. Drive paths and credentials are still a separate matter — the no-secrets rule ([[post-to-chat-on-milestones]] public channels) still covers passwords/keys.
