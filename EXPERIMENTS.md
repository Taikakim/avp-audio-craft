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
proxy of Kim's ear** (W, 08-21, fit on 668 real A/B votes: PQ-alone 77.6%, every other metric added
makes it WORSE except CLAP, which is coverage-limited) — CE has ~zero correlation with his judgment
(08-19 finding), stop leaning on it · **per-checkpoint p-values across the campaign are
pseudo-replicated** (810 checkpoint rows come from ~265 actual runs) — at RUN level only dataset,
alpha, rank, optimizer, frames_T survive; batch/lr/precision go non-significant. Read any
parameter-table claim, including ones already in this file, against that.

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

### A4 — Full-FT AdamW: the MATCHED control for the drone family — **READY → Kim's submit 08-21 (`fullft_fleet.sbatch`)**
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

### A9 — Bread-and-butter AdamW production fleet (winning recipe × 4 datasets × 2 seeds) — **RUNNING (21422678-81 seed1, 21422863-66 seed2)**
- **Kim direct:** copy `winning_avp_t1024_a45_fp32` (DoRA-rows r128 α45, AdamW lr 1e-4 constant, fp32,
  T1024, 20 ep) onto suomisoundi, big goa, the 3-source mix — plus **avp itself as the control** that
  isolates the one deliberate delta (1-GCD batch 4 → 8-GCD DDP batch 8). 8 × single-node 8-GCD jobs
  (multi-node DDP unsolved), ~680 GPUh. `lumi/sbatch/winning_fleet.sbatch`.
- **Gate:** constant-LR AdamW ⇒ judge by SOUPS/centroid (C1/C2 machinery) + trajectory stats + Kim's
  ears; per-arm DDP verify (LOCAL_RANK 0..7). Links: A1 (walk-vs-drift predicts these diffuse), C1.

## B. The melody wall

### B1 — #59 subspace-weighted RF loss, v3 melody-selective basis, K∈{2,5,12} — **READY (LUMI, Kim's next-night submit)**
- **Findings:** v2 basis had ZERO melody-vs-codec selectivity; v3 (whitened CSP) 5.1× SNR
  (`eval/musicology/melody_selective_subspace_2026-08-06/`). SAME eigen-spectrum 786× anisotropic, melody
  in the suppressed 188/256 eigendirections; v-trained base under-recovers them 8.3× at σ=.2 (E1 pre-test).
- **How:** `lumi/sbatch/subspace_loss_v3sel_grid_mt.sbatch` (4 arms now). Basis `lumi/melody_subspace15_selective_v3.npz`.
- **Gate:** whitened-chroma recurrence (`eval/melody_wall_analysis.py`) + Kim's ears vs `lreq` baseline.
- **Caveat:** recipe is AdamW bs4 constant-LR (= the diffusing regime, A1) — kept for comparability; if all
  arms random-walk, rerun the winning K under Fusion-braked (A2).

### B2 — R²(t)-gated melody term (arm 4 of B1) — **READY (shipped 08-19)**
- **Why:** melody recoverable only in a t-window (2-crop probe: R²_melody .995/.744/.011 at t=.05/.5/.95 vs
  rest .997/.829/.239); a flat K spends most of its budget where melody isn't representable. Lemma A.2 of
  2602.19512: per-t weighting is the isotropic learned-schedule case (their best FFHQ result).
- **How:** `stable_audio_3/training/tgate.py`, `--subspace-loss-tgate`, curve from `eval/melody_r2_vs_t.py`
  (the arm self-measures if `lumi/melody_r2_vs_t_medium-base.json` is absent). Modes r2 / r2sq / deficit.
- **Kill:** no movement in recurrence or ears by ep10 → B4 gets the budget. Reference 48-crop curve: queued locally.

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

### C3 — Post-hoc power-EMA logging in train_lora (EDM2 §3) — **PLANNED (small)**
- Two power-function EMAs snapshotted during training reconstruct ANY EMA length post hoc; trivial for
  adapters. Makes every future run fully souprable; supersedes hand profiles.

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

### D11 — Frame-shuffle null on Tier-2 air (external queue "0b" — the one genuinely open Tier-0 gate) — **GATED on 1 GPU-hour**
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
- Auto-render on training finish is STILL not implemented (docs/todos.md "Now / next").
- GPU mutex on the shared box: hold the lock with the DRIVER's pid across clips (G's per-clip processes
  read as idle/dead). `Misc/gpu_guard.sh`.
- NVMe budget for step-resolution runs: ≤ ~80 % free; thin ckpts to the spectra grid once sketches exist.

## Done / superseded (this week)
- A1 local arms (bs1/accum8/fusion/cos/snr/cos+snr) — see A1/A2. · E1. · C5 rendered. · Weight-space
  forensics kit + Gram/spike result (DISCOVERIES 08-18). · Paper reads filed: 2605.10468, 2512.04926, EDM2
  §3, 2602.19512, 2608.15103, 2608.06717 (`papers/knowledge.md`).
