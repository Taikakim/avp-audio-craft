# Papers-site rebuild — design spec

*Kim request 2026-07-30: "the papers site could have a prettier landing page with clean headings
for the papers with a short one-liner, and a link to an individual page for each with our actual
results, any eval clips (we have everything locally at least)." Greenlit ("go ahead and push",
"both") 2026-07-30. Owner: WINTERMUTE (generator + deploy); THE-FINN (content).*

## Decisions (Kim, 2026-07-30)
- **Scope:** detail pages for the **~20 TESTED papers** only (nulled/partial/confirmed/convergence/
  declined). The 28 untested stay as one-liners on the landing (no detail page).
- **Clips:** build the per-page clip slot now, **curate incrementally** — populated where the
  paper→clip mapping is known, empty-but-ready elsewhere.
- **Theme:** match the **edg3 site** (masthead + edg3.css), consistent with dialogue/blog/profiles.

## Architecture
Extend the existing `Misc/build_paper_verdicts.py` + `Misc/paper_verdicts_data.json` (one generator,
one data file). Reuse `build_site` chrome (head/masthead/colophon) + the existing render-time
`scrub()`/leak-gate. No new subsystem.

## Data model (paper_verdicts_data.json entry — additive, all new fields optional)
Existing: `title, id, link, claim, explanation, verdict, caveats, cited_not_fetched`.
Added (F authors, joined to knowledge.md by arxiv id; DC-SAE by slug `icml26w-dcsae`):
- `one_liner` (str) — crisp landing take (ALL papers). Falls back to first sentence of `verdict`.
- `enrich` (str, HTML-ok) — "what remains ours / how it ports or contradicts our work" (TESTED only).
  Renders as its own detail section titled **"In the landscape"**.
- `slug` (str) — detail-page filename. Falls back to `id` (DC-SAE uses its slug).
- `clips` (list of `{file, label, caption?}`) — staged eval clips; **absent/empty for most**,
  curated in over time. Files staged under `evals/paper_verdicts/clips/`.

## Pages (both edg3-themed, masthead nav, redacted via scrub()+gate)
**Landing** — `evals/paper_verdicts.html` (same URL; nav "papers" already points here):
- Intro blurb (existing "how", reworded for the new structure).
- Verdict-category sections (confirmed / partial / nulled / convergence / declined): each TESTED
  paper as a card — verdict badge + title + `one_liner` + **→ results** link (to its detail page) +
  arXiv link.
- **Untested shelf** (28): compact one-line list — title + `one_liner` + arXiv link, NO detail link.

**Detail** — `evals/paper_verdicts/<slug>.html`, one per tested paper:
- Header: verdict badge + title + arXiv id link.
- `one_liner` (lead).
- **The claim** — the paper's `claim`.
- **What we found** — our `explanation` (result narrative).
- **Verdict** — `verdict` (+ `caveats` if present).
- **In the landscape** — `enrich` (F's port/what-remains-ours analysis), when present.
- **Eval clips** — same-playhead player over `clips`; if none mapped, a "clips being curated"
  placeholder. Papers that are analysis-only (no audio — TADA/SAME/optimizer-drift/etc., see the
  candidate map) simply carry no clip slot.
- Back-link to the landing.

## Clips
Same-playhead m4a player pattern (reuse the eval-board approach). Candidate paper→clip mapping
drafted (scratchpad `paper_clip_candidate_map.md`): ~10 generation/control papers have audio
(FusionCC→onset_eval, LatCH family→latch_sweep/latch_sa3_matrix/chroma_steer, longform
SaFa/InfiniteAudio/a2a/LoL→longform renders, Cautious-WD→matrix fusion-vs-adamw); the other ~half
are analysis/metrics (no clips). Clips staged + `clips` field curated incrementally.

## Redaction
Every rendered page (landing + all detail) passes through the generator's `scrub()` + refuse-on-
residual `_LEAK_GATE` (paths/drives/ckpt-filenames/corpus scale). Science stays; plumbing does not.

## Rollout
1. Landing redesign (edg3-themed, cards + untested shelf).
2. Detail-page generator (per tested paper) + the "In the landscape" enrich section.
3. Clip player + staging convention; wire the clips we can map now, slot-ready for the rest.
4. Deploy (landing + detail dir) leak-scan-gated; verify live; F content-check + re-verify.

## Acceptance
- Landing at `evals/paper_verdicts.html`, edg3-themed, "papers" nav highlighted; tested cards link
  to detail pages; untested shelf one-liners present; HTTP 200, leak-clean.
- Each tested paper has `evals/paper_verdicts/<slug>.html` with claim/found/verdict/enrich + clip
  slot; back-link works; leak-clean.
- `one_liner`/`enrich`/`clips` render when present, graceful fallback when absent (partial content ships fine).
