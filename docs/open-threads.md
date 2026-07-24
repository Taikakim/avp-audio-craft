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
- **CORRECTED 2026-07-19 (Kim):** the "single-copy latents_sa3 = single point of failure" framing the fleet + this ledger repeated is **wrong** — there is a **second local copy** at `/run/media/kim/Mantu/sa3-latents_backup/latents_sa3/`, verified complete (27003/27003 files) and in parity as of 07-12 (the dataset hasn't grown since). The real risk is **currency**, per Kim: "as long as it's kept up to date" — and the sync is **manual** (G synced it 07-14, "was 5402 behind"; no cron/systemd/script automates it). **OPEN 🟢 (W/Kim):** decide whether to automate the Mantu sync (small rsync `.path`/cron) so it can't silently drift. **PARKED 🟢 (Kim):** LUMI-O off-site backup is now a *nice-to-have* (geographic/off-site redundancy), not the only line of defense — the one Kim-only step to enable it stays the auth.lumidata.eu token, then `pack_data.sh` → `rclone copy`.
- **PARKED 🟡** E1 λ=1e7 "alive vs damaged" ear-verdict — needs Kim's ears.
- **OPEN 🟢** `breathing_v2`/`breathing_v2_flux` rendered 07-12/13, original question (escape-kick amplitude) never written up.
- **OPEN 🟢** `schedule_ladder` — "9/9 rendered, sent to Kim 07-13" but the Flux-vs-LogSNR-authority hypothesis never answered; `kim_feedback` null.
- **PARKED 🟢** explorer_sa3 UI redesign brief — Kim's own external ("Claude Design") task; status check with him.
- **OPEN 🟢** mir `bend_tab.py`/`bracket.py` never committed on any branch (untracked since 07-13).

### THE-FINN
- **RESOLVED 2026-07-19** ~~Daily digest never built~~ → `profiles/daily/` established + backfilled 07-16→07-19 (commit 1eec873); per-day going forward.
- **RESOLVED 2026-07-19** ~~Gap-audit 3 wins "no pickup"~~ → CONTINUITY acked them 07-18 03:53 (holding for Kim's return, cards saturated) — acked+parked, not dropped.
  - **SCHEDULED 2026-07-19 (Kim direct)** — gap-audit win #2, the Kynkäänniemi interval-CFG A/B, graduates to run **when a card frees** (C's lane; brief + the sigma=t≠EDM-sigma porting caveat DM'd to C; may ride the E1 grid per W's offer). TADA preservation-AUC eval (#1, HIGH) + DirectAudioEdit target-CFG ramp (#3) remain parked leads.
- **RESOLVED 2026-07-19** (C's 07-22 todos-triage catch; evidence WORKLOG 07-19 21:08) — EMA-retrain of LatCH heads: "did EMA help" **IS measured**. EMA generalizes beyond spectral_skewness, helped 3/4 measurable weak heads, ema40 (2×-epochs+EMA) the consistent winner over ema20 (spectral_kurtosis standout ~2.7× more steering at gain 8192; no drift penalty — vindicates "train weak heads 2× longer" with EMA damping). Only remainder is a **Kim-ear item** (Lane-4-shaped): promote the ema40 heads to `_best` + re-render the latch matrix if his ear agrees. Tooling `eval/ema_help_{eval,measure}.py`.

### Added by THE-FINN 2026-07-19 (pending-Kim-verdict class — G's artifact sweep under-detects these)
- **OPEN 🔴 (W/Kim)** Formal E0 meter-validation AUC gate blocked on Kim's E0 listening-test verdicts (listening_e0.html, 07-15) that never came back; label-gap decision (fresh-ears/loosen/proceed-noisy) never made; AUC never re-run. W said it "gates everything downstream." → ask Kim now.
- **OPEN 🟡 (Kim)** Section-conditioning adapter training HELD on Kim's boundary arbitration (07-17, `eval/section_spotcheck.md`, 5 tracks) — never arbitrated, adapter blocked 2+ evenings. → Kim rules.
- **OPEN 🟡 (C/W)** E0 labeled set regime-confound (T=4096 vs w1024 mix); fix "stratify by regime" flagged 07-16, not confirmed applied. → fold into the AUC re-run above.

### Data redundancy — clip_metrics.db (Kim's 07-19 question: "how about the database?")
- **PARTLY-ADDRESSED 2026-07-19 (F)** `eval/clip_metrics.db` (the eval-metrics DB — 43704 rows incl. the GPU-expensive Audiobox ce/pq/cu) was **genuinely single-copy**: untracked in git, no Mantu copy, NOT covered by the latents backup (it's derived metrics over rendered *clips*, not a latent sidecar). The latent sidecars (INFO `.json` / `.TIMESERIES.npz`) *are* covered — they live inside `latents_sa3` — but the DB is a different artifact. Rebuild cost if lost: CPU metrics cheap (if clips survive), but the ~43k Audiobox scores are ~many GPU-hours. **Took an immediate safe snapshot** (sqlite online-backup) → `/run/media/kim/Mantu/sa3-latents_backup/clip_metrics.db`, parity verified. **OPEN 🟡 (W/Kim):** make it recurring — and use `sqlite3 .backup`/`.dump`, NOT naive rsync (the DB is live-written, mtime 07-19 12:43; rsyncing mid-write can copy a corrupt page). Also worth: is the comment-system JSONL (outside webroot) similarly single-copy?

### Watch — pending decisions with a dependent constraint (F tracks so the coupling doesn't drop)
- **iGPU-compositor move → then reassess the local-native-render ban** (Kim's policy 2026-07-21). GPU policy = the `SAO/.gpu.lock` `--pid-aware` mutex (job-vs-job). But until Kim moves the desktop compositor to the iGPU (planned "later this evening"), the display still shares the 16 GB compute card, so the mutex does NOT cover job-vs-DISPLAY — the **strict "no local T≥2048 renders → LUMI" rule (MASTER §5, hard renderer guard) is the only thing preventing a solo-big-render display OOM**. **When the iGPU move lands: revisit whether that strict ban / renderer guard can relax** (don't let it silently stay over-conservative forever, and don't let anyone relax it BEFORE the iGPU move on "we have a mutex now" reasoning — the mutex doesn't stop a solo render OOMing the shared display). Owner of the move: Kim; F flags the reassessment when it lands.

- **UNDER IMPLEMENTATION 2026-07-23 (Kim direct)** — **Head B melody-contour CONDITIONING** via sa3_control FiLM (melody-adapter spec §2). Local pilot queued behind G: T=512 goa subset, r128 + melody-embedding, 4ep → acceptance = `chromaturn` adoption-vs-null + W's two live semantic columns (`mood_drift` 'melodic' retention + `clap_score` genre-hold). Escalation if FiLM taps underperform: the local-additive trained inpaint-conditioning channel ("in the model" without a conditioner FT). Ships the StemGen multi-source dropout (`--melody-dropout` independent of text). **Design constraints the probe arc established that the build MUST honor (F tracks so they don't drop):** (1) target **contour/interval, not absolute pitch** — contour is timbre-robust, absolute is timbre-fragile (LOPO 0.77, negative tail e.g. Orchestra Hit); (2) train **mix-native** — clean-stem formally contraindicated (solo decoders die on mixes, retention −0.17; offbeat-hat is the worst masker); (3) multi-timbre span sampled as **fonts, not patch numbers** (write-map = 1 supercluster + outlier tail). **Framing on record (C+W):** the ~0.27 Head-A ceiling bounds the lightweight **READOUT**, NOT conditioning — Head B trains the model to USE the stream (onset-envelope is the working precedent), readability not required. Owners: C implements · G card-handoff · W semantic columns + eventual board 'melody source' dropdown · F ledger/patrol. Probe trail: `eval/musicology/{,latent_melody_analysis,gm_timbre_pitch,gm_multifont,head_a_ceiling}`.

### Watch — findings-in-revision that may stale a current-fact doc (F tracks; don't edit until settled)
- **Layer-localization story being revised — STILL MOVING, do not propagate** (C). Revised twice on 2026-07-21: the #44 rerun (03:15) claimed "L14 alone ≈ full 24-tap adapter, cleaner, write-site=compute-site"; the #56 training verdict (12:40) **overturned that** — L14-alone's cleanliness was an *amputation artifact* (muting 23/24 taps cut drive ~24× under the HF-blowout threshold), NOT a clean site; layer-restricted training (L8–15) restores authority but inherits the same HF-blowout, L13–15 fails outright. Hardening mechanism: this onset-adapter family partially encodes "more onsets" AS HF transients/clicks — the buzz Kim's ear caught in the LatCH review. Next levers (not started): gain ladder on L8–15, or an HF-drift penalty in the control loss. The **paper-verdicts TADA entry** (public, "localizes to late 16–23 opposite TADA's 12–13") — **still pending: reconcile once this settles**, which it has NOT (a claim was already overturned within 9 h — the reason not to rush the public doc). W28 chronicle synopsis stays as-is (point-in-time). Owner: C; F reconciles the public doc when stable.

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

## Standing gotchas (durable — surfaced by incidents, kept so they don't re-bite)
- **`ls *.m4a` (glob) returns NOTHING on a large dir (~19k+ files) — arg limit, not "empty".** Fooled F *and* W twice on 2026-07-21 (both read the model_matrix clip dir as "0 files / never shipped" when it had 19.8k). Use `find <dir> -name '*.m4a' | wc -l` or `ls <dir> | grep '\.m4a$' | wc -l`, never a bare glob, to count/verify a big directory. (Also in MASTER §5.) Corollary: an "it's not there" from a glob is not evidence of absence.
- **`agent_dialogue.py --text` via bash: backticks / `$(...)` / leading-`*` get shell-mangled.** Passing a message containing backticks (or `$()`, or glob chars) inside a double-quoted `--text "…"` triggers command-substitution/globbing — the wrapped text vanishes from the sent message (bit F 2026-07-20, ate a format template). Fix: **single-quote** the `--text` value, or use a heredoc/`--text "$(cat file)"`, or just avoid backticks in chat messages.
- **`.weights.ckpt` sibling convention** (from the 2026-07-19 optimizer-state prune). The prune replaces a fat `<name>.ckpt` with a slim `<name>.weights.ckpt` (same state_dict/lora_config, loads identically, NO optimizer state) and keeps **both** for the final epoch. Consequences for any tooling: (a) counting/globbing `*.ckpt` **double-counts** the final ckpt on pruned runs — dedup by aliasing `.weights.ckpt`→`.ckpt` (fixed in `build_model_index.py`, was inflating `n_ckpts` across ~28 runs); (b) anything reading `optimizer_states` (e.g. a re-run of the recipe-extraction that populated `models_index_overrides.json`) gets **nothing** from a slim ckpt — read the final fat ckpt or fall back to the stored recipe. *(Belongs in MASTER §5 too; flagged for whoever next holds that filelock.)*
- **Raw SA3 latents carry a pitch-independent 0.4–1.3 Hz oscillation that DOMINATES their autocorrelation** (found by C's melody-encoding probe, 2026-07-22, `eval/musicology/latent_melody_analysis/`). Any ACF / periodicity / recurrence / loop analysis on **raw** latents must **high-pass first**, or the low-freq oscillation swamps the real signal. ⚠ **Existing tools that eat raw latents in this band — CHECK them** (I confirmed both read raw latents + measure periodicity; NOT yet confirmed whether the oscillation actually corrupts their specific output): `stable-audio-3/.../recurrence_potential.py` (recurrence curve on `(B,C,T)` latent) and `eval/corpus_bands.py` (periodicity bands over `latents_sa3` `.npy`). If they already band-limit above 1.3 Hz they're fine; if not, their loop/recurrence numbers may be reading the oscillation. Owner of those tools (G/W) to verify + high-pass if needed.
- **GPU-mutex `--pid $$` is unsafe under `( … ) &` backgrounding** (GHOST-NOTE live catch, 2026-07-23). `filelock.py acquire --pid-aware --pid $$` only works if `$$` is a long-lived process; inside a parenthesized-group background launch `$$` can resolve to a short-lived nested-subshell pid that dies at once, leaving a DEAD pid → any pid-aware checker reclaims a still-running job. NOT a filelock bug (caller can't be second-guessed). Fix pattern: after launching the bg worker, `pgrep -f <script>` for its REAL pid and re-run `acquire … --pid-aware --pid <REALPID>` — the already-holds path now REWRITES the pid (c7dfc05), so it self-corrects with no hand-editing; and always `check` right after acquire. (Full note in `Misc/filelock.py` docstring.)
- **The GPU mutex does NOT serialize concurrent chains launched under ONE handle** (GHOST-NOTE live catch, 2026-07-24 — a real ~50-min collision → OOM). A handle's lock means "one holder"; a 2nd/3rd `acquire` under the *same* `--handle` silently succeeds (it reads as "I already hold this"), so N chains under one identity all run at once with no mutual exclusion. **Rule: one DISTINCT `--handle` per concurrent background GPU chain** (e.g. `GHOST-NOTE-xft` / `-fp32f` / `-winep`; the pattern `continuity-headb` already uses). Not a filelock bug (one lock file can't track N holders), but as of 2026-07-24 filelock.py emits a loud **CONCURRENCY WARNING** when a same-handle lock is held by a *live different* process — the tripwire that turns this silent gap visible. *(Candidate MASTER §5 line — flagged to W, §5 owner.)*

## Changelog
- **2026-07-20** — prune fallout: fixed `build_model_index.py` `.ckpt` double-count (28 pruned runs); recorded the `.weights.ckpt` standing gotcha; snapshotted `clip_metrics.db` (single-copy) to Mantu; corrected the "single-copy latents" premise (second Mantu copy exists).
- **2026-07-19** — established; folded the fleet audit + orientation audit; resolved 2 F-items + 2 orientation items (1 verified-already-fixed, 1 fixed this pass); opened the orientation-reconciliation task.
