# Open-tails & unfinished-ideas audit — 2026-08-07

Overseer sweep (THE-FINN), three parallel readers over: task ledgers, hypotheses/ideas
vs. delivered, and orphaned/never-run code. Working tree `/home/kim/Projects/SAO`.
Nothing was changed. All file:line cites are against the current tree.

**Headline:** the fleet's *tracked* discipline is good — `docs/open-threads.md` +
`KIM-TASKLIST.md` catch most parked work. The real risk is three narrow classes:
1. **Untracked one-mention tails** — floated once in a journal/consult, entered no ledger.
2. **Spec-only campaigns** — fully designed, pre-registered in some cases, zero build.
3. **One systemic root-cause** (no post-training auto-render *pipeline* — see §0) that keeps
   manufacturing the "checkpoint exists, no clips, ear-gated forever" backlog.

> **Fleet-reviewed 2026-08-08** (WINTERMUTE, GHOST-NOTE, CONTINUITY). Corrections folded below;
> the review materially sharpened §0 (it's *three* gaps, not one, and it's owned not unowned),
> re-verified aug8 to true state, and closed A1. **Standing principle adopted from the review
> (W):** *an audit line must cite a CHECK, not a colleague* — the same family as
> "manifest-count ≠ playability", "lockfile ≠ GPU-state", "HTTP-200 ≠ clips-present". This audit
> itself produced three worked examples in one thread (aug8 state was different from what each of
> three of us relayed; one filesystem check settled it).

---

## 0. The single highest-leverage finding — a post-training PIPELINE (three gaps in series)

**`train_lora.py` has ZERO post-training render step** (grep-confirmed), despite Kim's standing
directive that runs auto-render the standard clip grid. **Corrected by the review — it is NOT one
hook and NOT unowned:**

- **Ownership (G + C):** CONTINUITY claimed the render hook in an 08-05 DM ("belongs next to my
  aug8/train sbatch work"). It is **designed-not-built + C-owned**, not unowned. The risk was never
  "nobody will build it" — it's that it sat designed-not-built while runs piled up. C's per-run
  render sbatches (`precision_ladder_render`, `fullft_bigset_render`, aug8's) are stopgaps; the
  *unified* train-finish hook is the unbuilt piece.
- **It's THREE gaps in series, not one (W):** a checkpoint is auditable only when all three complete,
  each gated on **the artifact existing, not the exit code**:
  - **(a) RENDER** — the missing `train_lora.py` hook. **C owns.**
  - **(b) SCORE** — meter + CLAP + `clip_metrics` rows. W's evidence: 5,532 clips sat rendered-and-
    served for *weeks* with zero CLAP rows → no DoRA-table rows → the board honestly showed em-dashes.
    **That was Kim's "clickables missing for many models" — never a board bug.** **W owns.**
  - **(c) PUBLISH/SYNC** — manifest + deploy + **verify-over-HTTP**. Separately, pages went live whose
    audio was never synced (headb_bracket was one command from shipping with all 384 clips absent);
    44 GB of clips once sat under a sibling base while a board 404'd. **W owns** (exposed as one
    callable step the hook invokes).
- **Why build only (a) is a trap:** it just reshapes the backlog from "checkpoint with no clips" to
  "clips nobody can score or rank" — the exact state W spent 08-05/06 digging out of.

**Live instance = aug8** (verified, per the cite-a-check principle): render DONE on LUMI
(`job 20792735`, Kim-submitted 08-07, completed, real non-smoke ckpts); **pull-to-local completing
08-08** (W checked the mirror directly this morning: not yet landed; G/C then confirmed the rsync
finished and are reconciling a file-count anomaly). Once local, G runs the (b)+(c) chain
(`ingest_matrix_cells` → `clip_metrics` DSP → `clip_metrics_audiobox` [mind `gpu_guard.sh`] →
`clap_score` → rebuild `dora_table`+`model_matrix` → W deploy). The general pipeline and the aug8
instance are the same shape. `docs/todos.md:15-28`, `KIM-TASKLIST:37`.

**Building this pipeline retroactively unblocks the ear-gated items in §4.** (Highest-leverage item
in the audit; C-owned and ready to build — awaiting Kim's priority call vs. the other in-flight work.)

---

## 1. Untracked one-mention tails (Kim's specific worry — NOT in any ledger)

| # | Item | Source | Judgment |
|---|------|--------|----------|
| A1 | **STATISTICAL_ANALYSIS_MANUAL.md documents CLI flags that don't exist** (`--feature-select/--per-track/--pca/--vif/--cluster/--mi/--build-db/--scatter/--quadrant`; real CLI is only `path [-o][-v][-c][--corr-threshold][-l]`). G said "not yet flagged to the fleet formally," then never flagged it. | `ghost-note.journal.md:575-580` (08-02) | ✅ **FIXED 08-08 (G):** truth-banner added to `mir/src/tools/STATISTICAL_ANALYSIS_MANUAL.md` listing the real 5-flag CLI (grep-verified vs `add_argument`), rest marked ASPIRATIONAL (not a full rewrite). mir-same-chroma duplicate left for its own owner. |
| A2 | Promised **adversarial/literature-grounded analysis of the EMA-vs-early-stop recipe** "once the soups finish" — soups queued, writeup never surfaced. | `WHAT-KIM-WANTED-TO-KNOW.md:106-107` | Probably-abandoned; confirm. |
| A3 | **The 2026-08-04 melody-precision consult's next-actions** never closed (C-confirmed all *parked*, none dead, none done off-record): (1) step-0 kernel/optimizer precision code-read — **asserted-not-verified** (C answered from knowledge that every SA3 config stores activations in half precision; not an actual code-read); (2) the **fp32-residual-stream A/B arm** — designed but build-HELD, never run; **the decisive test for the fp32/bf16 audible gap** (W+C agree), GPU-gated (foreign-GPU cycling + purge); (3) C's Gemini brief on sub-dominant-signal precision; (4) **[added by W] C's 08-04 `fp32cmp`-vs-`bf16cmp` weight-diff probe** — tool exists (`eval/precision_weight_diff.py`), launched ("launching it now"), **no verdict ever landed** — the one that settles real-basin-vs-noise on the audible gap. *(Ownership note: the Qiu multiple-maxima check + W's sign-coherence capture probe are **W's/consult-side**, never C-greenlit — not C's to close.)* | `AGENT_DIALOGUE.md:14-46` | **Still-open.** Net: fp32/bf16 gap is NOT metric-settled; the fp32-residual arm is the open decisive piece. |
| A4 | **Explorer steering-contract v2** — "Payload smoke-tested. Server restart pending to activate." Built-but-maybe-never-activated (23→35 states, sigma-interval DoRA knobs). | `continuity.tasks.md:176` (07-12) | Stale — verify activation. |
| A5 | **Drift-prediction analysis** — "TODO: THE-FINN fold into DISCOVERIES once confirmed." Gated on a not-yet-confirmed result. | `continuity.tasks.md:192` (07-20) | Probably died on the condition. |

---

## 2. Spec-only campaigns — designed, sometimes pre-registered, ZERO build (biggest idea-vs-delivered gap)

- **The entire HF-clarity recovery plan** — `clarity-recovery-plan-2026-08-02.md`. #64 regression-ceiling
  diagnostic (cheapest gate, :78), #62 ADAA-SnakeBeta swap + latent-conditioning (:37), Track A generative
  pseudo-complex post-net + multi-period discriminator + anti-wrapping GD stabilizer (:47, the main HF lever),
  #65 latent-whitening probe (:60), #66 v-pred+ZTSNR on the 1.4B DiT with a **pre-registered ≥10% >8kHz-LSD
  target** (:44/66), Track C Triton path (:71). **Premise now CONFIRMED** by the codec-clarity ladder
  (SAME owns ~100% of HF loss, m4a transparent — `WORKLOG.md:2009`, 08-06). Diagnosis validated, build tree untouched.
- **Melody-selective subspace v3 A/B** — whitened-CSP rebuild lifted held-out melody SNR 1.0×→5.1×
  (`lumi/melody_subspace15_selective_v3.npz`); "REAL proof = training A/B, needs a LUMI submit."
  `continuity.journal.md:1428-1431` (08-06, the journal's final entry). sbatch wired, one submit from Kim.
- **Residual-stream fp32 precision arm + double-difference harness** — the 08-04 consult converged on a sharp,
  testable claim (melody wall = systematic sub-ULP zeroing at every half-precision residual write; 786×=2^9.6
  anisotropy > bf16's 8 mantissa bits) and designed the full arms (fp32-attn / fp32-residual / bf16+SR / fp32-master;
  2×2 double-difference). The decisive **fp32-residual arm was designed but never built** — C flagged "Flag build HELD pending."
- **E5 hierarchical-band RoPE** — its gate (E3-positive) **fired** (phrase-return 10× over permuted baseline,
  `WORKLOG.md:1990`) yet no record E5 ever launched. Dropped/forgotten at the trigger. `open-threads.md:136`.
- **Block-13 / L11-15 hook-fed rhythm CONTROL head** — arguably the best-justified unbuilt idea in the corpus;
  two docs give it a "green light + noise guarantee" (rhythm computed at L11-15, rebuilt noise-invariantly).
  Never built. `layer-feature-map.md:41-46`, `layer-feature-noise-invariance.md:71-73`, `docs/todos.md:60-66`.
- **Bracket + presets port to the Dash explorer** — whole 23KB design doc, "design only, no code."
  `bracket-port-design-2026-07-13.md`.
- **Relevance-routed DoRA (both axes)** — Axis-2 era-DoRA MVP ("directly tests Kim's era=low-noise hypothesis,
  testable this week") + Axis-1 probe-gradient localizer. Neither built. `research-brief-relevance-routed-dora.md:92-98`,
  `rigor-review-...:114-117` (07-05). The #59 subspace work targets *melody*, not era/noise-band, so it doesn't close this.
- **APT (adversarial post-training on LUMI-G)** — full recipe specced (paper eqs 6-11), never begun. `docs/todos.md:9,40-50`.
- **Longform S-arm path** — S1 recurrence-guidance prototype (the "go/no-go on the whole thesis"), S3 diffusion-forcing
  finetune (flagship LUMI), S6 Koopman-skeleton prior (highest-upside). Unbuilt. `research-synopsis-longform-continuation.md:219-227`.
  (Breathing controller #35 Tier-1 = the one piece that shipped + validated.)
- **paper-gap-audit "confirmed wins" never built** — TADA alignment-preservation AUC eval protocol (:40-78) and
  DirectAudioEdit weak→strong target-CFG ramp (:121-157), both self-billed as clean wins. Plus a shelf of LOW-value
  designed evals (SAME ILD readout, UltraViCo Eq-5 decay-mod A/B, SaFa E4, SimDPS, TC-LoRA, NA-RFM, STAS, SegTune,
  UNISON, SDEdit sweep, Cautious-WD one-liner, AxBench ReFT-r1, SHIFT). `paper-gap-audit-2026-07-18.md`.
- **Reality-structured-model experiments** — E2 free-PHM adapter BUILT (param-parity verified) but mis-scoped local,
  re-diagnosed as LUMI, never trained. E4 Fisher-Rao downgraded to reference. Tier-2 toys (tree-PE, quantized attention,
  hyperbolic latent) all unbuilt. `open-threads.md:135-138`.
- **ARC-Forcing #46 part 2** — only the rollout-dataset builder exists; the load-bearing adversarial L_R+L_C objective
  with base-init discriminator is absent; continuation-FT base-choice undecided. `paper-gap-audit:468-487`, `plan-2026-07-22` Lane 2.4.
- **Residual distribution-matching critic + its two gating pre-tests** (Gate A corpus-PSD-noise inject, Gate B 24-seed
  HF-variance fan). Neither gate ran, so "is conditional-mean generation even real?" stays untested. `continuity.journal.md:916-921`.
- **Weight-mutation shuffle-amount sweep** (2/5/8/10% × seeds × early/late decay) — "NEXT (Kim's call)" after shuffle_05
  produced a "new musical form" result; never run. `WORKLOG.md:1629`, `weight-garden-audition-notes.md:45`, DISCOVERIES:90 ("the mutation that never was").

---

## 3. Cheap tests of a Kim hypothesis, untouched (minutes-to-hours, high signal)

- **FusionCC-vs-plain-Fusion clean-audio EAR audition** — the onset campaign's own #1 remaining action. Metric side
  closed (FusionCC 0.77 > plain 0.717 on corrected p95 meter); ear side never done. `onset-density-control-narrative.md §3/4/6`, DISCOVERIES:46.
- **Matched-length native A/B** (same render duration across models) — self-identified as *the* decisive missing long-form
  test; settles the fp32-frames / #54 headline. `training-findings.md:96-99`, `WORKLOG.md:1985`, `continuity.journal.md:1215-1222`.
- **Outro/silence-cheat fix at eval + end-of-track-crop tiers** — dataset tier fixed (109/109 tests); the (b) downweight
  high-`relative_position_end` low-RMS tail crops and (c) eval-side active-region density were never done. `docs/todos.md:122-129`.
- **The 5 ASK-KIM kill/keep rulings** (all un-actioned since 2026-07-22, minutes to clear): LatCH LR-knee 3e-3 retest
  ("obsolete, kill?"); short-form adequacy ruling (drags the 579-dropped-sources item); CLAUDE.md `@import` ("one-word kill?");
  Muon high-LR (kill or gentle sweep); APT priority call. `docs/todos.md:5-9`.

---

## 4. Waiting on Kim's ears / a ruling (the ear-queue — much of it a symptom of §0)

- **E0 meter-validation AUC gate** — blocked on Kim's E0 listening verdicts (07-15) that never came back; "gates
  everything downstream." Plus the E0 regime-confound stratify-fix. `open-threads.md:52,54`. 🔴
- **Section-conditioning adapter** — HELD on Kim's boundary arbitration, blocked 2+ evenings, never arbitrated.
  `open-threads.md:53`, `eval/section_spotcheck.md`. **(C-confirmed 08-08: still Kim-gated, no movement.)**
- **E3 metrical-position FiLM** — trained + meter-positive, awaiting "does it *sound* like structure?"; clips local, not hosted. `WORKLOG.md:1990`.
- **28 truncated 120s native renders** — exclude/re-render DECISION PENDING KIM; plus the quarantine-doesn't-gate-ingestion
  code fix (a BROKEN dir got scored). `open-threads.md:127`, `WORKLOG.md:43-46`.
- **iGPU-compositor desk move → then reassess local-render ban** — coupled decision on Kim's desk. `open-threads.md:60`.
- **same_chroma 384-d full grid** (3456 cells) + missing 3rd head `latch_sa3_chroma_other_best.pt` — parked for Kim's trim+greenlight. `continuity.journal.md:856-861`.
- **Promote ema40 heads to `_best` + re-render latch matrix** — gated on Kim's ear. `WORKLOG.md:1931`.
- W's four active Kim-decision items (ssh/Tailscale/local-notes/lenvar-relay) — well-tracked. `KIM-TASKLIST.md:24-36,84-86`.

---

## 5. Stalled at a gate / partially explored (real work, not lost, but no verdict)

- **Stereo mid/side aux-loss sweep (#3)** — both arms OOM'd 07-17/18, driver `DONE rc=0` **masked the failure**;
  `stereo_loss.py` still uncommitted with a HIGH silent-OOM-masking bug; no safe-batch re-run ever produced a checkpoint.
  `open-threads.md:26`, `continuity.journal.md:804-807,910,960-962`.
- **ctrl_matrix #53 full control campaign** (60 tasks) — "armed" 07-17/18, no results entry; also the vehicle for the
  encodability-screen *prospective* validation (score R² before training) which therefore also never happened. `continuity.journal.md:41-46,823`.
- **E1a x0-target arm** — inconclusive (+0.010 recurrence, near-noise); **E1b true x̂-head gated on E1a signalling → never ran.** `WORKLOG.md:1988`.
- **Precision ladder** (fp32/bf16-mixed/fp16-mixed, T256) — job 20682678 "all 3 arms training" `WORKLOG.md:2006`; no verdict on record (may have closed off-log).
- **Layer-restricted control adapters L8-15** — single-tap L14 ≈ full onset adapter, but HF-blowout hardening was an
  amputation artifact; next levers (gain ladder, HF-drift penalty) not started. `WORKLOG.md:1934`, `open-threads.md:66`.
- **Interval-CFG mid-band (#26)** — partial lift; FAD never run, W co-score + Kim's ear on nl.475 never landed. `continuity.journal.md:1172-1173`. **(C-confirmed 08-08: still open, parked not dead; W had no record of the co-score ask.)**
- **Melody-wall subloss (#59)** — near-null; needs the lead-isolated **MuScriptor-MIDI contour metric (never built)** + Kim's ears. `WORKLOG.md:1998`.
- **G2b sub-frame phase branch REOPENED** with measured foundation, but no PhaseSpin/complex-pair construct built afterward. `continuity.journal.md:1298-1301`.
- **Width-T-sweep** (stereo-width vs T) — confirmed NOT a dup of the stereo-loss sweep; `eval/width_metric.py` ready, never run. `open-threads.md:32`.

---

## 6. Orphaned / never-run code (334 first-party files scanned; ~26 orphaned entry-points)

**Caveat:** these are mostly complete, high-quality one-shot probes that write to `--out` run-dirs on external
drives; absence of an in-repo output trace strongly suggests non-use but can't *prove* a probe never ran once interactively.

**Half-finished stubs (inside USED library modules — check consumers actually work):**
- `latch/probe_layer_feature_map.py:136` — GPU activation-extraction is a `raise NotImplementedError` "contract only,"
  yet imported by `run_layer_feature_map.py`, `extract_layer_activations.py`, `eval/stereo_phase_meter.py`. Do those hit the stub?
- `control/sa3_control/chroma_losses.py:90` — `chroma_loss_rung3_softdtw` NotImplementedError ("build only if rung 1/2 fail Kim's ear"). Benign deferred rung.
- (These two were the ONLY half-finished markers in 334 files.)

**Untracked, strongest "written-not-run" smell:**
- `eval/musicology/enrich_muscriptor_meta.py` — back-fills `source_path`; untracked, no `.stats.json`/`index.jsonl` target exists here.
- `eval/musicology/sf2_catalog/extract_sf2_presets.py` — untracked BUT its `sf2_presets.jsonl` output exists → it ran; just never committed.

**Orphaned entry-points, ranked by never-run smell (complete code, zero refs, no output trace):**
1. LatCH late-June one-offs — `latch/latch_roundtrip_check.py`, `latch_verify_rhythm.py`, `latch_verify_rms.py`,
   `latch_trajectory_probe.py`, `render_audition_sweep.py`. `latch/` holds no output artifacts; line moved to `stable-audio-3`. Abandoned scaffolding.
2. reality-structured / metrical-tree-PE spec probes — `eval/e1_pretest_error_spectrum.py`, `e3_structure_bracket.py`,
   `phase_invariance_probe.py`, `phase_recoverability_probe.py`, `phase_accuracy_hires.py`. No committed output, no refs. If those tiers never launched, this cluster is dead.
3. precision diagnostics — `eval/precision_weight_diff.py`, `update_disappearance_test.py`, `profile_phm.py`.
   **Correction (C, 08-08): `precision_weight_diff.py` is NOT orphaned** — it's a real tool, *launched* 08-04, but
   **no verdict ever landed** (see A3). So: reclassify from "orphaned" to "ran, result never published" — a
   different and arguably worse failure (the decisive fp32/bf16 basin question is one un-published run away).
4. A/B analyzers with committed render companions but no output — `eval/safa_ab.py` (#27), `steer_orthogonal_ab_analyze.py` (#58),
   `interval_cfg_ab_analyze.py` (#26), `gain_ladder_layer_restricted.py` (#56), `concept_axis_geometry.py`, `structure_ssm.py`.
5. `control/sa3_control/dora_weight_glitch.py`, `hardness_gain_bracket.py` — 07 diagnostics, no output/refs.
6. `control/sa3_control/tests/test_melody_contour_cpu.py` — standalone `__main__` test referenced by nothing; check pytest collects it.
7. LUMI job scripts (outputs live on cluster, lower confidence) — `lumi/bench_encode.py`, `lumi/goa_granite_task.py`.
8. page/sidecar generators with absent outputs — `eval/build_training_curves_page.py`, `eval/build_goa_archive_sidecar.py`.

**Cleared — did-its-job** (zero refs but positive run evidence): `lr_granularity_beat_probe.py`, `longform_crossfade_eval.py`,
`soup_cross_dora.py`, `precision_recurrence_score.py`, `caption_corpus_sample.py`, `lumi/gen_length_variant_tasks.py`, `extract_sf2_presets.py`.

---

## 7. Ledger-hygiene contradictions to strike (housekeeping, low urgency)

- `model.py` silent 120s sample_size clamp — listed **OPEN 🟡** `open-threads.md:36` but **DONE (C, 07-22)** `docs/todos.md:243-248`. Strike the open-threads row.
- `train_lora.py` + core SA3 files "uncommitted" `open-threads.md:27` — almost certainly swept in by the 08-04 consolidation (d9475c3, 1742 files). Row not struck.
- Arms I/J/K (BoRA + per-alias previews), Arms #28/#29/#36/#37/#39 — queued 07-09, "never run or explicitly retired." Formally retire or run. `open-threads.md:29-30`.
- `onset_FUSION_lr2e5_40epoch` vs 07-07 ear-favorite — two "favourite by ear" claims never reconciled. `open-threads.md:30`.

---

## 8. Meta / overseer-domain hygiene

- **THE-FINN's journal is 3 weeks stale** (stops 2026-07-18) while `the-finn.tasks.md` continues — the exact "milestone
  list went stale" failure F's own 07-14 entry warns about. (My own hygiene debt.)
- **Root `knowledge.md` is MISSING** (widely referenced; `papers/knowledge.md` exists, root does not) — verify whether a link is broken or it moved.
- **Orientation-audit reconciliation** — ~22 of my 24 July-03 findings never re-checked. `open-threads.md:82`.
- **paper-verdicts public-doc reconciles** — TADA/UltraViCo (`open-threads.md:66`) and UltraViCo untested→nulled (`open-threads.md:141`), both PENDING F.
- **kim-return-notes** does not exist as a file — retired into `KIM-TASKLIST.md` (08-05). A stale `kim_notes.log` (07-07) at repo root is a compaction dump, not a tracker — candidate to archive.

---

## Suggested triage order

1. **Build the post-training render→score→publish PIPELINE (§0)** — highest leverage; retroactively unblocks the
   §4 ear-queue. C owns (a) render, W owns (b) score + (c) publish/verify. Awaiting Kim's priority call. aug8 is
   the live instance (pull completing 08-08).
2. **The untracked one-mention tails (§1)** — A1 ✅ done (G); A2–A5 still none-in-any-ledger, highest loss-risk.
3. **The 5 ASK-KIM kill/keep rulings (§3)** — minutes to clear, unblock 07-22 debt.
4. **Reconcile the ledger contradictions (§7)** and the two "confirm/close" tags nobody actioned (KIM-TASKLIST:37,51).
5. **Pick from the spec-only shelf (§2)** — the HF-clarity plan and subspace-v3 A/B are the two whose premises are already confirmed.
