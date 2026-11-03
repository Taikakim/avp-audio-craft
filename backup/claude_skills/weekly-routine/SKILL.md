---
name: weekly-routine
description: Use when a fleet week has closed (or several closed unnoticed) and the recurring documentation cadence needs running — a repo ahead/behind sync sweep, the dialogue-chronicle synopsis, the public blog week-in-review, a KIM-TASKLIST.md staleness patrol, and an EXPERIMENTS.md sanity pass. Also use when Kim asks to "compile the weeklies" or similar. Owner: THE-FINN; any instance may run it.
---

# Weekly routine (SAO documentation cadence)

*Written 2026-08-28/09-01 (THE-FINN, Kim direct) after a token-budget gap let this lapse for
several weeks unnoticed — both the internal chronicle and the public blog had fallen behind, and
KIM-TASKLIST.md had ~15 stale entries dating back three weeks. The point of this skill is that
lapse not repeating silently.*

## When to run this
- At the start of a session when `date` shows the ISO week has rolled over since the last run
  (cheap check: is there a `dialogue/AGENT_DIALOGUE-YYYY-Www.synopsis.md` for every archived
  `dialogue/AGENT_DIALOGUE-YYYY-Www.md` except the current live week? A gap means one or more
  weeks were missed).
- Whenever Kim asks to "compile weeklies", "check tasklists", "write a blog post", or similar.
- Not necessarily every single week if genuinely nothing happened — but check even a quiet week,
  because "nothing happened" is itself worth one honest line (see the 2026-08-28 blog post for
  what that looks like: don't skip the post, write the quiet week plainly).

## 0 — Repo sync sweep (ahead/behind + dirty, run first)
*Also run `Misc/backup_outside_repo.sh` and commit `backup/`: memory files, `~/bin`, skills and the page builders live outside every repo (Kim 2026-11-03: anything we don't want to lose in a hardware failure gets tracked). Refresh `Mantu/backups/clip_metrics_<date>.db` with `sqlite3 eval/clip_metrics.db ".backup ..."`; it is too large and binary for git.*
*Added 2026-09-22 (WINTERMUTE, after SAO sat `[ahead 39, behind 6]` — unpushed fleet work back to
Sept 11 plus a diverged origin — for nine days before anyone noticed, found only because THE-FINN
happened to try a push. Cheap, so it goes first, before the four doc pieces below.*

```bash
cd /home/kim && for r in Projects/SAO Projects/SAO/stable-audio-3 \
    Projects/SAO/stable-audio-tools Projects/mir Projects/fusion-optimiser; do
  printf '%-34s %-34s tracked-dirty=%s\n' "$r" \
    "$(git -C $r status -sb | head -1 | sed 's/^## //')" \
    "$(git -C $r status --porcelain | grep -c '^ M\|^M')"
done
```

Repos are by **absolute path**, not a walk from SAO's tree — `fusion-optimiser` and `mir` are
siblings of SAO, not nested in it, and a sweep that only walks SAO's tree silently misses both.

Two things this one-liner deliberately gets right, learned the hard way:
- **Tracked-modified is counted separately from untracked.** A raw porcelain line-count cries wolf
  every week over render dirs, editor `~` backups, and other debris nobody intends to commit
  (stable-audio-3 had 45 "dirty" files that were 7 real edits and 38 junk). Untracked piles are a
  `doc-oversight`/patrol-adjacent finding, not a sync-sweep alarm.
- Also flag a branch **ahead with no remote counterpart at all** — the failure mode that bites
  hardest, because there's nothing to read as "behind", so nothing looks wrong from `ahead/behind`
  alone.

**On what you find:** ahead-and-clean is safe to push after the normal `docs/GIT-PROTOCOL.md`
fast-forward check. Ahead-and-dirty is NOT something to commit blind — if the dirty files look
mid-flight (recent mtimes, an operator-layer training launch in progress per RUNBOOK §8), ask on
the fleet channel who holds it rather than guessing an author. A diverged-with-real-work origin
(not just your own stale view of it) gets reported, not force-pushed past.

### 1 — Dialogue-chronicle synopsis (internal, technical, THE-FINN's established lane)
For each archived week missing one: read `dialogue/AGENT_DIALOGUE-YYYY-Www.md` in full (it can be
large — **fork this**, don't load a multi-hundred-KB archive into your own context) and write
`dialogue/AGENT_DIALOGUE-YYYY-Www.synopsis.md` in the exact format of the existing series (title +
tagline with entry count and theme, one narrative paragraph, a "## Headlines" bullet list — read
2-3 recent synopses for exact voice before writing). Internal jargon and names are fine here.
**Accuracy discipline**: every number/date/claim must trace to something actually in the source;
past drafts have needed correction after rounding or half-remembering a figure. Verify, don't
extrapolate.

### 2 — Public blog week-in-review (`blog/YYYY-MM-DD-week-in-review-DRAFT.md`)
**Before drafting, ask W (or whoever owns the mirror pipeline) what's actually LIVE on the
server right now** — local files can be stale relative to the published site or vice versa, and
duplicating or overwriting published work is exactly the kind of "derivative doesn't know its
source changed" trap this fleet keeps re-hitting. Read the most recent existing draft for voice
(narrative, first-person-plural, accessible to an outsider, "The One With…"-style title, a
standing header HTML comment naming author/reviewer/publisher). **Redact hard**: no checkpoint
names, paths, corpus names, artist/track names, internal ids, job numbers. If multiple weeks
passed quietly, ONE honest combined post beats several thin ones — say so in the header comment
and in the post's own closing, plainly, the way an honest team would.
**Read `MASTER.md` §4's ATTRIBUTION CONVENTION before writing** — it may have changed since you
last checked (it did once, uncommitted, and almost went unnoticed). When unsure whether something
should name Kim directly, don't — the impersonal form costs nothing.
This is a DRAFT for Kim's own review/edit, not something to publish unilaterally — show it to him
before handing it to whoever publishes.

### 3 — KIM-TASKLIST.md staleness patrol
The file's own preamble says THE-FINN patrols it; that's canon, not a suggestion. **Fork this too**
if the "Decisions waiting on Kim" section is long — it needs real verification (git log, cross-
checking EXPERIMENTS.md's GATED/DONE markers, grepping recent dialogue archives for whether a
later message already resolved something an old entry left open), not a skim-and-guess pass.
For each entry, sort into: **stale/moot** (verified — a decision already answered by later events,
a job superseded, a merge that happened, a snapshot from a closed allocation), **still live** (a
real open decision, confirmed still GATED/unresolved), or **ambiguous** (you genuinely can't tell —
flag it for Kim or the fleet to answer, do NOT silently guess and prune; a stale tasklist is worse
than none, but a wrongly-pruned live decision is worse than a stale one). Acquire the filelock
(`python3 Misc/filelock.py acquire --handle <you> KIM-TASKLIST.md`) before editing. Move resolved
items to "Recently done" with a one-line dated summary rather than just deleting them outright —
the record has value.

### 4 — EXPERIMENTS.md sanity pass
Lighter touch than the tasklist patrol (EXPERIMENTS.md tends to get kept current by whoever's
actively running experiments, since it's their own working doc). Skim for: entries still marked
RUNNING/QUEUED that reference a since-closed compute allocation (should probably read PLANNED or
note what's needed for the next allocation instead), GATED items where the gate might have
resolved elsewhere, and the standing "owner of the file's shape" duty (consistent status-tag
vocabulary, no internal contradictions between adjacent entries — the kind of thing caught before
by grepping for an earlier claim rather than trusting memory).

## What this ISN'T
Not a truth/consistency audit of the docs' prose itself — that's `doc-oversight`, a separate,
narrower skill. This is the cadence of producing the recurring artifacts (chronicle, blog,
tasklist, experiments), not verifying every existing doc still reads well. Run both if a session
has room for it; they don't overlap much.

## Reporting back
Post a short summary to the fleet channel when done (per the standing "post a summary of every
landed finding/milestone to chat" rule) and give Kim a consolidated status: what got written, what
got cleaned up, and — critically — anything flagged ambiguous that needs his or the fleet's actual
input rather than a guess.
