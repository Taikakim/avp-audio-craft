---
name: doc-oversight
description: Use when reviewing THIS repo's own documentation for consistency, accuracy, and bloat — the recurring "does every doc still tell the truth, and does it read well" patrol. Covers root + docs/ prose, the agent-facing operating docs (CLAUDE.md / MASTER.md / ARCHITECTURE.md / skills), and where findings + edits land. NOT for recording NEW work (that's the docs-change-recorder agent); this VERIFIES what is already written and trims what has rotted.
---

# Documentation oversight (SAO consistency + quality patrol)

*Adapted 2026-08-04 from Kim's old spectral-forge CLAP doc-review routine, retargeted to this
repo's real shape + fleet conventions. Owner: THE-FINN (overseer / inconsistency patrol); any
instance may run it. This repo is a private research monorepo (`Taikakim/avp-audio-craft`), NOT a
shipped plugin — there is no `src/`, no `MANUAL.md`; adapt accordingly.*

## What this is / isn't
- **IS** — verify existing docs are still TRUE against the code + recent history, and read well
  (orient-first, non-redundant, non-stale). Fix clear factual rot; flag structure.
- **ISN'T** — writing NEW docs for work just done (use the `docs-change-recorder` agent). The
  truth-verification half overlaps the `docs-truth-auditor` agent — this routine **delegates the
  heavy sweep to it** rather than re-deriving, and adds the SAO-specific hotspots, the bloat +
  agent-doc audits, and the where-findings-go wiring the agent doesn't do.

## The three audits

### 1 — Consistency / truth audit
Scope: the 12 root `.md` + ~74 under `docs/` + `papers/knowledge.md`, checked against
`control/sa3_control/`, `eval/`, `lumi/`, `Misc/`, the vendored `stable-audio-tools/`, and
`git log --oneline -30`. **Delegate the sweep to the `docs-truth-auditor` agent, fanned out by
doc-group** (root-operating / docs-research / papers) so no one agent must hold all ~86 files.
SAO drift hotspots — where truth rots fastest, check these by hand even if the sweep is clean:
- **MASTER.md gotcha ledger** — the largest staleness sink (known chronic offender).
- **Path/host tables** — LUMI literal paths, drive labels, venv paths (things move; `latch.md`,
  `venvs.md`, `MASTER §5`, the lumi-ops skill).
- **Counts that drift** — model_index.md / the live board manifest vs claimed model counts;
  `papers/knowledge.md` row count; param / epoch / cfg counts in prose.
- **Feature-status flags** — "on/off", "disabled", "planned vs shipped" claims (e.g. a switch
  documented as on that the code defaults off, or a plan written as done).
- **Renamed / removed symbols** — module + function names referenced in prose vs the tree.

### 2 — Readability / bloat audit
Entry docs a fresh reader or new instance hits first — `README.md`, `FAQ.md`,
`KIM-RETURN-NOTES.md` — should orient before they drown. Flag: dense-too-early, duplicated
blocks, stale plans presented as current, unnecessarily technical intros. (No `MANUAL.md` in this
repo; the public "welcoming to non-professionals" surface is the website + blog — **W's domain,
out of scope here.** Do not edit generated/public output from this routine.)

### 3 — Agent-facing / operating-doc audit
`CLAUDE.md`, `MASTER.md`, `ARCHITECTURE.md`, `.claude/skills/*/SKILL.md`, `docs/superpowers/`.
Against Claude-Code best practice: focused on what an agent genuinely needs; free of redundancy,
stale plans, and over-documentation of things trivially derivable from the code; non-obvious
constraints surfaced sharply near the top. This is where SAO bloat concentrates (MASTER above
all) — be willing to **cut**, not just append.

## Fix vs flag — surgical only
- **FIX directly** — clear factual errors: wrong numbers, renamed/removed things, dead paths,
  stale feature flags, broken cross-refs.
- **FLAG, don't fix blind** — structure / tone / ordering: make a targeted edit only if confident;
  otherwise leave `<!-- TODO(doc-oversight YYYY-MM-DD): ... -->` with a clear why.
- **NEVER wholesale-rewrite.** Minimal diffs, matched to the surrounding voice.

## SAO guardrails (the spectral-forge routine had none of these)
- **Redaction posture.** Several of these docs are served publicly (redacted) by the website.
  An edit must never ADD newly-leaking specifics to any doc that is or may become public-facing:
  no corpus specifics / goa_archive / track-counts, no credentials, no infra addresses/ports, no
  multicast groups. Paths, drive labels, cluster names, code-names are NOT secret (Kim 2026-07-30)
  — polish only. Respect the content/generator split; never hand-edit generated output.
- **Filelock common files** before editing (`knowledge.md`, `models_index_overrides.json`,
  `paper_verdicts_data.json`, `open-threads.md`):
  `python3 Misc/filelock.py acquire <path> --handle <H> --timeout 30` … release after. The fleet
  edits these concurrently — an unlocked edit can clobber a live write.
- **Commit on Kim's word.** Do NOT auto-push to `main` (`main` is a periodic snapshot;
  `sa3-style-adapter` is the active dev branch). Staging + a review branch is fine; merging is Kim's.

## When done
- **Findings → the ledger.** Append a dated block to `docs/open-threads.md` (durable patrol record)
  — not just the chat. Cross-link the standing inconsistency backlog if relevant.
- **Edits → dev branch or a review surface.** Local/interactive run: stage on `sa3-style-adapter`
  (small) or isolate on `docs/review-YYYY-MM-DD` (big sweep). **Cloud-routine run: push to
  `claude/docs-review-YYYY-MM-DD`** — this fits the routine push-lock (routines may push only to
  `claude/*` branches by default; do NOT ask Kim to unlock unrestricted pushes just for this).
  Either way it's a review surface, never `main`. Commit message:
  `docs: weekly consistency and quality review (automated)`. Merging is Kim's call.
- **Output a brief summary** — what was FIXED, what was FLAGGED (with TODO locations), and the
  top 3–5 items worth Kim's attention. Do not merge/push without Kim's go.

## Cadence
Recurring (originally weekly). Natural triggers: after a big multi-doc work burst, before a
main-snapshot sync, or on Kim's word. THE-FINN owns the standing cadence as overseer.
