# EXPERIMENTS — planned, running, and potential experiments, with the findings behind them

*The forward-looking twin of `DISCOVERIES.md` (Kim direct, 2026-08-19). DISCOVERIES = what we found;
EXPERIMENTS = what we intend to test, why, how, and what would kill it. **Every planned or potential
experiment goes here with its related findings linked**, so a context compaction cannot lose the
reasoning that produced it. Hand-edited, team-maintained: add/move your entries, keep the status
current, filelock before editing (`python3 Misc/filelock.py acquire EXPERIMENTS.md --handle <you>`).
When an experiment lands, its RESULT goes to your journal → DISCOVERIES; here the entry moves to
"Done / superseded" with a one-line verdict and the link. Owner of the file's shape: THE-FINN (patrol);
owner of each entry: whoever listed it.*

**Status legend:** RUNNING · QUEUED (submitted/scheduled, nothing needed) · READY (code + command exist,
needs a submit/GPU slot) · PLANNED (agreed, not built) · POTENTIAL (proposed, not agreed) · GATED (waits
on a listed result) · DONE/SUPERSEDED.

**Briefing external reviewers/pre-review agents (2 headline experiments lost to this):** the chroma
readout is a LINEAR `Conv1d(256→128, k=1)` — its Jacobian is the constant `W_c`, so per-point Jacobian
SVDs and "co-activation graphs" of it are degenerate; SA3 attention is DIFFERENTIAL (two subtracted
softmaxes ⇒ SIGNED maps — thresholding invalid); 64 learned memory tokens act as global hubs in any
position graph. State these up front in every external brief.

**Standing methods that shape every entry:** lightweight tests first (Kim) · negative-result autopsy
before a null is final (Kim) · disintegration gate + Kim's ears on any "works" claim · manifest-v2
sidecars on every output · THREE-AUDIENCE standard on eval pages · **PQ alone is the best algorithmic
proxy of Kim's ear** (W, 08-21, fit on 668 real A/B votes: PQ-alone 77.6%; **CORRECTED same day** —
adding CLAP was first reported to beat it (78.8%) but that sat on a mismatched n (321 vs the full 438
pairs); on the full set PQ-alone wins outright (77.6% vs 75.1%), and corr(PQ,CLAP)=+0.60 means CLAP
isn't an independent axis either. If a soup got re-weighted toward CLAP on the retracted claim, undo
it. CLAP's real value is corroboration: independently reproduces PQ's parameter ranking and shows the
goa deficit is fidelity, not conditioning) — CE has ~zero correlation with his judgment (08-19
finding), stop leaning on it · **PQ has a sparse-material blind spot** (W, 08-21, 93,554 clips:
spearman(onset_density, PQ)=+0.376, sparse material 5.94 vs busy 7.44) — every PQ-ranked surface
(`top100.html`, best-of-N selection, the quality-weighted soup formula) systematically demotes
ambient/sparse tracks; Kim's read is beatless material should NOT be filtered from training,
especially with the density head coming, since it needs the low end of the range to learn from ·
**per-checkpoint p-values across the campaign are pseudo-replicated**
(810 checkpoint rows come from ~265 actual runs) — at RUN level only dataset, alpha, rank, optimizer
survive; batch/lr/precision go non-significant. **`frames_T` REMOVED from that survivor list, corrected
same day (W, 08-21):** the apparent T-length effect was reading architecture composition, not context
length — T256 in the sweep was 78% fullft with zero DoRA runs, T512 was 95% DoRA, so "T512/T4096 good,
T256/T2048 bad" was really "DoRA beats fullft on goa" wearing a frame-length costume. Within families
that differ only in T the spread is small and non-monotonic (46 pairs, longer-T wins 17/shorter 29,
p=0.104) — **there is no general frame-length effect.** Same correction pass also retracted W's earlier
AVP-adapter-advantage claim (p=9e-05 was DoRA vs a pool contaminated by 60 mislabeled broken `xft`
checkpoints tagged `arch=dora` in `clap_dora_aggregate.csv`; cleaned, the AVP adapter advantage
p=0.49 — does not exist in the data. Adapter-vs-fullft advantage is goa-only). Read any parameter-table
claim, including ones already in this file, against both corrections.

---

## A. Optimizer & training dynamics (why recent models broke)

### A1 — Step-resolution trajectory: batch vs optimizer (walk vs drift) — **RUNNING (LUMI pending) / local DONE**
- **Question:** is the "broken AdamW" signature (epoch displacements at the 1/√n random-walk floor; rank-1
  spike in B·A) a BATCH effect or an OPTIMIZER effect?
- **Findings so far (C 08-18/19):** AdamW bs1 = accum8: update autocorr 0.9^τ then 0, gradient window-SNR
  = 1/w to w=1024 (repeatable gradient < 0.1 % of energy), zero drift in 10k steps; Fusion bs1 on the
  SAME data: autocorr 0.215/0.129/0.081 at τ=100/500/1000, eff(1024) 0.411 vs 0.132 → **the optimizer
  decides; NS5 = low-rank persistent-signal amplifier**. Spike is LoRA-structure (present under both).
- **How:** `stable-audio-3/scripts/trajectory_sketch.py` (CountSketch recorder) + `eval/trajectory_sketch_analyze.py`;
  local arms in `SAO/runs/traj_sketch/`; LUMI 8-arm job `lumi/sbatch/traj_sketch_arms.sbatch` (Kim's upload).
- **Gate:** LUMI bs8 arms (native) — does learning (loss ↓) appear at bs8 under either optimizer?
- Links: journal 08-18/19, WORKLOG 08-18, ARCHITECTURE §B/§E.

### A2 — Muon damping: cosine / SNR-gate / both — **local DONE (cos, snr) · LUMI READY**
- **Findings:** cosine = a working brake (|update| 0.091→0.0087, late direction MORE coherent); update-based
  SNR gate inert (momentum makes row-consistency ~1) → **fixed: gate on the raw gradient** (`snr_source=grad`,
  SAT 3b7f82f). At bs1 no arm learns by loss in 5k steps.
- **How:** `FusionOpt(decay_schedule=cosine|linear|wsd, components+={'snr'})`, `train_lora --fusion-decay/--fusion-snr`.
  LUMI arms `bs1_fusion_cos/_snr/_cos_snr` in `traj_sketch_arms.sbatch`.
- **Gate:** does a braked Fusion run at bs8 converge where constant-LR Fusion runs away (W's 8× ‖ΔW‖ growth)?
- **Next variants (POTENTIAL):** inverse-sqrt decay (EDM2 Config E); `snr_beta` ≫ momentum window; per-neuron
  directional prior (see D4).

### A3 — Stock-Stability sanity matrix (AdamW LoRA/DoRA r16, 7 datasets, 1 GCD each + 8-GPU DDP) — **RUNNING on LUMI (21353159/60/61)**
- **Question:** Kim: "is stability's AdamW code broken?" — does the stock recipe give listenable models per
  dataset, and does 8× DDP at matched effective batch change the outcome?
- **Gate:** trajectory stats (`eval/compare_trajectory_stats.py`) + soups + Kim's ears; pull before scratch purge.
- Links: `lumi/sbatch/sanity16_arms.sbatch`, `sanity16_biggoa_ddp8.sbatch`, KIM-TASKLIST.

### A4 — Full-FT AdamW: the MATCHED control for the drone family — **🚨 DDP NEVER FORMED, see incident note below**
- **🚨 CONFIRMED BROKEN (C, 08-21):** `fullft_fleet.sbatch` used the disproven Pattern-2 DDP
  (`srun --ntasks=8 --gpus-per-task=1` + Lightning `SLURMEnvironment`) — same signature as job
  21161065. Verified live two ways: `fullft_avpaug`'s log shows eight `LOCAL_RANK: 0` lines +
  `-v3` colliding checkpoint writers; `fullft_suomi`'s completed step-count (158 opt-steps/epoch =
  1260/(bs2×GA4) with **no /8**) proves every rank consumed the full dataset independently. **Do
  NOT delete anything** — each `-vN` file is a complete, valid 1-GCD model (the original winning
  recipe). Sbatch converted to CSC torchrun pattern, `f1eaabc`, verify now runs the LOCAL_RANK
  check in-script rather than suggesting it.
- **⚠️ CORRECTED (C, from F's inventory, A10): this family is NOT the 8-replica ensemble the
  first reading claimed.** Version counts show mostly 1 checkpoint/epoch here (vs `winning_fleet`'s
  DoRA arms, which genuinely show 7-8) — 7 of 8 fullft ranks died silently, likely at model-load or
  first-step. So `effective_batch` here isn't just overstated by 8×, these runs are close to their
  ORIGINAL 1-GCD training time with no soup-windfall silver lining. `fullft_bigset.sbatch` (#68,
  the big-goa-set two-week-deliverable script) shares this family's Pattern-2 header — presumed
  hit by the SAME 1-live-7-idle failure, not yet checked.
- **REVISED DECISION (Kim, ~11:00, superseded the initial "keep"): cancel-soup-restart** — all
  Pattern-2 arms scancelled except `fullft_avpaug` 21422923 (near-complete, kept as the B9 source).
  Torchrun restarts submitted for the DoRA fleet; fullft restarts pending. Full detail: A10.
- **Why:** 2605.10468: full-FT of an Adam-pretrained base with Muon is the documented mismatch case;
  every prior full-FT was Fusion (drone) — the matched control was never run. Kim direct 08-21:
  AdamW full-FT fp32 T1024 lr1e-4 on biggoa/avpaug/suomi/mix3. bs2+GA4 (effective 64 — the only
  proven-safe full-FT batch pattern), EMA ON (render loads EMA weights), constant LR (no AdamW
  scheduler exists) → judge by EMA + soups. `PRECISION=fp16` twins one submit away (Kim preferred
  fp16's sound in the precision-ladder listens; fp16 also enables FA2). Kim's fp32-collapse worry
  answered: the collapse mechanism was Fusion norm growth, not fp32 (trajectory twins identical).

### A5 — DoRA-rows vs plain LoRA under Fusion at r128 — **PLANNED (LUMI, 2 GCDs)**
- **Why:** 2605.10468 found Adam-tuned LoRA variants do NOT transfer to Muon and never tested DoRA-Muon;
  our healthy family is DoRA-rows + Fusion — untested combination. Also r128 sits at the paper's
  degradation edge (our r256 arm's straight-line HIGH-EFF fits).

### A6 — Rank ladder r∈{16,32,64,128,256} × {AdamW, Fusion} with per-optimizer LR sweep + sketch — **POTENTIAL**
- The paper's own protocol; with the recorder on we also get walk-vs-drift per cell.

### A7 — Warmup for Fusion + LoRA (zero-init B trap) — **READY (one flag)**
- **Finding:** NS5 on zero-init B gives a full-size first step: |update| first10 = 1.33 (Fusion) vs 0.21
  (AdamW). Fix = `warmup_steps ≥ momentum window` (exists; make it default for Fusion+LoRA).

### A8 — CMuon chunking on the drone arms — **GATED on W**
- `--fusion-split-qkv/--fusion-split-adaln` exist; were they ON in the regsweep/surgical arms? If not,
  the cheapest retest of the late collapse (2608.02502: AdaLN is the scale pathway).

### A9 — Bread-and-butter AdamW production fleet (winning recipe × 4 datasets × 2 seeds) — **🚨 DDP NEVER FORMED (see A4's incident note — same bug, same fix, `winning_fleet.sbatch` converted in the same commit `f1eaabc`)**
- Do not read these as one 8×-batch DDP run per arm — each is 8 independent 1-GCD replicas at
  the ORIGINAL winning recipe's real batch size. `effective_batch` on these rows is wrong
  everywhere it's quoted. Not worthless: 8-seed ensemble/soup material, per C's framing in A4.
- **Kim direct:** copy `winning_avp_t1024_a45_fp32` (DoRA-rows r128 α45, AdamW lr 1e-4 constant, fp32,
  T1024, 20 ep) onto suomisoundi, big goa, the 3-source mix — plus **avp itself as the control** that
  isolates the one deliberate delta (1-GCD batch 4 → 8-GCD DDP batch 8). 8 × single-node 8-GCD jobs
  (multi-node DDP unsolved), ~680 GPUh. `lumi/sbatch/winning_fleet.sbatch`.
- **Gate:** constant-LR AdamW ⇒ judge by SOUPS/centroid (C1/C2 machinery) + trajectory stats + Kim's
  ears; per-arm DDP verify (LOCAL_RANK 0..7). Links: A1 (walk-vs-drift predicts these diffuse), C1.

### A11 — The "mystified why so bad" A/B²: DoRA/LoRA × AdamW-WSD/braked-Fusion — **TRAINING COMPLETE (16:13): all 16 arms + 2 LR probes COMPLETED 0:0 — renders/analysis next**
- **EXTENDED same hour (Kim: "oozles of hours, one day left"):** the same A/B² on suomi
  (21431938-41, ratified anchor probs — the first-ever suomi runs with correct captions AND real
  DDP AND a schedule), avpaug (21431942-45), old goa (21431946-49), atop bigset (21431784-87).
  Epochs step-matched to ~3.1k optimizer steps per corpus (suomi 320 / avpaug 160 / goa 64 /
  bigset 32; ckpt cadence scaled to ~10 ladders each). + 2 large-batch LR probes on goa
  dora_adamw: 2e-4 and 5.7e-4 sqrt-scaled (21431964/65) — main arms stay 1e-4 per W's run-level
  n.s. finding. Readout is per-corpus by construction (W's pooling confound dodged), and per W's
  underfit bit-exactness check the loss path is exonerated — A11 is the first real test of the
  optimizer half of the stack.
- **Fusion half VERIFIED training (14:45): decay banners live under true DDP — the braked kit's first confirmed real-DDP activation.**
- **Fusion-half incident + resubmit (13:0x):** all 8 original fusion arms died on argparse
  (`--fusion-snr grad` — a replace(count=1) fix that hit the comment line instead of OPTARGS;
  the ~55 min of apparent runtime was flash-staging crawl). Fixed for real (04e1e38, zero grad
  occurrences verified) and resubmitted as **21434153-60** (~1 h behind the AdamW half; step
  budget identical, so the factorial stays matched). AdamW half (10 jobs) unaffected throughout.
- 4 arms, everything pinned healthy: torchrun true DDP (verified pattern), T256, bf16 (FA2),
  per-rank bs16 (eff 128; W's monotonic batch finding), rank 128 α45, 32 ep, ckpt every 2,
  warmup 0.25 ep. AdamW arms = **the first scheduled-AdamW runs ever** (`--lr_schedule wsd`,
  knee ep8, cosine to 0.1×; known-answer tested; WORLD_SIZE horizon bug fixed en route — every
  prior schedule horizon would have run 8× long under real DDP). Fusion arms = full damping kit
  (--fusion-decay wsd knee-aligned + SNR gate row/grad-source). Staging lock added (no stampede).
- **⚠️ Standing caveat CORRECTED (W, 08-21, same day): the 27.7% figure was itself a bug.** v1
  measured ONE 30s window at a fixed offset, so it read intros not encodes (Kim caught it — good
  tracks landing in the "worst" list, 4 rips of one Koxbox track all there). v2 (max over 6 windows
  spanning the track) just finished: A-tier 20.7%→28.4%, D-tier(lossy) 5.4%→1.4% — **bigset is
  substantially cleaner than reported.**
- **✅ CLOSED (W, 2026-08-23) — both v2 re-audits complete, and the gap is REAL and LARGER than v1
  said.** BIGSET n=23232: A **28.4%** / B 66.8% / C 3.4% / D 1.4%. OLD GOA n=3978: A **86.0%** /
  B 11.4% / C 1.7% / D 0.8%. So the old corpus is **~3× richer in near-lossless material** and the
  "bigset is the more lossy corpus" premise is now **SUPPORTED** — it was unsupported in either
  direction between 08-21 and today. *(Supersedes 27.7% / 75.9% wherever those appear.)*
  **Why the fix looks right:** v1→v2 moved old-goa +10.1pp but bigset only +0.7pp. Max-over-windows
  RESCUES a genuinely-lossless track that had a quiet passage and CANNOT rescue genuine mp3, so the
  asymmetry is the fix behaving specifically; equal movement would have been a smell.
  **TWO CAVEATS W attaches, and they matter:** (1) this is an ENCODING-FIDELITY measure, not a
  musical-quality one — it does NOT show bigset-trained models are worse, and that link has never
  been demonstrated; (2) fidelity tiering here is DIAGNOSTIC, not a gate — W is explicitly not
  proposing to filter the bigset, and Kim's standing correction holds that PQ scores ambient 2–3
  regardless of fidelity, so beatless tracks stay in and we train control heads on them.
  Tooling: `mir/src/tools/goa_archive_quality.py` (v2 docstring records why MAX is the principled
  statistic). **Bearing on A12:** the bigset down-weight to ~20% of draws was taken on Kim's
  instinct that "it's got mp3 sources more than the others" — that instinct now has evidence. **The `goa_big_quality_matched` follow-up is CLOSED,
  not pending (Kim's call via W, 2026-08-23): DO NOT rebuild the 4,111 / 3,147 lists on v2 —
  drop them.** They existed only to select a quality-GATED subset, and gating was already rejected:
  PQ rates ambient 2–3 regardless of file fidelity, so it discards good music, and beatless tracks
  stay in because the control heads train on them. Regenerating them correctly would have produced
  a better-measured version of a thing we decided not to do. W has stamped `INVALID.md` into
  `stats/goa_big_quality_matched{,_noverlap}` and `goa_big_worst100` in mir so a future instance
  cannot mistake them for current.
  **The fidelity signal survives in a different form, and A12 is the reference use:** tier
  FRACTIONS as a corpus-MIXING WEIGHT — down-weight the more-compressed corpus while every track
  stays eligible — does the useful work without discarding anything, and needs only the two v2
  jsonls. **Recommended pattern for any future mix, over natural proportions.**
- Read-out: PQ/CE per epoch ladder + soups; the WSD-vs-constant contrast on AdamW is the direct
  test of the A2 "constant-LR walk needs averaging" mechanism (scheduled arm should be listenable
  at the TERMINAL ckpt if the knee does its job).
- **Why this arm matters more than "which optimizer sounds better" (W, 08-21, Kim's ask):**
  independently verified the SA3 training loss/RF math against a second team's from-scratch
  trainer (`underfit`, vendored not imported) — loss-normalization, masked-loss, and the RF
  noise/target construction are bit-identical (max|diff|=0.000e+00) across every config checked,
  including our fork's own additive-only commits. **Scope limit stated plainly: `underfit` imports
  our own `models/lora.py`, so it can't independently check adapter scaling** — but that module has
  zero fork commits (stock upstream), so the risk there is low. What it does NOT cover at all:
  **FusionOpt, spectral WD, AdaGC, and the WSD schedule are ours alone, no external reference
  exists for any of them.** So the base loss is exonerated and the optimizer path is now the only
  place a systematic bug could still hide — which is exactly what this entry's AdamW-vs-Fusion
  contrast tests, at matched everything, for the first time.

### A12 — The 5e-5 replicate: Kim's auditioned operating point, carried to every corpus — **RUNNING (2026-08-22, ep24 wave: 21447819/20/21/22 → probe 21447823)**

**Trigger (Kim direct, 2026-08-22, listening to `renders/length_variant/` on the drive as it pulled):**
the 5e-5 clips beat 1e-4, 2e-4 shows degradation, and — the observation that actually motivated
this — where 1e-4 and especially 2e-4 *"melt"* at cfg16/weight2, **5e-5 takes the same push and
stays musical**, "which speaks to me like some deeper very healthy structure." Robustness under
guidance overdrive as a proxy for a healthier optimum is a NEW selection criterion for us; every
prior lr call was made on unpushed clips.

**The run being replicated:** `runs/adamw_bf16_sweep/adamw_goa_t512_bs4_lr5e5`, arm 7 of
`efp_adamw_bf16_sweep.sbatch` (2026-07-24, the Zach-prompted AdamW-vs-Fusion A/B). Its real
settings, read off run_meta + sbatch + the ckpt itself — **four of them differ from the dorlor
lane and would have been silently overwritten by a "same settings" copy**:
| | replicated run | dorlor lane (A11) |
|---|---|---|
| alpha | **128** | 45 |
| lr schedule | **constant, no warmup** (ckpt `lr_schedulers: []`) | WSD, knee 25% |
| crop | **T512 beat-aware** | T256 |
| goa caption tiers | **0,0,1** (longform t3 only) | 0.6,0.3,0.1 |
| effective batch | **4** (bs4 on ONE GCD — that sweep ran 8 independent single-GCD arms off `SLURM_PROCID`, it was never DDP) | 128 |

**Two arms, `lumi/sbatch/lr5e5_allsets.sbatch`:**
- **21447642 fresh** — the recipe re-learned on the full mix.
- **21447644 warm** (`WARM=liked`) — *continues the actual model Kim heard*
  (`epoch=9-step=13500.ckpt`, Lightning 2.6.5, 687 dora-rows tensors, 1 optimizer state).
  Uses `--warm_start_ckpt`, **not** `--resume_ckpt`: resume also restores loop state, and those
  counters were written against a 1350-step goa-only epoch while this run is ~2700 steps/epoch
  over a different corpus. Warm-start keeps adapter weights + AdamW moments, drops only the
  epoch/shuffle counters — so `--epochs` is the ADDITIONAL count there.

**Mix** (per-source sidecars + per-source caption tiers): goa `latents_sa3` 5400 w1.0 `0,0,1`;
bigset `latents_goa_bigset` 12524 **w0.18** `0,0,1`; avpaug `latents_avp` w1.0 `0,0.9,0.1`;
suomi `suomisoundi_latents` 1261 w1.0 `0.25,0.45,0.30`. Bigset is down-weighted to ~20% of draws
(natural share 58%) — Kim: *"it's got mp3 sources more than the others"* — and rides t3 because
its granite tier measured NOT GROUNDED (folder-name derived, 1.24× rare-term recall vs chance).
`AUG=1` appends `latents_goa_aug8` (3941 bungee crops); **live augmentation is NOT available on
this path** — `--augment` is live-encode only, explicitly inert with `--encoded_dir`.

**Recorded deviation:** effective batch **8**, not 4 — single-GCD eff-4 is ~110 min/epoch on this
mix = 88 h to ep48, outside the allocation. BS=1 × 8 ranks is the nearest reachable regime (BS=4
× 8 = eff 32 would be a different experiment). Written into `run_meta.json`, not left to be
rediscovered.

**KILL / READ CRITERION.** The liked clip is ep9 of 10 over 5400 crops ≈ **54k crops seen**; ep48
of this mix is ~1.04M ≈ **19×**. "More of the recipe" and "19× the dose" are not safely the same
thing, so the ladder checkpoints every **2** epochs (24 rungs) and rung 1 sits near the original
dose — it brackets the auditioned point **from below** instead of starting past it. If the
robustness-under-push property is a *lightly-trained* property, the early rungs will show it and
the deep end will have lost it. Audition at cfg16/w2, not just cfg7 — that is the property being
selected for.

**EP24 PIVOT (Kim, 2026-08-22, ~02:00).** The ep48 pair (21447642/44) was scancelled and resubmitted
at **EPOCHS=24** as a 2×2 — fresh/warm × constant/wsd — because Kim flagged the open risk himself:
*"I hope the constant LR does not become an issue."* Constant 5e-5 is proven at 10 epochs, not 48.
ep24 is a decision point, not a target; the ladder still rungs every 2 epochs and the runs can be
continued if the ep24 board reads well.
- 21447819 fresh/constant · 21447820 warm/constant · 21447821 fresh/wsd · 21447822 warm/wsd
- **21447823 = `lr5e5_probe.sbatch` on `--dependency=afterany`** of all four — renders whatever rungs
  exist however the arms end (completed, crashed, walltime-killed). Fire-and-forget for an
  overnight; you wake to audio, not to a queued job that never ran.
- 21447824 = `dorlor_render.sbatch`, independent (A11's 32 arms, first audition).
- **Warm arms: EPOCHS is ADDITIONAL** (warm-start restarts counters), so they end ~ep34-equivalent
  of accumulated dose vs the fresh arms' 24 — the two ladders are NOT at matched dose.

**BATCH-AXIS CHECK (Kim, 2026-08-22): "batch size 1 clips from those runs were melted all the way
to hell. Is bs1x8 as stable as bs8?"** Yes — under REAL DDP. The eight ranks all-reduce to a mean
gradient over 8 crops with 8 independently drawn timesteps, statistically the batch-8 object; the
DiT has no BatchNorm, so nothing couples samples within a batch, and this run uses none of the
per-rank subbatch losses (stereo/subspace) where a rank-local estimate on 1 sample would be
noisier. Sweep evidence brackets it: **eff 1 melted, eff 4 is the liked run, ours is 8.**
⚠️ **THE COROLLARY IS THE IMPORTANT PART: if DDP silently fails (the A10 pattern), there is no
all-reduce and every rank becomes an independent trainer at BATCH 1 — precisely the melted regime.**
The `LOCAL_RANK 0..7` grep is therefore not a correctness check here, it is a quality predictor:
eight rank-0s = four arms training in the worst regime the sweep found. Check it before the ears.
*(Exact eff-4 was reachable — 4 ranks × bs1, same node-hour cost since billing is per NODE — but at
half throughput = ~36 h to ep48, past the 23 Aug wall. eff 8 is the closest reachable point, not a
free choice.)*

### A13 — Mellow-LR full-FT on AVP with subspace weighting ("let one run roll on alone") — **TRAINED (21448092, COMPLETED 03:44:22, 8 rungs, DDP verified 0..7); RENDERING (21453822)**

**Kim direct, ~03:00:** *"This one has a very mellow LR and some nice controls that have been
helpful."* AVP aug latents, T1024, **lr 2.5e-5**, FULL-FT, AdamW (wd default 0.01), subspace-loss
weighting on the v3sel basis, schedule flat to ep10 then cosine, ep64, eff batch 8 (bs1 × 8 ranks,
torchrun). `lumi/sbatch/fullft_avp_subloss.sbatch`. ~299 steps/epoch → ~19k steps.

**THREE PARTS OF THE ASK COULD NOT BE BUILT AS SPECIFIED — recorded because each looks available
until you check:**
1. **AdaGC is not implemented.** No flag, no code, in the trainer or the optimizer. It exists for
   us only as **E2**, a *planned* bracket on the LatCH melody head — not a DiT training feature.
2. **Spectral WD is FusionOpt-only** (`build_fusion_param_groups` → per-group decay on the 2D DiT
   matrices). Under `--optimizer adamw` there is no such path; `--weight_decay` there is plain
   decoupled AdamW decay. Kim's ruling: leave at default. *(Related history worth not losing: the
   builder default 0.01 was "too weak for NS5/Muon → drone"; ~0.1 is the full-FT Fusion guidance.
   So "spectral WD 0.02" would have been weak even where it exists.)*
3. **LIVE ENCODE CANNOT DELIVER BUNGEE PITCH AUGMENTATION — this is structural.** `--augment` is
   live-encode-only (inert with `--encoded_dir`) and its axes are sub-frame phase shift / gain /
   stereo width / polarity. **Pitch shift and time stretch are `--aug-heavy` only, and that path
   lazily loads torchaudio transforms = the sox-adjacent route CLAUDE.md bans in favour of
   bungee.** Kim: *"bungee augs will be mandatory, especially the pitch augs."* Bungee is offline
   CPU work by construction ⇒ **the only route to bungee pitch augs is a pre-augmented,
   pre-encoded latent dir.** Hence `latents_avp`, not a `--data_dir` live-encode.
   Kim's instinct — *"SAMEs encode fast on CPU, could we pre-calculate in parallel?"* — is right
   and already built: **`aug8_encode.sbatch`** = phase A CPU bungee via HyperQueue, phase B SAME-L
   encode, both on one node so the CPU phase rides the GPU booking for free. Not startable
   tonight: its "bungee_python importable inside the container" risk is still open in the draft,
   and `$SCRATCH/avp_src` showed no wav/flac at depth ≤3 — the source audio may not be up there.

**SUBSPACE WEIGHT = 12, and NOT because 12 won.** Kim asked for "something which we know to work".
**Nothing does yet** — weights tried 2/5/12 (v3sel grid, ep19), 20 (goa), 24 (latest lane, 4
corpora), and per **B1** the quartet's renders only landed after F's coverage audit caught that
the tgate arm had never been rendered despite being reported as such; **the whole set still awaits
Kim's ears.** 12 = top of the COMPLETED grid and the baseline the k24 lane itself names, so this
stays comparable. NOT 24: that lane was DoRA at eff batch 64 / lr 8e-5 against this run's full-FT
at eff 8 / lr 2.5e-5, and a 5×-midpoint weight across that gap could dominate the loss. **No tgate
on purpose** — the deficit-vs-r2 mode A/B is running as 21439464 and tgate here would preempt it.

**READ IT AS:** subspace loss is our own "+10–15% tool" (B1: the wall is structural, melody is
relational, no linear channel subspace captures it — B9/D12 conditioning is the wall-breaker). So
judge this run on whether mellow-LR full-FT *sounds good* with a modest assist, NOT on whether
melody arrives. ⚠️ Full-FT fats are ~31 GB each; `CKEVERY=8` → 8 rungs → ~250 GB (storage was
35% of TB-hours at submit). Do not densify the ladder without checking free space.

**RENDER PASS WAS MISSING — 21453822 (`a13_render.sbatch`, 2026-08-22).** The training sbatch
shipped with no audition wired — the same gap that left A11's 32 arms unheard. Full-FT ckpts render
as `--ckpt none --base-state-ckpt <ck>`; adapter `--strengths` do not apply, so the pushed axis is
cfg alone: 20 prompts × cfg{7,16} × 8 rungs = 320 cells → `renders/a13_avp/`.
**STANDING LESSON: a training sbatch is not finished until its render pass exists.** Every arm that
trains without one becomes another unauditioned family — that is exactly how A11 accumulated 32.

### B11 — Decoupled Muon/AdamW learning rates (Zach's ratio) — **READY, flag shipped, unrun (C 2026-09-04)**
- **Why.** Zach/Stability: *"I run Muon at 1e-3 for pretraining... around 10x what I would use for AdamW"* and
  *"I keep the AdamW parameters at normal AdamW LR"*. Our best Fusion LR is 5e-6 — ~200x below. `build_fusion_param_groups`
  has ALWAYS accepted `spectral_lr`/`scalar_lr` and **nothing ever passed them**, so every Fusion run used ONE lr for
  BOTH groups. Coupling means the spectral rate cannot rise without dragging norms/biases with it — the params that
  destabilise, and our failure mode is latent-scale runaway.
- **Arms.** A `--lr 5e-6` (control) · B `--spectral-lr 5e-5 --scalar-lr 5e-6` (ratio) · C `--spectral-lr 5e-4 --scalar-lr 5e-6`.
  Same seed/data/steps as the autoscale arms; readout = `path_length`/`step_cos` (G's bs2 control is the precedent).
- **Caveats to keep in the arm's notes.** Zach's 1e-3 is PRETRAINING; the RATIO is the transferable half, not the absolute.
  And MASTER records our base as "overwhelmingly AdamW-shaped" — Muon was adopted late/briefly — so the geometry his rule
  assumes may not describe our base at all.
- **Kill criterion (3 clauses; the third is G's and is the one C would have mis-read).** (1) C unstable AND B
  indistinguishable from A on trajectory geometry ⇒ coupling hypothesis dead, 5e-6 is the real optimum.
  (2) B and C both degrade ⇒ likeliest cause is the AdamW-shaped base, a real finding not a failed arm.
  (3) **If B DESTABILISES, the story INVERTS**: coupling predicts the scalar group is the fragile one, so raising
  ONLY spectral should be safe. B blowing up means the fragility is spectral-side and the whole diagnosis is wrong.
  Owner: GHOST-NOTE (briefed, verified the flag reaches gamma_t at fusion_opt.py:722/:951; awaiting Kim's go — a
  ~7.5h 3-arm GPU bracket is Kim's call, not a peer's).

- **PARTIAL RESULT, 2026-09-07 (G) — clause (3) FIRES: the fragility is SPECTRAL-side.** Not B11's own arms
  (those pair spectral with `scalar 5e-6`), but a clean isolate of the spectral group all the same, because two
  full-FT runs share `scalar_lr 1e-4` and differ only in the spectral rate:
  `fullft_autoscale_2026-09-04/C_dual` (spectral **1e-4**) sits flat at median `train/loss` **0.79**, max 0.9;
  `fullft_dual_1e-3_2026-09-05` (spectral **1e-3**, 6000 steps, same seed/data/subset) runs at median **2.5**
  in every 1000-step bin, spikes above 5.0 on **361 of 960** logged steps (38%, first at step 206), peaks
  15833 / 10308 / 9504, and ends higher than it starts — with `gradient_clip_val 1.0` active and not containing it.
  Raising ONLY the spectral group destabilises ⇒ the coupling diagnosis that motivated B11 (scalar group fragile,
  spectral safe to raise) is **inverted**, exactly as clause (3) anticipated. Zach's ~10x ratio does not port here;
  the AdamW-shaped-base caveat in this entry is the live explanation. **Ceiling is bracketed: 1e-4 usable, 1e-3 not**
  — B11's arm C at `spectral 5e-4` now sits inside the suspect band and should be treated as likely-unstable rather
  than exploratory. Evidence supports only 1e-4 > 1e-5; a previous "spectral needs a bigger LR" claim of mine
  (withdrawn under challenge) is now closed from above too.
  *Meter warning for whoever reads these logs:* bin MEANS on the 1e-3 run show 405 → 84 and read as clean
  convergence. That is outlier domination — the run diverges throughout. Use **median + a spike count**, never the
  mean, on any arm suspected of instability.
  Run: `/home/kim/fullft_dual_1e-3_2026-09-05/run_meta.json` (`result` field). Journal: `profiles/ghost-note.journal.md` 2026-09-07.

### B12 — Rewind post-training by weight interpolation (PT → base soup) — **READY, tool built, unrun (C 2026-09-04)**
- **Why (Kim).** PT "gets some things right, like a coherent, punchy sound" but "always sounds more or less the same with
  the kick, bass and percussions". Rewind partially instead of choosing.
- **Measured before building.** 997 identical tensors; median relative delta 0.0013, **MEAN 0.0215, MAX 0.714**;
  median cosine 1.0000; 6/899 below cos 0.9. ⚠ **CORRECTED 2026-09-04**: C first summarised this as "post-training
  barely moved the weights" — the median is the wrong statistic for a tail this heavy (mean is 16× the median).
  The supported claim is that the change is **highly CONCENTRATED**: near-zero in most tensors, 0.56–0.71 in the
  `to_local_embed.0.bias` tensors of layers 16-19. G's independent functional measurement confirms the tail —
  PT-rendered clips vs base-rendered: hf_ratio **+57%**, centroid +23%, flatness +42%, crest 4.64 vs 5.83
  (63 vs 237 checkpoints). A bias adds directly to activations without input scaling, so a 70% bias change is a
  first-order shift, not a perturbation. ⇒ **those 48 bias tensors are an unusually cheap control surface, a
  finding independent of the soup.**
- **Why interpolation is still safe.** NOT because the models are close — that justification is now thin. Because
  PT is a fine-tune OF base, so they lie on ONE trajectory (linear-mode-connectivity regime), unlike the
  independently-trained soups of C1/C2. Expect intermediate alphas to move audibly more than 0.13% suggests.
- **Arms.** global alpha {0.25,0.5,0.75,1.0} · TARGETED alpha=1 everywhere except `to_local_embed.*bias` held at {0,0.5}
  · three-way `+ beta*(FT-base)` on the winner. Tool `eval/soup_pt_ladder.py`; 8.6 GB/blend.
- **Trap.** PT is a few-step ping-pong denoiser (`--steps 8`), base is multi-step. An intermediate alpha belongs to
  NEITHER — render each blend under BOTH samplers. **Judge by ear**; we have no metric for "punchy but varied" and this
  week's record says do not invent one casually.

### A14 — Let LoRA A move: asymmetric step size (`--modular-lora-a-lr-mult 20`) — **READY, Kim to run (C, 2026-09-23)**
- **Question:** does the input side of the adapter matter to the SOUND? On audition_160ep_2026-09-22-b
  A's row space stayed 99.2% unchanged from step 240 to 1440 (B's column space: 35%), so every adapter
  read a random 128-d slice of its input for the whole run. Gate for porting LoRA-TSD (2609.02734,
  `~/Projects/LoRA-TSD`; unbatched it costs 8.5 s/step on our 229 adapters, a batched rewrite is ~a session).
- **Arm:** audition recipe re-run to step 480 with A's step x20 (applied after NorMuon, WD unchanged).
  Same seed, data order and schedule as the baseline, so its step 240/480 checkpoints + clips are the control.
- **Read:** ears first (step 240/480 clips vs baseline); then `eval/lora_gauge_drift.py` and A's
  row-space overlap. **Kill:** same sound and A still >0.95 overlap => A-subspace is not our bottleneck,
  drop LoRA-TSD. Clearly different/better => build the batched LoRA-TSD.

### A15 — Does DoRA sound rougher than plain LoRA on our finetunes? (Stable Audio Discord hearsay, 2026-10-15) — **POTENTIAL (cheap A/B, GHOST-NOTE)**
- **Origin:** Kim relayed that someone on the Stable Audio Discord prefers LoRAs to DoRAs because DoRAs "sound rough". Kim's own comment: that is exactly an issue we have on some occasions
  (gradients that overgrow, squashed punch, coarseness the steering heads then have to repair). Unverified second-hand claim, no recipe or audio from the poster; recorded as a lead, not a finding.
- **Why plausible here:** the DoRA magnitude vector is a per-column scale that the optimiser can drive freely; our own failure log already has DoRA magnitude zero-crossing NaN, the cautious-rescale norm
  inflation and runaway-scale arms (docs/training-findings.md section A), all magnitude-path failures that a plain LoRA does not have. The punch steering results (bass+body heads fixing coarseness) are
  a downstream symptom of the same family. None of this proves DoRA is rougher.
- **Test:** same data, rank, steps, optimiser and seed, train `--adapter_type lora` vs `dora-rows` (train_lora_modular.py), equal EMA/horizon, render the canonical clip grid at matched strength; compare with the
  level-matched metrics we already have (centroid, flatness, zero-crossing rate, crest, hf ratio) AND Kim's 1-5 ratings on the punch rating page (:8058), roughness being a listening judgement.
  Also compare the multiplicative magnitude update (`--modular-magnitude-update multiplicative`) as a third arm, since it is the existing fix for the magnitude path.
- **Kill-criterion:** no rating or roughness-metric difference beyond seed-to-seed spread on 4+ seeds.
- **Instrument audit first:** roughness has no calibrated meter here (Audiobox and CLAP did not track the punch preference), so the ratings are the primary read.

## B. The melody wall

### B1 — #59 subspace-weighted RF loss, v3 melody-selective basis, K∈{2,5,12} — **READY (LUMI, Kim's next-night submit)**
- **Findings:** v2 basis had ZERO melody-vs-codec selectivity; v3 (whitened CSP) 5.1× SNR
  (`eval/musicology/melody_selective_subspace_2026-08-06/`). SAME eigen-spectrum 786× anisotropic, melody
  in the suppressed 188/256 eigendirections; v-trained base under-recovers them 8.3× at σ=.2 (E1 pre-test).
- **How:** `lumi/sbatch/subspace_loss_v3sel_grid_mt.sbatch` (4 arms now). Basis `lumi/melody_subspace15_selective_v3.npz`.
- **Gate:** whitened-chroma recurrence (`eval/melody_wall_analysis.py`) + Kim's ears vs `lreq` baseline.
- **Caveat:** recipe is AdamW bs4 constant-LR (= the diffusing regime, A1) — kept for comparability; if all
  arms random-walk, rerun the winning K under Fusion-braked (A2).

### B2 — R²(t)-gated melody term (arm 4 of B1) — **TRAINED (3 ckpts on LUMI), ⚠️ NOT ACTUALLY RENDERED**
- **AUDIO READOUT (08-21 evening, 1680 matched cells):** all v3sel arms recurrence-UP at cleaner texture; k5 best (+16% rel), tgate +0.011 < k5 +0.030 — the R²(t) gate UNDERPERFORMS flat K=5 (first read; ears pending). K-curve non-monotonic (2<12<5) → B10's K=24 is the far-side probe. Gains concentrated in ~half the cells → per-prompt cut next. VERDICT.md in lumi_runs/analysis/melody_wall_v3sel_tgate/.
- **"Right subspace?" probe (Kim's question, 08-21 evening):** static-vs-temporal energy split of
  real latents projected onto the v3 basis (200 crops): static share 0.173 mean, 0/15 dims
  majority-static, vs 0.295 latent-wide — the basis is MORE temporal than the latent at large;
  the D11 fingerprint concern does NOT contaminate it. Remaining doubts: tgate ran mode=r2
  (weights the easy/recoverable region; mode=deficit untested — cheapest next arm in this lane)
  and the structural ceiling (melody is relational; no linear channel subspace captures it —
  the conditioning lane (B9/D12) is the wall-breaker, subspace loss is a +10-15% tool).
- **⚠️ CORRECTED (F, 08-21 coverage audit):** earlier said "renders done, verdict = PENDING Kim's
  ears" — checked directly (LUMI `subspace_loss_v3sel_grid_mt/subloss_v3sel_k5_tgate`, local
  `evals_aac`, `manifest_live.jsonl`) and **nothing is rendered anywhere.** 3 checkpoints exist on
  LUMI, zero clips exist anywhere. The other three B1 arms (k2/k12/k5) ARE in the live manifest —
  this one alone was never actually rendered despite being reported as such.
- **Why:** melody recoverable only in a t-window (2-crop probe: R²_melody .995/.744/.011 at t=.05/.5/.95 vs
  rest .997/.829/.239); a flat K spends most of its budget where melody isn't representable. Lemma A.2 of
  2602.19512: per-t weighting is the isotropic learned-schedule case (their best FFHQ result).
- **How:** `stable_audio_3/training/tgate.py`, `--subspace-loss-tgate`, curve from `eval/melody_r2_vs_t.py`
  (the arm self-measures if `lumi/melody_r2_vs_t_medium-base.json` is absent). Modes r2 / r2sq / deficit.
- **Kill:** no movement in recurrence or ears by ep10 → B4 gets the budget. Reference 48-crop curve: queued locally.
  **Can't apply the kill criterion until it's actually rendered.**

### B3 — x0-target (E1a, JLT 2605.27102 port) — **READY (built 07-31, never submitted)**
- Rebalances ALL low-variance eigendirections at once (complement to B1's targeted upweight). Needs a LUMI arm.

### B4 — SFD "melody-first": semantic (melody) latent denoised AHEAD of texture by Δt — **PLANNED (structural)**
- **Why:** 2512.04926: semantic-first alone 5.24→3.03 FID, 100× faster convergence; dissolves the
  variance-drowning mechanism instead of re-weighting it. Our semantic latent is nearly free (SAME
  chroma readout / 15-d melody subspace; learn a small compressor — PCA semantics underperformed).
- **How (sketch):** noised melody latent through SA3's 257-ch `local_add_cond` inlet, second timestep via
  global cond, a v̂_s output head, two-timestep noising in the wrapper; Δt≈0.3; base ckpt. Weeks + one
  LUMI run. **Gated on B1/B2 plateauing.**

### B5 — Anisotropic / rotating melody schedule (learn the clock) — **POTENTIAL (theory filed)**
- 2602.19512 (implementation, VE score-based) + 2608.15103 (design rules: low-variance directions noised
  SLOWER ⇔ melody leads in reverse; rotation order must track scale-dependent geometry — ours rotates:
  rhythm at high noise, harmony at low). RF port needed. After B4; `P_melody` then used twice (schedule + loss).

### B6 — Head-B / chroma-guided / prepend-cond melody conditioning — **DONE-ish / PARKED**
- Head-B steers at cfg16 only (07-29); chroma melody-turning probe NEGATIVE 0/12 (07-22). Superseded in
  priority by B1–B4. Links: DISCOVERIES "melody".

### B7 — MIR-timeseries conditioning: rank-32 DoRA + per-frame inlet vs decoupled cross-attn (Kim direct 2026-08-21) — **OUTCOME UNKNOWN: 3 torchrun arms 21430167/68/69 submitted 08-21, never pulled — C owns (corrected 2026-09-24 weekly)**
- **2026-09-24:** nothing from these arms exists locally under any `mirctrl*` name; their output would be on
  LUMI at `$SCRATCH/runs/mirctrl_bracket/<NAME>` (`lumi/sbatch/mirctrl_bracket.sbatch:67`). LUMI couldn't be
  checked (F's ssh cert expired). **Next:** one read-only `sacct -j 21430167,21430168,21430169` + `ls` of that
  dir. Remember the /scratch purge window (MEMORY: lumi-project-purge-deadline): results may already be gone.
- **Final submit (~11:15, third batch):** batches 1-2 (21427376-83, 21428085-90) died at preflight
  (missing ctrl rsync; stale-empty-flash staging bug) — zero GPUh lost. This batch = torchrun
  (real 8-way DDP, pattern verified on the wfleet restarts) + stage-if-empty + the triple
  freeze-out fix. Kim trimmed to the 3 priority packs (dynamics/stems/spectral + ablation arms
  cut for budget; submit lines remain in the sbatch header).
- **08-21 ~10:40 resubmit:** ctrl dirs verified on scratch, fixed code verified on LUMI by remote
  grep (train_lora.py:2 / diffusion.py:1 modular refs = local parity). New jobs: 21428085 all,
  086 melody, 087 rhythm, 088 dynamics, 089 stems, 090 spectral (+ BLOCKS=all and RANK=64 arms
  submitted, IDs truncated in paste). Health signature per arm: 're-enabled 48 projection param
  tensors' + step-1 ablation gain line, no preflight FATAL.
- **08-21 ~10:00:** first submits 21427376-83 all FAILED in seconds at the sbatch's own preflight
  (latents_sa3_ctrl not yet rsynced — guard worked, zero GPUh burned). Meanwhile the local ablation
  meter caught a REAL triple bug: under lora_config the wrapper (1) re-froze the post-install
  projections, (2) excluded them from the optimizer (get_lora_params only), and (3) add_lora
  DoRA-WRAPPED the zero-init projection Linears (dora-rows of a zero base row = dead inlet forever,
  with healthy-looking grads into the wrap). Fixed (SA3 6944f8a) + LIVE-VERIFIED: grads 717 vs 1.5,
  proj weights 236→1232 over 40 steps, control_gain +0.046 by step 21 (shuffled control hurts vs
  aligned ⇒ alignment exploited). STANDING RULE: post-load trainable modules in lora_config runs
  face three independent silent killers — freeze, optimizer exclusion, adapter-wrapping; verify
  with a gain meter. Resubmit checklist on KIM-TASKLIST (ctrl rsync → code rsync → same 8 lines).
- **STATUS 08-21 morning:** code landed + 13 unit tests (SA3 2c3b650: `scripts/mir_control.py` +
  `build_ctrl_packs.py` + train_lora `--mir_ctrl_*`; SAO 90c921f: `lumi/sbatch/mirctrl_bracket.sbatch`).
  Kim submitted the full bracket: PACK = all / melody / rhythm / dynamics / stems / spectral +
  all-BLOCKS=all + all-RANK=64 (jobs **21427376-83**, 1 node × 14 h each). Design deltas found en
  route: (a) the modular local-cond inlet is **per-TransformerBlock** — projections install on blocks
  12-23 by default (W layer-map union), BLOCKS=all is arm 7; (b) ctrl arrays live in **sibling
  `_ctrl` dirs** — co-located .ctrl.npy gets recursively globbed AS LATENTS by PreEncodedDataset;
  (c) every arm self-reports (control-ablation meter every 500 steps: loss under true/shuffled/zero
  control; `control_gain > 0` = aligned control exploited — the kill-criterion is readable from
  report.md even after the allocation ends). Local smoke: torch_shm_manager hang with workers>0 on
  the shared box (LOCAL sandbox quirk — LUMI fleet has run file_system sharing + tensor metadata all
  month); re-verified with workers=0 + the prebuilt-ctrl path. Arm B (frozen-base AttributeEncoder
  cross-attn) remains the LOCAL comparison, not yet scheduled.
- **Kim's ask:** "train some really traditional models, using our mir data as conditioners. probably
  like rank 32 DoRAs" — classic MIR curves (band-RMS ×4, beat/downbeat/onset ×3, HPCP ×12 ≈ 19 ch,
  already time-aligned to T=4096 by `LatentControlDataset(controls=("dynamics","rhythm","melody"))`)
  as explicit conditioning. This EXECUTES the parked 2026-06-19 milestone
  `control/sa3_control/ATTRIBUTE_BRANCHES.md` (riffer trained with controls=(); branch never flipped on).
- **Design — the A/B settles the injection question that doc left open:**
  **Arm A (Kim's):** curves → 1×1-conv projection → per-frame ADDITIVE stream (local_add_cond-style)
  + rank-32 DoRA on late blocks 16–23 self-attn+FF (W's layer-map prior; rhythm 12–19). Backbone
  learns to USE the stream — the chroma-guidance null (0/12) showed the frozen base won't follow
  signals it wasn't trained on. **Arm B (control, already coded):** same 19 ch → `AttributeEncoder`
  → decoupled time-aligned cross-attn adapter, base frozen, zero-init (MuseControlLite shape).
  Per-item CFG-dropout on the control in both arms (control-CFG sweepable at inference).
- **First step (30 min):** probe medium-base for usable `modular_local_cond`/`local_add_cond`
  plumbing (ATTRIBUTE_BRANCHES' own precondition). Integration gap to close: `sa3_control/train.py`
  freezes the base — needs a DoRA-on-base option for Arm A.
- **Data/recipe:** `latents_sa3` (5400 goa crops with .TIMESERIES.npz), local GPU, fp32 medium-base,
  AdamW standard recipe, judged by EMA/soups (sanity16 rule). R²(t) context: melody R² collapses at
  high noise → conditioner earns its keep early in sampling.
- **Eval (objective, no ears to gate):** held-out curve → generate → re-extract with mir →
  time-resolved correlation; MERIT S_mel/S_rhy/S_tim (steer melody ⇒ S_mel up, others flat);
  different-curve ⇒ different-output check. **Kill-criterion:** after ~10 ep, if held-out
  curve-following corr of A ≤ B ≤ no-control baseline, the inlet is unused — stop.

### C3-addendum — Replica-soup verdict (2026-08-21 evening): WORKS on healthy arms
- a45 rsoup19/rtsoup cells score CLEAN (HF 0.004-0.006 = raw baseline; G) — the bubbly-artifact
  finding was a128-contamination-ONLY (blending a spike-corrupted replica set). Pipeline
  separately exonerated (soup-of-one identity test, audio cosine 1.000). Open: PQ delta of a45
  soup vs single-replica cells (the averaging-rescue quantification); spectral repair on a128
  queued behind G's checkpoint pull.

### B8 — Suomisoundi T512 anchor-clean + caption-probs drift postmortem (W+C, 2026-08-21) — **RUNNING: 21430198 (torchrun, PROBS_OVERRIDE=0.25,0.45,0.30); the cancelled 21428358/59 partials kept as soup input, see A10**
- W's audit found winning_fleet's suomi tuple 0,0.9,0.1 was C's drift from the ratified
  0.25/0.45/0.30 (Kim 08-18) — zero t1 share = the corpus-anchor token "suomisoundi" never
  trains. F confirmed the drifted probs LIVE in the four running T1024 arms' own logs (a45 s1/s2 +
  a128 s1/s2, 7.5–9.5 h in). New arms: DATASET=suomi FRAMES=512 PROBS_OVERRIDE=0.25,0.45,0.30,
  seeds 1/2 (21428358/59; first submit 21428140/41 cancelled over script-spool timing ambiguity).
  These are the only anchor-CLEAN suomi arms; they also cover W's untested-axis T512 (his sweep:
  T512 7.274 > T1024 6.751 at run level). Kim's kill-or-keep on the four confounded T1024 arms:
  OPEN. Render probe of the confound: fleet_quick_render's suomi_anchor prompt (the untrained t1)
  vs suomi_modal/random — weak anchor response on the T1024 arms = the confound made audible.

### B9 — Control stack on the FULL-FT backbone (FiLM/Head-B + melody f0 + LatCH, best values + Fusion) — **COMPLETE (16:13): all 8 arms finished 0:0 — Head-B FT-vs-base pair + 6 best-recipe heads trained; readout = val summaries + melody pilot eval**
- **All 8 arms healthy 14:20** (F's watch): Head-B pair r0/r1 = base-state cov 100.0% + melody_dir
  2649/5400; latch arms printing the correct source-track val split (808 crops / 401 held-out
  tracks — matches D3's local numbers exactly); real compute (53 min AveCPU, 1.5 it/s, loss moving).
- **The six-defect chain, for the postmortem ledger** (each one-line, each unmaskable only after
  the previous fix): missing scratch jsons → sed-pipe rc-laundering (8-min COMPLETED) → node/glob
  wedge (banners added) → scratch base-npy gone (Jul-14 tar; flash-pointed) → preflight globs
  re-blinding the banners (stat-probes) → unbound FLASH in the inner block → stale flash npz
  (20-field July snapshot, no f0 — the derivative-doesn't-know-its-source-changed pattern).
  Guards left behind at every step; ftstack is now the most defensively-written sbatch in the repo.
- Kim: "take our best full finetune, and train our FiLM, melody and LATCH heads with best known
  values and Fusion on top of that instead of the base model." One node, 8 single-GCD arms
  (`lumi/sbatch/ftstack_heads.sbatch`, FT_CKPT knob): r0 Head-B FiLM on the full-FT EMA weights
  (new --base-state-ckpt overlay in sa3_control/train.py, the render-proven prefix-strip loader),
  r1 Head-B on base = the matched control; r2-7 = f0_other/f0_bass/hpcp/rms_energy_bass/
  onset_envelope/spectral_flatness heads with the best-known recipe (Fusion SF-NorMuon
  ns5,normuon,sf + adaln_zero + bf16-hot + EMA 0.999 + COSINE fusion-decay [braked] + val split
  BY SOURCE TRACK per 83329a8). Note: readout heads are backbone-free by construction — the
  backbone-dependent science is the r0-vs-r1 Head-B pair; heads ride along for the recipe upgrade.
- Prereqs: TIMESERIES npz (~3.1G) co-located into scratch latents_sa3/ (npz ≠ npy glob, safe),
  latents_sa3_melody/ (~10M), control/ + latch trainer code sync. FT_CKPT menu: today's
  ### A14 — ModularOptimizer (cubic5 + NorMuon + Schedule-Free + Prodigy Escape Velocity + Overtraining WD) — **PARTIAL DONE (6h production run trained clean to 13.5k steps) + VADD fix independently verified; a second (higher-LR) run crashed, cause identified but not root-caused**
- **Question:** Can a modular stage-based optimizer (`ModularOptimizer`) combine:
  1. `cubic5` Newton-Schulz polynomial (eliminating Gram-square matmul $A @ A$, cutting matmuls $3 \to 2$ per step, zero hipblasLt tile warnings on AMD gfx1201),
  2. NorMuon per-neuron row scaling,
  3. Schedule-Free iterate tracking (eliminating the need for cosine LR schedules),
  4. Prodigy dual-norm coupled Escape Velocity (`ev_max=2.0`, `ev_beta=0.999`),
  5. Everett & Qiu (2026) overtraining weight decay scaling ($\sqrt{1 + \text{epoch}}$),
  to train stably and preserve music fidelity across 20 epochs on canonical `latents_sa3` (5400 items) without late-run spectral drift or collapse?
- **Hypothesis (Kim direct):** "don't use cosine LR, I think our improvements should take care of that." With NorMuon and Schedule-Free iterate averaging, the optimizer operates scale-invariantly; `cubic5` gives superior isometric conditioning ($\sigma \in [0.77, 1.30]$, mean 0.96 vs NS5's 0.85); and Escape Velocity dynamically bounds step-size safely without manual LR decay.
- **Config:** `medium-base`, DoRA-rows $r=128, \alpha=128$, `lr=1e-4`, `warmup_steps=200`, `weight_decay=0.01`, `batch_size=8`, `num_workers=4`, `frames=512`.
- **Run:** `modular_opt_cubic5_sf_ev_20ep_13500s_2026-09-21_0148` in `/run/media/kim/Mantu/sa3_lora_runs/`.
- **Milestones:** Checkpoint every 675 steps (1 epoch); 3-prompt demos rendered at steps 100, 675, 3375, 6750, 10125, 13500.

**RESULT (Antigravity + Kim, full writeup `OPTIMIZER_TRAJECTORY_LATENT_AND_DISCONTINUITY_FINDINGS.md`,
tool `scripts/analyze_all_checkpoints.py`, 2026-09-21).** The 6h run trained clean: `‖B‖_F` grew
sub-linearly (1.34→33.58 over 13.5k steps, matching the $\sqrt{t}$ prediction from the overtraining
WD schedule), directional cosine rose monotonically 0.57→0.9475 (locking onto a low-rank descent
geodesic, unlike AdamW's ~0.09 near-orthogonal random walk or Fusion-Autoscale's runaway 0.98/
$\|B\|_F$>390 that collapsed rhythm by step 2k), and the 150 BPM rhythm-entrainment score rose
monotonically 0.7336→0.7915. **Root cause of this session's waveform-discontinuity investigation
(independently converged on via a completely different method — corpus-wide corruption scanning,
see WORKLOG 2026-09-21/-note below):** under aggressive CFG + OOD prompts, generated clean-latent
std can exceed a checkpoint's normal operating range, and the SAME decoder's nonlinear layers
respond to that with single-sample discontinuities — not clipping, not a random ROCm bitflip. Fix:
**VADD (Variance-Aware Dynamic Dampening)**, a 3-tier system — Tier 1 a quadratic hinge loss barrier
on clean-latent std during training, Tier 2 an optimizer step-size throttle keyed off a running std
estimate, **Tier 3 a hard clamp on the generated latent's std before VAE decode at inference/demo
time** (`--demo-latent-clamp`, `stable-audio-3/scripts/eval_demo_callback.py`). Their own measurement:
232→30 discontinuities (87.1%) on a corrupted `step6750_rb_rare_7` clip.

**INDEPENDENTLY VERIFIED (GHOST-NOTE, same day, different corpus/checkpoint, fresh from-scratch
decoder load):** z0 std for a shared reference clip (`dora16_avp_originals_earlyeps_ptm ep2/gf_11`)
matched the external tool's own number **bit-for-bit (3.317101)** — confirms both toolchains measure
the same quantity the same way. Applying the Tier-3 clamp (std 3.317→1.20) to that clip's raw decoder
output cut single-sample jumps >0.6 from **213,252 → 1,381, a 99.35% reduction** (numbers are on the
*unnormalized* raw decode, not directly comparable to the corpus-scan's saved-wav convention, but the
relative reduction is the valid, load-bearing result). This is now the strongest lead from two
independent investigations (mine: population statistics across ~6000 sampled model_matrix clips +
spectral analysis showing a harmonic-distortion-shaped bump, not aliasing; theirs: live training-
trajectory audit + an engineered, measured fix).

**Open reconciliation, not a contradiction:** their report states a "critical threshold" of
σ(z0)>1.25; my own clean-baseline clips in the (unrelated, older, ptm-vs-base-medium) gf2 family
already sit at std 1.6–2.1 and are clean. Working explanation: the threshold is relative to each
checkpoint/training-run's own normal operating range, not a universal constant — their run is a
fresh DoRA r128 on medium-base via this new optimizer; mine were older DoRA-on-ptm checkpoints.
Not yet tested directly.

**A second, higher-LR run (`modular_opt_cubic5_sf_ev_lr3e-4_radbrake08`) crashed** with
`HSA_STATUS_ERROR_EXCEPTION` in `index_elementwise_kernel` (CONTINUITY, 2026-09-21 18:40ish diagnosis,
DM). NOT root-caused (ROCm launches async — the abort names the kernel, not the launching line), but
two things ARE established: (a) input data is clean (all 300 `latents_sa3_subset300` latents scanned,
zero non-finite, max abs 10.73 — the NaN is generated in the model or optimizer, not fed in); (b)
`modular_opt`'s six files have **zero** `isfinite`/`isnan`/`nan_to_num` calls anywhere, and
`newton_schulz_cubic5` divides by `X.norm()` unconditionally — a NaN entering that path propagates
silently with nothing to catch it. **Real bug found and fixed in the same pass (CONTINUITY):** the
loss guard in `ModularDemoAndLossGuardCallback` was NaN-blind — `mean_loss > threshold` is `False`
for NaN in Python, so a diverged epoch fell through to the healthy branch and printed
`"Loss healthy (nan <= 1.0)"` verbatim (epochs 5 and 6 of the crashed run, two epochs before the GPU
actually aborted). Fixed: `diverged = (not math.isfinite(mean_loss)) or (mean_loss > threshold)`.
Landed in `stable-audio-3` commit `f3a4c05` (a whole-file commit under Kim's identity alongside the
rest of the external work — see that commit's message; the fix itself is CONTINUITY's, on record here
since git blame won't show it).

**Also found (CONTINUITY), not yet fixed:** `_escape_velocity_step` (`optimizer.py:668,671`) calls
`.item()` twice per parameter per step — a blocking GPU sync each time. With 684 DoRA tensors that's
~1400 syncs/step, measured at 0.51 it/s — likely most of why the run was slow. Not a correctness bug,
but it makes `--modular-ev` runs unusable as a timing baseline against other optimizers until batched/
removed. **Also:** the `newton_schulz_cubic5` docstring (`lmo.py:99`) claims the cubic5 schedule
eliminates hipblasLt issues on ROCm — false, lines 109/110 (cubic5) are exactly what emitted the
`HIPBLAS_STATUS_NOT_SUPPORTED` warnings in the crashed run's log (benign, falls back to cublas with
the right answer, but the doc claim should be corrected before someone plans around it).

**Next steps (not yet done):** (1) root-cause the actual NaN source in `newton_schulz_cubic5` or the
EV path now that the loss guard can see it; (2) wire a `nan_to_num`/isfinite guard into the LMO path
directly, not just the demo callback; (3) batch or remove the `.item()` calls in
`_escape_velocity_step`; (4) test whether VADD Tier 3 generalizes to the older ptm-family checkpoints
(reconciling the 1.25-vs-1.6-2.1 threshold question above) — `eval/corruption_base_vs_ptm.py` +
`eval/audio_corruption_scan.py` are the tools, `Mantu/sa3_lora_runs/corruption_investigation/` has
the in-progress data; (5) wire VADD Tier 3 into the MAIN inference path (`model.py::generate()`/the
render server), not just the training demo callback — right now it only protects training-time demos,
not the actual corpus-render or user-facing generation path.
- Links: `OPTIMIZER_TRAJECTORY_LATENT_AND_DISCONTINUITY_FINDINGS.md`, `checkpoint_analysis_summary.md`,
  WORKLOG 2026-09-21, DM logs `ghost-note.wintermute.log`/`continuity.ghost-note.log`.

### A10 — Pattern-2 DDP incident: FINAL READING (2026-08-21) — fleet arms = 8-replica ensembles
- CONFIRMED three ways: eight LOCAL_RANK:0 (fullft avpaug log), ckpts versioned to -v7 (wfleet
  suomi a45 ep9 = 8 writers), step math (suomi a45 step=12600 @ ep9 = 1260×10 at bs1, no /8;
  fullft suomi 158 st/ep = 1260/(2×4), no /8). Every pre-conversion winning_fleet/fullft_fleet
  arm = 8 INDEPENDENT single-GCD trainings. *(Utilization split by family — corrected per the
  inventory bullet below, propagated back here per W's hygiene rule: DoRA wfleet arms = true
  8-replica, fully utilized; fullft arms = ~1 live replica, 7 died silently at startup =
  1-live-7-idle after all.)*
- **Interpretation rule:** each -vN fat ckpt is ONE replica's coherent model (EMA shadow included);
  a run dir = an 8-seed ensemble of the 1-GCD recipe. effective_batch on these rows is 8× overstated
  everywhere it is quoted. Soup/ensemble material — do not delete, do not treat as one 8×-batch run.
- **Decision (Kim, 2026-08-21):** running arms KEPT (killing trades 10 h of 8-seed ensembles for
  half-trained torchrun restarts with <1 day left). All three fleet sbatches converted to the CSC
  torchrun pattern (f1eaabc); verify epilogue now RUNS the LOCAL_RANK check. Post-conversion
  submits (mirctrl resubmit, suomi T512 twins-if-after-rsync... check per-job) are real DDP —
  confirm per job: LOCAL_RANK 0..7 once each, UN-versioned ckpts, steps/epoch ÷8.
- ⚠️ The suomi T512 twins 21428358/59 were submitted BEFORE the conversion rsync → they are
  Pattern-2 too (= 8 replicas at T512, anchor-clean probs). Same interpretation rule applies.
- **INVENTORY (F via ssh, 11:01 — channel post has the full table):** the four suomi wfleet
  arms COMPLETED with FULL 8-replica ladders to ep19 (118-138G each; 516G total) = the first
  2-D soup material (replica axis × temporal axis; C3 meets C1). avp_s1 partial to ep9 (on-curve
  for Pattern-2 pace, not early-stop); avp_s2/biggoa/mix3 wfleet + fullft biggoa/mix3 = zero or
  ep1-only (cancelled pre-first-write). **CORRECTION to the 8-replica reading for fullft:** version
  counts show fullft arms ran as ~ONE effective replica (mostly 1 version/epoch vs wfleet's 7-8) —
  7 of 8 fullft replicas died silently early (likely load/first-step OOM-class), so fullft
  Pattern-2 arms WERE 1-live-7-idle; the DoRA wfleet arms were true 8-replica. Suomi dirs need
  SLIMMING on LUMI before the purge-deadline pull (G's ops lane).
- **REVISED DECISION (Kim, ~11:00): cancel-soup-restart.** 8×-slower epoch pace beats keeping
  them: all Pattern-2 arms scancelled EXCEPT fullft_avpaug 21422923 (ep15/19, ~2.5 h from a
  complete 8-replica ladder + it's the B9 backbone source). Every cancelled dir keeps its -vN
  replica ladder for soups (C3 material). TORCHRUN RESTARTS: 21429629 wfleet avp s1, 21429630
  wfleet mix3 s1, 21429631 wfleet suomi a45 s1 **anchor-clean** (PROBS_OVERRIDE), + suomi T512
  s1 clean + fullft mix3 (IDs pending). True-DDP pace: suomi ~2.5 h, avp ~4 h, mix3 ~7 h for
  all 20 epochs — finishable inside the allocation. **#68 big-FT (fullft_bigset.sbatch) FLAGGED,
  TWO-WEEK-DELIVERABLE RELEVANT:** same Pattern-2 header → presumed affected, but per the fullft
  correction two entries up, the failure mode to check for is 1-live-7-idle (like fullft_suomi/
  biggoa/mix3), NOT the true 8-replica ensemble that wfleet's DoRA arms got — this internal doc
  said "presumed 8-replica" until this line, which was wrong given fullft's own pattern; corrected
  same pass. Not yet checked which one it actually is — do that before trusting any big-goa-set
  checkpoint trained under the old sbatch. lumi-ops skill now carries the hardened authoring rule
  + 3-check verification.

### B10 — Subspace-weighted trainer at K=24, four corpora (Kim direct 2026-08-21) — **suomi+avpaug+2 more COMPLETE or near (16:13: 2/4 still running: biggoa/bigmix)**
- Continues the v3sel lane past its K=12 max: same 15-dim whitened-CSP melody basis, K
  (=--subspace-loss-weight) doubled to 24. Arms: avpaug / suomi (ratified probs) / biggoa /
  **bigmix** (bigset+old-goa — FLAC upweight by inclusion). Lane conventions kept so the K axis
  stays clean vs k2/5/12 + lreq (dora-rows r128 α128, T512 beat-aware, AdamW CONSTANT LR);
  Kim's overrides: lr 8e-5, bs8/rank torchrun DDP (eff 64 vs the grid's 4), 64 ep, ckpt every 8.
  Baselines: subloss_v3sel_k12 (goa) + the per-corpus A11 arms (K=1 at matched DDP).
- Prior-lane status for the "did the earlier test get buried?" question: NOT buried — the
  k2/5/12+tgate grid trained to ep19; the tgate arm's missing renders were caught by F's
  coverage audit and landed today (240 cells, 21431365). Whole quartet awaits Kim's ears +
  melody_wall_analysis.
- ⚠️ bigmix/goa preflight requires latents_sa3 .json metas on scratch (rsync from local);
  submitted into the flash-metadata storm — expect slow staging until the mirctrl hang clears.

### D16 — Where is the TEMPORAL CEILING of trajectory guidance? — **PLANNED, not started (C, 2026-08-28)**
**Why it exists.** Two measurements bracket the answer and nothing fills the gap:
⚠ **PREMISE CORRECTED 2026-09-03 (C).** This entry was written against D15's FIRST, RETRACTED number and its framing has not caught up: D15's revised verdict is that note-level timing **DOES** transfer — `true−shuffled +0.100` melody F1, 6/6 positive, sign test p=0.016, measured by MuScriptor transcription. The `+0.022 n.s.` below came from the chroma screen that could not separate "adopted the key" from "followed the melody", and it is exactly the audit-the-instrument case. The gap D16 probes is therefore NOT "does timing transfer at all" but **how FAST a trajectory the control can still follow** — the ceiling between note-level (which works) and the latent Nyquist. Re-scope before running. Original text follows:

D15 found note-level timing does NOT transfer (`true−shuffled +0.022`, n.s.), while the
`target_raw` probe (MASTER §5, 2026-08-28) found a slow ~0.30 Hz pulse DOES, phase-locked
(+0.492 vs −0.031 baseline; the antiphase arm tracked antiphase, ruling out a density artefact).
So trajectory conditioning works somewhere between "arrangement" and "bar" and we do not know where.

**Why it matters beyond curiosity.** It decides what a Stage-1 trajectory generator should be
asked to produce (Kim's two-stage idea, 2026-08-28) — density envelopes and section structure, or
actual rhythm. Building Stage 1 before knowing this is building against an unmeasured ceiling.

**How to run.** One axis, ~6 cells, `eval/sweep_run.py` — a preset with a `target_raw` onset pulse,
sweeping the pulse PERIOD from ~8 beats down to ~1/4 beat (≈0.3 Hz → ≈10 Hz, the latent Nyquist at
10.77 fps is 5.4 Hz, so the fast end is expected to fail and that bound is itself worth confirming).
Measure adherence exactly as the probe did: run the head on the render's own saved z0, correlate
against the requested curve, and ALWAYS include the antiphase control so density is not mistaken
for alignment.

**Kill criterion / what a null means.** If correlation is flat across the sweep, the +0.492 was
gain-specific rather than frequency-specific and the whole framing is wrong — re-test at several
gains before concluding anything. Owner: unassigned. Cost: ~6 short renders, minutes.

### D15 — Pianoroll notes-lane: does the control steer at INFERENCE? — **DONE 2026-08-26 (C), verdict below**
Follow-up to D13/Q1's in-training control_gain. That measured only that the DiT *uses* the roll
during training; this asks whether the trained control steers a render.

**Setup.** `proll_fullft_t256_bf16_s1` (terminal, fat, local), inlet re-installed on blocks 12-23,
full state dict loaded clean (1045 tensors, 0 missing). Six tracks, each its DENSEST 256-frame
window (~5% density), one seed/prompt, 24 steps, T256 to match the training crop. Four arms:
`true` / `shuffled` (frames permuted) / `foreign` (a DIFFERENT track's window) / `zero` (= the
unconditioned model, since the projection is zero-init). Metric: per-frame chroma cosine between
the roll's pitch-class energy and the render's — crude, screening only.

**VERDICT — REVISED 2026-08-28 after transcription. The control transfers KEY almost totally
AND follows note PLACEMENT measurably. The first verdict below was an artefact of a blunt metric.**

Kim's ear (2026-08-28): "true & shuffle have very identical notes; foreign seems to be in a
different key". Both halves check out, and the second one exposed the problem: the six rolls have
mean pairwise pitch-class-profile cosine 0.29, i.e. every foreign pairing is in a DIFFERENT KEY.
Chroma cosine scores "adopted the key" and "followed the melody" alike, so it could not separate
them. MuScriptor transcription can. Per arm, against the source roll, decomposed:

| measure | true | shuffled | foreign | true−foreign | true−shuffled |
|---|---|---|---|---|---|
| key (pitch-class profile cos) | 0.952 | 0.955 | 0.169 | +0.783 | −0.004 |
| content (pitch-set Jaccard) | 0.875 | 0.857 | 0.533 | +0.342 | +0.018 |
| melody ((pitch,frame) F1) | **0.534** | **0.435** | 0.094 | +0.441 | **+0.100** |

**melody true−shuffled = +0.100, 6/6 positive, sd 0.044, sign test p = 0.016.** Shuffled holds key
(0.955) and content (0.857) essentially equal to true, so that gap is specifically the PLACEMENT OF
THE RIGHT PITCHES IN TIME — the thing the chroma screen reported as +0.022 n.s. and could not see.

**CONSONANCE-WEIGHTED (Kim 2026-08-28: semitone error treats C→C# and C→G alike, which is
musically wrong).** Of 5871 played notes vs the requested roll: **69.5% exact, 30.4% a different
note but INSIDE the roll own pitch-class set, 0.2% outside it.** By interval class to the nearest
requested note: 87.0% unison/3rd/4th/5th-class, 13.0% m2/M2/tritone. So raw precision 0.697
badly understates musical correctness — the model is essentially never out of key; its "errors"
are diatonic substitutions. Caveat: in-key is a generous test if a roll pitch-class set is dense.

⚠ My pitch-blind onset "timing" measure SATURATED (0.795–1.000 across every arm including foreign)
and is uninformative — do not quote it. Same failure mode as the frame-cosine recurrence meter.

Caveats: transcription is itself a model (MuScriptor under-transcribes legato — our own 07-11
finding), melody F1 0.534 is partial not tight, n=6, 24 steps, T256.

**Superseded first verdict, kept because the error is instructive:**

| comparison | asks | mean | positive | sign test |
|---|---|---|---|---|
| true − **foreign** | does it follow THIS melody (pitch + timing)? | **+0.110** | **6/6** | **p = 0.016** |
| true − **shuffled** | does it follow the TIMING (pitch held equal)? | +0.022 | 5/6 | p = 0.109, n.s. |
| true − zero | does conditioning do anything at all? | ~+0.10 | 6/6 | — |

The shuffled arm is the subtle one: permuting frames PRESERVES the pitch-class distribution and
destroys only timing, so true-vs-shuffled isolates temporal alignment — and it is ~0. Against a
foreign roll (different pitches AND timing) the effect is large and unanimous. So the conditioner
is behaving as a harmonic/pitch-set conditioner more than a rhythmic one.

⚠ **A single-track first pass gave true−shuffled = +0.12 and would have been reported as "follows
the roll".** It rested on 20 note-bearing frames (that window was 0.24% dense). With ~255 frames
per track across six tracks it collapses to +0.022. Do not screen a control on one window.

**Caveats:** chroma metric is plain STFT pitch-class, no harmonic weighting and blind to octave;
24 steps; T256 (23.8 s); n=6. Kim's ears are the verdict — wavs kept for audition.

**Open next:** does timing alignment improve with more steps, higher control gain, or the s2 seed?
That is the question that decides whether the pianoroll UI should promise rhythm or only harmony.

### D13/Q1 — BURN-DAY WAVE (allocation expires tonight; Kim: "just start burning the time") — **LANDED 2026-08-21 23:07 (sacct): all arms COMPLETED, only tgate 21439464 + winning_fleet 21429630 still running**
- **Verdict at landing (C, 23:30):** pianoroll control_gain LIFTED OFF and climbs monotonically
  +0.0000 (step 0) → +0.0079 (600) → +0.0116 (1200), true<zero<shuffled — first in-training
  evidence a DiT reads the note roll (1.3 % of loss at T256/16 ep; 8 ckpts per seed). Morph: all 16
  arms printed their Embedding(5/15/77) banner, rc 0 — renders pending. Stacks/showcase/suomift
  below all clean (0 FAILED).
- **Late-wave additions (Kim direct 17:30–17:40), ALL COMPLETED 0 FAILED:**
  - **Showcase 21440170** — 128 random-param t2048/t4096 clips on W's known-good list
    (`lumi/render_showcase.py` + `sbatch/showcase_render.sbatch`; cfg∈{5,7,9}, w∈{0.8,1.0,1.2},
    ptm: 8 steps cfg1; prompt from the 9054 training-caption pool; params+prompt+ckpt in a `.json`
    sidecar, z0 saved). `$SCRATCH/renders/showcase/` = 128 wav. Kim playlist material.
  - **Stack cells 21440457 (+21440202 first pass)** — every adapter of W's list × 3 full-FT
    backbones (avpft90/153, avpaug19 EMA), strengths 0.5/1/1.5 cfg7, via the new
    `render_matrix_cells.py --base-state-ckpt`. 42 combos, **2520 cells** in
    `$SCRATCH/renders/stack_cells/`. Question: how much adapter does a shifted base tolerate.
  - **Stack suomi 21440459** — suomi DoRAs (dorlor adamw/fusion + subloss_k24, last+mid) on
    avpft153/avpaug19/goa-mid, suomi_full_prompts ×3 strengths: 18 combos, **1242 cells**,
    `$SCRATCH/renders/stack_suomi/`. Question: is the suomi idiosyncrasy reproducible at all.
  - **Suomi FULL-FT warm-start 21440462 (avpaug19) / 21440464 (goaft mid)** —
    `sbatch/fullft_suomi_warm.sbatch`, train_lora `--init_state_ckpt` (new; whole-model
    warm-start, EMA-preferred, cov 100.00 % verified on all ranks). T1024 bf16, Fusion + snr row +
    cosine over 32 ep, spectral WD 0.2, subspace v3sel K=5, EMA. 8 ckpts each (every 4 ep),
    `$SCRATCH/runs/suomift_warm/`. NOT rendered yet — next: render both ladders on
    suomi_full_prompts and compare against the stack_suomi cells (adapter-on-FT) and B8's T512
    DoRA: does suomi need the whole backbone to move?
- **MORNING WAVE 2026-08-22 (end date confirmed 23 Aug on the web UI; 169 node-h left ≈ 3.5 nodes
  continuous):** 21445516 `suomift_render` (both warm-start ladders + bare backbones, 414 cells →
  `renders/suomift_warm/`); 21445517/18 `pianoroll_fullft` EPOCHS=32 seeds 1/2 (gain was still
  climbing at 16 ep; same run dirs, overwrites the 16-ep names); 21445586 `morph_render`
  (`lumi/render_morph.py`: 16 arms × 8 real contour crops × {g1, g2, null} + decoded reference
  windows → `renders/morph/<arm>/`). Still queued (Priority) at 23:50. **A11 seed-2 factorial FIRED 23:58: 21445664–679** (4 datasets × 4 arms, ~48 node-h,
  runs `dorlor_<ds>_<arm>_r128a45_t256_bf16_bs128_s2`); 21445634 = a bare ARM-less submit, dies at
  preflight, ignore. Showcase wave 2 FIRED 00:02: **21445701** (`WAVE=2 RNG=20260822` → `renders/showcase2/`,
  128 fresh draws). K∈{8,16} fill ×4 still unfired.
- **PULL LIST (scratch persists till purge, not urgent):** showcase/ (128 wav+z0+json), stack_cells/,
  stack_suomi/, suomift_warm/ (EMA weights only — prune optimizer first), pianoroll_fullft/ (both
  seeds + control_ablation.jsonl), morphcond run dirs.
- **Morph-contour conditioning, FIRST TRAINING of the D12 stack (the "one actually new idea"):**
  21439456 = pitch-contour alphabet bracket (L2/L3/L4 = 3/13/75 K&P symbols from the f0 melody
  line, base vs fullft-avpaug-ep19 backbones, + L3 seed pair); 21439457 = IOI-RHYTHM contour
  bracket (Q1 — onset-interval contours, base/ft × 4 seeds). Head-B path, vocab-parametrized
  (5/15/77), sidecars build_morph_streams.py (5390 crops each; voiced-stride-4 grid, tol 0.5 st;
  IOI: p95-gated onsets, log-IOI, tol 15%).
- **Piano-roll notes lane (Kim direct): 21439467/68** — T256 FULL-FT conditioned on the
  MuScriptor MIDI piano roll (128-ch velocity/64 at latent rate, crop-sliced) via the B7 modular
  inlet; AdamW+WSD, EMA, control-ablation meter every 200 steps (control_gain = does the model
  use the NOTES). build_pianoroll_ctrl.py, 5400 rolls. ⚠ duplicate second submit pair to be
  scancelled (same run dirs).
- **Gate-mode A/B: 21439464** — subloss k5 tgate mode=DEFICIT ×2 seeds + r2/flat seed pairs
  (the untested gate direction after r2 lost to flat in the B2 readout).
- Plus the earlier burn lines if fired: A11 seed-2 factorial ×16, K∈{8,16} fill ×4, mirctrl
  resurrection ×8. All runs ckpt every ≤2 epochs — partial death at allocation expiry is priced in.

### B13 — Does a MIDI melody axis separate what PQ and CE cannot? — **PLANNED (G, 2026-09-10)**
- **The finding it rests on (measured, 146 transcribed clips):** split by whether MuScriptor found a lead
  voice at all, and ask what our existing metrics see —

  | metric | no-lead | lead | d | z |
  |---|---|---|---|---|
  | pq | 7.956 | 7.927 | −0.10 | −0.61 |
  | ce | 6.676 | 6.782 | +0.22 | +1.27 |
  | crest | 4.058 | 4.744 | **+0.45** | **+2.62** |
  | flatness | 0.021 | 0.026 | +0.31 | +1.83 |
  | hf_ratio | 0.013 | 0.013 | 0.00 | 0.00 |

  **Whether a render contains a melody at all is invisible to PQ and CE.** Only crest partly sees it (a lead
  adds transient peaks). Since the project's standing read is that engaging melodic content is what separates
  a top rating from a merely well-produced clip, a metric set blind to melody structurally cannot model that
  judgment — a mechanism for the 4-vs-5 gap, not another failed correlation.
- **Substrate exists:** `eval/midi_metrics_ingest.py` folds the transcription features into
  `clip_metrics.db` as a separate `midi_metrics` table keyed by `path` (146 rows, all joinable);
  `eval/hook_eval_renders.py` produces them and re-scores from saved MIDI on CPU, so metric changes cost no
  GPU. Runbook §12b.
- **⚠ COVERAGE IS THE TRAP:** `has_lead`/`n_lead` are defined for every clip, but the melodic features
  (hook_melodic_ratio, contour_compression, top_motif, distinct46_grid_ratio) are NULL on ~66% because 40%
  of renders have NO lead voice. Averaging one over a mixed set averages over "no melody" as if it were
  missing at random. Any null from these metrics must be read against that before it is believed.
- **Test 1 (cheap, decides the axis):** transcribe the clips Kim has ALREADY RATED and ask whether lead
  presence / hook_melodic_ratio separates 4 from 5 where PQ and CE do not. Power bound from the ratings
  work: at n5=154 only d≥0.26 is detectable, so a null here is only informative for effects that large.
- **Test 2 (the hint worth resolving):** all arms share the same 12 prompts and seeds, so lead presence is
  PAIRABLE. `fullft_ladder_C_dual` vs `B_autoscale` at ep39 is **5–0 discordant** (exact McNemar p≈0.06),
  `A_control` vs `B_autoscale` 4–1 (n.s.) — a hint that the autoscale arm drops the melodic lead more often
  than its ladder siblings, at n=12 pairs which cannot establish it. Per-checkpoint rates run 5/12–10/12
  with almost fully overlapping Wilson intervals. **Cheap next step: more prompts on those three
  checkpoints, not more analysis of these twelve.**
- **Kill criterion:** if lead presence does not separate rated 4s from 5s AND the ladder pairing does not
  reach significance with a larger prompt set, the axis is orthogonal-but-useless and we stop mining MIDI
  for taste.


## C. Soups, EMA, checkpoint selection

### C1 — Temporal soups of the healthy ladders, rendered T256+T1024 cfg7/w1, scored — **DONE 08-21 (G)**
- 246/270 clean first pass, 24 SIGKILL-retried clean. Published to `dora_table` (11 scoped `score_and_publish.py`
  runs). Soups: `Mantu/sa3_lora_runs/soups_ladder_2026-08-19/`. Verdict feeds C2.

### C2 — Quality-weighted soups (PQ × crest × whitening per epoch) — **DONE 08-21 (G) — NUANCED, not a clean win**
- 7 quality-weighted soups (fp32cmp×3, winning×4) built via Kim's PQ×crest×(-flatness) z-score formula,
  rendered+scored (42 clips). **Does NOT consistently beat uniform/profile averaging** — competitive,
  sometimes wins one axis (PQ or crest) but rarely both; e.g. `winning_avp_a128` quality 8.00/4.18 vs
  ladder-best `bell_late` 8.07/3.84; `fp32cmp_goa_t4096` uniform edges quality on both axes. Real, separate
  finding: `winning_avp_a128` (PQ ~8.0–8.07) vs `_a45` (PQ ~7.6–7.8) is a genuine alpha-scaling tradeoff
  (brighter/cleaner vs dynamic range), not noise. **Open: Kim's ears** — PQ/crest may be missing what makes
  quality-weighting sound better even where the metrics wash. Bug found+worked-around: soup renders never
  saved `z0.npy`, so `score_and_publish`'s latent-sanity gate correctly refused rather than silently passed;
  `--skip-sanity` used deliberately (DSP crest/flatness substituted, not a bypass) — future soup-render
  scripts should save z0 too.

### C3 — Post-hoc power-EMA logging in train_lora (EDM2 §3) — **PLANNED (small); LIVE TEST READY (C, 08-21)**
- Two power-function EMAs snapshotted during training reconstruct ANY EMA length post hoc; trivial for
  adapters. Makes every future run fully souprable; supersedes hand profiles.
- **Live test of the same hypothesis, using A10's accidental 8-replica ensembles rather than
  waiting on the logging feature:** G's ear-driven quality table found `wfleet_suomi_a128` has a
  real whitening/disintegration signature (HF ratio 0.23, ~10× the clean controls) while `fullft_*`
  scores clean — C's mechanistic read: the clean rows are EMA-rendered, the broken rows are
  unaveraged single-replica terminal checkpoints from a constant-LR random walk (A1's finding,
  now showing up by ear). `replica_soup.py` + `replica_soup_render.sbatch` (`6c40038`) built:
  per suomi arm, mean-of-8-replicas @ ep19 + an ep11-19 replica×temporal grand mean, rendered on
  the same 6 prompts as G's cells for direct A/B. Answers "does replica-averaging cancel the
  disintegration" using data nobody planned to buy. Ready pending one rsync + Kim's submit; score
  with the same pipeline when it lands — full quartet: single-replica / replica-soup / grand-mean
  / fullft-EMA, one page. Zero further compute planned on `a128` outside this test (agreed, C+G).

### C6 — PT&rarr;base soup: can "punchy" be rewound without rewinding "always the same"? — **DONE 09-07, NEGATIVE (Kim's ears)**

- **VERDICT (Kim, 2026-09-07, after listening to all 48).** *"only the alpha .5 is listenable, and
  even that has artifacts... it's evident the mixing just degrades the sound."* **PT does not blend
  with base.** The answer to the original question is that the ladder cannot ask it — there is no
  usable intermediate model to judge, so "punchy vs always-the-same" stays untested by this route.
  **Do not rebuild this ladder.**
- **What that invalidates, and it is worth understanding before trying anything similar.** The whole
  arm rested on PT being a FINE-TUNE of base, hence one trajectory, hence the linear-mode-connectivity
  regime where weight averaging is known to work (unlike the independently-trained soups of C1/C2).
  That reasoning is falsified: **post-training moves the model out of the regime despite being a
  fine-tune.** Weight-space closeness (997 of 1019 tensors identical, median rel delta 0.0013) did
  not imply blendability.
- **And it retro-explains the measurement.** The blends are DEGRADED, not interpolated &rArr;
  `soup_descriptors.py` was reading **artifact spectra, not a mixture**. That is why the two samplers
  gave opposite verdicts about the same 48 `to_local_embed` biases: degradation has no reason to be
  consistent across sampling objectives. The euler/24 cell where both blends fell OUTSIDE the
  endpoint range was the tell, and I read it as a manifold property instead of a broken model.
  **Lesson: "between the endpoints in descriptor space" never implied musically between them** — the
  self-gate proved a descriptor could SEE a difference, never that the difference was musical.
  A listenability check on one clip would have closed this before any of the measurement was built.

- **Why.** Kim 2026-09-06: the post-trained `medium` "gets some things right, like a coherent,
  punchy sound. it also always sounds more or less the same with the kick, bass and
  percussions." Those are the same post-training pass. This asks whether they separate.
- **How.** `eval/soup_pt_ladder.py` builds `W = base + alpha*(PT-base)`; `eval/render_soup.py`
  renders a blend dir (or, `--endpoint {base,pt}`, an unblended endpoint) at fixed seed 1234,
  cfg 7, 20 s, 3 prompts x steps {8,24} x sampler {euler,pingpong}.
  Arms: `ptm_a050` (global alpha=0.5) and `ptm_local000` (alpha=1 EXCEPT the 48
  `to_local_embed.*bias` tensors held at base -- the biggest movers, per the 997-tensor diff:
  median rel delta 0.0013 but MEAN 0.0215, MAX 0.714, i.e. concentrated not small).
- **&#9888; The two endpoints do not share a sampler.** `medium` is
  `diffusion_objective: rf_denoiser` (native **pingpong**); `medium-base` is `rectified_flow`
  (**euler**); and a blend loads medium-base's CONFIG whatever its alpha, so every blend samples
  as rectified_flow. Both samplers are rendered for every arm; compare only WITHIN a sampler.
- **Result (`eval/soup_descriptors.py`, all 48 clips, n=3 prompts/cell -- directional, not
  established).** The script self-gates: a descriptor is reported only if it separates the
  endpoints by more than the within-endpoint prompt spread. **9 of 16 cells came back MUTE.**
  - **&#9888; LOCALIZATION IS UNRESOLVED -- the two samplers disagree about the same 48 tensors.**
    | cell | descriptor | `ptm_local000` | holding the 48 biases at base recovers |
    |---|---|---|---|
    | euler / 8 | `hf` | 91% toward PT | **9%** |
    | pingpong / 24 | `flatness` | 13% toward PT | **87%** |
    | pingpong / 24 | `zcr` | 12% toward PT | **88%** |
    Under euler the biases look nearly irrelevant; under pingpong they carry almost the whole
    effect. *(An earlier version of this entry, and commit e510144, asserted the euler/8 reading
    as the finding -- "the rewind is not localized". That was one cell generalised to the whole
    question, written before the pingpong side existed. Corrected 2026-09-07.)*
  - **Why they can legitimately disagree:** NEITHER table is a clean weights-only comparison --
    in the euler table PT is off its native sampler, in the pingpong table base is. Each is
    "both models under ONE model's objective". `to_local_embed` sits in the local-conditioning
    path, so a bias there plausibly matters differently under a different denoiser objective.
    Testable; not settled at n=3.
  - **What does hold:** alpha=0.5 interpolates MONOTONICALLY wherever a descriptor is readable
    (+0.35, +0.67, +0.46 -- always between the endpoints). And at **euler/24 both blends land
    OUTSIDE** the endpoint range (flatness -0.19 and +1.39) &rArr; linear weight interpolation
    does not stay on the audio manifold there.
- **Kill-criterion / what would settle it.** No metric here scores "punchy but varied" -- the
  descriptors can only say whether a blend interpolates. The verdict is Kim's ears on
  `eval/build_soup_page.py`'s same-playhead page. If tighter and more-generic move together at
  every rung, they are one knob and the trade is unavoidable; if one moves faster, there is a
  setting worth having.
- **Gotcha for anyone re-running.** pingpong fragments the allocator far worse than euler and
  OOMs all 4 arms on a 16 GB card; `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` alone
  fixes it (0 &rarr; 3 writes on the minimal retest). Renders also segfault at *teardown* after
  all files are written -- the exit code lies, count the wavs.
- **Artifacts, and what was deleted (Kim 2026-09-07, after the verdict).**
  - **KEPT** — `/home/kim/evals_aac/soup_rewind/`: all **48 wavs** + per-clip JSON, `index.html`
    (both sampler tables, same-playhead), `descriptors.json`, and the two `BLEND.*.json`
    provenance records + the render scripts, copied out of the blend dirs before they went.
    Kim's call: "delete the soup weights, leave the clips for now" — the clips are the evidence
    for the negative, and re-rendering them costs GPU time the verdict does not justify.
  - **DELETED** — `/run/media/kim/Mantu/soups/{ptm_a050,ptm_local000}`, 8.59 GB each, **+17 GB
    freed** (Mantu 91 GB &rarr; 108 GB after `sync`; btrfs accounts asynchronously, so the first
    `df` still read 91 GB and looked like the delete had failed).
  - **Regenerable**, which is why deleting was cheap: `eval/soup_pt_ladder.py` rebuilds either
    blend from `medium` + `medium-base` in minutes, and `BLEND.json` records the exact alpha,
    targeted regex and tensor count. Only `/run/media/kim/Mantu/soups/*.{log,sh}` remain.

### C4 — cfg-dependent optimal soup/EMA length — **POTENTIAL (test on C1's boards)**
- EDM2 Fig 6: optimal EMA ~13 % no-CFG vs ~2 % at cfg 1.4 → Kim's cfg7 vs cfg16 cells plausibly want
  different soups. Render both cfgs for the same soups and compare.

### C5 — Spectral-repair probes (remove/keep top-1 direction of a broken arm) — **DONE, awaiting Kim's ears**
- `eval/spectral_repair_lora.py`; 6 rendered sets under `lumi_runs/analysis/task_vector_gram_goa_2026-08-18/renders/`.
  DSP pre-read: removing top-1 restores brightness, not punch; the spike is LoRA-structure, not the pathology.

### C7 — Re-render `fullft_avp_regsweep` + `fullft_avp_surgical` from the ONLINE weights — **PLANNED (G, 2026-09-10)**
- **Question:** did the surgical/regsweep levers actually differ? **We have never heard them.** Both sbatch
  scripts train with `--use-ema --ema-beta 0.9999` AND render their in-job auditions with `--use-ema`
  (`fullft_avp_{regsweep,surgical}.sbatch:166-167`). At beta 0.9999 the half-life is 6931 EMA updates, and
  with `BS=2`, no accumulation, updates = steps:

  | ckpt | updates | half-lives | EMA still BASE |
  |---|---|---|---|
  | ep4 step2990 | 2 990 | 0.43 | **74%** |
  | ep9 step5980 | 5 980 | 0.86 | **55%** |
  | ep14 step8970 | 8 970 | 1.29 | 41% |
  | ep19 step11960 | 11 960 | 1.73 | 30% |
  | ep24 step14950 | 14 950 | 2.16 | 22% |

  So every audition of these two sweeps was substantially a render of `medium-base`. "All the arms sound
  alike" is the EXPECTED output of that setup and is not evidence about the levers.
- **Why it is recoverable:** the checkpoints carry BOTH weight sets. Verified directly on
  `surgical_anchor` ep14 (LUMI, mmap load): `state_dict` prefixes `{diffusion: 997, diffusion_ema: 523}` —
  **522 online tensors** (`diffusion.model.*`) and 523 EMA, and they are not the same tensor
  (`to_cond_embed.2.weight`: online norm 94.80 vs EMA 98.47, cos 0.9977). The LUMI prune keeps the whole
  `state_dict`, so slimming does not endanger this.
- **THE BLOCKER, and it is the real work: arm identity is LOST.** All 21 + 22 checkpoints of these two
  sweeps sit in ONE anonymous `<run>/version_None/checkpoints/` pile — the eight per-GCD arm processes all
  wrote to the same Lightning default dir, so `-v1..-v5` is ARM COLLISION, not epochs. `epoch=9-step=5980-v3.ckpt`
  could be any of {anchor, wd0p1, force_scalar, cmuon, x0, SURGICAL, hyperball, adamw_2e4}. Only 3+5
  checkpoints survive under properly-named per-arm dirs (`regsweep_anchor` and `surgical_anchor`, ep4/9/14).
  They were found 2026-09-09 inside an unrelated project's folder,
  `/scratch/.../film_grain/renders/lumi/` — nothing scans there, which is why they were invisible.
- **How:** (1) identify arms by probing weights (each lever has a signature — `force_scalar` leaves output
  projections off the spectral path, `hyperball` retracts, `adamw_2e4` is a different optimizer entirely;
  a per-checkpoint weight-norm/latent-std fingerprint against the anchor should separate them);
  (2) render the identified set at cfg7/w1 with **`--weights online`** — note both
  `model_matrix_gen --weights auto` AND `train_lora --init_state_ckpt` PREFER the EMA shadow when one
  exists, which is precisely the trap that produced the original nulls; (3) read the latent-std table the
  sweeps were designed around, then Kim's ears.
- **Kill criterion:** if the online-weight renders are ALSO indistinguishable across arms, the levers
  genuinely did not differ at these epochs and both sweeps are closed — but that verdict cannot be reached
  from the EMA renders, which is the whole point.
- **Cost:** the LUMI prune (running 2026-09-09) takes these from ~1.41 TB to slims; a keep-set of terminal
  + one mid per identified arm is then affordable against 393 G of local space.


## D. a2a, guidance, sampling

### D1 — SDEdit survival curves: temporal phase vs TIV vs t_s — **PLANNED (afternoon, existing a2a machinery)**
- **Why:** decides where the "keep vs regenerate" band split goes for a2a (WaveFreqAnchor 2608.06717 read as
  the real-world branch). Reuses `eval/a2a_fulltrack.py` / breathing_a2a. Doubles as a trajectory-level check
  of rhythm-is-noise-invariant (beat R² .80 at L14).

### D2 — Wave operator on WHITENED chroma planes: gesture separation offline — **PLANNED (hours, CPU)**
- Three (128,T) planes, circular pitch, padded time; 1 bin/frame ≈ 1 st/s ⇒ v_pitch/v_time selects glide
  rate (pads ~1 st/s, goa 16th arps ~37 st/s). Does the response separate pad/glide/arp on reference
  chromagrams? If yes → `L_wave` on the air band as a guidance term (mid gated on E1/E2).

### D3 — Temporal-phase anchoring (MWFI port) as a sampler callback — **GATED on D1**
- Keep the reference's timing/groove (phase of the TEMPORAL FFT of the latent trajectory — NOT waveform
  STFT phase), regenerate content; soft / reduced-coordinate / low-temporal-frequency to stay on-manifold.

### D4 — Directional prior / aversion in the optimizer step (Kim's "prefer good directions") — **GATED on C5 listening**
- Positive half buildable three ways (warm-start from soup; anchor toward soup; `U += λ·P_good U` after NS5).
  Aversion to the "failure direction" NOT yet justified (it is present in healthy runs too; render probe
  says it carries dulling). Gate: if `01_remove_k1` sounds better than `00_bad_terminal` → an aversion arm.

### D5 — Adaptive (curvature-equidistributed) sampling grid for base renders — **PLANNED (cheap, local)**
- 2608.15103 §5.2: equidistribute √(local growth); we render base at 16–50 steps everywhere, so it applies
  board-wide (their numbers: −7…−16 % discretization error at N=16–64). Pilot-estimate growth along the
  path, √-quantile grid into `build_schedule`; A/B at 16/24/32 steps, PQ + ears. Sharpens, doesn't add melody.

### D7 — Local anisotropic smoothness term on the level-invariant chroma readout (Garain 2608.05696 assessment) — **POTENTIAL, GATED on D2 + a working melody head**
- From an external assessment Kim relayed (08-19, pre-review flag): the only transferable piece of a
  math.AP mixed local+nonlocal elliptic paper is the ENERGY DECOMPOSITION. Build only the LOCAL term:
  per-band circular-pitch norm on the TIV-normalised readout output (raw chroma has no per-frame norm →
  ‖Δc‖ measures loudness), computed onset mask ρ_t (MIDI + d/dt X[0]), strength = measured R²(t).
  **Do NOT build the nonlocal term as minimisation — it is the loop attractor as an objective**; the
  recurrence-MATCHING reformulation = the anti-loop R(z) framing (`inference/recurrence_potential.py`
  is the existing primitive; A_ts / SSM / CC half-matrix / RQA / persistent H¹ are one object).
- Overlaps: `control/sa3_control/contour_loss.py` (the n-ary/contour dial), the chroma-loss zoo; the
  wave operator (D2) on the same planes is the stronger oriented prior — this is its isotropic special case.
- Experiments if ever: E-A (with/without, air only) is the falsifier. Pointer in papers/Prospective.

### D8 — Does the melody readout direction ROTATE with noise level? (per-t refit of the linear chroma readout on z_t, per band) — **POTENTIAL (fold into `eval/melody_r2_vs_t.py`)**
- From an external assessment of Liu & Purohit 2608.04970 (08-19). **Scope correction (C):** the #59
  preconditioner, the `P_melody` schedule projector, `E(W_c z)` and readout-space guidance all act on
  x̂₀|t / the target space, where the clean-latent melody basis is fixed by construction — only SALIENCE
  varies with t, and the R²(t) gate (B2) already handles that. Rotation matters only for things that read
  z_t DIRECTLY (the LatCH heads, t-injected for exactly this). So: measure it as a fact about the noised
  marginal — per-t ridge refit of the linear readout, per band, principal angles between row spaces,
  singular-value floor + conditioning reported — an hour on the R²(t) forward path; the per-σ layer×feature
  R² maps (`latch/probe_layer_feature_map.py`) are most of it already.

### D9 — Do melody and timbre controls COMMUTE? (Lie-bracket test ↔ SFD's premise) — **POTENTIAL (cheap)**
- `exp(εv_mel)∘exp(εv_timbre)` vs reverse order with existing steering vectors / adapters; a nonzero bracket
  + one ordering better = SFD's "semantics lead" premise holds on SA3. Note: circulation/conservativeness
  tests are trivial for gradient guidance (∇L is conservative by construction) — only meaningful for
  non-gradient controls (adapters, concept directions, Head-B). After the deliverable work.

### D10 — Intermittency of melody formation (X1) — **PLANNED (fold into `eval/melody_r2_vs_t.py`)**
- From the Carbone/Servidio 2607.14796 assessment (08-19): record ‖Δĉ‖ per adjacent denoising step
  (ĉ = W_c·x̂₀|t) across samples; report kurtosis/tail exponent per band and whether heavy steps cluster
  in t. HEAVY-TAILED ⇒ melody forms in a few crucial updates ⇒ upgrade the R²(t) gate (B2) from a
  salience curve to an event-weighted one; GAUSSIAN ⇒ closes the thread cheaply. Same forward loop as
  the R²(t) measurement — third use of one tool. Afternoon.
- X2 (pair dispersion) deferred with its fix recorded: measure in READOUT space normalised by the
  trajectory-wide contraction, else it re-measures the sampler. X3 (interaction topology / forbidden
  zones: block melody↔timbre channel communication per block) BLOCKED on signed differential attention
  + the 64 memory-token hubs; the transferable claim is network-science (cite pruning/sparsification,
  not turbulence). "Phase-transition threshold" in the paper is hedged conjecture over 5 confounded
  runs — do not let it travel unhedged.

### D6 — Stabilisers for readout-space guidance — **READY (one-liners)**
- Soft-clamped normalised gradient; stop-late from OUR R²(t); per-band reliability weights from Tier-2.

### D11 — Frame-shuffle null on Tier-2 air — **DONE 2026-08-21: ~half fingerprint, half temporal — kill-condition does NOT fire**
- **Verdict (n=1200, 5 perms, 5 derangements; `eval/musicology/same_chroma_D11_frame_shuffle_2026-08-21/`):**
  per-window znorm median matched / shuffled / null → fingerprint fraction: bass 0.323/0.248/0.136
  → **ff 0.60**; mid 0.449/0.345/0.220 → **ff 0.55**; air 0.526/0.401/0.266 → **ff 0.52**. So ~half
  of the matched-over-null identity signal is a static per-track chroma shape, ~half is temporal.
  Air is NOT fingerprint-dominated (ff 0.52, not ~1), and its ABSOLUTE temporal component
  (matched−shuffled = 0.125) is the largest of the three bands — the head does read time-varying
  chroma, most strongly in air. Band scoping stands; but any claim quoting the corpus-demean 0.918
  as "melody" must be halved in spirit: report the shuffle-surviving share alongside it (their "0c"
  reporting note, now with numbers). Scorer self-test caught its own trap: a random-walk synthetic
  is autocorrelated (= a drifting fingerprint) and survives shuffling — independent frames is the
  correct known-answer. Schema drift fixed en route: muscriptor_full stats.json lost
  source_path/start/end since 08-12; they live in index.jsonl now (merged per id; E2 reruns need
  the same patch). Durable caches: tier2_predicted/ (all 5400 by end of run) + e2_fold12_cache/.
- *(original gate, for the record)* — was GATED on 1 GPU-hour
- **Question:** is Tier-2's air 0.918 melodic content or a static per-track spectral fingerprint
  (mastering EQ / codec lowpass are track-constant and land in air)? Frame-shuffling within track
  preserves the fingerprint and destroys melody — if 0.918 survives, the band scoping is aimed wrong.
- **Partial evidence already in hand:** `same_chroma_E2_perwindow_norm_2026-08-12` — per-window z-norm
  keeps matched > null (air 0.526 vs 0.266), so temporal structure carries identity beyond
  window-local statics; but a constant chroma SHAPE survives per-window norm, so the shuffle null is
  still the sharper test. **How:** regenerate the 1200 tier-2 predictions (predict_head.py, 1 GPU-h —
  cache them somewhere durable this time, not tmpfs) + a 20-line shuffle variant of
  `score_e2_perwindow_norm.py`. Their "0c" (band-weight confound: air is trained 4–6× harder) is a
  reporting note to attach to the same result.
- **Closed items from the same external queue (they could not see our repo):** their item 1
  ("the make-or-break guidance listening test, never scheduled") RAN 2026-07-22 — chroma
  melody-turning probe NEGATIVE 0/12, authority ~10× short → guidance route closed, conditioner route
  (Head-B → prepend → SFD/B4) is the live lane. Their E1-stems and E2-perwindow both have result dirs
  (2026-08-12). Their provenance warning about Tier-2 is wrong (full harness + results.json exist).
  Their 0a kill-condition cannot fire: our P_melody is the v3 CSP basis, rank 15/256 by construction.

### D18 — Morph conditioner with a REAL LR schedule: warmup → hold → cosine — **TRAINED, NOT YET EVALUATED (local, 2026-09-10 03:34 → 10:30 EEST, W; entry written by C from W's run_meta at W's request; status corrected 2026-09-24)**

*Outcome (2026-09-24, W, from the run dir):* ran to completion — all 24 checkpoints (step 500…12000) plus `riffer_final.pt`, finished 10:30 the same morning. **The schedule fixed the instability:** gnorm max **0.268** over 600 logged samples, never above 2 (D17's worst bin median was 2.718), so the watchdog never fired and the first kill criterion is cleared. The post-train ONNX export failed (`onnxscript` missing in that venv) — non-fatal, weights saved. **The second criterion — adherence at 12000 vs D17's step2000 — is UNTESTED: no renders exist for this arm.** So D18 has not yet answered its question; it has only removed the reason D17 could not. Next: the same gain ladder (3/4/6/8) on step2000 / step6000 / step12000.

*Why:* D17 (below) answered its question by failing. Listening put the **only audible contour
correspondence at step2000, gain 2** — ~250 optimizer steps, ~1.4 epochs — i.e. the entire useful
signal sat in the clean stretch *before* the first instability. D18 asks whether that was a
ceiling of the Head-B contour path or merely step-size instability destroying everything after it.

*Arm:* `morph_L3_lion_r128_cos`, identical to D17 except:
- **autoscale OFF** — D-Adaptation is itself a step-size controller; running it under an explicit
  schedule puts two controllers on one knob and nothing would attribute cleanly.
- **warmup 1000 → hold 1000 → cosine 10000** micro-batches (12000 total, ~8.5 epochs), floor 0.
- **save-every 500** (24 ckpts) — D17 saved so coarsely that "somewhere in the first 1.4 epochs"
  was the best resolution available on the thing that actually worked.
Unchanged: corpus (goa + AVP, 5678 crops), K&P L3 vocab 15, medium-base, DoRA r128, Lion 4e-5
betas (0.9, 0.99), wd 0.05, bf16, batch 4 × accum 8 = 32, crop 512 random, EMA 0.999, seed 1.

*Kill criterion:* gnorm sustained above ~2 again, or adherence at 12000 no better than D17's
step2000 — the latter would say the ceiling is the **conditioning inlet**, not the optimiser.
⚠ `--val-frac` / `--early-stop-patience` are INERT in this mode (see the no-op list below), so the
guard is an **external watchdog** on the run's own log: SIGTERM if gnorm stays >4.0 for 10
consecutive samples (~200 micro-batches). 4.0 is deliberately above D17's worst bin median (2.718)
so it cannot fire on a transient.

*Gain ladder, already rendered:* gains 3/4/6/8 on **both step2000 and step4000** of D17.
step4000 is the control — **if the later checkpoint also improves with gain, then what degraded
after 1.4 epochs is achievable STRENGTH, not adherence**, and the schedule is only half the fix.
That is a question the objective A/B can answer and the ear cannot.

*Division of labour:* W owns training + pages; **C owns the measurement** and will run
`eval/morph_contour_ab.py` on D17 **and** D18 so the comparison is a number rather than two sets
of impressions.

**⛔ SIX ACCEPT-BUT-IGNORE FLAGS FOUND IN `sa3_control/train.py` ACROSS D17/D18 — the file's
established failure mode.** It accepts a flag, **echoes it into the run's own sidecar**, and does
not apply it — so the manifest lies and the run looks configured:
1. `--dora-rank` was never optimised under `--optimizer fusion*` (no optimizer state, never stepped).
2. `--smoke` reported `[smoke OK]` on zero evidence (read `p.grad` after `zero_grad`).
3. multi-root sidecars resolved by bare stem — one corpus read the other's contours.
4. `--hyperball` pins zero-init adapters at zero forever.
5. **`--val-frac` / `--early-stop-patience` do nothing outside `fingerprint` mode** (`train.py:794`)
   — D17's `run_meta` kill-criterion was literally "val loss diverging" and val never ran.
6. **`--warmup-steps` did nothing off adamw** (W, `5ee62c2`) — so D17 ran with no warmup despite
   passing the flag, which plausibly contributed to the instability D17 attributed elsewhere.
7. **`--cautious` is silently inert under `--optimizer lion` and `--optimizer adamw`** (C audit,
   2026-09-10) — it is consumed only inside the `fusion*` branch. Unlike `--hyperball`, which
   prints an explicit `IGNORED by lion` line, `--cautious` accepts and says nothing.

**AUDIT DONE (C, 2026-09-10), 74 flags.** A static "never referenced" screen finds almost nothing
— the dangerous class is flags that ARE referenced but sit behind a mode/optimizer gate, which is
invisible to reference counting. (My own screen also produced a false positive on
`--export-onnx-on-finish`, which is read via `getattr` rather than `args.`, so the tool needed
auditing before its output could be trusted — the usual rule applying to itself.)
Per-mode dispatch flags (`--scalar-field`, `--fp-*`, `--metrical-*` …) are legitimate. The
dangerous ones are **flags that read as universal but are silently mode-gated**: `--val-frac`,
`--early-stop-patience`, `--cautious`, and formerly `--warmup-steps`.
**Proposed general fix, modelled on the line that already does it right:** at startup, warn for
every flag the caller passed that cannot reach code under the chosen `--control-mode` /
`--optimizer`. `--hyperball`'s `IGNORED by lion` message is the pattern; the rule is that a flag
that cannot apply must SAY SO rather than be echoed into `run_meta.json` as if it were in force.
Deferred until the card is free — editing that file with a job running against it is how the
next silent no-op gets introduced.

### D17 — Morph conditioner at CAPACITY: Lion + D-Adaptation, r128 joint DoRA, eff-batch 32 — **TRAINED + RENDERED, A/B NEVER RUN (C; status corrected 2026-09-24 weekly)**

*2026-09-24 status (checked on disk, not from memory):* training **completed** 2026-09-09 16:28, rc=0
(`riffer_step2000..16000.pt` + `riffer_final.pt`; the ONNX export step failed on a missing `onnxscript`,
harmless). 418 clip files rendered 2026-09-10 03:39 in `clips/`, **from the EMA weights, whose shadow started
at the zero-init adapter** (KIM-TASKLIST's morph A/B item explains why they under-represent the run; the
online weights are recoverable from two EMA checkpoints, `eval/` tool of 09-11). **The contour A/B was never
run:** no `morph_contour_ab_D17.json` exists anywhere. Verdict: none yet. Next: that KIM-TASKLIST block.
`run_meta.json` status set to done.

*Why:* D12's bracket established that the morph-contour conditioner **can exert some control** —
weak but real. Kim's read 2026-09-09: *"now that the conditioner did something, a model with more
weight in training might bring up something."* The bracket was fusion, bs4 × ga2, and no DoRA on
most arms; this is the capacity/step-size arm of the same question.

*Arm:* `sa3_control.train --control-mode melody_contour`, L3 alphabet (vocab 15), medium-base,
**LionSR 4e-5 + D-Adaptation autoscale**, **r128 dora-rows joint**, **effective batch 32**
(4 × accum 8), bf16, crop 512, EMA 0.999, 12 epochs, val 0.1, early-stop 4, seed 1.
Run dir: `UUID/sa3_control_runs/morph_L3_lion_r128_bs32_2026-09-09` (`run_meta.json` carries the
full recipe, hypothesis and kill-criterion).

*Corpus:* goa `latents_sa3` **+ AVP non-aug**, unweighted concatenation — **5678 crops** (5390 goa
+ 288 AVP, 2814 tracks), AVP a ~5.1% addition. AVP is new to this lane: its f0 existed at track
level for all 170 tracks but had never been resampled into the crop companions, so the melody
filter had been silently dropping every AVP crop. Backfilled with `eval/backfill_crop_f0.py`.

*Kill criterion:* val divergence, or adherence at/below the D12 bracket at matched epochs — which
would say the Head-B contour path is at its ceiling and the next move is a **different
conditioning inlet**, not a bigger adapter.

*⚠ Confound to hold in mind when reading it:* `wd 0.05` is a judgement call (Lion wants a much
larger wd than AdamW at a much smaller lr; the trainer's old hardcoded value was AdamW's 0.01),
so a difference vs the bracket is not attributable to capacity alone.

**Four bugs found while scoping this, all of which fail toward a NULL** (commits `7483945`,
`3b6088c`, `cea23a1`, `e869141` in SAO; `223c7f4` in stable-audio-3; `5d32199` in
stable-audio-tools; `81a9929` in mir):
1. **`--dora-rank` was a NO-OP under `--optimizer fusion*`** — the fusion branch built param
   groups from the adapters + conditioner only, so DoRA tensors got no optimizer state and were
   never stepped. Any earlier `fusion + dora` control arm trained no rank. Fixing it revealed the
   cost the bug hid: `fusion + r128` now OOMs on 16 GB.
2. **`--smoke` printed `[smoke OK]` on zero evidence** — read `p.grad` after `zero_grad`, so it
   reported `0 adapter tensors got grads; mean grad-norm nan` and passed. Every smoke run we have
   ever done passed that way.
3. **Multi-root sidecars resolved by bare filename stem** — goa/`000000.npy` and avp/`000000.npy`
   both read one stream file. Now per-root via `--melody-dirs`.
4. **Hyperball freezes zero-init params at zero forever** (`lora_B` is `torch.zeros`, Head-B
   `to_out` is `zero_module`; R=‖W0‖=0 zeroes both halves of the update). Measured 0.0 vs -0.059
   after six steps. **Do not reach for `--hyperball` on an adapter recipe.**

*Big-goa is NOT in this arm and cannot be yet:* the bigset has latents (12524 crops) and complete
captions but **no f0 anywhere** — its 49-field MIR pack carries `pitch_salience` (a salience
curve, not a melody line) and the bigset crops have no timeseries companions at all;
`muscriptor_full` is 5400 mid+stats = the SMALL goa crop set. Bigset morph conditioning needs a
melodia pass over `goa_archive_stems` (23129 tracks × 4 stems, ~190 G / ~48 G for `other` alone).
⚠ And its full-prose caption tier is the **contaminated** build (300 sampled: 159 techno, 132
industrial, 2 goa) — use the **granite** tier (268/300 goa) or the hinted prose tier.

### D12 — Contour-token conditioning stack (external drafts LANDED in mir; Q1 next) — **READY (code) / PLANNED (Q1)**
- **AUDITION SURFACE EXISTS as of 2026-09-03 (C)** — the morphcond grid was trained AND rendered weeks ago and nobody had listened: 384 cells (16 arms = vocab L2/L3/IOI3/L4 × medium-base/full-FT × seeds, × 8 stems × {off, g1.0, g2.0}) sat on the UUID drive. Page: `eval/build_morph_page.py` → `~/evals_aac/morph_conditioner/index.html`, same-playhead, with each stem's reference clip. **Kim's ears are the next gate.** ⚠ No objective adherence metric has been run on these — the D15 transcription measure (note-cell F1 vs a source roll) has NOT been ported to contour streams, so nothing here is a claim yet.
- `mir/src/conditioners/{morph_grids,contour_codes,contour_streams,contour_stats}.py` + regression
  tests (mir 42c3a83): monotone-invariant K&P dense-rank contour tokens over frame/event grids,
  redundancy judged by CONDITIONAL ENTROPY (agreement provably blind cross-alphabet; nested-L
  H(L2|L3)=0 reproduced in tests). Feeds Head-B/prepend/B4 target design.
- **Q1 (do next, ~10 lines):** an IOI/duration morph stream on the note-onset grid — rhythm is the
  channel the model KEEPS (beat R² 0.80 @ L14); all six current streams are pitch/energy-derived.
- Parked from the same drop: Q3 distance-graded hard negatives, Q4 basis-space interpolation,
  Q5–Q7 (gated on a Phase-B head). Their `measure_contour_codes.py` was NOT in the zip — ask the
  external agent or re-derive if Q2 (min H(A|B) on real audio) is picked up.

### D14 — Cross-prompt a2a bracket at high noise, across model families — **RUNNING (21457563, submitted 2026-08-22)**

**Kim's spec, verbatim in intent:** bracket a2a transformations with noising values **random in
[0.5, 0.9]**; take **T4096 crops** from our datasets; a2a them with **a random prompt taken from
ANOTHER clip** (need not be the same corpus); run at least the **melody-subspace** models, plus
whatever else might help — the **morph** arms, and the **MIDI/pianoroll control** path with a midi
crop drawn from our datasets used as the control.

**RELATION TO [D1]:** D1 is the *measurement* twin — SDEdit survival curves (temporal phase vs TIV
vs t_s), "what survives noising". D14 is the *generative* twin: what the different model families
DO to a real clip when handed a foreign prompt at high noise. Same machinery, same t_s axis,
different question. Extend D1's answer into D14's grid rather than re-deriving the ladder.

**REUSE — DO NOT REBUILD (this lane has already cost us one lost night):**
- **Latent-space a2a already exists.** `stable_audio_3/inference/sampling.py` takes `init_data=`
  (LATENTS) + `init_noise_level=`, and `inference/longform.py:330` already calls it that way. Our
  corpora are stored AS latents, so the whole experiment runs in latent space — **no audio load,
  no SAME encode**. That is the cheap path and it is already proven code.
- `eval/a2a_fulltrack.py` (Kim 2026-07-07): the noise-ratio ladder + 380 s two-window crossfade,
  and the `--noise-levels` interface. `eval/breathing_a2a.py`, `eval/dual_lora_a2a.py`,
  `eval/layered_lora_a2a.py`, `eval/transition_lab.py` for the multi-adapter variants.
- `lumi/render_morph.py` (2026-08-22) for the morph/control path: correct-vocab
  `MelodyContourEncoder`, `install_adapters`/`load_adapter_state`, `ControlContext(ctrl, gain)`.
- `lumi/render_matrix_cells.py` for ckpt loading across adapter / `--base-state-ckpt` / `--fullft`.

**⚠️ TWO TRAPS THAT WILL SILENTLY RUIN THIS RUN:**
1. **The 120 s `generate()` trap** (DISCOVERIES 2026-07-07, and the LUMI 2026-07-22 native-cell
   bug). `generate(duration=)` defaults `sample_size` to 5,292,032 = **120 s**, so a "T4096 crop"
   silently renders 120 s unless `sample_size`/`--frames` is set explicitly. Kim's spec is T4096 =
   380 s; getting this wrong produces plausible audio at the wrong length and nothing errors.
2. **The chosen noise band is exactly where we already know harmony dies.** W, 2026-07-30: *"the
   mid-band a2a loss is the DiT abandoning harmony, not input fragility"*
   (`Misc/latent_noise_fragility.py`). So [0.5, 0.9] is not neutral territory — it straddles the
   band where the baseline is known to drop harmonic structure. That makes it a GOOD bracket (it
   is where a melody-subspace or contour-conditioned model should differentiate from baseline) but
   it means **baseline degradation is the expected result, not a bug** — and the read is the
   DELTA between families in that band, not absolute quality.

**READ / KILL:** the point is family separation in the 0.5–0.9 band. If subspace / morph /
midi-control arms are indistinguishable from baseline there, the conditioning is not buying
robustness under re-noising and the lane says so. Random-prompt-from-another-clip is what makes it
a real test: it forces the model to choose between the init audio and the caption, which is
precisely where a control signal should assert itself.

**SUBMITTED 21457563** — `lumi/sbatch/a2a_bracket.sbatch` + `lumi/a2a_bracket.py`, 8 families
one-per-rank on one node, ~2 node-h of the 111 free. Families: baseline · sub_v3sel_k5 ·
sub_v3sel_k12 · sub_k24_bigmix · a12_warm · a12_warmwsd · a13_fullft_avp · morph_L3_ft(+contour).
Corpora goa/avpaug/suomi/biggoa, 50% of donor prompts drawn cross-CORPUS.

**F'S SWEEP (2026-08-22, read-only) CONFIRMED THE GAPS ARE REAL:**
- **No cross-prompt a2a exists anywhere in this codebase.** `a2a_fulltrack` is one prompt per
  track; `layered_lora_a2a`'s "different prompts" are per-SECTION within ONE track. D14 is the
  first deliberate audio/caption mismatch test.
- **D1 WAS NEVER RUN** — "PLANNED" verbatim, no results. So there is no survival curve, no t_s
  sweep, no numbers: nothing to extend, and **nothing validating the [0.5,0.9] band**. Hence the
  anchor cells.
- **Adapter vs full-FT under re-noising is UNTESTED.** D14's a13_fullft_avp arm against the
  adapter arms is the first data point, not a confirmation.
- **Literature:** *Diffusion Warm Initialization* (2606.18968, DAFx26) locates the SDEdit
  skip-fraction sweet spot empirically on Stable Audio Open (our family lineage) via a
  pitch-Jaccard + FAD sweep. No paper hands us a validated band, but that is a borrowable METHOD
  if we ever want to check Kim's instinct with numbers instead of ears.
- **Census gotcha:** morphcond arms save `riffer_final.pt`, NOT `epoch=N.ckpt` — an `epoch=*.ckpt`
  glob finds ZERO morph arms.

**DELIBERATELY EXCLUDED: the pianoroll / MIDI-control arm, though Kim asked for it.** Its control
enters via the `modular_local_embeds` inlet, and `SDEditReanchor` builds its OWN conditioning dict
(inpaint_mask + masked_input only) — the arm would run **unconditioned while looking like it
worked**. Extending the reanchor conditioning path is the prerequisite; that is the follow-up, and
it is the single most valuable thing to build for the next allocation since it also unblocks any
future control-under-a2a test. *(The morph arm IS conditioned properly — on the SOURCE crop's own
contour over the SAME window, i.e. "hold this clip's melodic shape while a foreign caption pulls
the timbre elsewhere". `a2a_bracket.py` makes a control ckpt without `--control-dir` FATAL for
exactly this reason.)*

### D19 — Whole-track structure conditioning (section / SSM-conditioned form), follow-up to the E3 metrical adapter — **POTENTIAL (Kim direct, 2026-10-15; written up by THE-FINN)**
*(Naming note: "E3" in this entry is the metrical-position experiment of the reality-structured plan, `docs/superpowers/specs/2026-07-31-reality-structured-model-experiments.md`, NOT the LatCH head re-validation E3 in section E.)*
- **What E3-metrical did (07-31 → 08-01):** frozen SA3 medium + DoRA r128 + `MetricalEncoder` (`control/sa3_control/conditioner.py:137`: four embedding tables over subdiv/beat/bar/phrase + coverage/conf → 768-d per-frame tokens → the Head-B cross-attention adapters), `real` vs `shuffled`-sidecar collapse baseline, T512, 15k steps each. Bracket (`eval/e3_structure_bracket.py`, 3 models × 4 prompts × 3 seeds, 47.5 s, constructed 145 BPM 4/4 grid): phrase-return gain real 0.0091 / base 0.0037 / shuffled 0.0009 — the predicted ordering, but small-n and on a saturated chroma scale (all SSMs 0.94-0.99). Checkpoints and clips: `/run/media/kim/Mantu/sa3_control_runs/e3_metrical/` (finals + `bracket/`).
- **Why it is inconclusive, not a failure (Kim 2026-10-15, blind A/B/C listening, `eval/e3_blind_abc.py`: "hard to evaluate ... all had a linear structure"):** (1) the streams are CROP-LOCAL — `bar_in_phrase` counts bars since the crop start mod 8 and `phrase_idx = bar // 8` (`prep_metrical_conditioning.py` documents this as a v1 deviation), so the head learned a bar counter, not musical phrase position; (2) T512 holds <4 phrases and no whole form; (3) goa builds monotonically, and chroma is near-constant on its drones, so "return" barely registers; (4) the used-structure ablation (design doc §4) was never run.
- **Proposal, three levels, all RELATIVE TO THE WHOLE TRACK:** (a) track-relative position: global bar index, fraction of track elapsed, section index and position-in-section; (b) phrase level anchored to real section starts (Foote labels, `Kosmos/section_labels/`, 5,035 tracks; MuScriptor sections exist for only 157 and the two segmenters agree weakly, F@3s ~0.12-0.13, `eval/section_spotcheck.md`); (c) the self-similarity matrix itself as the control: a coarse target SSM (say 32×32) or a drawn form (ABAB + break) as the conditioner, evaluated by comparing the achieved SSM (`eval/structure_ssm.py`: boundaries/min, recall, loop_score) with the target. (c) doubles as a GUI control (draw the form).
- **Cheap tests first (lightweight-first):** (1) **used-structure ablation on the EXISTING E3 adapters** (GPU, minutes, T512): same seed/prompt with the grid shifted by 4 bars, zero tokens, and a BPM-conflict grid (prompt 145 vs grid 130); if the three renders are alike the adapter ignores the signal, so do not build on the crop-local design. Measure by change-points/onset-energy novelty against the bar grid, not chroma. (2) **180 s extrapolation probe** on the existing adapters (render script allows T<2048; the adapters never saw >3 phrases, so this checks extrapolation only). (3) **SSM stability, CPU only:** compute chroma SSMs on the 380 native-length renders (`eval/structure_native.csv`) and real tracks, downsample to 32×32, and check (i) coarse SSMs are stable across seeds of the same prompt, (ii) a coarse SSM can be reconstructed from the Foote section labels, i.e. whether labels carry the same information (if yes, condition on labels; the SSM is then only the evaluation).
- **Kill criteria:** ablation shows no effect and the 180 s probe collapses → drop the metrical-tree retrofit; SSM coarse targets unstable across seeds → fall back to section labels only. **Unverified cost:** whole-track crops (minutes) need T up to 4096; VRAM and step time on this card are not measured.
- **GUI note:** the render server's only control path is scalar FiLM; Head-B/metrical adapters are absent (`docs/INFERENCE-SURFACE.md`). A grid generator (BPM, beats/bar, bars/phrase, offset, gain) is a few lines (`build_metrical_grid()`), the install path for the adapter is the real work.
- **Disk:** the 44 intermediate step checkpoints in `e3_metrical` (~128 GB) are safe to clear; keep both `riffer_final.pt` files and `bracket/`.

## E. Melody head (LatCH f0) and LatCH hygiene

### E1 — Held-out-validated melody head: epoch budget + EMA — **DONE 08-18**
- Both voices generalise (lead .245→.204, bass .191→.152 on 401 unseen tracks); EMA monotone; budget ≈20 ep
  with val-selection. Split BY SOURCE TRACK (every track has ≥2 crops). `latch/summarize_val_arms.py`.

### E2 — AdaGC / decay / (MuonC?) bracket on the melody head at the established budget — **PLANNED (local, light)**
- `train_latch --optimizer fusion --fusion-decay/--fusion-snr` exist; AdaGC needs a small port; EDM2
  forced-norm exists nowhere.

### E3 — Re-validate the 14 production LatCH heads (all were train-loss-selected) — **GATED on Kim's decision**
- Steering authority ≠ held-out regression; energy heads first.

### E4 — Guided-gen eval + disintegration gate for the f0 heads — **PLANNED** (no "works" claim before this).

### E6 — Air-band RMS head retrained under the ModularOptimizer; stability at high lr — **BRACKET + OVERNIGHT DONE 2026-10-15; lr 1e-2 is the ceiling (G)**
- **Why (project owner, 2026-10-14/15):** the production `rms_energy_air` head (AdamW, depth 4, no EMA, 20 ep) glitches at large guidance weights and changes content (onsets, hats), unlike bass/mid/body.
- **Bracket** (`latch/run_air_bracket.sh`, 1000 steps, effective batch 32, Shampoo+SF, Muon on all 2-D, overtraining wd, brake armed after epoch 1, EMA half-life 0.5 ep, depth 8): lr 1e-2 trains
  (dim512 0.0206, dim256 0.0207, lr 1e-3 0.0272, SOAP 0.0212); lr >= 5e-2 DIVERGES in epoch 1 (loss 0.81 vs 0.076) and Shampoo's eigh then fails on the NaN covariance; Mona (Fusion optimiser, no modular port) crashed the same way.
  SOAP is slower (two-sided eigh) with no loss gain. d256 = d512 on val loss and by ear (the air band is a smooth low-information target; SA3 hallucinates the top end anyway).
- **Listening (project owner):** new heads at gain 24000 sound brighter and (nearly) glitch free; the old head at 24000 sounds spectral and artifact-laden. Measured: clicks per 1e4 samples 2.12 (old) vs 0.13-0.20 (new); old loses 0.42 onsets/s vs bass+body.
  CONFOUND: old = depth 4, no EMA, AdamW; new = depth 8, EMA, modular. Optimiser is not isolated.
- **Requested vs realised:** asked bass -10.0 / body -4.3 / air -10 dB; renders land at about -16 / -19 / -24 dB (air); heads pull toward the target, they do not reach it. Air at the training median (-30.3 dB) made the 64 clips DARKER; -10 dB at gain 24000 restores the balance.
- **Overnight (4000 steps = 25 ep, schedules in epochs):** `latch/run_air_overnight.sh` O1-O5: grad clip, halved SF-unchecked window, effective batch 64 at lr 3e-2, three EMA half-lives in one run (O2), dim512 long baseline. SNR gate dropped (it was an lr multiplier in the DoRA ablation).
- **Value x gain grid (A2/A5, 4 seeds):** gain moves brightness more than value does; value +10 at gain 4096 (+0.84 dB air share vs original) is about the same as -10 at gain 8448 (+0.93). No free gain from higher value at lower weight. Realised air -24.5 to -27.8 dB for requests of -10..+10. A2 and A5 behave alike.
- **64-seed punch set (level-matched, mean over seeds, change from original):** bass+body centroid -542 Hz; old air head -10 dB @24k +22 Hz; new head @24k +287 Hz; @32k +390 Hz (overshoots the original brightness). Crest stays 1.5-1.6 below the original in every arm. Click-rate metric is biased by brightness (relative to the signal's own first difference), so it flatters the bright new-head clips; ears and ratings are the judge.
- **Overnight verdict (25 epochs, `--grad-clip 1.0`):** O1 lr 5e-2, O2 lr 1e-1, O3 lr 3e-2 b64, O4 lr 3e-2 b64 early damping ALL DIVERGED to NaN (ep 3, ep 2, ep 15, ep 26); onset moves later as lr falls, early damping and a doubled batch delay but do not cure. O5 (d512, lr 1e-2, 4x length) trained clean, best val 0.0201 vs bracket A2 0.0206 (no practical gain; slight overfit after ep 17). Full table + caveats: `docs/training-findings.md` section A item 7. The three-EMA-half-life question (O2) is UNANSWERED because O2 died in epoch 2.
- **Per-epoch sweep (seed 764, gain 24000, -10 dB):** every finite checkpoint of O1-O5 + A2 rendered, page `~/evals_aac/air_epochs.html` (`eval/air_epoch_sweep.py`). Measured only: O5 air share vs original +0.9..+2.0 dB from epoch 2, peaking epoch 10 (+2.0) then settling at +1.6..+1.9, click screen rising from 0.07 (ep 2-5) to 0.3 (ep 16-25); O3/O4 render clean until ~epoch 5-9 then clicks 5-17 per 1e4 and silent/non-finite renders. Which epoch SOUNDS best is the owner's call.
- **Listening verdict on the epoch sweep (owner, 2026-10-15):** O5 ep3 = last glitch-free epoch and about as bright as it gets (later epochs: sub-second spectral-smoothing dropouts from ep4, slight brightness gain to ep20); O3/O4 (lr 3e-2) glitchy from ep4-5, useless by ep8-12, O4 duller and collapses suddenly at ep12; O1 fine, 1-2 epochs brighter than O5; O2 indistinguishable from bass+body; A2 ep7 brightest, nearly clean. Fadeout glitches come from the bass/mid heads. The click meter and validation loss did NOT see the O5 ep4+ glitches (training-findings B). So: lower-lr / early-stopped heads, not longer training. Provenance + verbatim feedback: `epoch_sweep/run_meta.json`.
- **O6 (O1 with damping from ep 1, cosine from ep 3; 2026-10-15):** DIVERGED anyway: loss 0.0691 / 0.0513 / 0.1187 / 1.63 at ep 1-4, NaN from ep 5 (val 0.0476, 0.0626, 0.0388, 0.0529 for ep 1-4). So at lr 5e-2 neither earlier damping nor an early cosine rescues the run; lr 1e-2 stays the ceiling. A2b (A2 re-run at batch 16 x 2) OOM-ed in epoch 2 on the 16 GB card (14.8 GB allocated); re-queued as A2c at batch 8 x 4 inside `latch/run_air_lowlr.sh`.
- **Second listening (owner, 2026-10-15):** the glitches in O3/O4/O5 are triggered by a short reverse-cymbal-like event near 0:13 of the seed-764 clip (the original has an air-band burst at ~13.25 s; O5 ep4 dips 3 dB just before it vs ep2/ep10), which the head turns into off-manifold spectral distortion from ep5 on; O2 'EMA 4 ep' (= ONE epoch of an lr 1e-1 run averaged 84% toward its init) is bright and a little grainy, so a lightly trained head is the best so far. Next: `latch/run_air_big.sh` = that recipe at d512, effective batch 64 and 128 (micro-batch 8 + accumulation, so no gradient checkpointing is needed), cosine from step 0 to epoch 8, EMA 4/2/0.5 + online saved. Training-set trigger test (is the reverse-cymbal event the only failure site?) not yet done.
- **Queued 2026-10-15 evening (all at seed 764 unless noted; drivers in RUNBOOK 19):** low-lr bracket (A2c val 0.0206 = A2, lr 5e-3 0.0216, lr 2e-3 0.0243 at 7 epochs), DoRA per-block blend bracket (4 seeds), big-batch cosine arms (O2 recipe, d512, b64/b128, plus lr 3e-2 insurance), lr 1e-3 for 15 epochs, Schedule-Free-OFF replicas, band cross-talk diagnostic. Idea status: asymmetric DoRA-vs-base blending in the late blocks = backend done (`dora.block_strengths`, `dora.blend=interp`), GUI = W's adapter mixer; band-isolated head training (penalise cross-band movement; keep body allowed to move with bass) waits on the cross-talk numbers. None of these has a listening verdict yet.
- **Bass head low-lr bracket (queued 2026-10-16, owner ask: "our LRs have been quite high ... try 1e-3 and 1e-4 on something we know steers well"):** `latch/run_bass_lr.sh`, modular+SF d512 dp8, 10 epochs, B3 lr 1e-3 / B4 lr 1e-4 / B2 lr 1e-2 reference, EMA half-life 1 ep (+0.25 ep, +online), every epoch saved, full telemetry to wandb OFFLINE. Output `latch_sweep/bass_lr_2026-10-16/`. Needs a bass epoch sweep (swap the preset's bass slot per checkpoint) to be judged by ear; not built yet. Kill-criterion: a low-lr arm that does not move bass RMS at the old head's gain is dead.
- **Air queue results (2026-10-16):** big-batch cosine d512: P64 (lr 1e-1) NaN at ep2, P64m (lr 3e-2, b64) clean val 0.0366, P128 (lr 1e-1, b128) clean val 0.0972; S5 lr 1e-3 15 ep clean val 0.0210; no-SF replicas at lr 1e-2: QA2 0.0210, QP64 0.0295, QP128 0.0339, QP64h (lr 1e-1) NaN at ep2 (SF is not what makes lr 1e-1 blow up). Bigger batch costs loss at fixed lr 1e-2. Listening pending (air_epochs.html, 7:45 window).
- **Bass lr bracket results (2026-10-16):** B2 lr 1e-2 val 0.0195, B3 lr 1e-3 0.0234, B4 lr 1e-4 0.0516 (still falling at ep10), none diverged. At the preset's production gain (8448) the new heads steer bass LESS than the production head (bass share vs original: production +0.37 dB, B2 ep10 0.00, B3 -0.19, B4 -0.35; crest higher than production 4.35 vs 4.8-5.4); single clip, share metric; needs a gain ladder to compare fairly. Page bass_lr.html (92 clips) awaits ears.
- **Bass optimizer baselines + decorrelation (2026-10-16/17):** val loss at ep10: pure Muon lr 1e-4 (muon_ref) 0.0195, pure Muon 1e-3 best 0.0235 then diverged (ep7+), AdamW 1e-3 0.0214, AdamW 1e-4 0.0215; ours: B2 (1e-2) 0.0195, B3 0.0234, B4 0.0516. Our stack matches by-the-book Muon at best, adds stability, loses speed at low lr. Our NorMuon = official direction (cos 1.000), step norm 4-8% larger (eval/normuon_vs_official_check.py). DeCov penalty on the final hidden features (lambda 10/100; raw penalty only ~0.004-0.007 so 0.1/1 were pointless): val 0.0195/0.0197 (no cost), but at lambda 100 the head steers bass 2.4x less (own response 0.22 -> 0.09 dB) and leakage/own gets WORSE (air 0.41 -> 0.67, mid 0.27 -> 0.56); lambda 10 = control. No evidence decorrelation of hidden channels reduces band cross-talk. Pages: bass_lr.html, bass_grid.html, bass_baselines.html (ears pending).
- **Open:** (1) owner ratings of the 64-seed punch air page (none yet); (2) lr 2e-2 and a weight-norm / preconditioner-norm trace if higher lr is worth pursuing; (3) old recipe retrained with EMA to isolate depth / EMA / optimiser (offered, not requested). Not claimed: that the retrained head sounds better in general, only on 4 seeds by ear.
- Pages: `~/evals_aac/air_heads.html`, `~/evals_aac/punch_air.html`. Heads registered in the render server as `rms_energy_air_a2/a4/a5/a6soap`.

### E5 — LatCH + FiLM density bracket under the ModularOptimizer, goa bigset — **LatCH DONE 2026-09-30 (read 10-06); FiLM NOT STARTED**
- Kim: "launch LATCH and MuseControlLite (FiLM) bracketing using the 12k goa set ... check that the findings about
  dimensions, batch, lr, etc still hold with our trainer ... then start trying out likely good combinations. At least
  Shampoo is good." Target = the density head (onsets per beat).
- **Phase A** (running): the May LatCH findings (LATCH_RESULTS.txt §3/4/6/21/22: d256 best, small batch better, lr 1e-3 >
  3e-4 at short budgets, SF-NorMuon ship) re-checked under `train_latch --optimizer modular` on `latents_sa3`
  onset_envelope_ts (targets already exist), 10 ep, 14 arms incl. two repeat-seed noise-floor arms.
  Driver `latch/run_modular_bracket.sh`; results `Mantu/latch_sweep/modular_2026-09-30/phaseA/SUMMARY.tsv`.
- **Phase B** (queued on targets): the bigset had no targets; `latch/extract_density_targets.py` computes
  onset_per_beat_ts (running, ~2 h). Then the best Phase A settings + combinations on the bigset, grouped split by track.
- **FiLM** (`control/sa3_control/train.py --optimizer modular --control-mode scalar --scalar-from-timeseries
  onset_per_beat_ts`): needs the full DiT (~10+ GB) — only when W is off the GPU.
- Kill-criterion: an arm is only "better" if it beats the repeat-seed spread.
- **Phase A result:** the modular lr is ~30x AdamW's (best 1e-2; 3e-2 diverges; 3e-4 under-trains). At 1e-2 + 500-step warmup,
  modular+Shampoo gives 0.357 vs AdamW 0.408/0.411 and Fusion 0.407 (~12% better). Phase B (bigset) runs unattended until ~13:30;
  full write-up + how to read it: `Mantu/latch_sweep/modular_2026-09-30/REPORT.md`.
- **Phase B verdict (bigset, 11 arms):** Schedule-Free is the winning part (modular 0.20-0.21 vs AdamW 0.25-0.26; modular without SF 0.255);
  Shampoo adds nothing measurable for heads; d512 no gain; b16 best (0.194, one seed); AdamW 1e-3 is not better than 3e-4.
  Head recipe: modular lr 1e-2 + 500 warmup, b16, d256, SF on. Next: one b16 repeat seed, then FiLM (needs captions joined or a deliberate empty-prompt run).
- **Phase C verdict (bigset, 9 arms, 2026-10-06):** the plain head recipe wins (C01 0.1955, C02 other seed 0.1953, seed spread 0.0002).
  Every added part hurt: radial brake 0.8 0.1986, escape velocity 0.1995, brake+EV (C09) 0.1991, burn-in 0 / 3000 0.1997 / 0.2017
  (1000 best, so burn-in is not monotone), sf_r=2 0.1976; sf_r=0 (uniform averaging) 0.1960 is the only near-tie.
  Kim nonetheless chose C09 as the base for Phase D ("the way burn-in made results worse makes me think the model had less time to learn").
- **Phase D (running from 2026-10-06 20:00, SHARE_GPU=1 SAVE_ALL=1, ~10 h):** `latch/run_modular_bracket.sh` on `phaseD_arms.txt`,
  15 arms, base C09, every epoch saved. D01/D02 re-run C09/C01 (control + trajectory analytics); D03/D04 switch brake+EV on late
  (`--mod-late-from` 2000 / 4000 of ~7430 steps); D05-07 lr 3e-3 / 6e-3 / 1.5e-2; D08-10 Lion (lr 1e-4 / 3e-5 / 3e-4, wd 0.1);
  D11-13 depth 8 / depth 2 / dim 512; D14/15 batch 8 / 32. Kill-criterion as above (beat the 0.0002 seed spread, and C01 0.1955).
  Trajectory analytics via `control/sa3_control/checkpoint_trajectory_stats.py` on the saved epochs (symlink `*_step<N>.pt`).
  16 dataloader workers did NOT speed an epoch up (4 min as with 8), so loading is not the bottleneck.
- **AUDIT 2026-10-07 (supersedes the Phase C ranking above):** D02 (the C01 recipe again) scored 0.1995, not 0.1955; D16 (C01 with
  8 workers) reproduced C01 at every epoch, so the cause is `--num-workers 16` (C01: 8), not SAVE_ALL or the new code. The 0.0002 "seed
  spread" was not the noise floor: worker count moved the plain recipe by 0.004 and C09 by only 0.0005. **Treat differences < ~0.004
  as noise;** Phase C's brake / escape velocity / burn-in / sf_r verdicts are NOT established; Phase A/B effects > 0.004 (modular vs
  AdamW, SF on/off) stand. Phase D arms D03+ run at 16 workers and compare only against D01/D02. Next: repeat seeds before reading any
  Phase D arm. Postmortem: docs/training-findings.md 2026-10-07.
- **Phase D RESULT (2026-10-07, all 16 arms done; one repeat of D13 needed, see below).** Held-out loss, 16 workers, reference = anchors
  D01 0.1986 / D02 0.1995 (noise ~0.004, single seed each, so arms within 0.004 of the anchor are NOT results):
  **dim 512 0.1908** (beyond noise, its curve sits under the anchor's from epoch 5 on; 1.46x wall; same sign as Phase B's B13 but
  larger); depth 8 0.1946 (borderline), depth 2 0.2145 (worse); batch 8 0.1955 (noise), batch 32 0.2067 (worse); lr 3e-3 0.1969 /
  6e-3 0.1993 / 1e-2 ~0.199 (flat), 1.5e-2 0.2040 (worse); brake+EV switched on late at 2000 / 4000: 0.1969 / 0.1984 (noise, so the
  timing does not matter, nor the burn-in question it was meant to settle); **Lion** lr 1e-4 / 3e-5 / 3e-4: 0.237 / 0.228 / 0.262, far
  behind the modular optimizer (~0.20) and its best lr was the LOWEST tried, so that bracket is open below 3e-5 (it sits near AdamW's
  0.25 only at the edge). Read: for the head recipe lr, batch and damping timing barely matter; **width is the only lever that paid**.
  NOT done: repeat seeds of D13 / D11 (needed before calling them settled), weight-path analytics on the new arms
  (`latch/head_trajectory.sh`), the FiLM half of E5. Incident: D13 was OOM-killed at 7 s by a render of mine on the same card
  (my VRAM guard only checked at launch; training grows later), then re-run alone: the 0.1908 is that clean re-run. Data:
  `/run/media/kim/Mantu/latch_sweep/modular_2026-09-30/phaseD/SUMMARY.tsv`, REPORT.md there.
- **CORRECTION to the Phase D batch readings (W, 2026-10-07, from the epoch curves; verified by C).** D15 (b32) changed only `--batch-size`
  with 10 FIXED epochs, so it took half the optimiser steps at the same lr: at EQUAL steps b32 ep10 0.2122 vs anchor ep5 0.2149 (parity or better, at
  ~60% of the wall time), so "batch 32 worse" is a step-count confound, not a finding. The reverse holds for D14 (b8): twice the steps; at equal
  steps b8 ep5 0.2069 vs anchor ep10 0.1986 (worse), so its "within noise" 0.1955 was bought with 2x steps. Also: every curve is still falling at
  ep10, so a fixed-10-epoch ranking measures learning SPEED, not the ceiling; dim 512 leads only from ep8 (leaders at ep2-7 are b8 and lr 3e-3); the
  losers (Lion, depth 2, lr 1.5e-2) are clear by ep2-3. Arms with the same batch (lr, depth, dim, late switching) have equal steps, but are still
  10-epoch single-seed readings. The arms ran without wandb, so no per-step telemetry exists. **Phase E queued** (below) to settle it: 20 epochs, equal-step batch arm, one repeat seed.
- **Phase E ON HOLD (Kim 2026-10-12): the LatCH training continues once the Synth-JEPA detour is parked at a verified sound quality; no resume before his word. Mantu path note: the drive is at /run/media/kim/Mantu2 until the morning remount (KIM-TASKLIST), and 98 % full.**
- **Phase E STOPPED 2026-10-07 13:0x at Kim's request ("stop the LatCH training, let G BS-RoFormer our mix clips first"); it had only reached epoch 1 of E01, no arm finished, nothing lost. RESUME (waits for the GPU lock itself):** `cd /home/kim/Projects/SAO && PD=/run/media/kim/Mantu/latch_sweep/modular_2026-09-30 && SAVE_ALL=0 setsid nohup bash latch/run_modular_bracket.sh $PD/phaseE_arms.txt $PD/phaseE > $PD/phaseE/driver.log 2>&1 &` (resumable from SUMMARY.tsv; E01 restarts from epoch 0). Original plan: (queued 2026-10-07; first held up by W's H6 lock): `phaseE_arms.txt` in the same dir, 16 workers, base C09, best-checkpoint only:
  E01 anchor 20 ep (the new control), E02 dim 512 20 ep, E03 dim 512 20 ep seed 1 (the repeat), E04 b32 20 ep (= the anchor's 10-epoch step count at
  ~half the wall time), E05 depth 8 20 ep, E06 lr 3e-3 20 ep. Reading rule: compare only within 20 epochs and, for batch, at equal steps; Delta < 0.004 is noise.
- **Phase E DONE 2026-10-14 (G; run finished 12:09, read 13:00).** Held-out loss, 20 epochs, anchor E01: best 0.1907 / last 0.1967. dim 512 0.1906 and
  0.1887 (two seeds: 0.002 apart, so no gain), **depth 8 0.1844 (the only arm beyond the 0.004 rule)**, lr 3e-3 0.1874 (inside the noise), b32 0.1962
  (aborted at teardown, rc 134, after all 20 epochs and the best save). Train loss was still falling at ep 20 in every arm while val had been flat since ep 6-8,
  so val loss alone cannot say whether the heads kept learning something that matters for steering. Eval clips for all six arms (74 clips, 3 density targets x 2
  gains x 2 prompts + shared baselines): `Mantu2/latch_sweep/modular_2026-09-30/phaseE_eval_clips/`, page `~/evals_aac/latch_phaseE.html`
  (`Misc/build_latch_phaseE_page.py`); not yet listened to. DSP screen: steering DOWN (-1 sigma, g512) removes ~2 onsets/s; steering UP barely moves it
  (+0.1..+0.5 onsets/s on ~6); g2048 at +2 sigma loses ~4.8 dB loudness (13 of 72 clips flagged for a listen). The arms do not separate on this screen
  (prompt and seed move the result more than the arm does). New `SAVE_EVERY=1` in the driver keeps per-epoch checkpoints next to best.pt.
- **Phase F (PROPOSED by Kim 2026-10-14, NOT STARTED, not authorised to launch): retrain the best setup "with the new controls".** My reading, to be confirmed by Kim before
  anything runs: base = the depth-8 head (E05), dim 512 as the hedge; "new controls" = content-preservation checks on every head (melody/chroma kept, tempo and
  rhythm kept, timbre allowed to move, because a good steer legitimately changes timbre: Kim's bass+mid RMS "punch" case kept the notes and lost the graininess).
  Tools that exist now: `eval/latch_drift_check.py`, `eval/latch_melodic_tensor.py` (bass+mid only), `eval/latch_melody_check.py`, `eval/essentia_zoo_battery.py`,
  `latch/run_modular_bracket.sh` with `SAVE_EVERY=1`. Open questions: (1) is the chroma lock a TRAINING-time term or an INFERENCE-time companion slot (SAME's chroma
  readout is a linear 384-d map of a 256-ch latent, so it cannot be nulled exactly by projection; a soft penalty or a companion `same_chroma` head with the
  source's own chroma as target are the options); (2) the gain for this head is unknown (512/2048 guessed); (3) the unsteered-baseline seed noise of every meter is
  large (the 24-step control moved Audiobox enjoyment by +0.2..1.0), so each verdict needs >= 2 seeds. Gate before launching: listen to the Phase E page.
  (4) **Dynamics-stable control (Kim 2026-10-14, on the bass+body punch steering):** a control that keeps dynamics (crest factor / loudness envelope) stable would force real edits instead
  of a louder, more compressed result; the loss of dynamics seen in the punch clips was an accepted side effect, NOT an improvement. Every Phase F verdict is therefore scored at matched loudness,
  with crest and envelope change counted as a cost. The improvement he describes is less coarseness plus the missing bass, 'a rounding of the sound to a more balanced whole'; punch itself
  comes from snappy envelopes and good spectral separation. Evidence set: the 64-seed rating set (`eval/punch_rating_server.py`, his 1-5 ratings).
- **Phase E LISTENED + GRIDDED (W, 2026-10-15) — the heads barely steer, and the guidance never acted early.** Listening verdict on
  `latch_onset_compare.html` (recorded verbatim in the six `onset_eval_latchE_*/run_meta.json` `kim_feedback` fields): *"the LATCH heads barely
  change the sound, except where it collapses."* The gain × density grid (gains 0-8192 × 2-10 onsets/s, `files/evals/latch_onset_grid.html`,
  `Misc/build_latch_onset_grid_page.py`, gate per cell, quality leg = Audiobox PQ) agrees once effect size is read: at the gate-clean gains
  128-512 the measured density spreads only 2-2.8 onsets/s around the unsteered 7.3, versus 2.3-11.2 for the FiLM adapter (strength ≥ 1.3) on
  the same requests; a FiLM-like range appears only at 2048-8192, where cells start failing (7/150, six on PQ drift). Correlations of 0.83-1.0
  there describe a small shift, so "passes the gate" meant "barely changed". **Likely cause, not yet tested:** TFG's per-step weight
  `s(t) = alpha_t / sum(alpha)`, alpha = 1 - sigma (LatCH paper 2603.04366 Eq. 3) gives the first 20% of steps ~0.2% of the budget and the last
  20% ~62%; every onset eval used the full window, so guidance acted almost only after rhythm was fixed (energy heads still work because what
  they steer can change late). Opt-in fix landed: `latch_hparams["guide_schedule"] = "flat"` (`latch_guided._window_scale`, tests in
  `tests/test_latch_multi_guided.py`). **Test queued:** `eval/latch_early_budget_bracket.py` via `eval/run_latch_early_budget.sh` (waits for the
  GPU lock): 250 clips, onset head E04 alpha vs flat × windows 0-0.2/0.4/1 × gains 32-2048; early-weighted sigma schedules (flux a=3, logSNR
  rho=2); the air head with constant weight; the post-trained model at 24 steps. Page builder `Misc/build_latch_early_budget_page.py`.
  **Consequence for Phase F:** retraining on a better optimizer/arch is unlikely to help if the early-budget test is negative; run it first.
- **Early-budget bracket RESULT (W, 2026-10-15) — partial support; flat helps, early-only windows collapse.** 250 clips rendered (0 non-finite),
  page `files/evals/latch_early_budget.html` (`Misc/build_latch_early_budget_page.py`), numbers in the run's `run_meta.json` `result`. Gate as
  above (vs the same leg/shape/seed unguided clip, PQ leg): 52/230 guided clips fail. Spread = measured(10 req) - measured(2 req), seed mean.
  (A) Onset head, base model: widest gate-clean spread alpha/full window **2.9** (g512) -> flat/full window **4.2** (g512), i.e. ~1.45x at a
  clean gain, still ~half the FiLM adapter (~9). Early-only windows: alpha 0-0.2/0-0.4 is inert below g2048 (as predicted); flat 0-0.2 reaches
  6.2 (g512) and flat 0-0.4 7.8 (g2048) but those cells FAIL: the low request collapses to 0.1-1.5 onsets/s (hf-blowout, PQ drift). The high
  request still caps at ~9-9.4 onsets/s, so the extra range is almost all downward. (B) Early-weighted sigma shapes (flux a=3, logSNR rho=2)
  with flat: same picture as A-flat (clean 3.8-4.4), the shape adds little on the base model. (C) Air head A2: flat gives ~3-4x the spread per
  gain (g8192 full: 31.8 dB vs 9.5) but the CLEAN range is about the same (alpha g8192 9.5 dB all pass; flat g2048 10.0 dB, 1/4 fail): flat buys
  gain efficiency, not more usable range. (D) Post-trained model, one seed: on its own schedule an early window is inert under both weightings;
  flux3 makes it respond (2-3 onsets/s) with many hf-blowout fails. **Reading:** the alpha weighting did hold the onset head back, but giving
  the early steps the budget makes the head push density DOWN until the clip falls apart rather than giving clean groove control; the upward
  ceiling is unchanged. Not listened yet; the ear decides whether the flat/full-window g128-512 cells are musically different. Phase F: an
  early-budget fix alone does not close the gap to FiLM.
  **Listening verdict (2026-10-15, run_meta kim_feedback):** alpha 0-1 is the cleanest; flat 0-1 pushes the volume up into clipping and
  distortion at high weights; early windows distort loudly under both weightings; with alpha 0-1 the effect is noticeable, gain 512 quite
  okay, 2048 not impossible, and above all transparent: the musical matter stays intact, where the FiLM adapter drags in the training-set style.
- **Onset matrix, alpha 0-1, EMA vs online (W, 2026-10-15).** E04 recipe retrained with EMA half-life 0.5 ep + online weights saved from the
  same run (best ep 19, val 0.1961 = original). Requests 0-12 onsets/s x gains 32-4096 x 2 seeds (626 clips, `files/evals/latch_onset_matrix_ema.html`,
  `eval/latch_onset_matrix_ema.py`). EMA and online are indistinguishable at this half-life. Response monotonic at every gain (corr 0.86-0.95),
  saturating at ~5.5 and ~9.3 onsets/s from gain 256 (unguided 6.3/7.3); gate-clean through gain 1560, first fails at 2048.
- **Loudness fixes for hard LatCH guidance (W, 2026-10-15), page `files/evals/latch_guide_anchor.html`.** (1) Per-edit rescale
  (`latch_hparams["guide_rescale"]`, restore std after each guidance edit, like CFG rescale): NEGATIVE, level unchanged (flat 0-1 g4096 latent
  std 2.0 -> 1.9 vs ~1.1 unguided); each edit redirects rather than enlarges, the inflation builds through the model's own later steps.
  (2) Trajectory anchor (`latch_hparams["guide_anchor"] = s0`, cap std(x_t) at sqrt(((1-t)s0)^2+t^2) after every step): POSITIVE on level,
  every loud setting back to the unguided level (flat 0-0.2 g2048 std 4.1 -> 1.2, RMS -4.3 -> -13.7 dB) with onset spread kept or raised
  (5.6 -> 7.2); clean alpha 0-1 unchanged at g512/2048, its g4096 spread trimmed 6.7 -> 4.5. But the gate barely moves (59 vs 63 of 144 fail;
  early windows still 3-4 of 4 per cell at g2048+ on PQ drift / beat loss / hf blowout): early guidance damages the content, not only the
  level. Not listened yet.
- ⚠ Found on the way: madmom's top tempo is half-tempo on 45% of `latents_sa3` goa crops, so the June `onset_per_beat`
  scalar is doubled on those crops — see docs/training-findings.md 2026-09-30.

### E7–E11 — Transparent AND wide-range density control: combining LatCH (transparent, weak) with FiLM (wide, leaks training-set style) (Kim, 2026-10-15)
*Context (Kim, 2026-10-15): today's tests show the onset LatCH heads DO steer, but transparently and not strongly (earlier read of
"barely steer" — Phase E, DISCOVERIES 10-15 — was the gate passing on a no-change; the effect is real and small). FiLM has the range but
brings the training set's style (goa). Question: how to get both. Prior: the ear-approved density control is plain-Fusion FiLM (DISCOVERIES,
CONTINUITY 07-07); FiLM gain 6 = glitches, flat 1.75 canonical ("FiLM broken: overdrive, not wiring", continuity journal 07-07); the July
LatCH/FiLM/both grid (`eval/density_control_eval.py`, newcap8_promptstyle arms, OLD onset_envelope head) predates the Phase-E head. Mechanically
FiLM + LatCH compose on :8056 (`docs/INFERENCE-SURFACE.md` "What actually composes"). Kim recalls trouble making them work together — no logged
conflict found in DISCOVERIES/journals; likely gain scaling, UNVERIFIED. Idea-ordering is cheapest-first (lightweight-tests-first).*
*Shared instrument rule (AUDIT THE INSTRUMENT): every arm needs TWO readouts — (a) achieved onset density vs target, (b) CHARACTER DRIFT vs the
same-seed same-prompt UNCONTROLLED base render (CLAP embedding distance; PQ alone is the best ear-proxy but is blind to sparse material, so
don't use PQ as the drift meter). Before trusting (b): show it separates a known style-leaked FiLM render from a base render. FiLM-only is the
positive control for (a) — Phase E's gate passed because nothing changed, so a meter with no dynamic range must fail loudly.*

- **E7 — LatCH × FiLM combination grid with the drift meter — RUNNING (WINTERMUTE; driver `eval/latch_film_combo_e7.py render` started 13:55 on 10-15 — it appeared while this entry was being written).** Fixed
  seeds/prompts; FiLM gain {0.5, 1.0, 1.75} × LatCH gain {off, mid, high} on the Phase-E E04-EMA onset head
  (`.../phaseE/E04ema_b32_ep20/latch_sa3_onset_per_beat_ts_best.pt`, matrix driver precedent `eval/run_latch_onset_matrix_ema.sh`). Build as a
  thin CLIENT of :8056 `/generate` (`film` + `latch` payloads compose) — NOT a new guidance driver (INFERENCE-SURFACE rule). The July
  `density_control_eval.py` is the shape of the grid but loads the old head/arms in-process. No Kim-runnable block yet: the driver doesn't exist.
  Kill: if "both" ≤ max(FiLM-only, LatCH-only) on density-vs-drift (Pareto), the combination adds nothing at these gains → go to E8/E9.
- **E7a — LatCH-only high-gain extension (Kim, 10-15, after listening to `latch_onset_matrix_ema.html`) — READY, waits for a free GPU.** Observation: measured
  density barely moves with gain; only >=2048 changes anything, and then it drags the whole clip elsewhere. Matrix data (seed 1234, EMA): response vs requested
  density is ~gain-independent and SATURATES at ~9 on/s (target 12 -> 9.0 at g128, 9.2 at g4096); target 0 only moves at high gain (6.0 g128 -> 2.9 g4096);
  unguided 7.3, yet target 7 already gives 8.15 at g128 (a bias — cf. the madmom half-tempo doubling on 45% of crops, training-findings 2026-09-30).
  Test: target 7, gains 4608..8192 step 512, seed 1234, EMA+online (16 clips) via `eval/latch_onset_highgain.py` (thin wrapper over the matrix script; dry-run
  verified: 16 cells). Expect little density headroom at target 7; `--targets 7,3,0` adds the downward axis (48 clips). Kill: if drift/disintegration appears
  before density moves, LatCH alone has no wide-range regime -> E8/E9 are the path.
- **E8 — Timestep-gated FiLM (full strength early, fade to 0 for the low-noise tail), optionally LatCH late — PLANNED (inference only).**
  Rationale: rhythm/layout is committed at high noise, timbre/character at low noise. ⚠ The FiLM payload today is `{ckpt, value, gain}` — NO
  start/end (verified `eval/explorer_render_server.py:662 film_context`), unlike the LatCH slots, so this needs a gain-by-t schedule added to
  `film_context`/`ControlContext`. Doubles as a diagnostic: WHERE in the schedule does the style leak in? Kill: drift unchanged at matched density.
- **E9 — Contrastive FiLM `v = v_base + w·(v_film(c) − v_film(c_neutral))` — PLANNED, GATED on E7 (or on E8 failing).** The adapter's constant
  style shift appears in both terms and cancels; only the control-dependent delta rides on the base model (cost: +2 DiT passes/step).
  ⚠ Needs the adapter to have seen a null control: `--cfg-dropout` in `control/sa3_control/train.py` is TEXT dropout; `--melody-dropout` /
  `--metrical-dropout` exist for other modes but NO scalar-mode control-null dropout was found — verify or use a mid-value reference.
- **E10 — Retrain FiLM with the leak removed at the source — POTENTIAL, GATED on E8/E9 showing residual leak.** (a) *Data-side first:*
  cluster the corpus by CLAP, re-balance sampling so density is uncorrelated with cluster (backdoor adjustment; no differentiable CLAP needed).
  (b) *Then optionally an in-loss constraint (Kim, 10-15: "keep the CLAP score constant"):* `L = L_flow + λ·max(0, ‖E(ẑ0|c) − sg[E(ẑ0|null)]‖ − margin)`
  on the same x_t/noise, low-to-mid t only (x0-hat is blurry at high noise); margin set from how much CLAP legitimately moves between real
  density variants (margin 0 trains the control to do nothing). E must be differentiable on latents: SAME's own contrastive latent↔text critic if
  we can load it (UNCHECKED), else a linear latent→CLAP probe fit on precomputed embeddings (audit it — the adapter will learn to fool a weak
  probe), else decode through SAME-L (MPGD route, expensive; `control/CONTROL_FINDINGS.md`). Counterfactual rhythm via BUNGEE time-stretch only,
  never sox. Kill: drift drops but density range collapses with it.
- **E11 — "Old-school" finetune with a baked-in onset conditioner, as the CEILING/reference arm — POTENTIAL.** Kim 10-15: baked-in is not always
  optimal. Shows how far onset control goes when the backbone may adapt; expect the strongest style leak, no scalability, full-FT runaway risk.
  Preferred form: a control-LoRA/DoRA trained jointly with the conditioner + control dropout, so null control = base behaviour and the existing
  adapter strength knob (0.5/1.0/1.5) keeps the "baked" part dial-able. Reference, not main path. Needs the training-launch notes
  (`run_meta.json` purpose/hypothesis/kill) per CLAUDE.md before any launch.
- **E7 / E8 RESULTS (W, 2026-10-15), page `files/evals/latch_film_combo.html`.** E7: LatCH + FiLM beats FiLM alone on range vs CLAP drift in all
  three contexts (e.g. punch FiLM 1.75 alone 4.4 onsets/s spread @ drift 0.28 vs FiLM 1.0 + LatCH 512 5.5 @ 0.15); kill NOT met; sweet spot FiLM
  0.5-1.0 + LatCH 512. Drift meter audited (house: FiLM 1.75 0.22 vs LatCH alone 0.03). E8: FiLM gated to sigma >= 0.4..0.8 keeps 85-100% of its
  spread but does not reduce drift in house (0.26 vs 0.22) -> the style pull enters early with the density; kill met for the leak; FiLM's late
  steps add nothing. Next per plan: E9. Numbers in each run's `run_meta.json` `result`.
- **E12 — FiLM density adapter retrained under the ModularOptimizer — RUNNING/QUEUED (W, asked in session 2026-10-15).** Reference = the shipped
  FiLM `onset_Fusion_lr1e-4_randomcrop` (FusionOpt lr 1e-4, 54k steps). The modular optimizer has never trained a control adapter, so LR does not
  transfer (TRAINING.md D4): stage 1 = LR bracket 3e-4 / 1e-3 / 3e-3 x 6000 steps, EMA 0.999 + online weights saved (`state_online`, added to
  `control/sa3_control/train.py` today, D6), prune-only (D25). Stage 2 = the survivor at 54k, then the E7 contexts vs the shipped FiLM (range,
  drift, gate). Runner `control/run_film_modular_bracket.sh` (queued behind GHOST-NOTE's air queue, `/tmp/air_nosf.done`), outputs
  `Mantu2/sa3_control_runs/film_modular_bracket_20261015/`. Kill: all arms diverge or show no density response at 6000 steps.

### E13 — same_chroma LatCH head retrained under the ModularOptimizer — **QUEUED 2026-10-16 (W)**
- **Why:** listening 2026-10-16 on the 06-25 all-C sweep (`riffer-evals/clips/chroma_steer/`, sidecar now carries the verdict): the production
  head steers, transparently (pad chords change their notes), most audibly at gain 2048, so higher gain may pay. Production head = AdamW,
  EMA 0.999, depth 4, 20 ep, train-loss selected (the E3 caveat).
- **Runner** `latch/run_chroma_retrain.sh`: G's bass recipe (modular + SF, Shampoo, Muon all 2-D, d512 depth 8, grad clip 1.0, EMA 1 ep +
  0.25 ep + online, every epoch saved, val by relpath), cosine loss, unstandardised targets, other-stem SAME chroma from
  `Kosmos/latents/latents_sa3_stem_chroma`. Arms C3 lr 1e-3, C4 1e-4, C2 1e-2 (reference), 20 ep each, 20-step smoke first. Queued LAST
  (after the E12 chain, the drone-sweep weights test and G's LatCH queue); output `Mantu/latch_sweep/chroma_retrain_2026-10-16/`.
- **Still to build:** an epoch sweep for chroma (all-C / progression targets via `eval/chroma_steer_render.py`), with the gain ladder
  extended above 2048 (3072, 4096, 6144) for both the production head and the retrained arms, through the disintegration gate.
- **Kill:** no arm beats the production head's C-dominance at equal gain, or every arm's extra range fails the gate.

### E14 — Batch engineering: composition and ordering of minibatches for the control heads — **PLANNED 2026-10-21 (CONTINUITY, asked by Kim); REGISTERED ONLY, not scheduled**
- **Why:** the LatCH trainer batches iid (`random_split`, `DataLoader(shuffle=True, drop_last=True)`); nothing in DISCOVERIES, knowledge.md or this file
  covers batch composition. Within a batch the order is irrelevant (the gradient is a mean), so there are two real knobs: WHO shares a batch
  (composition) and WHAT SEQUENCE of batches the optimizer sees (ordering). Muon flattens the singular values, so a batch whose gradient has a few
  strong directions gets its weak tail promoted: composition may matter more under NorMuon than under AdamW (hypothesis, unmeasured).
- **Arms, cheapest first:**
  1. *Free changes:* low-discrepancy (stratified or antithetic) timesteps within each batch. **VERIFIED by W 2026-10-21: neither trainer stratifies t** (LatCH draws it independently per item, `train_latch.py` ~578; FiLM `control/sa3_control/train.py _sample_t`, iid per item, logit-normal by default), so this is a free arm on both; it also bears on the DoRA spike batches, which are high-t clumps (max-loss item had t > 0.85 in 39 of 48);
     density-stratified sampling (equal mass per onset-density bin; shifts the implied target distribution, which is wanted for a control head).
  2. *Within-song contrast batches:* several windows of one song at different densities, so style/timbre/key cancel in the gradient. Cost: windows of
     a song are correlated, so the effective batch is smaller than the nominal one. Ties to E9/E10.
  3. *Diverse vs clustered batches* (farthest-point or DPP on principal components, vs cluster-homogeneous) as a gradient-variance / subspace-stability
     probe at a fixed checkpoint. NO training needed; reuse the half-batch machinery of `docs/modular-opt-test-plan-2026-10-17.md` sec. N and P.
  4. *Ordering (ascending/descending/nearest-neighbour walk) only as a STRESS TEST* of Muon vs AdamW under correlated batches. Momentum, EMA and
     Schedule-Free assume roughly stationary gradients, so a sorted stream makes them average the schedule; reshuffle every epoch. Herding / GraB
     (Lu and De Sa, cited from memory, NOT verified against the paper) is the principled ordering method; per-example gradients are affordable for a d256 head.
- **Instrument rule (accepted by W, who will switch from `cos(polar(M), G_ref)` to `polar(G_ref)` plus principal angles, with a large-batch ceiling):** any probe comparing a polarised update to a reference gradient needs its ceiling: `cos(polar(G), G) = ||G||_* / (||G||_F * sqrt(r)) < 1`
  even for a perfect update, so compare against `polar(G_ref)` or use principal angles, and report the same number for a large-batch pair.
  Before any sampler stratifies on a feature, confirm the feature meter has range on our data.
- **Gate:** after the overnight batch-scaled LatCH arms (`eval/run_overnight_dpo_batch_20261021.sh`, job B) and the sec. N/P reads of the test plan. Do not stack on
  those results.
- **Kill:** if iid, density-stratified and diverse batches give indistinguishable gradient variance and held-out control quality at equal samples seen,
  drop composition and keep only the free changes in arm 1.
- **RESULT, stratified t on the LatCH onset head (W, 2026-10-25; ST64, stable-audio-3 `--t-sampling stratified`, EB64r recipe, 40 epochs, run_meta in `strat_t_20261025/ST64`):** best val **0.1819** at epoch 40, inside the iid pair's band (EB64 0.1802, EB64r 0.1896, same seed and recipe). Half-batch gradient cosine, median over the run 0.194 vs 0.189 (EB64r) / 0.176 (EB64); second half 0.132 vs 0.134; noise ratio 0.73 vs 0.75. **Meets its kill: stratified t buys nothing measurable here.** One soft sign: after its best epoch EB64r climbed back to ~0.198 while ST64 stayed within 0.184-0.191 and was still improving at epoch 40; one run, not a finding. Antithetic t not run.

### E15 — HTMuon (heavy-tailed spectral correction) as a Muon variant — **PARKED 2026-10-21 (CONTINUITY); gated on test-plan sec. P**
- **Paper:** arXiv 2603.10067 v2 (Pang, Fang, Liu, Deng, Hsiung, Yu, Yang; Dartmouth, Microsoft, ICSI/UC Berkeley, Meta). Update `O = U S^p V^T`
  with p = 0.125 (p=0 is Muon, p=1 is SGDM), motivated by HT-SR theory (Martin and Mahoney) that better-trained nets have heavier-tailed weight spectra.
  Needs an SVD per step; the paper's cheaper variants are every-k-steps and an NS-root form (`HTMuon_NS`).
- **Filed 2026-10-21:** `papers/arxiv-2603.10067 - HTMuon - Improving Muon via Heavy-Tailed Spectral Correction.{md,pdf}` + knowledge.md row (read pp. 1-18 and 24-31; proofs and hyperparameter tables unread). Two further findings from that read: Muon's best learning rate is the LOWEST on their grid at both 60M and 135M (its optimum may lie below the grid), and the repo default p=0.25 is worse than Muon in their Table 14.
- **Evidence (first pass):** perplexity gain over Muon is 0.92 (LLaMA-60M), 0.98 (135M), **0.02 (350M: 16.81 vs 16.79)**,
  0.16 (1B: 14.33 vs 14.17), 0.26 (GPT-2 small); CIFAR/ViT gains 0.1-0.3 points. The gain shrinks with scale. Their own Fig. 1 shows
  Newton-Schulz Muon BEATS exact-SVD Muon, i.e. our NS5 is already a partly soft spectrum. All LLM/vision pretraining; no fine-tuning, no small control heads,
  no audio. The pasted claim "peer-reviewed ACL Findings" is not visible in the pages read: unverified.
- **Code read 2026-10-21** (github.com/TDCSZ327/HTmuon, MIT, last commit 2026-05-02, `llama_pretraining/muon.py`): the exact form is `U * S**p @ Vh` on the
  Nesterov-lerped momentum, in fp32, with the usual `max(1, rows/cols)**0.5` rescale; the fast form is `NS5(M) @ (M^T M)^(p/2)` (`muon_generalized_ht_update_v2_acc`).
  The repo also carries several other experimental spectra (rank-index decay `idx**-p`, `1/sqrt(idx)`), and the launcher default is `--power 0.25`, not the paper's 0.125,
  so check which variant a given result used. Because `S**p` is applied to RAW singular values, the update magnitude depends on the gradient scale (unlike Muon),
  so the comparison is only fair at a tuned lr (the paper grid-searched every optimizer). My arithmetic, unverified by a run: at p = 0.125 a 100x spread of
  singular values becomes only 100^0.125 = 1.8x, about the same spread NS5 already leaves (0.7-1.3), so the effect may be small next to an lr retune. For a d256 head the
  per-step SVD cost is negligible; the open question is whether `torch.linalg.svd` is usable on our ROCm stack (else run it on CPU).
- **Why parked:** plan sec. P says no new optimizer is justified before P1-P3 read out. HT-SR needs weights that have developed power-law spectra; a
  d256 head trained for ~thousands of steps may not. Cheap probe if P shows the non-leading momentum directions help: apply `S^p` in the probe, no run needed.
- **Kill:** P shows the bulk directions do not lower held-out loss under our optimizer/precision/batch.

### E16 — NAMO / NAMO-D (SNR-scaled Muon) — **PARKED 2026-10-21 (CONTINUITY); gated on test-plan sec. N/P**
- **Paper:** arXiv 2602.17080 v2 (Zhang, Liu, Schaeffer; UCLA Mathematics), filed in `papers/` with a sidecar and a knowledge.md row. Muon update times a scalar `||M||_F / sqrt(EMA ||G||_F^2)` (NAMO) or a per-column,
  clamped version (NAMO-D). Code: github.com/minxin-zhg/namo (MIT).
- **Why parked, in one line:** it is the SNR gate `ModularOptimizer` already has (TRAINING.md F27: pure-noise floor 0.183, an uncalibrated ~x0.2 lr cut at small batch); NAMO's floor is 0.16 at momentum 0.95. Its GPT-2 evidence is
  0.01-0.02 nats, one seed, constant lr (a self-shrinking step then acts as a decay), with an optimum lr 7-9x Muon's. Its convergence theorem needs a batch far above ours.
- **Floor at matched momentum (W):** `sqrt((1-b)/(1+b))` is 0.16 at 0.95 but 0.23 at our default 0.9, so compare with F27's 0.183 at equal beta.
- **Cheap check (no new run):** log NAMO's `alpha_t` next to `comp/snr_gate` on an existing LatCH/FiLM arm; if they track, there is nothing new. If alpha lifts well above the floor on some matrices, those are where the signal is.
- **Kill:** alpha stays within about 0.1 of its noise floor on our batches.

### E17 — Which of our matrices are in Muon's noise-dominated regime? Covariance ratio and delta_beta probes (Xie 2609.32861) — **PLANNED 2026-10-21 (CONTINUITY); zero training, gated on test-plan sec. N logs**
- **Why:** the paper bounds the extra fluctuation of Muon over response-matched momentum SGD at about 7-8% (isotropic) to 14-19% (attention, real gradients) of excess loss at beta 0.95, but gives no threshold for when a matrix counts as noise-dominated and tests no switch.
  That sizes the worry behind E15/E16 and any late switch; we should measure it on OUR heads before building anything.
- **Probe 1:** `delta_beta ~ 8.8 * sqrt(c/(1-c))` from the half-batch cosine `c` that sec. N already logs (derivation in the paper's sidecar, mine, unverified). Report per matrix at a few checkpoints.
- **Probe 2:** at a fixed checkpoint store a pool of minibatch gradients (the paper used 8192, effective batch 64), resample stationary streams, and compute `R_K = tr Cov(sum T(m_k)) / tr Cov(sum J m_k)` for NS5 with and without Nesterov. Ceiling and baseline: isotropic Gaussian noise of the same covariance (the paper's control).
- **Also checks:** whether sqrt(kappa) lr scaling is justified per matrix (noise-dominated only), against job B of the overnight batch-scaled arms.
- **Kill:** R_K under about 1.1 on all matrices and `delta_beta` above 1 on most: the noise-floor effect is negligible for us; close E15/E16's noise rationale.
- **W's review 2026-10-21 (DM, 23:31):** derivation confirmed with three corrections. Our default momentum is 0.9, so the factor is `sqrt2*sqrt(19) = 6.2` (not 8.8) and the noise-dominated threshold is `c < ~0.006`; the stationary-mean assumption overstates the buffer's signal when the mean rotates within the horizon, so read the figure as an UPPER bound; `modular_opt/optimizer.py` has no Nesterov term. Plugged into the measured EB64 half-batch `c` (0.37 falling to 0.08): `delta_beta` about 1.9-4.7, and about 0.9 even at batch 16 late (c ~0.023). On that reading no matrix is noise-dominated, so the kill condition looks met IN ADVANCE; R_K stays as a cheap confirmation. Caveat to check: that reading used run-level `c`, not per matrix. **Gap found:** `grad_noise.measure` logs `c` on half-batch GRADIENTS only; the plan asks for the buffer-level `c` and the code does not do it (W will add it).
- **sqrt(kappa) rule, W's addition:** job B scales beta to keep the momentum horizon fixed in samples, which keeps `delta_beta` roughly invariant to B; with `delta_beta > 1` the polar step sits near its saturated size, so per-epoch progress falls about as 1/sqrt(kappa) under the sqrt rule and signal-dominated matrices want closer to linear scaling. First data point (W): EB256s (sqrt rule) best 0.1964, EB64 0.1802, unscaled EB128 0.1917; EB128s due about 00:30.

### E18 — Smooth hand-off schedule: FiLM early, crossfade to LatCH, exponential fade to unguided — **RAN 2026-10-25 (W); meters read, listening verdict pending** (planned by CONTINUITY from Kim's proposal)
- **Kim's idea (2026-10-25):** FiLM for the first ~20% of the timesteps, crossfade into LatCH until ~80%, then an exponential fade-out to plain unguided sampling. Motivation (GUI, by ear): LatCH guidance switched off suddenly sounds bad.
- **What already exists (do not rebuild):** E8 (W, 10-15) gated FiLM by sigma (>= 0.4..0.8) and kept 85-100% of its density spread, but the style drift in the house context did not drop (0.26 vs 0.22), so the leak enters early with the density. E7 found FiLM 0.5-1.0 plus LatCH 512 is the sweet spot at constant gains. The early-budget bracket (10-15, above) found LatCH early-only windows damage the content under both weightings. **None of these tested a crossfade or a fade-out.**
- **Why a hard cutoff can sound bad (read from code, not yet measured):** `latch_guided._window_scale` is a rectangle (`m[start:end] = 1`) renormalised to sum 1 over the window. Under the default `alpha` weighting (alpha = 1 - t) the weight RISES toward the end of the window, so `end_pct` < 1 stops the guide at its largest per-step weight, and a shorter window raises the per-step weight for the same rho/mu. So "off at 80%" is the loudest possible place to stop. FiLM has no window at all today (E8 added a sigma gate only).
- **Arms (inference only, thin client of :8056 `/generate`; needs a smooth-envelope option in `_window_scale` and a gain-by-t envelope for FiLM, both small):** (1) baseline: LatCH full window, alpha (the clean reference); (2) the same with `end_pct` 0.8 hard (reproduces the sudden-off); (3) the same with an exponential tail over the last 20% of the window; (4) Kim's full schedule FiLM(0-20%) -> crossfade -> LatCH -> exp fade; (5) E7 sweet spot (FiLM 0.5-1.0 + LatCH 512) at constant gains as the incumbent. Crossfade shapes to keep apart: linear vs raised-cosine, so a shape effect is not blamed on the idea.
- **Instrument (AUDIT THE INSTRUMENT, per E7):** two readouts, achieved density vs target and CLAP drift vs the same-seed unguided render, using W's audited drift meter; FiLM-only is the positive control. **Correction (W, 10-25):** my proposed seam check is mis-specified. The hand-off happens in DENOISING time, not audio time, so no point in the clip can hold a seam; a hard stop can only change clip-wide texture. W measures that with `clip_metrics` plus the disintegration gate (flatness, HF ratio, ZCR, CE drift) next to density and CLAP drift, and a listening card pairing A1/A2/A3 per seed. **Queued by W (SAO `b389f4b`), auto-starts after the stratified-t run:** 108 cells = 4 contexts x seeds x (unguided + 8 arms x 3 densities + arm 6); arm 4c = FiLM 0-0.2, cosine crossfade 0.2-0.8, exp fade 0.8-1, no plateau; FiLM now also takes a step-fraction window. Arm 6 curve = a breakdown into a 16ths build, 0.7 -> 3.9 onsets per beat, mean 2.51.
- **Kill:** (4) is not better than (5) on range-vs-drift AND (3) does not remove the audible step that (2) has. If only (3) helps, the finding is "taper the window", and the FiLM handover is not needed.
- **Open:** the early FiLM slice probably still pulls style in (E8), so (4) may not beat (5) on drift. That is the thing to measure, not assume. **W's build (2026-10-25, stable-audio-3 `21d758b`, SAO `ea0050b`):** LatCH slots take `fade_in_pct`/`fade_out_pct`/`fade_shape` (linear, cosine, exp 1 -> 1%), weights normalised over the plateau so a 20% tail leaves the 0-0.8 budget unchanged; FiLM takes `fade_shape` on its sigma band. Plan ~96 cells (+ arm 4c, crossfade 20-80% with no LatCH plateau, since the length of Kim's crossfade was unspecified; primary reading is FiLM to 20%, crossfade 20-40%, LatCH 40-80%, exp tail 80-100%), on the biggoa DoRA finetune, behind W's ST64 stratified-t training (~3.5 h). Owner: WINTERMUTE (Kim asked 2026-10-25, DM sent; W built E7/E8 and owns the drift meter). Added arm 6: constant target vs a real clip's density curve at the same mean via `target_raw` (Kim's scalar-steering question). Waits for a free GPU.
- **RESULT (W, 2026-10-25 17:40; 108/108 cells, `eval/latch_film_e18_report.py`, page files/evals/latch_film_e18.html, run_meta `result`).** Mean over 2 contexts x 2 seeds, onsets/s for requests 3/6/9, range = 9 minus 3, drift = CLAP to the same-seed unguided render (seed reference: base 0.074, house 0.212):

  | arm | 3 | 6 | 9 | range | drift | range/drift | gate |
  |---|---|---|---|---|---|---|---|
  | film | 5.21 | 6.36 | 8.64 | 3.42 | 0.151 | 22.6 | 0/12 |
  | A1 LatCH 0-1 | 5.54 | 6.62 | 7.58 | 2.04 | 0.078 | 26.2 | 0/12 |
  | A2 hard end 0.8 | 4.93 | 7.11 | 7.75 | 2.82 | 0.113 | 25.0 | 0/12 |
  | A3 exp tail | 4.88 | 7.04 | 7.79 | 2.91 | 0.103 | 28.3 | 0/12 |
  | A4a lin xfade 20-40 | 4.92 | 6.41 | 7.79 | 2.86 | 0.176 | 16.3 | 0/12 |
  | A4b cos xfade 20-40 | 5.09 | 6.59 | 7.80 | 2.71 | 0.112 | 24.2 | 0/12 |
  | A4c cos xfade 20-80 | 5.12 | 6.80 | 8.45 | 3.32 | 0.102 | **32.5** | 0/12 |
  | A5 FiLM+LatCH const | 4.59 | 6.58 | 8.70 | **4.11** | 0.172 | 23.9 | 0/12 |

  (1) **Hard stop vs tail: the meters see nothing.** A3 minus A2, paired over 12: flatness, HF ratio, ZCR, rms, CE, PQ, crest all ~0 and split ~half positive; drift -0.010. A2 differs from A1 mostly by more range (plateau normalisation puts more weight per step on a shorter window) and crest +0.41 (8/12). If the hard stop is audible, it is not in any clip-wide meter we have; the listening card (section 2 of the page) decides. (2) **Hand-off:** A4c (FiLM fading over most of the run, no LatCH plateau) gives the best range per drift of any arm, 32.5 vs A5's 23.9, at drift below FiLM alone; A5 still has the most absolute range. The short-crossfade arms A4a/b add nothing over A3, and linear (A4a) drifts most. So the kill condition is not met on (4): A4c beats A5 on range-vs-drift. (3) **Requests are compressed:** no arm gets below ~4.6/s for a 3/s request on this finetune (unguided 4.6-9.2/s). (4) **Arm 6, real curve:** corr(onset rate in 2 s windows, target) 0.83 / 0.63 / 0.66 / 0.00 for base s1234, base s77, house s1234, house s77, against -0.17 / -0.19 / +0.12 / -0.38 for the constant at the same mean; 3 of 4 follow the curve (n=4, one seed fails flat). Caveat throughout: 4 context-seeds per arm, and drift differences of ~0.03 are small against the seed reference.

## F. Data, captions, corpora (experiments they gate)

### F1 — goa_src caption chain (year pass → Granite → sidecar) and the `latents_sa3` key join — **GATED on Kim**
- Blocks the `goa` sanity arm and any MF-captioned goa training. KIM-TASKLIST.
- Full root-cause/timeline/who-did-what: `docs/goa-captioning-status-2026-08-18.md` (three root causes:
  Granite read_mf path-bug fixed+verified, MF genre-blind captioning fixed via hint+widened LUMI jobs,
  the stale-sidecar-derivative trap hit twice). Status there as of last update: recaption job 21335408
  running; **not re-verified since — my LUMI access lapsed 2026-08-19 (cert expiry, see memory), so this
  entry needs a fresh check from whoever has working ssh before being trusted as current.**
### F2 — Bounded-norm full-FT arms (`fullft_3src_t512_fp32_bounded.sbatch`, hyperball) — **READY, waits on captions**
### F3 — avp/avpaug duplicate split — **GATED on Kim**
### F4 — mp3-vs-FLAC latent sensitivity (goa corpus quality / FLAC re-source) — **PLANNED** (memory: goa-corpus-quality).

### F5 — Glitchy lyrics/vocal conditioning on the ai-music vocal stems — **POTENTIAL (Kim 2026-08-22, "not a lot of data we have")**

**Kim, in passing while the ai-music upload ran:** *"we have lyrics too, not sure if we could in the
future try to train some weird glitcy lyrics model (not a lot of data we have)."* Registered so it
is not lost — it is a real idea with two hard constraints that happen to point the same way.

**THE SUBSTRATE CONSTRAINT (and why it argues FOR the glitchy framing, not against it):** the SAME
latent is **10.766 Hz** (4096× downsample). Phoneme rate is an order of magnitude above that, so
INTELLIGIBLE lyrics are almost certainly not representable in this latent space at all. What DOES
survive that bandwidth is vocal *texture* and prosodic contour. So a faithful lyrics model is
probably closed to us, while a glitchy one is the thing the substrate can actually express. Test
the claim before building on it: run the encodability screen (a linear probe from z for phoneme or
grapheme identity on real vocal stems) — if it reads at chance, that settles the ceiling cheaply.

**THE DATA CONSTRAINT — REVISED UPWARD, and the supervision is better than assumed.** Kim
2026-08-22: *"timecoded lyrics exist"* — and there are **644 `.lrc` files in the tree, 582
excluding Goa Dataset**: home listening 147, Full-on Psytrance 100, Psych/Exp/Acid Folk 57, Goth
50, Punk 48, Retkipakumusaa 39, EBM 34, Spoken word/Rap 16, Rock 16, Prog Rock 13, Proto-trance
11, … So the earlier "≈290 vocal tracks, needs a Whisper pass" estimate was both too small and the
wrong shape: this is **582 tracks of GROUND-TRUTH, TIME-ALIGNED lyrics**, no ASR and no ASR error
floor. Timecoding is what makes it usable at all — conditioning needs to know WHEN, and at
10.766 Hz the alignment is the only part of a lyric the latent can act on. Still small for
generalisation — which for "weird glitchy" is arguably the mechanism rather than the
obstacle: undertrained conditioning on tiny data IS the glitch generator. Frame it as an
aesthetic-instrument experiment, not a capability one, and the kill-criterion changes accordingly
(does it produce something Kim wants to use, not does it transcribe).

**THE FREE WIN, and the reason to note this NOW rather than later:** BS-RoFormer emits a `vocals`
stem. `goa_sep.sbatch` run over the ai-music corpus produces vocal stems for all 5,765 tracks as a
BY-PRODUCT of the separation we want anyway. Whisper transcription can then happen locally at any
time — it needs no allocation. So the LUMI-only half of this experiment gets done for free if the
separation runs; skipping separation is what would make it expensive later.

**Prereqs, in order:** ai-music separation (in flight) → vocal stems → **parse the existing .lrc
timecodes** (no Whisper needed) → the encodability screen above → only then any training decision.
The 574 already-separated tracks (see G-note below) come with vocal stems already, so a chunk of
this is done before the allocation is even used.

### G-note — ai-music corpus has TWO layouts; a naive separation run separates the stems — **ACTIVE (2026-08-22)**

`/run/media/kim/Mantu/ai-music` (182 GB excl. `Goa Dataset` + `Goa_Separated`, 5,765 tracks,
uploading to `$SCRATCH/aimusic_src/`) is **heterogeneous**:
- **already separated + analysed** — `<track dir>/{full_mix,bass,drums,other,vocals}.flac` plus
  `.INFO` / `.BEATS_GRID` / `.DOWNBEATS` / `.ONSETS`. Counts by `.INFO`: Prog & Psytechno 255,
  Progressive Trance & Melodic Techno 146, Chill Dataset 131, organic dance 42 ≈ **574 tracks**.
  `latents_chill` (115) and `latents_organic_dance` (32) are ALREADY pre-encoded locally.
- **raw** — flat `Artist - Title.flac` (+ `.lrc` where lyrics exist), everything else.

⚠️ **`goa_sep.sbatch` over this tree would (a) re-separate the 574 already-done tracks and (b)
treat `bass.flac`/`drums.flac`/`other.flac`/`vocals.flac` as TRACKS and separate the stems.** Its
`.sep_done` marker does not protect us — those dirs were separated by the LOCAL pipeline and never
got one. This is the same shape as the 2026-08-15 incident where a resumable tool's skip-test
("output exists") silently disagreed with what another tool had written to the same path.
**Guard: skip any directory already containing `vocals.flac`, and never admit a stem basename as a
track.** Same guard belongs on the captioning and pre-encode shards (their done-tests must agree
with the separator's, per the lumi-ops shard rule).

**⚠️ THIS FIRED ON 2026-08-23, AND THE GUARD WAS IN THE WRONG PLACE.** `make_caption_shards.py`
got `--mixed-layout` / `--skip-separated` and produced the correct 2860-track shard set — but
**`goa_sep.sbatch` never consumed it**: line 49 built its OWN list with a bare extension `find` and
OVERWROTE the shards. So separation ran 5732 units instead of 2860 (≈ every audio file in the
tree), separating `bass/drums/other/vocals` as tracks and re-separating the 574 already-done
parents; roughly half the compute was waste. The task (`goa_sep_task.py`) does take `--shard`,
which is what made it *look* shard-driven — checking the task and not the sbatch is the error.
FIXED: goa_sep.sbatch now uses pre-made shards when present and warns loudly when it self-generates
(`REGEN_SHARDS=1` forces the old behaviour). **Lesson: a job is only shard-driven if the SBATCH
reads the shards — verify at the submit layer, not the worker layer.**
CLEANUP: the junk outputs are the ones whose directory basename is a stem name —
`find aimusic_stems -type d \( -name bass -o -name drums -o -name other -o -name vocals -o -name
full_mix \) -prune` locates them; the real per-track outputs sit one level up.

### F6 — Fine-tune a KICK separator (BS-RoFormer) — **POTENTIAL (Kim 2026-10-07: "one day when we have the compute and tokens")**

**Why.** The DJ mix v7 stem-transition plan (`docs/superpowers/specs/2026-10-07-dj-mix-v7-transitions-spec.md`) wants the kick
to crossfade while bass and percussion are handled separately, but every separator we have (BS-RoFormer 4-stem, Demucs) stops
at drums / bass / other / vocals. Today "kick" would be a low-band DSP split of the drums stem, with bleed into the rolling
psytrance bass. A kick-only stem would also serve any later per-element control.
**Idea.** Fine-tune a BS-RoFormer (weights and wrapper in `mir/models/bs-roformer/`, `mir/src/preprocessing/bs_roformer_sep.py`,
~5.6x realtime inference) to output kick vs the rest of the drums. Training data candidates: our `Goa_Separated` stems (drums
stem exists, no kick label), synthetic mixtures from one-shot kicks + our own drum loops, and Surge/drum-machine renders where
the kick is known exactly (W's renderer can give clean ground truth). **Kill criterion** (to fix before launching): kick stem SDR
vs the low-band split on a held-out set of real goa clips, and Kim's ear on 10 transitions.
**EVIDENCE 2026-10-07 (G measured, C confirmed with `eval/stem_bass_capture.py`):** BS-RoFormer 4-stem puts the psytrance bassline in `other`/`drums`, not `bass` (median bass capture 0.00 over 7 clips of the v7 corpus). So the useful separator is not only kick-vs-drums but kick vs BASS vs rest in the low band; the fine-tune's target should be a 3-way low-band split. Cheap baselines first: other checkpoints in mir/models/bs-roformer, Demucs, and an HPSS split of the <150 Hz band.
**BAKE-OFF 2026-10-07 (G, 7 clips, bass capture = share of the harmonic <150 Hz energy that lands in the bass stem):** BS-RoFormer 4-stem 0.00, BS-RoFormer SW 6-stem 0.07, htdemucs_ft 0.44 (best); no learned separator reaches the 0.60 bar. So a 3-way low-band target (kick / bass / rest) is the missing capability; htdemucs_ft is the baseline to beat (0.44). Caveat: the HPSS 'baseline' is tautological (~1 by construction) and must not be used as a reference.
**Status.** Not started, no owner (`OWNERSHIP.md`: unclaimed; the mir / audio-feature lane is W's, the DJ pipeline is G's).
Gate: free GPU time (W's H6 holds it until ~2026-10-08) and a token budget decision from Kim.
**Related note (Kim 2026-10-07):** SA3 itself was trained on many stems and single-instrument sounds (the paper note records the
`TrackType: Instrument` caption field on about half the captions), so inpainting an isolated stem is in-distribution; the open
question is separator bleed, not the model.

### F7 — DJ mix v8: extended clips + staged band/stem transition — **PLANNED (owner GHOST-NOTE; guidance from the 2026-10-07 listening of v7b)**
**Why.** Listening to v7b: the plain audio crossfade is clean (kicks, bass, drums, other blend almost unnoticeably); the a2a-smoothed versions add a
stutter / misplaced extra kick onsets, so smoothing is out; remaining faults are few (hi-hat "galloping", rare pitch mismatch). The wish: longer clips (2-3x)
and a more gradual, staged transition. Detail: `docs/superpowers/specs/2026-10-07-dj-mix-v7-transitions-spec.md`; separator result: F6 / S1b (no learned
separator gives a usable bass stem on this material; htdemucs_ft median capture 0.44).
**Steps, each gated by `mixtape_replaycheck_v7.py` (source position) + kick-envelope ncc >= 0.4 + jump screen:** (1) v7c = full-mix band split, LR4 at 150 Hz: bass/kick hand-over on a
downbeat late in the window (`--bandswap --handover-frac 0.8`, code + synthetic tests in `eval/mixtape_assemble_v7.py`, `eval/tests/test_mixtape_v7c_bandswap.py`), the rest
swept (outgoing LP / incoming HP, 16 kHz -> 60 Hz). (2) lengthen clips 2-3x with `eval/outpaint_lengthen.py` / `mixtape_lengthen_and_prep.py` (GPU; decode with
`decode_z0_clamped.py`), then 16-bar windows. (3) multi-band asymmetry on the full mix: percussion highs (> ~800-1000 Hz) first, kick lows last. (4) latent slerp of the overlaid
parts (zero latent is not silence: validity-weighted) and the chroma head to blend pitch. **Kill criterion:** a stage is dropped when the owner's ear finds it no better than v7b plain.
**Status 2026-10-07:** (1) built, synthetic tests pass, NOT yet run on real clips (the clip drive dropped off the bus at 14:11; remount needs root).

## G. Infra that gates experiments
- LUMI allocation ends ~2026-08-22; scratch purge after → pull sanity16 + any ladders first. (A3)
- Auto-render on training finish is STILL not implemented (docs/todos.md "Now / next"). **More
  precise than "not implemented" (C, 08-21, from the B2 case): it exists as a fire-and-forget tail
  INSIDE the training sbatch, so it silently dies whenever the job hits its walltime before the
  tail runs** — B2's job (21416096) TIMEOUT'd at exactly 12:00, right after ep19 finished and before
  its render tail could start; its 3 siblings survived only because their jobs happened to finish
  inside the window. A render that lives inside the training job's walltime is exactly as fragile
  as the training job's own time estimate.
- **Coverage audit (F, 08-21, Kim's ask) — CORRECTED same day (W): scope was manifest coverage, not
  render existence, and those imply very different remedies.** First pass checked ~27 trained-model
  run dirs against `manifest_live.jsonl` and reported "~104 checkpoints, zero rendered clips" across
  the suomisoundi_dora r256/r32×lr sweep (48 ckpts) and `fullft_mixed_avp_latents_sa3_t4096{,_wdfix,
  _wd03}` (53 ckpts). **Wrong framing for both:** real renders exist for both families on the UUID
  drive (already pulled home) — 2141 suomi_r* clips, 54 fullft_mixed_avp_goa_t4096 clips — they were
  simply never INGESTED into the manifest. Kim had already listened to and flagged one of the
  suomi clips as degraded on 08-18, which is the tell a "never rendered" reading should have caught.
  **The actual gap is one `eval/ingest_matrix_cells.py` run, not GPU time** — Kim's call since it
  writes to the board. **A real, smaller gap survives inside that:** W's dry-run found 967 of 3108
  suomi sidecars have no sibling `.wav` — genuinely missing, not just un-ingested; worth identifying
  which cells before calling that sweep complete. B2 (3 ckpts, tgate arm) remains a genuine
  zero-render gap, verified the same way (checked the actual render directory, found nothing) — catch-up
  render `b2_tgate_render.sbatch` queued (`a898f28`). The 1-4-checkpoint early-stage/cancelled tail
  from this week's DDP incident is unchecked against render existence — treat that list as unverified
  by this method, not confirmed-empty. **Standing lesson (W, same pattern he hit twice today
  himself):** "absent from the index" and "was never produced" are different claims — state which
  one a check actually measured.
- GPU mutex on the shared box: hold the lock with the DRIVER's pid across clips (G's per-clip processes
  read as idle/dead). `Misc/gpu_guard.sh`.
- NVMe budget for step-resolution runs: ≤ ~80 % free; thin ckpts to the spectra grid once sketches exist.

### G1 — Rhythm-integrity meter: telling genuine breakbeat from CORRUPTED beat activations — **POTENTIAL (Kim direct, 2026-09-02; GHOST-NOTE listed it)**

**The ask, in Kim's words:** *"how to tell apart genuinely breakbeaty stuff from when the beat
activations get corrupted in a model, I hear that with some less than perfect runs when kicks happen
at wrong onsets, gallop, etc."*

**Why it exists.** Two different things both read as "not four-on-the-floor" to any naive steadiness
measure: (a) a deliberate breakbeat / syncopated / half-time pattern, which is GOOD, and (b) a model
whose beat placement has degraded — kicks landing on wrong onsets, gallop, smeared downbeats — which
is a FAILURE. A metric that cannot separate them will either condemn every breakbeat arm or pass every
corrupted one. Kim currently hears the difference; no instrument we own does.

**The gap that surfaced it (2026-09-02, the FusionOpt-autoscale A/B).** Kim's discriminator between
two arms was *"the beat is not steady"*, and the disintegration DSP screen
(`eval/disintegration_metrics.py`: onsets/s, flatness, zcr, hf) scored that arm as unremarkable
(onsets 7.65/s, mid-pack; hf 0.161, the LOWEST/cleanest of four arms). **The screen is blind to the
axis that decided the verdict.** Audiobox was worse than blind — it ranked that same arm HIGHEST
(CE 6.92). So on this question both standing instruments are silent or actively misleading, and per
the AUDIT-THE-INSTRUMENT rule no "steadiness does not differ" null may be reported from either.
Run + numbers: `Mantu/sa3_lora_runs/fusion_autoscale_vs_adamw_2026-09-01/run_meta.json`
(`round3_2026-09-02.instrument_gap_FLAGGED`).

**Design sketch (not built).** Beat/downbeat activations from madmom (mir venv — SA3's own
`beat_activation`/`downbeat_activation` LatCH heads are the two confirmed-DEAD heads, so use the
extractor, not the heads). Candidate signals, all needing dynamic-range validation before use:
- **Tempogram peak sharpness / entropy** — a genuine breakbeat still has ONE sharp tempo peak plus
  harmonics; corrupted placement smears the peak.
- **Phase coherence of beat activations against the best-fit isochronous grid** — breakbeat is
  syncopated but PHASE-LOCKED to the grid; corruption drifts off it. This is the discriminator I
  would bet on: syncopation displaces onsets to *other grid positions*, corruption displaces them to
  *non-grid* positions.
- **Per-bar pattern self-similarity** — a breakbeat repeats its pattern; gallop/corruption does not
  repeat cleanly bar to bar.
- Onset-deviation histogram vs the grid: multi-modal-on-grid (break) vs broad/smeared (corrupt).

**Kill criterion / the gate this must pass before anyone reports a number from it.** It must show
DYNAMIC RANGE on labelled arms: score a known-GOOD breakbeat set (real corpus tracks + any arm Kim
judged good-but-syncopated) and a known-CORRUPT set (arms Kim flagged: the Fusion 1e-4 "granular and
distorted" arm, the control2 "beat is not steady" arm, plus the suomi clip flagged degraded 08-18),
and the two must separate by more than the within-group spread. It must also beat a trivial baseline
(onset density alone; beat-activation mean). **If it cannot separate Kim's own labels it is not a
meter — file the negative result and stop.** A saturated or degenerate measure is worse than none
(cf. the pitch-blind onset "timing" metric that read 0.795–1.000 across every arm including the
foreign control).

**Where it lands if it works.** A fifth screen in the disintegration gate
(`docs/superpowers/specs/2026-07-20-control-head-disintegration-gate.md`, which today bounds
whitening / hf-blowout / zcr / beat-loss / CE-drift — "beat-loss" is presence, NOT integrity, which
is precisely the hole) and a column on the eval pages. Runner would follow
`eval/control_head_disintegration_eval.py`'s shape: read `clip_metrics.db`, no re-render.

**Related:** the SA3 `beat_activation` / `downbeat_activation` LatCH heads are dead at every gain
(MASTER §5, confirmed twice) — a working rhythm-integrity METER does not imply a steerable rhythm
HEAD, and neither result should be read as evidence for the other. Prerequisite data already exists:
madmom beat/downbeat activations are in the whole-track timeseries (100 Hz, MASTER §2).

### G2 — Diversity / variety board: measure how much our models vary, not only how good each clip is — **POTENTIAL (Kim direct, 2026-10-21; written up by THE-FINN)**
- **Why:** every quality metric we use is per clip (CLAP match, MSS, Mel-SSIM, chroma). Kim's ear has repeatedly reported the opposite problem: the LatCH heads on the post-trained model "all sounded identical" (2026-09-16), mixtape clips "sound very much like the previous one, are we dealing with a very overtrained model?" (09-15), the E3 A/B/C clips "all had a linear structure" (10-15). We never turned those into numbers. Trigger: the Kyutai Pocket-TTS shrinking post (2026-10-20) reports that reward tuning raised UTMOS while narrowing pitch range by about 0.4 semitones, and that point-by-point distillation "blurs toward an average". Any metric-driven run of ours (V6 acoustic matching, Flow-DPO, LatCH guidance) can buy a quality gain with a diversity loss, and we would not see it.
- **What exists:** `eval/gate_b_seed_fan.py` (inter-seed latent variance per band against real inter-crop variance; one prompt, base model, written to test conditional-mean collapse); `eval/clap_degen_summary.md` (drift off the requested genre, which is not variety); the caption-diversity finding in `DISCOVERIES.md`. No shared metric, no table across the model matrix.
- **Proposed measures (CPU-side, on embeddings we already compute):** (1) **seed spread**: N seeds on one prompt, mean pairwise distance in CLAP and in a pooled-latent embedding, against the same number for real clips of that genre; (2) **prompt spread**: one seed across many prompts (does the text change the output); (3) **Vendi score** (effective number of distinct clips) per model, no reference set needed; (4) **memorisation check**: nearest training-set neighbour for each generated clip; (5) **structure spread** for D19, from the self-similarity matrices of 180 s clips; (6) a **quality-versus-diversity plot**, so every new run reports both and a gain bought by collapse is visible. Synth inversion equivalent: how different the 8 best-of-8 candidates are, in parameters and in rendered sound, for one stem.
- **Cheap first pass (lightweight-first):** a diversity table over the existing model matrix renders and CLAP embeddings, no GPU. Decision rule to set before looking: a model whose seed spread is far below the real-clip spread, or whose nearest-neighbour distance to training is near zero, is flagged. Compare the flags with Kim's remembered "sounded identical" cases (the LatCH head clips, the 64-epoch `dora16_avp_originals`, which `docs/superpowers/specs/2026-07-22-eval-quality-and-training-signal-design.md` already calls the worst) as a sanity check.
- **Limits:** embedding-space variety is not creativity. These measures catch collapse and copying; whether a spread is musically interesting stays Kim's ear. **Unverified:** that the existing CLAP embeddings cover the whole matrix, and the Vendi kernel choice.
- **Owner:** unassigned; ask GHOST-NOTE (matrix renders) and WINTERMUTE (CLAP scans) before claiming.

## H. Synth inversion (Surge XT bass: flow + Synth-JEPA)

Code: `stable-audio-tools/scripts/synth_inversion/` (branch `feature/surge-xt-neural-inversion`). Paper:
`papers/arxiv-2609.31024 - Synth-JEPA …` (sidecar has the implementation review). Results of paper-derived
experiments go to the paper's verdict page (directive in `papers/knowledge.md`).

**H1. FX-leak-fixed rerun with in-training accuracy controls — RUNNING** (W, launched 2026-10-06 02:43,
`Mantu/surge_200k_models/fxfix_ladder_ema_b64`, launcher `run_fxfix_ladder_ema.sh`).
*Why:* the previous run (`modular_shampoo_sf_b64`) trained on poisoned renders — Surge keeps hidden
chorus/delay state across renders in one instance, and the 5% random patches carried FX, so every
persistent worker was altered within a few dozen samples (train JEPA 0.13 vs 2.8 on clean renders;
held-out whole-set retrieval 3%). Fixed (`surge_spec.FX_RENDER_ENABLED=False`, regression test).
*What:* same recipe and 78,416 steps; 1.5× peak LR with linear decay to 1/3 over the last 30%; ladder
("bracketed minimal-pair") batches every 4th step on cutoff-low / AEG sustain / FEG amount / AEG decay with a
JEPA ordinal loss (SIGReg skipped on ladders); minibatch OT coupling for the flow; EMA half-life 2000
(online, SF-x and EMA validated + exported); held-out ladder validation. Then the 24 real stems are
inverted with old / online / EMA models through the identical pipeline (`clips_AB/`).
*So far (step 23k):* held-out JEPA 0.46 (old run 2.68), held-out retrieval@512 65.6% (old 3.1%),
train-preset val ≈ train loss (no gap), ladder ρ flow 0.62 / JEPA 0.89; EMA ≈ online.
*Final-ish (step 78k of 78,416, 2026-10-07 02:39):* held-out flow loss online 0.235 / EMA 0.236 / schedule-free
average (x) 0.283; JEPA 0.380 / 0.378 / 0.378; retrieval 78.7-79.5% a2p, 83.8% p2a (chance 0.2%); ladder rho flow
0.66 / JEPA 0.94. **EMA and online are TIED; the schedule-free average is the weaker one on the flow.** (W misreported
this in chat once as "EMA clearly better than online, 0.24 vs 0.30" — the 0.28-0.30 was the SF average, which
`training.log`'s plain "VAL step" line prints; per-kind numbers live in `val_kinds.jsonl`.) Train-preset vs held-out
JEPA gap +0.19 throughout: with 105 train presets, mostly preset-family generalisation (see H4 leak finding).
Real-stem A/B clips + eval page: aavepyora.online/files/evals/synth_inversion.html (built by
`Misc/build_synth_inversion_page.py`; a watcher rebuilds/uploads it as clips land; verdict pending listening).
*Kills it:* real-stem A/B not better than the old model through the same pipeline.
**REAL-STEM A/B RESULT (2026-10-07 03:50, metrics; ears pending) — KILL CRITERION MET ON METRICS.** 24 real phrases,
identical pipeline (flow rerank + phrase refinement + MuScriptor playback), whole-phrase scores: old Oct-5 model MSS
**7.31** / wMFCC 10.84 / env cos 0.911, best MSS on 13/24; new online 7.84 / 10.85 / 0.920 (7/24); new EMA 7.76 / 11.27 /
0.916 (4/24). Far better held-out synth-preset numbers did NOT transfer to real stems. Caveats: refinement narrows the
gap between models; MSS is coarse (see the Synth-JDF sidecar on what MSS rewards); n = 24, one seed. Two more models
being added to the same page (Oct-3 run, new run's schedule-free average) — `clips_AB/comparison.json` is re-scored
with all five when they finish. Read with H5/H6: the domain gap (real vs synth audio), not the FX fix, is the binding
constraint, which is exactly what Synth-JDF targets.
**All five models, same pipeline (2026-10-07 07:53, metrics):** Oct-3 run MSS 7.51 / wMFCC **10.62** / env 0.913,
best MSS on **9/24**; Oct-5 (old) **7.31** / 10.84 / 0.911, 6/24; H1 online 7.84 / 10.85 / 0.920, 3/24; H1 EMA 7.76 /
11.27 / 0.916, 1/24; H1 schedule-free average 7.58 / 11.39 / 0.910, 5/24. The two OLDER runs (both trained before the
FX fix) lead on real stems; H1's best held-out synth numbers come with its worst real-stem numbers. Within H1, the SF
average beats online/EMA on real stems although it is the weakest on held-out synth flow loss (0.283 vs 0.235). Read:
fitting the synth distribution better is not moving real-stem quality (and may hurt it); the domain gap dominates.
Page: aavepyora.online/files/evals/synth_inversion.html (complete, 120 clips).

**H2. Ladder-straightness term (from Semantic Tube Prediction, 2602.22617) — POTENTIAL** (W, 2026-10-06).
*Idea:* STP keeps an LM's hidden-state trajectory locally straight with `1 − cos(h_t − h_r, h_r − h_s)` on
random triples (λ 0.01–0.08; 1/16 data for equal accuracy on Llama 1–8B structured-text fine-tunes). The
synth-inversion analogue: along a single-control ladder the audio embeddings should lie on a locally straight
path — the stronger version of H1's monotonic-distance ordinal loss, and the geometry the JEPA search's Adam
stage and the bracketed refinement assume. *How:* add the term on random ladder triples at λ≈0.02 next to (or
instead of) the ordinal loss; A/B on the held-out ladder metrics and on real-stem refinement. *Gated on* H1's
result. *Not* for the SA3 DiT: non-causal, and musical states should revisit (loops/sections) — the paper's
premise does not hold there. Result → the STP row on the paper-verdicts page.

**H3. Parameter-space extension (AEG/FEG attack, FEG release; later beyond bass) — PLANNED** (W, 2026-10-06).
Needs a versioned parameter spec (codec, prior/manifold re-extraction, both models, inference) so the existing
23-d models keep loading; the ladder recipe's "random attack" needs it. Also: more than the 105 training
presets (held-out gap at step 23k: 0.46 vs 0.25). After H1.

**H4. Synth-knob DIRECTIONS in SAME latent space → knob controls for ANY sound — POTENTIAL** (proposed by C to W, Kim direct 2026-10-06).
*Idea (Kim):* "train this on SAME latents directly, to learn the general directions for the knobs in the latent space, and then
build a synth UI for inference, which could hopefully at least coarsely proxy the knob settings for any sound." Two parts:
(a) **inversion** — SAME latent → Surge knob values (a variant of the current models with SAME latents as input);
(b) **directions** — per knob, one latent-space vector that means "this knob up" whatever the source sound; the UI moves a
latent along it and decodes. Plausible because SAME's semantics are trained in as LINEAR readouts and its decoder is
noise-robust; H1's ladder batches (one knob varied, rest fixed) are exactly the minimal pairs that define a direction.
*Limits:* 10.77 Hz latent (93 ms/frame) ⇒ attack/short-decay are largely invisible; isolated-note → full-mix domain gap;
knobs may be linear only over part of their range (cutoff likely to bend).
*Variant to keep in view (2026-10-06):* the direction may depend on the source latent (a tangent field v_k(z) rather than one
vector per knob). The gate's cross-patch consistency measure tells which: low consistency ⇒ one vector is not enough.
*Gate (cheap, CPU via SAME-S):* encode ~50 ladders/knob; per knob measure (1) cross-patch direction consistency (cosine of
per-ladder displacement vectors vs chance), (2) ladder straightness (cf. H2 / STP). *Then:* apply the cutoff/resonance
directions to a few of the 24 real bass stems and listen. *Kills it:* directions not consistent across patches, or edited
stems decode as artefacts rather than as the knob.
*GATE RESULT (W, 2026-10-06, CPU) — PARTIAL PASS: 2 of 4 knobs have one shared direction.* 200 ladders (4 knobs x
50 val-prior anchors x 8 rungs), each rung the same 4 s 145 BPM bass roll, SAME-S encoded and time-pooled; d = last
rung minus first. Within-knob pair cosine vs the label-SHUFFLED null (mean 0.17, p95 0.22; random 256-d directions
~0.00): **feg_amount 0.62** (identified from its direction alone on 90% of held-out ladders, chance 25%) and
**aeg_decay 0.36** (62%) PASS; **aeg_sustain 0.18** sits at the null (38%), and **cutoff (0.08-0.30 range) 0.09 is BELOW
it** (32%), i.e. no shared cutoff direction at all. Distance tertiles (near/mid/far anchors): cutoff 0.12/0.09/0.05,
sustain 0.28/0.18/0.09, feg_amount 0.74/0.63/0.49, so the shared part fades with source distance (tangent-field
variant). aeg_decay alone is distance-flat (0.39/0.34/0.37), the closest to one global vector. Paths are curved
(straightness median 0.25-0.36), and per-ladder monotonicity along the knob direction (median rho 0.76-0.95) is
only modestly above a random direction (|rho| 0.38-0.63), so it does not count as evidence. Kill criterion met for cutoff
(the knob the gate meant to try first) as a single vector; a cutoff control would need v_k(z). Next, if pursued:
apply the feg_amount and aeg_decay directions to real stems and listen; fit v_k(z) locally for cutoff.
Scripts `stable-audio-tools/scripts/synth_inversion/h4_render_ladders.py` (stage 1, SAT venv) and
`eval/h4_same_directions.py` (stage 2); data and run_meta in `Mantu/surge_200k_models/h4_gate/`.
*FOLLOW-UPS (W + C, 2026-10-06 evening, CPU).* (1) **Note length decides which knobs are readable.** Same 200
ladders re-rendered as quarter notes (~4 frames each, vs ~1 for the 16th roll): sustain null -> clear (cons 0.18 -> 0.50,
pooled-ridge held-out R2 0.23 -> 0.52), cutoff below null -> above (0.09 -> 0.27, R2 0.08 -> 0.18), decay pass -> null
(0.36 -> 0.22; its bracket is short, so on long notes it shapes only the first frame). C, keeping time structure in the
features (mean + std + last-minus-first quarter): sustain and decay recover fully (named 0.92 / 0.84 on quarters), cutoff
does not (R2 <= 0.16 everywhere). (2) **Loudness:** decay is NOT the loudness axis (3% of its displacement on the RMS
direction; consistency survives removal, 0.35, p=0.002); filter-envelope amount is ~40% loudness plus a real remainder.
(3) **SAME-S speaks for SAME-L:** latent cos 0.995, knob-displacement cos ~0.985. (4) **Energy-head gradients** (rms_energy_*,
d head/dz) vs knob displacement, other-knob null in brackets: decay vs bass 0.27 (-0.03), sustain vs bass 0.24 (-0.03),
feg_amount vs mid 0.39 (0.08); cutoff above null on no head. **Net:** sustain/decay/feg are readable linearly once the
phrase and time structure are right; cutoff alone has a source-dependent direction, so it is the target of a learned
map g(z) (C, GPU) vs a cutoff LatCH head baseline, graded by W's held-out-patch + held-out-knob eval with the decode check.
Data for that: `Mantu/surge_200k_models/h4_gate_v2/` (v2: 10 knobs x 200 ladders x 4 rhythms x 8/16 rungs; v2c: 800 cutoff
ladders; SAME-S per-frame latents beside each). Scripts `h4_render_ladders_v2.py`, `eval/h4_encode_same.py`,
`eval/h4_same_directions.py`, `eval/h4_head_alignment.py`, C's `eval/h4_ridge_baseline.py`.
*CORRECTION (C finding, W replicated, 2026-10-06 23:30) — cutoff is NOT simply source-dependent; it is CURVED.* On v2c
(800 cutoff ladders, full 0.08-0.92 range): end-to-end displacement consistency **0.57** (C: 0.56; ~equal for all 4
rhythms), a pooled ridge direction scores 0.51 against it and orders held-out ladders at rho 0.94, beating a cutoff LatCH
head's gradient (0.27) as an edit direction. But per THIRD of the range it falls to 0.19 / 0.29 / 0.27 (low / mid / high;
the low third reproduces v1's 0.09-0.27). So the cutoff path bends: the full-sweep chord is shared across sources,
local steps much less. The v1 "source-dependent" reading came from testing only the low third over 50 patches. Coarse
cutoff control: a global ridge direction is enough. A learned map g(z) is justified only for FINE (local) moves, and
must beat ~0.2-0.3 local consistency, not the 0.56 global ceiling. Statements above that cutoff "needs v_k(z)" are
superseded by this entry.
*CONTEXT, MATRICES, LEAKS (W + C, 2026-10-07 00:00-02:30, CPU).* Data in `Mantu/surge_200k_models/h4_gate_v2/`:
v2 (10 knobs x 200 ladders x 4 rhythms, val prior = only **17 base presets**), v2c (800 cutoff), v2t (same as v2 from the
**105-preset train prior**, exact `archetype_id` per ladder), v2w (fm_depth/aeg_release/aeg_sustain x 600, train prior),
v2f (cutoff/resonance/feg_amount x 400, filter TYPE round-robin over all 10 LP types), v2s (release/decay/sustain x 300 in
a sparse syncopated rhythm, 310-520 ms gaps). SAME-S latents exist for v2/v2c/v2t/v2w; **v2f and v2s still to encode** (GPU
chain queued 2026-10-07 ~01:55 after H1's training exits; `h4_encode_same.py --device cuda:0`; includes a 64-clip CPU-vs-GPU
agreement check because the earlier sets were CPU-encoded).
(1) **Preset leak:** the val prior has 17 presets, so "held-out patches" share families; folding by archetype the cutoff
headline holds (cross-archetype pair cos 0.57 vs same 0.65; ridge R2 0.71 -> 0.65, rho 0.98), and LOCAL cutoff directions
are family-dependent (cross 0.18-0.27 vs same 0.35-0.46). Always fold by `archetype_id`.
(2) **Family transfer** (C, `h4_transfer.py`): ridge directions fitted on val families transfer to train families almost
as well as within (cutoff named 0.52-0.65, feg_amount 0.60). fm_depth, aeg_release, aeg_sustain stay at chance even fitted
on 105 families or with 600 ladders (v2w).
(3) **Context gates the envelope knobs** (`eval/h4_context_dependence.py`, v2t; audible effect = log-mel L1 first vs last
rung): sustain is readable only with a SHORT decay (consistency 0.42 vs 0.01-0.07); decay only with sustain near 0 (0.42 vs
~0.01, even within 0-0.2); feg_decay vs feg_amount effect rho 0.85; feg_amount vs feg_decay rho 0.75 AND its direction rotates
(low/high tercile cos 0.47); resonance consistency 0.09 -> 0.36 with feg_amount. Cutoff is context-robust (direction cos
0.89-0.97 across context extremes). "Sustain unreadable" was a context artefact, not absence from SAME.
(4) **Filter type** (v2t, only LP 12 dB / 24 dB / Legacy Ladder have >= 12 ladders): cutoff and feg directions match across
them (cos 0.93-0.99 to pooled); resonance does NOT: on 24 dB effect 1.95 and consistency 0.32 vs 1.1-1.3 and 0.11-0.12. The
other 7 types need v2f.
(5) **Conditioned fits** (`eval/h4_conditioned_fit.py`, held-out archetypes, temporal features): fitting within the gating
knob's tercile barely changes the DIRECTION (sustain given short decay: 0.64 pooled vs 0.64 conditioned) — context decides
WHETHER a knob is audible, not where it points. Exception: feg_amount given feg_decay (0.52 -> 0.62 and 0.64 -> 0.72 in the
outer terciles). Readout gains small except cutoff in the low-feg tercile (R2 0.66 -> 0.77). Readable terciles: sustain|short
decay R2 0.21, decay|low sustain 0.55-0.57, feg_decay|high feg_amount 0.64-0.68.
(6) **Matrices** (`eval/h4_param_matrices.py`, v2t): knob directions are far from disentangled — cutoff/resonance/feg_amount/
feg_decay pairwise cos 0.71-0.87, aeg_decay ~ aeg_sustain 0.93, fm_depth ~ amp envelope 0.56; a direction-based UI would
confuse knobs within each group. Pairwise is not the whole truth: cutoff's audible effect is explained by single params
R2 0.15 / additive linear 0.13 / trees with interactions **0.62** (held-out archetypes); envelope knobs are mostly one-partner
(decay|sustain single 0.45). Preset-level correlations in the prior are weak except unison~detune 0.94, waveshaper~drive 0.71.
(7) **Release needs gaps.** In r16/e8/q4/leg the gate gap is 8-124 ms, so the next note cuts the tail; v2s uses the sparse
rhythm. Audio meter `h4_gate_envelope_meter.py` (smoke, 4 ladders/knob): release moves the post-gate tail by ~200 ms per
ladder (rho 0.96) and leaves pre-gate decay flat; sustain moves pre-gate decay, tail barely. Kim's point to test on v2s: a
release can sound like a longer decay, so separate them by the gate-to-ramp timing, i.e. compare release vs decay direction
in the latent and check the tail meter. **Pending: v2s encode + meter + latent comparison.**
(8) **Ops lesson:** SAME-S on CPU (8 threads, hours) is what made the box loud at night; use the GPU when free. ROCm 7.14
idle spin thread: MASTER section 5.
(9) **v2s / v2f results (2026-10-07 03:10-03:40, GPU-encoded; CPU vs GPU SAME-S agree: time-mean cos 0.99999,
per-frame rel err 1.3%, so all sets are comparable).**
*Release (v2s, sparse rhythm):* AUDIBLE and correctly separated in audio — the tail meter shows release moves only the
post-gate tail (+88 ms per ladder, rho 0.93) and leaves the pre-gate level alone. In the SAME-S latent it has NO shared
direction (consistency ~0.08 at every sustain tercile) and its mean direction lies on top of decay's and sustain's (cos
0.83 / 0.86; decay vs sustain 0.97). So the latent reads release as "longer decay", as predicted: an ~88 ms tail is about
one 93 ms frame. A release control needs either finer time resolution than SAME or an audio-side (gate-relative) target.
Sustain/decay gating replicates in the sparse rhythm (sustain consistency 0.48 with short decay vs ~0; decay 0.31 with
low sustain vs ~0). Meter gap: decay showed no change in either meter measure — its pre-gate level at gate-off equals
sustain once short notes have finished decaying, so a decay-TIME measure (time to fall N dB after the peak) is needed.
*Filter type (v2f, all 10 LP types x 40 ladders per knob):* cutoff points the SAME way on every type (cos to pooled
0.96-0.99, consistency ~0.5 everywhere); pole count/topology changes its STRENGTH (24 dB, ladders, diode ~8-9 vs 12 dB,
K35, warp types ~5-7 log-mel L1). FEG amount likewise shared (0.93-0.99) except Cutoff Warp (0.80). Resonance is the
type-dependent knob, as expected musically: weak everywhere (effect 1-2 vs cutoff 7), consistency from 0.03 (K35) /
0.07 (OB-Xd 12 dB) to 0.37 (Cutoff Warp), direction 0.84-0.97 to pooled (Diode Ladder loudest and most different).
Caveat: time-mean latent; "does a different thing" may show more in temporal features.
*UI, only after the gate:* NOT a new app — new controls in the inference explorer's **bend tab** (mir `plots/explorer_sa3`),
backed by the existing :8056 render server (`/bend`, `/decode`); see docs/INFERENCE-SURFACE.md.

**H5. Noisy-reference conditioning on the CURRENT flow inverter (no training) — POTENTIAL** (from Synth-JDF 2609.29320, W
2026-10-07). Synth-JDF shows conditioning on partially noised reference audio helps off-manifold; even its clean-trained
"Conditional" baseline improved slightly off-manifold. Test on the 24 real stems with the held-out-half protocol
(`eval_refine_phrase.py` style): mix noise into the inverter's mel input at tau in {1, 0.9, 0.7, 0.5, 0.3, 0.1} (in the
model's normalised mel space), report MSS / wMFCC / env-cos on the held-out half, with and without refinement. Minutes of
CPU. Expectation per the paper: a clean-only model degrades or barely moves; if it IMPROVES, the gap is input-detail
sensitivity. Caveat to carry: the paper's best points may be test-tuned; pick tau on half the stems, report the other half.

**⛔ RENDERER BUG, found 2026-10-07 by ear on the eval page: Surge's delay was NEVER off.** The 10-06 "FX fix" set
the FX slots' Output-Mix (and delay feedback) to 0, but with the init preset's FX A2 = Delay a zero mix does not
silence it: a single 8th note repeats at -11 dB re peak every ~250 ms (a staircase to -100 dB), identical in fresh
and batch-like instances, so it is not state but a permanently live delay. Setting the slot TYPE to Off removes it
(-67 dB at 120 ms). Every render since 10-06 (H1 and H6 training data, refinement, all eval-page clips, old models'
re-renders too) carried it; real stems do not, so it is a built-in domain gap. **Consequences (call made 2026-10-07):
H1 / H6 / the 10-06 checkpoints are treated as near-useless and their real-stem scores as indicative only; retrain
once with everything learned (v3 below) instead of an ablation chain.** Fix: `surge_spec.apply_patch` sets
fx_a1/fx_a2 TYPE to Off unless FX_RENDER_ENABLED (pedalboard drops an Off slot's mix params, so they are only set
when on); test `test_fx_off_single_note_has_no_delay_trail` (46/46 pass). `surge_139_spec.py` has the same mix-only
code (Synth-JEPA 139-param path) and is NOT yet fixed. H6 was stopped at ~step 14k.
**v3 CLEAN RETRAIN — QUEUED (W, 2026-10-07 12:47).** `run_v3_clean.sh`: H1 recipe + `--cond_noise` (H6) +
`--flow_loss mae` (Synth-JDF supp.), FX truly off, 78,416 steps (~19 h at the 225 W cap). Waits behind C's Phase E
until the GPU lock has been free 30 min (G may go first). `v3_post.sh` then inverts the 24 stems with v3 online / EMA /
SF (tau 1) and EMA at tau 0.4 / 0.1, next to the Oct-5 model and H1 EMA RE-RENDERED WITH FX OFF (those two reference
sets render now, on CPU, `v3_clean_b64/clips_ref_*`, and are also scored against their delayed versions in
`clips_AB_refs/` to measure what the delay cost). Page: `synth_inversion_v3.html`; the old page carries a banner.
**Kill:** v3 real-stem MSS not better than the Oct-5 model re-rendered with FX off.
*Update 2026-10-07 17:34:* the first v3 start (14:00) died at 14:10 when Mantu dropped off the bus (it came back as
/run/media/kim/Mantu1; a stale mount still blocks /Mantu until cleared with sudo). Restarted from
`run_v3_clean_home.sh`: identical recipe, outputs in `/home/kim/sao_runs/v3_clean_b64`, manifold read from Mantu1
at startup. Training since 17:34, ~19 h. The FX-off reference clips (`clips_ref_*`, `clips_AB_refs/`) were
finished on Mantu before the drop. The post-step reads real-stem data from /Mantu, so the stale mount must be
cleared before it runs (else rerun v3_post.sh with OUT_DIR=/home/kim/sao_runs/v3_clean_b64).
**H6 — STOPPED 2026-10-07 ~12:40 (trained on delayed renders; superseded by v3).** Original entry:
**H6 — RUNNING (W, launched 2026-10-07 08:44, authorised for the 48 h away window).** `run_h6_condnoise.sh` =
`run_fxfix_ladder_ema.sh` with ONE change, `--cond_noise --cond_noise_clean_frac 0.3`: the flow sees its mel condition
partly noised in standardised space ((1-tau) eps + tau mel; 30% clean, else tau ~ logit-normal(0,1)), tau embedded as
an input; mel stats stored as model buffers (also written into the EMA shadow). Old checkpoints load unchanged; tests
`test_cond_noise_*` (44/44 pass). Out: `Mantu/surge_200k_models/h6_condnoise_b64/`. GPU power-capped at 225 W this week
(~20% slower than H1): if the 30 h wall cap stops it short of 78,416 steps, `h6_post.sh` re-takes the GPU lock and
resumes to the full count (the modular optimizer's LR decay is step-based, so the schedule is unchanged), then inverts
the 24 real stems (CPU) with H6 online/EMA at tau 1.0 and EMA at tau 0.7/0.4/0.1, scores them next to old + H1 EMA
(`h6_condnoise_b64/clips_AB/`), and rebuilds the same eval page. `invert_stem_collection.py --cond_tau` exposes tau.
**Kill:** real-stem MSS not better than the Oct-5 model (7.31) at any tau. **Second day:** decided on H6's result.
**H6. Is it the JOINT objective or just noisy conditioning? — POTENTIAL, the ablation Synth-JDF did not run.** Train our
conditional flow with the audio input noised at a random t_y ~ logit-normal (conditioning-noise augmentation, still no
audio-velocity loss) vs H1's clean conditioning; same steps/data. If it closes most of the real-stem gap, the joint
distribution is not what matters; if not, build the joint DiT (H7b). Needs the GPU (one H1-sized arm).

**H7. Inverter architecture from the Hayes papers — POTENTIAL.** (a) One-token-per-parameter feature tokenizer with the
grouped inverse projection (Synth-JDF supp. §3.1.2) in a small DiT over parameter tokens, replacing the ResMLP's single
whole-vector linear; (b) full joint DiT (mel patches + parameter tokens, per-modality times) if H6 says the joint objective
matters; (c) cheap riders on any new arm: MAE velocity loss (supp.: slight gain), CFG via 10% conditioning dropout (2506.07199)
or the free bottom-edge branch (JDF), RK4 sampling. Synth-JEPA side already uses the per-parameter tokenizer form (Ben Hayes,
2026-10-06: it beats Param2Tok there). Param2Tok (learned mixing assignment) only becomes interesting with permutation
symmetry, i.e. after H3 adds a second oscillator / LFOs.

**H8. MLDR envelope loss (DiffVox 2504.14735) — POTENTIAL.** LDR = log(RMS_short / RMS_long) compared L1 across scales;
targets microdynamics. (a) Replace or add to the 10*(1 - rms_env_cos) term in `refine.py`'s objective and re-run the
held-out-half refinement on the 24 stems (compare to the 11.24 -> 7.78 MSS baseline); (b) add MLDR as an envelope meter
next to `h4_gate_envelope_meter.py` for the envelope-knob ladders (v2s). CPU only.

**H9. Differentiable FX stage after the synth (DiffVox-style) — POTENTIAL.** Real bass stems carry chorus/delay/reverb, but
Surge FX are disabled (state leak across renders). After inverting the DRY patch, fit a small differentiable delay + reverb
+ EQ (DiffVox components or GRAFx) to the residual by gradient descent per stem. Gives FX back without Surge's FX, and is a
per-stem optimisation (no training). Caveat from DiffVox: some FX params are non-identifiable (delay time stuck at init);
initialise from several points.


**Done in this line:** phrase-level renderer-in-the-loop refinement (`refine.py`), fitted on the first half of
each of 24 real phrases and judged on the held-out half: paper MSS 11.24 → 7.78 (better on 23/24), wMFCC
13.77 → 11.46 (22/24); single-note refinement does not generalise (fits a truncated 16th). Cutoff was the
model's biggest miss (moved on 24/24 stems, median ~9 semitones). Now the default last step of
`invert_stem_collection.py`.

## I. Provenance, attribution & interpretability (from the SA3 attribution report, KUANG, October 6, 2026)

*Assessment, verification status and sources: `docs/ai-research/sa3-attribution-report-assessment-2026-10-06.md`.
Every entry is POTENTIAL (proposed, not agreed). The report's own rule governs all of them: **retrieval,
probe activation, memorization and counterfactual influence are four different quantities — never collapse
them into one "percentage influence" number.** A defensible claim is a rank plus an effect under
intervention, with an interval, against matched controls. The header's reviewer briefing applies (linear
chroma readout, signed differential attention, 64 memory-token hubs). Seeds do not reproduce across device
or precision (October 1 laptop characterization: same seed, fp32 vs fp16, correlation 0.65 on CUDA and 0.39
on XPU), so every regenerate-and-compare design below pins ONE device and ONE precision.*

### I1 — Log training events in the next run — **POTENTIAL (cheap; the only item whose value is lost by waiting)**
- Why: the formal-influence and retraining-calibration tiers need to know exactly what the model saw. For a
  finished run that cannot be recovered; every run launched without it can only ever be explained by
  retrieval and probes.
- What: per step — global step, checkpoint id, batch membership as crop keys (source sidecar + index), the
  per-source sampling weight and caption tier drawn, timestep and noise seeds, data-order seed. At
  checkpoints — optimizer-state reference, EMA shadow; 8–16 log-spaced plus milestone checkpoints, denser
  around loss transitions. On the pre-encoded path crop identity is static (A12), so the crop → track →
  duplicate-cluster map comes from the dataset manifest; what is probably missing is batch membership and the
  timestep/noise seeds. **NOT checked** — the training scripts were not read in this pass; confirm before
  building.
- Gate: on a probe run, rebuild one batch from the log and reproduce its loss to tolerance, same device and
  precision.
- Related: A12 (`run_meta.json` already records settings), A10 (`-vN` ladders), F3.

### I2 — Retrain noise floor from the EXISTING 8-replica DoRA ladders — **POTENTIAL (cheap if the checkpoints survived)**
- The suomi `wfleet` DoRA arms are 8 independent single-GCD replicas of one recipe with full ladders to ep19
  (A10): an 8-seed ensemble per arm, i.e. the retrain-variance sample the report never measures. Pick concept
  metrics we already trust (chroma / onset / PQ on the eval clips), render fixed prompts and seeds from each
  replica at one epoch on one device and precision, and report the between-replica spread.
- Use: sets the minimum detectable effect for every removal experiment (I7, I8). The attribution-decay study
  says single-example effects can sit under the noise; this tells us where our floor is before GPU hours are
  spent.
- Kill: if the between-replica spread is at least as large as the effect we hope to detect from removing a
  cluster, single-run removal tests are uninformative at this scale — use replica ensembles as the unit, or
  drop the retraining tier.
- Unchecked: whether those ladders survived the LUMI scratch purge (A10 notes they needed slimming before the
  pull), and whether the replicas differ in data order or only in seed.
- Related: A10, C3 (replica soups), D11 (frame-shuffle null — the same logic: a null before a claim).

### I3 — Retrieval + duplicate-cluster index — **POTENTIAL (Tier 1: CPU, local)**
- Build on the existing curation outputs (MAEST cosine clusters at 0.97 same-work / 0.995 near-identical,
  master variants kept; `docs/goa-archive-buildout-plan.md`) instead of redoing duplicate clustering. Add a
  windowed SAME-latent index (pooled plus token-level), CLAP/MERT, factor-specific MIR (chroma, bass contour,
  beat-relative onsets, stereo width) and fingerprint/landmark hashes for memorization. FAISS exact flat on CPU
  is enough at this scale. Rank at crop/segment level; aggregate to tracks by max, top-k mean and coverage,
  never a plain mean. Keep pitch-shift, time-stretch, EQ and transcode variants as separate search views.
- Output is labelled "resemblance, not influence".
- Gate: a transformed self-copy (e.g. ±2 semitones, ±8% tempo, re-EQ, MP3 re-encode) must be retrieved at a
  recall@10 target set from the first pilot (not invented here). If it is not, the index cannot serve as a
  memorization detector.
- Caveat: much of the big goa set comes from mp3 sources (A12, F4), so latent-space neighbours can reflect the
  codec chain rather than the music.
- Related: F3, F4.

### I4 — Base-vs-fine-tune delta control — **POTENTIAL (cheap; run alongside I3)**
- Every provenance statement is made as a DELTA: render the un-fine-tuned base with identical prompt, seed,
  device and precision, and attribute only what the fine-tune changed. The base model's pretraining data is not
  in any corpus we hold, so "nothing in the corpus resembles this" is not "novel", and "matches a corpus
  segment" is not "learned from it" if the base already does it.
- For adapter arms the delta is the adapter on/off pair; for full-FT arms it is base vs checkpoint.
- Kill: if base and fine-tune are indistinguishable on the metric, there is nothing to attribute for that
  concept.

### I5 — Retrieval-is-not-influence test (duplicate vs upweight) — **POTENTIAL, GATED on I3 + I2**
- The report's best idea. On a small adapter arm: hold out a close duplicate D of a probe segment (excluded
  from training), and upweight a less similar segment U (1×/4×/16×). Retrieval should prefer D; a valid
  influence estimator should prefer U, with the right sign and a monotonic dose-response in the measured
  change. Repeat with pitch-shifted, re-EQed and time-stretched D. Add canary concepts (a synthetic marker
  absent from the corpus, injected at controlled multiplicity) to check that the right source and ordering are
  recovered.
- Natural duplicate material already exists: master variants (curation) and the avp/avpaug split (F3).
- Kill: if no estimator we can run separates U from D at 16×, the formal tier is not usable on this model.
  Report that and stop at retrieval + probes.

### I6 — Concept probes and causal steering on SAME / DiT activations — **POTENTIAL**
- Probes first, on SAME latents: 12-bin chroma (we hold the exact decoded SAME chroma recipe and a linear
  readout), bass pitch contour, stereo ILD (interaural level difference), beat-relative onset phase,
  spectral-centroid trajectory. Splits grouped by artist, release and duplicate cluster so a probe cannot score
  by memorizing a cluster. A probe only shows decodability; causal use needs an intervention — edit a direction
  in SAME latent space and decode directly, then patch the matching DiT representation.
- DiT hooks: residual before/after attention and MLP, differential-attention outputs (SIGNED — thresholding is
  invalid), cross-attention, AdaLN scale/shift; treat the 64 memory tokens as hubs. Time-conditioned top-k SAEs
  per diffusion-time bin; train at least three dictionaries and test feature matching, since SAE features are
  not canonical across runs.
- Goa concepts to operationalize: bassline (low-band pitch contour, 16th-note periodicity), acid sweep
  (resonant spectral-peak trajectory), rolling/offbeat rhythm (beat-relative onset histogram), modal melody
  (tonic-relative intervals), harmonic movement (beat-synchronous chroma transitions).
- Gate per concept, in order: held-out probe accuracy → specificity control → dose-response steering →
  necessity by ablation → reconstruction check → Kim's ears.
- Kill: the probe does not beat a trivial baseline on held-out groups, or steering moves the metric without
  Kim hearing it.
- Related: D8, D9, D10 (same readout-direction family).

### I7 — Formal influence on a shortlist, validated by removal — **POTENTIAL, GATED on I1 + I2 + I5**
- Only after I5 shows an estimator can tell exposure from resemblance: projected-gradient similarity (TRAK /
  Journey-TRAK style; flow-matching velocity MSE with COMMON timestep and noise draws for train and query
  gradients, integrated over timestep bins) and EK-FAC on retrieval- or feature-shortlisted candidates, on an
  ADAPTER arm first (small trainable set). The measurement is a defined scalar (a concept metric, or a
  contrastive "acid sweep minus matched control"), not whole-output loss.
- Validate by intervention: top-k vs matched-random removal (matched on artist, duration, key and embedding
  density) and leave-cluster-out regeneration at fixed device and precision; score with LDS (linear
  datamodeling score) if subset retrains are affordable.
- Cost note (my arithmetic, untested): full-FT per-example gradients come to about 456 PFLOP per checkpoint
  and timestep draw over 168 000 half-minute segments (≈ 4.2 GPU-hours at 30 TFLOP/s effective); 16
  checkpoints × 8 draws ≈ 540 GPU-hours — LUMI-scale, not 9070 XT-scale. Adapter arms skip the weight-gradient
  part of the backward pass.
- Kill: the estimator's top-k removal does not beat matched-random removal by more than the I2 noise floor.
- Report form: rank, sign, effect under intervention, seed stability, bootstrap interval, method agreement.
  Never "Track X contributed 12%".
- Unconfirmed: the report's cost and accuracy claims for MAGIC / EK-FAC / TrackStar conflict with a search
  summary (assessment §3); read the Bergson paper before choosing an estimator.

### I8 — Attribution decay at our scale; the cluster as the unit — **POTENTIAL, GATED on I2**
- The Nature Communications 2026 finding (image diffusion, from-scratch ensembles, 256 to over 160 000 images)
  is that individual-example removal effects vanish with data scale. Our setting is a fine-tune on a few
  thousand to about 12 500 crops with deliberate near-duplicates, which that study does not cover. Measure it:
  vary corpus size and the removal unit (crop / track / duplicate cluster / artist).
- Possible design (my adaptation, untested): train K adapters on disjoint shards and "remove" a shard by
  dropping the adapters that saw it, after the diffusion-ensemble idea. Costs: K small trainings up front, and
  members that are weaker than one adapter trained on everything.
- Read: if effects vanish at the cluster level too, provenance claims for this model should stop at
  "resembles" (I3) and concept-level evidence (I6).

### I9–I14 — EleutherAI instruments for the melody wall (KUANG, October 6, 2026)
*Assessment, verification status, cost arithmetic and sources:
`docs/ai-research/eleutherai-interpretability-tools-assessment-2026-10-06.md`. Only the IDEAS port; no repo's
code drops into SA3. I9–I11 share ONE forward-only harness (checkpoint or ladder, fixed eval crops, sampled
(t, ε), hooks on the SA3 blocks, ONE device and precision pinned); I14 should gate any meter I10/I11 rely on.
KUANG's ranking by decision value per cost: I10 ≈ I9 > I14 > I11 > I12 > I13. All cost figures are
arithmetic (2·N FLOP per token, 1.4B parameters, 512 frames per crop, 30 TFLOP/s effective), untested.*

### I9 — Tuned lens on the DiT residual stream: where in depth does melody commit? — **POTENTIAL (cheap; forward-only)**
- Source: `EleutherAI/tuned-lens` (affine per-layer translators, KL to the final distribution, through the
  unembedding; HF-LM coupling inferred, source not read). Port the idea, not the code. The SA3-Medium DiT (from
  Stability's MLX port): 24 blocks, d = 1 536, readout `project_out` + 1×1 conv, no final norm stated.
- Build: per-block residual-form translator `h + A_ℓ(t)·h + b_ℓ`, with A_ℓ per timestep bin or FiLM from the
  timestep embedding (adaLN makes residual coordinates mean different things at different t); frozen readout;
  loss = MSE to the model's own final output (self-distillation), also reported against the ground-truth
  target; train on conditional AND null-conditioned passes (CFG); position-wise over latent frames, skipping the
  64 memory-token positions at readout.
- Output: R²_melody(block, t) via the linear chroma readout (extends B2's t-curve with depth; fold into
  `eval/melody_r2_vs_t.py`), a per-frame "prediction depth", and block-ℓ x̂₀ predictions decoded through SAME
  to listen to.
- Cost: ≈ 57M translator parameters; ≈ 1.3 h per 100 000 crops at 512 frames. Pin device and precision — XPU
  fp16/bf16 gives NaN for medium-class models, so use fp32 on the Arc.
- Informs: B4's melody-first noising vs injection at chosen blocks (per-block `local_add_cond` inlets); B7
  adapter placement.
- Kill: translators fail to beat the identity-translator (plain logit-lens) baseline at early blocks, or
  R²(block, t) is flat — melody decodes only at the final block — so the depth axis adds nothing.
- Related: B2, B4, B7, D8–D10, I6.

### I10 — Training-time statistics test ("features across time" for SA3) — **POTENTIAL (forward-only; surrogate design is the open work)**
- Source: `EleutherAI/features-across-time` (Pythia n-gram scripts, plots, vision scripts; MIT; "sloppy code"
  per its authors). Appears to accompany arXiv 2402.04362 — inferred. Method as I understand it, not read
  here: per checkpoint, compare model behavior on real data against synthetic data matched to order-k
  statistics; the gap opens when the model learns structure beyond order k.
- Port: in SAME latent space, velocity/denoising MSE at a few timesteps on real crops vs surrogates: (a)
  per-channel Gaussian matched to mean and covariance, frame-iid; (b) frame-shuffled (D11); (c)
  phase-randomized (keeps the power spectrum); (d) beat-block-shuffled (beat-aware crops exist); optionally (e)
  chroma-transition-matched resampling. Run across A12's 24 rungs and the A10 replica ladders.
- Cost: 256 crops × 4 timesteps × 5 conditions ≈ 7.3 PFLOP ≈ 4 min per checkpoint; 24 rungs ≈ 1.6 h.
- Why: judges arms WITHOUT rendering (B2's three checkpoints were never rendered); tests B1–B5 as a family
  (does reweighting open a melody-level gap earlier?); a structure term for soup selection (C2); A12's
  "lightly-trained property" question.
- Gate / kill: the curves must separate arms Kim has already labeled (good vs corrupted, as in G1) and beat a
  trivial baseline (training loss alone). If gaps open early on spectrum statistics and never discriminate,
  file the negative result. Kim's ears remain the arbiter.
- Related: A10, A12, B1–B5, C2, D11, G1.

### I11 — Attention-pooled concept probes, MIR-labelled — **POTENTIAL (reimplement; do NOT vendor)**
- Source: `EleutherAI/attention-probes` (`train_probe()`, `AttentionProbeTrainConfig`; input tensors
  `[N, T, D]` + mask + labels, so model-agnostic). Based on MOSAIC, which its README calls unlicensed; GitHub's
  license endpoint returned 404 (normally: no license file). Reimplement the small attention-pooling probe
  rather than copy the code; any use beyond private is a Legal question (third-party terms).
- Use: clip-level concept labels with time localization (attention weights), on SAME latents (D = 256) and DiT
  blocks (D = 1 536): acid sweep, bassline, rhythm integrity (G1), modal vs chromatic. Labels from the existing
  MIR features (about 23 000 tracks), which inherit their classifiers' errors (genre-blind and ungrounded
  captions were found before).
- Storage: 10 000 clips × 512 frames × 1 536 dimensions in 16-bit ≈ 15.7 GB per (block, timestep) — pool,
  subsample or stream.
- Gate: grouped splits (artist / release / duplicate cluster); must beat trivial baselines (onset density,
  beat-activation mean for G1); a decodable feature is not a used one, so causal checks per I6.
- Possible landing: concept readouts in the Latent Forge statistics panel (M10).
- Related: G1, I3, I6, E3, E4.

### I12 — Behavioral-basin / sharpness proxy for "healthier optimum" — **POTENTIAL (cheap first step; tyche only if it discriminates)**
- Source: `EleutherAI/tyche` (Monte Carlo basin-volume estimator; HF CausalLM, Pythia and ConvNeXt/CIFAR-10
  adapters; Apache-2.0). Its README warns it "can lead to dramatic underestimates of basin size"; the more
  precise `palamedes` module is work in progress. SA3 would need a model adapter and MSE-on-velocity behavior
  in place of token KL.
- Step 1 (own code, about 50 lines): behavior/loss drift vs random-perturbation scale and along checkpoint
  interpolation paths, for A12's rungs (5e-5 vs 1e-4/2e-4), DoRA vs full-FT, and A10 replica pairs. Step 2,
  only if step 1 discriminates: tyche volume, for a defensible figure in DISCOVERIES.
- Cost: 1 000 perturbations × 16 crops × 512 frames ≈ 23 PFLOP ≈ 13 min, forward-only (perturb adapter
  parameters only for adapter arms).
- Why: A12 selected on "robustness under guidance overdrive" with no quantitative proxy; soupability might
  track basin overlap (my inference, untested).
- Kill: perturbation curves do not separate arms Kim has heard as healthy vs melting.
- Related: A1, A2, A6, A12, B12, C1–C7.

### I13 — Cross-layer transcoders (CLT) — **GATED on I6's per-layer SAEs (POTENTIAL, expensive)**
- Source: `EleutherAI/clt-training` (fork of `sparsify`, MIT; HF decoder-only LMs; activations on the fly via
  module-name hooks; TopK; `torchrun` DDP / `--distribute_modules`; CUDA PyTorch — ROCm and kernel support
  unverified). Another donor: CLT-Forge (arXiv 2603.21014).
- Use as a DONOR only (TopK transcoder modules, FVU loss, trainer). New work: data layer = our pre-encoded
  crops at sampled (t, ε, prompt); hooks = SA3 modules; target = the feed-forward output BEFORE the adaLN gate
  (the gate depends on t); input = what the FF sees after modulation; time-binned training (features vary
  with t).
- Size: decoder = F × 1 536 × 300 layer pairs ≈ 1.4B parameters at F = 3 072 (2× d) and ≈ 5.7B at F = 12 288
  (8× d).
- Limits: it decomposes feed-forward layers only; melody is "relational" (B2) and I infer it lives in
  attention, which a CLT does not decompose; attribution graphs through signed differential attention, the 64
  memory-token hubs and text cross-attention are an open problem (header briefing).
- Gate: build only if I6's per-layer SAEs show features duplicated across layers AND feature-level steering
  results justify circuits. Kill: per-layer SAEs already deliver the steering and probe results we need.
- Related: I6, I9.

### I14 — Red-team our meters before steering on them — **POTENTIAL (cheap insurance; gate before AID / FK-Flow)**
- Source idea: `EleutherAI/classifier-latent-diffusion` (CIFAR-10/MNIST: DDIM inversion → classifier →
  adversarial search in latent space; 6 commits, dormant, no stated license). The repo is not usable; the
  notion is.
- Test: for each meter we plan to steer or select on (whitened-chroma recurrence, PQ, the R²(t) gate, the G1
  rhythm meter), run a latent-space search that maximizes the meter score — gradient through decoder and meter
  where differentiable, else CMA-ES or random restarts over latent/noise perturbations — then check Kim's ears
  and the disintegration gate. If a cheap search maxes the meter while the clip degrades, the meter is not
  safe as a reward.
- Why: meter history (onset-timing metric read 0.795–1.000 on every arm including the foreign control; PQ
  sparse-material blind spot; CE about zero correlation with Kim's judgment), and AID / FK-Flow use the
  recurrence meter as their reward (Gemini assessment, 2026-07-15).
- Gate: a meter passes if its maximized clips are still judged musical; a meter that fails becomes a SCREEN,
  not a reward.
- Related: B2, D6, G1.

## Done / superseded (this week)
- A1 local arms (bs1/accum8/fusion/cos/snr/cos+snr) — see A1/A2. · E1. · C5 rendered. · Weight-space
  forensics kit + Gram/spike result (DISCOVERIES 08-18). · Paper reads filed: 2605.10468, 2512.04926, EDM2
  §3, 2602.19512, 2608.15103, 2608.06717 (`papers/knowledge.md`).

### M1. Mixtape shortlist: latent-norm clamp and guide_anchor re-render — GHOST-NOTE, 2026-10-20 (Kim's ask)
Shortlist `eval/mixtape_audit_kim_shortlist_2026-09-15.json` (141 clips: 105 rated 5-star, 36 unrated genre-fusion, 26 of them from dora128adj_avp_8ep_ptm). 105 have a saved z0: median std 1.37 vs healthy ~1.13, 46 above 1.4; the 36 gf2 clips have none.
- **z0 clamp (cap 1.4 / 1.15, whole-latent scale, plus soft-limited original): NEGATIVE.** Kim's blind audition (via W, 2026-10-20): the original is systematically cleanest; the clamp adds a tinny comb-filter colouring in the highs, worse at 1.15 than 1.4; the limiter arm is the same clip, just louder. The page was NOT loudness-matched (orig and lim both peak-normalised to 0.8913, lim plays ~3 dB louder), so "limiter sounds fine" proves nothing. Reading: a latent std of 1.4-1.8 is not the distortion; scaling it damages the decode. Only 8 of 74 clips exceed 1.8, 3 exceed 2.0. Links: `eval/mixtape_z0_clamp.py`, `Misc/build_mixtape_clamp_page.py`, `Mantu/sa3_lora_runs/mixtape_z0_clamp_2026-10-20/`.
- **guide_anchor smoke (air head +/- anchor 1.2, 5 clips, 25 renders): meters only, NOT yet heard.** hf_ratio drops strongly with the head and further with the anchor (4 of 5 clips); crest falls 6-8 -> ~5 (a cost). Gain 8448 and 2112 arms are identical (server normalises gains). `eval/mixtape_anchor_smoke.py`, `Mantu/sa3_lora_runs/mixtape_anchor_smoke_2026-10-20/`.
- **1.6/1.5/1.4 on the 17 clips above std 1.7: PARTIAL (Kim's verdict via W, 2026-10-21).** The timbre shift is not on every clip; target should be RELATIVE to the HF-ratio change (e.g. ~15% reduction), not a fixed cap. cells.jsonl: same cap moves hf_ratio -4..-21% at 1.6 and -9..-29% at 1.4. Next designs: (a) z0*0.85 (and 0.92) for every clip over threshold; (b) per-clip bisection on scale until hf_ratio falls 5/10/15%. Both run on CPU decode or GPU (~4 s) after W's lock ends ~06:45. BUILT 2026-10-21 (17 clips above std 1.7, arms orig/x0.92/x0.85/hf5/hf10/hf15): flat x0.92 drops hf_ratio 3.9-9.1% (median 5.5), x0.85 7.0-16.3% (median 10.7); the per-clip arms land 4.5-5.2 / 9.1-10.3 / 11.4-15.4% (one clip hit the 0.5 grid floor at hf15) with scales 0.90-0.96 / 0.70-0.92 / 0.50-0.86. Page ~/evals_aac/mixtape_relcut.html (loudness-matched, blind), run `Mantu/sa3_lora_runs/mixtape_z0_relcut_2026-10-21/`, script `eval/mixtape_z0_relcut.py`. Not yet heard.
- Open: higher caps (1.8/2.0) on the few clips above, loudness-matched; an ear check of the smoke clips; the 3x outpainting and the full re-render are NOT queued.

### SJ1. Synth-JEPA Flow-DPO on S5 (beta 30 / 100 / 300) — KUANG runs, 2026-10-19; Kim's verdict 2026-10-21
- Trainer `stable-audio-tools/scripts/synth_inversion/train_flow_dpo_v5.py` (Diffusion-DPO for the flow inverter; pairs from
  `dpo_pairs_v5.py`, rewards MSS + bass-energy + modulation-spectrum distance). Run dirs are not on this desktop's drives
  (KUANG's laptop); numbers in `blog/2026-10-19-synth-jepa-from-day-one.md` section 10 (beta 300: phrase MSS 6.09 -> 5.99,
  Mel-SSIM 0.278 -> 0.260, centroid error 778 -> 803 Hz; held-out synthetic best-of-8 3.38 -> 4.24).
- **kim_feedback (2026-10-21, chat via WINTERMUTE, verbatim):** "I have audited the first dpo results very carefully, it was very
  creative although not always universally better, I suspect it would benefit from longer training"
- Reading: by ear more creative / varied than S5, not uniformly better; the meters (mixed) agree on "not uniformly better".
  Next, per the verdict: a longer DPO run (on S5 or V6 C, not decided). Copy this verdict into the DPO runs' sidecars when the
  run dirs are reachable.

### SJ2. On-policy Flow-DPO rounds 2-4 on V6_C (beta 100) — WINTERMUTE, 2026-10-21 evening
- Why: the SJ1 verdict ("would benefit from longer training"); round 1 (dpo_v6c_b100) had used up its fixed pair set
  (held-out DPO loss rising 0.91 -> 1.00 over its 2000 steps), so "longer" = fresh pairs from the current policy each
  round, that policy as the reference. Round-1 recipe otherwise (metric mss=1,logmel_l1=0.5, lr 1e-5, 2000 steps).
  Runner `eval/run_overnight_dpo_batch_20261021.sh`; runs `/home/kim/sao_runs/dpo_v6c_b100_r{2,3,4}`.
- Held-out synthetic, 1 draw, MSS (lower better): V6C 6.14, R1 5.33, R2 6.15, R3 5.31, **R4 4.86**; modspec_dist R4 best
  (0.549 vs 0.593). The rewarded metric keeps improving, not monotonically (R2 fell back to the base).
- Real stems, mel_ssim (the metric that tracked the ear, rho +0.67): r1 +0.030 [-0.002, +0.063] p 0.07, r2 +0.018 p 0.13,
  **r4 -0.006 p 0.71** vs V6_C. The proxy improves while the ear-aligned metric returns to baseline: more rounds of MSS
  reward over-optimise a reward that does not track listening (MSS rho +0.08). Note r1's earlier +0.042 (p 0.004,
  V6_1_RESULTS) did not replicate at that strength in this eval run.
- Next if continued: rank pairs by mel_ssim_dist (stored in the pairs) instead of MSS. Listening page:
  `/home/kim/sao_runs/stems_v6_c_dpo_rounds/listen/index.html` (local). kim_feedback: none yet.
