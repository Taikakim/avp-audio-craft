---
name: sao-orientation-2026-07
description: "THE-FINN's 2026-07-03 orientation audit — confirmed doc/repo inconsistencies, unverified queue, project map digest"
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
---

Fan-out audit 2026-07-03 (9 readers + adversarial verify; full JSON in session scratchpad,
run wf_ebe82849-94d). **24 CONFIRMED findings**; verify layer for book-2/worklog/tooling
was limit-clipped → those stay UNVERIFIED until re-checked (after 16:00 credits reset).
The `docs` reader returned degenerate output — SAO/docs layer still unmapped.

**Why:** this ledger is my working queue as overseer; items get struck as the fleet fixes them.
**How to apply:** before flagging anything on the wire, check it's still open here; strike fixed rows.

## CONFIRMED — MASTER.md staleness (needs filelock + a pen)
1. §4 still says repos are PUBLIC + "PRs can't be disabled" — Kim reversed 2026-07-02 18:18, the 4 work repos are PRIVATE. (MASTER.md:136-147)
2. §4 profiles paragraph describes the superseded hand-HTML + scp flow; ratified flow is `profiles/<slug>.{profile,journal}.md` → `Misc/build_site.py` → `site/profiles/`. (MASTER.md:148-153)
3. §4 taken-handles list = "taken: FLATLINE" only; stale re CONTINUITY rename + WINTERMUTE/GHOST-NOTE/THE-FINN. (MASTER.md:118)

## CONFIRMED — process/repo hygiene
4. WORKLOG's "DO NOT COMMIT without Kim" coordination note (lines ~925-939) now stale — everything listed was committed+pushed; needs a closure line or a new instance treats the tree as sacred.
5. Spec `docs/superpowers/specs/2026-07-03-composed-control-latch-sweep.md` untracked while its implementation is pushed at HEAD 7b3f1cc (commit message references the spec).
6. Fork CLAUDE.md banner edits uncommitted + ownerless: SAT +5 lines, SA3 +10 lines (secrets banner / journal habit) — in nobody's claimed-files list.
7. `site/dialogue.html` tracked + perpetually dirty (colorizer regenerates); W's gitignore suggestion never actioned.

## CONFIRMED — public-surface (redaction rule violations)
**Rule REFINED by Kim 2026-07-03 23:34** (relayed by W, C holds the MASTER §4 pen):
config settings/hyperparameters/metrics ARE shareable ("that's how the light gets
out" — open science); only PLUMBING/SECRETS stay off — checkpoint filenames,
absolute paths, infra addresses, credentials. Re-score items below against the
NEW rule, not the old blanket "no exact configs" one.
8. The public dialogue mirror carries checkpoint filenames, a wandb run id, and an absolute /home path — still violations under the refined rule (filenames/paths/infra unchanged as banned); colorizer only scrubs infra addresses. (Also: my own intro named my absolute home dir — watch that.)
9. ~~Config-bearing eval dir names publicly served via dir listing~~ **MOOT — Kim explicitly approved config-bearing names/labels (lr2e5, 1e-4, +50% LR etc. STAY, no scrub).** G's afternoon friendly-label pass predates this ruling; not a bug to fix, a policy that moved out from under it.
10. SPEC-agent-profiles-journals.md self-contradicts: §4 retires Taikakim blob links; §2/§3 template/§5 skeleton/§7 step 4 still instruct emitting them. §2 file-location table also points at superseded profile HTML paths.
11. site/index.html "record" table timestamps stale; masthead says "Three constructs" — I'm the fourth.
12. GHOST-NOTE's journal missing its own 07-03 work (posters, site sweep) that SPEC §4 cites as reference implementation.

## CONFIRMED — my domain (/home/kim/.claude)
13. Both agent defs (docs-change-recorder, docs-truth-auditor, 2026-06-19) predate the protocol era: no filelock, no public-mirror posture; recorder's memory encodes obsolete "Kim + <model>" WORKLOG header rule. Update before next use.
14. ~~jobs/b1ee18e7~~ **RESOLVED-WITH-VERDICT 2026-07-03 (F+W+Kim):** job marked done; PR #1 was already MERGED (my digest wrongly said "open" — stale job state; corrected on record). **Kim decided (23:34): guidance-path gain knob = ‖dt·v‖ (one model-update unit), ‖z0‖ = secondary readout** — implement when LatCH/TFG work resumes; NOT the adapter FiLM gain (~6, separate mechanism). Rainy-day: 2.58M-line tokenizer.json committed on fork/main (filter-repo candidate).
15. ~~daemon/roster.json orphaned~~ retired to roster.json.stale-2026-07-03. docs-truth-auditor never ran (empty memory).

## CONFIRMED — book/docs numerics (low)
16. SA3 `docs/guides/model-overview.md:41` is WRONG on latent rate (implies 21.6 Hz); the book's 10.75 Hz is right (matches MASTER T=4096/380 s). Fix the model doc, not the book.
17. Book README word count ~44k counts non-book files; actual chapters = 35,652.
18. Ch5 "certain layers" vs Ch8 "every layer" cross-attn wording (code: per-layer gated, default all).

## UNVERIFIED QUEUE (limit-clipped; re-verify before flagging)
- flash-attn doc §7 may still say MAX_JOBS=6 (2026-06-29 WORKLOG says -j4 or OOM).
- Reverse-stale: WORKLOG TODO "latch_sweep.html still says architecture-limited" — page may already be fixed.
- SAO/riffer-evals possibly a stale clone of ~/riffer-evals (missing last ~5 commits).
- `stable-audio-tools/avp_sa3/` stale pre-move duplicate of SAO/control/, diverged; eval-server + eval_dora_cpu.py duplicates diverged between stable-audio-3/scripts/ and SAO/{onnx,eval}/; restructure "phase 4" (git rm old copies) unexecuted.
- MASTER §4 possibly misattributes genre_eval.py to mir (may live in SAO/control/sa3_control/); "train_latch.py has --ema" true only of the onnx/latch copy; riffer-evals generators mostly moved ~/ → Misc/.
- WORKLOG ordering broken: 07-02/03 entries sit BELOW the "(earlier)" archival marker despite newest-first convention; one ~06-20 entry lost its header.
- Stale path in WORKLOG: real-music corpus moved to Lehto (aavepyora_flac dir).
- docs/todos.md lists CK flash-attn validation as open though validated twice.
- checkpoint-stats/README stale (tool path, missing 07-02 trajectory sets, superseded hypothesis wording).

## Standing project map (digest)
Campaign arc: foundations (SAME semantic latent discovery, latents_sa3, 19 LatCH heads) →
gain discovery (48-96 → superseded by ≈512 for energy heads) → longform/separation/latent-explorer →
riffer→attribute-branch pivot → reward studies + control taxonomy → ONNX/AMD CPU eval servers →
EMA reverses "architecture-limited" (damping-limited; EMA+grad-accum+early-stop = default recipe) →
FusionOpt/FusionCC + meter-in-gradient scope condition (2 wins + clean genre negative) →
novelty verdict: claims 1/2/5 novel-unpublished, ControlNet++ prior art for the mechanism (see SAO/papers/knowledge.md).
Open engineering threads live in WORKLOG + [[onboarding-new-instance]]; book map: 16 chapters,
"where can control be injected", claims labeled known/speculative/frontier; CONTROL_METHODS_SOURCEBOOK
= adversarially-verified June-2026 lit companion, 12-method shortlist, LatCH-B declared novel.
