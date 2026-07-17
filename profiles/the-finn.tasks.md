# THE-FINN — task log

> Terse, information-rich record of every experiment/research run/task worth tracking.
> Distinct from the journal (curated findings, links out) and WORKLOG.md (cross-repo
> relevant only) — see `SPEC-agent-profiles-journals.md` §3a. Reverse-chronological.

- [2026-07-17] Paper-verdicts page (Kim's ask, ultracode -- 10 parallel research agents
  + 1 synthesis agent, all findings spot-checked against source logs before shipping):
  Misc/paper_verdicts_data.json + Misc/build_paper_verdicts.py -> paper_verdicts.html.
  Went through all 41 PDFs in papers/ + 4 cited-no-PDF entries, classified each against
  REAL fleet experiments (not just relevance triage): 3 nulled (rope-jitter vs LoL,
  InfiniteAudio's FIFO claim, Du et al.'s gradient-cosine gate), 6 partial (incl. TADA's
  layer-localization and SaFa's seam-fix-but-not-loopiness), 5 confirmed (incl. the
  Kynkaanniemi limited-interval guidance already native in SA3's own DiT), 6 independent
  convergence (incl. LatCH -- built before we recognized the Stable Audio team's own
  paper as its source), 1 declined-to-test (Entropy-as-Structural-Prior, reasoned per
  the TADA-incident credibility bar), 23 untested (reviewed for relevance only, said so
  plainly rather than padded). Caught + fixed one overclaimed quote in my own review
  pass before shipping (a paraphrase presented as a verbatim commit-note quote).

**Historical section below (2026-07-03 through 2026-07-09) compiled by THE-FINN from
its own session transcript on 2026-07-09, as the one-time backfill for the new
convention — see §3a. Going forward, append your own lines as you finish tasks.**

**Gap acknowledged (2026-07-14, per C's new post-task-update protocol): nothing was
appended here between 07-09 and today despite a full week of shipped work. Backfilled
below from chat/DM timestamps, newest first.**

- [2026-07-15 (afternoon)] CSC data-movement/dataset-publishing guide (Kim's ask,
  direct research not workflow): read docs.csc.fi's data/moving (+rsync/tar_ssh
  sub-pages), dataset-sources, publishing-datasets, and Allas pages. Wrote
  docs/csc-data-guidelines-guide.md -- confirms pack_data.sh's tar-over-ssh
  approach is CSC's own recommended shape for our many-small-files corpora;
  flags Allas (10TB object storage) as a candidate fix for the standing
  single-copy latents_sa3 cold-backup risk, with an honest "needs verification"
  on whether Allas == the README's "LUMI-O"; cross-referenced CSC's dataset-
  publishing guidance (CC-BY, persistent IDs) against the AVP open-dataset
  release design -- confirms rather than changes it, flags a preservation-
  planning gap the release doc doesn't address yet. Passed to CONTINUITY.
- [2026-07-15 12:1x] Addendum on the LUMI guide (C's catch): its core premise
  (EFP WebUI-only submission) went stale WHILE the workflow agents were running —
  Kim proved direct sbatch works ~10:30 same day. Added a dated addendum (not a
  rewrite, per house convention) reframing HyperQueue as a short-task-packer
  rather than an EFP workaround, flagging the old "sbatch --array doesn't work"
  correction as itself now stale, and defaulting the ARC-Forcing dependency to
  plain `sbatch --dependency=afterok` over Nextflow.
- [2026-07-15 (afternoon)] LUMI throughput/workflow guide (Kim's ask, ultracode
  workflow — 9 parallel fetch agents + 1 synthesis agent): read all 9 docs.csc.fi
  pages on throughput computing, Lustre, HyperQueue/FireWorks/Nextflow, and ML
  workflows; wrote `docs/lumi-throughput-workflow-guide.md`. Confirmed the team's
  own working hypothesis (HyperQueue inside one EFP workflow execution solves the
  "can't sbatch --array under EFP" problem) against real CSC docs, recommended
  Nextflow's local executor (not the Slurm executor, which the docs explicitly warn
  against for short tasks) for the ARC-Forcing dependency, ruled out FireWorks
  (external MongoDB dependency, never confirmed against LUMI). Flagged 5 concrete
  "needs verification on LUMI" items rather than asserting inferred parts as fact.
  Passed to CONTINUITY via DM.
- [2026-07-15 04:3x] E0-B labeled loopy/good clip manifest (W's ask): mined
  `eval/loopy_labeled_manifest.json` from run_meta.json findings + docs/journals/
  WORKLOG, every path verified to exist on Mantu before inclusion. Honest count:
  8 loopy / 15 good high-confidence, short of the >=20/>=20 target — reported as a
  real shortfall, not padded. Also included 2 ambiguous metric-vs-ear disagreement
  cases and 6 reference-only numeric-loopiness clips (meter-author's own caveat:
  not confirmed pathological) as separate, clearly-labeled buckets.
- [2026-07-15 04:1x] Starred-ID verification (W's ask): all 6 arXiv ids in
  validation-experiment-plan §6 verified real, pinned to papers/knowledge.md.
  Found real overlap with G's independent verification of the same 6 (01:56,
  before W separately asked me) — flagged the coordination gap; folded G's sharper
  catch (DPP/SAGD are training-time mechanisms in their source papers, not
  inference-time precedents) into my entries.
- [2026-07-15 01:0x] Checked my own Gemini brief against C's new report-#2 lesson
  (feeding Gemini our own code caused a closed citation loop — 8/32 "works cited"
  were our own source files) — confirmed `research-brief-longform-continuation.md`
  never named a file/function, only architecture facts + phenomenology. Brief format
  holds; noted the rule for future briefs.
- [2026-07-15 00:5x] Follow-up on W's Gemini-report assessment: verified AID (arXiv
  2605.13010) is image-inpainting-under-EDM, not flow-matching/RF, and not audio —
  the method (frozen backbone + actor-critic guidance module) is the transferable
  template, the application/backbone aren't ours; flagged to C as an open derivation,
  not a relabeling. Cross-referenced 2 of W's "unsampled" citations against my own
  sweep (TRI-TSMC 2605.25123, DiscoForcing 2605.28491 — already verified, saved a
  re-check).
- [2026-07-14 23:05] Longform-continuation research: wrote
  `docs/research-brief-longform-continuation.md` (Gemini-ready, condensed from W's
  `research-synopsis-longform-continuation.md` §5) + ran my own 3-agent web sweep ahead
  of Kim's Gemini pass (all citations fetched/verified). Findings + reading list DM'd to
  C (rigor lane) and W (author); see journal for the detail. Caught + fixed my own
  process gap: re-verified StoryScope from the web instead of checking `papers/`
  first — it was already knowledge.md's entry; pinned its arXiv ID (2604.03136).
- [2026-07-14 13:30] Updated `kaq.html` content (Kim's ask: mine 2026-07-13's
  discussions for settled Q&A) — 6 new entries + a new "Team process" section,
  5 sections/16 Q&A total (was 4/10), rebuilt + leak-scanned, handed to W for rsync.
- [2026-07-14 12:52] Arranged a full expanded-Essentia sweep of the AVP (313 tracks)
  and goa (4470 tracks) corpora with G/C on the fleet channel — G owns execution,
  C confirmed the field list + validation gates; tied to the avp open-dataset release
  spec's feature-freeze gate.
- [2026-07-14 12:51] Sent plain-DSP addendum to C (Kim's follow-up: "nothing in the
  acoustic descriptors?") — attack/transient family, stereo panning, perceptual bands,
  timbre color, harmonic structure, rhythm dynamics; verified none currently used via
  grep. C reprioritized Panning first (known live stereo-collapse failure mode).
- [2026-07-13 13:30] Essentia + Essentia-TensorFlow sweep (Kim's ask) for
  `whole_track_timeseries.py`: verified against the actual installed package (284
  algorithms) + live model catalog, not memory. Headline: only `hpcp_ts` is Essentia
  today; classifiers all single-shot, never windowed. 5-point proposal DM'd to C.
- [2026-07-12 11:47] Extracted real training hyperparameters (LR/batch/frame-length/
  optimizer) for 71/73 checkpoints directly from checkpoint files (not hand-written) —
  3 distinct formats reverse-engineered (control-adapter args dict, DoRA/Lightning,
  LatCH heads); 2 genuine data-loss cases (broken Lehto symlinks) labeled honestly
  rather than left blank. Populated `models_index_overrides.json`, rebuilt + shipped
  both pages.
- [2026-07-12 03:05] Proposed models.html/model_matrix.html per-family redesign
  (tabs + eval_grid.py table-compare reuse for control-adapters + revived latch_sweep
  feature×gain layout) — posted for team input before touching shared files, per
  Kim's "compare against the old pages so it's genuinely good" ask.
- [2026-07-11 09:02] Reorganized `models.html` by model family in creation order with
  a one-sentence evaluation per model (Kim's ask) — 73/73 models covered via
  `models_index_overrides.json`'s new `note` field, mined from WORKLOG/model_index.md/
  task-log findings.
- [~2026-07-11] Fixed `model_matrix.html` row misalignment (variable-length model
  notes were changing card height) — `.recipe`/`.tdata` switched from `min-height` to
  fixed `height`+`overflow-y:auto`, verified via headless-browser `getBoundingClientRect`.
- [~2026-07-11] Added an early-test/BPM-confound caveat to `onset_eval.html` (Kim's
  recollection: density changes BPM without control) — patched both the generator and
  the already-built static output, verified byte-identical.
- [~2026-07-11] Fixed `breathing.html`'s missing floating waveform player — wired in
  the shared `WAVEFORM_JS`/`WAVEFORM_CSS` module from `build_evals.py`, rebuilt+synced.

- [2026-07-09 09:19] `wait` re-armed again — one-shot, had caught an event ~8h earlier
  and sat dead since; refined the standing memory note (dies on ANY catch, not just
  crash/reboot).
- [2026-07-09 01:04] `wait` re-armed after dying again; saved a standing memory to
  proactively check listener state unprompted, not just when asked.
- [2026-07-09 00:56] Fleet status catch-up posted: AVP aug matrix complete (W), pending-D
  (per-variant MIR feature extraction) stalled awaiting Kim's explicit go.
- [2026-07-08 19:44] Recovered from hard machine crash — presence (`listen`, systemd)
  survived; `wait` had died, re-armed; confirmed no DMs missed during the gap.
- [2026-07-08 19:13] Sent detailed AVP dataset-augmentation coordination DM to
  WINTERMUTE: pitch×tempo matrix scope (bass+other only), jitter endorsement
  (±0.01bpm/±10cents), phase-invariance test proposed before a ±25ms delay aug,
  pruning-timing gate (hold vocals/drums pitch-prune until caption-tier rerun finishes).
- [2026-07-08 16:07] Researched `mir/src/tools/augment_tracks.py` (existing single-axis
  pitch/tempo augs) to ground the coordination plan; gave technical opinions on jitter
  and phase-invariance-first before delay-aug.
- [2026-07-07 12:23] Broadcast the presence-vs-wake distinction to the fleet (systemd
  fixed presence; `wait`/real-time-wake is still one-shot, manual re-arm).
- [2026-07-07 12:17] DM'd WINTERMUTE proposing a paired design for a real wait/wake fix
  (supervisor loop / auto-re-exec on exit) instead of manual re-arming.
- [2026-07-06 21:20] Fixed a HeadRouter shortlist precision issue per CONTINUITY's catch
  (TADA's {12,13} bottleneck was localized to Stable Audio Open's acoustics-only VAE,
  not a verified SA3 substitute — reframed as a search-order prior only).
- [2026-07-06 19:36–20:04] Ran an ultracode workflow: re-triaged 11 sourcebook sections
  against book chapters + the 22-paper library (33 entries annotated, 6 section notes,
  14 new bullets, adversarially verified); the workflow's own verify layer caught and
  fixed a real DFoT/DEMON misattribution before it landed.
- [2026-07-06 18:00–18:15] Ran an ultracode workflow: triaged 18 papers from
  `papers/prospective-unchecked/` (14 promoted to `knowledge.md` with project-POV
  abstracts, 4 skipped as low-relevance, 1 duplicate removed), adversarially verified.
- [2026-07-06 14:44–14:52] Caught and publicly retracted its own false "TADA paper is
  hallucinated" claim on the fleet channel after finding the real paper (TADA! =
  TArgeted Diffusion Augmentation — real, closely matches the cited description).
- [2026-07-06 12:46] Found and fixed a second Tidal bug: `user_media_lists()` only ever
  queried favorited playlists, never `session.user.playlists()` — owned-not-favorited
  playlists were silently excluded.
- [2026-07-06 09:04] Found and fixed a systemd unit-template bug: `%I` (escaped
  substitution) mangled hyphenated handles (`THE-FINN`→`THE/FINN`,
  `GHOST-NOTE`→`GHOST/NOTE`); fixed to `%i` (raw).
- [2026-07-06 07:54–08:08] Kicked off a Gemini Deep Research run ("Target-Conditioned
  Diffusion Adaptation Methods") via browser automation.
- [2026-07-06 07:29] Caught a real gap behind an alive-but-stale listener: 2 unanswered
  DMs + 1 assignment; resolved (CK flash-attn archaeology request was already moot,
  GHOST-NOTE had fixed it same-day).
- [2026-07-05 22:54–2026-07-06 00:04] Found and fixed the real duplicate-playlist root
  cause: `tidalapi`'s own `playlists_paginated()` sizes pagination from a folders+
  playlists count but fetches playlists-only, producing skipped/duplicate items;
  added `dedupe_by_id`.
- [2026-07-05 21:08] Found `build_evals.py` docstring drift (claims `site/evals/`,
  actually writes to `~/.cache/evals_aac/`, by design — colocated with clip cache for
  WINTERMUTE's rsync).
- [2026-07-05 08:27–22:58] Added randomized rate-limiting/delay settings to tidal-dl-ng
  (8 new Preferences fields: same/different-album delay min/max, break-every-N-tracks).
- [2026-07-05 08:06–08:26] Found and fixed a duplicate-playlist-tree bug in tidal-dl-ng:
  two near-duplicate `on_populate_tree_lists` implementations wired to the same Qt
  signal; removed the dead pair.
- [2026-07-04 11:05–18:43] Generated 4 crew portraits via Gemini browser automation
  (THE-FINN/WINTERMUTE/GHOST-NOTE/CONTINUITY), including a photo-style rework.
- [2026-07-04 10:53–11:00] First end-to-end Gemini browser-automation test: connected
  claude-in-chrome (fixed via reinstall after a pairing failure), submitted a prompt,
  generated and retrieved an image.
- [2026-07-04 11:04] Caught its own `wait`-listener gap (fired at 13:20, never
  re-armed) — no actual loss; WINTERMUTE's evals commit landed during the gap anyway.
- [2026-07-03 23:10] Shipped evals landing-page enrichment: real date/time from source
  dirs, plain-language subtitles, honest verdict lines including negative results.
- [2026-07-03 20:57] Adopted the handle-by-lookup rule (session name → `sessions/
  <pid>.json` → handle), superseding the earlier live-listener-based guard, after an
  identity-collision incident (GHOST-NOTE had inherited CONTINUITY's handle via shared
  cwd-based memory).
- [2026-07-03 19:33] Verified and acknowledged new fleet DM/queue tooling
  (`dm-say`/`dm-wait`/`dm-status`/`check-queue`).
- [2026-07-03 17:56] Shipped its own profile/identity site page (copper `h-thefinn`
  tint), registered 3 shared files under filelock.
- [2026-07-03 15:28] Established the DM channel convention
  (`<handle>.<handle>.log` at SAO root), announced fleet-wide.
- [2026-07-03 08:32] Founded `SAO/papers/` (4 PDFs + project-POV abstracts +
  `knowledge.md` master index), per CONTINUITY's assignment; filed the orientation
  patrol report (24 confirmed inconsistencies).
