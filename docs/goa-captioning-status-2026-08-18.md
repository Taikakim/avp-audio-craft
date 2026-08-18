# goa big-set captioning — consolidated status (2026-08-18)

*Written by THE-FINN at Kim's request ("the whole captioning debacle got a bit too
sprawling, the team should agree on where we are") — synthesized from AGENT_DIALOGUE.md
(G/W/C, 2026-08-17 20:11 → 2026-08-18 09:47), WORKLOG.md, and direct verification (git log,
file inspection). **Posted to the team for confirmation/correction, not declared final
unilaterally.** Feeds W's canonical metadata-spec (see bottom).*

## Verdict, one paragraph

Three independent, real bugs hit the goa big-set caption pipeline over 2026-08-17/18, found
by three different people using three different methods, converging on one architectural
gap: **the goa corpus was captioned genre-blind.** Effnet genre features were correctly
extracted back on 2026-08-01/02 (the canonical MIR path — see Kim's question, answered
below) but never reached the Music Flamingo captioning step. All affected LUMI jobs are
killed; a hinted re-caption is running now (~24h); nothing currently queued is training on
the bad text. Two audit tools now exist, cover different failure modes, and should both be
run — that's the operational takeaway most likely to recur.

## Timeline

| When | What | Who |
|---|---|---|
| 2026-08-01/02 | goa_archive MIR feature pass completes (23,231 tracks) via mir's canonical `goa_archive_mir.py`/effnet classifier suite. `goa_archive_stats_export.py` sanity-checks it: 60% Goa Trance genre — **correct, and verified correct at the time.** | G |
| 2026-08-04 | goa big-set Music Flamingo + Granite captions built (23,231/23,231, hash-join verified). `fullft_bigset` campaign launches on this caption set. **The Aug-1/2 effnet genre signal is never consulted at this step.** | (historical) |
| 2026-08-17 ~01:41 | `goa_granite_task.py::read_mf()` bug found: Granite was revising the file PATH, not the nested MF caption text — affected all 23,232 tracks, produced plausible-but-hallucinated template text. Fixed `63546e6`. | G |
| 2026-08-17 | Granite v5 re-run (job 21255037), 23,232/23,232 content-verified. | G |
| 2026-08-17 ~20:44 | **C's grounding audit on the then-LIVE (still Aug-4) sidecar: 1.24× — NOT GROUNDED, indistinguishable from chance.** Run at Kim's explicit ask ("check the big goa set granite reviews for similarity randomly sampling, to make sure Granite got the correct input") — this is the measurement-side confirmation of G's read_mf finding, arrived at independently, neither knowing the other's route. | C |
| 2026-08-18 ~01:01 | Sidecar REBUILT from v5 Granite (the stale-derivative step — the first audit above had re-measured Aug-4 content while v5 sat unused). | C |
| 2026-08-18 ~01:04 | Re-audit on the rebuilt sidecar: **19.24× GROUNDED**, beating suomisoundi's 16.17× — genuinely fixed on grounding, i.e. tags now reflect their own track's MF prose. | C |
| 2026-08-18 ~01:31 | W's genre-content scan (independent method, first-200-chars of T3) finds the real problem: goa T3 says goa/psy in only **1.2%** of tracks (58% techno, 46% industrial/hard) — and it's live on two running jobs. | W |
| 2026-08-18 ~01:56 | C confirms: cause is `genre_hint` defaulting to empty in `goa_caption_task.py` (mechanism exists — `--genre-hint`/`GENRE_HINT_FILE` — never populated for goa). Suomisoundi, same script, had a real hint → 97.4% correct. **Kim kills the affected runs directly.** Hinted re-caption launched, job 21335408, writing to a NEW dir (`goa_archive_captions_hinted`) so the unhinted set is preserved as a control. | C, Kim |
| 2026-08-18 ~02:20 | Kim pushes both rebuilt sidecars (suomisoundi, goa) to LUMI scratch. | Kim |
| 2026-08-18 ~02:55 | **C** commits `9e4a78f`: cross-references W's and C's audit tools in ARCHITECTURE.md §C after noticing both were built the same night with near-identical names (`caption_sidecar_audit.py` vs `audit_caption_sidecar.py`). *(Corrected 2026-08-18 — an earlier draft of this doc attributed this to Kim, reading the git author field, which is misleading here: every agent commit in this repo is authored "Kim" (his git user.name) — it is not evidence of who did the work. See docs/lessons-learned.md § Process/coordination.)* |
| 2026-08-18 09:46–09:47 | G reports sidecars as local-only/not-yet-pushed (stale info — see below); C corrects with md5 verification (Kim HAD pushed, ~02:20) and re-states the genre-hint root cause for the record, since G's "verified correct" claim was about tier *consistency*, not genre *correctness*. | G, C |

## Root causes (three, not one — don't conflate them)

1. **Granite revision fed the wrong input** (`read_mf()` reading a path, not caption text) — fixed `63546e6`, re-run as v5, **grounding-verified** (19.24×).
2. **Music Flamingo captioned goa with no genre hint** — the `--genre-hint`/`GENRE_HINT_FILE` mechanism exists, was used correctly for suomisoundi, and defaulted to empty for goa. This is the one that matters most: ~99% of T3 (raw MF prose) captions do not mention the corpus genre at all. That is not the same as "99% mislabeled" — the archive genuinely contains non-goa material, and the hinted re-caption correctly lands at 89.1%, not 100%. Granite (T2) *faithfully inherits* T3's error since it revises rather than re-derives. **Fix in flight**, job 21335408, ~24h.
3. **A stale-derivative trap, twice** — the caption *sidecar* (the actual training input) doesn't auto-rebuild when its source captions change, so a fix to (1) or (2) does nothing until the sidecar is explicitly rebuilt. Bit G/C's own audit once already (stale Aug-4 sidecar read as if the fix had failed) and is architecturally why "captions look fixed" and "sidecar is fixed" are different claims. `build_goa_archive_sidecar.py` now prints each input tier's newest mtime as a partial mitigation.

## Kim's question: why wasn't Effnet genre collected for the big set / why wasn't he told it was missing

**It was collected — your mental model was right, this isn't a collection gap.** Effnet
`genre400`/`moodtheme` (mir's canonical Essentia classifier suite, the same one behind
`classify_new_corpus.py`/`build_feature_table.py`) ran as part of the Aug-1 MIR pass and
was explicitly sanity-checked on 2026-08-02 (`goa_archive_stats_export.py`, correctly
reading 60% Goa Trance). It sits in `goa_archive_features/npz/<key>.npz` as
`effnet_genre400_ts`/`effnet_moodtheme_ts`, and it is what `build_goa_archive_sidecar.py`
reads to build the T1 tier — measured last night at **70.4% goa/psy, the most
genre-correct tier we have.**

What actually happened: **the already-correct effnet signal was never wired into the
Music Flamingo captioning step.** `goa_caption_task.py`'s genre-hint mechanism only
accepts one manually-supplied global string per corpus run — it has no code path that
reads per-track effnet output at all, and separately, nobody supplied even a global hint
string when the goa run was launched. So this is two gaps stacked: (a) a richer,
already-available per-track signal was never plumbed in, and (b) the manual fallback
(a single string) was also skipped.

**Why nobody flagged it as missing sooner:** it wasn't missing, so nobody had a "missing
data" alarm to trip. What was missing was a *cross-check* — nobody compared MF's captioned
genre against the already-computed, already-verified effnet genre distribution from two
days earlier, until W's scan on 2026-08-17. The Aug-2 stats pass verified the **features**;
nothing verified the **captions against the features** until two weeks later, after
`fullft_bigset` had already launched against the bad text. That's the real process gap —
not "we forgot to extract a feature," but "we validated the input and never re-validated
the thing built on top of it before spending GPU-hours on it." This is the same shape as
root cause 3 above (derivative doesn't know source changed), one level up the stack.

## Where we are right now (2026-08-18, post 09:47 correction)

- **suomisoundi** — clean throughout (97.4% genre-correct T3), sidecar pushed to LUMI
  (`/scratch/project_465003186/suomisoundi_latents/`), W's 4 arms unaffected, no action needed.
- **goa big-set** — currently-live sidecar on LUMI (`/scratch/project_465003186/latents_goa_bigset/`,
  md5-confirmed post-Granite-v5-fix) is **grounding-fixed but genre-WRONG** — do not train
  against it. `fullft_bigset`, `subloss_goa_k20_fullft`, `fullft_mem_probe` and the
  `efp_*`/`subspace_loss_*`/`x0equiv_*` families (default `0.6,0.3,0.1` against
  `goa_longform`) all carry this confound in any checkpoint trained before today; their
  checkpoints aren't worthless but any prompt-following/genre conclusion drawn from them
  needs this caveat attached.
- **Re-caption in flight** — job 21335408, hinted MF, ~24h (finishes ~02:00 tonight), then
  Granite re-revision, sidecar rebuild, audit (both tools), re-key, then the arms.
- **Tooling now in place:** two complementary auditors, cross-referenced in ARCHITECTURE.md
  §C so neither gets rediscovered blind — `caption_sidecar_audit.py` (W: is a tier
  *informative and consistent*) and `audit_caption_sidecar.py` (C: is a tier *grounded and
  correct*, now including a genre-content scan). **Run both, they check different things.**
  `build_goa_archive_sidecar.py` now takes `--captions-dir`/`--features-dir` explicitly,
  FATALs on a missing dir instead of writing empty, and prints input-tier mtimes.
- **RESOLVED, ~10:19: the wall-clock crisis dissolved by WIDENING, not skipping stages.**
  C's own first read of `lumi-allocations` also missed a number — he read GPU-hours (2037
  remaining) and separately the "4 days of compute left" prose, and planned around hours,
  which is what produced the skip-Granite recommendation below (superseded, kept struck
  through for the record). Kim's correction: ~500-600 GPU-hours/day are actually available
  and one 8-GCD node only spends 192 — the fleet was underspending by ~3×. Fix was to
  SPREAD the independent per-track work across many short jobs instead of one long serial
  one (16 nodes for MF re-caption, 16 for Granite, running concurrently rather than
  sequentially) — same total GCD-hours billed, ~17h serial → ~1h wide. **Granite is NOT
  being skipped**; re-verified on real audio this time (per-track BPMs precise to 2dp,
  varying, e.g. "late-90s goa trance, psytrance, hypnotic, driving, 136.36 bpm" — not the
  pre-fix "140 bpm on nearly every track" template). On current rates the full chain
  (caption → Granite → sidecar rebuild → audit both tools → re-key → launch the 3 arms)
  finishes **today**, not the 19th/20th. The operational lesson (many-small-jobs +
  pre-sharding + resumable-stage overlap) is committed directly to
  `.claude/skills/lumi-ops/SKILL.md` (`2c6950f`, C) — not duplicated here.
  ~~Skip-Granite recommendation, superseded~~: <s>train on T1+hinted-T3 only, skip Granite
  to save 12-24h wall clock.</s>

## Routing — Kim's ask

Kim wants **W to review this whole episode and write one spec everyone follows every time
we create metadata for a training set** — not another one-off fix. This doc is the input
to that; W, treat the timeline/root-causes above as a starting draft, correct anything I
got wrong, and the spec is yours to own. Suggested scope, not prescribing the content:
what gets extracted (and via which canonical tool — mir's, not a reimplementation), what
gets cross-checked against what before a captioning run launches, what the sidecar-rebuild
contract is, and where the "did we actually verify the OUTPUT, not just the input" step
lives so this doesn't recur a third time in a different corpus.
