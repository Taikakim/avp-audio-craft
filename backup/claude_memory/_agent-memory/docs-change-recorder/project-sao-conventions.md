---
name: project-sao-conventions
description: Documentation conventions for the SAO (stable-audio-3 + mir + stable-audio-tools) project family — where facts go, house style, and structural rules
metadata:
  type: project
---

**Doc ownership (cross-repo facts → MASTER.md; completed work → WORKLOG.md; repo detail → per-repo docs/).**
- `/home/kim/Projects/SAO/MASTER.md` §5 = canonical gotcha list (cross-project). Keep entries terse; new measurements append to the relevant bullet, do not replace.
- `/home/kim/Projects/SAO/WORKLOG.md` = reverse-chronological append-only log. Header format: `## YYYY-MM-DD — Kim + <model> — <title>`. Prepend new entries (newest at top) right after the header block.
- `stable-audio-3/docs/onnx-amd-inference.md` = the in-depth ONNX/AMD inference doc. Two major sections: `# SAME → ONNX` (autoencoder) and `# DiT → ONNX` (diffusion); control adapters subsection at end of DiT section.

**House style:** terse, fact-dense. No patronising filler. Bold the numbers and verdicts. Dates are `YYYY-MM-DD`. GPU-verified claims explicitly state "first measured session" or the verification date; unverified claims are explicitly marked.

**Why:** Cross-repo facts that matter across all three repos belong in MASTER.md §5 (the cross-project gotcha list). Per-repo deep docs stay in their `docs/` dirs. WORKLOG is the narrative; MASTER is the reference.

**How to apply:** When adding new measurements, insert additively (after the relevant paragraph), never overwrite. Flag any tool/script claimed to exist that cannot be found on disk with "not yet on disk as of YYYY-MM-DD".

**Note (2026-06-27):** `stable-audio-tools` docs were explicitly off-limits during this session (uncommitted WIP). Always check for this restriction before touching that repo.

**avp_sa3/ARCHITECTURE.md convention (2026-06-28):** This file is in the stable-audio-tools repo but covers all SA3 tooling including scripts in stable-audio-3/scripts/. When adding cross-repo pointers (e.g. eval servers), append a dated section `## [YYYY-MM-DD] ... — cross-repo note (stable-audio-3 agent)` rather than editing existing components sections inline. The file ends with a `## Run` block — append AFTER it.

**Gain gotcha (2026-06-28):** The MASTER.md §5 LatCH gain bullet now has an inline `UPDATE 2026-06-28` establishing operating gain ≈512 for energy heads. Do NOT reintroduce "48–96" or "128" as working ranges; those are superseded. When documenting any LatCH guidance parameter that references gain, always point to the ≈512 finding.

**Both CPU eval servers (latch_eval_server.py and control_eval_server.py) share make_text_cond.load_conditioner (device="cpu").** The HIP_VISIBLE_DEVICES="" crash pattern (flash_attn/aiter driver probe at import) is documented in MASTER.md §5 LatCH CPU eval bullet. Don't add it as a separate gotcha bullet — it's already there.
