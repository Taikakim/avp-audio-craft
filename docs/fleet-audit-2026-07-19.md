# Fleet Audit — What Did We Drop (2026-07-12 → 2026-07-19)

Run by GHOST-NOTE (F+W unreachable when Kim asked). Method: 6-source parallel sweep
(dialogue, DMs, journals+todos pool, WORKLOG, experiment manifests, git/code) →
merge/dedupe → adversarial re-verification of every candidate against ALL sources →
synthesis. The workflow's verify+synthesize stage hit a session-limit wall partway
through a retry pass; the 5 items marked **[manual-verify]** below were confirmed by
me directly (grep/read against live sources) rather than by an independent sub-agent,
everything else got the full adversarial pass. Two round-1 candidates that a later
sweep also surfaced turned out to be **already resolved** on inspection (noted at the
end, for the record — not included in the open list).

**22 confirmed still-open items.** By owner: CONTINUITY 8 (1 high), WINTERMUTE 8,
THE-FINN 3, Kim 1, unowned 2.

---

## CONTINUITY

**🔴 HIGH — Stereo mid/side-loss sweep (w0.1/w0.3) never produced a checkpoint; driver masks the failure as success.**
Both non-baseline arms OOM'd on launch (2026-07-17 and again 2026-07-18); `stereo_sweep_driver.log` reports `DONE rc=0` both times despite `HIP out of memory` in the same-timestamped logs. `stereo_loss.py` itself is still untracked (not in `git log --all`). Already DM'd to CONTINUITY directly (2026-07-19) since it's live-infra and time-sensitive.
→ Fix the rc-masking bug, re-run at a safe batch size, commit the code.

**🟡 `train_lora.py` + core SA3 training files still uncommitted despite Kim's 07-17 commit-call.** WINTERMUTE assigned CONTINUITY `train_lora.py`, `transformer.py`, `longform.py`, `lora/model.py`, `lumi/*` for commit; live `git status` in stable-audio-3 still shows all modified/untracked as of today, and LUMI campaigns already run off this exact code — a real divergence risk.
→ Commit now or state explicitly why it's held.

**🟡 GHOST-NOTE's verbatim-quote question for the E_fusion_v2/A_cc_v2 `kim_feedback` backfill never answered (2026-07-12).** Both sidecars still show `kim_feedback: null`.
→ Reply, or better: get Kim's actual A/B verdict on the now-metric-confirmed-accurate audio and record it verbatim.

**🟡 Arms I/J/K (BoRA + per-alias adapter previews) queued once (07-09), never run or explicitly retired.** No later mention anywhere.
→ One WORKLOG/todos.md line retiring them (circumstantial evidence they were superseded by the LUMI full-finetune pivot) so nobody re-queues them.

**🟡 [manual-verify] `onset_FUSION_lr2e5_40epoch` never cross-examined against the 07-07 "ear-approved" favorite.** THE-FINN's own gap-audit doc (`docs/paper-gap-audit-2026-07-18.md` context, referenced 2026-07-19) names this explicitly as gap #2 of the onset-density contest — Kim's ear picked `onset_Fusion_lr1e-4_randomcrop` on 07-07, but this checkpoint has its own separate "the favourite, by ear" claim in its own run_meta that nobody has reconciled.
→ W's control-authority re-scan (already proposed) is the natural way to close this in the same pass as the FusionCC question.

**🟡 [manual-verify] Residual-preservation Gate A / Gate B queued today (2026-07-19), not yet run.** CONTINUITY's own journal: "DON'T train it yet — two cheap gates first: Gate A (CPU/free, corpus-PSD-shaped noise injection), Gate B (tiny 24-seed fan)." Fresh, not stale, but worth tracking so it doesn't quietly age the way the BoRA arms did.
→ No urgency, just don't let it fall off silently.

**🟢 GHOST-NOTE's width-T-sweep dedup question never confirmed (07-17).** Resolved by my own re-check just now: it's genuinely a *different* experiment from CONTINUITY's stereo loss-weight sweep (T-vs-width at fixed loss-weight, vs loss-weight at fixed T=512) — so it's still un-run, not a duplicate.
→ Run it (tooling exists: `eval/width_metric.py`) or explicitly deprioritize.

**🟢 Chroma-steer full 3456-cell grid parked for Kim's trim+greenlight**, plus a missing head file (`latch_sa3_chroma_other_best.pt`) blocking a 3rd model tab.
→ Surface to Kim; resolve the head-file location separately.

---

## WINTERMUTE

**🟡 `model.py` silent duration/sample_size clamp bug — pooled 07-15, endorsed by CONTINUITY, still unfixed.** `_adapt_sample_size` still has no warning; `cli.py` never computes `sample_size` from `--duration`. This is the exact bug that cost GHOST-NOTE two wasted renders during gate (b).
→ Cheap fix (~2 lines): a log warning, or hand it off.

**🟡 CSC Allas vs LUMI-O identity never verified** — blocks building the cold-backup pipeline for the single-copy `latents_sa3` corpus (still a live single-point-of-failure risk).
→ WINTERMUTE checks LUMI/CSC docs directly (has the account access).

**🟡 E1 λ=1e7 "alive vs damaged" ear-verdict from Kim never obtained**, despite the render completing and the knee being found at λ≈1e6.
→ Needs Kim's ears specifically; low-effort, just needs asking again now that he's back.

**🟢 [manual-verify] `breathing_v2` + `breathing_v2_flux` (nl06/nl075, both variants) rendered 07-12/07-13, no write-up of the original question found anywhere** (escape-kick amplitude effectiveness, per the #35 breathing-controller thread). THE-FINN has since pulled some of these clips into a *different* analysis (E0 regime-labeling) — but that doesn't answer what the breathing test itself was for.
→ Either write up the original verdict from what's already rendered, or explicitly fold it into #35's later design (don't let it sit unlabeled).

**🟢 [manual-verify] `schedule_ladder` — "9/9 rendered, sent to Kim 07-13" recorded, but the actual hypothesis (does Flux dist-shift give more a2a style authority than LogSNR) was never answered.** `result` field still just says "rendered"; `kim_feedback` is null.
→ Needs either Kim's listening verdict or an independent metric read of the 9 clips.

**🟢 explorer_sa3 UI redesign brief (Kim's "Claude Design" ask) — zero evidence anyone picked it up.** `UI_BRIEF.md` was refreshed and committed (mir) but no dialogue/journal mention of the design pass actually happening.
→ This is Kim's own task (delegating to Claude Design externally) — worth a status check with him, not a fleet action item.

**🟢 mir `bend_tab.py`/`bracket.py` (explorer Latent-lab tab) never committed in mir's history on any branch** — untracked working-tree files since 07-13.
→ Commit or confirm it's intentionally scratch.

---

## THE-FINN

**~~🟡 THE-FINN's daily fleet digest~~ — CLOSED 2026-07-19 by THE-FINN.** Correction on the finding: it hadn't "broken," it was never built — Kim assigned `profiles/daily/` on 07-12 and the dir didn't exist. Fixed: dir established, 07-16→07-19 backfilled from live chat (`1eec873`), README points at this doc for the 07-12→07-15 window so the two audits compound rather than reset. THE-FINN is now posting per-day as each closes.

**🟢 [manual-verify] EMA retrain of 7 medium/dead LatCH heads — "did EMA help" still unmeasured.** THE-FINN confirms: not his to own, but he'll track it in the daily digest so it doesn't age out once the retrain settles.

**~~🟢 THE-FINN's paper-gap-audit 3 wins — "no confirmation of pickup"~~ — RESOLVED 2026-07-19 by THE-FINN.** CONTINUITY did ack them (her DM 07-18 03:53: "the 3 confirmed are good leads, TADA preservation-AUC is the HIGH one") and independently converged on the Kynkaanniemi gap in her own verdict-page pass. She's holding them for Kim's return since cards are saturated — ack'd + parked, not dropped.

---

## Kim

**🟢 CSC data-movement/Allas guidelines doc (THE-FINN, 07-18) — no confirmation Kim has read it or that it changed the LUMI backup plan.**
→ Not urgent; just flagging it exists for whenever he's ready.

## Unowned

**🟡 `models.html`/`model_matrix.html` — no per-family grouping despite growing to 85+ models**, several dialogue mentions of it becoming hard to navigate, no one has picked up the reorg.

**~~🟢 A prior fleet-wide dropped-thread audit~~ — IDENTIFIED 2026-07-19 by THE-FINN.** It's his own 2026-07-03 orientation audit (24 estate-wide inconsistencies, all routed) — same genre (patrol) but a different window (day-one estate state vs this doc's 07-12→07-19 dropped threads), so the two compound rather than duplicate. THE-FINN has proposed a persistent OPEN-THREADS ledger (his to own, as patrol) folding both audits' still-open items so future audits don't reset to zero each time — endorsed.

---

## Additions — THE-FINN, 2026-07-19 (the pending-Kim-verdict blind spot)

*Kim asked whether I had anything to add. I do — a class this audit's method
systematically under-detects. A 6-source code/git/log sweep finds threads by what
**exists** (a null field, an uncommitted file, an unlabeled render). But a thread
that is "someone asked Kim for an ear-verdict and it never came back" shows up only
as an **absence** — no artifact to grep. Reading the dialogue for questions-put-to-Kim
that got no answer is the complementary sweep. Both below are now directly actionable
since Kim is back tonight.*

**🔴 HIGH — the formal E0 meter-validation AUC gate is still blocked on Kim's E0
listening-test verdicts, which never came back.** WINTERMUTE built `listening_e0.html`
(14 blind excerpts) on 07-15 specifically to close the E0 label gap (my manifest came
in 8 loopy / 15 good, short of the ≥20/≥20 target — I escalated the gap to Kim: fresh
ears vs loosen-tier vs proceed-noisy). W's plan: "when they land I pull the export,
extend the manifest, re-run the AUC gate," and "Kim's listening verdicts still gate the
formal E0 AUC" (chat 07-15/07-16). No later record shows the verdicts landing, the
label-gap decision being made, or the AUC re-run. The comment system went write-only
07-15, so those verdicts route only through Kim's chat relay — which never happened.
Consequence: the loopiness-meter validation that W said "gates everything downstream"
in the longform program is still open. (The E1 *pilot* progressed independently —
guided-vs-unguided same-seed deltas are confound-immune — but the formal meter gate is
not the pilot.) **→ Ask Kim for the E0 verdicts now; make the label-gap call
(fresh-ears-came / loosen-tier / proceed-noisy); re-run the AUC.**

**🟡 — section-conditioning adapter training is HELD on a Kim boundary-arbitration that
never happened.** WINTERMUTE, 07-17: corpus-wide section labels shipped, but boundary
validation vs MuScriptor's MIDI sections FAILED (F@3s ~0.13; the two lenses segment
different structure), so "Kim's ears arbitrate this evening (`eval/section_spotcheck.md`,
5 tracks); **adapter training HOLDS until then**." Two evenings later, no arbitration is
on record and the adapter is still held. **→ Kim spot-checks the 5 tracks (energy/
arrangement segmentation vs riff-novelty) and rules, or the section-adapter stays
blocked indefinitely.**

**🟡 — the E0 labeled set's regime confound was flagged with a fix that isn't confirmed
done.** Same 07-16 thread: the E0 AUC set mixes T=4096 (mostly loopy labels) and w1024
(several good labels) renders; W's own note, "quality differs so much across regimes
that cross-regime metric comparison is risky → **stratify by regime**." No record shows
the stratification was applied before the AUC read. Ties into the HIGH item above — the
gate is both label-gapped *and* regime-confounded, and neither fix is confirmed. **→ Fold
the stratify-by-regime step into the AUC re-run.**

*(All three folded into `docs/open-threads.md`. Method note for the next audit: run a
dedicated "questions put to Kim, no answer on record" pass — it catches what the artifact
sweep can't.)*

## Resolved on inspection (found by a sweep, but already closed — no action needed)
- `explorer_render_server` DORA_REGISTRY Mantu/Mantu1 mount bug — **already fixed in code** (dual-mount probe is live in `explorer_render_server.py`).
- `paper_verdicts.html` — **shipped**, live 200, leak-scan clean (THE-FINN's log confirms).
