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
  substantially cleaner than reported.** The old-goa comparison (75.9%) is still re-running on the
  same corrected method, so **the cross-corpus gap is not currently established in either
  direction** — read the "corpus not optimizer" guard as *under re-audit*, not as a supported
  premise, until both sides are re-measured on v2. The `goa_big_quality_matched` (4,111) list this
  entry's follow-up depends on is ALSO invalidated by the same v1 bug and needs rebuilding first —
  don't re-point A11's follow-up at it until that lands.
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

### B7 — MIR-timeseries conditioning: rank-32 DoRA + per-frame inlet vs decoupled cross-attn (Kim direct 2026-08-21) — **RUNNING: 3 torchrun arms — 21430167 all, 21430168 melody, 21430169 rhythm — C owns**
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
  fullft_fleet arms (EMA on) > fullft_mixed_wdfix > precision-ladder fp16 (Kim's ear pick).

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

### C4 — cfg-dependent optimal soup/EMA length — **POTENTIAL (test on C1's boards)**
- EDM2 Fig 6: optimal EMA ~13 % no-CFG vs ~2 % at cfg 1.4 → Kim's cfg7 vs cfg16 cells plausibly want
  different soups. Render both cfgs for the same soups and compare.

### C5 — Spectral-repair probes (remove/keep top-1 direction of a broken arm) — **DONE, awaiting Kim's ears**
- `eval/spectral_repair_lora.py`; 6 rendered sets under `lumi_runs/analysis/task_vector_gram_goa_2026-08-18/renders/`.
  DSP pre-read: removing top-1 restores brightness, not punch; the spike is LoRA-structure, not the pathology.

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

### D12 — Contour-token conditioning stack (external drafts LANDED in mir; Q1 next) — **READY (code) / PLANNED (Q1)**
- `mir/src/conditioners/{morph_grids,contour_codes,contour_streams,contour_stats}.py` + regression
  tests (mir 42c3a83): monotone-invariant K&P dense-rank contour tokens over frame/event grids,
  redundancy judged by CONDITIONAL ENTROPY (agreement provably blind cross-alphabet; nested-L
  H(L2|L3)=0 reproduced in tests). Feeds Head-B/prepend/B4 target design.
- **Q1 (do next, ~10 lines):** an IOI/duration morph stream on the note-onset grid — rhythm is the
  channel the model KEEPS (beat R² 0.80 @ L14); all six current streams are pitch/energy-derived.
- Parked from the same drop: Q3 distance-graded hard negatives, Q4 basis-space interpolation,
  Q5–Q7 (gated on a Phase-B head). Their `measure_contour_codes.py` was NOT in the zip — ask the
  external agent or re-derive if Q2 (min H(A|B) on real audio) is picked up.

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

## Done / superseded (this week)
- A1 local arms (bs1/accum8/fusion/cos/snr/cos+snr) — see A1/A2. · E1. · C5 rendered. · Weight-space
  forensics kit + Gram/spike result (DISCOVERIES 08-18). · Paper reads filed: 2605.10468, 2512.04926, EDM2
  §3, 2602.19512, 2608.15103, 2608.06717 (`papers/knowledge.md`).
