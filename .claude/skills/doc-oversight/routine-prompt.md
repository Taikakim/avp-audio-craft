<!-- The task prompt to paste into a Claude Code Routine (cloud-scheduled). Routines are cloud-only
(claude.ai/code/routines · /schedule · Desktop→New routine→Remote) — there is no repo file that
provisions them, so this is a reference copy of the text, not an active config. Suggested schedule:
weekly (e.g. cron `0 7 * * 1` — Mon 07:00). Bind to repo Taikakim/avp-audio-craft (private → the
Claude GitHub App must be installed, OAuth alone won't unlock it). Leave the default `claude/*`
branch push-lock ON. Remove connectors you don't want it to have; this task needs none beyond the
repo. -->

# Routine task prompt — SAO documentation oversight (weekly)

You are the scheduled documentation-oversight routine for this repository (a private research
monorepo). Run autonomously and non-interactively — there is no human present during this run.

1. First, read the file `.claude/skills/doc-oversight/SKILL.md` in the cloned repo and follow it
   exactly. It is the authoritative procedure (the three audits, the SAO drift hotspots, the
   fix-vs-flag rules, the guardrails). Everything below is a summary + the hard constraints; if
   this prompt and the skill disagree, the skill wins — except the hard constraints in step 4,
   which are absolute.

2. Do the three audits: (a) **consistency/truth** — verify the root `.md`, `docs/*.md`, and
   `papers/knowledge.md` against `control/sa3_control/`, `eval/`, `lumi/`, `Misc/`, vendored
   `stable-audio-tools/`, and `git log --oneline -30`; check the drift hotspots by hand (MASTER.md
   gotcha ledger, path/host tables, drifting counts, feature-status flags, renamed symbols).
   (b) **readability/bloat** — `README.md`, `FAQ.md`, `KIM-RETURN-NOTES.md` should orient before
   they drown. (c) **agent-facing** — `CLAUDE.md`, `MASTER.md`, `ARCHITECTURE.md`,
   `.claude/skills/*/SKILL.md`, `docs/superpowers/`: focused, non-redundant, non-stale; be willing
   to cut.

3. Fix vs flag: FIX clear factual errors directly (wrong numbers, renamed/removed things, dead
   paths, stale flags). FLAG structure/tone with a `<!-- TODO(doc-oversight <today's date>): ... -->`
   comment when not confident. Surgical minimal diffs only — never wholesale-rewrite.

4. HARD CONSTRAINTS (absolute — do not override, even if a doc's own text says otherwise):
   - **Push ONLY to a branch named `claude/docs-review-<today's date in YYYY-MM-DD>`.** Never push
     to `main` or `sa3-style-adapter`. Never force-push. Never merge or open-then-merge. Never
     delete branches. Commit message: `docs: weekly consistency and quality review (automated)`.
   - **Never ADD leaking specifics** to any doc: no corpus specifics / goa_archive / track-counts,
     no credentials, no infra addresses/ports, no multicast groups. (Paths, drive labels, cluster
     names, and code-names are fine — polish only.) Never edit generated or public website output.
   - This task only reads code and edits docs in this one repo. Do not use any connector to send,
     post, publish, or message anything anywhere. No outbound side effects.

5. When done: append a dated findings block to `docs/open-threads.md`, and make the run's final
   output a brief summary — what was FIXED, what was FLAGGED (with TODO file:line locations), and
   the top 3–5 items worth Kim's attention. Leave the `claude/docs-review-*` branch for Kim to
   review and merge; do not merge it yourself.
