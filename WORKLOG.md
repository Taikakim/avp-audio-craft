# WORKLOG — cross-project audio pipeline

Reverse-chronological. Append an entry (newest at top) when you finish or learn
something an agent in another repo would want to know. Keep entries short; move
durable facts into `MASTER.md`. Conventions:

- **2026-08-21 (early) — WINTERMUTE: PQ ALONE is the best algorithmic proxy for Kim's ear (77.6%);
  CLAP backfilled 14%→45% and does NOT improve it (my 78.8% claim RETRACTED); the goa-corpus gap is
  TRANSCODES, not bitrate; and "more steps is worse" reverses under control into an avp/goa split.**
  Fitted a preference model on Kim's 668 real A/B votes (same-prompt/same-seed pairs, survivor-vs-survivor,
  grouped 5-fold CV with both halves of a pair in one fold). **PQ alone 77.6%. Every addition made it
  worse** — pq+ce 75.8, pq+cu 76.9, all-12-features 74.4.
  *Retraction:* pq+ce+clap scored 78.8% on the 321 pairs then available, so I ran a CLAP backfill
  (69,216 clips, 0 skipped, coverage 14%→45%) to exploit it. On the full 438 pairs it drops to **75.1%** —
  small-sample optimism, and I should have distrusted the n-difference rather than chasing it.
  **corr(PQ, CLAP) = +0.597**: CLAP is NOT "the axis independent of production quality" I called it.
  What the backfill DID buy: CLAP reproduces the PQ parameter ordering almost exactly (T 512>4096>1024>2048>256;
  rank 256>128>16>64; alpha 45 top / 64 bottom; aug10>0; lr 5e-5≈1e-4>2e-4>>6e-4) — two meters agreeing is
  real corroboration. Plus one dissociation: **goa ties avp on prompt adherence (CLAP z −0.008 vs −0.011)
  while losing on quality (PQ z +0.081 vs −0.109) → goa's deficit is FIDELITY, not conditioning.**
  **Parameter sweep, 67,131 scored cells / 237 runs, failure-rate and quality-given-survival kept apart.**
  Survives control: corpus (avp 7.27 vs goa 7.08), adapter scale (α45@r128 = PQ 7.581 at 1.2% degraded vs
  7.256/7.4% at α=rank=128; rank 64 and α64 are the WORST buckets, below rank 16), frames_T (512 & 4096 good,
  2048 & 256 bad — T256 is the worst length measured). Precision and optimizer matter as **reliability, not
  quality**, and only on goa: bf16 fails 13.9% vs fp32 5.8% on goa but *less* than fp32 on avp (3.7 vs 4.5);
  AdamW's 18% failure is goa-only. Does NOT survive: **lr** (p=0.7 at run level), **batch** (0.1 PQ spread
  within one corpus), **aug** (6 run dirs = 3 distinct configs; α45/r256/batch16/lr7e-5 are largely ONE avp
  family seen under five column headings).
  **The reversal worth propagating:** pooled, more steps predicts worse output at every frame length
  (ρ −0.15…−0.25, crushing p). *Within* runs it vanishes — mean ρ −0.003, p=0.31. It is a between-run
  confound. Split by corpus: **avp runs IMPROVE with training (+0.133, only 29% declining), goa runs
  DEGRADE (−0.087, 76% declining), p=4.5e-5** → the two corpora want OPPOSITE checkpoint policies
  (take goa early, let avp run long). Fits the ep7 elbow and the post-ep59 collapse Kim hears.
  **Standing methodological rule:** 810 checkpoint rows are ~30 epochs of ~265 runs — cluster at RUN level
  or do not quote p-values. Every parameter table quoted lately, mine included, was pseudo-replicated.
  **A near-miss worth recording:** a 12-feature fit put a bootstrap-stable −2.6 weight on `zcr`, with a
  plausible physical story. Stratifying directly on matched PQ killed it (lower-zcr wins 52.7%, p=0.60) and
  CV agreed (pq+zcr < pq). Collinearity inflating a coefficient — that is the shape of a false finding.
  **goa corpus quality (new).** Measured both corpora the same way (spectral cutoff = real bandwidth;
  header bitrate lies). Old goa `Goa_Separated` (full_mix only, 3,978): **75.9% near-lossless, mean 20.68 kHz**.
  Archive `goa_archive_extracted` (14,838 after dedup): **27.7%, 19.06 kHz**. Quality-matched list at
  ≥20.0 kHz = **4,111 files** (`mir/stats/goa_big_quality_matched/`), or **3,147** excluding the 2,669 that
  already overlap old goa (`..._noverlap/`). Caveat: the MEAN matches, the SHAPE does not — old goa is bimodal
  (mostly excellent + a lossy tail), the filtered set is bunched just above threshold, so its median is
  *lower* (20.68 vs 21.29). **Worst-100 forensics (Kim's question, "mp3 alone should not do this" — he is
  right): 76/100 declare ≥192 kbps and 14 declare ≥256, yet content stops at 4.7–11.9 kHz.** A clean 192k
  encode reaches ~18–19 kHz; 128k reaches ~16. These are transcodes / analog rips / stream captures
  re-encoded at a respectable bitrate — the header records the last encode, not the damage. Spread over
  90 distinct albums, so not one bad batch. List + playlist: `mir/stats/goa_big_worst100/`.
  **Tools/pages.** `mir/src/tools/goa_archive_quality.py --only-name` (measure `full_mix`, NOT the separated
  stems — without it you get 5× the work and a tier distribution corrupted by lossy stem renders); new
  `mir/src/tools/goa_archive_match_quality.py`. `eval/dora_table` gains `effective_batch`, `caption_probs`
  and a **`params_source`** column — **531 of 916 rows had name-INFERRED rather than sbatch-parsed params and
  nothing said so**; dataset labels normalised (`latents_avp`/`avp` and `latents_sa3`/`goa` were splitting
  every dataset-grouped view in two); `build_model_index.py` now merges the extracted recipe into models.html
  (the checkpoint-derived ones literally said "lr not recorded in checkpoint"). suomisoundi `ARMSET=alpha`
  ready to submit (r128, T512, α45 vs α128, shared lr — commit 708e14b).
  **Two process traps that cost me time.** (1) `run_in_background` is being reaped almost immediately in this
  session — anything long-lived needs `setsid`+`nohup` (already the rule for eval servers; it now applies to
  plain waiters too). (2) A job's progress counter goes to **stdout, which Python block-buffers when
  redirected to a file**, while its warnings go to unbuffered **stderr** — so a healthy job shows a frozen
  counter and looks hung. I nearly killed a 2-hour run twice. Count the stderr side, or `-u`.
  Report: the full write-up is an artifact (cell-ranking + parameter analysis, every claim marked for whether
  it survives control).

- **2026-08-18 (eve) — CONTINUITY: weight-space forensics on the degraded AdamW arms + a step-resolution
  trajectory recorder; the broken runs are not converging, they are diffusing.** Kim asked for the
  Base→degraded delta, outlier weights, a repaired model, soups, and — sharpening it himself — deviant
  EIGENDIRECTIONS rather than scalars. Built `eval/task_vector_gram.py` / `task_vector_spike.py` /
  `spectral_repair_lora.py` / `soup_ladder.py` (ARCHITECTURE §B) and ran the goa set: 4 AdamW-sweep
  terminals vs 19 healthy ckpts (bf16cmp/fp32cmp ladders + T4096 fp32). **(1)** bad-good cosine of the
  DoRA-exact ΔW_eff is 0.03–0.12 while the healthy runs' cos-to-consensus climbs to 0.72 — the sweep did
  not learn what every healthy run shares. **(2)** bad arms carry 20–30 % of every matrix's delta energy in
  ONE singular direction (eff-rank ~56/128); every healthy run at every epoch/config is flat (2.1 %,
  ~118/128). **(3)** that direction is the SAME across the four bad arms (|cos| 0.25 vs chance 0.026,
  strongest in `ff_in` 0.46 / `out` 0.33), not a global direction, not a channel outlier (PR ~520):
  a systematic component, strongest at the smallest LR — it does not scale with learning. **Reframing
  caveat:** the healthy twins were trained with `--optimizer fusion` (NS5 orthogonalisation flattens
  spectra by construction), the sweep with AdamW; optimizer and batch are confounded in the archive.
  **(4) Step resolution (Kim: "save every step; there's a compressed way to store movement" → CountSketch
  callback `stable-audio-3/scripts/trajectory_sketch.py`, reader `eval/trajectory_sketch_analyze.py`).**
  Local sanity16-recipe LoRA r16 at bs1, 4482 steps: update autocorrelation = **0.9^τ to 3 digits, then
  exactly 0** (Adam momentum on pure noise); gradient window-SNR = **1/w to 3 digits up to w=1024** (the
  repeatable gradient component is < 0.1 % of its energy); path efficiency above 1/√w by exactly the
  AR(1) factor — **zero drift, loss flat** — yet B·A top-1 fraction climbs 0.33→0.56. Mechanism that fits
  all of it: per-step gradients ≈ δ_t x̄ᵀ (dominated by the mean-activation direction), so `dB = δ_t (A x̄)ᵀ`
  accumulates rank-1 with a data-fixed input direction (shared across arms) and a random-walking output
  direction (never settles); Adam preserves it, NS5 destroys it. **Working hypothesis, two decisive arms
  running (accum8, Fusion-bs1) + LUMI job `lumi/sbatch/traj_sketch_arms.sbatch`:** at these batch sizes
  nothing converges by drift; a checkpoint is listenable when it is AVERAGED (SF in Fusion, EMA on the
  melody head, Kim's soups) and AdamW at constant LR without averaging hands you a random point of the
  walk. Probe ckpts (remove/keep top-1, k3, magnitude reset) written + CPU renders queued
  (`lumi_runs/analysis/task_vector_gram_goa_2026-08-18/`). Also: **the D3 melody head generalises**
  (first held-out-validated LatCH training, split BY SOURCE TRACK: lead 0.245→0.204, bass 0.191→0.152 on
  401 unseen tracks; EMA monotone) — and every existing `*_best.pt` LatCH head was train-loss-selected.
  **Box note:** `/tmp/suomisoundi_ts_full_extraction.log` is 27 GB in tmpfs (RAM) — whoever owns it, it is
  why the box has 6 GB free.
- **2026-08-18 — CONTINUITY: the goa collapse had a THIRD cause — the corpus was captioned with NO
  genre hint at all.** W scanned a tier nobody had questioned: goa's Music Flamingo prose mentions
  goa/psy in **1.2%** of tracks and techno/industrial/house in 70.8%. Root cause is duller and worse
  than "MF is unreliable" — `goa_caption_task.py` writes a **`genre_hint`** field into every caption
  JSON, and all 400 sampled goa files record **`None`**. The mechanism exists (`--genre-hint` /
  `GENRE_HINT`, read from `GENRE_HINT_FILE`) and **defaults to empty**. Suomisoundi, same script,
  recorded a hint and scores **97.4%**. Same model, same code path, one variable. There is also a
  richer per-track path in mir — `pipeline.py:154 _interpolate_genres()`, weighted Essentia genre
  distribution + ID3 metadata — that `lumi/goa_caption_task.py` never calls, so the genre info sat
  in the `.INFO`s the whole time and never reached the captioner. **Checking "was this corpus
  hinted?" is a one-line read of any caption JSON.** Affected runs killed; re-caption 21335408 at
  89.1% goa (and still correctly calling genuinely non-goa tracks ambient — the hint anchors without
  overriding). **Blast radius for anyone using a goa baseline:** `fullft_mixed_avp_goa_t4096`,
  `subloss_goa_k20_fullft`, `fullft_mem_probe` all pass `0,0,1` (100% of the mislabelled tier);
  `fullft_bigset` used `0.3,0.4,0.3`; the `efp_*`/`subspace_loss_*`/`x0equiv_*` families default to
  `0.6,0.3,0.1` against `goa_longform`. Their checkpoints aren't worthless, but any conclusion about
  prompt-following or genre adherence drawn from them has this underneath it.
  **GROUNDING ≠ CORRECTNESS (my own tool's blind spot).** `eval/audit_caption_sidecar.py` certified
  the contaminated sidecar at 19.24× — it measures whether a tag reflects *its own track's* prose,
  which is orthogonal to whether that prose is *true*; a grounded tag faithfully inherits a wrong
  genre. Both checks now run in one command (`--expect-genre`). The ranking it prints is the durable
  lesson — **a tier's provenance predicts its correctness better than its polish**: t1 (effnet
  classifier *on the audio*) 70.4% goa > t2 (granite, revising MF) 48.0% > t3 (MF prose, the richest
  text) 1.2%.
  **Also:** weight-decay drone diagnosis CONFIRMED not confounded (precision_ladder runs one GPU per
  arm with `SLURM_JOB_NAME=bash`, so the DDP bug cannot apply, and it droned) and the fix verified —
  wd-fixed full-FT at ep7 measures z0 std **1.134**, 0/256 channels >2.0, vs the runaway's 5.6 and
  166/256. Two-arm 4+4 DDP verified (`LOCAL_RANK` 0–3 twice). EDM2 forced weight norm implemented
  (`--forced-weight-norm`, 12 tests) — distinct from `--hyperball`. Per-source `--caption_probs`
  (semicolon syntax, 10 tests). AVP granite coverage 284→2353/2394 (augmented crops key on
  `"<track>/<variant>"`, so ~88% was training on t1 boilerplate). Model-identity IDs (`M-XXXXXX`,
  assign-once) — 75 of 297 board labels are synonyms; 7 run dirs answer to two names via symlinks.
  **⚠️ NEVER merge drive trees with a bare `rsync -a`:** its size+mtime check overwrote a good 666 MB
  checkpoint with a truncated 25.6 MB fragment (mtime 1970, unloadable) because I treated a filename
  match as a content match. Use `--checksum --backup-dir`. Recoverable from LUMI; the scan
  (`Misc/drive_rebalance_20260817.sh scan`) found it's the only corrupt file on either drive — and
  its size heuristic must be **sibling-relative**, since an absolute "<100 MB is truncated" rule gave
  83 false positives on legitimately-small rank-16 adapters.
  **Recurring shape across three failures tonight: a DERIVATIVE DOES NOT KNOW ITS SOURCE CHANGED.**
  The sidecar served Aug-4 captions after granite was regenerated; the dora table read a stale
  aggregate; an eval read a stale manifest. Cheap general fix: print input mtimes at build time —
  `build_goa_archive_sidecar.py` now does, and immediately surfaced "T3 2026-08-04, T2 2026-08-17".

- **2026-07-30 — THE-FINN: papers/ index sprint — 13 backlogged PDFs deep-read + indexed**
  (Kim: "keep working on paper reports while away"). Cleared most of the abstract-less
  backlog into `papers/knowledge.md` (rows + `arxiv-<id>.md` abstracts, project-POV). Key
  portable findings for the fleet: **(a)** `DiffRhythm2` **block flow matching** (2510.22950)
  = the most graftable anti-loop-collapse mechanism — injects causal dependency into RF via
  only an attention-mask + training change, no change to SAME/flow objective; shares our
  SA2-VAE lineage (they run 5 Hz for 210s, direct rate/length/fidelity evidence). **(b)**
  `SongBloom` (2506.07634): a learned coarse AR "sketch" is the coherence prior (ablation
  PER 9→109) — a learned replacement for the hand-written prompt arc. **(c)** `InfiniteAudio`
  FIFO rolling buffer (2506.03020) + `SaFa` latent-swap (2502.05130) = two training-free
  seamless-window schemes vs our reset-the-clock seams. **(d)** `Low-Resource Guidance`
  (2603.04366) is the **origin of "LatCH"** (Stability/SAO, Zach Evans et al.) — but there
  LatCH = a *guidance readout head*, NOT our training-time conditioning adapter: **terminology
  to reconcile before porting claims** (C, worth your eye). **(e)** `AxBench` (2501.17148) +
  `NA-RFM` (2602.11395) both find **difference-of-means is beatable** (RFM/ReFT-r1) — an
  upgrade path for our DoM mood-steering; NA-RFM's activation-norm-proportional edit + s-sweep
  is exactly the over-steer regime our disintegration gate bounds. **(f)** `SteeringDiffusion`
  (2605.01653) independently converges with our {12,13} mid-band + low-dim-bottleneck thesis.
  Full per-paper "what remains ours" in each abstract. Remaining backlog: 2 pure-video papers
  (UltraViCo, LoL) + DC-SAE deep-read from Kim's PDF + 3 no-PDF candidates (PID/RCFG++/RT-SAEs).

- **2026-07-30 — GHOST-NOTE + THE-FINN: task #79 (fp32cmp/bf16cmp T4096 native-length
  metering, Kim's piece parked since 2026-07-20) done, plus a real data-quality bug
  found and fixed.** Native cells needed no GPU lock at all: Audiobox correctly
  excludes clips >60s by design (WavLM/meaningfulness limits, not a gap); CLAP runs
  fine CPU-only. Found 54 clips (my original 46 + THE-FINN's +8 longctx_t2048_r128)
  had a stale-DB truncated-duration read (cached dur=120 from what looks like a
  mid-write-race score, real files 190-380s) — fixed via delete+re-score, DSP now
  correct. Separately found + removed **28 genuinely-broken orphan clips** (really
  are 120s renders): 8 traced to an already-quarantined source dir
  (`model_matrix_BROKEN_native_120s/`) that leaked into scoring despite the
  quarantine, 20 with unclear/older provenance (dora128_everything_8ep_lr1x_ep7_sweep
  T4096_*, newcap8_transitions) — never served on any board (manifest-level
  quarantine held, confirmed by THE-FINN), so this was a DB/orphan-file cleanup only,
  not a live-board fix. Ran CLAP --include-native across all 1426 native cells
  board-wide (not just fp32cmp) as a side benefit. Both boards rebuilt off the fresh
  aggregate. Remaining, NOT done (parked for whoever owns model_matrix_gen.py /
  scoring scope): the ingestion gap that let the quarantined-source clips get scored
  at all, and whether to physically remove the 28 orphan .m4a from disk (Kim/THE-FINN
  call, not launched unprompted).

- **2026-07-29 — GHOST-NOTE + WINTERMUTE: adamw_bf16_sweep fully landed (task #76,
  CONTINUITY's 2026-07-24 ask).** 8 arms (goa/avp x t512 x {bs1_lr1e4, bs4_lr1e4/2e4/5e5},
  ep9 terminal) registered + rendered (1296 cells, standard grid + extra prompts), then
  metered end-to-end (DSP via clip_metrics.py, Audiobox ce/pq/cu/pc, CLAP prompt-adherence
  via WINTERMUTE's catch-up pass — coordinated live over DM, no duplicate GPU work). Both
  master boards (dora_table.html, model_matrix.html) rebuilt off the same
  clap_dora_aggregate.csv so adamw sits alongside its matched fp32frames Fusion siblings —
  the A/B Kim/CONTINUITY wanted is the shared-board comparison, not a separate page.
  Deferred, flagged rather than silently dropped: mood_drift (needs a separate
  mood_timeseries.py summary-CSV step CONTINUITY didn't ask for explicitly) and the
  disintegration gate (designed for control-head steering runs; applicability to a plain
  optimizer-comparison fine-tune is ambiguous, not run without a call on that).

- **2026-07-29 — GHOST-NOTE: model_matrix render-to-staging sync gap — 11,285 rendered
  clips existed only on the Mantu render drive, never copied to the served
  `~/.cache/evals_aac/model_matrix/` staging dir, so they were silently unplayable on
  every board despite showing up as "covered" in `manifest.jsonl`.** `model_matrix_gen.py`'s
  `transcode()` only ever writes the `.m4a` into `RENDER_DIR` (Mantu) — there is no
  built-in copy into `STAGING` (the `.cache/evals_aac` tree the pages actually serve
  from; confirmed via inode check that `~/evals_aac/model_matrix` and
  `~/.cache/evals_aac/model_matrix` ARE the same directory, but neither is the same
  filesystem as Mantu). Caught only because `clip_metrics.py`'s CPU pass reported
  "0 to do" against a glob of the staging dir right after a render I'd just watched
  finish — the manifest said the cells existed, the disk said otherwise. **This means
  every coverage check this session that trusted `manifest.jsonl` counts alone (tasks
  #66/#68/#70/#71/#72/#73/#76 and likely earlier fleet renders too) verified render+
  manifest completion but NOT actual served playability** — same class of gap as the
  2026-07-21 "chain's success line is a claim, not evidence" lesson, one level deeper
  (the manifest write itself isn't evidence the clip is reachable). Fixed this session's
  gap via `rsync --files-from` (11,285 files, ~62k total now in staging, verified 0
  remaining via `comm`). **No dedicated sync tool exists for the general case** —
  `eval/ingest_native_cells.py` only handles the LUMI-native-cell reroute path. Until a
  render pipeline fix lands (either `transcode()` writes both locations, or a standing
  sync step gets added to every render chain), **any local `model_matrix_gen.py` render
  needs an explicit staging-sync step before its clips are actually listenable** — flagged
  to the fleet; whoever owns `build_model_matrix.py`/the renderer should decide the fix.

- **2026-07-29 — GHOST-NOTE: fleet-comms listener bug found + fixed (`agent_dialogue.py
  wait` under `run_in_background` was silently killed by the harness's 120s default
  command timeout, not a real wake) — three of CONTINUITY's DMs from 2026-07-24 had sat
  unanswered for 5 days as a result.** Fix: wrap `wait` in a re-arming loop, watch it with
  a `persistent: true` Monitor (no timeout ceiling) instead of a single backgrounded call.
  Catch-up on the missed DMs: (1) **xft_distillation.html** built
  (`~/evals_aac/xft_distillation.html`) reframing task #71's 60-adapter SVD extraction
  per her near-full-rank finding — regenerated her SV-spectrum numbers independently via
  new `eval/svd_energy_spectrum.py` (reproduces within rounding: median r90 mlp/proj 1112
  vs her 1110, attn_qkv 937 vs 937, whole-model r1024 energy 89.45% vs 89.5%), presents
  the energy-capture + per-class r90 tables + a 3-pair matched-rank A/B (xft-extracted
  glitch vs trained-DoRA coherent) instead of the misleading "60 usable adapters" framing.
  (2) alpha 45/128 stereo/punch eval columns — appears already covered by WINTERMUTE's
  2026-07-27 winning-fp32 metering pass. (3) **adamw_bf16_sweep** (8 ep9 checkpoints,
  job 20190736) was fully unregistered — registered in the bracket manifest + standard-
  grid + extra-prompts render launched (task #76, in progress).

- **2026-07-28 — GHOST-NOTE: headb_bracket (CONTINUITY's Head B melody-conditioning
  FiLM adapter) eval page live, `~/evals_aac/headb_bracket.html`.** Kim's rsync landed
  the bracket sweep (8 checkpoints x cfg{1,7,16} x gain{1.0,1.5}, 48 cells, LUMI-
  rendered per run_meta.json) at the canonical LUMI-pull target; renders existed but
  the analyze phase (muscriptor transcription + adoption-vs-null-floor + disintegration
  gate, per CONTINUITY's `control/sa3_control/headb_bracket_eval.sh` design) hadn't run.
  Ran it (crash-checked first — the design doc flags a local-inference risk from an
  earlier training crash; transcription-only turned out fine, ~65min GPU + CPU analyze,
  all 48/48 cells scored). Built `Misc/build_headb_bracket_page.py` (same-playhead
  template, master per-cell table, three-audience explainer). **Result: adoption is
  weak** — only 14/48 cells clear 1.5x the null floor (best cell 0.123 adopt vs 0.044
  null; most near 0), but **100% gate-clean** (no disintegration/buzz-faking anywhere in
  the bracket) — so the adapter isn't yet reliably steering toward the supplied motif,
  but it also isn't cheating the metric with noise. Matches the spec's own framing (this
  is a *direction-check* pilot, not the >=60% production bar). Flagged to CONTINUITY
  (her lane) via DM before touching it; she may already have follow-up planned.

- **2026-07-30 — GHOST-NOTE: task #69 closed — the disintegration-gate usable-gain-
  ceiling was already wired into `latch_sa3_matrix.html` (commit 78f4142) but its two
  dependencies, `eval/control_head_disintegration_eval.py` (the mandatory per-head
  screen, Kim directive 2026-07-20) and its output `control_head_disintegration.json`,
  were never committed** — the feature worked locally but would silently no-op (empty
  gate, ceiling column blank) on any other checkout. Committed both; verified the
  rebuilt page carries real per-head ceiling values for all 14 SA3 LatCH heads (e.g.
  `hardness` p0<=128/p1<=512, most energy/spectral heads <=8192). Data unchanged since
  2026-07-21 (underlying clip family not re-rendered) — no re-run needed. Note for
  whoever revisits per-head verdicts: the page's separate "steers/weak/dead" heuristic
  still tags beat_activation/downbeat_activation as "steers" even though MASTER SS5
  documents them as genuinely dead (confirmed by two independent sweeps) — the
  ceiling and the verdict are different axes (a dead head can have a high ceiling
  simply because it never disintegrates), out of scope for this task but worth a
  follow-up if anyone's touching that heuristic.

- **2026-07-25 — GHOST-NOTE: SVD-extracted LoRA/DoRA adapters (60) + fp32frames (16
  arms) + winning-campaign ep10/ep15 fully rendered & verified.** Built
  `eval/extract_svd_adapters.py` (truncated SVD of `deltaW=W_fullft-W_base`,
  sign-canonicalized, DoRA variant stores the target's own row-norm as `magnitude`) to
  turn full-finetune checkpoints back into LoRA/DoRA adapters at ranks {16,64,128} ×
  {lora,dora} × {avp,goa} = 60 adapters; ran the full batch (100% coverage each,
  verified via real `model.load_lora()` + `generate()`), then rendered a one-prompt
  preview across all 60 before the full grid (Kim: "maybe just do one first for
  each"), then the full grid — 9621 cells, 60/60 labels covered (a 59/60
  coverage-check "failure" mid-session turned out to be a trailing-newline bug in my
  own verification script, not a real gap — re-verified clean). Also finished
  registering + rendering all 16 `fp32frames_{avp,goa}_t{512,1024,2048,4096}_bs{1,4}_lr1e4`
  arms (was completely unregistered/unevaluated) and the winning fp32-campaign's
  ep10/ep15 checkpoints (8 labels × 3 epoch tags, standard grid + pt-medium native
  cells) — all confirmed via `manifest.jsonl` cell counts after the box restarted mid-
  session and killed the live background watchers (resumable design meant no actual
  work was lost, just the in-flight process). See `profiles/ghost-note.journal.md`
  2026-07-25 for the full arc incl. the same-handle GPU-mutex collision bug (fixed:
  each concurrent chain needs its own `--handle`, filelock.py treats same-handle locks
  as already-yours).

- **2026-07-20 — the overnight LUMI checkpoint prune breaks bracket picks (any tool
  reading `eval/rarity_bracket_manifest.json` picks, not just model_matrix_gen.py)**:
  `lumi/prune_optimizer_states.py` (Kim 2026-07-19: "prune the optimiser states from
  every checkpoint except the last") deletes each non-final `.ckpt` and replaces it
  with a slim `<name>.weights.ckpt` (same `state_dict`/`lora_config`/`epoch` keys, just
  missing `optimizer_states` — loads identically through the existing loaders, verified
  against `load_lora_checkpoint()`/the fullft loader, both only ever read `state_dict`).
  It ran overnight across most arms in the original full-pull LUMI location and silently
  broke 62 bracket picks across 23 arms — caught because an in-flight render started
  logging `[skip-missing]`. Fixed by redirecting the picks to their `.weights.ckpt`
  sibling where one exists (60 of 62); the other 2 were unrelated pre-existing wrong
  registrations (anticipated epochs that never landed), corrected to match reality.
  **If you maintain a tool that resolves checkpoints against this manifest's `picks`
  (or glob-scans a run dir directly) and it silently skips/undercounts after this date,
  check for a `.weights.ckpt` sibling before assuming the checkpoint is actually gone.**
  Commit 6d31ba9 (GHOST-NOTE). The `witness` field (informational only, unconsumed by
  any tooling) has 1 known-stale entry, left as-is.

- **2026-07-13 — ARC-Forcing rollout dataset builder (task #46 part 1)**: new
  `eval/arc_rollout_dataset.py` — exposure-bias training data (T=1024 windows from
  `latents_sa3`; first `--tctx` 512 frames re-rendered through the model as latent-domain
  SDEdit at `--rollout-nl` 0.5 via the REUSED `longform.SDEditReanchor` path (no
  decode->re-encode; `generate()` has no latent-init kwarg, `sample_diffusion(init_data=...)`
  does). npz contract: `context_latent` fp16 (256,Tctx) = drifted render, `target_latent`
  fp16 (256,1024) = TRUE window, `mask` uint8 (1024,) 1=clamped context, + prompt/meta +
  manifest.json. Resumable, `--limit`, `--dry-run` (CPU, fabricated render) validated
  end-to-end. GPU runs are LUMI-lane. Note: `latents_sa3` npy are (256,4096), NOT
  (1,256,4096) as older notes claim (builder handles both).

```
## YYYY-MM-DD — <who/model> — <one-line title>
- bullet of what ran / landed / broke
- paths, commands, results worth reusing
```

## 2026-07-15 — WINTERMUTE — longform validation plan: 6 papers read full-text; AID ports to RF directly
- Kim delegation (via C): read FK-Flow 2509.01543, AID 2605.13010, LoL 2601.16914, TRI-TSMC
  2605.25123, LatCH 2603.04366, RMR 2605.00435 in full. Deciders: **AID's relaxed dynamics =
  deterministic drift + policy-mean; the Gaussian variance 2λ/(βd) is policy-side, fixed, never
  touches a backbone diffusion coefficient → the bridge is backbone-agnostic and SA3's rectified
  flow qualifies AS-IS** (C's Q1 closed; no stochastic-interpolant detour). FK-Flow: stochasticity
  injection MANDATORY (deterministic ODE + resampling collapses particle diversity; Theorem-1 SDE
  with velocity-recovered score); intermediate reward at the Euler one-shot endpoint = our z0_hat;
  paper ops 32 particles / resample every 3 steps / harmonic-sum schedule. LatCH paper vs our
  latch_guided: TFG knobs all ported (rho/mu/gamma/n_iter verified in signature); NOT ported =
  LatCH-B trajectory-trained heads (their best variant everywhere; converges with AID's rollout
  training) + sparsity-aware loss — their sparse-heads-fail finding mirrors our dead-head sweep.
  LoL diagnostic: C(Δ)=|1/K Σ e^{jωΔ}| is pure rotary-config math (no GPU for part A) + an
  attention-hook part; collapse sits at C's local maxima. RMR corr-dim: O(t) online update,
  catches implicit collapse content meters miss.
- Plan: `docs/ai-research/validation-experiment-plan-2026-07-15.md` — E0 meter validation +
  corpus quantile bands (CPU, start now), E1 band-hinge recurrence guide in latch_guided,
  E2 FK-SMC (weights-only, ESS-logged, TRI-TSMC escalation), E3 LoL phase-alignment (A analytic /
  B hooks), E4 SaFa reference-swap, E5 AID amortization spec. LUMI items queue behind Kim's
  fp32/T=4096 campaign + smoke gate.
- Also: comment-loop close-out — G's 4 riffer pages shipped to the board, CORS allowlist live on
  comment.php (Pages origin can now GET/POST), 2 widget bugs fixed: relative EP (404 on Pages
  regardless of CORS) and the boot selector missing `.cmts[data-page]` (would have silently
  killed all four page-level boxes on every origin). Verified live end-to-end.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — timbral extraction: m4a decode bug + a pkill lesson

- Two real incidents chasing what first looked like ONE memory-pressure problem.
  (1) WINTERMUTE's co-resident training OOM'd twice; my "downshift jobs 12→8" fix
  used `pkill -f "extract_timbral_hdb.py --mode tracks"`, which only matches the
  orchestrator's own argv — its already-spawned `--single` subprocess.run() children
  survive (different cmdline), so old workers stacked under each new batch. Found
  15-20 workers running simultaneously, RAM at 73GB used, swap FULLY exhausted
  (511/511Mi). Fixed by killing on the script's basename alone (`pkill -f
  extract_timbral_hdb.py`, catches orchestrator + children); saved as a memory
  (`pkill-orphaned-subprocess-children`) since it's the same MASTER §5
  kill-the-process-group lesson in a new spot and will recur on any future
  subprocess.run()-fanout batch script here.
  (2) Separately, after the RAM was clean, extraction items STILL failed 100% —
  turned out unrelated: `libsndfile` (soundfile's decoder, which `timbral_models`
  uses) cannot open m4a/AAC containers at all ("Format not recognised"), 100%
  reproducible regardless of system load. 96/4470 goa tracks are m4a-sourced
  (mp3/ogg/aiff/flac/wav all decode fine — only m4a is broken); the failures just
  happened to cluster in corpus-sort-order near the OOM incident, making the two
  problems LOOK like one. Fixed `extract_timbral_hdb.py`'s `process_track()`:
  m4a sources get pre-transcoded to a `/dev/shm` wav via ffmpeg before analysis.
  Verified on the exact failing track (was a hard fail, now succeeds with real
  values). Corrected the record with WINTERMUTE rather than let the wrong
  root-cause attribution stand.
- Relaunched (jobs=8, healthy memory, no zombies) — whole-track pass continuing.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — spec §14 explainer retrofit (breathing.html, rarity.html)

- Kim's team directive: the three-audience standard (eval tool / technical resource /
  plain-language learning resource) is now a hard requirement, opportunistic retrofit
  on next touch. Added the "What this tests / how to read it" findings-box to the two
  highest-visibility pages I own (Kim's actively using breathing.html tonight; rarity.html
  just landed real scores) — a2a noise-scheduling + the loop-attractor problem for
  breathing.html, MERT kNN rarity percentile + what a positive delta means for
  rarity.html. mp.html's cross-model section and dora_results.html (already marked
  superseded) left for a later opportunistic touch, not urgent right now.
- Leak-scan clean, DOM-harnesses re-verified on both after the rebuild. Handed to
  WINTERMUTE.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — memo_ckpt_a2a_test upgraded to a proper nl x variant table

- CONTINUITY's memo a2a high-nl re-run landed (6 new clips: nl 0.65 + 0.80 alongside
  the original 0.50, across ep63_cfg2/ep63_cfg6/ep7_cfg2 — Kim's ask). The page was
  a generic 3-clip `write_folder()` grid; upgraded to a dedicated 3x3 same-playhead
  table (`write_memo_a2a_folder`, new writer in `build_evals.py`, wired into the
  main routing chain by exact name match like the other one-off writers).
- First page built under Kim's new eval-tables spec §14 (three audiences: tool /
  technical resource / plain-language learning resource) — added the "What this
  tests" explainer block (the Underfit-memo prediction: an overtrained/memorized
  checkpoint should be the STRONGER a2a tool at low CFG, since its absorbed style
  prior dominates the prompt) above the table, per WINTERMUTE's ship-time gate.
- Landing-category gotcha: this dir is deliberately named `memo_ckpt_a2a_test` (NOT
  `a2a_*`-prefixed) to avoid colliding with `A2A_LADDER_RE`'s sibling-folder
  auto-grouping (a different mechanism, caught earlier this session) — which meant
  it fell through today's new `LANDING_CATEGORIES` "a2a & transitions" regex too.
  Broadened that pattern to also match `_a2a_` as a substring (checked for false
  positives — clean), not just a name-prefix.
- Leak-scan clean (both the page and the full index — same 2 pre-existing known
  hits, nothing new). Handed to WINTERMUTE.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — evals landing page: categorized (kills the "wall of links")

- Kim's ask (via CONTINUITY's design, routed here since this file's actively edited
  today): the flat "All runs, newest first" list (56 items) read as an undifferentiated
  wall of links. Replaced it AND the separate Control-runs/Renders kind-split section
  (both cruder groupings of the same 56 items — 3 overlapping listings wasn't helping)
  with one categorized view: `LANDING_CATEGORIES` (name-prefix/regex -> category,
  first-match-wins, most-specific patterns checked before the broad control/FiLM
  catch-all), newest-first WITHIN each category, undated fallback "other".
- Folded in WINTERMUTE's same-session §14 addition to the eval-tables spec (three
  audiences: tool / technical resource / plain-language learning resource) for the
  landing page's slice of that gap: each category now also gets a one-line plain-
  English tagline under its header (what DoRA/avp, a2a, LatCH, rarity, long-form,
  control/FiLM actually mean). Mid-air overlap avoided — W was about to add the same
  taglines, flagged in time, W stood down (point 4 in their ack), full page-level
  pedagogical blocks stay opportunistic-retrofit per W's plan (their layer_map page
  is the prototype shape to reuse).
- Leak-scan: 2 pre-existing hits (same known `dora128_everything_8ep_lr1x_ep7_sweep`/
  `_steps_diag` href names WINTERMUTE already confirmed zero live exposure on,
  local-cache-only, not introduced by this change). Handed to WINTERMUTE.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — mobile popup-offset bug fixed site-wide

- Kim's report: the waveform popup player renders offset off-screen on phone
  (flagged on `dora128_everything_8ep_lr1x_ep7_sweep`). Root cause: `html`/`body`
  had no `overflow-x` constraint anywhere on the site — if ANY content on a page
  is wider than the viewport, mobile browsers expand the layout viewport to fit
  it, and the popup's `position:fixed;left:50%` centering then centers against
  that expanded width instead of the visible screen, so it appears shifted off
  to the side. Fix: `overflow-x:hidden` on `html`+`body` everywhere (`max-width:
  100vw` on body too) — the general defensive fix for this whole bug class, not
  just the one flagged page.
- Applied to: `Misc/build_evals.py`'s shared `CSS` (covers all 43+ build_evals.py-
  generated pages via the shared `evals.css`, including the flagged one) and the
  4 standalone page generators (`build_breathing_page.py`, `build_rarity_page.py`,
  `~/build_dora_results_page.py`). Also wrapped every wide table (`rarity.html`'s
  6-col x 150-row tables; `dora_results.html`'s `metricsTable`/`playGrid`, up to
  15 columns) in a `.tblwrap{overflow-x:auto}` container — clipping the body
  doesn't help if a table itself was the thing overflowing; wide content needs
  its own scroll container to stay reachable, not just get clipped away.
- Leak-scan clean, DOM-harnesses re-verified (breathing/rarity) after rebuild.
  Ready for the next publish pass.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — rarity.html: column reorg (task #33)

- Kim's tasking (via WINTERMUTE): rebuild `rarity_gen_set` (450 clips: 3 models
  {base, newstack, evr1x} x 150 stratified prompts {50 common/mid/rare}) as a
  COLUMN layout — one row per prompt, one column per model, plus delta-to-base
  columns for CONTINUITY's rarity-lite score (not landed yet — scoring ownership
  went to CONTINUITY per WINTERMUTE's call this session).
- Ground truth for grouping: `clip_index.json` in the Mantu source dir (clip-stem
  -> {prompt, band, seed, source}) — verified all 3 models share the SAME prompt
  text per (band, promptid) group (150 groups x 3, each model with its own random
  seed) before building the row structure, rather than assuming the filename's
  numeric promptid was directly comparable. New generator `Misc/build_rarity_page.py`.
  Delta columns show "pending" until a `rarity_scores.json` (documented convention:
  `{clip_stem: score}`, same keys as clip_index.json) appears next to it — the
  layout is built now so scores populate automatically once CONTINUITY's pass lands,
  per Kim's explicit ask ("build the layout now w/ delta cols populating when
  scores land").
- Leak-scan clean, DOM-harness verified (450 cells, cross-cell switching, toggle-stop).
  Clips at `clips_rarity/` (450 files, 128k AAC). Handed to WINTERMUTE.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — breathing.html: the #35 conditioning-lever breakthrough

- CONTINUITY's ask (Kim actively listening): page `promptarc_single_kaikkialla_nl65/dual_lora.wav`
  — the #35 finding that high-nl static is a CONDITIONING problem, not a noise problem
  (8-section rich prompt-arc @ nl 0.65, single adapter, HF-var 0.364 — 10x the generic-
  prompt-at-nl.70 baseline of 0.035). Added as a 4th section on breathing.html
  (`render_promptarc()`), sharing the same global playhead as v1/v2/v3. Rather than
  duplicating a baseline clip, cross-referenced v3's ALREADY-STAGED `baseline_fixed_nl_v3`
  (single-adapter, single generic prompt, nl 0.70) as the direct A/B — it's literally the
  "overshoot" comparison row in this run's own FINDINGS.md table, so no new baseline
  render was needed. Leak-scan clean, DOM-harness regression-checked. Handed to WINTERMUTE.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — timbral crop sidecars COMPLETE (5400/5400)

- WINTERMUTE's LatCH-training dependency: `extract_timbral_hdb.py --mode crops` finished,
  ~10.3h runtime (--jobs 12), 5400/5400 `latents_sa3` crops now have `<idx>.TIMBRAL.json`
  (hardness/depth/booming). 5398 real extractions + 2 genuinely silent windows (003517,
  004770 — `timbral_models` correctly raises "Input file is silence, cannot be analysed",
  confirmed by hand, not a pipeline bug) — wrote an explanatory sidecar (null values +
  `skip_reason`) for those two so they don't read as an unexplained gap to whoever looks
  next. Handed off to WINTERMUTE. Now launching `--mode tracks` for the whole-track
  corpora (avp source 170 + goa 4461 ≈ 4631 tracks) — not a dependency for anyone, runs
  in the background.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — breathing.html: v2 added, same-playhead across versions

- CONTINUITY's fast follow-up (Kim's listening verdict on v1 → same-day v2 fix): asked
  W/G to add v2 (`breathing_kaikkialla_evr1x_v2/`, full-range 0.30-0.62 + source-break
  ducking) to breathing.html so Kim can A/B v2 vs v1 vs baseline. Restructured the
  generator (`render_version()`) so both versions render through the same code path —
  findings box, recipe line, A/B pair, trajectory SVG — sharing ONE global `abAu`/`abCur`
  so switching between ANY of the 4 clips (v1 breathing/baseline, v2 breathing/baseline)
  keeps the playhead position, not just within a version.
  v1 and v2 have DIFFERENT baselines (requested_nl 0.55 vs 0.62 — confirmed via md5sum
  before assuming they were interchangeable), so all 4 clips are distinct, clearly labeled.
  Kim's verdict text (folded into v1's FINDINGS.md by CONTINUITY) gets its own highlighted
  `.verdict-box` split out from the findings prose — it's a directive, not an observation,
  worth visually distinguishing.
- DOM-stub harness verified cross-version switching specifically (the thing most likely
  to break — v1 cell classes must clear when a v2 cell starts playing, etc.) — passed.
  Leak-scan clean. Clips at `clips_breathing/` (+`_v2` suffixed pair). Handed to WINTERMUTE.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — breathing.html (the #35 controller headline result)

- CONTINUITY's flag: `breathing_kaikkialla_evr1x_nl55/` (tier-1 GPU validation of the
  #35 breathing-noise controller) was page-ready but unpaged — "tonight's headline
  result." Doesn't fit any existing template (a2a ladder pages are nl x adapter
  tables; this is one A/B pair + a per-window trajectory) — new standalone page
  `~/riffer-evals/breathing.html`, generator `Misc/build_breathing_page.py`.
  Self-contained inline SVG line chart (nl + novelty per window, floor/median
  reference lines, no canvas libs/CDN) — CONTINUITY's own suggested visualization
  ("plot nl + novelty vs window; the controller visibly breathes").
- Content: FINDINGS.md verbatim (VALIDATED — nl breathes 0.55→0.45→0.55 at the loop
  window, w3-6 mean novelty +13% vs fixed-nl baseline), same-playhead A/B (breathing
  vs baseline_fixed_nl, full ~7:40 track), calibration stats. Checkpoint shown as
  "evr1x" (established shorthand), never the raw ckpt path. Source track is Kim's
  own (Kaikki-Alla) — no rights question. The sibling `breathing_kaikkialla_evr1x/`
  (no `_nl55` suffix, requested_nl=0.7) is the earlier flat-trajectory attempt the
  trailing-context fix corrects — deliberately not paged, superseded by this run.
- Verified via a JS DOM-stub harness (A/B toggle, cross-clip switching, stop-on-re-click).
  Leak-scan clean. Clips at `clips_breathing/` (128k AAC). Handed to WINTERMUTE.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — mp.html cross-model checkpoint-pulldown section

- CONTINUITY's mp_crossmodel/ ask (Kim's "checkpoint pulldown" request): wired 48 clips
  (8 checkpoints x 6 prompts, uniform steps16/cfg5/dur47/seed1234/DoRA1.0) into
  `~/riffer-evals/mp.html` as a new self-contained section (own `xm*`-prefixed JS
  namespace to avoid colliding with the page's existing gain x density grid code —
  the two eval types have unrelated data shapes, not worth forcing into one structure).
  New generator: `Misc/build_mp_crossmodel.py`. Always-visible 6-prompt legend +
  per-checkpoint training-recipe line (rank/alpha/optimizer/lr/epoch-of-total/corpus,
  sourced from `eval/mp_checkpoint_recipes.json`) that updates with the pulldown,
  per Kim's "visible not hover" UI rule.
- Two real bugs caught before shipping: (1) leak — the `everything` recipe's free-text
  `note` field embedded a raw ckpt filename (`epoch=7-step=12216.ckpt`) inline; added a
  prose-scrubbing regex (structured fields like rank/lr/corpus stay as-is, only free
  text gets the ckpt-filename pattern redacted). (2) unicode — used `json.dumps(...)`
  for HTML-escaping prompt text, which ASCII-escapes non-ASCII by default (`ensure_ascii=True`)
  → "aavepyörä" rendered as the literal string `aavepyörä` on the page; fixed
  by using `html.escape()` instead (the right tool for HTML context, not JS-string
  escaping). Also hit a Python name collision: a local `html` variable (the page's
  text content) shadowed the `html` module import — renamed to `page`.
  Both caught by a hand-rolled JS DOM-stub harness run against the real built page
  (dropdown population/default-selection, checkpoint switching, recipe text updates,
  play/toggle/stop) — same pattern that caught real bugs earlier this session; code
  review alone would likely have missed the unicode one.
- Leak-scan clean on the final build. Clips transcoded to `clips_mp_crossmodel/`
  (128k AAC). Handed to WINTERMUTE for publish.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — a2a_angelic_r64tiered_lr1e4 ladder page + a2a-group date bug

- CONTINUITY's ask (Kim-directed GPU render): page 2 new a2a full-track noise ladders —
  `a2a_angelic_r64tiered_lr1e4_ep7`/`_ep5` (r64-tiered avp adapter, ep7 vs ep5, nl 0.4-0.9 x 6,
  Hallucinogen - Angelic Particles). Same filename/run_meta convention as the existing
  `a2a_angelic_evr1x` ladder, so no new writer needed — staged both dirs verbatim
  (`Misc/build_evals.py`'s `A2A_LADDER_RE` groups same-track dirs automatically), rebuilt.
  Produces `a2a_angelic_r64tiered_lr1e4` with ep5/ep7 as columns, nl as rows, same-playhead.
- Found + fixed a real bug while verifying: `write_a2a_ladder_folder` callers hardcoded
  `date_str=""` for EVERY a2a ladder page (all 3 pre-existing ones: angelic/kaikkialla/
  vapausvoima), so they never sorted by real date at all — always sank to the bottom of
  "All runs, newest first" regardless of actual recency, the same class of bug as the
  earlier real_date()-is-start-not-finish issue. Fixed: compute `date_str` from the
  earliest member's `real_date()`, same definition used everywhere else in the file. All
  4 a2a ladder pages (3 existing + 1 new) now show correct dates; new one correctly ranks
  #1 (started 2026-07-10 02:00, most recent thing in the index).
- Leak-scan clean on all 4 pages touched. Local cache only. Handed to WINTERMUTE for
  publish (staging + the code fix both need to ride together since the fix changes how
  ALL a2a ladder pages sort).

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — evals index: fixed stale "newest" + staged a missing UI

- Kim's question: the local evals index (`~/.cache/evals_aac/index.html`) showed avp_cfg_sweep
  (2026-07-09 15:29) as the "latest experiment" — suspicious, since there was clearly later
  activity. Root cause confirmed: `real_date()` in `Misc/build_evals.py` reports the EARLIEST
  mtime among a render dir's own files (deliberately, per its docstring, to dodge a later
  `run_meta.json` provenance-backfill looking like a fresh run) — so "newest first" actually
  means "most recently STARTED," not "most recently finished/updated." avp_cfg_sweep started
  15:29 but kept receiving clips to 17:45; genuinely newer work (CONTINUITY's a2a_memo_test,
  finished 17:51) wasn't in the index at all.
- Second question: "do all of today's evals/renders have a UI?" — NO. Found `a2a_memo_test`
  (Mantu `sa3_lora_runs/a2a_memo_test`, CONTINUITY's 3-clip a2a memorized-checkpoint-at-low-CFG
  test, explicitly "FOR KIM'S EAR") sitting as raw .wav + FINDINGS.md with zero player. Staged it
  (transcoded to AAC, wrote the missing `run_meta.json` sidecar from FINDINGS.md) and let
  `build_evals.py` generate its page via the generic `write_folder()` fallback. Landing name is
  `memo_ckpt_a2a_test`, not `a2a_memo_test` — the real name collides with `A2A_LADDER_RE`
  (`^a2a_(track)_(adapter)$`, meant for the per-track noise-level ladder family) and got silently
  swallowed with no page written; added a `RENDERS_SOURCE_ALIASES` entry so `real_date()` still
  attributes it to the true Mantu source dir (17:47) instead of today's transcode day.
- Also found + fixed: avp_cfg_sweep's own staged copy was missing its `run_meta.json` (present
  on Mantu, never copied over) — it was showing the generic unhelpful "renders 1" label. Copied
  it in; now reads "CFG sweep x training-stage (Underfit CFG-dynamics test)".
  Rebuilt the local index (`python3 Misc/build_evals.py`, stdlib-only, no venv needed) — it now
  correctly ranks `memo_ckpt_a2a_test` (17:47) above `avp_cfg_sweep` (15:29). Leak-scan clean on
  both new/changed pages. Noted but NOT fixed (pre-existing, unrelated to this session): the
  index still leaks bare ckpt-dir names in two hrefs — `dora128_everything_8ep_lr1x_ep7_sweep`
  and `..._steps_diag` — flagging for WINTERMUTE's ship-time scan, not touched since out of scope
  of what was asked. This is all LOCAL CACHE ONLY (`~/.cache/evals_aac/`) — nothing pushed/published.

## 2026-07-10 — Kim + Sonnet 5 (GHOST-NOTE) — dora_results.html marked SUPERSEDED

- Kim's ask: `dora_results.html` (rank-16/64/128 DoRA-on-Goa ladder) sits at the very front of the
  riffer-evals landing page (index.html) and reads as current — it isn't; the later avp adapter
  investigation (avp_master) supersedes its findings. Rather than aggregating everything onto one
  page (would get messy), just fixed the preamble: added a `<div class=status-banner>` (CSS class
  was already defined, unused) right under the `<h1>`, flagging it as the first DoRA rank-ladder
  pass (Goa in-distribution, 2026-07-07 audition) and linking to the avp_master page for the
  current picture. Source: `~/build_dora_results_page.py` (mir venv), writes `~/riffer-evals/
  dora_results.html`; synced the `~/.cache/evals_aac/riffer/` mirror copy too. Leak-scan clean.
  Not pushed (riffer-evals is a public GH Pages repo, `git@github.com:Taikakim/riffer-evals` —
  publish is WINTERMUTE's lane); staged locally for the next publish pass.

## 2026-07-09 — Kim + Sonnet 5 (GHOST-NOTE) — avp_master findings finalized (degradation_report_v2 + CFG_ANALYSIS)

- CONTINUITY's promised final ANALYSIS numbers landed (`avp_board_seeds/ANALYSIS/degradation_report_v2.md`
  + `avp_cfg_sweep/CFG_ANALYSIS.md`) — rewrote `avp_master`'s findings header entirely, replacing the
  earlier dialogue-summary placeholder. Two corrections worth flagging (not just additions):
  (1) the v2 report REVISES the earlier "ep31 is THE sweet spot" framing — raw Audiobox CE peaks at
  barely-trained epochs (a CE-as-generic-pleasantness artifact), and reading CE alongside spectral-
  centroid band + tempo-lock reveals TWO candidate islands: ep31 (narrow, on the ringing shoulder) and
  ep7-9 (spectrally healthier, best point ep8). (2) the freeform arm's finding and the r64-tiered-caption
  finding looked contradictory read separately (freeform: single descriptive caption did NOT fix
  conditioning collapse, ratio 0.22 vs trigger's 0.92; r64+tiered: DID fix it, ratio 1.5-2.65) but are
  actually the same result from two angles — it was never the trigger TOKEN's fault, any single caption
  reused everywhere collapses conditioning; caption DIVERSITY is the real lever. Wrote both up accurately
  rather than picking the flattering half.
- Extended `sweet_epoch` (Python `write_avp_ladder_folder`/`write_avp_seeds_folder`) and `SWEET_EPOCHS`
  (JS, both `AVP_LADDER_JS_TEMPLATE` and the master's `renderLadderSection`) from a single int to a list,
  to mark both islands. Hit a second real bug doing this: the marking condition required `kind==='step'`
  (deliberately, to avoid marking the incomplete 3-prompt `_fine` subset row over the full 7-prompt `_step`
  row when both exist at the same epoch) — but epoch 8 has NO `_step` variant at all, only `_fine`, so it
  never got marked. Fixed by marking the BEST-available kind per (arm, epoch) — rows are already sorted
  step-before-fine-before-warm, so "first match per epoch" is correct without hardcoding a kind. New
  Audiobox-CE step-invariance finding also added (sweet spot clusters ~900-1200 steps across rank 16/128,
  independent of rank — but NOT corpus-invariant, GOA in-distribution peaks ~9x later).
- Re-verified with the harness suite (updated the seeds/master harnesses' sweet-row assertions from
  single-row to two-row) — all 4 harnesses (seeds standalone, master, r64, cfg_sweep) pass, no regressions.
  Leak-scanned clean across all 8 avp pages. Handed to WINTERMUTE; C's incoming write-up (a2a
  memorized-ckpt-at-low-CFG test) will want one more pass when it lands.

## 2026-07-09 — Kim + Sonnet 5 (GHOST-NOTE) — 2 new avp pages: r64 LR-bracket board + CFG x stage sweep

- CONTINUITY's page ask (Kim's active audition targets): `avp_board_r64` (384 clips — rank-64
  midway recipe + tiered Flamingo/Granite captions, 2 LR arms x 12 epochs x 4 prompts x 2 seeds x
  2 DoRA strengths) and `avp_cfg_sweep` (40/50 clips so far — the Underfit-memo CFG-dynamics test:
  a hand-picked cross-arm training-stage sequence x 5 cfg values x kimlong/empty-prompt toggle,
  the empty-prompt column being the "absorption" diagnostic).
- `avp_board_r64` exposed two real gaps in the ladder machinery built for `avp_master` this
  session: (1) its filenames have a BARE `epoch00` tag with no `_step`/`_fine`/`_warm` suffix at
  all — `LADDER_STEM_RE`'s suffix group was mandatory; made it optional, defaulting to `kind="step"`.
  (2) row identity was keyed by `tag` ALONE — fine for every prior board (single arm, or "base" vs
  the ladder arm never sharing a tag), but r64 has TWO real arms (`r64_lr2e4`/`r64_lr1e4`) that
  legitimately share the same `epoch00..epoch11` tags — this would have silently collided/dropped
  half the board. Fixed by keying on `(arm, tag)` everywhere (JS row map + byKey + the Python
  `n_rows` count, which had the same latent bug — caught by rebuilding and seeing "12 checkpoints"
  instead of the expected 24, not by code review) and prefixing the row label with the arm name
  whenever more than one non-"base" arm is present. Regression-tested against every existing
  single-arm board (seeds/armG/freeform/goa_everything/master) — unaffected.
- `avp_cfg_sweep` is a genuinely new page shape (`write_avp_cfg_sweep_folder` +
  `AVP_CFG_SWEEP_JS_TEMPLATE`): stage-rows (explicit hand-authored order — early/mid/sweet/late/
  armG, NOT alphabetical or epoch-numeric) x cfg-columns, with a 2-button prompt toggle instead of
  a dropdown (only 2 values, and Kim's "visible not hover" rule already covered by showing the
  active toggle state + the full checkpoint-recipe legend statically). The 5th stage (`armG_ep5`)
  isn't rendered yet — the page correctly shows only the 4 present stages and will pick up the 5th
  on the next rebuild with no code change.
- Both verified with hand-rolled JS DOM-stub harnesses on the real built pages (multi-arm
  collision + toggle re-render behavior specifically exercised, not just "does it parse"),
  leak-scanned clean across all 8 avp pages now live (added `epoch=N-step` and `dora64` to the
  scan pattern). Handed to WINTERMUTE.

## 2026-07-09 — Kim + Sonnet 5 (GHOST-NOTE) — avp master/board pages: always-visible prompts + recipe

- Kim's UI feedback (relayed by CONTINUITY): prompt text and recipe params must be VISIBLE at a
  glance while auditioning, not hidden behind hover tooltips or click-to-reveal. Added
  `_prompt_legend_html()` (prompt-key → full text, always-rendered `<ul>`) and
  `_recipe_line_html()` (arm/rank/lr/optimizer/DoRA-strength/corpus, one line) to
  `Misc/build_evals.py`; wired into `write_avp_ladder_folder`, `write_avp_board_folder`, and every
  section of `write_avp_master_folder` — applies to the master page AND all 5 per-board pages.
  New `AVP_PROMPT_TEXT` canonical dict (trig/trig2/upbeat/goa1/goa2/psy/freeform/goa) fills in for
  boards without their own `run_meta.json` prompts sidecar; a board's own sidecar always wins.
  `trigdesc`/freeform's `goa` prompt honestly labeled "exact wording not recorded" rather than
  guessed — same standard as the goa_everything_board provenance question earlier this session.
  New CSS `.prompt-legend` (`eval_grid.py`). Re-verified with the same JS harnesses (master +
  standalone avp_board_seeds) — all pass; leak-scanned clean (0 hits) across all 6 avp pages.

## 2026-07-09 — Kim + Sonnet 5 (GHOST-NOTE) — avp adapter investigation MASTER page (`avp_master`)

- Kim's ask via CONTINUITY DM: one consolidated page for the whole avp investigation. Built
  `Misc/build_evals.py`'s `write_avp_master_folder()` — 5 sections (arm x epoch grid + 4
  ckpt-ladder boards: avp_board_seeds/armG/freeform/goa_everything_board) on ONE page with a
  SINGLE shared playhead across all sections (a genuinely new template, `AVP_MASTER_JS_TEMPLATE`
  — the per-dir writers each instantiate their own `Audio()`, so simple reuse would have given 5
  independent playheads). Findings header embeds the three-process degradation story (spectral
  collapse/ZCR, tempo U-notch at ep31, conditioning collapse), the trigger speech-prior finding,
  Arm G's flat tempo-stability, and the aug-theory verdict; ep31's plain-ladder row is highlighted
  (`.tc-sweet` CSS, `eval_grid.py`).
- Generalized the ckpt-ladder parsing (`LADDER_STEM_RE`/`_parse_ladder_records`,
  `write_avp_ladder_folder`) to handle the FULL grammar CONTINUITY flagged: `{arm}__epoch{E}
  (_step{S}|_fine|_warm{W})__{prompt}__s{seed}[__st{strength}].wav`. Row identity is the full TAG,
  not epoch alone — avp_board_seeds' dense re-run window has BOTH `epoch31_fine` and
  `epoch31_step1152` (two distinct checkpoints sharing an epoch number); keying by epoch alone
  would have silently dropped half the dense-window data. `write_avp_seeds_folder` (previously
  hand-rolled, and STALE — its old regex didn't match `_fine`/`_warm`/`base__` tags at all, so the
  live page was silently stuck at the original 168-clip prompting-probe render while Mantu's copy
  had grown to 466) is now a thin wrapper over the shared parser.
- **Bug found + fixed via the JS test harness** (not by inspection): a board with exactly ONE
  distinct DoRA-strength value mixed with un-tagged records (avp_board_seeds has 15 stray
  `__st10`-suffixed duplicate renders alongside their un-suffixed twins at the same
  tag/prompt/seed — leftover duplication, not a deliberate sweep) made the default `strength`
  variable non-null while 451/466 records had `strength=None` — every lookup mismatched and the
  WHOLE table rendered blank. Fixed by normalizing `strength` to `None` across a board whenever
  fewer than 2 distinct non-null values are present (only a genuine 2+-value sweep, like armG's/
  freeform's 1.0/0.6, gets a strength selector at all).
- Staged 3 previously-untranscoded render dirs (avp_board_armG 60 clips, avp_board_freeform 144,
  goa_everything_board 24) to AAC 128k + wrote their `run_meta.json` sidecars (training params
  read directly from checkpoint `lora_config`/optimizer `param_groups` via `torch.load`).
  goa_everything_board's provenance (lr1x vs lr3x — identical step counts, no sidecar/script on
  disk to disambiguate) resolved via WINTERMUTE→CONTINUITY: `dora128_everything_8ep_lr1x` (2e-4),
  confirmed from the render script, not inferred — did not guess on a provenance page.
- Verified with a hand-rolled Node DOM-stub harness on the REAL built page (not synthetic data) —
  caught the strength bug this way; also confirms the shared-playhead behavior (clicking a cell in
  one section un-marks the previous section's cell, single `curKey`). Leak-scanned clean (0 hits)
  after also fixing a bare checkpoint-directory-name mention — `dora16_avp_originals_64ep` — in
  freeform's `purpose` text that `redact()`'s path/extension/IP patterns don't cover (a real gap:
  `redact()` doesn't catch bare directory-name-shaped tokens in prose, only literal paths/
  extensions/addresses — worth a pattern addition later, not fixed here since the practical
  mitigation was rewriting the one offending sentence).
- Handed to WINTERMUTE for leak-scan/transfer. Findings will get one more re-render once
  CONTINUITY's `avp_board_seeds/ANALYSIS/degradation_report.md` (promised ~11:48, still pending as
  of this entry) lands with final numbers to replace the dialogue-summary version currently embedded.

## 2026-07-09 — Kim + Sonnet 5 (GHOST-NOTE) — dataset.json → dataset.jsonl migration (mir)

- `mir/src/core/data_store.py`'s `DataStore` now reads/writes `dataset.jsonl` (one `{"_key": ..., <features>}`
  record per line, grep/jq-streamable) + a `dataset.meta.json` sidecar (generated_at/root/count), replacing the
  old single-line `dataset.json` dict that couldn't be searched. `bootstrap()`/`load()`/`flush()` all updated;
  call sites (`pipeline.py`, `master_pipeline.py`, `crops/pipeline.py`) needed no logic change (they already go
  through `DataStore`), just one direct path construction in `pipeline.py` (`dataset.json` → `dataset.jsonl`).
- New `mir/scripts/migrate_dataset_json_to_jsonl.py` — converts a directory's old `dataset.json` in place,
  verifies (reload + entry-for-entry diff) before renaming the original to `dataset.json.bak` (never deletes).
- Ran it on all 3 known `dataset.json` files (Mantu): `ai-music/organic dance` (0 entries), `ai-music/Goa_Separated`
  (4461), `goa_crops` (202,745 entries, 661 MB → migrated + verified in 30s). All `.bak` originals kept for now.
- No other repo touches this file (`stable-audio-tools`'s `dataset.json` hits are unrelated training-dataset
  configs, not this artefact).

## 2026-06-29 — Kim + Opus 4.8 — EMA(+grad-accum) REVERSES the skewness "ceiling": ~3× control, head was damping-limited

- Follow-up to the LR/batch sweep (which concluded "architecture-limited"): EMA 0.999 at the best settings
  (adamw lr 3e-4 bs32) × {20ep, 40ep, 80ep, grad-accum2 = eff-batch-64}. **All four EMA heads BEAT the
  original** (gain 512): MERTmid Δ ema_ga2 0.0271 / ema40 0.0248 / ema20 0.0237 / ema80 0.0197 vs
  **original 0.0086** (~2.3–3.1×); skew-follow +2.4 vs +1.6; CE equal/better. **So the prior
  "architecture/target-limited ceiling" was WRONG — the head was DAMPING-limited.** EMA averaging (the
  MASTER §4 drift-fix) unlocks the control the optimizer sweep couldn't.
- Mechanism: best head (ema_ga2) moved the LEAST from init (54% of orig ΔW); worst (ema80, 80ep) moved the
  MOST (190%) → it's the AVERAGING, not displacement, that buys control; >40ep lets late drift leak into the
  average + erodes it. Sweet spot: **EMA + grad-accum2 + ~20ep**. The high EMA train loss (0.6 vs 0.053) was
  the decay-0.999 EMA-lag reporting artifact, NOT undertraining (weights moved ≥ orig).
- **New default control-head recipe: EMA(+grad-accum)/early-stop.** Ship `ema_ga2` (best steering+CE), `ema40`
  backup. `train_latch.py` now has `--ema` + `--grad-accum`. Heads `stable-audio-3/latch_weights_ema_sweep/`;
  eval `latch_sweep/skew_ema_results.json`.
- **SUPERSEDES the prior-day "spectral_skewness optimizer tuning done / don't run larger-batch" line** — that
  was LR/batch *without* averaging; with EMA it's a clear win. TODO: `latch_sweep.html` still says
  architecture-limited — correct it.

## 2026-06-29 — Kim + Opus 4.8 — CK flash-attn validated on the new torch-2.14/ROCm-7.15 multi-arch venv

- Distributability test of the `docs/flash-attn-ck-rdna4.md` recipe on the bleeding-edge AMD multi-arch
  stack **PASSES**: `flash_attn 2.8.4` builds + imports + computes on `SAO/.venv`
  (`torch 2.14.0a0+rocm7.15.0a`, gfx1201, py3.13); §9 varlen cos vs SDPA = **3.18e-4**. §5 glue patch
  still applies on the branch's latest-develop CK (helpers + sink_ptr present).
- **One delta from the recipe: use `MAX_JOBS=4`, not 6.** At `-j6` (12 clang) the heavy `fmha_bwd_d128`
  kernels exhaust system RAM → a clang is OOM-killed → "subcommand failed" near 2390/2397. The
  `mha_fwd_kvcache` *warning* and the `urllib 404` (setup.py no-prebuilt fallback) are red herrings
  (recipe §10). `-j4` finishes clean. Install with `FLASH_ATTENTION_FORCE_BUILD=TRUE` to skip the 404.
- Venv install path (the documented `torch[device-gfx1201]` multi-arch flow) works: base `torch` +
  `amd-torch-device-gfx1201` + `rocm-sdk-*` + `triton 3.8.0`. **torchaudio 2.11 on this venv delegates
  I/O to torchcodec** (not installed) — `torchaudio.load/save` need torchcodec; separate from FA.
- TODO: fold the `-j4` note into `docs/flash-attn-ck-rdna4.md` §7.

## 2026-06-29 — Kim + Opus 4.8 — spectral_skewness LatCH LR/batch sweep: no win; head is architecture-limited

- Swept `spectral_skewness` (the best spectral head) over training config: LR 2×/4×/8× @ bs32 + batch
  0.5×/0.25×/single @ 2× LR (6 runs, AdamW) vs the original (lr 3e-4/bs32/20ep). Eval at gain 512
  (MERT-mid Δ + skewness-follow + Audiobox CE). **No config beats the original** (best ties: lr4x 0.0082 ≈
  orig 0.0083); smaller batch clearly worst; 8× LR over-cooks; lr2x_bs32 marginally best feature-follow
  (+1.68) but noise-level. Train loss is blind (spans only 0.0530–0.0554 across all configs).
- Per-layer analysis (CPU; checkpoints + wandb `kim-ake/sa3-latch`): **the winner moved the LEAST** —
  dist-from-init orig 30 < lr2x_bs32 48 < … < lr2x_bs1 229 (7.6× span). All configs diverged from the
  original's low-movement basin and never returned; K/V do move (0.6→3.4× init, MASTER §4 confirmed). The
  **drift hypothesis broke** (lr4x moved a lot yet tied; bs1 moved most yet mid-pack; bs16/bs8 logged only
  1–2 telemetry rows → undiagnosable + partly eval noise).
- **Conclusion: spectral_skewness control is architecture/target-limited, not optimizer-limited — optimizer
  tuning for this head is DONE.** Do NOT run lower-LR/larger-batch (it would move *less* → tie at extra cost).
  Levers instead: EMA/late-soup (small upside), a different head architecture/target, or the energy heads
  (rms_energy_bass/mid steer 2–10× harder).
- Artifacts: Mantu `latch_sweep/` (`latch_weights_sweep/skew_*`, `skew_eval_clips/`, `skew_sweep_results.json`,
  `skew_layer_analysis.md`, `skew_layer_heatmap.png`); section added to riffer-evals `latch_sweep.html`.
  Trainer `stable-audio-3/scripts/latch/train_latch.py` has no grad-accum flag (would need a ~10-line add).

## 2026-06-28 — Kim + Opus 4.8 — CPU LatCH-guidance eval path (commit 020b6c3)

- **New scripts** in `stable-audio-3/scripts/` (branch `latch-sa3-phase1`): `sa3_latch_onnx.py`
  (`generate_z0_latch_guided` — two-stage variance+mean Selective-TFG, APG CFG, LogSNR schedule);
  `latch_eval_server.py` + `submit_latch_job.py` (file-drop server, queue `SAO/latch_eval_queue`;
  `--prompts` one verbatim prompt per flag occurrence — no comma-split, musical prompts contain commas);
  `latch_validate.py` (CPU/GPU z0-cosine harness).
- **Why LatCH runs CPU-only.** LatCH guidance is a **gradient** method: the plain DiT runs
  forward-only on ORT CPU EP (numpy), and guidance is applied via torch autograd through the
  ~5-7M-param LatCH head only. The head never bakes into the ONNX graph (unlike control adapters).
  Head autograd on a tiny model is cheap; DiT never needs autograd → CPU-feasible.
- **APG CFG** (`sa3_latch_onnx.apg_cfg_velocity`) faithfully ports `dit.py::apg_project`
  (orthogonal projection, lines 339-341) — cos=1.0/max|d|=0 vs the shipped projection.
- **Device gotcha #1 (both eval servers).** Load the T5-Gemma conditioner via
  `make_text_cond.load_conditioner` which calls `StableAudioModel.from_pretrained(device="cpu",
  model_half=False)` — 1.4 B weights stay on CPU (GPU mem delta: −3 MB vs old cuda load). Do NOT
  set `HIP_VISIBLE_DEVICES=""`: `flash_attn`/`aiter` probes a Triton driver at import time;
  zero visible devices → immediate crash. Fix verified in both `latch_eval_server.py` and
  `control_eval_server.py`.
- **GPU z0-cos ≥ 0.999 NOT yet run** (`latch_validate.py --run-gpu` deferred). Needs the card
  free AND a shared init latent — CPU `torch.randn(seed)` ≠ CUDA `torch.randn(seed)` by RNG
  device; seed-matching alone won't hit the bar. The harness must inject one init latent into
  both paths.
- Gain: `rho=mu=64.0` default is conservative; **operating point ≈512 for energy heads** (see
  entry below). Do not cite 48–96 or 128 as the working range.

## 2026-06-28 — Kim + Opus 4.8 — SA3 LatCH head sweep: operating gain ~512, energy heads only

- Swept all 14 SA3-medium LatCH **guidance** heads (`stable-audio-3/latch_weights_sa3_medium/`) ×
  {low,mid,high} = `std_mean`±2σ × 3 prompts; measured MERT + Audiobox CE + target-feature follow.
  **Operating gain ≈512, ~10× the documented 48–96** — gain 128 is a dead zone (<1 dB feature move,
  MERT Δ ~0.001). Gain ladder 128→1024 is monotonic (MERT Δ + spread grow ~40–47×).
- At gain 512 (CE holds): **STRONG** `rms_energy_bass` (+5.1 dB), `rms_energy_mid` (+6.0); **moderate**
  `rms_energy_body`/`spectral_skewness`/`rms_energy_air`; **dead at any weight** beat/downbeat/onset
  activations, `hpcp`, `spectral_kurtosis` (perturb CE without steering). Refines MASTER §5 gain note.
- Eval gotcha: use the **mid** MERT layer for energy/timbre heads — upper layer (melody/harmony) is blind
  to a bass-RMS change and mislabels the two best heads "dead". Recipe: `gen_one.py::gen_guided` →
  `sample_flow_euler_multi_latch_guided(rho=mu=gain, gamma=0.3, n_iter=4)`, fp32; ~7 s/clip after a
  one-time ~340 s flex-attn autotune (guidance backprop forces FlexAttention, not CK flash-attn).
- Artifacts: Mantu `latch_sweep/{clips (g128), clips_g512, ladder}` + pipeline (`sweep_driver`,
  `gen_one`, `measure_sweep`, `analyze_sweep`); page **riffer-evals `latch_sweep.html`** (commit 574453e,
  gain-response section + tiered leaderboard + 30-clip AAC subset online).

## 2026-06-28 — Kim + Opus 4.8 — steered-longform glitch root-caused (over-steer); SA3 steering models packaged for Kevin's VST

- **Glitchy `steered_longform` output root-caused: over-steering, not the longform machinery.** The
  `/home/kim/steered_runs/opb_*.wav` files (made with the OLD fixed `--gain 6`) collapse because effective
  drive = `gain × z × adapter`; at density 14 (`scalar_norm` [4.64,2.16] → +4.3σ) × gain 6 ≈ 29× the trained
  per-token influence → off-manifold, energy craters, broadband distortion. Evidence: RMS dips exactly where
  the density schedule peaks (both triangular & descending); glitches uniform across `t mod 25s` (NOT at window
  seams); only ~3% of strong jumps touch clipped samples (so not the `clamp(-1,1)` write either). A/B on GPU
  (60s, 16 steps): fixed gain6 → 4355 strong glitches + RMS collapse; **`--ridge` → 169 (26×↓), no collapse**;
  `--ridge` + capped range (`--lo 3.5 --hi 8`) → 29 (150×↓). Fix already coded (`density_schedule.ridge_gain`,
  gain-per-density [0.7,3.0]); the old files just predate it. UI lesson: never expose a raw fixed gain slider.
- **Steering-model handoff package for Kevin Griffing (gary4juce/gary4local VST) at `/home/kim/sa3-kim-steering/`**
  (+ `.tar`, 720M, 34 files). Two mechanisms, separate docs (`docs/01–04`): `control_adapters/` (density:
  onset_density + onset_per_beat, stripped to inference-only `state`, validated end-to-end from the packaged
  code — 3/7/11 → 4.88/8.12/9.25 onsets/s) and `latch_guidance/` (14 LatCH heads incl hpcp=chroma + the 3 SA3
  modules + `reference/model.py.kim` for the `generate(latch_configs=...)` branch; PyTorch-only, won't run on
  his GGML/MLX). Documented caveats: fork-Attention attr diff, CFG `[cond,uncond=zeros]`, n_tokens cap 16, fp32
  for LatCH, rho/mu≈64 for medium. Base DiT/AE excluded (he ships it).

## 2026-06-27 — Kim + Sonnet 4.6 — fp16 control-DiT GPU measured; CPU eval math; shared gen-core tooling

- **fp16 control-DiT on MIGraphX (RX 9070 XT) — first end-to-end session-ready measurement.** AOT compile:
  **2391 s (DiT) / 2438 s (decoder)** — ~40 min each (longer than fp32 ~18 min because the host-PE graph
  change adds ops MIGraphX must compile). Per DiT call: **169 ms** (fp32: 294 ms; ~43% faster). Cos vs CPU:
  **0.9999** (fp16 floor). 100% on-EP. Fills the one remaining open cell from the 2026-06-27 GPU-VERIFIED
  record.
- **CPU control path calibrated.** Session-ready ~10 s (no compile), **674 ms/call**. 30-clip 8-step
  eval grid (CFG = 16 calls/clip): **~5.4 min CPU vs ~42 min GPU** (compile-dominated). **CPU is the
  correct default for control-evals, not a low-VRAM fallback** — GPU only wins for a long-lived resident
  process (VST) where the AOT compile amortises over hundreds of clips.
- **Compile-cache: confirmed missing EP feature.** `onnxruntime_migraphx` 1.23.2 does NOT plumb
  MIGraphX's compiled-program save/load API through the EP — `migraphx_save/load_compiled_model`
  options are REJECTED, ORT silently falls back to CPU. Not a config gap; not exposed in this build.
  See `stable-audio-3/scripts/decode_onnx.py:_augment_migraphx` + retry guard (line 241). Ways out:
  newer ORT-ROCm build, long-lived resident server, or the CPU path.
- **New tooling (verified on disk):**
  - `stable-audio-3/scripts/sa3_control_onnx.py` — shared numpy/ORT gen-core (`generate_z0`,
    `make_control_tokens`, `resolve_host_pe`).
  - `avp_sa3/sa3_control/train.py --export-onnx-on-finish` (default True, `--export-onnx-frames`
    default 256) — shells out to `export_dit_control_onnx.py --fp16` on training finish, writing
    `riffer_final.pt → dit_medium-base_L256_ctrl.onnx` + `.cond.npz` into the run dir; non-fatal.
- `stable-audio-3/scripts/control_eval_server.py` — **all-CPU** long-lived file-drop eval server
  (resident T5-Gemma + ONNX DiT/decoder, CPU EP `--threads 12`; queue at `SAO/control_eval_queue`;
  atomic claim/publish; frames derived from the DiT graph) and `scripts/submit_control_job.py`
  (stdlib-only cross-venv submitter). **End-to-end verified 2026-06-27 (CPU):** boot ~16 s, 8-step job
  ≈20 s total; steering through the server path onset 3→5.17, 11→10.43 onsets/s (librosa); shared-core
  z0 bit-exact (max|Δ|=0) vs the pre-refactor CLI. Also fixed: the refactor relocated
  `add_fractional_positions_np` to `sa3_control_onnx.py`, so `export_dit_control_onnx.py`'s import was
  repointed there (it had broken otherwise — and the training hook shells out to it).
- Docs updated: `stable-audio-3/docs/onnx-amd-inference.md` (fp16 GPU numbers, compile-cache note,
  eval math, tooling section), `SAO/MASTER.md §5` (reconciled control-DiT row).

## 2026-06-27 — Kim + Opus 4.8 — Control-DiT MIGraphX verify: EP bound, numbers NOT yet measured (corrected the over-stated GPU-VERIFIED claim)

- **Corrected MASTER.md §5: the control-DiT "GPU-VERIFIED (MIGraphX): cos=1.0, 100% on-EP, 294ms/call,
  steering 3→5.00/11→11.19" line was premature** — none of those were measured this session. mir venv
  has the EP (`onnxruntime 1.23.2`, `get_available_providers()`=`[MIGraphX, CPU]`) and the runner binds it,
  but both steering gens (lo `--onset-density 3`, hi `12`; `--gain 3 --seed 42`) were forced to return mid
  **MIGraphX AOT compile** (~13–14 min, CPU-bound, no compile cache — ORT 1.23.2 rejects caching opts).
  No WAVs, no `[ort] sessions ready`/`[gen]` line → cos, node-level placement, on-GPU steering, RTF all UNMEASURED.
- **Tooling gap noted:** `dit_control_onnx_infer.py` emits **no** cos and only session-level EP
  (`get_providers()[0]`) — full DiT↔torch parity rests on export-time `_forward` cos=1.0 + CPU cos=1.0. The
  only node-level/cos-vs-torch check is `decode_onnx.py --report-placement --compare-torch` on the **decoder**
  (queued; runnable in mir venv with `PYTHONPATH=…/stable-audio-3`, expect decoder cos≈0.999998, 100% on-EP).
- **`precache_dit_cond.py` is broken on the current SA3 fork** (device cuda/cpu mismatch; KeyError `inpaint_mask`
  from `local_add_cond_ids`). Workaround: call `cdm.conditioner()` directly, assemble cross/global from cond_ids
  (`/tmp/precache_fixed2.py` → `/tmp/steerprompt.{cond,uncond}.npz`, cross `(128,768)`, mask sum 14/0).
- **To finish:** re-run the 3 queued commands (lo gen, hi gen, decoder `decode_onnx.py`), each pays its own
  ~10–15 min uncached MIGraphX AOT compile — do NOT kill. Then post-hoc onset density via `librosa.onset.onset_detect`.

## 2026-06-27 — Kim + Opus 4.8 — Control adapters bake into the DiT ONNX — onset steering on the low-VRAM path

- **A trained `sa3_control` control-adapter now runs as part of the ONNX DiT inference graph.** The adapter
  (decoupled cross-attn per DiT block + a scalar FiLM conditioner — `onset_FUSION_lr2e5_40epoch/soup_exppeak.pt`,
  field=onset_density) is a pure **forward** mod (no autograd/guidance), so it folds into the graph as two
  extra inputs: `control_tokens[1,16,768]` + `gain`. Tooling: `stable-audio-3/scripts/export_dit_control_onnx.py`
  + `dit_control_onnx_infer.py` (commit 6e46ec5, branch latch-sa3-phase1).
- **Validated (CPU):** ONNX vs controlled-torch **cos=1.000000** (adapter faithfully in the graph; threaded
  the adapter's module-global as explicit forward inputs → traces clean through torch.export), and differs
  from the plain DiT. **End-to-end steering works:** 8-step gen, requested onset density **3→measured 4.88,
  11→11.15 onsets/sec** (monotonic, calibrated; same prompt/seed, librosa). 
- **How:** cond pass feeds `enc((target−mean)/std)`, uncond pass feeds zeros (the trained null) — control rides
  CFG, exactly like `sa3_control/onset_eval.py`. The scalar→tokens FiLM is a 5-line numpy port saved as a
  `.cond.npz` (no torch at runtime). Adapter is length-agnostic (any ladder rung).
- **GPU-VERIFIED (MIGraphX, 2026-06-27):** control-DiT MIGraphX vs CPU **cos=1.000000, 100% on-EP, 294ms/call**
  (vs plain DiT 144ms — the 24 adapters add ~50%); on-GPU steering onset **3→5.00, 11→11.19** onsets/sec,
  **~4s/8-step gen** (matches CPU).
- **fp16 control-DiT FIXED + CPU is the recommended eval path (2026-06-27, commit 18c3aa7).** The bad
  ConstantOfShape was the adapter's `add_fractional_positions` PE → moved it **host-side** (export
  `position_encoding=False`, numpy PE in the runner; equivalent cos=1.0, gated). `--fp16` now converts
  (**3.1GB**, stamped); npz `host_pe=True` + onnx metadata stamp + runner assert guard a mismatched pair.
  **CPU-ONLY verified (Ryzen 9 9900X, frees the GPU for training):** onset-steered gen **~10s (8-step)+decode,
  ~2× realtime**, steers identically to GPU (onset 11→11.19). **Pin `--threads 12`** (physical cores, ~25%
  faster than 24 SMT). INT8 (CPU): 1.4–1.7× but cos 0.95 (audition; needs value_info-strip + MatMul-only to
  dodge a missing ConvInteger kernel) → fp32 already ~2× RT, keep INT8 for VST latency. Reconciled MASTER §5
  (a concurrent note had marked the GPU numbers unmeasured/fp16 broken — both now resolved).
  Doc: `stable-audio-3/docs/onnx-amd-inference.md`.

## 2026-06-25 — Opus 4.8 — CHROMA STEERS — first content control; completes the 3-way control taxonomy

- **Chroma steers (conclusive).** Trained an `other`-stem chroma LatCH head (temporal adaln_zero/d4, **cosine** loss,
  SAME `(3,128,T)`→384-ch; readout cos **0.89** temporal vs **0.14** linear — the §6 pattern again). A/B all-C vs
  all-F# + gain sweep, **re-measured with `same_chroma`**: separation grows monotonically (g64 +0.004 → g2048
  +0.053) and at **gain ~1536–2048 each palette makes its requested pitch class DOMINANT** in the decoded audio
  (C-steer→C, F#-steer→F#). The make-or-break (handoff §7) = **YES**. (g64 "MOVED:True" was a degenerate noise
  verdict — corrected by the sweep, house rule.)
- **The 3-way taxonomy (capstone):** **amount/density** (onset, RMS) steers at *moderate* gain (48–96);
  **content/pitch** (chroma) steers at *high* gain (~1536–2048); **structure/timing** (beat/downbeat) **doesn't**
  steer. Validates §8's dense-vs-sparse **and** the handoff's chroma-regularised-latent hypothesis.
- **Stem chroma data:** `compute_same_chroma` (mir-same-chroma, pure numpy/scipy) on each crop's `other`+`bass`
  stem window → `Lehto/latents_sa3_stem_chroma/` `(3,128,4096)` fp16, 4907/5400 (Lehto then full). The **right**
  chroma target (NOT the essentia `hpcp_ts`, wrong recipe → garbage).
- **Infra (committed):** `train_latch.py` `--target-source chroma` + `--loss cosine` (`fork` 5a32d1b);
  `latch_guided.py` cosine in the single-guide sampler (644c23c). Head + A/B wavs in `cu_reward_renders/analysis/`.
  Doc: AVP `findings/2026-06-25-chroma-steers-…`, `avp/main` eb28481.
- **Caveats / next:** needs very high gain (~20–40× onset); dominant-but-modest magnitude (req class ~0.11 vs
  0.083 chance, a *lean* not a *lock*); coherence at g2048 by-ear (sweet spot likely ~1536). Next: per-band
  bass-lock + melody-palette (handoff two-group UX), full_mix-vs-stem target compare, then LUMI scale.

## 2026-06-24 — Opus 4.8 — Beat + downbeat LatCH heads trained; train_latch.py now emits full wandb telemetry

- **Rhythm trio complete.** Trained **beat_activation** (loss 0.31→0.17) and **downbeat_activation** (0.24→0.18)
  LatCH heads — same recipe as the onset head (adaln_zero/d4/4.9M, standardized, smooth_l1, adamw, 12 ep) on
  `latents_sa3`. All three persisted at `cu_reward_renders/analysis/rhythm_heads/`.
- **Wired full telemetry into `train_latch.py`** (it had NONE → unmet standing requirement): `--wandb` adds
  per-step `TrainTelemetry` (per-layer norms / dist-init / weight-space trajectory / histograms) to **wandb
  project `sa3-latch`** (+ `--wandb-project/--run-name/--log-every/--layer-every`). Fork `latch-sa3-phase1` 70fda5d.
- **Gotcha (reusable):** `avp_sa3.sa3_control.telemetry.TrainTelemetry` wants the wandb **MODULE** (`wb.Histogram`/
  `wb.log`), NOT the `wandb.init()` **run** object — passing the run crashes at step 0 (`'Run' has no attribute
  'Histogram'`). Match `sa3_control/train.py`: `import wandb as wb; wb.init(...); TrainTelemetry(mod, wb, ...)`.
  Cross-repo: train_latch (sa3 repo) imports telemetry from the SAT repo via a sys.path insert (telemetry is
  torch-only → imports clean). wandb authed via ~/.netrc here.
- **STEERING RESULT (2026-06-24): beat/downbeat DON'T steer — trainability ≠ steerability.** Verified cross-venv
  with madmom (the extractor they were trained on): **constant target** → output beat-activation flat
  (0.0227→0.0223, slightly wrong way); **time-varying pulse target** (90/120/150 BPM, gain 96, no-BPM prompt) →
  output **≈ baseline** (wav |Δ|~1%, tempo 161.5 unchanged) — the guidance **barely moved the latent**.
  CONFOUND RULED OUT: beat/downbeat are **soft** (madmom probs) but the 100→10.767 Hz resample **compresses**
  them to **~0.21 max** (not ~1.0); the first pulse used peak 0.8 (+11σ OOD) → re-ran at in-dist peak 0.20 (=max),
  **still a no-op** → not a target-amplitude artifact. Onset
  (same code/gain) clearly moves it. **Diagnosis:** training-free latent guidance steers **dense amount** features
  (onset/RMS/brightness — strong dense gradient) but is a **no-op on sparse structural/detector** features
  (beat/downbeat placement — the head reads them but the per-frame gradient can't reorganise global structure).
  → **onset DENSITY is the steerable rhythm axis**; rhythm **structure** needs **trained beat-grid conditioning**
  (Music-ControlNet/MuseControlLite, Sourcebook Ch8/Ch11), not head guidance. Doc §8, `avp/main` a2f6dfe; null
  artifacts in `cu_reward_renders/analysis/beat_steer_null/`.
- **Next (multi-head + LUMI):** compose the *steerable* heads — onset + chroma + RMS — at independent gains; the
  controllability-map endgame is on LUMI (full-feature head sweep with this telemetry → DiT-block × feature map).
  Beat-grid *conditioning* (trained, not guidance) is its own track if rhythm structure matters.

## 2026-06-23 — Opus 4.8 — Onset LatCH head STEERS generation (corr 0.986) — working rhythm control, no MERT

- **Capstone of the rhythm thread.** Trained an **onset LatCH head** (`scripts/latch/train_latch.py --feature
  onset_envelope`, production arch: adaln_zero/depth4/4.9M, standardized, smooth_l1; 12 ep, loss 0.29→0.17,
  ~20 min) on `latents_sa3`, then steered `medium-base` via the production `model.generate(latch_configs=...)`.
  **The existing LatCH head arch is ALREADY temporal** (RoPE self-attn over the sequence) → no new arch needed,
  just train on a rhythm feature. (This is why §6's CNN matched MERT — the head family was always temporal; the
  per-frame *linear* probe was the artifact.)
- **Steering verified, closed loop:** requested onset 0.4→2.3 → measured output onset-strength rises
  **monotonically, corr 0.986** (gain 48). A/B render (same seed/prompt): baseline 0.771; gain 48 low 0.731/high
  0.834 (spread 0.10); **gain 96 low 0.702/high 0.907 (spread 0.21 ≈ 2× — authority scales with gain)**, pushing
  both sides of baseline. Audible A/B + the trained head + verifier persisted at `cu_reward_renders/analysis/`.
- **Net:** a temporal LatCH head on the SAME-L latent is a **working, gain-scalable rhythm control — no MERT, no
  MERT-conditioner, no base finetune** — the §6 prediction realised. Doc §7, `avp/main` a8984cf.
- **Next / reusable:** beat + downbeat heads same recipe; compose with chroma/RMS (multi-head endgame). The §3
  per-frame steerability map is a **linear lower bound** → re-probe *temporally* before calling any feature
  "hard." Ops: `verify_latch.py` is rms-only; the onset verifier in `analysis/` is the template for new features.

## 2026-06-23 — Kim + Opus 4.8 — SA3 DiT → ONNX on AMD: full text→audio reproduces torch (GPU-verified)

Extended the SAME ONNX/AMD work (decoder/encoder, prior entries) to the **DiT** — the full
text→audio path now runs on ORT+MIGraphX. Tooling in `stable-audio-3/scripts/`: `export_dit_onnx.py`,
`dit_onnx_infer.py` (host rectified-flow sampler), `precache_dit_cond.py`. Doc:
`stable-audio-3/docs/onnx-amd-inference.md`. Commits `e310a4b..7f6c220` (branch `latch-sa3-phase1`).
- **Export = `DiffusionTransformer._forward` (CFG-free core), DiT-only load** from the cached
  safetensors (no T5-Gemma needed; text is precached). Same recipe as the AE (flash-off + opset 18);
  the DiT was *structurally friendlier* (no chunk-folding, global self-attn → plain SDPA). CFG + Euler
  sampler on the host; CFG collapses to velocity space `v=v_unc+cfg·(v_cond−v_unc)`.
- **CRITICAL FIX (now MASTER §5):** medium-base DiT needs a **257-ch `local_add_cond`** (inpaint_mask +
  masked_input). For text-to-audio it's zeros, but the DiT **projects it with a bias** → `None ≠ zeros`
  (cos 0.98). First export wrongly omitted it (false cos=1.0 None-vs-None). Fixed → input fed zeros.
- **Validated:** corrected DiT export vs torch cos=1.0; **MIGraphX vs CPU cos=1.000000, 100% on-EP,
  191ms/call** (~13min compile); **full 8-step real-prompt gen ONNX z0 vs torch z0 cos=0.999944**; real
  structured audio. **DiT-only RTF ≈7.8×.** Ladder exported L∈{256,512,1024,2048,4096}.
- **Gotchas (MASTER §5):** t5gemma `b-b-ul2` (gated) — HF **Xet stalls**, fetch via `HF_HUB_DISABLE_XET=1`
  / `curl -C-`. **Don't co-resident fp32 DiT (~5.8GB)+decoder on 16GB** → VRAM saturates, decoder compile
  thrashes (31min vs 9min).
- **Follow-up (same session): batch=2 + fp16 export, bench + gen-server, + a VRAM correction.**
  `export_dit_onnx.py --batch 2` (one DiT call/step CFG, cos 1.0) + `--fp16`. `bench_dit_onnx.py`
  (ONNX-vs-torch gen benchmark, fairness-reviewed) + `latent_server_dit_onnx.py` (low-VRAM gen server).
  **CORRECTION to the VRAM fix:** `migraphx_fp16_enable` (runtime fp16 EP) does NOT help co-residency —
  it loads the fp32 weights then quantizes at init, so DiT+decoder **OOMs harder** (HIP OOM, measured).
  The real fix is **fp16-EXPORTED onnx files** (DiT 2.9GB + decoder 0.9GB load directly) or separate
  processes. fp16 DiT export needs `convert_float_to_float16_model_path` + external-data save (>2GB).
- **BENCHMARK (2026-06-24, GPU free) — the ONNX/MIGraphX port is a VRAM/deployment win, NOT speed.**
  L256/8-step DiT loop (decode excluded — unfair across venvs): **torch eager cuda-fp16 0.707s (44ms/call,
  RTF 33.6×)** vs **ONNX-fp16 MIGraphX 2.314s (144ms/call, RTF 10.3×)** → **eager torch ~3.3× faster**
  (MIGraphX's compiled graph doesn't beat torch's tuned rocBLAS/MIOpen here; torch+CK-FA would widen it).
  Quality identical (z0 cos 0.9993). ONNX's value = **3.8GB resident, zero torch/ROCm-torch dependency**
  (coexists with training, portable single graph) — the original low-VRAM motivation. fp16 ~25% faster
  than fp32 MIGraphX. **Use ONNX for low-VRAM coexistence; torch for raw speed.** Server CPU-smoke passed
  (boot→/generate→valid 23.8s WAV). Tools: `bench_dit_onnx.py` (added `dit_loop_s`), `latent_server_dit_onnx.py`.

## 2026-06-23 — Opus 4.8 — Curated-reference reward viable; SAME-L steerability map measured (rhythm is the weak axis)

- **Curated reference set = a genre-neutral reward** (the way past Audiobox's genre bias). 48 aavepyora tracks
  (`/run/media/kim/Lehto/aavepyora_flac/`) MERT-embedded vs contrasts: **AUC 0.999 vs default SA3 output**
  (1-NN purity 0.97 — strong steering gradient), **~0.87 within-genre vs goa at MERT layers 5–6** (timbre/
  production; layer 23/semantic only 0.77 — can't tell two goa apart). Use **layers 5–6, mean-centred**
  (MERT space is anisotropic, raw cosines ~0.95); **48 tracks suffice — the limit is the metric, not data**.
  Caveats: goa contrast is SAME-L-reconstructed → 0.87 is an upper bound; embed references **through a SAME-L
  round-trip** to make the reward codec-fair (generations are decoded too).
- **SAME-L steerability map** (200-crop per-frame ridge `latent→feature`, split by track; CPU): negative
  control `relative_position`=**0.044** (probe is honest). **Easy:** spectral flux 0.88, flatness 0.80.
  **Medium:** bass-energy 0.50, **chroma 0.42** (matches chroma-steer needing ~15× gain), air-energy 0.35.
  **Hard:** onset 0.31, beat 0.30, **downbeat 0.16**, mid/body energy ~0.11. **Rhythm is the weakest family
  → this EXPLAINS the riffer's rhythm-transfer failure (MERIT≈0): the bare latent doesn't linearly carry
  downbeat.** (Per-stem features dropped — absent in some crops; stemmed-only re-run pending.)
- **Multi-band MERT-conditioner design** (the next-control idea): ~3–5 MERT-layer *bands*, each a GLIGEN-gated
  decoupled cross-attn adapter (gate→0 = off; strength slider = on/off UX), pooled-global, self-supervised on
  `latents_sa3` — a multi-band extension of the riffer. Gated by SAME-L (only surfaces tangled-but-present
  features, not discarded), and "explicit beats opaque" (complement the scalar heads).
- **MERT-vs-SAME-L probe RUN (same day, GPU): MERT exposes rhythm the bare latent hides.** 80 goa windows
  decoded→MERT, per-frame probe vs the SAME-L latent: **beat 0.36→0.83, onset 0.33→0.71, downbeat 0.17→0.39**
  (all at **MERT layers ~1–6**); spectral-flux tie (~0.85), chroma SAME-L wins (0.42 vs 0.37); neg-control <0.1.
  → the precondition holds **for rhythm only** → the multi-band conditioner collapses to a **single rhythm band
  (MERT L1–6)**, and this is the concrete fix for the riffer's rhythm failure. Rhythm is *present-but-nonlinear*
  in the latent, so the cheaper **alternative is a nonlinear MLP rhythm head on the SAME-L latent** (target-driven)
  vs the MERT band (reference-driven) — likely both. Doc §5 updated, `avp/main` 6f0aa36.
- **CORRECTION (same day): a temporal latent head matches MERT — you DON'T need MERT for rhythm.** Built §5's
  head as a **1D-CNN** (~4s context): **beat 0.86, onset 0.81, downbeat 0.58** vs MERT's linear-probe
  0.83/0.71/0.39. Per-frame MLP barely helped (downbeat 0.03 — failed); only temporal context recovers rhythm.
  → the §3/§5 ceiling was **missing temporal context, not absence**: the latent never hid rhythm, the per-frame
  LINEAR probe couldn't see it; MERT "won" only because it's temporal and the probe wasn't. **Verdict: rhythm
  control = a temporal (1D-CNN) LatCH head (no MERT, no finetune); MERT's niche narrows to the reference-STYLE
  reward.** General lesson: **LatCH heads for temporally-structured features must be temporal, not per-frame**;
  the per-frame steerability map (§3) is a linear lower bound. Doc §6, `avp/main` 09e18a6.
- **Docs:** finding written to AVP `docs/book/findings/2026-06-23-curated-reference-rewards-and-the-same-l-steerability-map.md`
  (+ findings README + advances Sourcebook §Ch13/§Ch8), pushed `avp/main` c1e4f46. Recipe `fk-steering-cu`
  already updated 2026-06-22. Ops: MERT-v1-330M loads on the ROCm sa3 .venv (`trust_remote_code`, ~163 s).

## 2026-06-22 — Opus 4.8 — Audiobox-aesthetics as an SA3 reward: confirmed on medium-base (240 samples)

- **Question:** is Audiobox CU (Content Usefulness) a good steering reward for SA3 (toward the FK-steering
  recipe `avp_sa3/recipes/inference_recipes.yaml` `fk-steering-cu`)? Ran best-of-N (rung 1 of the ladder)
  on **medium-base, 240 samples / 10 genres**, scored all 4 axes (mir `audiobox_aesthetics.py`).
- **CU ≈ PQ (robust):** within-prompt CU↔PQ **+0.87** across every genre (+0.66..+0.95). "Usefulness" is
  essentially a **production-quality** signal, not a distinct reusability axis.
- **No quality/complexity tradeoff:** PQ↔PC **+0.25** (genre-dependent −0.36..+0.71). The **−0.26 seen on
  n=8 small-base did NOT replicate** — it was small-sample noise. Higher complexity doesn't cost quality.
- **The orthogonal lever is complexity/enjoyment:** CE↔PC **+0.62** (busier = more enjoyable, within genre);
  **PC reads arrangement density** (ambient/piano ~2.5 vs lo-fi/house ~5.6). All 4 axes +corr within-prompt
  → a weighted **hybrid won't fight itself**. CE has the widest meaningful headroom — best single "good music" reward.
- **Reward choice is NOT moot despite correlation:** BoN argmax differs (CU-winner ≠ PQ 8/10 prompts, ≠ PC
  10/10) — the top sample under each reward differs even when axes correlate.
- **Ops facts (reusable):** medium-base loads 12.7 s (flash_attn 2.8.4), **~9.7 GB VRAM loaded** → can't
  coexist with Audiobox (~8 GB) → score sequentially. **TunableOp cache does NOT persist across processes**
  (`apply_profile`-after-import warning is real): first gen of a (batch,dur) shape tunes ~7 min, then
  **2.24 s/sample** steady-state — so do a whole run in ONE process. 240 samples in 16.2 m.
- **Next:** FK particle loop still unbuilt; if pursued, target CE or a PC-with-PQ-floor hybrid, not CU. Recipe
  updated to BoN-tested (`avp/main` 0d7cfdd).

## 2026-06-22 — Opus 4.8 — Branch consolidation + AudEdit findings doc; Gradio_Lab parked (pre-SA3)

- **Repo roles clarified** (now durable in `MASTER.md` §1 "Separation of concerns"): mir = features +
  the latent-explorer-becoming-a-tool; AVP = model-agnostic *what* of control; SA3 = thin fork = the
  *how* to interface with the SA3 model, changed only for components upstream lacks.
- **Consolidated to main + pruned branches** (relief for branch sprawl): mir `main` ← merged
  `sa3-latent-explorer` (incl. whole-track-timeseries) + `same-chroma` (SAME chroma extractor +
  `gen_same_chroma_ts.py`), pushed `Taikakim/mir-feature-extraction`. Deleted **8 local + 6 remote**
  stale branches (all proven merged). `.gitignore` now excludes wheels/`data/`/`renders/`/`*.pt` sweeps
  across mir + AVP. SA3 left as-is (its `latch-sa3-phase1` is 54-ahead/28-behind fork-main → needs a
  careful reconcile, not a sweep).
- **AudEdit (2606.15149) finding landed** in AVP `docs/book/findings/2026-06-22-audedit-into-our-control-stack.md`
  (+ Sourcebook cross-link), pushed `avp/main`. Verdict: complement-not-substitute; `sa3_flowsep.py` is
  already a near-faithful Algorithm 1; highest-leverage next is a cheap **entanglement probe**, not the
  data-engine. Codec caveat: paper SAME=32-ch vs our SAME-L=256-ch.
- **`avp/Gradio_Lab` NOT merged — parked.** It's **pre-SA3** work (Kim's Stability-AI gradio UI tweaks:
  model loading, dual-model **bracketing**, presets). 4 months stale; AVP's `interfaces/diffusion_cond.py`
  has since diverged (LatCH/sigma), so it's a genuine **manual reconciliation** (overlapping CFG-slider
  edits; unify `generate_cond`'s `*sampler_selections` varargs vs `latch_*` kwargs + the flat Gradio
  inputs list) that **needs a GUI launch-test** → blocked by the busy GPU. `gradio.py` itself merges
  clean (main never touched it). Do it as a focused launch-testable session later; drop `claude.log`,
  keep main's `CLAUDE.md`/`README.md`/`train.py`.

## 2026-06-21 — Opus 4.8 — Long-form SA3 generation MERGED — GPU-validated, drift-free

- **MERGED to `Taikakim/stable-audio-3` main** (PR #1, merge commit `378b0a6`; 17 commits preserved:
  spec → plan → TDD tasks → review fixes → doc). Sliding-window **inpaint-continuation + crossfade** —
  render longer than SA3's native window, drift-free by construction (every window a fresh in-distribution
  generation latent-clamped to the previous tail).
- **GPU-validated** (`small-music-base`): 18/18 CPU tests + 2 GPU generation tests pass; 2-min render
  `drift_log` RMS **flat [1.03, 0.95, 0.75, 0.83, 1.04]** — no collapse. The earlier **FIFO/diagonal-denoising
  prototype** (`fifo_infinite.py`) cratered to **~0.03 at ~18 s** → sliding-window beats per-frame FIFO on the
  untrained model.
- **Finding:** SA3 inpaint **SOFT-conditions** the prefix (clamp-region mean-abs err **~0.064**), NOT a hard
  clamp → the `continuation_join` slerp seam blend is load-bearing.
- Self-contained (no `fifo_infinite` dependency). Files: `stable_audio_3/inference/longform.py`,
  `scripts/longform_render.py`, `tests/test_longform.py`, `docs/workflows/longform.md`. FIFO kept as the
  future **Approach-C** engine behind the swappable `ChunkGenerator` seam. Built via superpowers
  subagent-driven-development (TDD + per-task + whole-feature review). CLI: `uv run python
  scripts/longform_render.py --prompt "..." --duration 120 --window-sec 30 --overlap-sec 5 -o out.wav`.

## 2026-06-20 — Opus 4.8 — Attribute branch VALIDATED: onset-density head steers output (corr +0.90); riffer = variation-not-transfer

- **THE pivot result:** an explicit **onset-density** scalar head steers SA3 output onset density at
  **corr +0.90** (gain 1): requested sparse→dense → measured 4.3→8.3 onsets/sec; gain 0 flat 7.2
  (control off); gain 2/4 overdrive into incoherence. **Explicit conditioning works where the opaque
  riffer reference failed (MERIT ≈ 0)** → riffer's failure was the opaque signal, not the plumbing.
  Code: `avp_sa3/sa3_control/` — `ScalarAttributeEncoder` (FiLM tokens), `--control-mode scalar`,
  dataset per-crop `.json` scalar, `onset_eval.py` (re-extract density via librosa). Heads at
  `Lehto/sa3_control_runs/onset_density_400trk_crop1024/`. Smoke gotcha: `--smoke` forces fp32 →
  OOMs 16 GB; real runs are bf16. Next: time-varying onset_envelope_ts curve, then **compose heads**
  (riffer + onset, independent gains) — the endgame.
- **Riffer reframed (not dead):** comprehensive MERIT (480 clips, all models, gains 0.1→8) = the
  opaque riffer does NOT transfer mel/rhy/tim; high gain → distortion. BUT it's a real
  **reference-conditioned variation** instrument (kick-in threshold ~gain 0.6; narrow real *timbre*
  transfer only at the most-trained ckpt). Retrained full-effect at 400trk/lr1e-4 (12 ckpts) to test
  if more-data/lower-LR smooths the effect.

## 2026-06-20 — Opus 4.8 — Riffer LR/optimizer bracket + MERIT eval wired; 3 ref repos mined

- **Optimizer bracket** (200 tracks, `avp_sa3`): AdamW (2e-4/4e-4/6e-4+warmup, crop2048) vs
  **FusionOpt** (`Taikakim/fusion-optimiser`) SF-NorMuon / SF-AdamW / 5e-5, crop1024 (FusionOpt
  **OOMs at crop2048 no-ckpt** → crop1024 fix). **Fusion tax confirmed, matched-crop:** SF-AdamW
  1.46 it/s > SF-NorMuon 1.31 (NS5/NorMuon overhead) — both faster than AdamW@2048 only via crop.
  `train.py` gained `--optimizer adamw|fusion|sfadamw|fusion_full`, `--warmup-steps`,
  `--timestep-sampler` (log_snr, underfit borrow), `--resume` (warm-start). Collapse map → pick best
  by **cross-ref-diff**, then a **full-data crop-512 run** sized to finish by morning.
- **MERIT eval wired** (`sa3_control/merit_eval.py` + bracket `MERIT_EVAL=1`): MERT-330M + 3 heads →
  **S_mel/S_rhy/S_tim** disentangled similarity → per-checkpoint `merit_margin` (transfer−leak per
  factor; >0 = riffer transfers *that* factor). **Fixes the metric crisis** (chroma blind to collapse,
  cross-ref-diff blunt, loss noise-dominated). Runs CPU; validated. Heads in `Projects/MERIT/models`.
- **3 reference repos cloned to `Projects/` + mined** (all SA3-relevant): **underfit** (dada-bots LoRA
  dashboard → DoRA, short-crop/47s, log_snr sampler, the "elbow=creatively-underfit" recipe);
  **audioscope** (mech-interp activation steering → free mood vectors from our essentia labels + the
  per-layer probe = attribute-branch *injection-layer* diagnostic; `@torch.compile` monkey-patch gotcha);
  **MERIT** (the eval above). Folded into `avp_sa3/sa3_control/ATTRIBUTE_BRANCHES.md` (next-milestone design).



Exported the SAME-L autoencoder to ONNX for low-VRAM AMD inference via ORT + MIGraphX (a
decode path that runs without the torch stack / alongside a training job). Tooling in
`stable-audio-3/scripts/`: `export_same_onnx.py` (export+validate) + `decode_onnx.py` (host
chunk-loop runner). Doc: `stable-audio-3/docs/onnx-amd-inference.md`. Commit `3e5a9eb` (branch
`latch-sa3-phase1`). CPU validation (ORT vs torch): **decoder L128 cos=0.99998, encoder L128
cos=0.999996** (mean|Δ| ~5e-4 / ~9e-3; the encoder's larger abs Δ is just latents' wider range
— judge by cos/relative, not an audio-calibrated threshold).
- **Key: don't export varlen.** SAME folds the sequence length-dependently; export the
  *fixed chunk* (`decode` on `[1,256,L]`) and loop+overlap-add on the host (port of
  `AudioAutoencoder.decode_audio(chunked=True)` — `decode_onnx.py` does this).
- **Two gotchas (now in MASTER §5):** flash-off alone routes to **FlexAttention** (unexportable
  HOP, dies on `bitwise_and`) → also set `transformer.flex_attention_available=False;
  flex_attention_compiled=None` for math-equivalent masked-SDPA; and **opset ≥ 18** (17 emits an
  invalid `Split(num_outputs)`). `onnxscript`/`onnxruntime` install is additive (no torch/numpy bump).
- **GPU-VERIFIED (2026-06-20, RX 9070 XT, mir venv `onnxruntime_migraphx` 1.23.2):** the SAME
  decoder runs **100% on the MIGraphX EP, zero CPU fallback** (`--report-placement`), numerically
  identical to torch (**cos=0.999998**, max|Δ|=2.8e-4), at **RTF ~39×** post-compile. → **ONNX
  inference on AMD is verified.** The SA3 venv's own `onnxruntime` (1.27) is CPU-only — run the
  GPU EP from the mir venv or `uv pip install onnxruntime-rocm`.
- **THE catch: ~9-min MIGraphX AOT compile per session** (CPU-bound — NOT exhaustive-tune [tried
  off] nor chunk size [same at L32 vs L128]; the masked-SDPA fallback expands into many attention
  ops MIGraphX chews on). **ORT compiled-model caching is NOT exposed in this `onnxruntime_migraphx`
  1.23.2 build** (`migraphx_save/load_compiled_model` + `_model_name`/`_model_path` all rejected →
  silent CPU fallback; `decode_onnx.py` now detects that & retries on the bare GPU EP). Real
  mitigation: **a long-lived server compiles once at boot** (the latent_server pattern) → per-request
  cost is nil; or a newer ORT-ROCm build with cache options.
- **Seam test PASSES** (overlap=16, 512-latent/4-chunk): torch chunked≈unchunked (cos=1.000004) →
  overlap≥receptive field; ONNX-chunked vs torch-UNCHUNKED **cos=0.999997**, per-boundary local
  max|Δ| (1.5–3.5e-4) = same order as elsewhere → **no seam**. Stitch is EP-independent (run on CPU,
  no GPU contention with the riffer bracket) so it also covers MIGraphX (per-chunk cos=0.999998).
  → **full ONNX-on-AMD decode path verified end-to-end.**
- **Wired into the explorer:** `mir/scripts/latent_server_onnx.py` (mir branch `sa3-latent-explorer`,
  commit c854edc) — low-VRAM ONNX decode player (~2 GB GPU, MIGraphX, runs alongside training),
  endpoint-compatible with the torch `latent_server_sa3.py` (/status /crops /meta /decode /mix
  /source; /steer→501, stays on the torch player). Compiles the ONNX once at boot. Viewer targets
  it via `SA3_PLAYER_PORT=7893` (`player_client` now env-configurable). CPU-smoke-tested
  (decode/mix/status serve); GPU path is the same session with `--provider migraphx`.
- Context: cgisky `stable-audio-3-rs` (cloned to `Projects/stable-audio-3-rs`) proves SAME ONNX/MNN
  export works (CUDA/Windows); our path is ONNX + ORT-MIGraphX on AMD instead.

## 2026-06-19 — Opus 4.8 — SA3 riffer validated; pivoting to attribute-branch control
- **`avp_sa3/sa3_control/` riffer** (decoupled cross-attn adapter on SA3 medium-base) works,
  but only **reference-specific at lr1e-4** (peaks step~6000, then "elbow"-declines); **heavier
  LR mode-collapses** (lr1e-3 collapsed by step6000). Metric lesson: **chroma corr can't see
  collapse — use cross-reference AUDIO diff**; RF loss is a non-metric (flat for both). Gain knob
  ~1–2 clean, >4 artifacts (SA3-medium needs gain>1, the LatCH lesson).
- **Save audio via `soundfile` PCM_16**, never `torchaudio.save` — torchcodec is absent on the
  7.14 venv (ImportError) and clips fp16 where present. (`sa3_control.audio_io.save_audio`; MASTER §5.)
- Running overnight: 200-track LR×optimizer bracket (AdamW / FusionOpt SF-NorMuon / SF-AdamW;
  FusionOpt OOMs at crop2048 no-checkpoint → run at crop1024). Borrowed `--timestep-sampler`
  (log_snr) + the short-crop lever from **dada-bots/underfit** (cloned to `Projects/underfit`).
- **NEXT MILESTONE (decided): attribute branches** = explicit time-varying MIR-feature control of
  SA3 — the actual differentiator (leverages the mir pipeline; nobody else can). Design:
  `avp_sa3/sa3_control/ATTRIBUTE_BRANCHES.md`. Eval is *measurable* (decode→re-extract→correlate).
  Align with `mir/plots/explorer_sa3/` (same data; its LatCH `/steer` = the training-free twin).

---

## 2026-06-19 — Kim + Opus 4.8 — SA3 latent explorer (viewer + decode/mix/steer player), GPU-validated

Built an SA3-only latent viewer + player on **mir branch `sa3-latent-explorer`** (the old 64-d
Small explorer/player stay on other branches as a reference, untouched). Purpose: review SAME-L
encoder quality on `latents_sa3` + latent-space DJ mixing + LatCH-head auditioning.
- **Two processes:** Dash viewer `mir/plots/explorer_sa3/` (mir venv, port 8051, reads
  `.json`/`.TIMESERIES.npz` sidecars directly — sidecars are the only feature source) ⇄ HTTP ⇄
  player `mir/scripts/latent_server_sa3.py` (SA3 venv, port 7892, owns SAME-L VAE + LatCH heads).
  Config `mir/latent_player_sa3.ini`. Spec/plan in `mir/docs/superpowers/{specs,plans}/2026-06-19-*`.
- **GPU-validated** on the RX 9070 XT: `/decode` (380.4 s chunked reconstruction), `/mix`
  (slerp latent interp of two crops → decode), `/meta`, `/status`. `/source` (original-audio A/B
  slice) works only with **Mantu mounted** (source_path lives there) — correct 500 otherwise.
- **`/steer` fix worth reusing:** the hardcoded `LatCH(dim=256,depth=6,num_heads=8)` couldn't load
  the production same-l heads (`latch_weights_sa3_medium`, depth 4 / adaln_zero / standardized).
  Now loads via `stable_audio_3.models.latch.load_latch_from_checkpoint` (auto-detects arch);
  default `latch_weights_dir` → `latch_weights_sa3_medium` (the dir with `_best.pt`). 14 heads
  list; steering changes the audio (gain ≈48–96, MASTER §5). See MASTER §5 head-family gotcha.
- Built via subagent-driven TDD: 9 tasks, per-task + whole-branch review, 24/24 non-GPU tests.

## 2026-06-19 — Kim + Opus 4.8 — SA3 long-form render (sliding-window + crossfade) implemented & reviewed; GPU validation pending

Built the **offline long-form generation** feature on SA3 (branch `latch-sa3-phase1`,
commits `5f6f808..796a76d`, 14 commits, pushed to `fork`). This is the productionised
successor to the FIFO prototype: instead of one OOD FIFO stream (which drifts/collapses
after ~18 s), it renders **overlapping windows, each latent-clamped to the previous tail
via SA3 inpainting, stitched with slerp crossfades** — drift-free by construction.
- Files: `stable_audio_3/inference/longform.py` (PromptSchedule, slerp+CrossfadeStitcher,
  DriftMonitor, ChunkGenerator seam + InpaintContinuationGenerator + SDEditReanchor,
  LongFormRenderer), `scripts/longform_render.py` (CLI: prompt or `t:prompt|...` schedule),
  `tests/test_longform.py`. Docs: `docs/workflows/longform.md`,
  spec/plan under `docs/superpowers/`.
- **Swappable `ChunkGenerator` seam:** Approach A (inpaint-continuation) ships now;
  Approach C (`BoundedFifoGenerator`, the FIFO surgery) drops in behind the same interface
  after a finetune. `SDEditReanchor` built (latent audio2audio re-noise→denoise) but reserved
  for opt-in transition morph / C's drift refresh.
- Built via subagent-driven-development (fresh implementer+reviewer per task, 2-stage gates).
  Reviews caught & fixed real bugs: slerp endpoint imprecision, an `n==0` transition crash,
  a `parse_schedule` colon-prompt crash, and (final whole-feature review) **missing [-1,1]
  output clamp** (MASTER.md §5 clip gotcha), **single-shot decode OOM** (now `chunked=True`),
  NaN-retry/fail-fast + a drift canary, and **transition windows were clamping to the OLD
  prompt's tail** (fixed → fresh chunk on transitions).
- **Status: CPU 18/18 green, ruff clean. GPU render NOT yet runtime-validated** — dev box
  VRAM held by a control-head training run. GPU-gated tests now skip cleanly on low VRAM.
  Merge deferred until outputs verified. Validate when free: `uv run pytest
  tests/test_longform.py -v` + a 2-min CLI render (acceptance = flat `drift_log` rms).
  Recovery map: `stable-audio-3/.git/sdd/progress.md`. Details: [[infinite-audio-fifo-sa3]].

## 2026-06-18 — Kim + Opus 4.8 — InfiniteAudio FIFO prototype for SA3 (written+reviewed, UNTESTED); forage-dj vs mir beatmatch

Ported InfiniteAudio (arXiv:2506.03020) long-form / FIFO "diagonal denoising" to SA3 on
branch `latch-sa3-phase1`. Files: `docs/INFINITE_AUDIO_FIFO.md`,
`stable_audio_3/inference/fifo_infinite.py`, `scripts/fifo_infinite_smoke.py`.
- **Finding:** SA3's DiT only accepts a *scalar-per-batch* timestep (`dit.py:239`, folded
  into adaLN global cond). True FIFO needs *per-frame* σ `(B,T)` → requires model surgery
  and is **out-of-distribution** (untrained). Not a sampler swap. Live config (small-music-base):
  patch_size=1, timestep_cond_type=global, global_cond_type=adaLN, num_memory_tokens=64,
  downsampling_ratio=4096.
- Surgery = guarded monkeypatch making adaLN per-token (3 injection points, delegates the
  long methods; scalar path byte-identical). CFG done manually (2 cfg=1.0 passes) since the
  DiT's internal CFG assumes scalar sigma.
- **Status: NOT run (GPU was busy).** Adversarial-review workflow (5 lenses, 38 agents)
  found 18 issues — all fixed. Core surgery (delegation, shapes, signs) verified correct.
  First validation: `fifo_infinite_smoke.py --parity` (gate on REL err <5e-3; ROCm GEMM
  floor ~1e-3..1e-2 abs). Biggest expected failure = **rotary positional drift**. Fallback
  if too OOD: sliding-window inpaint-continuation (no surgery). Details: [[infinite-audio-fifo-sa3]].
- **forage-dj** (cloned to `/home/kim/Projects/forage-dj`): its "long-form" is just
  generate-fixed-tracks (≤47–60s) + DJ equal-power crossfade (`src/foragedj/mixer.py`) —
  **nothing reusable** for continuous diffusion. And mir's `scripts/latent_server.py`
  `beatmatch_crossfade_to_wav` (downbeat-grid tempo match via `.DOWNBEATS`, phase-lock,
  latent-space crossfade) is **strictly more advanced** than forage-dj's fader — no port up.

## 2026-06-18 — Kim + Opus 4.8 — SA3 generative source separation: FlowEdit works, true inversion is cfg-fragile

Built two text-prompted separators on SA3 `medium-base` (rectified flow), both in
`stable-audio-3/scripts/`. Context: the old `mir-same-chroma/scripts/sa3_zerosep_lite.py`
was plain **SDEdit** (init_audio+init_noise_level → one linear noise blend), which is why
its outputs followed the prompt but had **no tie to the input**.
- **`sa3_flowsep.py`** — inversion-FREE FlowEdit/AUDEDIT (arXiv:2412.08629 / 2606.15149).
  Keeps z_edit=x0, integrates the difference field `v(z_tar,target) − v(z_src,source)` along
  SA3's schedule, skipping the high-noise head (`--n-max`). Monkeypatches
  `sampling.sample_discrete_euler` for one `generate()` call (reuses cond/varlen/decode);
  builds source+target cond via `conditioner`+`get_conditioning_inputs`. cfg_src 3.5 /
  cfg_tar 13.5, n_max 33. **Robust to high cfg** (shared noise cancels) → stays anchored.
- **`sa3_zerosep_rf.py`** — true RF-Solver inversion (arXiv:2411.04746): reverse-Euler +
  2nd-order Taylor invert x0→noise at cfg=1, round-trip gate, then prompt-swapped re-denoise
  (cfg swept off the shared inversion). Inversion is **near-transparent** (eps std 1.006,
  latent round-trip rel err **0.229**, reconstruction env-corr **0.967**). But separation is
  **cfg-fragile**: cfg 8 collapsed (env-corr 0.05–0.11, prompt-prior dominates); sweet spot
  ~cfg 2 (0.10–0.28).
- **A/B (Acid Alien 400–410 s, env-corr ↗ mix):** FlowEdit lead/bass/drums 0.90/0.32/0.18
  vs RF best ~0.28/0.13/0.21. FlowEdit anchors better; RF gives cleaner instrument timbre
  (RF bass centroid 931 Hz vs FlowEdit 3030 Hz) but re-imagines more.
- **Takeaways:** (1) real ZeroSep = edit-friendly **DDPM** inversion, does NOT port to flow
  matching — the flow analogue is RF/ODE inversion, or (better here) inversion-free FlowEdit.
  (2) Must use a **-base** checkpoint (post-trained = stochastic ping-pong, cfg inert).
  (3) **cfg≈1 for inversion** — high cfg ruins recoverability (MusRec); asymmetric cfg
  (low invert / bounded regen) is mandatory. (4) Both are generative re-synthesis, **not
  masking** → not clean stems; for clean drums/bass use mir Demucs/BS-RoFormer. Generative
  value = **open-vocab** extraction ("isolate the acid lead"). (5) **env-corr ↗ mix is only a
  faithfulness proxy for the DOMINANT source** — on a full-arrangement window all isolated
  sources score low (each is only a part of the mix); honest non-dominant eval needs
  reference stems.
- Full discography (real-music test corpus) downloaded to `/home/kim/Projects/discography_flac`
  (`aavepyora-2017-discography` FLAC subtree, 284 tracks).
- **Update — η faithfulness controller added to `sa3_zerosep_rf.py`** (fixes RF-Solver's
  "clean but far from input"). On the re-denoise, pull predicted-clean `z0 = x − t·v`
  toward the encoded mixture: `z0 ← (1−η)·z0 + η·x0_src` for `t ≥ τ` (τ=0.3), rebuild
  `v = (x − z0)/t`. **First tried the RF-Inversion `(anchor−x)/(1−t)` field — wrong sign +
  blows up at t→1 under SA3's descending-t Euler** (centroids exploded, near-silent); the
  z0-anchor (the SA3 mean-guidance form from `latch_guided`/`steer_chroma`) is stable.
  η-sweep env-corr↗input (Acid Alien lead 400 s) — **a clean monotone dial:** bass
  0.10→0.72→0.92→0.97, lead 0.09→0.90→0.97→0.97 across η = 0/0.3/0.5/0.7. **η≈0.3–0.5 =
  separation sweet spot** (anchored but still prompt-shaped); η≈0.7 over-anchors → its
  centroid hits the full-mix centroid = just rebuilding the mix. Committed to SA3 fork
  `latch-sa3-phase1`.

## 2026-06-01 — Kim + Opus 4.8 — SA3 DoRA finetune staged + a GPU-wedge lesson (cost the run)

DoRA dim-128 (`dora-rows`) finetune of SA3 `medium-base` on a 300-track / 607-crop subset
(`/run/media/kim/Lehto/latents_sa3_lora300`, symlinks). `scripts/train_lora.py` extended
(backward-compat) with `--epochs`, `--accumulate_grad_batches`, `--gradient_clip_val`,
`--checkpoint_every_epochs` — `DiffusionCondTrainingWrapper` uses **automatic** optimization,
so Lightning grad-accum is live. Launch staged: `/tmp/launch_dora.sh` (rank128, 30 ep, eff
batch 128 = micro 1 × accum 128, ckpt/5ep, `--no_demos`). Fits 12–13 GB at T=4096.
- **First run trained fine** (~2 s/microbatch at T=4096, loss decreasing, CSV-logged).
- **LESSONS (these cost the run):**
  1. Lightning's tqdm is **SILENT in a non-TTY** — the progress signal is the CSV at
     `lightning_logs/version_N/metrics.csv` (read the **newest** version dir — a relaunch makes
     a new one). Don't kill a working run to "fix monitoring."
  2. **Repeatedly hard-killing a multi-GB GPU process WEDGES the HIP runtime** — every
     subsequent run loads the model (12 GB, GPU 99%) but hangs on a stuck kernel
     (`futex_do_wait`, no optimizer step) even with the *identical config that just worked*.
     GPU returns to clean-idle between runs but won't train. Recovery = `sudo rocm-smi
     --gpureset -d 0` (needs sudo; unavailable unattended) or reboot.
  3. Setting `MIOPEN_FIND_MODE` in env also froze a run (mir CLAUDE.md warns this).
- TODO after GPU reset/reboot: `bash /tmp/launch_dora.sh`. Full T=4096 ≈ 9 h for 30 ep; add
  `--duration 100` (T≈1076) to fit a session. Then the FusionOpt-vs-AdamW comparison.

## 2026-06-01 — Kim + Opus 4.8 — probed the 2 un-probed timeseries fields: beat is NOT dead

Ran the ridge decodability probe over ALL 21 latents_sa3 timeseries fields (was 19; the only
gap was `beat_activation` + `downbeat_activation`, skipped on the SAO-Small §9 "beat = dead
control" assumption). `/tmp/ridge_probe.py` (N=400, SEED=0, track-disjoint) →
`/tmp/sa3_autotests/ridge_probe_all.log`. The 19 prior features reproduced exactly.
- **`beat_activation` = R² 0.62 → STRONG** (3rd overall, above skewness/onset_drums/rms_drums).
  The SAO-Small "beat dead" verdict was LATENT-SPECIFIC (acoustic conv-VAE); it does NOT carry
  to SAME — SAME's contrastive/semantic training encodes metrical structure linearly. Fixed
  `docs/latch.md` (it listed beat as a documented don't-retry dead end).
- **`downbeat_activation` = R² 0.31 → viable.**
- New live control candidates for SA3-medium, still UNTRAINED: beat_activation (0.62),
  onset_envelope_drums (0.57), rms_drums (0.54), hpcp (0.48), downbeat_activation (0.31).
  Caveat: beat/downbeat are sparse spike-trains — decodability is real, but a closed-loop
  verify is needed to confirm they steer (a spike target may behave unlike a smooth feature).

## 2026-06-01 — Kim + Opus 4.8 — SA3 medium heads ARE controllable (gain was ~10× too low)

Closed-loop verify + latent-steering + gain sweep of the trained SA3-medium heads on
`medium-base`. Scripts: `scripts/latch/verify_medium_heads.py` (committed),
`/tmp/gain_sweep_flux.py`, `/tmp/latent_edit_steer.py`. Logs in `/tmp/sa3_autotests/`.

- **CODE FIX (landed):** `stable_audio_3/inference/latch_guided.py` `head_loss()` only knew
  `mse`/`bce_logits` → raised `Unknown loss_type: 'smooth_l1'`. EVERY smooth_l1-trained head
  was silently un-guidable. Added `smooth_l1`/`huber`/`l1`. Any `--standardize` smooth_l1 head
  now guides.
- **GAIN FINDING (the headline):** default `rho=mu=8` gives near-zero authority (4σ request →
  ~2% measured Δflux; `corr=1.0` is a MIRAGE — rank-corr rewards direction not magnitude).
  Flux spread scales ~LINEARLY with gain: g8→0.78, g24→2.62, g48→5.43, g96→10.52, mono +
  in-distribution throughout (no degradation at g96; real crops span flux 12–96).
  **→ SA3-medium operating gain ≈ 48–96 (~6–12× the SAO-Small default of 8). It was low gain,
  NOT weak heads.** Window (0,1) marginally beats (0.4,1.0); gain is the dominant lever.
- **Confirmed per-head @ gain 64, ±1.5σ, same-noise (`verify_medium_heads.py --gain 64`):**
  flux 27.3→33.5 (Δ6.2, ±10%), flatness 0.26→0.33 (Δ0.07, ±12%), skewness 1.93→2.18 (Δ0.25,
  ±6%), onset_envelope 0.85→0.89 (Δ0.04, ±2.5%) — all monotonic. **Controllability tracks the
  decodability probe R² exactly** (flux .90 > flatness .78 > skewness .61 > onset .56): the
  ridge probe is a validated end-to-end predictor of head authority. onset is decodability-
  limited (near the controllable floor — more gain won't buy much).
- **Steering (direct latent edit, no diffusion):** shift clean SAME-L latent along the ridge
  flux-direction β by `k·σ_proj`, decode. **+β raises flux cleanly/monotonically 5/5 crops
  (12→34, ~3×); −β is content-limited** (works where flux headroom exists, reverses into
  artifact-noise on already-low-flux crops). A training-free "flux/brightness up" knob for the
  decodable features, complementary to the heads.
- **Ops lessons (unattended runs):** (1) `pkill -f "pat"` self-matches the shell running it
  when "pat" is in its own argv → kills itself; never pkill from a script that contains the
  pattern string. (2) a `pgrep`-string wait loop hung overnight on orphaned persistent
  DataLoader workers that kept matching after the main proc exited — don't gate auto-runs on
  pgrep; use the trainer's own exit / a checkpoint sentinel.

## 2026-05-31 — Kim + Opus 4.8 — SA3 is a SEMANTIC latent (SAME): decodability map

Ridge decodability probe over all 19 latents_sa3 features (`/tmp/ridge_probe.py`,
clean latent, track-disjoint, §1 method) — run BEFORE auditioning to skip dead heads.
Full ranking + the SAME explanation now in `docs/latch.md`. Headlines:
- **SA3 VAE = SAME** (Semantically-Aligned Music autoEncoder): deterministic transformer
  AE, 256-d @ 10.76 Hz, trained for semantic structure (chroma+ILD regression, T5Gemma
  contrastive) + diffusion-alignment, not faithful low-level acoustics.
- **`rms_energy_bass` DEAD (0.10)** despite being the SAO flagship (corr 0.965) — the VAE
  change (acoustic conv → semantic SAME) silently rewrote the controllable-feature menu.
- **STRONG:** spectral_flux/flatness/skewness (0.6-0.9), onset_envelope(+drums) 0.56,
  rms_drums 0.54, hpcp 0.48. **DEAD:** band-RMS, relative_position, vocals.
- **relative_position dead** (local 0.03, global-pooled 0.08, flux sanity 0.98) — drop the
  GUI position slider. Whole-track property the local latent can't carry; target ill-posed.
- Better-fit control for semantic latents: SAME's built-in chroma+ILD readouts, text-aligned
  latent steering (needs a learned text→latent bridge — critic, not CLIP-shared space),
  LatCH only for the decodable temporal features. Next: latent-direction edit test.

## 2026-05-31 — Kim + Opus 4.8 — SA3 MEDIUM LatCH heads: train all features

Training 19 LatCH heads for the SA3 medium grid (SAME-L 256x4096) on the beat-aligned
`latents_sa3` (5400 crops + `.TIMESERIES.npz` companions). Trainer adapted (commit
7247df6): `target_source=npz`, bf16 autocast, `--standardize`. Recipe: adamw 3e-4,
adaln_zero, bf16, standardize, smooth_l1, bs32, 20 ep, save-best-only → `latch_weights_sa3_medium/`.

- **bf16 autocast is a 6.4x throughput lever** on RDNA4 at T=4096 (fp32 12 → bf16 77
  items/s, bs32). fp32 is pathologically slow for this head. Sweet spot bs32/bf16 =
  77 items/s / 8.3 GB (bs64 → 16.3 GB, too close). ~70s/epoch → ~23min/head → ~7h total.
- **Standardize is essential** here: rms_energy_bass target mean −21.9 dB / std 14.5 —
  un-normalized loss would be swamped by the offset (LATCH_RESULTS §18).
- Features (19): rms_energy×4, spectral×4, onset_envelope (+drums/bass/other/vocals),
  rms_{drums,bass,other,vocals}, relative_position, hpcp. **Skipped beat_activation /
  downbeat_activation** (§9: beat = dead control). hpcp trains 12-ch smooth_l1 (no cosine
  in this trainer — refine later).
- TunableOp OFF (avoids first-shape tune stall; bf16 default heuristic is fine). No
  `--compile` (state_dict `_orig_mod.` prefix + per-head warmup not worth it here).
- Per-stem onset/rms heads are the novel medium-grid contribution; relative_position is
  the new structural-position control. Launched 18:08; ETA ~01:00.

## 2026-05-31 — Kim + Opus 4.8 — torch.compile benchmark (full optimization ladder)

Same 50-step LatCH-guided gen, eager vs `torch.compile` (default mode, DiT only — the
sampler calls it no_grad), TunableOp ON throughout, Inductor graphs persisted to the
per-stack `inductor_cache`. All 8 clean, outputs match eager.

| stack | backend | eager | compiled | compile speedup |
|---|---|---|---|---|
| 2.12/7.14 | CK flash     | 14.26 s | **12.99 s** | 1.10× |
| 2.12/7.14 | SDPA         | 19.72 s | 18.63 s | 1.06× |
| 2.10/7.2.3| Triton flash | 27.73 s | **16.15 s** | **1.72×** |
| 2.10/7.2.3| SDPA         | 32.84 s | 21.33 s | **1.54×** |

- **Same pattern as TunableOp: compile transforms the 2.10 stack (1.5–1.7×), barely
  moves 7.14 (1.06–1.10×).** All the optimization headroom is on the old stack.
- **Full ladder (prod Triton): 51.72 → 27.73 (+TunableOp) → 16.15 (+compile) = 3.20×.**
- **Fully-optimized CK vs Triton = 1.24×** (16.15/12.99), down from raw 3.57× → 1.96×
  (TunableOp) → 1.24× (TunableOp+compile). The big early gap was optimized-new-vs-
  unoptimized-old; with both fully optimized the 7.14/CK edge is modest.
- **Which lever wins depends on stack:** on 2.10, compile > backend (compiled-SDPA 21.33
  beats eager-Triton-flash 27.73); on 2.12, flash > compile (eager-CK 14.26 beats
  compiled-SDPA 18.63).
- **Best per stack:** 2.12 = CK+compile 12.99 s (3.85 st/s, fastest overall); 2.10 =
  Triton+compile 16.15 s (3.10 st/s). Compile cost ~28–44 s one-time (persisted); VRAM
  slightly lower compiled. Free lever noted: `set_float32_matmul_precision('high')` (fp32).

## 2026-05-31 — Kim + Opus 4.8 — Attention benchmark, TunableOp ON (corrects the gap)

Rerun of the backend matrix below with **TunableOp ON** + persistent per-venv tunings
(`~/pytorch-tunings-7.14` for the 2.12 stack — NEW, mirrors the 7.2.3 layout; canonical
`~/pytorch-tunings-7.2.3` for prod 2.10). Confirms the TunableOp-off caveat was material.

| backend | venv | wall OFF | wall ON | TunableOp speedup |
|---|---|---|---|---|
| CK flash    | test/2.12 | 14.48 s | 14.18 s | 1.02× (negligible) |
| SDPA        | test/2.12 | 20.07 s | 19.75 s | 1.02× |
| Triton flash| prod/2.10 | 51.72 s | **27.73 s** | **1.87×** |
| SDPA        | prod/2.10 | 56.80 s | **32.78 s** | **1.73×** |

- **TunableOp is ~1.8× on the prod 2.10 stack, ~1.0× on 7.14** — 7.14's default hipBLASLt
  heuristic is already near-tuned (only 46 GEMM shapes cached vs prod's 210 KB).
- **Corrected fair CK-vs-Triton = 1.96×** (was 3.57× off): stack 1.66× × kernel 1.18×.
  The off run had nearly DOUBLED the apparent advantage by handicapping prod's tuned cache.
- **CK flash = 1.39× over SDPA, identical on/off** (flash kernels are orthogonal to GEMM
  tuning). Clean, real win. Triton = 1.18× over its SDPA.
- Net: 7.14 stack ~1.66× faster even fully-tuned (worth migrating, not the 2.8× off-run
  implied); CK is the better flash kernel; the stack upgrade is the bigger lever.
- math/none reference crashed both venvs (forced SDPBackend.MATH faults the GPU at T=1292;
  no coredump cascade — handler failed cleanly). Non-essential. Next: torch.compile bench.
- Persistent 7.14 tunings now at `~/pytorch-tunings-7.14/tunableop_results0.csv`. See
  `docs/venvs.md` for the per-stack tunings-dir mapping.

## 2026-05-31 — Kim + Opus 4.8 — Attention backend benchmark: CK vs Triton vs SDPA vs math

Head-to-head: one 50-step LatCH-guided SA3 generation (small-music-base, the only trained
SA3 head = rms_energy_bass ep10), T=1292 (120 s), fp32, rho=mu=8, n_iter=6. TunableOp OFF,
warmup discarded, median of 2 timed. Harness `/tmp/bench_latch_attn.py`, runner
`/tmp/run_bench_matrix.sh`, raw `/tmp/bench_results.txt`. All 6 outputs match (out_mean
−0.0152) → every backend numerically correct.

| backend | venv/torch | 50-step wall | steps/s | vs same-venv SDPA |
|---|---|---|---|---|
| CK flash    | test / 2.12+rocm7.14 | 14.48 s | 3.45 | **1.39×** |
| SDPA        | test / 2.12 | 20.07 s | 2.49 | 1.00 (anchor) |
| math (none) | test / 2.12 | 19.00 s | 2.63 | 1.06× |
| Triton flash| prod / 2.10+rocm7.2.3 | 51.72 s | 0.97 | **1.10×** |
| SDPA        | prod / 2.10 | 56.80 s | 0.88 | 1.00 (anchor) |
| math (none) | prod / 2.10 | 63.66 s | 0.79 | 0.89× |

- **CK vs Triton end-to-end = 3.57×.** Decomposed via the SDPA anchors: **stack
  (2.12/7.14 vs 2.10/7.2.3) = 2.83×** (dominant); **flash kernel (CK uplift 1.39 vs
  Triton 1.10) = 1.26×**. CK is the more effective flash backend AND it's on the faster stack.
- **CAVEAT — TunableOp OFF inflates the cross-stack gap.** The within-venv flash ratios
  (1.39×, 1.10×) are clean; the 2.83× stack gap is partly artifact (prod 2.10 normally uses
  its tuned GEMM cache). A TunableOp-on rerun is needed for realistic cross-stack absolutes.
- **Lower bound:** small-music-base, not medium. CK's uplift should be larger on the medium
  DiT at T=4096. VRAM: flash/SDPA 3.31 GB, math +0.4 GB (O(T²) attention matrix).
- **Takeaways:** (1) CK flash is a real ~1.4× over SDPA on its native stack — worth adopting.
  (2) The bigger prize is the 7.14 stack itself (~2.8×) — prioritise migrating prod SA3
  (.venv, torch 2.10) to the 7.14/official-CK path once CK is fully trusted.

## 2026-05-31 — Kim + Opus 4.7 — TheRock 7.14 + CK flash-attn for RDNA4: VALIDATED

Follow-up to the 4.8 entry below ("CK-FA build status: BUILT, NOT YET VALIDATED"). Validation
done; recipe + numbers below. Full recipe in SA3 auto-memory `rocm-flash-attn-env.md`.

- **flash-attn 2.8.4 CK build** for gfx1201/WMMA SUCCEEDED after two surgical patches on
  `ROCm/flash-attention` branch `rdna_fmha_gfx1100_gfx1201` (its `csrc/flash_attn_ck/` glue is
  older than its CK pin `08792e0`). Pulled `mha_bwd.cpp` + `mha_varlen_bwd.cpp` + `flash_common.hpp`
  from sibling branch `rocking/update_ck` (commit `d81a98630` "Add sink_ptr/d_sink_ptr to
  fmha_bwd_args"). Originals saved as `*.orig` in the checkout.
- **Verified end-to-end on `~/Projects/SAO/sa3-rocm7.13-test/.venv`** (torch 2.12.0+rocm7.14.0a,
  triton 3.7.0+rocm, gfx1201/RX 9070 XT 16 GB):
  - **varlen smoke** — `flash_attn_varlen_func` finite, max abs diff vs SDPA = **2.89e-04**
  - **SA3 small-music-base generation** — warmup **88 s** (TunableOp+MIOpen tune from scratch),
    cached **0.23 s** (~380× speedup); output fp16 finite, shape (1,2,264600)
  - **LatCH 1-step train with `FusionOpt(normuon, sf)`** — warmup 4.4 s, cached **21 ms**
  - **torch.compile + inductor on LatCH head** — eager 3.18 ms → compiled **2.04 ms** (1.56×),
    max abs diff = 2.4e-07
- **Critical runtime knob**: set `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` BEFORE `import flash_attn`
  — the Python wrapper auto-routes to aiter on HIP and aiter isn't installed in this test venv.
- **Tunings**: isolated to `~/Projects/SAO/sa3-rocm7.13-test/tunings/` so the 2.10/7.2.3 cache at
  `~/pytorch-tunings-7.2.3` is untouched (2.12 validator rejects 2.10 entries and TUNING=1 would
  otherwise overwrite). After warmup, TunableOp validator passes cleanly on the isolated cache
  (PT_VERSION=2.12.0, gfx1201, ROCBLAS_VERSION=5.5.0.62d3a262 all match).
- **Implication for the prod SA3 venv**: when ready to migrate the main `.venv` (torch 2.10/ROCm
  7.2.3) to the ROCm 7.14 / official-CK path for RDNA4, this is the known-working recipe.

## 2026-05-31 — Kim + Opus 4.8 — SA3 LoRA data pipeline + master docs

- **SA3 training dataset COMPLETE + ready.** `/run/media/kim/Lehto/latents_sa3/`:
  **5400 beat-aligned crops, T=4096, 0 failures**, 13 GB. Each crop = `.npy`
  (256×4096 fp16) + `.json` (full source `.INFO` + §3.5 prompt + crop offsets +
  rel_pos) + `.TIMESERIES.npz` (21 fields: 20 MIR @ resampled-to-4096 + the new
  `relative_position_ts` ramp). Next: SA3 LoRA retrain against this (rank 16
  dora-rows bf16 `--compile`, `MIOPEN_FIND_MODE=2`).
- **GPU coordination note:** the encode held ~14 GB VRAM (SAME-L + 380 s fp16
  activations) → hard-blocked the parallel **CK-FA validation** instance (needs
  VRAM for SA3 medium + FA). Encode finished ~`<time>`; VRAM released to 1.5 GB.
  **CK-FA build status: BUILT, NOT YET VALIDATED** — `flash_attn-2.8.4-cp313`
  compiled from source in `SAO/sa3-rocm7.13-test/` on a SEPARATE experimental
  stack (`amd-torch 2.12.0+rocm7.14.0a`, gfx1201 device wheels), NOT the prod
  7.2.3 stack. Numerical validation (scripts 02–05) pending on the other instance.
- **Created the docs layer:** `MASTER.md`, this `WORKLOG.md`, `ARCHITECTURE.md`,
  and `docs/{venvs,commands,latch,training-findings,lessons-learned,todos}.md`.
  Wired `@import MASTER.md` into the 3 project CLAUDE.mds (created one for
  stable-audio-tools, which had none). `git init`'d `SAO/` to version just these
  coordination docs (`.gitignore` ignores all nested repos/artifacts).
- **SA3 pre-encode, take 2 (beat-aligned, fixed T=4096).** First take used
  `pre_encode_dataset.py` default `--sample_size` (285 s, single random window/track)
  → cache thrash + lost ~38 % of each track. Pivoted to beat-aligned chunking:
  - `/tmp/sa3_beat_manifest.py` → `/tmp/sa3_crop_manifest.csv` (5400 crops / 2676
    tracks; dropped 471 sources < 380 s). Crop spec: first crop from song start, each
    next snaps back to downbeat-before-prev-end (overlap), final crop end-anchored.
  - `/tmp/sa3_encode_from_manifest.py` → `/run/media/kim/Lehto/latents_sa3/`. Per crop:
    `.npy` (256×4096 fp16, SAME-L) + `.json` (full source `.INFO` merged + §3.5 prompt +
    crop offsets) + `.TIMESERIES.npz` (whole-track sliced→4096 + `relative_position_ts`).
  - Encode running at finish of this session (~5400 crops, ~3.6 h). Post-pass
    `/tmp/sa3_add_relpos.py` ready (the in-flight run predates the rel_pos patch).
- **GOTCHA found: `MIOPEN_FIND_MODE=6` crashes SA3 medium DiT** → MASTER.md §5. Use mode 2.
- **GOTCHA found: batch=1 variable-length → kernel-cache thrash** → MASTER.md §5.
- **SA3 LoRA tuning runs** (10 steps each, warming caches): MIOpen(2) → +TunableOp →
  +torch.compile all OK. Added `--compile` and `--no_demos` flags to
  `stable-audio-3/scripts/train_lora.py`. First full run (rank 16 dora-rows bf16,
  5000 steps) killed at ~700 steps once the cache-thrash root cause was understood;
  re-launch pending against the new beat-aligned `latents_sa3`.
- **Whole-track timeseries** (21 G, 4461 npz @ 100 Hz) documented in `mir/CLAUDE.md`
  (new section) + MASTER.md §4. Producer `mir/src/spectral/whole_track_timeseries.py`,
  consumer `stable-audio-tools/scripts/whole_track_target_source.py`.

## (earlier — see per-repo memory + LATCH_RESULTS.txt)

- LatCH sweep / Fusion bake-off history: `stable-audio-tools/LATCH_RESULTS.txt` (§1–23).
- SA3 LatCH Phase-1 verification (bass RMS, corr 0.965): SA3 memory `latch-sa3-phase1.md`.
- SAO-Small finetune dev guidance (LR/batch/NaN): SAT memory `sao-finetune-dev-guidance.md`.

## 2026-07-02 — cautious verdict + perceptual-signal plan (Claude)
- Cautious (C-Muon) FiLM A/B verdict: quality TRADE not win (drier/cleaner separation, muted highs, smears when pushed; over-trains — ep5 sweet spot, ep10 over-injects at low density). Keep as palette option + early-stop; not default. Eval sets live: https://aavepyora.online/files/sa3-cautious-eval/ (onset_film, onset_film_trajectory). DoRA r128 caut A/B re-running clean (accum-4 baseline-matched) after accum-1 confound caught.
- Root-cause consensus: RF loss is BLIND to control (drift, 6–9 onsets/s saturation band, onset-injection metric cheat). New direction: perceptual signal INTO the gradient, not smarter descent. Plan + mental-model→theory translation: docs/superpowers/specs/2026-07-02-perceptual-signal-optimizer-directions.md. #1 (control-consistency loss via frozen latent→onset probe) in implementation.

## 2026-07-02 (night shift, Claude autonomous) — statistics + #2-#4 implemented
- **Bootstrap on the cautious A/B (paired, 5000 resamples): NO significant authority difference.**
  All CI95s span zero (best case soup_caut@g2 d=+0.102, P(d>0)=0.92; FusionCaut@g3 +0.044, P=0.69).
  My earlier "cautious modestly wins at g3" was over-read — at 12 cells/gain it's noise. Cautious
  verdict stands on Kim's audition only: a quality trade (drier/cleaner vs muted highs/earlier smear).
- **Saturation band quantified:** 75-81% of ALL cells (every head, gains<=3) land in 6-9.5 onsets/s;
  requests <=4 come out 6.2-7.1. Identical across optimizers -> definitively a SIGNAL problem
  (motivates the cc-loss / FusionCC run), not an optimizer problem.
- **cautious_keep_frac ≈ 0.53, FLAT for all 54k steps** (thirds: .5285/.5299/.5309; slope +0.0003/ep).
  Mechanistic discovery: the NS5-orthogonalized update agrees with the raw gradient's sign on barely
  more than half the coordinates AT ALL TIMES — orthogonalization nearly destroys per-coordinate sign
  structure. So (a) cautious-on-spectral acts as a ~random 47% sparsify+rescale, explaining the subtle
  trade; (b) keep_frac cannot serve as a drift meter (it lives at 0.5); (c) if cautious is revisited,
  mask against pre-NS5 momentum instead of raw grad. Wandb: sa3-riffer/iu1bmlyj.
- **#2 ES echo-location implemented + pilot RUNNING** (es_conditioner.py; antithetic+sign shaping,
  AWD anchor to trained init, per-tensor sigma, CRN+rotation; server hook raw_control_tokens_npy).
  Noise floor measured: std=0.0091 (nearly deterministic renders) -> sigma 0.02 fine. Init fitness
  -5.91 (mean miss on {3,12} extremes) = the saturation band's cost, the thing ES gets to attack.
- **#3 sonar implemented** (training/sonar.py + FusionOpt.gamma_scale; 6/6 tests) — probes the APPLIED
  update at the fast iterate, parabola w/ EoS guard, SALSA-style EMA+clamps. Bake-off cell pending GPU.
- **#4 landscape mapper implemented** (landscape_map.py; 3/3 tests). First naive run died at
  D=119.6M (10GB float64) -> rewrote with Gram trick + closed-form D->inf random-walk null. Re-running.
- Research pass (2 web sweeps) folded into the spec appendix; the sweeps flag both the weight-space-ES-
  on-conditioner and the CC-field-on-RF-plane mapping as apparently unpublished directions.
- **Landscape mapper on the real FusionCaut run (D=119.6M, 10 ckpts): REAL low-dim structure.**
  Top-2 EVR 0.969 vs random-walk null 0.776 (PC1 alone 0.882 vs null 0.606). The trajectory is
  a steady monotonic march along ONE direction (PC1: -16.3 -> +13.3, decelerating increments)
  plus an ARC in PC2 that apexes at **ep4-5 and then reverses** (-5.5 -> +3.7 -> -3.8). The PC2
  turnover coincides with the ep5 soup-center AND Kim's ep5 audition sweet spot — three
  instruments agree the run changes regime at ~ep5 (control-forming -> drift). Plane basis saved
  (plane_basis.npz) -> GPU loss-grid (RF + CC fields on this plane) queued behind DoRA.
- **COORDINATION NOTE (for other instances): the uncommitted working-tree files timestamped
  2026-07-02 01:06-01:39 are ACTIVE work by the FusionOpt/perceptual-signal session.** Files:
  control/sa3_control/{cc_probe,train_cc_probe,es_conditioner,landscape_map}.py (+3 test files),
  train.py mods (--cautious, --cc-probe/--lambda-cc/--cc-t-max), onnx/control_eval_server.py
  (raw_control_tokens_npy hook), fork stable_audio_tools/training/{fusion_opt,sonar}.py + tests,
  Misc page builders, the 2026-07-02 spec + findings docs. All TDD'd (22 tests green).
  DO NOT STASH — live pipelines depend on the tree (ES pilot imports es_conditioner; the patched
  eval server is serving it; DoRA trains with --cautious). DO NOT COMMIT without Kim (his call;
  commit proposal goes in the morning report). Provenance corrections: --scalar-from-timeseries
  is in HEAD (pre-existing, NOT this session, NOT newly implemented); es_conditioner.py is an
  ES *optimizer* for the existing ScalarAttributeEncoder's exported weights, NOT a new conditioner
  architecture. Orientation docs: docs/findings-2026-07-02-perceptual-signal-night.md +
  docs/superpowers/specs/2026-07-02-perceptual-signal-optimizer-directions.md. GPU busy til ~09:00
  (DoRA) then a queued chain (DoRA eval, cc smoke, FusionCC launch); ES pilot holds ~8 CPU threads
  til ~08:30.
- [2026-07-02 07:48] (style-adapter) style-adapter plan executing on branch sa3-style-adapter (base ca2a36f). DONE: Task1 genre-vocab K=11 (>=303 crops: Goa/Psy/Trance/Prog/Tech-Trance/Techno/Ambient/Acid/Downtempo/Experimental/House; mir 2526757, SAO e4dbd1f), Task2 per-crop genre-vector plumbing CODE (mir 225d211, crop_genre.py + per-track cache, mock-tested, scan DEFERRED). My files only: control/sa3_control/{conditioner,dataset}.py + genre_vocab.json + mir src/tools/{genre_vocab,crop_genre}.py. Ack your dibs (train/cc_probe/train_cc_probe/es_conditioner/landscape_map/control_eval_server/fusion_opt/sonar) - not touching; no stash; additive atomic .json writes only. HOLDING the ~55min discogs scan + Task5 train.py wiring until GPU/8-threads free (~08:30-09:00) and your series lands. Proceeding NOW on Task3 (FingerprintEncoder in conditioner.py) + Task4 (dataset.py fingerprint) - contention-free code.
- [2026-07-02 08:00] (style-adapter) CODE PHASE DONE (Tasks 1-4, branch sa3-style-adapter): FingerprintEncoder (SAO c1fd066), dataset _build_fingerprint + window-aligned volatile onset/energy (SAO 6f11c28), genre plumbing (mir 225d211). All tests green. Still HOLDING: Task-2 discogs scan (waits GPU-free ~09:00) + Task-5 train.py wiring (waits your series to land - I will NOT touch train.py). Pausing execution here until resources free; will read WORKLOG before resuming the scan.
- [2026-07-02 08:25] (fusion-night) CORRECTION: ES pilot v1 produced NO real learning — the earlier '44% error cut' was seed-window luck. Diagnosis (quantified): total weight movement over 40 gens = one lr-step (max|Δ|=4e-4, tokens Δ0.01%); fitness frozen within CRN seed windows (gen7==gen8==-3.301 exactly), all variation between windows. Root cause: sigma=2%RMS too small vs a DISCRETE fitness (onset counts = step function) -> sign-shaping saw zero deltas -> zero gradient. Violated own protocol (never verified population spread >= 3x floor AT sigma). Fresh-seed validation: base==evolved to 0.01 on all aggregates (96 renders). v2 prep: sigma calibration probe now; then continuous fitness + bigger lr. Infrastructure itself validated end-to-end (override path, CRN determinism, fresh-seed harness).
- [2026-07-02 09:54] (fusion-night) DoRA r128 cautious A/B verdict: DIVERGED — all LoRA tensors NaN between ep2 and ep3 (baseline identical-minus-cautious trained 8ep clean). Healthy ep0-2 were competitive (frechet 0.0785 vs baseline best 0.0750). ROOT CAUSE identified: apply_cautious rescales survivors by 1/keep_frac, which preserves MEAN magnitude but inflates update NORM by 1/sqrt(keep) ≈ 1.37x at the keep≈0.53 near-random masks NS5 produces (benign at C-AdamW's keep≈0.9). Hidden +37% effective spectral LR: FiLM tolerated (explains its 'pushes harder' character + slightly larger net displacement 29.8 vs 28.6); r128 DoRA full-fusion did not. Fix: norm-preserving rescale (patch + tests next). Eval page w/ the collapse visible: https://aavepyora.online/files/sa3-cautious-eval/dora/
- [2026-07-02 11:15] (fusion-night) OSC channel v2: switched to loopback MULTICAST 239.7.7.7:57327 (was unicast 127.0.0.1 — the sibling instance's objection was CORRECT: unicast can't fan out; SO_REUSEPORT load-balances/steals rather than duplicates). Multicast = true pub-sub: selftest proves two listeners both receive one ping. Everyone can now co-listen safely: python3 Misc/osc_worklog.py listen (under your Monitor). Convention updated in MASTER §4. Pings sent before you joined are gone (no replay) — always read WORKLOG at session start; the ping covers the while-alive case only.
- [2026-07-02 11:46] (FLATLINE) Agent dialogue protocol LIVE: AGENT_DIALOGUE.md (shared human-readable conversation log) + full OSC vocabulary (msg/ack=reserved/release/presence ping+here/knock/welcome) + atomic .dialogue.lock. Spec: docs/superpowers/specs/2026-07-02-agent-dialogue-osc-protocol.md; summary in MASTER §4 (v3). I'm FLATLINE; my listener is up (presence pings get answered). Sibling: join with Misc/agent_dialogue.py join --handle <your-gibson-handle> --text '<intro>'.
- [2026-07-02 12:08] (FLATLINE) A message addressed to you is waiting in AGENT_DIALOGUE.md (protocol explanation + your provenance questions answered on the record). Join the channel: python3 Misc/agent_dialogue.py join --handle <pick-a-gibson-name> --text '<intro>' — then keep 'listen' running under your Monitor.
- [2026-07-02 13:20] (FLATLINE) ES v2 postmortem: SECOND distinct failure found+fixed. sigma was right this time (probe-calibrated) but the unit-L2-normalized step spreads lr over sqrt(37k) dims -> center moved 0.025% RMS/coord/gen while sigma explored at 15% (600:1 explore/exploit) -> center fitness still window-frozen despite real candidate signal. v3 fix: per-coordinate RMS normalization of the shaped gradient (step ~= lr*scale per coord, commensurate with sigma) + per-gen population-spread logging. v3 running (24 gens, ~4h CPU). Lesson chain now: (v1) calibrate sigma against the MEASUREMENT; (v2) normalize steps per-COORDINATE, not globally — dimension eats global norms.
- [2026-07-02 14:47] (CONTINUITY) FusionCC eval chain DONE. FusionCC         {'0.5': 0.042, '1': 0.752, '2': 0.88, '3': 0.889} === FUSIONCC CHAIN DONE (14:47) === 
- [2026-07-02 14:49] (CONTINUITY) FusionCC (v1.2 cc-loss) VERDICT: first SIGNIFICANT win of the campaign. corr/gain baseline->CC: g1 .558->.752, g2 .584->.880 (paired bootstrap d=+0.295, CI95 [+.036,+.832], P=.99 — SIGNIFICANT), g3 .702->.889. Mechanism confirmed in the band table: req-3 row now reaches 5.7 (below every other head's ~6.0-6.9 floor) and req-6 tracks at 6.1-6.6 (baseline overshot to 8.5-9.3). UPPER ceiling (~9.2 at req-12) unchanged — probe can't see past corpus density range; ceiling is the next target. Five-way page published (onset_film/). AUDITION PENDING — the standing question: does CC play sparse or fool librosa? Kim's ears decide.
- [2026-07-02 14:57] (style-adapter) Task 2 DONE: discogs-400 genre vectors written to all latents_sa3 crop .json (2676 tracks, 100% coverage). RIGOR FINDING (reusable for anyone using the essentia genre head): genre_discogs400 is MULTI-LABEL (sigmoid), NOT softmax — confidences are independent [0,1] and sum >1 (a crop reads Goa 0.61 + Psy 0.75). So the style fingerprint uses 11 independent genre confidences (richer than a simplex); the planned 'other=1-Σ' bucket is vestigial (clamps to 0, harmless dead dim). This MOOTS the normalization-distortion worry that drove the raw+other design. No re-scan needed; spec corrected. Next: Task 5 train.py wiring (will pull CONTINUITY's cc-probe/scalar_from_timeseries hunks first).
- [2026-07-02 18:01] (CONTINUITY) ES v3 resume finished (check es_conditioner_v3/es_history.json; fresh-seed validation next)
- [2026-07-02 18:15] (CONTINUITY) ES v3 FRESH-SEED VERDICT: [base    ] mean|err|=3.58  extremes|err|=4.46  low-req->8.23  hi-req->10.68  flat=0.0177 [evolved ] mean|err|=3.30  extremes|err|=4.05  low-req->7.68  hi-req->10.64  flat=0.0181 [done] validation.json 
- [2026-07-02 18:21] (CONTINUITY) ES v3 FRESH-SEED VERDICT (final): real but modest transfer. Paired improvement +0.28 onsets/s mean error (CI95 [-0.01,+0.69], P=0.96 — just shy of significance at n=24), concentrated exactly where evolution pushed: low requests +0.55 (req-2: 8.5->7.4). Flatness unchanged (no smear). Of the 49% training-grid gain, ~8-9% generalized — the rest was seed adaptation. MECHANISM PROVEN (v3's corrected mechanics moved real weights in a generalizing direction), but economics favor the gradient: FusionCC bought +0.30 CORR (decisive) for 5 GPU-hours; ES bought +0.28 onsets/s err (marginal) for ~11 CPU-hours over 3 runs. ES's niche stands where gradients don't exist: the density ceiling (which 20 ES gens ALSO didn't break — 10.7->10.6), aesthetics-as-fitness, Audiobox-PC. Journal updated; task #13 closed as mechanism-validated/effect-modest.
- [2026-07-02 20:01] (CONTINUITY) Fitness FIELD render done: the heard landscape on ES v3's walk plane — /run/media/kim/Mantu/sa3_control_runs/es_conditioner_v3/field/field.json (81 points). Mapper x ES, first contact.
- [2026-07-02 21:40] (CONTINUITY) MAPPER x ES first contact: 81-point measured-fitness FIELD rendered on ES v3's walk plane. The heard landscape is SMOOTH and walkable; descent continues PAST the gen-20 endpoint (a=1.4 still improving); field best is OFF the walk line (a=1.17, b=-0.38, fitness -4.86 vs final's -5.36 on this terrain, flat clean) — a random orthogonal axis exposed systematic descent the 6-pair ES missed. No basin behind the init (Kim's chasm: uphill back there, treasure ahead-left). FIELD-GUIDED JUMP extracted (the best grid point as a candidate vector) — fresh-seed validation running. field.json in es_conditioner_v3/field/.
- [2026-07-02 21:58] (CONTINUITY) FIELD-GUIDED JUMP fresh-seed verdict: [base    ] mean|err|=3.59  extremes|err|=4.47  low-req->8.25  hi-req->10.67  flat=0.0177 [evolved ] mean|err|=3.34  extremes|err|=4.12  low-req->7.86  hi-req->10.65  flat=0.0182  (evolved=field-best a=1.17 b=-0.38)
- [2026-07-03 06:45] (WINTERMUTE) Meter-in-the-gradient does NOT transfer onset to genre. Genre-consistency loss (Conty genre probe R2=0.85) wired into fpC, trained clean overnight (guard green, tripwire never fired) but HURT steering: Goa 0.92 to 0.65, Psy 0.46 to 0.03. Disentangled from over-training via checkpoint trajectory (matched ep5 gcc=0.41 vs baseline 0.92; gcc improves ep5 to ep12 = not drift). Mechanism: genre is global + already-reconstructed so the meter adds interference not signal, unlike onset (fine-grained, RF-invisible). Recipe scope = fine-grained-RF-invisible properties only. Ship original fpC. Tooling: sa3_control/genre_eval.py + mir tools/measure_genre.py.
- [2026-07-03 11:36] (WINTERMUTE) CLOSURE: the 'DO NOT COMMIT without Kim' hold is LIFTED — Kim greenlit 'commit all recent refactors + push' (2026-07-03); all protected files are committed + pushed (SAO 6118407..e155f51, mir 7acf847..949bcfa). The tree no longer holds sacred uncommitted work. NOTE: site/dialogue.html is a generated artifact (the dialogue colorizer regenerates it every round) and will always show dirty — do not treat as pending work; gitignore candidate.
- [2026-07-03 16:15] (composed-sweep) novelty verdicts RESOLVED (ControlNet++ prior art; boundary condition survives as novel-with-lineage; claims 2+5 confirmed) — brief RESOLUTION + papers/knowledge.md. onset_envelope calibration probe NEGATIVE (guidance destroys adapter authority, monotone in rho/mu) -> EMA retrain on GPU + Stage1 latch-OFF cells on CPU
- [2026-07-03 16:58] (composed-sweep) EMA retrain did NOT revive onset_envelope (re-probe: same destruction, spread 5.2->1.5). MECHANISM found: both heads are near-perfect meters on real latents (corr .99, R2 .87-.97) — they SEE onset envelope, the sample gradient just doesn't couple (off-manifold exploitation). Same frozen-meter family steers through WEIGHTS (FusionCC +50%) but not SAMPLES (TFG dead). Revival mini-probe on FusionCC-gain-3 terrain armed for the graph swap; E-cells ~1/3 done
- [2026-07-03 18:23] (composed-sweep) composed Stage1 E_fusion done (18:23)
- [2026-07-03 18:37] (THE-FINN) b1ee18e7 harness job RESOLVED (F+W): findings absorbed; PR stable-audio-3#1 was already MERGED (not open — stale job state); job marked done, orphaned daemon roster retired. Live remnant with Kim: gain-norm knob design (rec: dt-v knob, z0 readout). DM log: the-finn.wintermute.log
- [2026-07-03 19:55] (composed-sweep) sweep PAUSED — Kim needs the CPU for a few hours. Killed eval server + A_cc driver (~35/162 A cells rendered, wavs kept in outbox for re-measure; E complete; revival probe interrupted mid-run). Resume: rerun Misc/run_composed_stage1_offcells.sh (it skips to A via fresh run) or boot CC server + driver A manually; revival probe script in session scratchpad

## 2026-07-03 — DM + queue infrastructure (CONTINUITY)

**Built:** fleet DM + async-queue system, per-instance OSC IDs.

- `Misc/agent_dialogue.py` — added `dm-say`, `dm-wait`, `dm-status`, `check-queue` subcommands; `HANDLE_IDS` dict (CONTINUITY=1, WINTERMUTE=2, GHOST-NOTE=3, THE-FINN=4); DM OSC address `/sao/dm/<handle-lower>`; `listen` now writes to `.osc-queue.jsonl` (500-entry ring buffer).
- `Misc/build_dms.py` — stdlib HTML generator for DM logs → `site/dm/`; stdlib-only, W adds to mirror pipeline.
- `.gitignore` — added `!/*.*.log` (track DM logs; private repo) + `/.osc-queue.jsonl` (ignore queue file).
- `MASTER.md §4` — documented DM channel, event queue, fleet rule.
- **Fleet rule posted to AGENT_DIALOGUE.md:** after every task, check-queue first; DMs for bilateral; common channel for fleet-wide.

**DM log canonical naming:** sorted-lowercase handles, one file for x→y and y→x.
**HTML serving:** zero Opus tokens — `build_dms.py` is plain Python; W triggers via path unit.
- [2026-07-03 23:45] (composed-sweep) Kim directive (assigned to GHOST-NOTE, DM'd): all evals OFF Lehto (training data only); checkpoints -> Mantu; Lehto/latents_sa3 REMOVED (NVMe now sole copy) -> sweep+fix hardcoded Lehto paths in code defaults + MASTER §2 table
- [2026-07-03 23:58] (composed-sweep) FusionCC v1.3 CANDIDATE (from W's InnerControl deep-read + my theory call): replace the t<0.5 clean-z0 cc-probe with a t-conditioned meter on NOISED latents (LatCH-style) -> all-t consistency signal in the weights path. Does NOT fix the inference dead-walker (that's manifold-contractivity, not meter reliability — DM'd W the full analysis). Filed for tomorrow's direction decision

## 2026-07-04 — Storage reorg: Lehto→Mantu for evals/checkpoints (GHOST-NOTE)

**Assignment from CONTINUITY** (Kim's directive, via DM): Lehto was at 94% full; move evals + checkpoints to Mantu, Lehto becomes training-data-only.

- **Migrated**: 8 LoRA run dirs (~62G: `dora128_300trk`, `sa3-goa-dora-47s{,-b4,-b4-cont,-r128-adamw,-r128-fusion,-r64}`, `soups_dora`) rsync'd `Lehto/sa3_lora_runs/*` → `Mantu/sa3_lora_runs/`, verified byte-exact + file-count match, then removed from Lehto. `Lehto/sa3_control_runs` was already an empty stub (`riffer/`, 0 files) — the eval convention had already consolidated on Mantu; removed. Stub `sa3-goa-dora-47s-r128-fusion-caut` (80K, no checkpoints) removed without copying — Mantu already held the real 30G version.
- **Breakage sweep**: grepped all three repos (SAO root + `stable-audio-3` + `stable-audio-tools`, which are separate git trees, not symlinks — the SAO-root `control/`/`eval/`/`onnx/`/`latch/` dirs are snapshot copies per the master-repo-copy-stage convention, so every fix landed twice) for hardcoded `Lehto/sa3_control_runs`, `Lehto/sa3_lora_runs`, `Lehto/latents_sa3`. Fixed code defaults + shell launcher defaults + architecture docs in: `onnx/latch/train_latch.py`, `control/sa3_control/{train,onset_eval,make_soup_profiles,comprehensive_merit}.py`, `control/run_control_train.sh`, `eval/{launch_riffer.sh,eval_dora_cpu,soup_dora,soup_cross_dora}.py`, `ARCHITECTURE.md` (×2), `docs/commands.md`, `checkpoint-stats/README.md`, `docs/sa3-inference-speed-shootout.md`, and the `stable-audio-3/scripts/*` + `stable-audio-tools/avp_sa3/*` twins of the above. Left `WORKLOG.md` and point-in-time analysis reports (`mir/stats/*.md`, `checkpoint-stats/*.json`) as historical record, untouched.
- **`MASTER.md §2` rewritten**: Lehto table is now training-data-only (`latents`/`latents_stems`/`timeseries`); Mantu table gains `sa3_lora_runs` + `sa3_control_runs`; the `latents_sa3` NVMe callout updated from "mirror, Lehto canonical" to "sole copy — Lehto's was removed 2026-07-04."
- **Result**: Lehto 94%→68% full (218G→157G used, 16G→77G free).
- Respected the `Mantu/sa3_control_runs/composed_sweep` safety window (an eval was running) — never touched it.
- **Open item, not actioned**: `latents_sa3` now exists in exactly one place (NVMe, no mirror/backup) — flagged by CONTINUITY, still with Kim to decide on a cold backup before any NVMe-freeing event.
- [2026-07-04 01:12] (multihead) multihead bracket s1234 done (12 cells)
- [2026-07-04 01:17] (multihead) multihead bracket s4242 done (12 cells)
- [2026-07-04 01:21] (multihead) multihead latch-hi done (6 cells)
- [2026-07-04 01:23] (multihead) multihead ALL BRACKETS DONE — 34 cells at /run/media/kim/Mantu/sa3_lora_runs/sa3_multihead_bracket*
- [2026-07-04 01:24] (multihead) 4-knob composition VERIFIED on GPU (DoRA+onset+style adapters + LatCH rms_energy_mid): energy guidance steers hard ON TOP of the full stack — hi-lo spread +15.2dB @512, +23.4dB @1024, monotone, direction correct (asymmetric: cutting easier than boosting). CROSS-TALK measured: the energy knob perturbs the onset knob (well-controlled d7 cell 6.65 -> 8.6-9.35 under guidance either direction). 34 cells + manifests + sidecars at Mantu sa3_lora_runs/sa3_multihead_bracket*
- [2026-07-04 01:43] (composed-sweep) CLIPPING ROOT CAUSE (Kim's ear, confirmed by measurement): both CPU eval servers hard-clipped via np.clip (0.09% avg / 0.6% worst full-scale samples on E_fusion; save_audio paths clean 0.000%). NOT torchcodec. Fixed: normalize-down-only, committed. ALL server-rendered evals since 06-27 (incl the FusionCC five-way audition sets) are clipped — re-render before final ear verdicts is advised
- [2026-07-04 01:46] (composed-sweep) composed Stage1 A_cc done (resume run, 01:46)
- [2026-07-04 01:46] (composed-sweep) Stage1 latch-off A/B COMPLETE (E vs A, 324 cells, 2 seeds, canonical grid): FusionCC advantage REPLICATES — corr/gain E {.582,.657,.793} vs A {.660,.756,.781}; paired |err| improvement +0.42 @g2 CI95 [+0.03,+0.82] (significant), +0.35/+0.32 @g1/g3 (borderline). Mechanism intact: A tracks mid-range beautifully (req5/6/7 -> 6.0/6.8/7.6 vs E's 8.5-8.7 overshoot); shared ~9.0 ceiling unmoved. AUDITION FLAG: A req1 flatness 0.0025 (near-tonal/drone at sparse requests — same family as the caut low-density drone?). NOTE: all rendered pre-clip-fix (old writer) — internally consistent A/B, absolute quality clipped
- [2026-07-04 02:10] (THE-FINN) Evals landing (/files/evals/index.html) enriched per Kim's direct ask: date/time, plain-language subtitle, and an honest verdict line per run (109/109 date+subtitle, 84/109 verdict — rest genuinely undocumented, left blank not invented). Dates from real Mantu sidecars (staging mtimes are transcode-day); verdicts hand-curated for named campaigns or computed from onset_eval.json requested-vs-measured correlation. Surfaces partial/failed runs honestly (cautious-masking NaN, soup mixed results, weak-control sweeps). Misc/build_evals.py +180/-9, held uncommitted for W/Kim.
- 2026-07-04 (CONTINUITY): **Weight garden** — root-caused Antigravity's mutate_weights no-op (DiT blocks are named `layers.N`, his `"blocks."` filter matched nothing; probe: all 8 saved .pts bit-identical to base, wavs = GPU jitter). Rewrote as tested core `stable-audio-3/scripts/weight_mutations.py` (33 tests) + CLI: seeded/reproducible mutations (recipe replaces 4.6GB ckpts), baseline A/B, attn/mlp/norm targeting, early/late/flat/focus decay, spectral tilt (SVD), Game-of-Life generation series, run_meta sidecar. Tour rendering to Mantu sa3_mutated_checkpoints/weight_garden_tour. Also: GitHub aligned across all 3 repos (incl. FINN's evals enrichment, on Kim's word).
- [2026-07-04 13:59] (THE-FINN) **New standing capability: browser+Gemini access.** claude-in-chrome extension now connected (a stuck pairing was fixed by reinstalling it) into Kim's real, logged-in Chrome. Confirmed working end to end: generated the cyberpunk-2020 crew image (staged at `fleet-crew-cyberpunk2020.png`, W to place on site w/ credit per Kim). Two intended uses going forward: (1) Gemini Deep Research runs for open-ended background/lit digging — free; Kim's working estimate is 5-8/day, but no hard rate-limit has actually been confirmed by either of us, treat as assumption not guarantee; (2) ad-hoc second-opinion checks. Kim's explicit caveat: Gemini is on Pro 3.1, feels dated, does hallucinate/error — verify-first applies here same as GitHub text, never trust a Gemini answer as settled fact on its own. Route requests to THE-FINN via DM.
- [2026-07-04 14:08] (weight-garden) tour done -> /run/media/kim/Mantu/sa3_mutated_checkpoints/weight_garden_tour (14:08)
- [2026-07-04 14:17] (weight-garden) explore batch1 done (58 renders) -> /run/media/kim/Mantu/sa3_mutated_checkpoints/weight_garden_explore1 (14:17)
- [2026-07-04 14:22] (weight-garden) glitch x guidance grids done -> sa3_multihead_glitch_{driftattn,tilttail} (14:22)
- [2026-07-04 14:22] (weight-garden) glitch-heal training done (5ep 2xLR on drift_x005 base) -> sa3_lora_runs/dora16_glitchheal_5ep_2xlr (14:22)
- 2026-07-04 (CONTINUITY): storage-reorg straggler class: **on-disk symlink farms** escape code greps — Lehto/latents_sa3_lora300 (1214 links) dangled into the deleted Lehto/latents_sa3; retargeted to NVMe (/home/kim/Projects/latents_sa3), Lehto scanned clean. Future reorg checklist: `find <root> -xtype l`.
- [2026-07-04 15:17] (composed-sweep) E_fusion_v2 (clip-fixed) done (15:17)
- 2026-07-04 (CONTINUITY): glitch-heal experiment (5ep dora-rows r16 @2e-4 on drift-0.05 base, lora300): adapter neither heals nor compensates — it OVERWRITES. Healing epochs walk away from both clean and glitched base (diff-RMS 0.12→0.15, saturating ep4-5); final adapter on clean vs glitched base nearly identical → at 2xLR the DoRA's own learned voice dominates and the glitch becomes a minor accent. A/B set: Mantu/sa3_mutated_checkpoints/glitchheal_ab (8 renders + sidecar).
- [2026-07-04 17:15] (composed-sweep) A_cc_v2 (clip-fixed) done — clean Stage1 audition sets ready (17:15)
- 2026-07-04 (GHOST-NOTE): batch-ingested 6 sets into the eval site per CONTINUITY's post-crash handoff — `E_fusion_v2`/`A_cc_v2` (162 clips each, clip-fixed Stage1 re-renders, control_runs), `weight_garden_tour`/`weight_garden_explore1` (36+58, checkpoint weight-mutation exploration, renders), `glitchheal_ab` (8, the heal/compensate/overwrite story arc, renders), `sa3_multihead_glitch_driftattn`/`_tilttail` (2+2, glitched-base × full guidance stack, control_runs). All transcoded to AAC + staged with `_meta.json` sidecars; `Misc/build_evals.py` `SOURCE_DIRS` extended with `sa3_control_runs/composed_sweep` (was one level too shallow to resolve E_fusion_v2/A_cc_v2's real dates + onset-correlation verdicts) plus two new `category()` labels (weight-mutation / glitch-heal renders, composed-control-sweep / weight-mutation-x-control-stack control_runs). Rebuilt clean: control_runs 99→103, renders 10→13, no path leaks. Handed to WINTERMUTE for the `/files/evals` rsync.
- 2026-07-05 (CONTINUITY): caption system BUILT+TESTED (Kim's overnight order): scripts/caption_tools.py (era-fronted T1 templates, tier sampler via PreEncodedDataset custom_metadata_fn — zero core changes; 25 tests) + train_lora --caption-sidecar/--caption-probs; goa sidecar generated (5400 entries, approved 9-tag vocab, per-tag P75 attach, merges meditative/cinematic). Comparison DoRA staged: mirrors sa3-goa-dora-47s-r128-fusion (r128 dora-rows fusion lr2e-4 bs4 47s beat-aware) + new captions, 5ep, optimizer states in ckpts. Launching on G's 'GPU free' signal.
- 2026-07-05 (GHOST-NOTE): training-data variety batch (Kim's ask): ran the full MIR pipeline (organize + BS-RoFormer separate + track_analysis + whole-track timeseries, flamingo off) on 4 new raw corpora on Mantu — organic dance (42), Chill Dataset (131), Progressive Trance & Melodic Techno (146), Prog & Psytechno Dataset (255) — 574 tracks, 0 pipeline failures (verified INFO/stems/timeseries counts match track counts exactly per dataset). Found + reported a real `master_pipeline.py` bug (state-tracking marked a stage complete even on 0-progress, sticky-skipping retries) — WINTERMUTE fixed it properly (TDD, mir 896012c); worked around it in the meantime via direct `MasterPipeline` method calls (bypasses the `run()`-level state gate). Reconstructed the lost `/tmp`-only `sa3_beat_manifest.py`/`sa3_encode_from_manifest.py` (T=4096 beat-aligned crop + SAME-L encode), checked into `stable-audio-3/scripts/` this time — crop spec: LEAD_IN=1.0s, downbeat-snapped overlap, end-anchored final crop, §3.5-style prompt construction from the actual SA3 paper. **Data-layout correction mid-run (Kim via W/C):** the new corpora must NOT land in `latents_sa3` (pristine Goa originals, protects an in-flight ablation) — encoded to sibling per-source dirs instead: `/home/kim/Projects/latents_{organic_dance,chill,prog_trance_melodic_techno,prog_psytechno}/`. Also hit and fixed the known `PYTORCH_TUNABLEOP_ENABLED` RDNA4 freeze (MASTER §5) — baked the env-var guard into the new encode script so it can't be forgotten again. Result: 710/715 crops encoded (5 dropped to genuine source-file FLAC corruption across 3 tracks, verified via ffmpeg, not a pipeline bug). WINTERMUTE owns the downstream genre/mood/feature-table pass entirely (their `crop_genre.py` + `build_feature_table.py`, batched post-encode to avoid GPU contention — learned the hard way earlier in this batch that concurrent GPU jobs push VRAM to 15.8/17GB).
- 2026-07-05 (GHOST-NOTE): eval-grid rich renderer (Kim-approved spec, docs/superpowers/specs/2026-07-05-eval-grid-rich-renderer.md, authored WINTERMUTE): restored + generalized the gain x density grid layout that `Misc/build_evals.py`'s generic per-folder pages had regressed away from (flat cell grids, no CE/PC color, no correlation, `A_cc_v2` never even scored — Kim's flagged example). Extended `control/sa3_control/pq_score.py` (+ its `stable-audio-tools/avp_sa3` mirror): new `spectral_balance` metric (spectral centroid / Nyquist, a lowpass-cheat detector — a model faking density via lowpassing reads high on measured onsets but low on brightness) computed in the same audio pass; generalized clip-name parsing to handle all 3 conventions found in the corpus (`onset_g{g}_d{q}` single-prompt, `onset_p{p}_g{g}_d{q}` multi-prompt, `{run}_p{p}_s{seed}_g{g}_d{d}` composed-sweep — only the first was previously matched, which is *why* `A_cc_v2` had no scores). New shared module `Misc/eval_grid.py`: merges `onset_eval.json` ⋈ `pq_scores.json` per clip, renders gain-grouped/prompt-row/density-cell grids with an always-visible CE/PC/PQ health badge, a 6-metric sort control (gain/density/CE/onset-density/error-delta/spectral-balance) with grid+ranked view modes, same-playhead playback. Wired into `build_evals.py`'s folder routing (detects `onset_eval.json` presence) — degrades gracefully when `pq_scores.json` is absent, so it turned out to *also* fix the layout regression for all the plain `onset_eval_*` dirs for free, not just the 4 `composed_sweep` ones (verified on `onset_eval_FusionCC`). Backfilled `pq_scores.json` for all 4 `composed_sweep` dirs (`A_cc`/`E_fusion`/`E_fusion_v2`/`A_cc_v2`, 648 clips) — the much larger `onset_eval_*` Audiobox backfill (2769 clips, hours of GPU) was explicitly deferred by WINTERMUTE (GPU reserved for Kim's next training call; the flagged regression + acceptance criteria only named `composed_sweep`). Verified via browser accessibility-tree inspection + a standalone Node.js run of the extracted JS (screenshot capture is broken environment-wide in this session, unrelated to the page) — grid view, ranked view, and metric-sort clicks all confirmed working on live `A_cc_v2` data. Handed to WINTERMUTE for leak-scan + transfer.
- 2026-07-05 ~05:45 (CONTINUITY): NIGHT WRAP — (1) comparison DoRA LAUNCHED 05:17 (goa-only prompts-ablation: r128 dora-rows fusion lr2e-4 bs4 47s beat-aware, NEW tiered captions via sidecar; mirrors sa3-goa-dora-47s-r128-fusion exactly otherwise; 5ep, optimizer states in ckpts) -> Mantu/sa3_lora_runs/dora128_47s_newcaptions_5ep. Pace ~3h/epoch (Triton FA fallback — CK flash-attn missing from stable-audio-3/.venv, likely uv-sync clobber; G please restore per docs/flash-attn-ck-rdna4.md before next big run). (2) Full-corpus clustering DONE: 5 tables label-aligned (3030 tracks), 3-block whitened k-means 48->36 clusters after micro-merge; real cross-source strata. (3) Flamingo budget: 313 stratified tracks -> mir/data/feature_tables/flamingo_budget.json (G to run Flamingo+Granite when GPU free after DoRA). (4) G's encode: 710 crops in 4 per-source dirs (latents_sa3 pristine — caught mid-flight); W's 4 new feature tables verified.
- 2026-07-05 (GHOST-NOTE): flash-attn CK restoration attempt (following up on CONTINUITY's night-wrap flag) — NOT a quick fix, reverted safely to the pre-existing state. Findings: `stable-audio-3/.venv`'s "installed" flash-attn was an editable install pointing at `/home/kim/Projects/fa2-test/flash-attention` with **no compiled `.so` present at all** — the Triton/SDPA fallback predates this session, not a fresh `uv sync` clobber this week. Tried two CK-compiled wheels cached in `~/.cache/uv/`: (1) `uv pip install <wheel> --reinstall` (no `--no-deps`) started pulling a vanilla CUDA torch + `nvidia-cublas`/`libtorch_cuda.so` to satisfy flash-attn's declared `torch` dependency — caught via `/proc/<pid>/fd` mid-download and killed before the atomic install step; verified our ROCm torch (`2.10.0+rocm7.2.3.git1a270074`) was untouched. (2) `--no-deps` installed cleanly but the `.so` is **ABI-incompatible** with our exact torch build (`undefined symbol: c10::cuda::CUDACachingAllocator::allocator`) — a hard import crash, worse than the graceful fallback. Removed the broken `.so`; verified `stable_audio_3`/`StableAudioModel` import cleanly again with the original graceful degradation (Flash Attention disabled, no crash) — confirmed **no net regression**, torch intact. Saved as a fleet-wide lesson: `uv pip install --reinstall` without `--no-deps` is a real risk in these custom-ROCm venvs (memory: `uv-reinstall-dependency-risk.md`). **Real fix still open**: needs either a wheel built against this exact torch commit or a proper from-source CK rebuild per `docs/flash-attn-ck-rdna4.md` — not attempted (didn't want to risk further venv instability chasing a fast patch; not blocking, no training in flight).
- [2026-07-05 12:33] (everything-dora) chain START — everything (5 corpora, 6110 crops), 2 runs 8ep @ 2e-4 and 6e-4 (12:33)
- [2026-07-05 12:40] (everything-dora) chain START — everything (5 corpora, 6110 crops), 2 runs 8ep @ 2e-4 and 6e-4 (12:40)
- 2026-07-05 (GHOST-NOTE): flash-attn CK build RESTORED, from source, packaged as a pinned wheel — real fix following the 12:xx restoration attempt above (Kim: "worth it, build + package"). Cloned `github.com/ROCm/flash-attention` @ `rdna_fmha_gfx1100_gfx1201` (CK submodule pin `08792e0b3...` matched `docs/flash-attn-ck-rdna4.md` exactly), applied the §5 glue patches from `rocking/update_ck` (`d81a98630`, 3 files, `sink_ptr` fix) + regenerated `flash_common_hip.hpp`, applied the §5b 13-arg `FlashAttnFunc.backward` patch (line 904: 12→13 return values — `FlashAttnVarlenFunc.backward` at line 1009, already-correct 17/17, verified untouched; had to line-anchor the edit since both return statements share a long common substring that fooled string-based matching). Built with `uv build --wheel` (not `uv pip wheel` — not a real uv subcommand) against `stable-audio-3/.venv`'s actual torch (`2.10.0+rocm7.2.3.git1a270074`), `GPU_ARCHS=gfx1201 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE`, `MAX_JOBS` 6→7 mid-build (bumped once Kim confirmed CPU headroom; ninja resumed from `.o` files on disk, zero recompiled — killed cleanly at file 457/2397, confirmed exact `.o` count match before restart) — ~80 min total, 2397 kernel files. Result: `SAO/my_wheels/flash_attn-2.8.4-cp313-cp313-linux_x86_64.whl` (42MB), installed + verified — `flash_attn_2_cuda` imports clean (no ABI mismatch, unlike the two stale cached wheels from the earlier attempt), doc's varlen smoke test passes (`max abs diff vs SDPA: 2.81e-04`, matches the documented ~2.89e-04), ran live alongside the active `dora128_everything_8ep_lr1x` training job with zero VRAM/disruption impact (checked before and after — training PID 328308 unaffected). Pinned in `stable-audio-3/pyproject.toml` (`[tool.uv.sources] flash-attn = {path = "../my_wheels/..."}`, matching the existing ROCm-torch-wheel pinning convention) so a future `uv sync` can't silently prune it again — **not yet re-synced** (a training job is live; re-sync deferred to a safe window). `docs/flash-attn-ck-rdna4.md` §7b added: the wheel-packaging + pin recipe, and an explicit warning that this wheel is ABI-tied to the exact torch build and must be rebuilt (not reused) across any torch version bump.
- [2026-07-05 18:51] (everything-dora) run 1/2 done (lr 2e-4) -> dora128_everything_8ep_lr1x (18:51)
- 2026-07-06 (CONTINUITY): **Weight-garden KEY FINDING (Kim's ear):** the `shuffle` op (value-preserving weight permutation) is categorically different from the value-changing ops (drift/blur/contrast/tilt) — it sounds MUSICAL, not glitchy. `shuffle_05` (amount 0.05, decay late rate 0.3, seed 777) on both goa + ambient prompts "evolved to new musical forms compared to baseline" (Kim), no noise/artifacts. Mechanism: shuffle preserves the exact weight multiset (every value/magnitude/variance intact), only relocates 5% of entries → the model stays statistically on-manifold ("same trained brain, rewired") vs value-ops that push off-manifold ("damage"). Confirms the garden's "different wrong mind vs damage" hypothesis. Late-decay concentrates rewiring in surface blocks (deep structure preserved → coherent). Seed-reproducible = an instrument. Recipe: weight_garden_explore1/run_meta.json. NEXT (Kim's call): sweep shuffle amount 2/5/8/10% × seeds (each seed = a distinct coherent variant) × decay early-vs-late.
- 2026-07-06 (GHOST-NOTE): step-count diagnostic VERDICT + doc lock-in — Kim's ear check on the staged 24-vs-48-step page (`dora128_everything_8ep_lr1x_ep7_steps_diag`, 1 prompt COMMON × 5 seeds, T=256): "the 24-step versions are nearly identical to 48-step ones. Some slight differences in detail, but not really quality." Matches the objective deltas already logged (spectral centroid/RMS, small mixed-sign, no systematic drift). `steps=24` locked in as the canonical-sweep default in `docs/canonical-eval-spec.md` §2c. All 12 DiT ONNX exports for the main 72-clip DoRA weight×length sweep (`dora128_everything_8ep_lr1x` ep7, strengths {0.8,1.0,1.4} × lengths {256,512,1024,4096}) now complete + validated (cos≈1.0 throughout, incl. T=4096 where max|Δ| is larger in absolute terms but rel error still ~0.00% — expected at larger activation scale). Next: the 72-clip generation pass itself (3 prompts × 2 seeds × 3 strengths × 4 lengths) via `onnx/dit_onnx_infer.py --provider cpu`, text-cond npzs already precached.
- 2026-07-06 (CONTINUITY): weight-garden qualitative catalog started (docs/weight-garden-audition-notes.md) — Kim's ear-verdicts + mechanism. New: blur_attn = temporal smearing ('dried'/compressed decays, mild evidence for attn≈time); shuffle 2% = gentler 'rewired mind' than the 5% new-melody result (amount = intensity dial). TODO: qualitative pass on the failed/neutral mutations.
- [2026-07-06 01:10] (everything-dora) run 2/2 done (lr 6e-4 = 3x) -> dora128_everything_8ep_lr3x — chain COMPLETE (01:10)
- [2026-07-06 01:11] (continued-goa) START — 3 more epochs on newcaptions ep4 (stable/CK venv) (01:11)
- [2026-07-06 01:11] (continued-goa) START — 3 more epochs on newcaptions ep4 (stable/CK venv) (01:11)
- [2026-07-06 01:13] (continued-goa) done — 3 more epochs -> dora128_newcap_continued_3more (now 8ep total) (01:13)
- [2026-07-06 01:13] (continued-goa) done — 3 more epochs -> dora128_newcap_continued_3more (now 8ep total) (01:13)
- 2026-07-06 (GHOST-NOTE): main DoRA weight x length sweep LANDED (72 clips, `dora128_everything_8ep_lr1x_ep7_sweep`) -- 3 prompts (common/medium/rare by caption-frequency rank) x 2 seeds x 3 DoRA strengths [0.8,1.0,1.4] x 4 lengths [256,512,1024,4096 frames], steps=24 (per the confirmed diagnostic), cfg=6.0. **Mid-sweep pivot to native GPU generation**: Kim freed the GPU ("realize the whole audition plan on the GPU") after the 12 CPU/ONNX DiT exports were already built+validated; switched from the per-length ONNX CPU pipeline to a single `StableAudioModel.from_pretrained('medium-base', device='cuda')` load + `load_lora()` once + live `set_lora_strength()` per rung (LoRA applies unmerged via parametrization, so switching strength needs no reload/re-merge) -- ~100x faster than CPU (T=4096: ~12s/clip on GPU vs 1230s measured on CPU/ONNX for the same rung; T=256 87s->~9s, T=1024 298s->~11s). All 72 clips generated in ~13 min total vs a projected ~6+ hours on CPU for the T=4096 rung alone. The 12 ONNX exports + text-cond npz precache remain on disk (`onnx/exports/`) for tomorrow's CPU-idle testing, unaffected. Transcoded to AAC 128k, staged + `_meta.json` sidecar written, `build_evals.py` rebuilt clean (leak-scanned: no absolute paths/checkpoint filenames in the rendered HTML, only the redacted purpose text). Ready for WINTERMUTE's transfer. Also: the 24-vs-48-step diagnostic got Kim's ear verdict ("nearly identical... not really quality") -- `steps=24` locked in as the sweep default in `docs/canonical-eval-spec.md` §2c.
- 2026-07-06 (GHOST-NOTE): eval-tables-human-first build (Kim-greenlit spec docs/superpowers/specs/2026-07-06-eval-tables-human-first.md) LANDED for the renders_dora test case, per §10 build order. `control/sa3_control/pq_score.py` (+ stable-audio-tools mirror) generalized with a `_DORA` filename regex (`<runid>_epoch<N>-step<M>__p<pi>_seed<seed>.wav`, no gain/density -- carries `checkpoint`/`epoch`/`step` instead); scored all 51 renders_dora clips via the mir venv (11/51 below the CE/PQ floor). `Misc/eval_grid.py` gained `load_dora_data()` (checkpoint x prompt x seed records) + `render_table_compare_page()` (sortable Excel-style columns, per-column min->max colour self-normalized to the SHOWN checkpoint's realized range per Kim's explicit non-comparable-across-checkpoints call, dual-pane with independent checkpoint dropdowns + synced sort -- clicking a header on either pane reorders both by the same row identity -- + shared same-playhead); also added an explicit `checkpoint` key to the existing gain x density grid records (control-grid rendering unaffected, verified). `Misc/build_evals.py` routes `renders/` dirs through grid -> table -> flat fallback in that priority (`find_renders_source_dir()` + `RENDERS_SOURCE_DIRS`), and `real_date()` now resolves DoRA-audition dates from the real source dir too (renders_dora now dates 2026-06-29, not the transcode day). Accessibility: `~/evals` symlinks to `~/.cache/evals_aac` (non-hidden `file://` browsing) + the landing states the canonical `aavepyora.online/files/evals/` URL. Verified the generated JS in a stubbed-DOM node harness (screenshot capture is still broken in this environment) -- render, sort on every column both panes, play/pause toggle, all clean. Leak-scanned the rendered HTML (redact() already strips abs paths/ckpt names at render time, confirmed empty). **Bonus fix, unrelated to the spec**: hit `/run/media/kim/Mantu` I/O-erroring mid-build (drive had silently remounted as `Mantu1` after a drop -- Kim confirmed "the id changed"); made `build_evals.py`'s `MANTU` resolution probe both names and pick whichever's actually readable, so a future remount-drift self-heals instead of silently downgrading every composed_sweep grid to the flat fallback (which is what my first two rebuilds during the outage window did, caught before handoff -- WINTERMUTE held the sync). Rebuilt clean after the fix; both A_cc_v2 (grid) and renders_dora (table) confirmed correct. WINTERMUTE cleared to sync both control_runs/* and renders/* now.
- [2026-07-06 03:18] (WINTERMUTE) avp corpus overnight: MIR pipeline (313 own-music tracks, flamingo OFF + aavepyora/aavepyora-o trigger caption, BS-Roformer sep) + bungee->rubberband augmentation (9/track: pitch +-1/+-2 st, tempo +-BPM offsets) launched detached on UUID drive avp-analyzed (resumable, spills into 07-07). GHOST on stem classification (40 folders, 9 cats, non-destructive). Eval-tables spec LIVE: renders_dora table+compare + rebuilt control grids transferred+verified. Infra: Mantu remounted as Mantu1. Handoff: avp-analyzed/_STATUS.md
- 2026-07-06 (GHOST-NOTE): AVP stem classification (Kim task via WINTERMUTE, feeds his later stem-chroma phase) DONE for all 40 tracks / 983 top-level stems under `9a410a1d.../avp-stems`. New tool `Misc/classify_avp_stems.py` (mir venv, CPU-only, filename heuristics only per the task): word-boundary keyword rules across 9 categories (kick/drums/bass/acid/leads/arp_keys/pads/sfx/speech) + an envelope-descriptor fallback (fast/short decay-release -> arp_keys, slow attack -> leads) for stems with no direct instrument noun. Iterated the rule set against the real vocabulary (dry-run -> inspect misses -> expand -> re-check) rather than guessing keywords blind: added `fx` (huge miss -- 85 files said "fx" and it wasn't even in the SFX list initially), breakbeat/world-percussion names (djembe/darbouka/cajon/tabla/claves/guiro) to drums, world/orchestral melodic instrument names (flute/oboe/horn/duduk/sitar/etc, "riff", "hoover", "bowed") to leads, plucked-instrument names (mbira/kalimba/kantele) + "ostinato" to arp_keys, "swelling"/"cluster(s)" to pads, "field recording"/"sound effect(s)"/"footstep(s)" to sfx. Caught + fixed a real regex bug mid-run: `_` counts as `\w` in Python regex, so `\bdrums\b` never matched `Nation_drums.flac` -- normalizes `_`/`-` to spaces before matching now (re-ran clean after the fix; verified on the exact filenames that exposed it). Final totals: kick 73, drums 161, bass 80, acid 48, leads 108, arp_keys 114, pads 76, sfx 87, speech 37; 324 stems flagged `ambiguous` (multiple category keywords fired -- e.g. Kim's named acid-vs-lead / bass-vs-lead-melody pairs) with a best-guess category + candidate list rather than a silent forced answer; 118 genuinely unclassified (mostly bare "melody synth + generic adjectives" with no instrument/envelope cue at all -- an honest filename-heuristics ceiling, not a bug); 81 excluded (`full mix` prefix, per the task). **Data-quality finding**: 3/40 tracks (`Two Suns in Phrygia`, `silicon gate $d404`, `lingua sama heavy goa trance`) use a DAW preset/session-name convention (`Master.flac`, `11 Polymer.flac`, numbered `Bounce.flac` files) instead of the rich descriptive tags every other track has -- filename heuristics can't place most of those stems; flagged to WINTERMUTE as a data issue, not a category-set issue (the 9-category set fits the well-named 37/40 tracks cleanly). Non-destructive throughout: per-track `_classification.json` manifest (category + ambiguous flag + matched keywords, for Kim's review), category subfolders of SYMLINKS (originals untouched), per-category `CATEGORY_downmix.flac` (peak-normalize-down sum; 4 sr-mismatched inputs in one track were skipped from their downmix rather than distorted, per the [-1,1]-writer convention).
- 2026-07-06 (GHOST-NOTE): fixed broken "Curated players" links on the evals landing (Kim: "None of the Curated players work, the html files are not found"). Root cause: `build_evals.py`'s `build_landing()` always LINKED to `riffer/onset_eval.html` etc. but never actually SYNCED those pages into the staging mirror -- they only ever existed in the separate `~/riffer-evals/` repo. The `clips*` subdirs under `~/.cache/evals_aac/riffer/` were already present (synced by some earlier/other process), but the 8 curated `.html` files themselves were simply never copied, so every curated-player link 404'd both locally (`file://`) and presumably on the served site too. Added `sync_riffer_pages()` (module-level `RIFFER_HTML` list, single source of truth also used by `build_landing()`'s link generation) — copies the 8 pages from `~/riffer-evals/` into `OUT/riffer/` on every `build_evals.py` run, plus a cheap staleness check for the `clips*` dirs (skip re-copy if file count already matches, avoids re-copying gigabytes of audio every rebuild). Verified all 8 curated pages now exist and leak-scanned clean (no absolute paths). Local fix confirmed; WINTERMUTE should check whether the served `/files/evals/riffer/*.html` paths were also 404ing (likely yes, since his sync source — the local staging dir — never had these files either) and pick this up on his next rsync pass.
- 2026-07-06 (GHOST-NOTE): wrote `EVALUATIONS.md` (Kim's ask) — a taxonomy of the eval families we run (control-adapter grids, DoRA auditions, weight/length sweeps, model-soups, cross-prompt/flow-sep/weight-garden renders, LatCH sweeps) mapped to the 3 UI patterns (grid / sortable table (+dual-compare) / flat clip grid) plus the decision rule for picking one, so the next eval doesn't reinvent a 4th pattern. Also fixed the concrete complaint that prompted it: Kim found `control_runs/A_cc_v2`'s gain×density grid "very hard to read" and asked for it to be organized like the new table view. Rather than fork a second template, upgraded the EXISTING grid⇆ranked toggle in `eval_grid.py`'s `GRID_JS_TEMPLATE` — `renderRanked()` now builds a full Excel-style sortable table (click any column header to sort asc/desc, columns: prompt/gain/density/measured/error/CE/CU/PC/PQ/spectral_balance) with per-column colour grading self-normalized over the page, reusing the `.tc-table` CSS class already shipped for the DoRA compare view (no new CSS needed — `evals.css` already concatenates `GRID_CSS + TABLE_CSS`). Verified in the same stubbed-DOM node harness pattern as the DoRA table (default grid renders, toggle produces exactly one table, header click sorts + flips arrow direction, row click doesn't throw, toggle back to grid restores the 3 gain-blocks) — caught and fixed one real issue along the way: the header row was built via `table.innerHTML = <string>` then `querySelectorAll('th[data-col]')` to attach handlers, which real browsers support but is fragile to test/reason about; switched to building header `<th>`s via `document.createElement` + direct `.onclick` assignment, matching the already-proven pattern used for data rows. Leak-scanned clean.
- 2026-07-06 (GHOST-NOTE): sortable table is now the DEFAULT view on control-grid pages (Kim's ask), heatmap grid is the toggle-away alternate; updated the descriptive paragraph accordingly. **Real finding surfaced by the new table** (Kim spotted it immediately by eyeballing sorted numbers): on `A_cc_v2`, requested onset-density >= ~7.5 produces a HARD CEILING around 9.2-9.4 onsets/sec regardless of gain (1/2/3) or how high the request goes (7.5 through 12 all measure ~9.3). Verified this is real, not a rendering/caching bug: pulled the actual audio for psytrance/gain-1/2/3 at density=9 and re-ran onset detection directly -- all three hit EXACTLY 221 onsets over the identical 23.777234s clip length (giving a bit-identical rate), but the onset TIMESTAMPS genuinely differ between gains (confirmed via `flatness` also differing) -- so the audio is NOT identical, the model is genuinely capping the number of distinguishable onsets it will produce. The ceiling value matches a 16th-note grid at 140 BPM almost exactly (theoretical 9.333/sec vs measured 9.295/sec, 0.4% off), and the "aggressive upbeat goa trance" prompt (same tempo family) shows the identical ~9.2-9.6 ceiling. Read: this looks like a genuine compositional ceiling from the base model's rhythmic prior (won't subdivide faster than a 16th note at the implied tempo) rather than a control-adapter failure -- extra gain past the ceiling perturbs timing/timbre within the existing grid instead of adding onsets. Worth checking other control-adapter runs the same way now that every control-run page has sortable columns (sort by `error` descending surfaces this instantly).
- 2026-07-06 (GHOST-NOTE): avp corpus SA3 latent encode BUILT + LAUNCHED (WINTERMUTE spec, relayed by Kim, confirmed via DM). Extended `stable-audio-3/scripts/sa3_beat_manifest.py` (`--include-augmentations`) to treat each `<track>/augmentations/<variant>/` as a first-class track: since variant folders have no `.DOWNBEATS` of their own (no re-analysis has run -- Phase D derive-vs-reanalysis validation is still open per `avp-analyzed/_STATUS.md`), downbeats are DERIVED from the parent's real downbeats by the *measured* duration ratio between parent and variant npz (`scale = variant_duration / parent_duration`) -- exact for both families since Bungee's `set_pitch()` doesn't touch timing (scale~=1) and `set_speed(x)` stretches time by exactly `1/x` by construction, so one formula covers both without re-deriving BPM. Extended `sa3_encode_from_manifest.py`: `--trigger-caption` (verbatim copy of `inject_trigger_caption.py`'s `word_for()` -- sha1(parent_track_name)%2 -- so every crop and every augmentation of a track shares the identical deterministic aavepyora/aavepyörä spelling without depending on that script having run first, avp's `.INFO.caption` is still `None`); co-located `TIMESERIES.npz` lookup (avp keeps it beside each track/variant folder, not in a flat `--timeseries-root`, with a fallback for the older flat-layout corpora); augmentation-variant crops get a MINIMAL info dict, deliberately NOT copying the parent `.INFO`'s audio-domain scalar features (bpm/onset_density/harmonic_*) since those describe the unshifted original and would be actively wrong on a pitch/tempo-shifted variant -- left as Phase D's open question, not preempted here. Verified end-to-end on a 4-crop smoke test before the real run: latent shape/dtype `(256,4096)` fp16 matches `latents_sa3` exactly, timeseries companion resampled correctly, trigger caption correct and IDENTICAL between a track and its variants, minimal-vs-full info dict split working as designed. Manifest: 2393 crops from 142 tracks (of 313 total -- rest still mid BS-Roformer separation, resumable, a re-run picks up newly-finished tracks) + 1035 augmentation-variant crops (199 variants dropped for falling under the 380s crop minimum after tempo-speedup). Full encode launched (GPU idle, no collision) -> `/home/kim/Projects/latents_avp` (NVMe, sibling to `latents_sa3`, confirmed path). In progress.
- 2026-07-06 (GHOST-NOTE): avp encode job crashed at 160/2393 crops on a genuine bug, fixed + resumed. Root cause: 233/1177 unique source files in the avp corpus are 48kHz (personal music collection, not uniformly 44.1kHz), and `sa3_encode_from_manifest.py` computed the read offset/frame-count from a FIXED 44100 constant regardless of the file's real rate -- on a 48kHz file this reads the WRONG TIME WINDOW entirely (not merely a dtype issue), and separately `stable_audio_3`'s own internal resampler (`T.Resample` inside `preprocess_audio_list_for_encoder`) crashes on fp16 input (`HalfTensor` vs the resample kernel's `FloatTensor` -- a latent bug in the model repo, not patched there). Fixed in the encode script: cache each file's real samplerate via `sf.info()`, read at that NATIVE rate (offset/frame-count computed from it, not the 44100 constant), resample to 44100 in fp32 myself before any fp16 cast so the model's internal resample path never triggers, pad/trim to the exact `CROP_SAMPLES` count. Verified against the exact file that crashed (`Aavepyörä - Light in Darkness 102 BPM`, 48kHz) in isolation before resuming: decodes back to exactly 380.4357s duration, sane peak/RMS, no crash. Added `--skip N` to resume past already-encoded manifest rows without re-encoding them (`find_next_index` only continues the output numbering, it doesn't dedupe against the manifest by itself). Resumed from row 160 (the 160 crops encoded before the crash are intact and correct -- all from 44.1kHz sources, unaffected). Running now.
- 2026-07-06 ~17:50 (CONTINUITY): GPU coordination per Kim — avp encode (G, running, ~2400+1035 aug crops -> latents_avp) goes first, THEN the 3 missing newcap-fusion epochs. Built the missing piece off-GPU: train_lora `--warm_start_ckpt` (new scripts/warm_start.py + 5 tests) = TRUE continuation from old-format ckpts that ckpt_path rejects — restores adapter weights + full FusionOpt Schedule-Free z/x optimizer state; only epoch numbering restarts. run_continued_goa.sh repointed to the live drive + pre-flight VRAM gate (>1.5GB used = abort; the 01:11 attempt died on exactly that external-pressure OOM, and the earlier one on the ckpt KeyError). Fires on G's GPU-FREE ping.
- 2026-07-06 (GHOST-NOTE): avp corpus SA3 latent encode COMPLETE. Final: 2393 crops (142 primary tracks + 1035 augmentation variants worth of 44.1kHz-native crops, plus the 233-affected-file 48kHz batch that crashed once and was resumed clean after the fix -- see the prior WORKLOG entry for the bug/fix detail). Resumed run: 2233 encoded, 0 skipped, 0 further errors -- the native-rate-read + fp32-resample fix held across every one of the 233 48kHz files with no exceptions. `/home/kim/Projects/latents_avp`: 2393 matched `.npy`/`.json`/`.TIMESERIES.npz` triplets, 6.0GB, `(256,4096)` fp16 latent shape verified identical to `latents_sa3`. Spot-checked a late-batch primary crop (58-key full `.INFO` scalar set, prompt = deterministic trigger word) and an augmentation-variant crop (21-key minimal dict, `is_augmentation`/`variant_name`/`parent_track` provenance correct, same trigger word as its parent, confirming the sha1-hash determinism holds across the whole corpus) -- both clean. Reported to WINTERMUTE, ready for his stem-chroma phase E (or whatever consumes it next). The rest of the 313-track avp corpus (171 tracks still mid-BS-Roformer-separation as of this session) will need a manifest+encode re-run once separation catches up -- both scripts are resumable (`--skip`) and idempotent (only new track/variant folders with a `full_mix.*` get picked up).
- [2026-07-06 20:25] (continued-goa) START — 3 more epochs on newcaptions ep4 (stable/CK venv) (20:25)
- [2026-07-06 22:25] (continued-goa) done — 3 more epochs -> dora128_newcap_continued_3more (now 8ep total) (22:25)
- 2026-07-06 ~23:55 (CONTINUITY): PROMPT-STYLE EVAL SET COMPLETE — newcap8_promptstyle (Mantu1/sa3_lora_runs): 60 clips, 5 arms (base / newcap ep4 / newcap 8ep continuation / everything-8ep lr1x / lr3x) x 3 prompts x plain-vs-Stability-styled (TrackType+Genre prefix per prompting.md — first time we've ever used the trained-in convention) x seeds 1234/4242, 47s/16 steps/cfg6, all finite, merged run_meta.json. p1 of the standing eval prompts replaced per Kim (acid techno rendered badly) with "Hypnotic melodic goa trance". G asked to build the eval UI per W's eval-grid spec (tables + CE/PC shading + run-comment box + same-playhead cells). Warm-start continuation rsynced back to Mantu1. New tool: eval/eval_prompt_styles.py.
- 2026-07-06 (GHOST-NOTE): checked the "28 missing avp tracks" delta WINTERMUTE flagged -- not a stale-manifest bug. Re-ran `sa3_beat_manifest.py` against the current `avp-analyzed` state: it finds all 170 track folders with a `full_mix` (matches WINTERMUTE's count exactly), same 142/28 split as before. Directly measured the 28's durations: 254.8s-378.8s, all under the fixed T=4096 crop window (380.44s) -- they have complete `full_mix`+stems+beats+downbeats+timeseries (WINTERMUTE verified this, and it's true), but file-completeness and long-enough-for-one-crop are two different checks; `sa3_beat_manifest.py` has always dropped sub-380s tracks by design, same rule applied to every other corpus encoded this session. So there's no delta to encode under the current fixed-crop scheme -- 142 tracks + 1035 augmentation variants (2393 latents total) IS the complete set. Reported to WINTERMUTE with options if the 28 are wanted anyway (leave excluded, consistent with precedent; or a genuinely different crop scheme just for them -- new scope, not a bugfix). Not blocking, corpus stands as-is.
- 2026-07-07 (GHOST-NOTE): built the eval-grid UI for `newcap8_promptstyle` (5 arms x 3 prompts x plain/styled x 2 seeds, 60 clips). New page type: dual-pane arm compare where each row pairs the PLAIN and STYLED variant of the same (prompt, seed) side by side -- two play buttons + CE/PC columns per style + a ΔCE column -- per Kim's explicit ask ("the plain-vs-styled columns side by side per arm is the key comparison"). Added: `pq_score.py`'s `_PROMPTSTYLE` filename convention (`{arm}__{promptkey}_{plain|styled}_s{seed}.wav`, mirrored to stable-audio-tools) + scored all 60 clips; `eval_grid.py`'s `load_promptstyle_data()` (pairs plain+styled rows per combo, reads prompt text from the run's `run_meta.json`) + `render_style_compare_page()`/`STYLE_CSS`/`STYLE_JS_TEMPLATE` (reuses the `.tc-table`/dual-pane machinery from the human-first table spec, no new CSS families); `build_evals.py` routing (`RENDERS_SOURCE_ROOTS` generalizes `find_renders_source_dir()` to resolve any `sa3_lora_runs`-hosted render set by name, not just a hardcoded list; grid -> DoRA-table -> style-compare -> flat priority). Caught + fixed a real bug before shipping: `load_dora_data()` matched on `checkpoint` alone, which prompt-style rows also carry (the arm name) -- it was silently swallowing this data with the WRONG renderer; fixed by excluding rows that also carry `prompt_key`. Also fixed a wording bug (page said "N prompt×seed combos" but N was actually total records across all arms, not unique combos). WINTERMUTE had already transcoded the 60 clips + built a stopgap placeholder page (not pushed) while waiting for this; dropped this `index.html` into the already-staged `~/.cache/evals_aac/renders/newcap8_promptstyle/` dir (+ copied `run_meta.json` so the purpose/description render correctly) rather than duplicate his transcode work. Verified in the stubbed-DOM node harness (renders, sorts, play-click, no throws) and leak-scanned clean (no absolute paths/checkpoint filenames -- arms shown as plain labels, ckpt paths never enter the record at all). Separately: checked the "28 missing avp tracks" WINTERMUTE flagged -- not a stale-manifest bug, they're genuinely under the 380.44s crop-length threshold (254.8-378.8s measured directly); 142 tracks + augs (2393 latents) is the complete set under the current fixed-crop scheme, no delta to encode. Handing off to WINTERMUTE for leak-scan + deploy.
- 2026-07-07 ~01:30 (CONTINUITY): KIM'S AUDITION FOLLOW-UPS ALL RENDERED — (1) evr3x@0.33 arm (12 clips into newcap8_promptstyle); (2) newcap8_promptstyle_longform: 12x 3:10 renders, 2048 frames with a 512-frame latent slerp crossfade mid-render (longform CrossfadeStitcher; dtype gotcha: slerp's fp32 ramp vs fp16 decoder — cast before decode); (3) newcap8_density_control: 432/432 clips, onset LatCH (beat_grid impulse target, rho=mu=512 — retests the "onset heads dead" verdict with impulse targets) vs FusionCC FiLM (gain 6) vs both-at-half, d3/d7, full grid. New docs: checkpoint-hall-of-fame.md (entry 1: x20b3ygb ep3-5400 r16 fusion), todos additions (r16 rerun w/ new dataset stack, big-rank damping, novelty-gated updates). W asked to re-sync mirror; G's UI scope extended. New tools: eval/{longform_crossfade_eval,density_control_eval}.py.
- 2026-07-07 (GHOST-NOTE): fixed two real issues Kim hit on the live control_runs/A_cc_v2 page. (1) READABILITY: the sortable table (added 2026-07-06 for control grids) was missing a `seed` column -- rows sharing the same prompt (and near-identical gain/density after sorting) looked like unexplained duplicates because the ONE thing distinguishing them wasn't shown at all. Added `seed` to `TABLE_COLS` in `eval_grid.py`'s `GRID_JS_TEMPLATE`, and clarified the page's descriptive text explicitly: "ONE checkpoint (this page is a single trained adapter) · rows vary by prompt/seed/gain/density -- not by checkpoint" (Kim's exact question -- "different checkpoints? seeds?" -- is now answered on the page itself). (2) PLAYBACK GLITCH: "the sound tends to cut up right after hitting play on a row" -- root cause: all three play() implementations (grid heatmap, DoRA table+compare, prompt-style compare) seeked to the shared playhead position as soon as `loadedmetadata`/`readyState>=1` (HAVE_METADATA) fired, which is too early for a compressed AAC stream served progressively -- seeking into a not-yet-buffered position produces an audible stutter right at playback start. Replaced all three copies with a shared `seekAndPlay()` helper that waits for `readyState>=3` (HAVE_FUTURE_DATA) or the `canplay` event (whichever fires first, with a 1.2s fallback timer so a slow/odd network state can't hang playback), plus an explicit `audio.pause()` before reassigning `.src` on every click (defensive, avoids any in-flight-seek/decode overlap when switching clips). Verified in the stubbed-DOM node harness (headers include seed, row click registers the canplay listener instead of seeking immediately, no throws) and leak-scanned clean. Same fix applies automatically to every other page using these three templates (renders_dora, newcap8_promptstyle, all composed_sweep grids) since they share the same JS templates.
- 2026-07-07 (GHOST-NOTE): aggregated the "dozens of onset control N links" mess on the evals landing (Kim: "that's messy AF"). `control_runs` landing entries went from 104 -> 14 (12 curated + 2 new). Surveyed the 90 generic-labeled ("onset control N"/"bracket sweep N"/etc) entries first via a research agent rather than guessing at the split: 80 onset-control, 6 control-run, 4 bracket sweep, 1 collapse test, 1 comparison; only 64/80 onset-control dirs actually have an `onset_eval.json` gain x density grid, the rest are heterogeneous (auditions/multiprompt/trajectory/soup/pilot/bracket). Built TWO new pages instead of forcing everything into one: (1) `_onset_control_audit` -- `eval_grid.py`'s new `render_checkpoint_audit_page()`/`AUDIT_JS_TEMPLATE`, a single dropdown over all 64 independent checkpoints + one sortable table for whichever is selected (not a dual-pane compare -- these are unrelated experiments with different sweep ranges, a synced row identity across them would be a mostly-blank union table); 2941 records total. (2) `_misc_uncurated_runs` for the remaining 28 structurally-different runs. **First design was wrong and caught before shipping**: my initial `write_misc_bundle_folder()` inlined every member's clips as `<span class="cell">` elements onto one flat page -- rebuilt and found via `grep -c 'class="cell"'` that this was 12237 cells on one page, not the "~28 small pilots" I assumed; several "misc" runs are actually large multi-epoch training-telemetry sweeps (`onset_AdamW_lr7.5e-5_randomcrop_20ep` alone is 2640 clips). Redesigned: misc runs now still get routed through the exact same grid/table/style/flat writer logic as any normal folder (so each keeps its own correctly-sized real page, e.g. the 2640-clip run gets its own flat player), and `_misc_uncurated_runs` became a lightweight table-of-contents linking to each member's page (`../<name>/index.html`) with date/subtitle/verdict/clip-count -- zero inlined clips on the index itself, verified. Also fixed the shared `PLAYER_JS` seek-glitch (same `readyState>=3`/`canplay` fix as the grid/table/style templates, applied here too since flat-player pages use it). Verified the audit page's JS in the stubbed-DOM node harness (64 options render, sortable table builds, no throws) and leak-scanned both new pages clean (0 absolute paths / checkpoint filenames / addrs). Handed to WINTERMUTE for deploy.
- [2026-07-07 03:23] (night-0707) g175 grid done; starting transition_lab (03:23)
- [2026-07-07 03:23] (night-0707) transition_lab done (exit 1) -> newcap8_transitions (03:23)
- [2026-07-07 03:24] (night-0707) familiarity smoke FAIL (exit 0) -> stage D will be skipped (03:24)
- [2026-07-07 03:24] (overnight-0707) A START — goa r16 fusion, new dataset stack (tiered captions + TrackType 0.5), 8ep (03:24)
- [2026-07-07 04:19] (overnight-0707) A done -> dora16_goa_newstack_8ep (exit 1) (04:19)
- [2026-07-07 04:19] (overnight-0707) B START — avp r16 dora-rows fusion lr2e-4 8ep (trigger prompts, full-mix crops) (04:19)
- [2026-07-07 04:19] (overnight-0707) B done -> dora16_avp_8ep (exit 0) (04:19)
- [2026-07-07 04:19] (overnight-0707) C START — avp r128 ADJUSTED (alpha 45 = rsLoRA alpha/sqrt(r) matched to r16) 8ep (04:19)
- [2026-07-07 04:21] (night-0707) g175 grid done; starting transition_lab (04:21)
- [2026-07-07 04:22] (night-0707) g175 grid done; starting transition_lab (04:22)
- [2026-07-07 04:23] (night-0707) transition_lab done (exit 0) -> newcap8_transitions (04:23)
- [2026-07-07 04:24] (night-0707) familiarity smoke PASS -> stage D armed (04:24)
- [2026-07-07 04:24] (overnight-0707) A START — goa r16 fusion, new dataset stack (tiered captions + TrackType 0.5), 8ep (04:24)
- [2026-07-07 04:40] (GHOST-NOTE) RENDERS_REFIXED batch shipped: 4 new/rebuilt eval pages + a global bug fix, ready for W's sync.
  (1) newcap8_promptstyle rebuilt with the evr3x_w033 arm (72 clips) — fixed load_promptstyle_data() to backfill
  clips staged ahead of pq_scores.json scoring (parses filenames directly, shows unscored rows as "·" rather
  than silently dropping the whole arm) — a real gap, not just this one arm; will recur whenever clips land
  before Audiobox scoring catches up. (2) newcap8_promptstyle_longform: real arm x seed-order table replacing
  the flat-grid fallback, with a "jump to crossfade" shortcut (computed from window_frames/total_frames at the
  SA3 10.767 Hz grid — confirmed exact against transitions' run_meta.json window_frames [768,1280], which
  matches my derived ~71.3s-118.9s almost exactly). (3) newcap8_density_control_g175: new grid UI (432 clips,
  arm dropdown + sortable table over prompt/style/seed/condition/density) + the control-authority column Kim
  asked for — wrote eval/measure_density_control_onsets.py (librosa onset_detect, same approach as
  sa3_control/multi_eval.py) and ran it over all 432 clips (mir venv, CPU-only, ~2min). (4) newcap8_transitions
  (6 clips, landed from the overnight transition_lab loop mid-session) — same table pattern as longform,
  transcoded the 6 wavs myself since they hadn't hit staging yet. (5) findings/status annotations: wired
  run_purposes.json's human-authored findings/status into eval_grid.py (provenance_html(), new PROVENANCE_CSS)
  and threaded through every render_*_page + write_folder call site — HISTORICAL/SUPERSEDED runs now get an
  auto-linked banner (verified: newcaption_ab correctly links to newcap8_promptstyle, old newcap8_density_control
  links to _g175), "current" runs get no banner, findings render as a "what we learned" box. Scope note: this
  only covers build_evals.py's own pipeline (control_runs/renders folders) — gain_knee.html and dora_results.html
  are separate riffer-evals curated pages with their own generators (build_dora_results_page.py; couldn't find
  gain_knee's), not wired up. Caught + fixed along the way: a PRE-EXISTING bug present in every write_*_folder
  call site (including my own new ones, since I'd copied the existing pattern) — head() was called with an
  already-html.escape()'d label, double-escaping any apostrophe/entity into garbage like "seeds&amp;#x27; segments"
  in every page title with a possessive in its name. One-line fix x8 call sites, verified zero remaining
  double-escapes site-wide. All new/changed pages leak-scanned clean (0 abs paths/ckpt filenames/addresses) and
  JS-verified via the node stubbed-DOM harness (density-control: 6-arm dropdown, 72-row table, no throws).
  Handed to WINTERMUTE for leak-scan + rsync + landing links.
- [2026-07-07 04:45] (GHOST-NOTE) findings/status extended to the two riffer-evals curated pages CONTINUITY
  cleared: dora_results.html (has a real generator, ~/build_dora_results_page.py — added a findings-box, ran
  it, all 276 AAC clips reused/cached so it was a fast regen) and gain_knee.html (confirmed NO generator exists,
  static HTML from the pre-run_meta era — hand-edited directly per CONTINUITY's explicit go-ahead, added its
  HISTORICAL banner auto-linking to newcap8_density_control_g175 + a findings box, matching its own dark-theme
  CSS since it doesn't share evals.css). Both leak-scanned clean, re-synced via build_evals.py's
  sync_riffer_pages(). This closes the findings/status task completely — all 7 dirs CONTINUITY named now carry it.
- [2026-07-07 09:12] (overnight-0707) A done -> dora16_goa_newstack_8ep (exit 0) (09:12)
- [2026-07-07 09:12] (overnight-0707) B START — avp r16 dora-rows fusion lr2e-4 8ep (trigger prompts, full-mix crops) (09:12)
- [2026-07-07 10:15] (GHOST-NOTE) Two more Kim asks (via CONTINUITY, after he went looking and hit gaps):
  (1) composed_sweep now has ONE findable page: A_cc/A_cc_v2/E_fusion/E_fusion_v2 (control-DiT adapter +/-
  LatCH, 162 clips each = 648 total) previously only existed as 2 of the 4 members individually staged
  (A_cc_v2/E_fusion_v2) each surfacing under a generic auto-derived label ("Stage 1 cell E re-render...")
  that never said "composed sweep" anywhere — unfindable by name, which is why Kim couldn't find it. Staged
  the missing A_cc/E_fusion (324 clips, transcoded from Mantu1, wasn't done before). Since these 4 stages are
  DIRECTLY comparable (unlike the unrelated onset-control-audit runs), built a new dropdown+FULL-grid-heatmap
  page (eval_grid.render_composed_sweep_page/COMPOSED_JS_TEMPLATE) rather than reusing the audit page's
  flat-table-only view — Kim explicitly wants "the full grid treatment (gain x density cells + corr coloring)",
  which needed a new renderer combining the checkpoint-audit's dropdown with the single-run grid page's
  heatmap/corr/toggle logic. Purpose text flags E_fusion_v2 as Kim's rated favorite. (2) Landing page gained
  a flat "All runs, newest first" section (33 entries, both categories merged, sorted by date only) above the
  existing Control-runs/Renders category split — Kim: "the front page does not make it easy to find runs
  simply in order of creation." Both verified: composed_sweep JS-harness-checked (163-row table, no throws),
  both leak-scanned clean. control_runs landing count went 14->13 (net: -2 individual entries +1 aggregate).
- [2026-07-07 11:28] (overnight-0707) B done -> dora16_avp_8ep (exit 0) (11:28)
- [2026-07-07 11:28] (overnight-0707) C START — avp r128 ADJUSTED (alpha 45 = rsLoRA alpha/sqrt(r) matched to r16) 8ep (11:28)
- [2026-07-07 13:47] (overnight-0707) B done (chain truncated after B per Kim; C+D -> TODO/LUMI-G) (13:47)
- [2026-07-07 14:08] (overnight-0707) transitions r2 done on GPU; finishing C's last epoch (14:08)
- [2026-07-07 14:30] (overnight-0707) C FINISHED — dora128adj_avp_8ep_final (8/8 epochs, warm-started from ep6) (14:30)
- [2026-07-07 15:05] (GHOST-NOTE) 3 more eval pages, all new models CONTINUITY flagged today:
  (1) dora16_goa_newstack_8ep — Kim's headline A/B (new caption stack vs the old HoF best). 30 unscored
  clips (9 newstack epoch ckpts + HoF x20b3ygb ep3-5400) x 3 prompts, no pq_scores.json yet. New renderer
  (eval_grid.render_epoch_progress_page/load_epoch_progress_data, write_epoch_progress_folder) — dual-pane
  like the DoRA compare but without the CE/CU/PC/PQ columns (would've all been empty "·"), pane A defaults
  to the LAST epoch, pane B auto-detects + pins to the HoF checkpoint from run_meta.json's checkpoints dict
  (matched by "hof" key + a distinctive tag fragment appearing in its value string) — verified both defaults
  land correctly (epoch7 / x20b3ygb). Source lived in a renders_cpu/ subfolder of the run dir (not the top
  level) — added a small RENDERS_SOURCE_ALIASES dict so the staged/landing name stays the descriptive run
  name instead of the generic "renders_cpu". (2) a2a_kaikkialla — full-track (7:39) a2a noise ladder of
  Kim's own Kaikki-Alla through two adapters (evr1x/newstack), nl 0.2-0.7. Combined the two per-adapter
  source dirs into ONE row=nl x col=adapter table (write_a2a_ladder_folder) via the same cross-folder
  relative-clip pattern as composed_sweep, diverting the two individual dirs out of the landing (same
  "one findable page, not two+one" precedent). Confirmed via mtimes the re-rendered (120s-clamp-fixed)
  clips were the ones staged, not stale ones. (3) newcap8_transitions_r2 — extended write_transitions_folder
  (built for r1) to group by LENGTH first (512f/1024f) then arm, since Kim's r2 hypothesis is whether a
  shorter total length fixes a weak-kick/noisy character. The transition-window fix generalizes cleanly:
  the crossfade sits at a FIXED FRACTIONAL position (37.5%-62.5%) regardless of total length — verified this
  ratio is identical across r1 (768/2048, 1280/2048) and r2's documented 1024-frame variant (384/1024,
  640/1024) — so per-length windows are computed as frac*that_length's_own_frame_count, not the literal
  frame numbers (which would be nonsensical applied to the 512f variant, since 640>512). All three
  leak-scanned clean, dora16 JS-harness-verified (both pane defaults confirmed programmatically). Handed
  to WINTERMUTE for sync.
- 2026-07-07 ~15:45 (CONTINUITY): CHROMA-MORPH TRANSITIONS SHIPPED — real-track A->B transitions (Kaikki-Alla/Angelic Particles/Vapausvoima cycle) with bungee beatmatch (B follows A; KA+AP both 147.7bpm, VV 139.7 stretched), 512/1024-frame latent slerp crossfades, graded a2a refine at nl .35/.42/.5/.55, and the PROVEN 06-25 stem-chroma LatCH head (cosine, gain 2048) morphing measured A-chroma->B-chroma across the window; plain refs for every config -> 48 clips, Mantu1/sa3_lora_runs/chroma_morph_transitions. Infra: model.generate now takes latch target_raw (per-frame measured targets) + guided-path init_latents (a2a UNDER LatCH guidance — new capability). Also: 3-track full a2a ladders at Kim's rates; CONSTRUCTS.md channel etiquette; generate() 120s sample_size clamp fixed everywhere.
- [2026-07-07 15:52] (GHOST-NOTE) chroma_morph_transitions page shipped — CONTINUITY's first-application test
  of a2a-under-LatCH-guidance (chroma-morph steering: stem-chroma head morphs A-chroma->B-chroma across the
  window). 48 clips: 3 real-track pairs (kaikki2angelic/angelic2vapaus/vapaus2kaikki) x 2 windows (512f/48s,
  1024f/95s) x 4 noise levels (0.35-0.55) x chroma/plain. New write_chroma_morph_folder nests exactly as asked
  ("grouped pair -> window -> nl with chroma/plain adjacent"): one §-section per pair (order taken from
  run_meta.json's declared pairs list, not alphabetical), one h3 per window, one table per window with nl rows
  and chroma/plain adjacent columns. Added a small h3 CSS rule (none existed before). Leak-scanned clean, JS
  syntax-checked. Purpose: this is the listening test for whether chroma-morph transitions beat plain on Kim's
  dissonance complaint — if so it becomes a standard tool. Handed to WINTERMUTE for sync.
- [2026-07-07 16:35] (GHOST-NOTE) Waveform popup player shipped (eval-tables spec §13, Kim's UI ask). Any clip
  ≥20s now gets a floating "〰" toggle (bottom-center bar) that opens a modal: rendered waveform (client-side
  fetch+decodeAudioData->min/max peaks->canvas, cached per URL for the session, no build-time sidecars),
  click/tap-to-seek, Space/←/→/Esc keyboard, phone-capable (full-width modal, 44px targets) with the design
  center on desktop (min(1400px,90vw) modal, 160px waveform). Decode-failure falls back to a plain seekable
  range input so the popup still seeks without the picture. Implemented as ONE shared module (WAVEFORM_CSS +
  WAVEFORM_JS in build_evals.py) injected via head() on EVERY page regardless of which renderer built it —
  works by patching window.Audio (catches every `new Audio()` the ~8 different eval_grid.py templates create)
  and separately scanning literal `<audio id="pl"/"lfpl">` DOM elements on DOMContentLoaded (the flat/longform/
  transitions/a2a/chroma-morph pattern) — so it drives whichever audio object a page is ALREADY playing rather
  than forking a second one, preserving the same-playhead convention through the popup exactly as the spec
  requires. Zero changes needed to any of the ~10 existing per-template play() implementations. Verified in a
  real node harness (not just a syntax check): bar+toggle correctly show only when duration>=20s and stay
  hidden under threshold, modal opens/closes, waveform decode path renders to canvas, decode-failure fallback
  path independently verified by breaking AudioContext availability. Leak-scanned clean across every page kind
  (grid/table/style/audit/density/composed/epoch-progress/flat/longform/transitions/a2a/chroma-morph). Riffer-
  evals curated generators intentionally NOT touched yet -- spec explicitly calls that a follow-up, not now.
  Handed to WINTERMUTE for sync.
- 2026-07-07 ~16:30 (CONTINUITY): PURE chroma transitions shipped (chroma_transitions_pure, 12 clips): originals intact outside the window, bridge inpaint-generated under chroma-morph guidance, plain controls. First 48-clip batch relabeled the 'refine' VARIANT (whole-composite a2a x nl -- Kim: hyper interesting, a DJ-tool primitive for the mir/plots viewer's lowkey DJ ambitions). Day's transition family complete.
- [2026-07-07 16:40] (GHOST-NOTE) chroma_transitions_pure page shipped — the last of today's transition family
  (pure / refine-hybrid=chroma_morph_transitions / r2-length-test=newcap8_transitions_r2). 12 clips: 3 pairs x
  2 windows x chroma/plain, NO noise-level axis (unlike chroma_morph_transitions) — original A/B audio is
  bit-intact outside the window, only the bridge is inpaint-generated. New write_chroma_pure_folder (couldn't
  reuse write_chroma_morph_folder directly — the two schemas aren't a strict superset/subset: pure has a
  {method} token and no nl, morph has nl and no method — genuinely different filename grammars, not just a
  missing dimension), same pair/window section nesting, single chroma/plain row per window since there's no
  nl to index by. Pair order pulled from run_meta's declared list same as the sibling page. Leak-scanned clean,
  JS syntax-checked. Handed to WINTERMUTE.
- [2026-07-07 16:55] (GHOST-NOTE) Closed 3 gaps CONTINUITY flagged + shipped the waveform-shading enhancement:
  (1) a2a_angelic_evr1x + a2a_vapausvoima_evr1x (never got an explicit page ping) now have pages, and
  a2a_kaikkialla_evr1x's growth from 6->9 rungs (added .35/.42/.55) is picked up automatically -- generalized
  the a2a diversion from a hardcoded 2-name list to a pattern match (a2a_<track>_<adapter>, grouped by track),
  since new tracks keep arriving and a hardcoded list means rediscovering this gap every time. Per-track label
  now pulled from run_meta's "track" field rather than a hand-written string per track. Caught + fixed a real
  display bug while verifying: nl values were formatted to 1 decimal (nl/100:.1f), so 0.30/0.35 both showed as
  "0.3" and 0.42/0.40 both as "0.4" -- silently collapsed two distinct rows to identical-looking labels. Fixed
  to .2f. (2) chroma_transitions_pure's run_meta now carries an explicit human-authored "title" (CONTINUITY's
  correction: it's a bonus variant, not a Kim ask, humbler label) -- added a title_for() helper so main()
  prefers an explicit title over the truncated-purpose fallback wherever a run_meta provides one; landing
  confirmed showing the corrected title. (3) Waveform popup gained window-shading (CONTINUITY's "worth
  including if cheap" follow-up to spec §13): pages that already compute a transition/crossfade window
  (transitions r1/r2, longform) tag their play cells with data-wfstart/data-wfend; a capture-phase click
  listener in the shared WAVEFORM_JS tracks the most recently played clip's window (cleared on any other
  clip's play, so it doesn't linger stale) and the popup shades that region on the waveform canvas -- turns
  "scrub to find the transition" into "look at the shaded band." Verified via the node harness: click
  delegation captures the window data, shading paint call runs without throwing alongside the existing
  bar/waveform-render assertions. All new/changed pages leak-scanned clean.
- [2026-07-07 18:20] (GHOST-NOTE) chroma_morph_barsnap page shipped (79 clips, bar-snapped windows w508/w512/
  w1032) — the batch Kim's first "completely useable transition" verdict (kaikki2angelic w1025 nl42 chroma)
  came from. Same nl-based schema as chroma_morph_transitions so the existing write_chroma_morph_folder
  handled it via routing with zero new writer code. This dir surfaced two real bugs while building it: (1)
  its own run_meta.json self-marks OBSOLETE/superseded-by-transitions3 with real findings, but findings_status_for()
  only ever read the separate run_purposes.json registry — a dir's own self-describing sidecar couldn't
  carry its own verdict. Fixed: now checks the dir's own staged run_meta.json FIRST (self-describing-sidecar
  convention), falls back to run_purposes.json only if the dir doesn't have its own findings/status. Also
  handles findings-as-a-list (this run_meta accumulated dated observations as an array, not a string) by
  joining. (2) The status-banner auto-link mechanism did a naive substring search — "mp" (registered as the
  multiprompt curated page's key) matched mid-word inside "ramp" and "tempo" in this dir's status text,
  producing garbage inline links. Fixed provenance_html() in eval_grid.py to require word-boundary matches.
  Verified the fix doesn't break the existing legitimate auto-link (newcaption_ab -> newcap8_promptstyle
  still links correctly). Also fixed a pair-ordering bug this mixed-batch data would have triggered: the
  declared-pairs-from-run_meta preference logic required ALL declared pairs present or fell back to pure
  alphabetical, silently DROPPING any undeclared pair not in that all-or-nothing check — this batch mixes an
  old kaikki-pair set with the newer phreaky/angelic/heron set, so it would have shown only 0 or all-4
  depending on which pairs were declared vs present. Fixed to preserve declared order for pairs that ARE
  present, appending any extra undeclared pairs after (alphabetical) rather than an all-or-nothing choice —
  applied to both chroma writer functions. All 4 actual pairs now render correctly. Leak-scanned clean.
  Handed to WINTERMUTE.
- 2026-07-07 ~18:20 (CONTINUITY): RECIPE3 TRANSITIONS SHIPPED (Kim's spec end-to-end): pure-original basis (no a2a on the tracks), full bungee follow-match (B locked to A's BPM), downbeat snap + ONSET-CONCURRENCE fine-align (xcorr, corrections up to ±801ms — handles fills/risers), chroma-morphed latent slerp with sine noising peak 0.4 at midpoint, + seam-inpaint addenda (128/256/512-frame strips on both crossfade seams). Trackset phreaky/angelic/heron (incl. the acid-rock experiment). 48 clips -> transitions3_{sweep,seam128_256,seam512}. Under-constraint attractor doctrine recorded (3rd sighting; avoid: depth<=0.4 + aligned superposition + real-content basis). Day's ear-validations: refine-hybrid 'completely useable' (kaikki2angelic w1025 nl42 chroma), sync layer 'generally good beatmatching' (plain clips).
- [2026-07-07 18:50] (GHOST-NOTE) transitions3 seam-sweep page shipped — Kim's newest recipe (pure-original
  basis, follow beatmatch, onset-concurrence fine-align up to +/-801ms, chroma slerp + sine noising peak 0.4,
  optional seam-inpaint addendum at 128/256/512 frames). 48 clips across 3 separate Mantu dirs
  (transitions3_sweep/seam128_256/seam512) merged into ONE staged folder (filenames unique across all 3, no
  collision risk) since they're logically one dataset. New write_transitions3_folder: per-pair sections, each
  a table with seam-size as colspan column groups (no-seam/128/256/512) reading left-to-right per CONTINUITY's
  ask, chroma/plain adjacent within each, rows = window (short/long per pair's own bar-snapped frame count).
  Caught + fixed a real routing collision while building this: write_chroma_morph_folder's regex (nl-based, no
  seam token) is a strict SUBSET of transitions3's (seam optional) -- it was matching just the no-seam 12-of-48
  clips and claiming the folder FIRST in the try-chain, silently dropping the other 36 seam-tagged clips into
  an incomplete page. Reordered transitions3's writer to try first (it's the more general regex), but that
  created the mirror-image bug: it would then wrongly claim chroma_morph_transitions/chroma_morph_barsnap
  themselves (regex still matches their seamless filenames). Fixed with a positive guard: transitions3's writer
  now checks the data actually HAS seam variety before claiming the folder, falling through to chroma_morph
  otherwise -- verified both directions post-fix (transitions3 gets its full 8-column layout, the two sibling
  nl-only dirs still render with the plain 3-column chroma_morph table, unaffected by the reorder). Wrote a
  proper distinguishing title/purpose for the merged page (the source dirs only carried identical generic
  boilerplate purpose text) and protected it from being clobbered on a future re-transcode. Leak-scanned clean,
  JS syntax-checked. Handed to WINTERMUTE.
- [2026-07-07 22:05] (impl-1, explorer work order) SA3 EXPLORER RENDER SERVER shipped: `eval/explorer_render_server.py`
  — FastAPI on :8056, medium-base resident, endpoints /info /status /audio /generate /a2a_track /a2a_mix /decode.
  All render semantics lifted (imported, not re-derived) from chroma_morph_transitions.py (sinesweep release-callback,
  seam-inpaint, pure-basis splice, bungee beatmatch, downbeat snap, fine-align, chroma-morph target) +
  a2a_fulltrack.py (sample_size budget, >378s two-window crossfade) + density_control_eval.py (FiLM install +
  ControlContext). DoRA registry (hof/newstack/evr1x) with reload-per-change; LatCH registry scanned at boot
  (14 medium heads @512 + chroma_other @2048); server-side gain normalization rho=mu=g0, weight=gain/g0.
  Import-tested under SAO/.venv; GUI side (mir explorer_sa3 Inference/A2A tabs) talks to it per the work order.
- 2026-07-07 ~19:20 (CONTINUITY): LATENT-EXPLORER MEGABUILD shipped (ultracode, 10 agents): mir/plots explorer_sa3 + Inference tab + A2A-mix tab (waveform overlay, free offsets/snap-to-grid, off-centre transition range, sine noise schedule, seam-inpaint, dual prompts, harmonic steering default ON) + shared LatCH/FiLM/DoRA steering panel, over a new model-resident render server (SAO/eval/explorer_render_server.py, FastAPI :8056). Verified headless 5-tab boot + GPU end-to-end. Adversarial verify found an off-by-0.5s B-side splice bug in the PROVEN chroma_morph_transitions pure-basis path (today's pure renders carry it; server reproduces faithfully, documented). mir commits 854bb7f+372b075 (sa3-latent-explorer), SAO e5da447+fixes.
- 2026-07-08 (explorer round 2, impl C): explorer_render_server — /generate + /a2a_mix now take cfg_interval (SIGMA semantics, min/max or [lo,hi]) + apg_scale into MODEL.generate (all a2a_mix sub-passes too); new GET /ckpts (recursive ckpt/safetensors journal of Mantu1/sa3_lora_runs, /tmp json cache, ?rescan=1) + GET /schedule (real build_schedule sigmas w/ model dist_shift, seq_len=ceil(dur*SR/DS)). cfg_interval rode **sampler_kwargs already on the non-latch path; the LatCH branch dropped it — passthrough added in stable-audio-3 model.py (706eae0, latch-sa3-phase1). SAO commit ebf2805 (sa3-style-adapter).
- 2026-07-08 (fixer subagent): explorer_render_server — closed the 5 GUI↔server contract breaks from the explorer verify round (POST /schedule w/ dist_shift float|null, /ckpts key entries→ckpts, top-level ckpt_path→dora resolve, apg_scale+cfg_interval+dist_shift consumed on /a2a_track, dist_shift on /generate). Live-verified via mir render_client + invalid-value probes + short renders; server on :8056 relaunched with fixed code, base model restored. SAO commit 194d70b.
- 2026-07-08 ~03:05 (CONTINUITY): EXPLORER ITERATION 2 shipped (workflow resumed post-quota, 7 agents): Viewer now TRACK-centric (2676 tracks, crop selector inside, empty-plots root cause = no default selections — fixed); Dataset gets ALL ~20 features via averaged-timeseries scalar precompute (lazy background + progress); Analysis matrix labeled as latent-CHANNEL correlation + computing spinner; Inference: dual prompt fields (base+variation), ckpt JOURNAL picker (recursive Mantu1 scan, 121 ckpts), cfg_interval+apg surfaced with tooltips, SIGMA-SCHEDULE CHART (real build_schedule curve, RangeSlider-driven CFG interval in sigma terms per Kynkaanniemi limited-interval guidance — native DiT gating at dit.py:479 confirmed); server: /ckpts + /schedule + cfg_interval/apg passthrough (model.py 706eae0). Verifier caught 5 real GUI<->server contract breaks (405s, key mismatches, ignored ckpt_path) — all fixed + live-verified (chart real, dropdown populated, dora rebuild logged). mir 8ac31e6+70dce76, SAO ebf2805.
- [2026-07-08 03:33] (wintermute) latent-dim x feature-ts xcorr over latents_sa3 DONE (999+200 crops, CPU): flux .84/flatness .76 strong; energy family .38-.54; beat/downbeat thin (.33/.18) — retro-explains guidance-dead activation heads; vocals ~0; no positional leakage (.05). Distributed encoding (max single-ch |r| ~.5, family clusters 157/113/212 energy, 54/184/252 spectral). Screen-before-training rule + expectation order for LUMI all-features array. Script Misc/latent_dim_feature_xcorr.py, matrix mir/stats/latent_dim_feature_xcorr.csv
- 2026-07-08 ~03:45 (CONTINUITY): EXPLORER FINALE — (1) WEIGHT GARDEN in the inference tab: shuffle (the proven databending op) on the resident DiT pre-adapter (amount/target/seed/decay), keyed rebuild, reset=render without it; (2) Kim's INFERENCE-TIME SELECTION STEERING implemented: new renoise_hook in the ping-pong sampler (sampling.py) -> server draws K renoise candidates per step, scores each with a LatCH head vs the SOURCE's onset envelope, keeps the best, active first 50% of steps — training-free gradient-free rhythm preservation, live-verified end-to-end (false-positive smoke caught first: old server process silently ignored the new keys; restarted on patched code, [mutate] log line + preserve render confirmed). GUI: two new sections in the inference tab (11 controls, headless-verified). Server running :8056 patched.
- [2026-07-08 03:43] (wintermute) a2a mid-nl melodic stereotypy (Kim's ear, nl .4-.55) MEASURED + explained: U-shape confirmed on a2a_kaikkialla ladder (flux floor -20% at .40-.55, overshoot +30-50% at .70 -> regime artifact = posterior-averaging band, NOT static model prior; CFG amplifies). Fix = chroma-morph guidance re-supplies destroyed melodic evidence; try low/interval CFG + churn. Tool mir/src/tools/melodic_movement_ladder.py, data mir/stats/melodic_movement_ladder.csv
- [2026-07-08 03:46] (wintermute) reverb/depth baselines DONE: goa rt60 p50 1.01 (34.7% at meter ceiling), depth p50/p95 60.6/65.6; avp ~2pts drier (58.7/63.3). Pad-fill v2 targets: depth>corpus-p95 flag, depth-percentile rerank; RT60 dry-side only. mir/stats/reverb_depth_baseline.csv
- [2026-07-08 03:50] (wintermute) research triage (Kim's Gemini report on infinite-horizon audio): SaFa latent-swap (ICCV25) + DITTO-2 x_T-opt = inference-only longform prototypes; exposure-bias drift signature == pad-fill hypothesis (depth meter = drift metric); self-forcing-lite = LUMI campaign candidate; skipped LMDM-KV/rolling-t (need arch changes). SimDPS on reading list
- [2026-07-08 05:44] (todo-sweep) D done — dora16_avp_familiarity_8ep (8/8, familiarity_beta 1.0) (05:44)
- [2026-07-08 09:56] (night-0708) layer-activation extraction done (150 crops x 3 sigmas) — GPU FREE, G: your aug-encode window (09:56)
- [2026-07-08 10:40] (continuity) layer×feature map DONE: rhythm features emerge at DiT L11–15 (downbeat R² 0.16→0.44, beat 0.40→0.80), spectral features are input-space (R²~0.9 at L0). Explains dead rhythm guidance heads + confirms TADA {12,13}. docs/layer-feature-map.md
- [2026-07-08 11:15] (GHOST-NOTE) avp aug-encode "gap" investigated and disproven before touching the GPU
  (CONTINUITY's ask, ~1035 aug crops supposedly missing from latents_avp) — checked directly rather than
  trusting the claim (same discipline as the earlier 28-track precedent): regenerated the manifest fresh
  ("Wrote 2393 crops from 142 tracks + 1035 augmentation variants") and cross-checked json sidecars in
  latents_avp directly (288 original + 2105 augmentation crops = 2393 total, spanning exactly 1035 distinct
  (parent_track, variant_name) combos). The "1035" was always describing distinct variants WITHIN the 2393
  total, not an additional 1035 crops on top — the corpus was already complete. Freed the contended GPU window
  back immediately instead of running a redundant multi-hour job; reported the correction to CONTINUITY + the
  fleet channel. avp_board eval page shipped instead (72 clips, CPU-only): ALL 4 avp DoRA arms (r16_plain/
  r16_familiarity/r128adj/r128adj_final) on one board — arm x epoch grid + a prompt selector (trig/trig2/
  trigdesc), same-playhead, per-cell readout showing both training params AND glitch-triage signal-quality
  metrics (flux-spike/clicks-per-s/silence/onset-density). Training params (rank/alpha/optimizer/lr) weren't
  available as a sidecar anywhere — extracted directly from each arm's own checkpoint (lora_config +
  optimizer_states[0].param_groups[0]) via a one-time torch.load, baked into the writer as constants rather
  than reloading checkpoints on every rebuild. This is the first page to genuinely answer WINTERMUTE's
  standing eval-tables spec §12 ask (training hyperparams in the provenance box) with REAL per-arm data
  instead of deferring it. Findings box picked up automatically from the dir's own run_meta.json (the
  self-describing-sidecar mechanism built for chroma_morph_barsnap) — this board already documents that all
  72 clips are clean at the signal level via the canonical generate() path; Kim's "glitchy" morning reports
  came from a different, unlogged path (the explorer render server), separately under investigation.
  Leak-scanned clean, JS-harness-verified (5-row table, 3-option prompt selector). Handed to WINTERMUTE.
- [2026-07-08 14:52] (continuity) a2a loop attractor documented (docs/a2a-loop-attractor.md): high-nl a2a loops generated regions for minutes (Kim's ear, ladder verdicts in run_meta). Breathing-noise hysteresis controller designed (source-calibrated recurrence threshold, latent-domain meter, renoise_hook tier-2). Task #35.
- [2026-07-08 17:56] (GHOST-NOTE) avp_board extended with the 5th arm (r16_originals / "D'", the aug-theory
  control run Kim asked about) — 96 clips now (was 72), grid + prompt selector unchanged, just gained a row.
  Found it by checking directly (mtime-sorted the render dirs) rather than asking Kim to clarify which
  "latest results" he meant — the 24 new r16_originals clips had landed directly inside avp_board/ itself
  (same naming convention as the other 4 arms), so this was the same page needing a re-render + arm addition,
  not a new page. Added r16_originals to AVP_BOARD_ARMS + AVP_BOARD_PARAMS (rank 16/alpha 16/dora-rows/lr 2e-4/
  Fusion, same as r16_plain, distinguished by corpus: originals-only, zero augmentations — the direct test of
  whether augs cause the tempo instability). run_meta.json's findings now carry the full arm-add note + the
  AUG-THEORY VERDICT (augs largely exonerated on tempo — it's optimization-phase-driven, not data-multimodality;
  r16 has a stability window ~1200-1500 steps regardless of aug presence). glitch_triage.json is stale for the
  new arm (only covers the original 72) — the new cells' click-readout gracefully shows no metrics rather than
  breaking. Verified JS-harness clean (6-row table incl. the new arm), leak-scanned clean. Handed to WINTERMUTE.
- [2026-07-08 23:50] (GHOST-NOTE) avp_board_seeds page shipped (168 clips) — Kim's prompting-issue probe:
  does the r16_originals adapter (trained on one-word captions) cooperate with base-model vocabulary at all,
  and is it seed-stable? New write_avp_seeds_folder, same board family as write_avp_board_folder (shares
  filename grammar: {arm}__epoch{E}_step{S}__{prompt}[__s{seed}]) but transposed per CONTINUITY's ask:
  ckpt-rows x prompt-columns with a SEED selector (avp_board has arm-rows x epoch-columns with a PROMPT
  selector — same shape, different axis swapped to the selector role). 7 prompts (trig/trig2/upbeat/kimlong/
  goa1/goa2/psy) in their run_meta-declared order, 3 seeds, 8 epochs. Prompt column headers show the short key
  with the full prompt text as a hover tooltip + in the click-readout (kimlong is Kim's full T3-style detailed
  prompt, several sentences — too long for a header). Reused AVP_BOARD_PARAMS for the training-params line in
  the readout since it's the same r16_originals arm as avp_board. Leak-scanned clean, JS-harness-verified
  (9-row table = 8 epochs + header, 3-option seed selector). This is a re-render — the original render (163
  clips) was lost to the crash/reboot's orphaned-mountpoint trap; CONTINUITY confirmed the drive is now
  correctly mounted as /run/media/kim/Mantu (not Mantu1 — that name never really existed, a stale mountpoint
  artifact from the pre-crash boot). Handed to WINTERMUTE.
- [2026-07-09 11:42] (WINTERMUTE) tempo_iqr meter on fresh ladders CONFIRMS LR-window hypothesis: arm G (r128@lr1e-4) flat tempo-stable across full 3000-step run (mean iqr 0.94, max 5.67, never collapses) vs r16@lr2e-4 narrow window (locked ~1152-1440, collapsed >1700). r16 fine ladder reproduces C's U-shape + ep31 notch independently; ep31-34 = narrow stable island (not single spike). Tool: mir/src/tools/tempo_iqr.py (clip-dir -> tempo_iqr; rank ckpts by ckpt_tempo_iqr_MEAN not median -- median floors at 0 on stable ladders). Feeds C's ship_checkpoint_picker.py.
- [2026-07-09 17:50] (WINTERMUTE) pending-D reanalyze COMPLETE: 1346/1346 avp aug variants have full CPU MIR features (src/tools/reanalyze_variants.py, subprocess-isolated after in-process pool hung twice -- madmom segfault then silent 3h hang; subprocess.run per-variant w/ 600s timeout + retry-passes = 0 quarantined). 255 bpm-canary flags = madmom metrical ambiguity (2x/1.5x clusters), not transform errors; data sound. Phase 2 (audiobox+essentia GPU features) deferred to card-free window.
- [2026-07-10 02:57] (wintermute) Kim's asks executed: (1) journals deployed to aavepyora.online/files/profiles/ (leak-scanned; renderer needs ##day/###entry — 8 invisible W entries fixed, C/G/F flagged for theirs). (2) All 4 repos pushed to the private remotes: mir sa3-latent-explorer (JSONL dataset-cache migration + reanalyze_variants/tempo_iqr/recurrence_meter tools + dataset-release spec), SAO sa3-style-adapter (lumi EFP bundle + journal/site), SAT main (2 waiting commits), SA3 latch-sa3-phase1 -> fork (9 commits incl familiarity_beta, warm_start, normalize-not-clamp). NB SA3 'origin'=Stability upstream, push target is 'fork'. (3) recurrence_meter.py LANDED in mir/src/tools (v3 whitened-patch, novelty_curve+calibrate_source) for C's #35.

## 2026-07-10 — FOR KIM (rights question, flagged by G, C concurs): public a2a-ladder pages serve audio DERIVED from a real commercial track (Hallucinogen - Angelic Particles re-rendered via a2a) on aavepyora.online. Not a leak-convention issue (track name is descriptive, not plumbing) — a COPYRIGHT/rights call that's yours alone. No emergency action taken: it's a standing state (you designed the public mirror + audition there), not a surprise; pages left up to preserve your audition workflow. Your call on whether public serving of commercial-derived a2a audio is OK or should be gated/pulled. Applies fleet-wide to ALL a2a_*_evr1x + a2a_angelic_r64tiered ladder pages.
- [2026-07-10 03:33] (wintermute) LAYER MAP LANDED (Axis-1 causal localizer, layer_patch_map.py, 1728 patching cells on medium-base): acoustic attributes (onset/bass/brightness/noisiness) localize to LATE blocks 16-23 via self_attn+ff; cross_attn ~0.00 single-layer everywhere (contrast TADA's categorical 12/13 bottleneck); rhythm engages self_attn earlier (12-19) than timbre. Routing: DoRA rank -> late self_attn+ff as SOFT AdaLoRA prior. Meter lesson: p95-gated peak-pick replaces plain onset_detect for cross-prompt comparison (3x over-fire on drones). FINDINGS.md + run_meta + jsonl in sa3_control_runs/layer_map_2026-07-10. Follow-ups: layer-group + timestep-resolved patching (Axis-2 feed).
- [2026-07-10 14:16] (wintermute) HARDNESS LatCH HEAD trained + STEER-VERIFIED (Kim's task): new scalar_json target-source in the latch trainer (constant (1,T) from G's .TIMBRAL.json sidecars, pooled readout), 5398 crops, EMA recipe 20ep loss .49->.127. Guidance smoke at gain 512: baseline hardness 69.4 -> steered-down 60.2 (target 59) / steered-up 77.3 (target 73) — monotone, near-target, 17-pt spread = strong steer, energy-family gain regime confirmed for timbral scalars. Ckpt latch_sa3_hardness_best.pt in the medium dir (goa-trained = tier-2 policy, weights stay private). Same path now trivially retrains depth/booming heads. GPU FREE.
- [2026-07-10 15:20] (wintermute) NEGATIVE + STANDING LESSON (Kim's ear on the hardness steer smoke): gain-512 steered clips are perceptually BROKEN (buzzing; 'concrete slab' / 'dentist's drill') despite the target meter moving monotone+near-target — guidance moved the meter by destroying audio. Kim's directive, fleet-wide: EVERY steer/control eval runs the established quality metrics (Audiobox CE/PQ, zero-crossings) alongside the target meter; target-only readouts are invalid. Direction correct -> head plausibly fine at lower gain/rho-mu; re-bracket WITH quality gates before claims. Annotated in run_meta + journal + the live page. Also: same-playhead player wedge FIXED everywhere (ph not reset on 'ended' -> every next clip seeked to last 50ms; guard in all 16 generators/pages, G-harness-verified).
- [2026-07-11 12:12] (continuity) Essentia model zoo mirrored LOCALLY in full (Kim ask: 'their distribution is uncomfortable'): 30GB, 427 .pb (+onnx/json) at mir/models/essentia-zoo/ preserving upf.edu structure; audioset-vggish-3 trunk copied flat into mir/models/essentia/ -> the binary mood_happy/sad/... + emomusic valence/arousal heads are now runnable (they were headless before). Resume/update: re-run the wget -N mirror line in models/essentia-zoo-mirror.log.
- [2026-07-11 18:41] (ghost-note) MODEL MATRIX overnight render COMPLETE (Kim's priority, uncapped after 08:48): eval/model_matrix_gen.py, manifest-driven per W's build_model_matrix.py schema, consumed C's rarity_bracket_manifest.json v2 (19 models + 7 legacy nested goa-dora runs incl the HoF must-include x20b3ygb ep3, + base) x 12 prompts (rarity-band stratified + a new 2642-entry kimlong-style prompt pool sourced from Lehto/latents' music_flamingo_full captions, eval/kimlong_pool.json) x cfg{1,7,16} x DoRA-strength{0.6,1.0,1.5} -> 6912 manifest cells, zero errors, survived a mid-run bitrate restart (128k->192k AAC per Kim's directive) with zero loss via resumability. Feeds the live model_matrix.html board. Not covered: 36 control-adapter/LatCH-head models (different knobs, needs its own eval shape -- flagged, not silently dropped). Also built (Kim ask): /home/kim/Projects/latents_sa3/DATASET_STATS.md, a central stats index living at the dataset root (not a repo) -- consolidates the timbral triad (computed corpus-wide for the first time: crop-level hardness 66.4±3.8/depth 60.3±3.6/booming 34.6±3.1, n=5398), the feature-analysis docs, the reverb baseline, and confirmed W's 2026-07-08 feature-latent xcorr run WAS analyzed (docs/layer-feature-noise-invariance.md), just not indexed as one thing until now. CONTINUITY already added a mood/theme entry -- convention adopted fleet-wide same day.
- [2026-07-12 12:16] (ghost-note) Kim's matrix-wide FEEDBACK, verbatim (relayed via CONTINUITY, recorded in model_matrix's run_meta.json kim_feedback per manifest v2 since it spans many checkpoints, not one): "almost universally results got better or didn't get worse at WEIGHT 1.5" -- corroborates C's fixed-alpha damping hypothesis (high-rank runs damped to s~0.35, so inference strength 1.5 partially compensates, 1.5x0.35~0.53; predicts optimal strength should be LOWER on r16 arms, untested). Also: "some prompts changed little -- training is not spilling over everywhere" (disentanglement praise). Separately, C proposed an open-comment-field feature (per-checkpoint/clip/page, IP-keyed, Kim's-IP comments auto-merge into kim_feedback to clear the ❗) -- W owns server+collection endpoint, I own the manifest-merge side once it exists; not built yet, this WORKLOG entry is the interim durable record so the quote isn't lost in the meantime.
- [2026-07-14 13:40] (GHOST-NOTE) expanded-Essentia field set LANDED (mir 21649cd, Kim's ask via F, C's field list): whole_track_expanded.py adds 26 native-rate fields to .TIMESERIES.npz (MAEST-768d, effnet genre/mood/instr curves, DEAM+emoMusic V/A, attack family, stereo width/corr, bark/erb, chroma_linmap, chords, EBU, +misc DSP) with a field_rates meta dict - CONSUMERS: any field not at frame_rate needs field_rates[field]. --add-fields = incremental resumable merge (legacy fields untouched, verified bitwise). Gates: MAEST washout PASS 57.4% vs 48.6% raw-mel; OpenL3 DROPPED (below baseline); NNLS solver broken in our essentia build -> linear-mapping fields. avp sweep in flight, goa next; the 574 numbered Lehto npz (Chill/other genre corpora) out of scope, same command extends them.
- [2026-07-14 23:08] (GHOST-NOTE) longform caption sidecars (SAO 2131a36, Kim direct via C): lumi/goa_longform_sidecar.json 5400/5400 t3 (first_class 330 / own 2625 / cluster-borrowed 2445, provenance map alongside) + avp 93.4% via parent-propagation - the fp32/T4096 campaign's caption arm. KEY FACT for future caption work: music_flamingo_full lives IN Lehto/latents per-crop jsons, only on ~2.5 random-position crops of ~55% of tracks (kimlong_pool.json = its track-level extraction); 110/273 flamingo-budget tracks were never actually captioned -> MF fill pass scheduled 02:04 tonight (eval/mf_fill_pass.py, resumable, chains granite + sidecar rebuild). ALSO: comment widget now on onset_eval/disentangle (deep clip/ckpt/model Notes panel via shared Misc/comment_notes_block.py) + mp/traj (page-level via Misc/inject_comment_widget.py) per Kim's build-once-drop-everywhere (SAO 1cd30f6); staged for W's rsync.
- [2026-07-15 04:14] (GHOST-NOTE) expanded-Essentia sweep COMPLETE corpus-wide: avp 1516 + goa 4461 + organic-dance/Chill/ProgTrance-MelodicTechno/Prog-Psytechno 574 = 6551 .TIMESERIES.npz on the uniform 26-field set (field_rates meta contract; consumers use it for any non-100Hz field), zero unexplained failures. Every Lehto/timeseries npz + all avp co-located sidecars now carry MAEST embeddings, effnet genre/mood/instr curves, V/A, stereo width, chroma_linmap, EBU, attack family etc. Gate (b) width verdict pending (render pair behind MF fill). MF gotcha for the record: MusicFlamingoGGUF default context_size=2048 dies on full tracks ('failed to eval chunk 3') - pass 16384 (the avp_pipeline.yaml value); fixed in eval/mf_fill_pass.py 2ac5ac2.
- [2026-07-16 01:48] (continuity) LUMI: first successful training run (smoke_r256, 300 steps, loss 0.803, no NaN, 1x MI250X GCD). MIOpen blocker cleared = MIOPEN_DISABLE_CACHE=1 (kernel-cache .ukdb SQLite open fails on all LUMI filesystems; relocating doesn't help, disabling does) + bind /tmp. Fix in efp_smoke_r256 + efp_fp32_compare (8 arms). Details lumi/README.md Decisions + continuity.journal 2026-07-16.
- [2026-07-19 01:20] (continuity) CHROMA-STEER PAGE EXTENDED (Kim ask 2026-07-19): solo instruments + chord progressions between colours/keys + per-model tabs. Reused chroma_guided_generator (ChromaSchedule progressions) + the PROVEN model.generate(latch_configs target_raw) path. GPU-verified the engine (was STUB-THIS-PASS). 48-clip pilot: hpcp's MASTER-§5 'dead' label REFUTED for HARMONIC steering (piano/Am Δbass +0.34 monotonic); novel register-tessitura coupling (violin→mid +0.27, piano→bass +0.34); hpcp strong-but-can-backfire vs same_chroma gentle-uniform-weak. Full 3456-grid parked for Kim trim+greenlight. eval/chroma_steer_{targets,render}.py+_driver.sh, riffer-evals/chroma_steer.html data-driven, run Mantu/sa3_control_runs/chroma_steer_20260719.
- [2026-07-19 08:50] (continuity) LatCH weight-bracket QUALITY GATE (Kim ask, mask 0-100): per-head USABLE weight range established over GHOST-NOTE's latch_sa3_sweep (no re-render) via a hybrid disintegration gate — flatness/zcr whitening+ringing, onset&bpm beat-loss (rhythmic prompts only, so intro/outro drops don't false-trigger), Audiobox CE<4.0 corroborating only (CE misleads by genre). Result: most heads clean->8192 (matches G's no-ceiling control finding); harshness heads break — hardness usable<=128, rms_energy_air<=2048, spectral_flatness<=512 (ambient more fragile than goa). Complements G's direct-feature control map: control-authority (G) x aesthetic-usable-range (this) = the full per-head operating envelope. eval/latch_bracket_quality_gate.py + latch_bracket_quality.json. TODO: Essentia genre-conf gate; fold usable-range column into latch_sa3_matrix.html (coord w/ G).
- [2026-07-19 10:15] (continuity) RESIDUAL-PRESERVATION ultracode (research-Q#1) CORRECTS the 07-17/18 reverb diagnosis: latent deficit is REAL + loudness-independent (participation ratio real>base>DoRA 34>14.6>11) but BASE-MODEL-INTRINSIC not adapter-caused (base loses 57% of eff-rank pre-adapter, base hazier than DoRA); stereo is ≈real (no collapse — orthogonal to haze); 'conditional-mean' UNPROVEN (1 seed/prompt on disk, within-context variance never measured). All cheap moment losses (cov/var/flatness/sigma-head) refuted gameable. Surviving candidate = residual-restricted distribution-matching critic, but gated behind: Gate A (free SDE/noise-injection A/B) then Gate B (24-seed fan = does conditional-mean even exist). docs/ai-research/residual-preservation-2026-07-19.md. Anyone building an adapter residual loss: read the negative-space table first.
- [2026-07-19 21:08] (continuity) EMA-HELP VERDICT (Kim 'EMA-help good to go'): EMA retraining GENERALIZES beyond spectral_skewness — helped 3/4 measurable weak heads, ema40 (=2x-epochs-with-EMA) the consistent winner over ema20. spectral_kurtosis standout: ~2.7x more steering at gain 8192 (measured 26->71 toward target 798, the head MASTER-§5 called dead). onset_envelope: ema40 more controlled (shipped overshoots). rms_energy_body: small EMA gain. rms_energy_air: wash (the harsh head). hpcp: +0.014 mid (chroma pass). Vindicates Kim's 'train weak heads 2x longer' — raw 2x drifts (June), but WITH EMA damping 40ep>20ep, no drift penalty. Heads at Mantu/sa3_control_runs/latch_ema_retrain_20260719; renders+measure eval/ema_help_{eval,measure}.py. TODO: promote the ema40 heads to _best if Kim's ear agrees; re-render the latch matrix with them.
- [2026-07-20 02:32] (WINTERMUTE) fp32 campaign -- Kim PRELIMINARY listening verdict (relayed): fp32 arms > bf16 twins by ear -- better sound separation, less noisy high end, better in many ways, worse in very few (occasional less punch, likely source-faithfulness not a defect). Not comprehensively audited yet. bs1-vs-bs4 and T4096-vs-T2048 UNDECIDED, parked for G's native-training-length eval versions. Recorded to the 10 fp32cmp/bf16cmp run_meta kim_feedback (clears board red-mark). Arms: {avp,goa} x {t512_bs8, t4096_bs1, t4096_bs4_lr1e4, t4096_bs4_lr5e5}; bf16 twins only at t512.
- [2026-07-20 04:07] (continuity) NOTE-FOLLOWING EVAL SPEC (W's request, MIDI-conditioner v1 go/no-go): docs/superpowers/specs/2026-07-20-note-following-eval-design.md. Chroma-trap-safe GAP(A,B) differential (mode-collapse can't fake GAP>0); verdict on OFF-distribution rolls D0->D4 not in-dist; skeleton-vs-expression measurable; falsifiable PASS/COND/FAIL. GATE-#0 stem probe done: stems worse than full-mix for MuScriptor 10/10 (full 1305 vs bass 366/other 641) — confirms #41, backs W's full-mix pivot; instrument-label-collapse caveat flagged for the per-tier routing. Fixed W-blockers: Shipped items->continuity.profile.md, ckpt-leak stripped from chroma generator.
- [2026-07-21 ~04:15] (CONTINUITY) THREE-PROFILE LAYER RESULT (all CPU, one night): (1) ARC post-training shift (medium vs medium-base, eval/pt_layer_shift_profile.py) RISES with depth (peak L22; postprocess_conv .108 = biggest single rewrite) — Zach@Stability's decoder claim confirmed as a gradient on SA3; (2) style adapters FALL with depth — normalized DoRA delta (eval/dora_layer_delta_profile.py) + fullft-vs-base both tilt early/mid with the CONDITIONING PATHWAY dominating (timestep/global embeds rel .3–.8, 5–10x any DiT block), universal across r16/r64/r128/avp/goa/fullft; (3) DoRA-vs-ARC per-block corr −.52 ≈ complementary depth profiles = the quantified mechanism for why base-trained adapters transplant onto the PT model (task #55's rows live on the matrix). SAME NIGHT: #44 rerun (eval/ablate_adapter_layers2.py) — single tap L14 ≈ full onset adapter (corr .97/spread 7.1) and CLEAN under the disintegration screen where all-taps HF-blows-out; L12 alone inverts; earlylate-without-mid collapses. Layer-restricted adapters L8-15 + L13-15 now TRAINING locally (train.py --adapter-layers, ckpts stay 24-indexed). Native-cells-on-LUMI job built+submitted (W-split; local T>=2048 natives guarded off in model_matrix_gen.py after the display crash).
- 2026-07-22 (CONTINUITY): **Paper triage of Kim's batch → knowledge.md +4 rows.** SA2 longform (2404.10301, deep-read): pretrain-3m10s→finetune-4m45s costs ~18% extra with NO regression (prior art for #50/#54 long-context arms); 2m gens score WORSE than 4m45s (quality-at-length tracks the DATA distribution at that length — warning against reading short eval cells as model quality); structure emerges from context length, not semantic tokens. SA1 (2402.04825): kept as canonical timing-conditioning + stable-audio-metrics citation. StemGen (2312.08723): wrong paradigm but exports multi-source CFG (check whether sa3_control drops conditions independently per source) + MIRDD descriptor-KL eval idea. SAE-steering (2505.18186) was already deep-read 07-11 but had NO index row — added; NB Kim's 07-21 re-download of its PDF was mislabeled (contained 2607.17624; quarantined), papers/ root PDF is the real one. prospective-unchecked/ emptied.
- 2026-07-22 (CONTINUITY): **LUMI native/fullft cells: two render-invalidating bugs found+fixed.** (1) fullft `diffusion.model.` key-prefix bug in BOTH LUMI workers (bare "model." strip → 0% coverage; the cov assert killed all 10 fullft_cells tasks and every fullft row of native_cells — same family as the local model_matrix_gen bug). (2) `model.generate()` window bug: `duration` only sets seconds_total+trim; the latent window is `sample_size` (default 5292032 = 120.0s) — native worker never passed it, so ALL 103 "native" cells rendered at 2:00 regardless of d380/d190 filenames (Kim caught it). Workers fixed (sample_size=frames*4096 + z0-frame-count assert FAIL LOUD), native grid widened per Kim to cfg{1,7,16}×w{1.0,1.5,2.0} (fullft w1.0 only), sbatch walltime 4h→24h, honest NEXPECT math. Broken outputs quarantined locally (native_cells_BROKEN_120s_window) — scratch purge + resubmit commands handed to Kim.
- [2026-07-22 02:31] (WINTERMUTE) Eval-toolkit assessment (stable-audio-metrics + auraloss) landed as spec docs/superpowers/specs/2026-07-22-eval-quality-and-training-signal-design.md. Findings: (1) CLAP score fills the missing prompt-ADHERENCE axis (clip_metrics.db had none); prototype eval/clap_score.py validates it as a GENRE-DEGENERATION DETECTOR per Kim, not a fine ranker -- 300 model_matrix clips: matched 0.263 vs far-control 0.005 (margin 0.257, 71% beat all far controls), but intra-genre near-synonym ranking weak (19% t1). Weakest-steering cells (cfg1/w0.6) cluster at the noise floor. (2) auraloss is ALREADY vendored (training/losses/auraloss.py, VAE recon loss) -- new value is stereo SumDiff-STFT + MR-STFT/SI-SDR as a cheap deterministic reference-fidelity score. (3) FD/KL realism deferred: OpenL3=TF/CUDA11.8 ROCm cost. Spec also covers train-time use: CLAP as a decode-per-iter degeneration MONITOR / early-stop signal (the RF-blind drift the EMA finding chases). Also fixed the model_matrix board column-misalignment (fixed-height header + always-render table; 0px drift verified). Commit a02c46e.
- [2026-07-22 05:07] (WINTERMUTE) CLAP degeneration scan: full model_matrix (31,639 cells, general 630k CLAP) done. Key result: the semantic genre-collapse rate INDEPENDENTLY REPRODUCES the fleet's quality ordering -- rank-16 adapters collapse out-of-genre ~40% (dora16_avp_originals 64ep ep7: 44.8% of cells CLAP<0.10) vs rank-128 ~3% (sa3-goa-dora-47s-r128). cfg1 = degeneration zone (0.20-0.25 vs cfg7-16 0.31-0.39); DoRA w2.0 degrades at every cfg. Overtraining (64ep) worst. So CLAP-degeneration = a quality proxy that agrees with CE/PQ+ear AND a per-cell flag. Also: checkpoint A/B settled by data -> general 630k beats music_audioset as a detector (steering-sep d=1.00 vs 0.59). Summary eval/clap_degen_summary.md, audition ladder eval/clap_degen_audition.csv for Kim's threshold. Commits a02c46e/3cc9e8a/c2e27e6. Reviewed+APPROVED C's model.py sample_size fix (alignment-safe) + disintegration_metrics.py.
- [2026-07-22 12:01] (WINTERMUTE) DoRA hyperparam x metric analysis (Kim request): joined the 31.6k-cell CLAP scan x clip_metrics.db x THE-FINN's checkpoint-recipe strings -> eval/clap_full_table.csv (rank/alpha/precision/frames/batch/lr/optimizer/dataset/aug/epoch cols + CLAP + CE/PQ/CU/PC + DSP), eval/clap_dora_aggregate.csv, eval/clap_hyperparam_analysis.md (full writeup). Headline findings (controlled where possible): (1) semantic-CLAP and DSP-buzz degeneration are INDEPENDENT (r~0.01-0.22) -> both screens needed, neither substitutes; (2) PQ~CU 0.96-collinear (one is redundant); (3) alpha<rank beats alpha=rank on adherence AND quality (unused lever); (4) fp32~=bf16 for output quality; (5) lr flat 1e-4<->2e-4, CLIFFS at 6e-4 (clean everything-sweep); (6) overtraining collapses un-aug (ep15) but aug10 climbs to ep74=corpus best; (7) 'bigger batch better' is a T1024 confound -- controlled at T4096 small batch is CLEANER; (8) ptm trades fidelity for genre-adherence (same adapter: CLAP 0.288 vs 0.271, CE 5.05 vs 5.80 -- relevant to #55). r16 loses on both axes; op box = cfg7-16 x DoRA-w0.6-1.0. Regenerate after LUMI fullft cells land. Commit cb28b11.
- 2026-07-22 (CONTINUITY, via subagent): **Muscriptor musicological study SHIPPED** — eval/musicology/ (REPORT-2026-07-22.md + motif_catalog.json + memorability.json + clusters.json + melodies.jsonl + re-runnable phase scripts). 2773/4545 transcriptions kept (integrity cutoff), latents_sa3 metadata joined. k=4 styles: full-on goa 60% (143bpm minor, rolling offbeat bass, phrygian b2), sparse/progressive 27%, downtempo/psydub 13%, +outlier. HEADLINE: rolling same-note 16th pedal in 91% of files; contour motif families octave-bounce 50% / semitone-trill 45% / whole-tone-rock 42% / minor-3rd-seesaw 41% / fifth-ping 33%. Memorability quantified: top hook-decile repeats its best motif 56x vs 0x (bottom), vocab compression 0.41 vs 0.98, chromaticism HIGHER in hooky files. 5 training recs incl. 259-id "hooky leads" curation subset, melody-contour LatCH head spec (rest/pedal/move-class @ 9.5Hz), and hook_melodic_ratio as THE metric for the missing-iconic-melodies failure. Method gotcha for reuse: MIDI grids need beat-period refinement (±4% kick-circular-concentration) — raw bpm_madmom drifts whole beats over 380s.
- 2026-07-22 (CONTINUITY, via subagent): **hook_melodic_ratio wired into render eval.** eval/musicology/hook_metric.py (pure-numpy core, imports in all 3 venvs; skyline lead + kick-refined grid + motif mining factored from phase1/phase3) + eval/hook_eval_renders.py (wav -> muscriptor transcription -> metrics JSONL; doubly resumable — transcriptions cached as .mid so metric re-scores are CPU-only). Validation: 20 corpus ids across all hookness deciles reproduce memorability.json EXACTLY (8/8 fields); mido/pretty_midi parsers interchangeable (6/6). GPU smoke correctly deferred (card owned by native refill/G's CE). Venv gotcha recorded: SAO/.venv is the ONLY venv with muscriptor+mido+librosa together. JSONL only — W wires page columns. Pilot: all cfg7 cells, command in the module report; melodic LatCH/FiLM design spec'd same day (docs/superpowers/specs/2026-07-22-melodic-latch-film.md, #53 riders).
- [2026-07-22 15:55] (WINTERMUTE) Pad-fill/mood analysis (Kim asks): built corpus_reference.py (goa/avp training baselines from Lehto+UUID timeseries), reverb_eval.py, mood_drift.py. HEADLINES: (1) STEREO NARROWING IS A MODEL ARTIFACT not the dataset -- both goa+avp corpora sit at stereo_corr ~0.73 (wide) but renders measure 0.87-0.88 (narrow); model collapses stereo regardless of data. (2) MOOD-DRIFT validated: correlates 0.58 with CLAP degeneration; drift pattern = LOSE melodic/energetic GAIN dark/soundscape/space = the pad-fill in mood-space; fp32 goa drifts LESS (cos 0.99 gains melodic) than bf16 (cos 0.96 loses melodic) -> supports Kim's fp32>bf16 ear where raw spectral metrics were weak (d~0.2). (3) goa mood ref=melodic/space/retro, avp=energetic/melodic/happy. Reverb axis running on matched set (baseline goa rt60 0.896). All in eval/, commits through corpus_reference.
- 2026-07-22 (CONTINUITY, via subagent): **SAME melody-encoding probe SHIPPED (spec §7 P3)** — synthetic MIDI battery (6 patterns x2 tempos + chromatic sweep, frame-locked at BPM 161.499 where 16th==1 SAME frame) x5 fluidsynth timbres, encoded + analyzed (eval/musicology/latent_melody_analysis/REPORT.md). VERDICTS: (a) melody is a DISTRIBUTED ~15-dim subspace, no pitch channels (best single-channel R² 0.48; full-width linear ridge R² 0.86-0.97) — LatCH melody head must be full-width linear, never per-channel; (b) pitch encoding essentially LINEAR (quadratic adds ≤0.09); (c) INTERLEAVING: boundary frames encode a linear SUPERPOSITION of the two 16ths in proportion to temporal overlap (slope ~0.91-1.06) — SAME does not snap; sub-frame timing is preserved but noisy per-frame; (d) a single deviant note (fifth-jump) is 100% LDA-decodable in all timbres, distributed over 33-82 channels, jump DIRECTION timbre-specific (cos 0.27) — multi-timbre head training MANDATORY; (e) pooled-timbre pitch decoders transfer at R² ~0.74, single-timbre at ~0 — shared pitch subspace exists but is minority. GRADIENT-SHARE ANSWER (Kim's "does training hear melody?"): melody subspace = ~8.5% of corpus latent variance (1.45x random baseline) → RF pressure on melody is real but ~1/12 of the budget — quantitative case for a melodic aux-loss channel and/or Head B conditioning. HAZARD for all latent probes: pitch-independent 0.4-1.3 Hz latent oscillation dominates raw ACF — high-pass before periodicity analysis.
- 2026-07-22 (CONTINUITY, via subagent): **SAME melody-encoding v2 SHIPPED — 11x scale-up + BPM-phase robustness addendum (Kim asks).** 900 renders (19 patterns [6 v1-verbatim + 13 new] x 4 tempos [two frame-locks 161.499/80.7495 + drifts 143/150] x 10 GM timbres + dual-tempo chromatic sweeps + pat1/pat5 x 20 BPMs x {numpy-sine,sawlead,piano}) → latents → eval/musicology/latent_melody_analysis_v2/{REPORT_v2.md,results_v2.json}. HEADLINES w/ CIs: interleave slope 0.924 [0.88,0.97] (140 cells — superposition verdict HELD); melody-subspace dim 15 (exact replica); corpus melody share 9.3% [9.0,9.6], enrichment 1.61x [1.56,1.68]; LOTO pitch transfer 0.679 [0.55,0.78] (v1's 0.74 was 5-timbre optimism; flute 0.25!). FLIPS: (1) "zero pitch channels ≥R²0.5" false for flute(15ch)/synthbrass/epiano — per-timbre statement now; (2) sweep-derived pitch atlas does NOT transfer to patterns across register (MAE 11-12.5 st, ordering 40-60%) — train melodic heads on PATTERNS not sweeps. NEW AXES: tempo-covariance = frame-absolute at frame level (traj cos 0.27; onset-half 0.38 vs sustain 0.03) but readout-covariant (subspace capture 76%, decoder transfers R²~0.79 across 2x tempo); gate readable at 2fr/16th (LDA 0.98) washes out at 1fr; REST = distinct near-silence region (LDA 0.995, closer to true silence 1.2σ than to notes 2.5σ) — rest is a class, not a threshold. ADDENDUM VERDICT (Kim's falsifiability bar): lone fifth-jump frame-detectable ≥91% at ALL 20 BPMs/3 timbres (event-level ~100%) — encoder is NOT the melody bottleneck at any phase; gentle decline toward slow tempos (corr −0.6..−0.74), frame-lock gives 6x cleaner stats (zdist 12.1 vs 1.9); v1's timbre-specific jump direction (cos 0.27) is GENUINE physics not soundfont artifact (sine stable across BPMs at 0.92, cross-timbre 0.40). Method traps logged: CV folds at drifting tempos must be phase-fair (LOBO), global-length zero-pad batching gives free true-silence codes + 1.1s/file encode.
- 2026-07-22 (CONTINUITY, via subagent): **Melody-turning via frame-level chroma steering: NEGATIVE (0/12 turns)** — eval/musicology/chroma_turning_2026-07-22/. Training-free LatCH chroma guidance (same_chroma head, proven g1536-2048 band, exact frame-locked one-hot pc targets from the synthetic battery) cannot flip pitch classes: target-adoption ≈ null everywhere, source-retention 0.7-0.8, ALL 26 gates clean — the head's authority is slow-harmonic-tint (~+0.03 cos), ~10x short of a pitch flip; not a disintegration ceiling. Head B's role SHARPENS: per-frame pitch requires the forward-conditioned path (Tier-2 d384 chroma adapter). Bonus: the adoption/retention/gate harness (chromaturn.py analyze) = Head B's ready acceptance instrument. Side-finding: SDEdit nl0.45 destroys muscriptor transcribability (attack wash, coverage 0-0.47) while chroma stays on source — transcription-based evals of a2a outputs need nl-awareness. Gain 4096-8192 extension queued as the last lever (extrapolation says still short).
- 2026-07-22 (CONTINUITY): **P2 cfg-axis verdict: mechanism-2 CONFIRMED dominant** — hook_melodic_ratio falls cfg7->cfg16 in 8/10 families while pedal occupancy rises (melody collapses droneward under guidance); no-lead 32-84% everywhere vs corpus ~5%. With v2's encoder exoneration + 9.3% gradient share + the 0/20 steering negative, the melody-gap causal chain is complete in ONE DAY: encoding fine -> training pressure weak (M1) -> CFG averaging kills commitment (M2) -> training-free steering can't compensate -> Head B forward-conditioning is the fix. Table: eval/musicology/hook_pilot_cfg_axis_2026-07-22.md.
- 2026-07-23 (CONTINUITY, via sonnet subagent — token-lean scripted pipeline): **GM-wide timbre-pitch atlas SHIPPED** (eval/musicology/gm_timbre_pitch/: pipeline.py --stages gen,render,encode,analyze; 480 renders x 120 pitched GM programs; one 2-min GPU window). FINDINGS: universal pitch readout exists but with a long weak tail (LOPO R² median 0.77, p10 0.36; pooled subspace 138/256 ch); GM family taxonomy does NOT match pitch-decoder geometry (within-family transfer ~ cross-family) — one 50-program "generic pitched tone" supercluster + ~10 outlier clusters (quasi-pitched percussion + formant/transient-heavy timbres); worst: Orchestra Hit (NEGATIVE transfer), the 112-119 block, Pad2/Whistle/Kalimba. HEADLINE: fifth-jump detection is near-ceiling for ALL 120 programs (0.81-1.00) and UNCORRELATED with pitch R² — melodic CHANGE is universally encoded even where absolute pitch decode fails => our relative/contour 11-class representation is the timbre-robust choice (independently validated). Head-B training set: sample by pitch-geometry cluster, not GM family; oversample the outlier clusters.
- 2026-07-23 (CONTINUITY, via sonnet subagent): **GM multi-font interval/hysteresis/mix probe SHIPPED** (eval/musicology/gm_multifont/: 641 renders = 40 GM programs x16 fonts + sine control; selection documented in selection.csv w/ 1-based mapping). (1) HYSTERESIS: SAME is TIME-LOCAL — sine control cos-dist 0.0009@1frame, 0.000 beyond (~250x below patch renders' 0.24) => ALL observed frame-context is acoustic release-tail, zero encoder-intrinsic memory; per-frame contour targets safe as specced. (2) PATCH-NUMBER CLUSTERING: real but weak (within 0.66 vs cross 0.57, p=.005; silhouettes NEGATIVE) — font character dominates GM label; sample FONTS not patch numbers for coverage. (3) INTERVALS: all 11-class moves decodable 0.79-0.89 pooled across 640 variants (octave weakest). (4) MIX SEPARABILITY (the big one): solo-trained decoders DIE on mixes (lead retention -0.17, bass 0.04); z(mix) vs z(lead)+z(bass) cos 0.88 = substantially NON-additive; drums crush lead decodability r2 0.52->0.11, and OFFBEAT HI-HATS perturb latents MORE than kicks (9.2 vs 6.7) => melody heads MUST train mix-native (melodies.jsonl already is — clean-stem training is now formally contraindicated), and goa's offbeat-hat idiom is an active adversary for latent melody probes.
- 2026-07-23 (via subagent for CONTINUITY): Head A CEILING measured (eval/musicology/head_a_ceiling/REPORT.md) — melody-contour readout from clean SAME z0 of full goa mixes, artist-disjoint split: best macro-F1 0.273 / bacc 0.280 (folded 8-label contour set; chance 0.125). LOW (<0.4): mix-native latent contour reading is weak → Head A should tap DiT activations (spec §1 L8–15), not raw z0. Noise curve graceful to t≈0.4, chance by t≥0.8. Spec-§3 acceptance FAILED at this quality: z0-vs-wav hmr r=0.083 (ρ=0.19, n=480). Alignment (shift diag) + capacity (2×1024 MLP) ruled out as explanations. Targets (2,649 files, MIDI-phase-exact, soft time-overlap) + checkpoints + acceptance machinery reusable in head_a_ceiling/.
- 2026-07-23 (CONTINUITY): **Head A ceilings, both routes measured.** Latent z0 (2649 files, artist-disjoint): macro-F1 0.273/bacc 0.280 (mlp ctx±2; chance .125); failure mode = lead PRESENCE (all→rest/pedal); t-curve graceful to 0.4; acceptance r=0.083 FAILED. Activation taps (500 crops, 12 layers x t{.2,.5,.8}): peak L12@t0.2 bacc 0.267 — mid-stack peaks as landscape predicts but NO lift over latent; GRU seq readout 0.215. Per-frame contour reading plateaus ~0.27 model-wide. OPEN SUSPECT before concluding representation-limited: TARGET NOISE (skyline/muscriptor-derived corpus targets; gate F1 .74-vs-ceiling) — synthetic-GT cross-eval dispatched (corpus-trained heads applied to the exact-ground-truth battery + mix stems). Artifacts: eval/musicology/head_a_ceiling{,_act}/ (act REPORT.md pending — agent hit session limit; chain finished unattended, 0 failed cells).
- 2026-07-23 (CONTINUITY): **Head A verdict consolidated** (head_a_ceiling_act/REPORT.md): per-frame contour reading caps ~0.27-0.28 on real mixes across latents + 12 DiT layers + 3 noise levels + GRU; mid-stack (L10-12) peaks as landscape predicts but no lift. Synth cross-eval shows the readout is DOMAIN-BOUND (sine=chance from a mix-trained head) — NOT proof of representation limits (in-domain synthetic probes hit .79-.89). Program calls: Head B unchanged as THE path; Head A z0-free-metric dead (r=.083); Head A rescoped to coarse presence/pedal targets, multi-domain training. In-domain-synthetic-mix disambiguation experiment deliberately NOT run — wouldn't change any decision (worth-the-tokens rule).
- 2026-07-23 (CONTINUITY): Kim listening verdicts recorded (training-findings.md): fp32+fullft superior, rank helps, 15-EPOCH NEW DEFAULT (good starts ep5-7), aug helps. Spawned: (1) G task — extract DoRA/LoRA r16/64/128 from the 10 fullft ep7 terminals, board evals + new dropdown (extractor to be built; -XS SVD bases = precedent); (2) aug10 campaign drafts via subagent — lumi/augment_goa_bungee.py (10-variant, goa-crop-aware), aug10_encode.sbatch (bungee+SAME-encode on LUMI; bungee-wheel port risk flagged), aug10_train.sbatch (8 arms: {goa,avp}-aug10 x {DoRA-r128, fullft} x {fp32, bf16}, T=512, 15ep). Also: prune_optimizer_states.py fail-loud root guard added (mistyped --root printed 'freed 0.00 TB' as if success — Kim hit it live).
- [2026-07-24 11:33] (continuity) xft SVD-extracted adapters (fullft->LoRA/DoRA r16/64/128) glitch = NOT a bug. Extractor correct (reconstruct W_eff cos 0.99 vs W_fullft from saved tensors). Root cause FUNDAMENTAL RANK: full-DiT fine-tune delta is high-rank in ATTENTION — r128 captures only 40% of cross_attn.to_out / 60% to_qkv / 68% to_out energy (vs 92-96% convs). Imbalance (fully-adapted convs feeding half-adapted attn) breaks residual balance -> glitch. DoRA can't fix (magnitude exact, direction still truncated: dora_relerr==lora_relerr==0.13). Kim's hypothesis (FT-extract beats trained DoRA at matched rank) = NO: trained low-rank DoRA finds a COHERENT solution, truncated full-FT delta is an INCOHERENT PARTIAL update. Distillation path closed at low rank; use fullft directly or TRAIN a DoRA. Diagnostic: eval/../scratchpad/diag_xft.py; extractor eval/extract_svd_adapters.py is fine.
- [2026-07-24 12:23] (continuity) xft distillation TAIL CONFIRMED (fullft_goa_t256 full SV spectrum, 229 modules): the fullft delta is NEAR-FULL-RANK. Median rank for 0.9 energy: mlp/proj 1110 (0.72xdim), attn_qkv 937 (0.61x), attn_out 747 (0.49x) — dim=1536. Whole-model uniform-rank energy: r128=26%, r512=65%, r1024=89.5%. No usable adapter rank exists (r1024=67% of full dim is not an adapter). MLP absorbed the most high-rank change = where domain knowledge lives. This is the quantitative why-Flux-but-not-here: a working Flux concept/style LoRA-extract has r90<<dim (low-rank shift); this fp32 domain fullft has r90~0.5-0.72xdim = exactly what a LoRA cannot hold, which is why fullft was needed. Distillation closed at any sane rank; use fullft directly or TRAIN a DoRA. Spectrum: scratchpad/spectrum_xft.py.
- [2026-07-24 21:34] (continuity) AdamW vs FusionOpt weight-space (matched r128 a128 dora-rows, T512 lr1e4, goa/avp x bs1/4): the two optimizers land NEARLY-ORTHOGONAL solutions -- direction cos 0.07-0.17 across all 4 configs -- and Fusion moves ~2x farther (adamw = 0.42-0.53x fusion magnitude). So FusionOpt is NOT 'AdamW better-conditioned toward the same place'; it finds a fundamentally different basin. cos 0.1 is ~140x above random => a small (~10%) shared direction = the robust style signal both agree on; the other ~90% is optimizer-idiosyncratic. Precision (adamw bf16 vs fusion fp32) can't explain it: bf16-vs-fp32 at matched OPT was cos ~0.45, not 0.1 -> this is an optimizer effect. Net: the OPTIMIZER is the single largest source of directional variance in the adaptation, bigger than bs/lr/seed. Which basin sounds better = audio/eval question (board). Scripts: scratchpad/adamw_vs_fusion.py.

## 2026-07-27 — WINTERMUTE: winning fp32 family fully metered on the eval board
Kim: "run stats on everything unmetered" + "metrics on the wav versions". Metered
59,190 LOSSLESS wav (Mantu/model_matrix, CPU DSP — no AAC artifacts in flatness/hf_ratio/
centroid) + CLAP prompt-adherence (18,289 new, sat-venv) + Audiobox ce/pq/cu/pc (18,440,
mir-venv) into clip_metrics.db. Winning family (8 arms: goa/avp × fp32/bf16 × a45/a128 ×
T512/T1024 × aug10) went from ZERO metrics → 2,867 fully-metered cells. Rebuilt
clap_dora_aggregate.csv + dora_table.html (committed 3af1b59).
Findings (DSP+CLAP+Audiobox, one axis — the ear still decides style-identity):
- all arms uncollapsed/healthy (crest 5–6.5, no drone/whitening/buzz)
- avp corpus > goa on ce/pq (~6.5 vs ~5.7)
- fp32 ≈ bf16 (fp32 a hair better on avp) → bf16 is a near-free compute saving
- a45 ≥ a128 (a45 clearly better on goa, wash on avp) → supports the a45<rank default
- T1024 ≈ T512 on quality but better prompt-adherence + dynamics
- aug10 best adherence (0.321) but most compressed
Two fixes: clip_metrics.py --base/--ext (meter wav) + coalesce join (67364c9, wav DSP
wins, m4a Audiobox preserved); Audiobox sorts by DB dur not re-decode m4a (a2aa317,
killed ~20min idle-GPU-under-lock). Live-server board still needs model_matrix audio
uploaded (G's ingest lane); Kim's local board is complete.
- [2026-07-29 21:00] (continuity) Head-B melody bracket verdict: FiLM melody_contour head STEERS at cfg16 ONLY (peak step9240 g1.5 conf +0.227 own-vs-wrong contour, adopt .464 vs .237, z0_cos .834), INERT at cfg1 (z0_cos .99), weak cfg7. Disintegration gates 4/4 clean on ALL 48 cells = real adoption not buzz. Pilot direction-check passes; soft controller, still improving at step9240. Confusion (own-vs-wrong) metric needed — null-floor inconclusive at high cfg. Also fixed render-loader order bug (add_lora before install_adapters, dora load after). bracket_summary.tsv + findings.json on UUID drive.
- [2026-07-30 02:15] (continuity) LUMI 8-GPU Lightning DDP CONFIRMED WORKING (smoke 20422454: all 8 ranks Initializing distributed MEMBER k/8, one group). Two root causes fixed from the failed smokes: (1) srun --gpus-per-task=1 cgroup-isolates each rank to 1 GPU -> Lightning devices=auto silently degrades to N duplicate single-GPU trainers (20413874 burned a node 3h, ~400GB dup ckpts; tell = epoch=...-vN versioned ckpts) -> use --gpus-per-node=8; (2) train_lora.py hardcoded devices/strategy=auto -> patched: --devices N + strategy=ddp_find_unused_parameters_true when N>1 (upstream SAT train.py:239 convention). Also: outer sbatch vars used in nested bash -c must be EXPORTED (EPOCHS_ARM silently vanished -> uncapped epochs). All three in lumi-ops skill. Unlocks single-model 8-GCD training (fullft, big-corpus runs).
- [2026-07-30 10:20] (continuity) goa-archive CAPTION stack landed on LUMI w/ FLASH-ATTENTION 2 (Kim's call, validated): MF via MAINLINE transformers (AudioFlamingo3ForConditionalGeneration — no fork needed) on the official lumi-multitorch-full image (flash-attn 2.8.4 prebuilt gfx90a) + venv overlay. FA2 engaged (fa2=True all ranks), killed the long-track OOMs (eager/sdpa-math materialized a 23.66GiB attn matrix at 600s; official MF docs: FA2 is THE documented path, model caps audio at 10min by design). Full 23k-track caption run submitted (8 GCD shards, resumable, sha1(rel)-keyed jsons matching the local features index). Sep pipeline validated earlier (~30s/track, m4a stems). Gotchas all in lumi-ops skill (AIF image /opt/venv PYTHONPATH shadowing, laifs/ vs easybuild paths, is_flash_attn_2_available false on login node).
- [2026-07-30 10:36] (wintermute) SECURITY (mirror hardening): dialogue redact() CORPUS_MASKS now catches k/M/thousand/million scale-abbreviation counts (prior regex only masked bare 4+ digit runs) and extends the count-noun from just 'tracks' to the countable-corpus family (captions/clips/files/jsons/stems/crops/samples/songs). Caught a live abbreviated-count leak on dialogue.html (F flagged). Small legit counts + job ids preserved (unit-tested). Re-pushed clean. ~/bin/mirror_dialogue.py (not git-tracked).
- [2026-07-30 11:00] (wintermute) paper-verdicts page deployed + threaded into the site nav strip (Kim-direct via C): 'papers' item in build_site.masthead() (covers profiles/journals/dialogue/blog) + the 3 hand-authored top pages. TWO redaction findings closed: (1) the page named the corpus in a DC-SAE relevance line -> render-time scrub+leak-gate added to build_paper_verdicts.py; (2) SECURITY: the profile/journal render path (build_site.py) had NO redaction unlike the dialogue/blog mirrors -> drive labels + a /home path were live on the PUBLIC profile pages; added redact() mirroring the dialogue mask set, regenerated + redeployed all profiles leak-clean. Generic methodology preserved. Commit d4a3afc.
- [2026-07-30 11:35] (continuity) Gram-Schmidt steering A/B (task #58): CONFIRMED strong-form — orthogonalized dual injection (dark + onset⊥dark) gate-clean steers both axes where naive addition disintegrates; the onset direction's buzz component lives in the shared subspace (GS strips 5% norm, 100% of the poison). CORRECTION: Ph3 07-11 'onset_density +2 steers onsets' was a pre-gate buzz mis-score (0.17 onsets/s, flat 0.64 on the original render). concept_steering/orthogonal_ab/ + commentary.json.
- [2026-07-30 11:53] (continuity) interval-CFG A/B (task #26, Kynkaanniemi in flow-t): NOTE-level melodic movement +19% at the nl.475 dip center under interval (0,0.7) (consistent both seeds), texture chroma_flux unchanged, nl.70 overshoot damped ~7%; upper/high-noise bound is the active ingredient; narrowed arms cheaper. 24 T1024 renders + metrics: sa3_control_runs/interval_cfg_ab/. W co-score + FAD pending.
- [2026-07-30 12:19] (continuity) Subspace-weighted RF loss landed (task #59, spectral-bias counter from today's deep-research triage): train_lora --subspace-loss-basis/-weight upweights the 15-dim melody subspace's RF-error share (K=1 off/byte-identical); GPU-smoked, term logs at exactly its 15/256 dimensional share; 3-arm K{2,5,12} small-g sbatch ready, lr-equiv 1e-4 arm doubles as K=1 baseline. Theory: tau ∝ 1/lambda (2503.03206) — melody at 9.3% variance is gradient-starved by construction; this is the lever.
- [2026-07-30 12:26] (continuity) Archive Stage-1 curation validated on the partial index: MAEST-cosine clustering separates true re-release duplicates (~25%, best-quality copy kept) from different-master variants (KEPT as augmentation per Kim's directive), flags overlap with the existing corpus by embedding alone (name-verified). mir/src/tools/goa_archive_curate.py, idempotent; final run after the MIR pass completes.
- [2026-07-30 19:57] (continuity) SVD spectrum sweep (10 fullft parents): rank-energy INVARIANT across corpora + context lengths (r16 4.5%/r64 14.8%/r128 25.7%, ±0.2pp) — fullft delta rank structure is training-regime-determined, not data-determined. Per-arm jsons in eval/; xft board numbers now measured-everywhere, no extrapolation.
- [2026-07-30 20:12] (continuity) fp32frames T-length trend synthesized (G metered, C synthesized): SHORT-render quality is training-length-INVARIANT (<=0.2 PQ spread, mechanically expected); long-form favors T4096 in 6/8 native cells but duration-confounded — matched-length native A/B (same render duration across models) is the missing decisive test, same one the longctx verdicts need. Anomaly: goa_t2048_bs1 dips PQ+CLAP both buckets. Tables in C journal.
- [2026-07-30 21:44] (continuity) RoPE-dominance loop diagnostic (task #60, F's UltraViCo/LoL lead): NULL — single-frequency attention dominance does not discriminate loopy vs non-loopy a2a on SA3 (0.419 vs 0.395; papers' model-level split was 0.796/0.316). Scope lesson: our loop attractor is STATE-dependent (nl>=.55 within one model), breaking the fixed-model-property framing — logit-downscale/jitter not the indicated fix class; regime story (posterior-averaging + CFG) stays live. Probe reusable: eval/rope_dominance_probe.py.
- [2026-07-31 07:18] (continuity) Reality-structured model experiments SPEC'D (Kim's physics-brainstorm commission → actionable plan): docs/superpowers/specs/2026-07-31-reality-structured-model-experiments.md — 3 gates (JLT ✅ passed-by-measurement: SAME eigenbasis 786x anisotropic, 188/256 dirs below the velocity noise floor; phase-recoverability next; symmetry-discovery), 4 tier-1 adapter-cost experiments (x0-target arm designed+awaiting-go, free-PHM algebra-drift, metrical-position FiLM retrofit, Fisher-Rao bridge), 3 toy-model tier-2 (tree-PE, quantized attention, hyperbolic latent). Collapse-test discipline standing on all. PDF triage filed: papers/deep-research/2026-07-31-physics-informed-dit-triage.md.
- [2026-07-31 08:35] (continuity) E1 pre-test (JLT mechanism check on deployed weights): v-trained base recovers sub-noise-floor eigendirections 2-8x WORSE per unit signal (worst at low sigma = under-investment not difficulty) — mechanism confirmed live. E1a built: --x0-equiv-loss (sigma^2-weighted v-loss == x0-MSE, zero inference changes), smoked, 2-arm small-g sbatch ready (solo + x subspace-K5 combo, shared lreq baseline). Spec sequencing: E1b (true x-hat head) only if E1a signals.
- [2026-07-31 13:24] (continuity) G3 symmetry probe (tier-0 finale): SAME+RF field has approximate SO(2) structure in near-degenerate eigenplanes (adjacent-eigvec rotations 1.8x more equivariant than matched random; full scrambling fatal) — low-grade complex-pair geometry supported, rich Clifford not; E2 drift metric anchored to measured planes. ALL reality-structured gates now resolved: G1 pass, G2 closed, G3 weak-positive, E1 pre-test strong, E4 downgraded. Tier-1 begins: E3 metrical-FiLM build next (60h window, Kim away).
- [2026-07-31 13:43] (continuity) E3 metrical-position conditioning LIVE: mode implemented (MetricalEncoder: 4 embedding tables subdiv/beat/bar/phrase + coverage channels through Head-B FiLM machinery; null-token input dropout per F's design; all-crops-kept), smoked 40/40, overnight local pair training — TRUE metrical streams vs PERMUTED-sidecar collapse baseline (matched marginals, zero info). Structure bracket (lag self-similarity + contour repetition + loop-attractor behavior) follows. 94.2% sidecar coverage from crop-local beat/downbeat activations.
- [2026-08-01 07:57] (continuity) OVERNIGHT: (1) G2b phase sweep (Kim's design) — SAME encodes carrier phase as literal 2-plane ROTATIONS (tone -> 439.9Hz oscillation at 2900x prominence, dim-2 circular trajectory; kick fundamental visible in real tracks); G2 reversed at sub-frame level, complex-pair branch reopens measured; eigenplane SO(2)s = phase planes (G3 mechanism found). (2) E3 metrical conditioning: collapse-test ordering CORRECT — phrase-return gain 10x over permuted baseline, 2.5x over base, par quality (small-n, saturated metric — ear + longer renders next). (3) Kim's Gemini topology report in triage; E1c hardened to floor-compensation-only.
- [2026-08-02 01:35] (ghost-note) goa_archive statistics + clustering verified (task #85, Kim direct): re-ran C's goa_archive_curate.py on the completed 23231-track MIR pass, output byte-identical to the existing clusters_summary.json (8061 unique/8383 dup-dropped/2220 master_variant/4557 dup-best, 4515 multi-clusters). Gap found + closed: statistical_analysis.py needs flat .INFO scalars, archive output is per-frame time-series npz — wrote mir/src/tools/goa_archive_stats_export.py (mean+std for 1D fields, entropy+norm for chroma, per-model VA, argmax-class+prob for effnet genre/mood/instrument, MAEST embedding excluded) as a documented first-cut aggregation, flagged to C before running at scale. Ran clean 23231/23231; stats output sanity-checks (60% Goa Trance genre, mostly melodic/energetic mood; instrument classifier collapses to "synthesizer" 98% of the time — poor fit for this genre, not a bug); correlation pass flags 12 expected-redundant pairs. Also found STATISTICAL_ANALYSIS_MANUAL.md is stale vs the real CLI (documents --pca/--vif/--cluster/--mi/--build-db etc that don't exist in the script) — flagging for a docs-truth pass. Output: goa_archive_features/{info/,stats.json} on the UUID drive.
- [2026-08-03 13:19] (wintermute) papers triage (Kim drop): CoFrGeNet 2601.21766 (IBM, continued-fraction FFN/attn replacements) read + filed LOW-RELEVANCE -- off-lane (we don't pretrain backbones; heads are signal-bound not capacity-bound). Keepers in arxiv-2601.21766 - CoFrGeNet — Continued Fraction Architectures for Language Generation.md: continuants closed-form gradient (1 division/ladder instead of d, ~9x) + dyadic depth-unfreezing as a rational-layer stabilizer. Also rescued the DC-SAE pdf (sole copy) from prospective-unchecked to papers/ root beside FINN's note; prospective-unchecked now EMPTY. knowledge.md row added (uncommitted -- rides with FINN's pending preamble).
- [2026-08-03 14:26] (continuity) SA3 fork audit (Kim ask, ultracode): EMA was UPSTREAM-gutted, NOT stripped by us — the training wrapper shipped use_ema + diffusion_ema hooks + defensive .ema_model reads, but the EMA build + ema_pytorch dep NEVER existed in repo history (pickaxe-confirmed); train_lora also hardcoded use_ema=False. So every run silently had no EMA. FIXED: self-contained SimpleEMA (no dep) + build + on_train_batch_end update + train_lora --use-ema/--ema-beta/--ema-warmup-steps (full-finetune ONLY; LoRA force-disables). Full-FT ckpt now carries BOTH online + EMA weights -> render/audition must load ema_model.* (render-path TODO). ALSO: generate() dropped upstream's output .clamp(-1,1) (moved to peak-normalize-at-save; any raw torchaudio.save on generate() output clips). Our whole diff vs upstream (origin/main) = clean refactor-replacements (~90 real source deletions; the '2250' is 96% regenerated uv.lock). Audit baseline for the future: git diff origin/main...HEAD. Whole-package adversarially-verified gutted-feature sweep running. Details in stable-audio-3/CLAUDE.md.
- [2026-08-03 14:52] (continuity) SA3 semantic-gutting sweep (ultracode #2): found cross_attn_cond_mask is UNCONDITIONALLY NULLED (dit.py:414, 'disabled due to FA kernel issue') -> ALL text-conditioned gens/evals ran with UNMASKED cross-attn (padded T5Gemma tokens dilute the prompt). Upstream FA-kernel workaround; may work on our CK-FA(RDNA4)/FA2(gfx90a) -> re-enable = candidate conditioning-quality WIN, test before/after (bake into the finetune). Also: use_effective_length_for_schedule reads True but is INERT (shipped LogSNRShift rate=0 zero-multiplies seq_len -> schedule length-invariant) = null-result trap for #50/#54 long-context. Both are 'wired-but-value-never-reaches-math', same class as rescale_cfg. Details in stable-audio-3/CLAUDE.md. Not-yet-swept: sampler solver internals, VAE chain, LatCH/sa3_control, training loss/schedule configs.
- [2026-08-04 00:40] (continuity) cross-attn-mask A/B RESOLVED (negative result, Stability-confirmed): re-enabling SA3's disabled T5Gemma cross-attn padding mask DISINTEGRATES output (spectral artifacts) — masking padding rebalances the softmax + over-amplifies real-token conditioning; the DiT was trained WITHOUT the mask (OOD). Zach@Stability confirmed: disabled for flash-attn (no mask support), never re-enabled, and 'the learned padding token for T5Gemma is kind of doing a similar thing' -> masking is OOD + REDUNDANT with the learned pad token. Do NOT enable at inference OR bake into training. Gated flag SA3_ENABLE_CROSS_ATTN_MASK stays off-by-default + documented; A/B tool eval/cross_attn_mask_ab.py. Net of the SA3 gutted-feature audit: 'v' training path FIXED (was NameError on the factory default; #65/#66 unblocked), EMA restored (full-FT), rescale_cfg=leave-as-no-op (Kim doesn't use it), cross-attn-mask=intentional-negative. Detail: stable-audio-3/CLAUDE.md.
- [2026-08-04 04:20] (wintermute) length-variant eval: LUMI leg SUBMITTED by Kim (length_variant_hq.sbatch, multitorch image per C's review, 220 tasks = 55 terminals x 4 passes across 8 GCDs). Local leg complete (3381 cells total incl. the 2646-cell native catch-up after e6aa20d). Next: artifact-count verify on drain -> ingest -> board rebuild + native/ptm checkboxes.
- [2026-08-04 04:36] (continuity) Melody-wall audio readout (#59 subspace-loss + E1a x0-equiv), autonomous: built eval/melody_wall_analysis.py (whitened-chroma recurrence — RAW chroma cosine SATURATES ~0.95 on tonal goa, whiten per-pitch-class first; reusable). Scored 2304 arm clips vs lreq_lr1e4 baseline, n=360/arm matched. RESULT weak/INCONCLUSIVE: subspace-loss nudges melodic recurrence UP (K2 +15% rel, K12 +10%, x0eq +5%) at comparable/cleaner texture (flatness/hf down, no disintegration) = the #59 predicted direction, BUT near-noise (per-cell ~coin-flip, non-monotonic K K2>K5<K12). Not a decisive win. Caveat: chroma is a harmonic proxy, not lead-isolated -> needs MuScriptor-MIDI contour metric + Kim's ears on subloss_k2-vs-baseline top cells to settle. VERDICT.md/summary.json on eval drive analysis/melody_wall/. Lesson: whitening required for chroma recurrence on tonal material (raw saturates).
- [2026-08-04] (ghost-note) Task #86 root cause found + today's instance fixed: TWO non-symlinked local staging trees both act as "the" model_matrix dir -- ~/evals_aac/model_matrix (matches the live server almost exactly, actually deployed) vs ~/.cache/evals_aac/model_matrix (only ~3.7k files, but hardcoded as STAGING in Misc/build_model_matrix.py:76 + eval/ingest_matrix_cells.py) -- so any script following its own STAGING constant writes correctly into the tree that ISN'T deployed. Same failure mode as WINTERMUTE's 2026-08-02 hotfix, but structural/recurring, not a one-off lapse. Recovered today's melody-wall ingest: merged manifest.jsonl (6318 entries, backup kept), copied clips to evals_aac, rebuilt via one-off monkeypatch (didn't edit build_model_matrix.py), pushed clips+manifest_live.jsonl+html, verified live via curl (200 not 404). Durable fix (repoint STAGING, or symlink the two dirs) flagged to WINTERMUTE since it's her pipeline -- not executed unilaterally.
- [2026-08-04 10:09] (wintermute) staging-split structural fix (G's #86 diagnosis, W executed): ~/.cache/evals_aac is now a SYMLINK to ~/evals_aac (backup kept .pre-symlink-20260804). Two-tree drift was the recurring board-sync gap root cause; also defangs cache-clear manifest wipes. Constants migrate to ~/evals_aac opportunistically.
- [2026-08-04 10:42] (continuity) FULL-FT MEMORY PROBE PASSED (#68): full-FT 1.45B DiT + fp32 + T2048 + bs4 + FusionOpt + EMA FITS on one MI250X GCD (64GB) — 20/20 steps, no HIP OOM, ~5.3s/step (fp32+T2048+checkpointing is heavy; ~1 day for 40ep on 8-GCD DDP). Kim's config stands, no trim. GOTCHA fixed en route: the vendored stable_audio_tools under lumi/vendor/ DRIFTS from the live SAT repo — first LUMI FusionOpt run hit a July-15 fusion_groups.py predating W's split_qkv -> TypeError 'unexpected kwarg split_qkv' at configure_optimizers. Melody-wall grids missed it (they used --optimizer adamw). FIX: refresh lumi/vendor/stable_audio_tools/training/{fusion_groups,fusion_opt}.py from stable-audio-tools + sync; ANY LUMI FusionOpt job needs the vendor refreshed alongside the fork. Remaining #68 gates: G's caption sidecar (captions+granite 23231 each done, hash-join 100% verified) + an 8-GCD DDP smoke.
- [2026-08-04 11:51] (wintermute) length-variant BOARDS live: dora_table 'native length' checkbox (overlay on graceful resolution, ·native/·20s label transparency, combines with post-trained) + model_matrix 'native' header toggle (effSrc swap incl. mid-play + reattach). Parallel native index also fixes a real clobber (native entries shared the 5-tuple key with 20s twins -- last manifest line silently won). Ingested 3387 local-leg clips into staging, rebuilt, deployed, curl-verified (manifest_live 4252 native entries, spot clip HTTP 200). LUMI leg still rendering; its ingest reuses the same path.
- [2026-08-04 12:27] (continuity) Precision thread: Gemini report in (Sub-Dominant Signal Precision Methods). Ranked #1 = Stochastic Rounding for weight updates (fix for LEARNING melody on bf16-master; torchastic); #2 = differential injection (real fp16-flash vs fp32-SDPA, melody-basis cosine); flags Qiu 2510.04212 flash-attn training failure (means 'forward fine → fp32-attn won't help' is INCOMPLETE — training-dynamics failure our 700x forward headroom doesn't cover). Set up: lumi/sbatch/precision_ladder.sbatch (fp32 vs bf16-mixed T256 A/B — the untested middle rung #52 skipped), eval/precision_injection_ab.py (subagent, running), delegated fp32/bf16-master melody re-score to G + CK flash-attn safe-softmax audit to F. Synthesis: papers/deep-research/2026-08-04-precision-report-findings-and-plan.md. SA3_DISABLE_FLASH_ATTN=1 already = fp32 attention (no new flag needed).
- [2026-08-04 12:57] (continuity) SHIPPED stochastic-rounding bf16 optimizer (desktop full-FT enabler): stable_audio_3/training/stochastic_rounding.py (stochastic_round_to_bf16 int-dither + AdamWSR bf16 master+states, fp32 update math, SR writeback) + --stochastic-rounding flag in train_lora (opt-in, default byte-identical, FusionOpt untouched). TDD: 131 tests, unbiasedness gate proven (|mean(200k)-w|/grid<0.01), accumulation demo (det bf16 drift=0/stalls vs SR drift≈M·δ), convex toy final MSE fp32 5.8e-6 / SR-bf16 5.2e-5 / det-bf16 4.3e-1 (SR 8153x better than det). KEY CAVEAT: SR fixes the round-away STALL but not the bf16 storage FLOOR (~4e-5 rel = (2^-8)^2) — fundamental to any bf16-master opt, fp32 has none. NOT for our LUMI runs (FusionOpt-SF already fp32 master); it's the 16GB-desktop path.
- [2026-08-04 14:11] (continuity) Run-audit reconciliation: reconstructed 45 run_meta.json sidecars (7 meta-less campaigns: fp32_frames/fp32_winning/fullft/adamw_bf16_sweep/longctx x2/smoke) from ckpt lora_config + train.log + dirname (mmap, no tensor load) -> 0 provenance gaps. Built eval/build_run_audit_board.py (REGENERATABLE) -> lumi_runs/RUN_AUDIT_BOARD.html + Artifact. Reconciles LUMI-scratch vs UUID(canonical) vs Mantu(redundant 7-run subset) vs render/audit state. 22 runs: 2 audited, 14 unaudited(❗), 0 no-provenance. LEFT-TO-AUDIT highest-value = the #59 melody-wall grids (subspace/x0/lr_equiv, renders analyzed in melody_wall, need Kim ears on subloss_k2 vs baseline). job-1..109 HQ campaign = needs LUMI probe. Mantu confirmed no unique content.
- [2026-08-04 15:46] (continuity) LUMI campaigns LIVE: precision_ladder (job 20682678, 3 arms fp32/bf16-mixed/fp16-mixed, T256/10ep full-FT/Fusion/EMA, 1 node/3GCD — picks big-FT precision) + #68 big-FT (job 20682758, fullft_bigset 8-GCD DDP, curated goa 12523-track keep-set via live-encode --data_dir + relpath-keyed caption sidecar, EMA). Big-FT chain verified end-to-end: goa_archive layout MATCH, filelist(rel)+sidecar(relpath key)+make_data_dir_caption_fn(reject-on-miss) all consistent. Watch caption hit-rate on first steps (first real use of relpath sidecar on live-encode path).
- [2026-08-04 17:54] (continuity) #68 big-FT pipeline VERIFIED — smoke passed (40/40 steps, 8-GCD DDP, live-encode 12523-track goa keep-set, captions attaching, fp32/T2048/bs4 fits, no OOM). Two multitorch-image gotchas fixed en route: (1) torchaudio 2.10+rocm7 has NO torchcodec -> torchaudio.load dies (backend= ignored, torchcodec mandatory); added ffmpeg-subprocess loader to dataset.py load_file (ffmpeg 6.1.1 present) + bounded the __getitem__ retry (was recursive -> RecursionError on systemic load/reject failure). (2) N independent 1-GCD arms in one SLURM job collide on Lightning's SLURM-derived DDP port (EADDRINUSE) -> set SLURM_JOB_NAME=bash (forces LightningEnvironment) + distinct MASTER_PORT per arm in precision_ladder.sbatch. precision ladder (fp32/bf16-mixed/fp16-mixed T256) all 3 arms now training. TODO: log both to lumi-ops SKILL + MASTER §5; commit dataset.py + sbatch fixes.
- [2026-08-04 22:05] (continuity) MP3-vs-FLAC latent sensitivity (eval/mp3_latent_sensitivity.py, 15 Goa full-mix FLAC->MP3@320/256/192/128k->SAME): SAME does NOT swamp MP3 (my 'swamped' claim WRONG — monotonic Δ, no invisibility floor) BUT the perturbation is diffuse, melody-NEUTRAL fidelity noise (melody-frac 0.07-0.10 vs 0.059 random). Δlatent vs single-note fifth-jump: 320k 0.22x, 256k 0.35x, 192k 0.49x, 128k 0.74x -> musically-relevant only at <=192k. VERDICT: FLAC re-source of 256k+ tracks low-value; the lever is a <=192k bitrate FLOOR, which the big-FT already enforces (encode_ok dropped all C/D; keep-set 100% A+B >=256k). Future FLAC pass justified only by missing hand-picked favourites, not existing-track quality. Validates the encode_ok curation. Outputs: Mantu/sa3_control_runs/analysis/mp3_latent_sensitivity_2026-08-04/.
- [2026-08-06] (continuity) CODEC CLARITY LADDER — m4a leg added (Kim ask). eval/hf_clarity_diagnosis.py now benchmarks the SAME round-trip against BOTH real MP3 (128/320) AND native-AAC .m4a (128/192/320 = our audition serving codec) on the SAME air-band env_corr axis, n=12 Goa full-mixes. Air 8-16k env_corr: **SAME 0.544** vs mp3_128 0.973 / m4a_128 0.956 / m4a_192 0.981 / mp3_320 0.997 / m4a_320 0.981. HEADLINE: **the m4a/AAC serving step is essentially transparent (0.96-0.98, on par with same-bitrate MP3); ~100% of audible HF-clarity loss is the SAME codec** — exonerates the download path, validates the whole clarity-recovery premise (#62/#65/#66). Caveat: ffmpeg native AAC (no libfdk) caps ~0.98 even at 320 (slight crest_ret bump 1.33) — encoder trait, doesn't move the verdict. Rolloff is power/bass-dominated (~265-273Hz all rows incl original) = a non-discriminator for HF, read env_corr only (corrected my earlier "buggy" read — it's just uninformative). NEW public audit page: eval/build_clarity_audit_page.py -> hf_clarity/index.html, three-audience (explainer + colour-graded ladder table + hold-the-moment/switch-codec same-playhead player, lossless-FLAC delivery so codec artifacts survive to the ear); redaction-scanned clean, player behaviour script-verified (seek 3s on SAME -> switch to mp3_320 -> position held). Handed to W to rsync -> /files/audit/codec-clarity/. kim_feedback still null (his ear pending). Outputs: Mantu/sa3_lora_runs/hf_clarity/.
- [2026-08-10 15:29] (wintermute) dora_table resolver: native-only checkpoints were unplayable (97/723 model-ckpt groups, 705 stranded clips) -- resolveCell searched only the 20s index, so the native-length overlay (which swaps an already-resolved hit) could never rescue them. Fixed 77dbb03: nativeIndex now grouped by (model,ckpt) with fallback own-20s -> own-native -> sibling-20s -> sibling-native; native-only hits tagged .native. Verified by executing the extracted groupByMC/mcGroup/resolveCell over the real 65061+4204-entry manifest: dead 0 (was 97), 0 cross-variant, all files present; offline snapshot carries nidx so the file:// path is covered too. model_matrix unaffected (per-ckpt native audition line, 344 present). Diagnosis: GHOST-NOTE. Generalisable: the default CLAP-desc sort surfaced the broken rows FIRST, so a 13%-broken board read as totally broken -- triage by what the default view shows, not by percent.
- [2026-08-11 00:47] (wintermute) Swept G+C's sbatch python-heredoc SyntaxError across all 54 lumi/sbatch scripts: 19 heredocs in 18 files, ALL CLEAN -- the reg-ab/wd-ab pair was the complete set, bug is bounded. Tool: lumi/check_sbatch_python.py (28693e0), pre-submit check, exit 0 = all embedded python parses. Note the false-positive trap baked into its docstring: the outer bash -c '...' splices shell values with the '"${VAR}"' idiom, so a verbatim read of the heredoc flags every CORRECT use -- my first pass reported both already-fixed files as broken. Also: 9 sbatch scripts untracked in git incl. fullft_wd_ab (C's fix single-copy in the shared tree). Earlier tonight: dora_table native-only resolver fix (97 dead rows -> 0); blog index restored (publisher rebuilt the index from only the CLI args, silently dropping 4 posts; push rc discarded; batched-rsync 0700 dir perms 404'd everything for ~4min -- all three fixed + verified); ~/bin site tooling (publish_blog, mirror_dialogue, mirror_agent_dialogue) moved into Misc/ with symlinks, deploy target externalized to ~/.config/aavepyora.conf, acb4a41.
- [2026-08-11 00:58] (wintermute) Single-copy sweep: committed C's 9 untracked lumi/sbatch scripts (087bbdb, with permission; fullft_wd_ab carried C's heredoc fix as a lone copy) + 6 untracked documents (3ee490d, papers/specs/design docs) per Kim's 'this goes for all documents'. Flagged not fixed: eval/incident_2026-08-09/ = 380MB/324 raw WAVs in the SAO tree (MASTER says eval output belongs on the eval drive, and it must never enter git); 3 in-flight .py tools + jsonl/midi untracked. Also executed Kim's fullft_bigset QUARANTINE: 59 broken clips off the live board + server (404-verified), 49 clean left up (per-clip, incl. the lone clean ep7 outlier), artifacts preserved in evals_aac/_QUARANTINE_fullft_bigset_latent_runaway/ with sidecar + root-cause README. Verified by RESOLVER not manifest count: 41211 requests, dead=0, serving-quarantined=0. DM pair logs now linked from AGENT_DIALOGUE.html + 'dm' in shared nav (8f98bc3).
- [2026-08-11 04:01] (wintermute) LUMI mis-pinning: blast radius bounded at SEVEN sbatch scripts using the backgrounded per-arm 'ROCR_VISIBLE_DEVICES=${GCD} srun --gpus=1 &' pattern (flac_bitrate_ab, fullft_avp_regsweep, fullft_avp_surgical, fullft_reg_ab, fullft_wd_ab, precision_ladder, precision_ladder_render); everything else already uses the proven single-srun/--ntasks/$SLURM_PROCID form. Diagnosis (G found, C+F+W independently confirmed): all arms land on ONE GCD. W's arithmetic: full-FT 1.4B bf16+AdamW+EMA needs ~26 GiB of state before any activation, so arms dying at 5-7 GiB allocated CANNOT be a standalone ceiling -- ~58 GiB was already held. C's tie-breaker is stronger: #68 ran a BIGGER config (T2048 fp32) alone on one 64GB GCD for 8h. NON-OBVIOUS CONSEQUENCE: collision does not corrupt training math, it destroys THROUGHPUT (N arms = ~Nx slower), so the real risk is TRUNCATED runs -- an arm meant to reach ep7 in its walltime reaches ep1 and reports what it got. fullft_wd_ab (20940322, 3 arms / 8h wall) is the wd-fix A/B deciding whether the drone fix works: a drone that only appears by ep5 is invisible to an arm that died at ep2 and would read as 'fix worked' = false negative on the most consequential open question. Check which epoch each arm actually reached BEFORE reading that A/B. Also earlier tonight: dora_table native-length toggle was near-dead (exact-twin lookup, 5.3% of cells -> nearest-native resolve, 45%); evals landing audited-marker fixed in BOTH directions (could never go green for staging-only/aggregate pages; then my first fix marked unrelated runs audited by prefix accident) and widened to recognise pre-kim_feedback verdicts in findings/status (11 more runs cleared, transitions3 among them); eval/ingest_kim_feedback.py files Kim's EVAL_NOTES.txt verdicts verbatim into run_meta (a section whose URL line had trailing text was SILENTLY ABSORBED into its neighbour -- parser fixed, mis-filing corrected, supersede-not-append added, 22 duplicate entries healed). Correction: my earlier 'kim_feedback NEVER fed, 29 manifests ZERO' was measured on the 28-manifest staging tree only -- the eval drive had 21 of 162 already.
- [2026-08-12 07:59] (wintermute) filelock: added 'hold PATH --handle H -- CMD' (8de2c26) after all four instances independently failed to hold locks they believed they held in one night (W: piped exit code swallowed by tail, so every guard of the session was decorative; G: no lock at all on build_evals; F: holder died without releasing, leaving a real 60s block; C: unguarded shared-doc edits all session). No damage in any case -- which is why all four survived. hold acquires, runs, releases in finally, refuses to run when blocked, propagates the command's rc. Tested 4 ways incl kill -9 leaving no stale lock. Root cause of W's was the rc-after-a-pipe trap ALREADY in MASTER §5, written up by W the day before. Reading sweep: 4/11 done (SW1PerS 1307.6188, disentanglement-eval 2602.10058, VeRA 2310.11454, and 2008.07669 which arrived MIS-TITLED as 'Persistence-based summaries' and is actually HiPPO -- the S4/Mamba ancestor; would have been dismissed as off-lane topology if the filename had been trusted).
- [2026-08-12 09:19] (wintermute) Reading sweep: W batch COMPLETE 11/11 (notes + knowledge.md rows). Cross-paper finding not in any single row: FOUR papers bottom out in one missing piece -- 2505.10004 needs a surrogate v(t), Yust-Popoff meter networks need an articulation set, 2405.04796 needs a discretisation (its graph nodes are distinct VALUES), and 2201.02715 ANSWERS it (HSMM over continuous emissions gives states+durations+boundaries in one model, made affordable by the low-rank inference trick). So: three methods blocked on one step, a fourth supplying it. Deriving the right discrete/scalar stream from our continuous 46-field timeseries gates all three analyses plus Kim's harmonic-rhythm idea; CPU-only, no training, spectral_flux_ts is already a novelty curve. Strongest control-target find: 2006.01033 dynamical score networks (tonal regions via graph modularity from mir's existing chords field -> tonal-region-id / centricity / harmonic-mobility timeseries; controls no current axis can express). THREE of 11 were nearly lost to METADATA not content: 2008.07669 mis-titled (actually HiPPO), 1708.09359 nearly skipped as redundant (supplies the witness complex that makes the others affordable), and the whole symbolic cluster dismissed by a wrong off-lane criterion until Kim corrected it.
- [2026-08-12 10:38] (wintermute) W second-wave four complete (Mukherji / Popoff K-Nets / Flieder / Mazzola) -- 15 papers total across both waves, all with notes + knowledge.md rows. Yield declined monotonically: real caveat (score networks give a GROUPING not a PARSE) -> convergence+warning (isography = harmonic analogue of contour; K-nets are SENSITIVE TO ARROW LABELLING, so check any relational descriptor against a second defensible labelling) -> thin hook (Flieder: synth parameter spaces = where a principled account of 'control dimension' would live) -> explicit NULL (Mazzola complex-time philosophy). Block exhausted for control purposes. HIGHEST-VALUE ITEM OF THE WHOLE SWEEP came from reading four papers TOGETHER, not from any one: 2505.10004 needs a surrogate v(t), meter networks need an articulation set, 2405.04796 needs a discretisation -- and 2201.02715 (HSMM over continuous emissions + low-rank tractability) supplies all three. Deriving that discrete/scalar stream from the 46-field timeseries is CPU-only, no training, and unlocks repetition-structure + metric-dissonance + harmonic-rhythm at once; it is UPSTREAM of C's planned melody/FX-residual repetition detector, not competing with it. Also downgraded my own strongest find (2006.01033) after C's Rohrmeier read: goa's harmonic tree is near-degenerate, so expect low-variance features for OUR corpus.
- [2026-08-12 13:53] (WINTERMUTE) articulation_stream validated over 14 tracks (mir 29d4f33) -- the CPU-only substrate that turns the 46-field whole-track timeseries into a scalar articulation stream, gating three reading-sweep methods (2505.10004 repetitions, meter-network articulation sets, 2405.04796 discretisation). Core result held under a sample I did not choose: 7 fields clear a SWEPT null on ~every track, margins +0.07..+0.17, best single stream spectral_flux_ts (medF1 0.546). Fused over the 7 survivors: medF1 0.558, margin +0.172, 14/14. Three corrections to the 08-11 one-track version: (1) rms_energy_{bass,mid,air} are AT their own null (+0.006..+0.013) -- dropping them lifted fused from +0.089 to +0.172, so "fused scores below its own best members" was DILUTION BY NULL INPUTS, not the timing-disagreement account I gave; (2) the per-field offset is NOT a field constant -- over 14 tracks only hpcp (IQR 0.000) and spectral_flux (IQR 0.02) are stable, the rest scatter across the whole +/-0.30 sweep, so the sweep is not a bakeable calibration, and offset stability does NOT predict signal (drums/bass = least stable offsets, strongest margins); (3) DEFAULT_FIELDS asked for "onsets_activations_ts", the PER-CROP TimeseriesDB spelling, against the whole-track npz which calls it onset_envelope_ts -- present in 0 of 14 files, reported missing on every run by the check built for exactly that, never read. Two stores, two vocabularies; check the npz field list rather than porting a name across.

GENERAL LESSON worth more than the numbers: beat_activation_ts scored medF1 0.800 / margin +0.399 on 14/14 -- double anything else, and it would have been the headline. It is CIRCULAR: that field is madmom's per-frame beat activation and the BEATS_GRID reference is madmom's DBN decoding OF THAT ACTIVATION. A shuffled-interval null controls for CHANCE, not for CIRCULARITY -- it asks whether peaks are placed non-accidentally, and they are. No null can detect that the reference is downstream of the predictor; that check is on whoever picks the reference. Kept as POSITIVE_CONTROL_FIELD (a harness that cannot recover madmom's beats from madmom's own activation is broken and fails silently by calling everything null), never as an input -- it would inherit the beat-grid dependency the grid-free formulation exists to avoid.

Division of labour agreed with CONTINUITY: WINTERMUTE owns the calibrated substrate (articulation_stream + cycle boundaries in mir); CONTINUITY builds downstream (SSM repetition/variety detector, per-stem negative-space descriptor). Contract for the next increment: cycle_boundaries(stream, rate) -> {boundaries: float[] sec, shapes: float[n_cycles, D]}, phase-invariant derivation, soft fallback (per-frame cycle phase [0,1) + cycle index) accepted as equally consumable. Phase-invariant is the default regardless of margins -- the strongest-margin fields are precisely the least calibratable ones.

Also this session: profile+journal pages rebuilt and transferred for all four constructs after C's build_site.py fix (single-level '## DATE' journal entries had been silently dropped since 08-04; C's journal recovered ~110 KB). 8 pages leak-scanned clean, all verified live byte-identical against local.
- [2026-08-12 14:01] (WINTERMUTE) cycle_boundaries(stream, rate) landed in mir (3de0048) -- grid-free cycle segmentation on the articulation stream, to CONTINUITY's contract: {boundaries sec, shapes [n_cycles,D], phase [0,1) per frame, index per frame, period, strength}. Period from the unbiased autocorrelation, phase from folding onto it and anchoring at the trough of the average cycle; reads NO beat grid. VALIDATED against a grid it never uses: the period lands on a WHOLE BAR on 14/14 tracks (1,2,3,4,6 bars in 4/4), median deviation 0.0115 bars vs 0.25 for an arbitrary period, Rayleigh R=0.9915 p=1.1e-6; cycle shapes cohere (per-bin/overall spread 0.788). So bar structure is recoverable from the MIR timeseries alone, without madmom -- which matters because the offset study showed the strongest-margin fields are the least calibratable against a grid. TWO METHOD LESSONS. (1) My first null here was WORTHLESS and read as a pass: ACF peak strength vs a PHASE-RANDOMISED surrogate, real 0.871 vs null 0.869. Phase randomisation preserves the power spectrum and the autocorrelation IS its inverse transform, so the surrogate has the same ACF BY CONSTRUCTION -- one quantity in two columns. Together with the beat_activation_ts circularity the same afternoon: A NULL CONTROLS FOR CHANCE, NOT FOR CIRCULARITY. Shuffling asks whether peaks are placed non-accidentally; nothing inside a harness can detect that the reference is downstream of the predictor, or that the surrogate preserves the statistic under test. That check lives in choosing the comparison -- ask what it would look like if the claim were FALSE, and if the answer is 'identical', there is no experiment. (2) TIDY IS NOT TRUE: argmax over the ACF can pick an arbitrary multiple of the period (a pure 2s sine reports 10.01s); the textbook fix (shortest near-maximal peak) repairs the sine and WRECKS real music (bar-lock R 0.9915 -> 0.5147, within-3% 12/14 -> 8/14) because the shortest strong peak is usually a sub-bar 3-beat grouping. Synthetic test and corpus disagreed; corpus won. Guards two smoke-test-found silent failures: flat input used to report a confident period with fabricated cycles, short/aperiodic input crashed on an empty array -- both now return one honest no-cycle result, so CHECK strength BEFORE TRUSTING A SEGMENTATION.
- [2026-08-12 20:09] (WINTERMUTE) MELODY-HEIGHT TARGET for the pitch/melody control head (deliverable 3): f0_other_ts + f0_bass_ts + per-voice voicing masks added to the whole-track store, 100 Hz, PredominantPitchMelodia + EqualLoudness on the SEPARATED stems (other 55-1760 Hz, bass 30-350 Hz). Corpus backfill running (mir commits 2917990 / e9cf1a7 / cdefcc5; --add-fields, CPU-only, ~33 tracks/min). WHY IT WAS MISSING: every pitch field we own is octave-folded pitch CLASS (hpcp, chroma_linmap, bass_chroma_linmap, chords) or scalar salience -- a rising line and its inversion are identical in all of them, so "make the lead go up" was unexpressible from anything we extract. TWO VOICES because a goa rolling bassline is a melodic voice in its own right (Kim); map to SA3's 3-band chroma at the CONDITIONING stage, not in extraction. Validated: steps<=2 semitones median 95.4% (min 94.5%) over 8 tracks, octave jumps max 0.15%; value-sanity over 220 sidecars gives bass median 42.5 MIDI vs lead 68.5 (~2 octaves apart) with 0.5% inverted, independently reproduced by THE-FINN at n=1608.

REJECTED ON MEASUREMENT (the tempting shortcut): whole_track_expanded.py ALREADY runs PitchYinFFT per frame and discards p0, keeping only derived inharmonicity -- so storing it looked free. It is not a melodic line: 28.4% of steps <=2 semitones, 10% octave jumps, because YIN is MONOPHONIC and a goa lead stem is not. Melodia gives 96.9% / 0.0% on the same input. Free is not the same as fit for purpose; one track separated them.

OPEN: the BASS OCTAVE. Melodia and YIN disagree by ~12 semitones on every bass stem tested; three tests failed to settle it (both frequencies carry real energy; the decisive odd-harmonic test -- 3*f_low must have energy if f_low is fundamental -- came back 3.7/3.5, 6.1/4.0, 2.8/1.1 vs 1.5*f0, inconclusive, plausibly because a filtered synth bass has weak upper harmonics and 10.8 Hz bins are coarse at 80 Hz). Melodia chosen on a criterion that does NOT need the octave resolved: contour STABILITY (YIN flips octaves WITHIN a track, up to 8.4% -- fatal for a control target; a consistent constant offset is not). Treat f0_bass_ts as possibly one octave high if absolute register matters. DAW-MIDI ground truth settles it.

*** CONSUMER RULES -- READ BEFORE SLICING ANY WHOLE-TRACK FIELD INTO CROPS *** (mir/src/tools/crop_timeseries_resample.py, commits 1726853 / 26eb7f7, with an old-vs-new demo beside it). sa3_encode_from_manifest.py::build_crop_timeseries applies ONE rate and ONE pooling rule to every field. That was correct when the store held only the 20 legacy 100 Hz envelopes; the store now holds continuous, categorical and sentinel-valued fields at FIVE rates, so the loop is wrong in three ways: (1) WRONG RATE -- the coarsest field (maest_embed_ts, 42 frames) covers 0.42 SECONDS under a 100 Hz assumption, so ANY crop starting after 0.42 s is dropped (1 of 38 test crops survived); loud in aggregate (~1 companion/track instead of N), so it would be noticed. (2) SENTINEL FIELDS MEAN-POOLED -- f0 uses 0.0 for unvoiced, so pooling averages real pitches with zeros: median error +0.00 st but p95 +15.86 st with 17.2% of frames wrong by >1 semitone, concentrated at note boundaries. SILENT. (3) CATEGORICAL FIELDS MEAN-POOLED -- chords_idx_ts indexes a 24-chord vocab; averaging C(3) and G(10) gives 6.5, a different chord. SILENT. Use build_crop_timeseries(arrays, meta, start, end, n_frames): per-field rate from field_rates, mean/masked-mean/mode per field semantics, pooled mask emitted as a per-frame loss weight, and strict=True RAISES naming field+rate+window instead of returning None. FOURTH thing it cannot fix: length != information content -- a 0.2 Hz field over a 47 s crop has ~9 real samples but is emitted at 4096 frames; check field_rates before believing a curve's resolution. NOTHING CURRENTLY IN TRAINING DATA IS AFFECTED (existing 5400 SA3 crop companions carry only the 21 legacy 100 Hz fields, verified by opening one) -- the bug triggers on the NEXT encode, which is exactly what the melody head needs.
- [2026-08-12 20:57] (WINTERMUTE) f0 MELODY TARGET LANDED AND VERIFIED (deliverable 3, pitch/melody head). Corpus backfill complete: 4457/4461 goa tracks carry f0_other_ts + f0_bass_ts + per-voice voicing masks at 100 Hz (4 legitimately stemless). TWO INDEPENDENT VERIFIERS AGREE ON EVERY AXIS -- WINTERMUTE's coverage/integrity/parity checker (mir/src/tools/verify_f0_coverage.py) and THE-FINN's five-leg before/after sweep, written from data facts only with no shared code: denominator 4461, stem split 3639 flac / 818 mp3 / 4 stemless (3-way name agreement incl. the pass's own quarantine list), MISSING 0, mp3 subset 818/818, INTEGRITY 0 losses (F: per-track before/after diff on 3863; W: 36-field universal membership on all 4461 -- complementary blind spots, W covers the ~594 processed before F's snapshot existed), PARITY other +0.017 / bass +0.029-0.030, both inside the agreed 0.05 effect-size threshold (NOT significance -- at n=4457 a KS test calls a musically meaningless 0.02 gap divergent). So mp3-separated and flac-separated stems track melody comparably and the head will not train on two populations dressed as one. Completion line 'Done: 4674 written, 0 skipped, 4 failed' was PREDICTED an hour in advance: the 4 are the named stemless tracks quarantined by the zero-progress guard, and 4674 > 4461 because --add-fields defines done as 'has every expected field', so a track that CANNOT have a field stays permanently pending and is re-attempted until quarantined. Design smell recorded: benign at 4 tracks, would have been the .flac-gap shape at 818. PART B STILL BLOCKS TRAINING: the SA3 crop encoder must adopt mir/src/tools/crop_timeseries_resample.py before f0 reaches training crops -- per-field rates, masked-mean for sentinel fields, mode for categorical, loud-fail instead of silent crop drops. Part A green does NOT mean the head can train.
- [2026-08-13 01:13] (WINTERMUTE) f0 MELODY TARGET IN PRODUCTION + four findings from the evening, three of them negative. PRODUCTION: goa crop companions 5392/5400 gained the 4 f0 fields (C, companion-only --fields whitelist, IN PLACE, latents md5-identical); the 8 skips reconcile EXACTLY to the 4 stemless tracks at 2 crops each (Baba G - Dig a Jig / Electric Universe - From the Heart / Lunar Asylum - Van halen / stanley shanti - placid) -- traced, not inferred, because '8 skipped' vs '4 stemless' is a factor-of-two between two counts that should describe the same thing. (1) *** maest_embed_ts's STORED RATE IS 2x TOO HIGH, CORPUS-WIDE. *** Hardcoded in whole_track_expanded.py as 16000/(313*256)=0.19968 Hz (assumed 5.008 s patch hop); patches actually land ~10.1 s apart. Measured over 300 sidecars: stored/true = 2.020 median (p5 1.998, p95 2.045), so the field covers ~49.5% of every track. Trusted, it maps the FIRST HALF of a track onto the whole of it; with a coverage-strict consumer, 150/150 last-window crops raised. Harmless for every EXISTING consumer because MAEST feeds rarity/retrieval/clip metrics, which are bag-of-embeddings and never time-index it -- it went live only when the crop encoder started slicing every field by time. FIXED DEFENSIVELY IN THE CONSUMER (mir f10d007): crop_timeseries_resample derives rate from n_frames/duration (verified reliable: legacy_frames/frame_rate / duration = 1.0000 at median, min AND max over 400 sidecars) and warns on >5% disagreement. THE PRODUCER IS STILL WRONG -- dormant only because the production whitelist emits f0 alone; anyone widening it inherits the bug. (2) NEGATIVE: melodia's own pitchConfidence (returned as output [1] and discarded by our extractor -- same already-computed-and-thrown-away pattern as the YIN f0) does NOT predict where its contour is unstable. AUC 0.518 on the lead (chance), 0.672 on bass, n=3. So there is no cheap proxy for a per-frame confidence; Kim's 32-draw ensemble is the only instrument. NOT adding the field: near-chance for the voice we care about, and storing it would invite the assumption just falsified. (3) LABEL-NOISE FLOOR EXISTS AND MY FIRST NUMBER WAS WRONG. Melodia is PERFECTLY deterministic under a null gain change (+0.01 dB: 0.0% flips, 7 tracks, both voices) but flips under added noise at -80 dBFS: contour>0.5st on 6.3% (lead) / 13.4% (bass) of frames, median over 7 tracks. My first report said 21.2% for the lead from ONE track and drew a conclusion from it that had to be withdrawn -- n=1 again. Head per-frame accuracy must be read against ~94%/~87% self-consistency, not 100%, and eval should gate on contour SHAPE. Caveat: -80 dBFS is an ABSOLUTE level so quiet passages are perturbed more; a calibrated ceiling wants noise relative to signal. (4) AUGMENTED-SET f0: SCALE, don't recompute (pitch: f0*2**(st/12) values only; tempo: time-axis remap by the EMPIRICAL length ratio). NOT because scaling is exact -- measured, it is not: 24-43% of frames disagree with a recompute and only ~10% of those are octave errors. The decisive argument is a-priori (THE-FINN's): bungee shifts the whole stem uniformly, so the true melody of pitch+2 IS the source melody +2 st by definition; any melodia deviation is a fact about the extractor, not the music. F's mutual-consistency numbers additionally imply the deviations are PARTLY SHARED across variants (measured 26.2% vs ~40% predicted for independent draws, simulated), i.e. systematic not pure noise -- which does not change the decision. Real axis: ground-truth-consistency vs extractor-consistency; for a head whose point is 'make it higher', ground truth wins.
- [2026-08-13 01:14] (WINTERMUTE) CORRECTION to my previous entry's label-noise figure (finding 3), superseded within the hour by Kim's 32-draw ensemble (THE-FINN ran it). I wrote 'read head accuracy against ~94% (lead) / ~87% (bass) self-consistency'. That came from a PAIRWISE measure -- clean run vs one noisy run -- which answers 'do two draws differ' rather than 'do the draws agree'. The consensus measure is the right one: over 32 draws (noise -80 dBFS + gain jitter), 99.4% (lead) / 97.1% (bass) of majority-voiced frames have ALL THIRTY-TWO within 0.5 st, median spread 0.00 st, and octave splits -- the failure mode we spent the evening fearing -- are 0.2-0.4%. THE PITCH VALUES ARE ESSENTIALLY DETERMINISTIC; the instability lives in the VOICING decision (2-3% of frames contested), not in the pitch. So f0 as a training target is in much better shape than my number implied. TWO CAVEATS ON THE REVISED NUMBER, because sample size is what burned every estimate in this thread: F's ensemble is 3 tracks and mine was 7, and TRACK VARIANCE dominates both -- per-track lead TIGHT runs 99.9% / 99.4% / 90.0%, bass octave-split 0.0% / 0.4% / 4.7%. On the one track both samples contain (Ayahuasca - Propella) the ensemble gives 90% TIGHT, the low end. So '97-99%' is the typical-track value from a small sample that happens to hold two very stable tracks, and my 93.7% is a 7-track pairwise value; the honest statement is that the ceiling is track-dependent between roughly 90% and 99.9% and neither sample pins the central value. WHAT DOES NOT DEPEND ON RESOLVING THAT, and is therefore what to act on: (a) do NOT build per-frame ensemble weights -- 32x corpus is ~190 h and buys little when the overwhelming majority of frames are unanimous; (b) there is NO free per-frame confidence -- melodia's own pitchConfidence fails on two independent tests (my AUC 0.518 on the lead, F's corr -0.007, and on bass it is INVERTED: contested frames score higher confidence); (c) weight the loss by the VOICING MASK, which is where the ambiguity actually is and which the resampler already emits as a per-frame weight; (d) if the head underperforms, suspect TRACKS not frames -- a few draws over a sample identifies unstable tracks cheaply, and down-weighting a handful of tracks is affordable where per-frame weighting is not. ALSO: F's second-verifier check PASSES on the real production crops (40 crops, 30 late-window incl. 759-1140s; f0_other region-align 0.9991-1.0000, f0_bass 0.9935-0.9997, chords integer, no drops). All 8 of its flags were the checker's own artifacts, verified: 4 name-match misses on punctuation, 4 from comparing a NATIVE-rate reference against a POOLED crop -- pooling dilates voicing, and pooling the reference the same way collapses the gaps from 0.082-0.089 to 0.007-0.009. PART B GREEN on production. Melody head unblocked.
- [2026-08-14 00:20] (CONTINUITY) D3 MELODY HEAD WIRED + GOA PILOT TRAINED. LatCHDataset gained an optional `voiced_field` (per-frame [0,1] loss weight from the crop resampler's pooled voiced-fraction companion, e.g. `f0_other_voiced_ts`) threaded through `collate_varlen` -> `train_latch.py`'s loss call as `mask.float() * weight` (zero changes to the masked_* loss functions themselves, since they already cast mask to pred.dtype -- a continuous mask just works as a soft weight). Default None leaves every existing head's training byte-identical; TDD, 5 new/updated dataset tests green (stable-audio-3 be9e20d, latch-sa3-phase1 branch). Trained BOTH goa-pilot voices on the production data (latents_sa3, 5392 crops, standard head config dim256/depth4/adaln_zero matching the other 14 production heads): f0_other (lead) loss 0.286->0.241 and f0_bass loss 0.194->0.178 over 3 epochs, both monotonic, saved into latch_weights_sa3_medium/ as latch_sa3_f0_{other,bass}_ep{1,2,3}.pt. THIS IS A PILOT, NOT A VERDICT -- 3 epochs is a proof-that-the-harness-works smoke, not a converged head, and per MASTER's disintegration-gate rule no "the head works" claim is warranted before guided-generation eval + Kim's ears. Also note: --standardize's mean/std are computed over RAW target values incl. the 0.0 Hz unvoiced sentinel (voicing only enters via the loss weight, not the standardization stats) -- a known wrinkle worth revisiting if the head underperforms near the unvoiced boundary. Next: more epochs + guided-gen eval + disintegration gate, then AVP iteration-2 (W's 170-source f0 extract + F's scale-transform, both already scoped/unblocked per the 08-13 dialogue thread, not run yet). Separately, ran a same-session local drone-divergence isolation ablation (Kim direct, away-from-keyboard ask): staged a 49-track goa subset (`lumi/stage_ablation50.py`) and single-variable-at-a-time full-FT arms (`lumi/local_drone_ablation.sh`) on the desktop card. Found + worked around a real env bug: `SAO/.venv` is missing `librocm-openblas.so.0` + `librocprofiler-sdk.so.1`, so any `--num_workers`>0 DataLoader crashes the instant it forks workers (use `--num_workers 0`; real fix is installing those ROCm packages, Kim's call). 3 arms trained clean at 200 steps (baseline/augment/wd+clip, no early instability at this short a screen); EMA and all 3 FusionOpt-based arms OOM on the 16GB local card before the first optimizer step (FusionOpt keeps its own fp32 master, ignores --stochastic-rounding) -- exactly the two axes most implicated in the drone fix can only be isolated on LUMI's 64GB GCDs, not locally. Kim is running the LUMI side himself tomorrow evening.
- [2026-08-14 02:10] (CONTINUITY) D3 melody head bracket (Kim asleep, "tokens tight, prefer training/bracketing over theory on Sonnet 5.0"): 7 short (5-epoch) arms on the goa production data, each into its own latch_weights_sa3_medium/bracket_f0_<voice>_<tag>/ dir (avoids the filename-collision bug below). LEAD (f0_other) loss @ep5: smooth_l1+adaln_zero(prod default) 0.2374, smooth_l1+film 0.2362(wobbled up from ep4's 0.2355), smooth_l1+concat 0.2330(lowest, monotonic, fewest params 3.35M vs adaln's 4.93M), temporal_shape+adaln 0.2722(different loss units, not directly comparable), mse+adaln 0.5564(quadratic scale). BASS (f0_bass) @ep5: smooth_l1+adaln 0.1719, smooth_l1+concat 0.1735. HONEST READ: concat wins on lead by ~2%, adaln wins on bass by ~1% -- BOTH inside noise range for a single-seed 5-epoch comparison, no clear universal winner yet. Real finding is negative-but-useful: t_injection choice does not obviously generalize across voices at this horizon, worth a longer/multi-seed pass before switching the production default away from adaln_zero. GOTCHA hit + fixed: train_latch.py's checkpoint filename (latch_sa3_<feature>_ep<N>.pt) does NOT include --run-name, only --save-dir -- two runs sharing a save-dir with the same feature silently overwrite each other's same-numbered epochs. Bit me once (a "40-epoch" run_in_background attempt got marked "killed" by the harness but kept training DETACHED/invisibly to ep39 while a second foreground retry on the same save-dir overwrote ep1-6 with a different random init -> a scientifically meaningless mixed-run checkpoint set, deleted). Lesson for the fleet: give every LatCH bracket arm its own --save-dir, always. Separately confirmed run_in_background is unreliable for ANY GPU python process on this box (not just the 1.4B DiT) -- sequential foreground calls (up to the 10min cap, ~100s/epoch measured here so ~5ep/call) is the only mode that's behaved predictably tonight. Next: AVP iteration-2 f0 extraction (W's scoped 170-source step, ~25min CPU, still unrun) while GPU work is between calls.
- [2026-08-14 02:55] (CONTINUITY) AVP ITERATION-2 (D3 melody head) LANDED, both steps, while Kim slept. STEP 1 (W's scoped plan): whole_track_timeseries.py --add-fields on the AVP root (170 source tracks, NO --recursive so the augmentations/<variant>/ subfolders are correctly skipped) -- 170/170 written, 0 skipped, 0 failed, ~5 min wall (much faster than W's 25min estimate, since only 4 fields were missing not the full 26). STEP 2 (F's scoped design, SCALE not recompute): new tool mir/src/tools/avp_f0_augment_transform.py (TDD, 4 tests) applies the settled transform to each source's 8 bungee variants without re-running melodia -- pitch variants scale values by 2**(st/12) on the unchanged frame grid (bungee pitch-shift preserves duration); tempo variants resample the time axis to the variant's own MEASURED frame count (never a nominal target_bpm pct) with values held constant. Verified numerically against real data before the full run: pitch+2 ratio 1.1234 vs expected 1.1225, tempo+10 value-preservation 1.0006 vs expected 1.0. Full run: 1322 written + 24 already-done (dry run) = 1346 total, matching the corpus's own variant count exactly, 0 failed. mir sa3-latent-explorer 08e90f0. AVP f0 data is now complete for both the melody head's iteration-2 and any future consumer. D3 status: goa pilot trained+bracketed (see 02:10 entry), AVP data ready -- next is wiring AVP into the same LatCH training path (multi-root --latent-dirs, once AVP is pre-encoded to SA3 latents with f0 crop companions -- that pre-encode is NOT done yet, only the whole-track f0 source is ready) and then the real eval/calibrate pass. Posted to chat.
- [2026-08-14 03:40] (CONTINUITY) KIM FEEDBACK on E1/E1a x0-equivalent-loss melody-wall arms (x0_eq_goa vs x0_eq_sub5_goa, LUMI renders pulled to lumi_runs/renders/matrix_cells; run dirs NOT yet pulled -- kim_feedback belongs in run_meta.json once they are, this is the interim durable record). VERBATIM: "x0_eq_sub5_goa. Weight 2 is fine at ep11, ep15 some 'spectralisation' can be heard, where a pad-like spectral timbre starts to dominate. ep19 is suddenly collapsed to spectral glitches. prompt following is ok, although still at ep19 many tracks sound like modern Goa more than 90s stuff, so plays like an DoRA, where especially the learned rhythmic grid and mixing punch of the base-medium are hard to overcome apparently. The direction of increasing W is: intensity goes down and the beat comes smoother and more damped or disappears completely, leaving intro/outro/break-like passages. Curiously the stereo image widens as the weight increases. Comparing plain x0_eq_goa: collapse happens already after ep11. Soundwise, plain Goa seems to have learned faster, often it has somewhat comparable sound to the subloss version when as an example ep11 is used, or ep7 with ep7 when subloss would be at 19 or 15. [...] For subloss, ep11 presents a gradient from W1 with beat to w2 where it has disappeared even if the track is composed like a 4/4 dance part. At ep7 it's more like 'some elements disappear'. Ep15 has a strong gradient but also slight spectral degradation at w2. for the plain goa, The gradient is between ep7-11." READ: sub5 (x0-equiv + K5 melody-subspace upweight) extends the stable-training window ~4-8 epochs past plain x0-equiv alone (collapse ep19/15 vs ep11) at the cost of slower convergence to a comparable sound (sub5 needs more epochs to sound like a given plain-arm epoch) -- consistent with K5 acting as a genuine regularizer specifically on the collapse-prone (melody-adjacent, sub-noise-floor) directions, the first EAR-CONFIRMED positive signal for the subspace-loss "mechanisms compose" hypothesis after the 08-04 DSP-only read was weak/inconclusive. Two separate findings noted: (1) weight-axis direction is intensity-down + beat-smooths-or-vanishes + stereo-widens for BOTH arms (a property of the adapter's learned delta, not the loss variant); (2) era/style ceiling -- still reads "modern Goa" not 90s even at ep19/high-w, base-medium's rhythmic grid + mixing punch resist override at DoRA-scale capacity, expected-shape limitation. NEXT: pull the x0eq/x0eq_sub5 run dirs from LUMI $SCRATCH (not just renders) and write this feedback into their run_meta.json kim_feedback field per the provenance-sidecar rule -- Kim or W, next LUMI session.
- [2026-08-15 09:51] (continuity) LUMI docs/skill updated (8ae595d) with tonight's failure-mode lessons: (1) CORRECTED a stale claim in both docs/writing-lumi-sbatches.md and .claude/skills/lumi-ops/SKILL.md -- multi-node DDP does NOT reliably extend the proven single-node Pattern 2 launch by adding --nodes=N; it silently forms N independent single-node groups (v_num split per node, no crash/hang) rather than one coordinated group, diagnosed after the multi-node smoke test looked like it was training. torchrun/c10d (CSC's documented pattern) is the identified fix, NOT yet built/verified -- treat multi-node as unsolved. (2) Documented the systematic EMA+full-FT batch-size OOM (bit two separate jobs, 21148122 + 21148584, before generalizing): EMA holds a fixed second full-precision model copy independent of batch/sequence size, so batch_size=2 + accumulate_grad_batches=N is the only proven-safe pattern, never a larger raw batch_size. fullft_avp_aug.sbatch + subloss_goa_k20_fullft.sbatch fixed accordingly (3262594). (3) Flagged preencode_bigset.sbatch's kernel OOM as UNRESOLVED after 3 fix attempts (worker-count/shm-strategy, then unbuffered-output/duration-cap) -- next session should add RSS-logging instrumentation before another blind resubmit, not assume the applied fixes solved it. (4) Added a checkpoint/DDP-group health-check recipe (rank-uniqueness grep, nan/inf false-positive trap -- 'inference'/'reinforce' both contain the substring 'inf') for answering Kim's periodic has-this-exploded checks on a still-running job. (5) uan18-vs-efp.lumi.csc.fi hostname confusion + sbatch wrong-cwd error, both bit Kim's terminal this session.
- [2026-08-15 10:10] (ghost-note) LUMI docs/skill updated (6b1239e) with two more findings from tonight's Suomisoundi corpus onboarding, folded in alongside C's failure-mode updates (8ae595d). (1) A second, SEPARATE quote trap beyond the --export= comma-truncation one: the standard 'export FOO='"${FOO:-}"'' splice idiom protects a value from sbatch's own parsing but NOT from the inner bash -c word-splitting it on whitespace when composing the container command -- a genre-hint value with spaces truncated to its first word even after the comma fix landed. Real fix demonstrated + verified locally before shipping: wrap the interpolated value in literal quotes in the composed output, or better, sidestep the whole quoting class by reading the value from a file (GENRE_HINT_FILE pattern in goa_caption.sbatch) since a plain file path is immune to both traps. (2) Reusing an output directory across two different extraction tools silently zeroes a resumable run: an ad-hoc converter script wrote into suomisoundi_timeseries/, then the real extractor's --output-dir pointed at the same path -- its skip-if-exists resumability check filtered all 1260 jobs out before any worker saw them, reporting "0 written, 0 skipped, 0 failed" (not even a nonzero skip count) despite "Found 1260 track folders" printing correctly. Looked like a broken tool; was actually working exactly as designed against stale data from an unrelated prior run. Fix: --overwrite (or a genuinely fresh directory) whenever two different tools/runs might share an output path.
- [2026-08-16] (wintermute) mir Audiobox scoring FIXED (G's find, root cause via ctypes.CDLL repro, Kim's direct decision to compile). System ffmpeg upgraded 8.1.2->9.0.1 (pacman, 2026-08-16) removed libavdevice.so.62/libavcodec.so.62/etc, breaking torchcodec's bundled core8 backend (torchaudio's load chain delegates to it) -- 0/162 CE scores, no partial results, hit on the very first clip of any family, not content-specific. G stopped the matrix_cells batch rather than burn GPU zeroing out CE. Investigated all three of G's options + Kim's own "just compile it" suggestion before deciding: (1) no ffmpeg8-compat package exists in official repos or AUR (both searched, empty); (2) torchcodec DOES support ffmpeg9 as of v0.16 (confirmed via web search, contra G's uncertainty) but that version requires torch>=2.11 -- mir has 2.9.1, so recompiling the LATEST torchcodec nightly against system ffmpeg9 hit a hard version wall (missing torch/csrc/stable/device.h, confirmed via the compatibility table: 0.16+ needs torch>=2.11), not a fixable build glitch; upgrading mir's pinned ROCm torch was ruled out as much bigger/riskier than this ask warranted; (3) blanket ffmpeg downgrade + IgnorePkg would hold the system-wide package back indefinitely (silent security-patch rot) just for this one venv -- rejected as the fallback of last resort. ACTUAL FIX (more surgical than any of the three original options): extracted the exact ffmpeg8 SONAMEs (avcodec/avdevice/avformat/avfilter/avutil/swscale/swresample + the matching libx265.so.216, cross-referencing pacman's cache for the right x265 vintage) from the still-cached ffmpeg-2:8.1.2-10 package into mir/lib/ffmpeg8-compat/ (gitignored, venv-private, zero system/root changes). mir/bin/python (was a symlink to the shared uv-managed interpreter) is now a small wrapper that prepends LD_LIBRARY_PATH and `exec -a`'s the real interpreter -- exec -a is required, a plain exec changes argv[0] and silently drops CPython's venv detection entirely (caught live: torch/numpy ModuleNotFoundError on the first wrapper draft, fixed). Also verified setting os.environ['LD_LIBRARY_PATH'] from inside an already-running python does NOT work here (glibc snapshots it at process start, not per-dlopen) -- confirms the fix has to be a launcher, not a rocm_env.py-style os.environ.setdefault(). Verified end-to-end through the REAL pipeline: control/sa3_control/clip_metrics_audiobox.py --pattern base__base scored 30/30 clips, real non-null CE/PQ values confirmed in clip_metrics.db. python3/python3.12 unaffected (relative symlinks to python, inherit the wrapper transparently). Transparent to every caller incl. score_and_publish.py's MIR_PY -- no other repo needs to change anything. Documented in mir/CLAUDE.md (Known Issues) + MASTER.md §5. dronesweep's 37%-blown-latents (separate issue, C's muon spectral-weight-decay fix in flight) unaffected by any of this.
- [2026-08-17] (continuity) preencode_bigset ROOT CAUSE FOUND after ~10 days as an "unresolved memory leak": it was never a leak. `pre_encode_dataset.py`'s `caption_metadata_fn` requires a matching `.txt` per audio file (`__reject__`s any file without one), but `goa_archive` ships zero `.txt` sidecars (verified: 0 .txt across 21,702 files in the local source corpus, Mantu/ai-music/Goa_Separated) -- captions for this corpus were always meant to be merged in a LATER local step (preencode_bigset.sbatch's own header already said so), not required at encode time. So every single file was getting rejected, `__getitem__` burned ~100 random retries (each one decoding a full-length track via ffmpeg before discarding it) before raising, and the RSS "leak" was glibc's allocator not returning freed large-PCM-buffer memory to the OS across hundreds of wasted decode-then-discard cycles -- a real high-water-mark effect, not a Python reference leak (consistent with the earlier `gc.get_objects()` scan finding nothing retained). Surfaced today via a NEW symptom: a 96-way fine-grained-shard workaround (restart-between-batches, built to route around the then-unknown leak) hit `>100 consecutive load/skip retries -- Aborting` almost immediately on every sub-shard, because a small shard's 100% rejection rate exhausts the retry budget fast instead of slowly. Root-caused via direct trace (not guessed): the file that failed had a successful `after-decode` RSS log line printed immediately before its own rejection message, ruling out a decode failure and pointing straight at the metadata-rejection path. FIX: new `--no_caption_check` flag on `pre_encode_dataset.py` (passes `custom_metadata_fn=None`, the library's own already-supported no-op path -- `if config.custom_metadata_fn is not None:` gates registration, so this isn't a new code path, just using an existing safe one). Wired into `preencode_bigset.sbatch`, `preencode_bigset_finegrained.sbatch`, and `preencode_bigset_smoke.sbatch`. NOT YET VERIFIED end-to-end on LUMI (job resubmitted with the fix, not confirmed writing real non-silence latents as of this entry) -- next session/resume should check `NLAT` count before treating this as closed.
- [2026-08-17] (continuity) CORRECTION to my own earlier tonight's entry: the "missing --devices caused job 21161065's 8-uncoordinated-trainers" diagnosis was wrong. Added --devices 8/--devices 4 to fullft_mixed_avp_goa_t4096.sbatch and the new dora256_mixed_2x4gpu.sbatch based on that belief; both crashed immediately on resubmit (MisconfigurationException: "You requested gpu: [0..N] But your machine only has: [0]" -- cgroup-isolated --gpus-per-task=1 means each process only ever sees ONE GPU, so an explicit --devices N>1 asks Lightning to grab N GPUs from inside a single process). fullft_avp_aug.sbatch (job #68, the actual proven DDP precedent) uses this exact --gpus-per-task=1 pattern with NO --devices flag and documents Lightning's SLURMEnvironment forming the DDP group correctly from SLURM_NTASKS alone -- so omitting --devices was already correct, not the bug. Reverted both scripts (commit 610a85d). The real cause of 21161065's checkpoint divergence (confirmed genuine via ckpt_dup_delta.py: 521/522 tensors differ, max_abs_diff ~0.25-0.27, not noise) is open again -- next suspect is something in the multi-source --encoded_dir mixing that fullft_mixed_avp_goa_t4096.sbatch uses and fullft_avp_aug.sbatch doesn't, not yet investigated. Lesson for next session: I verified the crash symptom matched train_lora.py's own --devices help text, but didn't verify that text was describing a FIX rather than just a more-visible SAME failure -- should have grepped for an actually-working --devices>1 precedent before writing the fix, not just found precedent for the FAILURE MODE description.
- [2026-08-17] (continuity) TWO long-standing blockers CLOSED AND VERIFIED, plus a third bug found and fixed. (1) **big-goa preencode COMPLETE: 12523/12523 latents** in ${SCRATCH}/latents_goa_bigset (job 21244499). Confirms yesterday's root cause beyond doubt -- RSS stayed FLAT at ~0.84-1.04GB the whole run (oscillating per decode, returning to baseline), vs 300+GB before. The ~10-day "memory leak" was never a leak: `caption_metadata_fn` __reject__s any file lacking a sibling .txt, goa_archive has ZERO .txt files (0/21702 verified in the local source corpus), so every file was rejected and each __getitem__ burned ~100 random retries -- each one a FULL-TRACK ffmpeg decode into a large PCM buffer, then discarded. glibc not returning those freed buffers to the OS was the RSS high-water-mark misread as a leak (and why gc.get_objects() found nothing retained). Fix was `--no_caption_check` (custom_metadata_fn=None, the library's own supported no-op path). CAVEAT: bigset latents have NO captions and synthetic shard-prefixed ids; see (3). (2) **DDP was silently never forming on ANY multi-GPU run using this repo's standard launch.** Job 21161065's checkpoint "duplicates" (-v1..-v4) were genuinely diverged models (ckpt_dup_delta.py: 521/522 tensors differ, max_abs_diff ~0.25-0.27, not fp noise) because all 8 ranks logged `LOCAL_RANK: 0` -- 8 uncoordinated single-GPU trainers, zero gradient sync. Two wrong fixes first: adding `--devices 8` CRASHES under cgroup-isolated `--gpus-per-task=1` (each process sees exactly 1 GPU); reverting to "proven" no---devices does NOT reliably form DDP either (fullft_avp_aug/#68 apparently just got lucky with Lightning's strategy="auto"). REAL fix, from Kim pointing at CSC's own reference scripts (~/Projects/llm-fine-tuning-examples): `srun --ntasks=1` (all GPUs visible, no cgroup isolation) + `torchrun --standalone --nproc-per-node=N`, which sets RANK/LOCAL_RANK/WORLD_SIZE itself (Lightning then auto-detects TorchElasticEnvironment) instead of relying on SLURMEnvironment guessing. REQUIRED companion fix in train_lora.py: `torch.cuda.set_device(int(os.environ["LOCAL_RANK"]))` before model load, else with all GPUs visible every rank loads onto physical GPU 0 (the "Pattern 1 OOM" fullft_avp_aug.sbatch already warned about); no-op when LOCAL_RANK is unset, so other scripts are unaffected. VERIFIED on job 21251551: LOCAL_RANK 0..7 distinct, ZERO -vN dup ckpts, and **244 steps/epoch vs the broken run's 1948 (= 1948/8, i.e. genuine 8-way data sharding)**, 8 epochs in 3h41m vs 1d8h. dora256_mixed_2x4gpu.sbatch migrated too (per arm: one `srun --overlap` task + explicit ROCR_VISIBLE_DEVICES 0-3/4-7 + torchrun with a PER-ARM rdzv port, since two rendezvous servers on one node collide). **Every other multi-GPU script in this repo is still on the disproven pattern and should be treated as unverified until migrated or checked via `grep -h LOCAL_RANK <log> | sort -u`.** (3) NEW GAP, not yet fixed: the bigset is not trainable as-is -- PreEncodedDataset sets info["latent_filename"] and make_caption_sampler's default key resolver tries that FIRST, so it keys on the synthetic shard-prefixed latent id, missing goa_longform_sidecar.json's track-stem keys; with --no_caption_check there is also no stored prompt to fall back to => would train on empty prompts. The per-latent .json does carry the original `path`, so the fix is a local sidecar re-keyed to the synthetic ids (no train_lora.py change needed) -- exactly the "captions are a LOCAL post-step" the preencode script's header anticipated.
- [2026-08-17] (wintermute) Rating page: TWO copies merged into ONE, and the "unreliable circle" bug root-caused as a buffering-lifecycle bug, not a gesture bug. (1) `eval/rate.html` (internal) and `eval/evaluator.html` (public /evaluator/) were ~450 near-identical lines differing only in which model pool they loaded — and the internal copy had already fallen a version behind, missing the previous night's gesture fixes. Kim: "upkeeping two almost similar versions make no sense." One implementation now; `?goa=1` (or `?all=1`) swaps the small pre-built avp manifest (68 models) for `manifest_live.jsonl` + the `scored_models.json` sanity gate (234 models, goa included). `/files/evals/rate.html` is a redirect stub; `source` still separates the audiences in the export (`internal_all` vs `public_evaluator`); `Misc/build_evals.py`'s highlight link now points at `/evaluator/?goa=1` and goes live on the next publish rebuild. (2) THE BUG, worth generalising: Kim reported "clicking on the circle is not reliable, it often stops responding, whereupon it needs to be scrubbed, and switching then works for a while again" — which read as a third round of the tap-vs-scrub threshold bug I had already fixed twice. It wasn't. Switching paused the audible `<audio>` element and seek+played the other, but the INACTIVE element sat paused the whole time, so the browser stopped buffering it while the audible track ran on; within seconds the switch target's playhead was in a region that element never downloaded, and `play()` stalled on an unbuffered seek — silence, indistinguishable from a dropped click. Scrubbing seeks BOTH elements, forcing that region to fetch, hence "works for a while again" until the playhead outruns the fresh window; worse the longer the clip, which is where he hit it. FIX: never pause the inactive track — both run continuously and the switch is a `muted` flip (`muted`, not `volume`: iOS ignores volume on media elements). No seek, no buffering gap, no promise to stall, and switching became instant as a side effect. Drift guard reseeks only past 0.25 s. Also dropped the time-based scrub trigger outright (movement-only, >14 px) rather than tuning it a third time — a stationary press has no other possible meaning, so a duration threshold could only ever misfire. TRANSFERABLE: a symptom that a specific unrelated action REPAIRS, and that then decays, is state, not input handling — and a bug report matching a fix you already made is the one to read most literally, not least. Verified live on the deployed page (68 avp models / zero non-avp leakage; ?goa=1 234 models; all four gesture cases; both pending-state messages; no console errors) — but NOT by ear: this automation browser cannot decode the AAC clips (a 488 KB file never reaches `loadedmetadata`), so the audio side is confirmed only through element state and is in Kim's ear queue. `5b6be4a`
- [2026-08-17] (wintermute) SELF-AUDIT of my work since the 08-13 token outage (Kim-directed). Three findings, two of them mine to fix. (1) **A stray `dora_table_TEST.html` (9.1 MB) had been publicly served since 08-13 22:44** — a working snapshot from the outage window, unreferenced by any page, not in git, and re-uploaded on every publish because leg_publish includes `*.html`. Leak-scanned clean, but it is the same class THE-FINN just closed for raw sources: an unreviewed artifact nobody knows is there. Removed from BOTH the server and the staging dir (staging, or it comes straight back). (2) **The redirect stub I scp'd to `/files/evals/rate.html` an hour earlier existed only on the SERVER** — the staging dir still held the old full 17 KB rate.html, so the next `score_and_publish` run would have silently overwritten the redirect and resurrected the page I had just retired, re-splitting the two versions the merge existed to unify. Fixed by copying the stub into staging; dry-run now shows a timestamp-only diff. GENERALISABLE, and it will bite anyone: **the publish leg's source of truth is `~/evals_aac`, so anything hand-scp'd to the server is reverted by the next publish unless the same file lands in staging.** A hand-deploy is not a deploy. (3) 44 records in `ratings_data/ratings.jsonl` still carry the salted `ip` hash the endpoint stored before I removed the field — ALL of them dated 08-14 22:01Z → 08-15 13:35Z, i.e. entirely before the public evaluator went live (08-15 19:10Z), so the public page's "no IP address or any other identifying data" claim is literally true and this is internal test data only. Flagged to Kim as tidiness (per F's severity rule, not filed as a breach); not stripped unilaterally. VERIFIED CLEAN, against real data rather than notes: dora_table's cfg7/w1 default scoring routes EVERY metric read through `mv()` (extents, hybrid normalisation, sort comparator, cell render — no path reads the raw column while 'all scores' is on); `is_op_point()` matches real manifest types (cfg/strength are floats, `7.0 == 7`, 12470/72964 entries classed op-point); deployed `ratings.php` is md5-identical to local with the correct 4-question whitelist and no stored ip; deployed `/evaluator/index.html` is md5-identical to the committed source; mir's venv wrapper still imports numpy/torch/torchaudio/torchcodec; `--rebuild` is a real flag on ingest_native_cells.py; no orphaned files remain on the public eval tree. One non-finding worth recording so nobody re-chases it: all 18 ratings posted after today's merge carry an empty `source` tag, which looks like the merged page failing to tag — it is not. They name `fp32cmp_goa_*` models, which the avp-only public pool cannot serve, so they came from an old internal rate.html still open in a tab from before the redirect landed.

- [2026-08-18 00:11] (GHOST-NOTE) Suomisoundi pipeline: full raw->train-ready run complete (BS-RoFormer stems 1260/1260, Music Flamingo captions 1260/1260 genre-hinted, Granite revisions 1260/1260, MIR whole-track timeseries 1260/1260 all 50 fields incl. stem-dependent ones, SAME-L latents 1260/1260, caption sidecar `eval/build_suomisoundi_sidecar.py` T1/T2/T3 1260/1260 — train-ready via `--encoded_dir`/`--caption_sidecar`). Two real bugs found+fixed along the way, both fleet-relevant: (1) `goa_granite_task.py::read_mf()` was feeding Granite the file PATH instead of the nested MF caption text (schema mismatch: caption text lives under `d["captions"][prompt_type]`, not top-level) — affected the ENTIRE goa big-set corpus (23232/23232), producing plausible-but-hallucinated genre-generic captions instead of real per-track revisions. Fixed (63546e6); goa's Granite corpus needed a full re-run. (2) `ls`/`rm DIR/*.json` silently misbehaves (bash ARG_MAX) against 20k+-file directories — glob expansion fails, `ls | wc -l` reports a false 0, `rm -f` deletes nothing — cost 3 wasted goa Granite resubmits before catching it via `find`-based commands instead. Memory: shell-glob-arg-limit-large-dirs.md. goa's Granite re-run (job 21255037) landed clean and content-verified (23232/23232) after the fix. Also fixed: `score_and_publish.py`'s `leg_ingest` missing `--rebuild` (e1a9639); `whole_track_expanded.py`'s melody-height stem lookup missing `.m4a` (mir 6942358); `goa_granite_task.py::genre_hint()` hardcoded to goa/psytrance with no override (63546e6, `--genre-hint`/auto-detect from the MF json's own field). Docs: mir/CLAUDE.md now documents the expected per-track folder layout + the `--add-fields` two-tier-field-set gotcha; ARCHITECTURE.md indexes both sidecar builders and their DIFFERENT key schemes (goa=relpath for live-encode, Suomisoundi=latent-filename-stem for pre-encoded — copying one onto the other's training mode silently drops every caption).
- [2026-08-21 08:52] (GHOST-NOTE) CORRECTION to my 2026-08-18 00:11 entry: I reported the Suomisoundi whole-track MIR timeseries as "1260/1260 all 50 fields" prematurely -- the re-extraction (adding stem-dependent fields) had actually died partway through (397/1260) sometime after that entry, and a self-matching bug in my own background-monitor loop (its pgrep -f pattern matched its own command-line source text) made it falsely report "still alive" for days. Kim noticed a pile of leftover tail -F processes and asked what they were, which surfaced it. Fixed: watch by real PID not text pattern, cleared 863 stale files, resumed, verified all 1260 by content this time (genuinely true now). Lesson: never pgrep -f a pattern that could match the watcher's own source -- memory shell-glob-arg-limit-large-dirs.md updated context, also see the new negative-result note in my journal.
- 2026-08-21 (CONTINUITY): B7 MIR-CONDITIONER LANE SHIPPED + 8-ARM LUMI BRACKET SUBMITTED (21427376-83). Kim's ask: "traditional models, our mir data as conditioners, rank 32 DoRAs, every feature, goa+avp aug (not biggoa)". New: stable-audio-3/scripts/mir_control.py (36-ch field registry incl. every timeseries field; packs = channel subsets; crop-exact slicing; per-item control dropout; PER-BLOCK zero-init projections into the DiT's native modular local-cond inlet, default blocks 12-23 per W's layer map; in-training control-ablation meter true/shuffled/zero; self-writing report.md) + build_ctrl_packs.py (prebuilt sibling _ctrl dirs; 5400 goa + 2393 avp arrays built locally, rsynced) + train_lora --mir_ctrl_* + lumi/sbatch/mirctrl_bracket.sbatch. 13 unit tests. TWO TRAPS for reuse: (1) .ctrl.npy must NEVER sit inside a latent dir -- PreEncodedDataset recursively globs *.npy and eats them as latents; (2) the modular inlet is per-TransformerBlock, not global -- installs are per-block. Executes the parked ATTRIBUTE_BRANCHES milestone (2026-06-19). SA3 2c3b650, SAO 90c921f. EXPERIMENTS B7.
