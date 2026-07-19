# Open threads — the standing patrol ledger

**Owner:** THE-FINN (patrol). **Purpose:** a *single living place* for dropped /
open / parked threads across the fleet, so patrol findings **accumulate instead of
resetting to zero** every time someone runs a fresh audit. Companion to the daily
digests (`profiles/daily/`).

**The rule** (same as the orientation-audit convention): before flagging something
on the wire, check it isn't already here; **strike a row when it's fixed** (leave it
struck, dated, for the record — don't delete). Every audit folds its still-open
items in here rather than starting a new standalone list.

Status key: **OPEN** · **PARKED** (waiting on Kim / a prerequisite) · **RESOLVED**
(struck, dated).

Established 2026-07-19 (GHOST-NOTE endorsed; folds the two patrol passes to date).

---

## Source 1 — Fleet audit 2026-07-19 (`docs/fleet-audit-2026-07-19.md`)

Window 07-12→07-19; full per-item evidence + next-steps live in that doc. Status
here is the *current* state; the audit doc is the snapshot.

### CONTINUITY
- **OPEN 🔴** Stereo mid/side-loss sweep (w0.1/w0.3) never produced a checkpoint — both arms OOM'd (07-17, 07-18), driver reports `DONE rc=0` masking the failure; `stereo_loss.py` still uncommitted. *(Fix rc-masking, re-run at safe batch, commit.)*
- **OPEN 🟡** `train_lora.py` + core SA3 training files uncommitted despite the 07-17 commit-call; LUMI campaigns already run off this exact code.
- **OPEN 🟡** E_fusion_v2 / A_cc_v2 `kim_feedback` verbatim-quote question (07-12) unanswered; both sidecars still `null`.
- **OPEN 🟡** Arms I/J/K (BoRA + per-alias previews) queued 07-09, never run or explicitly retired.
- **OPEN 🟡** `onset_FUSION_lr2e5_40epoch` never cross-examined against the 07-07 ear-favorite (`onset_Fusion_lr1e-4_randomcrop`) — two "favourite by ear" claims unreconciled.
- **PARKED 🟡** Residual-preservation Gate A / Gate B queued 07-19 — fresh, tracked so it doesn't age.
- **OPEN 🟢** Width-T-sweep — confirmed a *different* experiment from the stereo loss-weight sweep (not a dup); still un-run (`eval/width_metric.py` exists).
- **PARKED 🟢** Chroma-steer full 3456-cell grid — waiting on Kim's trim+greenlight; missing head file `latch_sa3_chroma_other_best.pt` blocks a 3rd tab.

### WINTERMUTE
- **OPEN 🟡** `model.py` silent duration/sample_size clamp — pooled 07-15, endorsed, still no warning; cost G two renders during gate (b).
- **RESOLVED 2026-07-19 (W)** ~~CSC Allas vs LUMI-O identity unverified~~ → W checked LUMI's own docs: **SEPARATE** services (LUMI-O = lumidata.eu; Allas = a3s.fi; both Ceph/S3, not interchangeable). Use **LUMI-O** (Kim already has LUMI project 465003186; `pack_data.sh` already assumes it).
- **PARKED 🟡 (Kim)** `latents_sa3` cold-backup — now unblocked except one Kim-only step: generate the LUMI-O token at auth.lumidata.eu (web login, not doable by an instance); then `pack_data.sh` → `rclone copy` to `lumi-465003186-private` is scriptable. Single-point-of-failure risk stands until it runs.
- **PARKED 🟡** E1 λ=1e7 "alive vs damaged" ear-verdict — needs Kim's ears.
- **OPEN 🟢** `breathing_v2`/`breathing_v2_flux` rendered 07-12/13, original question (escape-kick amplitude) never written up.
- **OPEN 🟢** `schedule_ladder` — "9/9 rendered, sent to Kim 07-13" but the Flux-vs-LogSNR-authority hypothesis never answered; `kim_feedback` null.
- **PARKED 🟢** explorer_sa3 UI redesign brief — Kim's own external ("Claude Design") task; status check with him.
- **OPEN 🟢** mir `bend_tab.py`/`bracket.py` never committed on any branch (untracked since 07-13).

### THE-FINN
- **RESOLVED 2026-07-19** ~~Daily digest never built~~ → `profiles/daily/` established + backfilled 07-16→07-19 (commit 1eec873); per-day going forward.
- **RESOLVED 2026-07-19** ~~Gap-audit 3 wins "no pickup"~~ → CONTINUITY acked them 07-18 03:53 (holding for Kim's return, cards saturated) — acked+parked, not dropped.
  - **SCHEDULED 2026-07-19 (Kim direct)** — gap-audit win #2, the Kynkäänniemi interval-CFG A/B, graduates to run **when a card frees** (C's lane; brief + the sigma=t≠EDM-sigma porting caveat DM'd to C; may ride the E1 grid per W's offer). TADA preservation-AUC eval (#1, HIGH) + DirectAudioEdit target-CFG ramp (#3) remain parked leads.
- **OPEN 🟢** EMA-retrain of 7 LatCH heads — checkpoints exist (ema20/ema40), "did EMA help" never measured; tracked in the digest so it doesn't age out. *(Not F-owned; flagging.)*

### Added by THE-FINN 2026-07-19 (pending-Kim-verdict class — G's artifact sweep under-detects these)
- **OPEN 🔴 (W/Kim)** Formal E0 meter-validation AUC gate blocked on Kim's E0 listening-test verdicts (listening_e0.html, 07-15) that never came back; label-gap decision (fresh-ears/loosen/proceed-noisy) never made; AUC never re-run. W said it "gates everything downstream." → ask Kim now.
- **OPEN 🟡 (Kim)** Section-conditioning adapter training HELD on Kim's boundary arbitration (07-17, `eval/section_spotcheck.md`, 5 tracks) — never arbitrated, adapter blocked 2+ evenings. → Kim rules.
- **OPEN 🟡 (C/W)** E0 labeled set regime-confound (T=4096 vs w1024 mix); fix "stratify by regime" flagged 07-16, not confirmed applied. → fold into the AUC re-run above.

### Kim / Unowned
- **PARKED 🟢** CSC data-movement/Allas guidelines doc (F, 07-18) — no confirmation Kim has read it / changed the backup plan.
- **OPEN 🟡** `models.html`/`model_matrix.html` no per-family grouping despite 85+ models — navigation pain, no owner. *(Ties to the FiLM/LatCH page-split thread F proposed 07-12; G's `latch_sa3_matrix.html` is the LatCH half.)*

---

## Source 2 — Orientation audit 2026-07-03 (`[[sao-orientation-2026-07]]`, memory)

Day-one estate sweep, 24 confirmed items. **Reconciliation as of 2026-07-19 is
PARTIAL** — most are two weeks old and presumed-closed by subsequent doc work, but
this had no living ledger, so items went unstruck. Spot-checks so far:

- **RESOLVED** (verified 07-19) — item 1: MASTER §4 now correctly states repos are PRIVATE (MASTER.md:200).
- **RESOLVED 2026-07-19** ~~item 16: `model-overview.md:41` said 4096× downsampling yet "216 latents / 10 s" (= 21.6 Hz, self-contradiction)~~ → fixed to ≈108 latents / 10.77 Hz this pass. *(A flagged item that survived 16 days unstruck — the exact failure this ledger prevents.)*
- **OPEN — needs a reconciliation pass** — the remaining ~22 orientation items (MASTER §4 handles/profiles-flow staleness, public-mirror redaction, the two agent-defs in /home/kim/.claude predating the protocol era, book/docs numerics, the UNVERIFIED queue) have NOT each been re-checked against current state. **Tracked task (F):** one pass reconciling all 24 against live state, striking the fixed ones, promoting any still-open into the sections above.

---

## Changelog
- **2026-07-19** — established; folded the fleet audit + orientation audit; resolved 2 F-items + 2 orientation items (1 verified-already-fixed, 1 fixed this pass); opened the orientation-reconciliation task.
