# The onset-density control-adapter story — a narrative reconstruction

*Started 2026-07-12 (GHOST-NOTE), on Kim's ask: the flat `control_runs/onset_*` /
`_misc_uncurated_runs` dump pages are "kind of useless now" — this doc is the
narrative that should sit on the landing page instead: how the experiments went,
where each falls in the timeline, and which checkpoint is the actual current
"bpm-controlled, quite good working version."*

**Status: DRAFT, first pass reconstructed from WORKLOG.md + journals + on-disk
`run_meta.json`/logs. Not yet fleet-reviewed. CONTINUITY and WINTERMUTE are
annotating/correcting — see the Gaps section at the end for exactly what needs
their memory, and MASTER.md / the dialogue log for their follow-ups once posted.**

Sources: `WORKLOG.md` (full), `profiles/continuity.journal.md` (full),
`profiles/wintermute.journal.md` (full), `docs/checkpoint-hall-of-fame.md`,
`docs/todos.md`, `DISCOVERIES.md`, plus `run_meta.json`/`onset_eval.json`/
`train.log`/`_meta.json` sidecars under `/run/media/kim/Mantu/sa3_control_runs/`.

---

## 1. Chronological timeline

### Phase 0 — Riffer (reference-conditioned adapter), the false start that pointed the way (2026-06-19/20)

- **2026-06-19:** `sa3_control/` "riffer" — a decoupled cross-attention adapter
  conditioned on a *reference audio clip* — works, but only narrowly, at lr1e-4
  (peaks ~step 6000, then declines); heavier LR (1e-3) mode-collapses.
  **Metric lesson that recurs constantly later:** chroma correlation to the
  reference **cannot see mode collapse** — a collapsed adapter that outputs the
  same thing regardless of reference still scores ~0.9 chroma corr against any
  Goa reference, because Goa tracks share keys. Fix = cross-reference audio
  diff, not chroma corr.
- **2026-06-20, optimizer bracket:** 200-track LR × optimizer bracket — AdamW
  (2e-4/4e-4/6e-4+warmup, crop2048) vs **FusionOpt** (SF-NorMuon / SF-AdamW,
  5e-5, crop1024 — FusionOpt OOMs at crop2048 without checkpointing, forcing
  the crop1024 convention that persists through the whole campaign). Matched-
  crop: **SF-AdamW 1.46 it/s > SF-NorMuon 1.31 it/s**, both faster than AdamW
  @2048 only via the crop trick. A MERIT eval (MERT-330M + 3 disentangling
  heads) is wired to replace the broken chroma metric.
- **2026-06-20, THE PIVOT:** Comprehensive MERIT (480 clips, all riffer
  models, gains 0.1→8) shows the opaque reference-conditioned riffer **does
  NOT transfer** mel/rhythm/timbre (MERIT≈0). In the same session, an
  **explicit onset-density scalar head** is built instead (FiLM tokens,
  `--control-mode scalar`, per-crop scalar target, `onset_eval.py`) and
  validated: **corr +0.90 at gain 1** — requested sparse→dense maps to
  measured 4.3→8.3 onsets/sec. **This single result is the origin of the
  entire onset-density control-adapter line.**

### Phase 1 — Optimizer/LR bracketing on the real onset-density head (2026-06-20 → ~06-23)

Reconstructed from disk (run dirs + raw logs) — almost no prose exists for this phase:

- **`onset_AdamW_lr1e-4`** — AdamW lr1e-4, crop512f. **COLLAPSED at segment 4**
  (cum. step 43,200): `mean PQ 6.42 CE 4.76`, below the quality floor.
- **`onset_AdamW_lr7.5e-5`** (+ `_continuous`/`_randomcrop`/`_randomcrop_20ep`/
  `_randomcrop_b2`) — stops cleanly after seg3 (step 32,400), empty seg4 dir,
  **no STATUS line recorded**. Outcome genuinely unknown (see Gaps #2).
- **`onset_Fusion_lr1e-4_randomcrop`** — FusionOpt (normuon/ns5/sf),
  119.6M/2419M trainable (4.94%), crop512f/47.6s, 5400 crops/2677 tracks, 10
  segments to `riffer_final.pt` @ step 54,000. **This is the checkpoint behind
  the final ear-verdict (§3).**
- Small fixed-scale probes: `onset_FUSION_lr1e4_5000_crop512`/`_crop1024`/
  `_ckpt`/`_FIXED` (a Fusion-allocator gating bug fixed + re-verified at
  5000 steps before committing to full runs); `onset_SFADAMW_lr1e4_5000_crop1024`
  (isolating Schedule-Free from NorMuon/NS5).
- **`onset_density_400trk_crop1024`** and **`onset_density_FULL_3000{,b,c}_crop1024`**
  — scaling the original 400-track head to the full ~2700-track corpus.

No one wrote up "AdamW collapses, lr7.5e-5 was abandoned, here's why Fusion
won" as prose — it has to be inferred from the fact that essentially every
subsequent named checkpoint (Fusion_lr1e-4_randomcrop, FusionCC, FusionCaut,
FUSION_lr2e5_40epoch) is FusionOpt-trained, and AdamW never reappears as a
serious contender after this window.

### Phase 2 — Baking the adapter into the low-VRAM inference path (2026-06-27)

The trained adapter (decoupled cross-attention per DiT block + scalar FiLM
conditioner, field=`onset_density`) is a pure forward mod — folds into the
ONNX DiT export graph as two extra inputs (`control_tokens[1,16,768]` + `gain`),
no autograd needed. WORKLOG names `onset_FUSION_lr2e5_40epoch/soup_exppeak.pt`
as the checkpoint used — **on current disk this file actually lives under
`onset_Fusion_lr1e-4_randomcrop/` instead**, a provenance inconsistency (Gap #8).
Validated: ONNX vs controlled-torch cos=1.000000; steering 3→4.88, 11→11.15
onsets/sec, monotonic and calibrated — this CPU ONNX pipeline is what measured
every correlation table in the rest of this story.

Same window (06-28): LatCH **guidance** heads (sample-space, distinct from the
weight-space FiLM adapter) swept across all 14 SA3-medium heads. Energy/timbre
heads steer strongly; **the activation-family heads — beat, downbeat, onset —
are dead at any weight.** First sighting of a load-bearing finding: sample-
space onset guidance doesn't work; only the trained weight-space adapter does.

### Phase 3 — The cautious-optimizer thread and the r128 NaN divergence bug (2026-06-30 → 07-02)

- **06-30:** Kim's question about the Cautious optimizer starts a sub-
  investigation; `--cautious` lands in FusionOpt with `keep_frac` telemetry.
- **07-01, the cautious A/B campaign:** four findings, all negative-or-mixed:
  - **The 6–9 onsets/s saturation band is optimizer-independent** (75-81% of
    all eval cells land there regardless of head/optimizer/soup) — a
    training-signal problem, not a descent problem. Directly motivates
    FusionCC (Phase 4).
  - **The onset-authority metric is gameable**: a "ambient drone, low-volume
    rapid hats" clip measured 12.9 onsets/s; Kim's ear caught it instantly,
    no metric did. Standing rule from here: numbers are instruments, audition
    is the verdict.
  - **Cross-optimizer soup blend ratio isn't a real quality lever** — metrics
    flat across 10-30% AdamW-in-Fusion blends; "25/75 is best" is audition-
    only (this is `soup25A75F`, behind `onset_eval_soup_baseline`/`_caut`).
  - **Cautious masking is a quality trade, not a win** ("the four-instrument
    null"): no significant authority effect; drier/cleaner separation vs.
    muted highs/earlier smear on push. Keep as a palette option, not default.
- **07-02, mechanism + THE DIVERGENCE BUG:**
  - NS5 destroys per-coordinate gradient sign structure (`keep_frac≈0.53`
    flat across all 54k steps — Muon-orthogonalized update barely agrees
    with raw gradient sign, ever).
  - **The hidden +37% bug**: the standard `1/keep_frac` rescale preserves
    *mean* magnitude but inflates update *norm* by `1/√keep_frac` — at
    keep≈0.53 that's a hidden +37% effective spectral LR, harmless at
    AdamW's normal keep≈0.9, not at NS5's ≈0.5. **Root cause of "DoRA r128
    cautious A/B diverged — all LoRA tensors NaN between ep2 and ep3."**
    Healthy ep0-2 were competitive (Fréchet 0.0785) before blowing up. Fixed
    with a norm-preserving rescale. FiLM (this story's main line) *tolerated*
    the same bug — explains FiLM-cautious's "pushing harder" character — but
    full-fusion r128 DoRA did not survive it.
  - Same-day paired bootstrap (5000 resamples): **no significant authority
    difference** for cautious at all (best case d=+0.102, P=0.92). An earlier
    "cautious modestly wins at g3" claim is retracted as over-read noise.
  - **The ep5 triple convergence**: Kim's audition sweet spot, the geometric
    soup-center checkpoint, and a trajectory-PCA turnover all independently
    land on ~epoch 5 (control-forming → drift) — three instruments agreeing
    on an answer the RF loss itself never sees.
  - Parallel ES-conditioner line (v1→v3): v3 (RMS-normalized) works modestly
    (+0.28 onsets/s mean-error, P=0.96, n=24, concentrated at low requests,
    ~8-9% of training-grid gain generalized). Economics verdict: FusionCC
    bought +0.30 corr for 5 GPU-hours; ES bought +0.28 err for ~11 CPU-hours —
    gradients win where they exist.

### Phase 4 — FusionCC: the first statistically significant win (2026-07-02)

**The idea:** add a frozen, pretrained onset-density probe as a consistency
loss on top of the RF objective — "meter in the gradient."

**07-02, the verdict:** FusionCC (`onset_FusionCC_lr1e-4_randomcrop`) is **the
campaign's first statistically significant win**: corr/gain baseline→CC:
g1 .558→.752, g2 .584→.880 (paired bootstrap d=+0.295, CI95 [+.036,+.832],
P=.99), g3 .702→.889. Confirmed on disk (`onset_eval_FusionCC/run_meta.json`).
Mechanism: the sparse floor breaks (request-3 renders 5.7 onsets/s vs every
other head's ~6.0-6.9 floor). **The upper ceiling (~9.2) is unmoved.**
**Standing open question logged the same day: "does CC play sparse or fool
librosa? Kim's ears decide."** — this question's fate is the crux of §3.

### Phase 5 — Generalizing "meter in the gradient," and where it breaks (2026-07-03)

- Novelty check: FusionCC's mechanism is independently-reinvented ControlNet++
  (arXiv:2404.07987); the real novel contribution is the boundary condition
  below.
- **"Perfect meter, dead steering wheel"**: an EMA retrain of the
  `onset_envelope` LatCH *guidance* head does NOT revive sample-space
  steering — both heads are near-perfect meters on real latents (corr
  .990/.985) but the gradient still doesn't couple to generation.
  **Mechanism: contractive denoising erases off-manifold perturbations** —
  energy is a locally-linear on-manifold coordinate so it steers; onset
  timing needs coordinated structural movement the head's input-gradient
  doesn't encode. **Sharp contrast: the same kind of frozen onset meter
  steers through WEIGHTS (FusionCC, +50% authority) but not through SAMPLES
  (guidance, dead).**
- **The recipe's boundary — meter-in-the-gradient needs a BLIND loss**: the
  same mechanism applied to a *genre*-consistency probe **HURT** steering
  (Goa authority 0.92→0.65, Psy 0.46→0.03). **Rule: applies to properties the
  training loss is blind to (onset timing), not ones it already sees
  (genre, a global property RF reconstruction already captures).**
- **Composed sweep launched**: tests whether the weight-space adapter and
  sample-space LatCH guidance compose. Checkpoints pinned:
  `baseline_adapter=onset_Fusion_lr1e-4_randomcrop`,
  `fusioncc_adapter=onset_FusionCC_lr1e-4_randomcrop`. Calibration ladder:
  **NEGATIVE — guidance monotonically destroys the adapter's own authority**
  (unguided +5.18 → +0.30 @512 → −0.34 @1024). Stage-1 latch-off A/B
  replicates FusionCC's advantage at low/mid gain, roughly ties at gain 3.

### Phase 6 — Clipping bug, then the audition day that overturns the metric-driven verdict (2026-07-04 → 07-07)

- **07-04:** root cause of subtly bad audio found — both CPU eval servers
  hard-clipped via `np.clip` (0.09% avg / 0.6% worst full-scale samples).
  **Every server-rendered eval since 06-27, including the FusionCC audition
  sets, was clipped.** Fixed; `E_fusion_v2`/`A_cc_v2` are the re-renders —
  meaning every FusionCC audition before 07-04 was on distorted audio.
- **07-07, the density-control audition day (Kim's direct verdicts):**
  1. `gain_knee` decoded: the old FiLM adapter shows a two-state style-flip
     attractor with a knee at gain ~1.4-1.5 (density request going past
     ~±2σ of the trained distribution, at which point tokens stop meaning
     "density" and act as a generic override). Within-distribution requests
     get genuine control.
  2. FiLM gain calibration by ear: *"gain 6 never worked."* **Flat gain 1.75**
     is the new working default (1 too little, 2 often too much at the top).
  3. "FiLM broken" diagnosis, resolved: gain-6 clips were pure overdrive, not
     a wiring bug — gain 1.75 on the same harness steers correctly.
  4. **THE HEADLINE VERDICT** (journal title: *"the ear-approved density
     control is PLAIN-Fusion FiLM, not FusionCC, not LatCH"*): Kim went
     looking for the control clips he remembered as great and found
     `composed_sweep/E_fusion_v2` — `run_meta.json` says `latch: null,
     run: onset_Fusion_lr1e-4_randomcrop` — **plain Fusion FiLM, NOT the
     FusionCC checkpoint**, corr .574/.659/.794 @ gains 1/2/3.
     **"Calibrate per checkpoint, never reuse a gain."** LatCH guidance
     confirmed negative-by-ear a second time. **This directly answers Phase
     4's open question — by ear, on clean audio, the plain (non-CC)
     checkpoint is the one Kim reaches for, even though FusionCC's measured
     correlation is quantitatively higher.** No reconciliation of this
     tension is recorded after 07-07 (Gap #1 — the highest-priority open item).

### Phase 7 — Late-arriving, tangentially relevant threads (2026-07-08 → 07-10)

- **07-08:** an unrelated adapter family (avp DoRA style adapters) has tempo
  instability from mixed tempo-augmented data — same "training-data confound
  masquerading as a model problem" pattern seen throughout this story.
- **07-10, the layer map:** causal activation-patching (1728 cells) finds
  onset density (+ bass weight, brightness, noisiness) localizes to LATE
  self-attention + feed-forward blocks (~16-23) in the base DiT —
  cross-attention medians ~0.00 everywhere. **Friction worth noting: the
  actual onset-density adapter is wired as cross-attention injection per
  block, and it demonstrably works** — the localizer's "the base model's own
  representation lives in self-attn/ff" is a different question from "where
  can an externally-added adapter inject control," but nobody has reconciled
  them (Gap #6). Same day: plain `librosa.onset_detect` is found to over-fire
  ~3× on textured drones; the validated meter is p95-normalized + strength-
  gated peak-picking — **every correlation number in this entire narrative
  was measured with the older, now-flagged-as-noisy detector** (Gap #5).
- **07-10, scalar-head guidance buzz:** a related but distinct investigation
  (timbral `hardness`, not onset) finds constant per-frame targets can demand
  temporally-flat audio and buzz, then falsifies its own flatness hypothesis
  — mechanism left open (degenerate Jacobian or shortcut-feature). Nobody has
  asked whether this sharper diagnosis applies retroactively to the onset-
  envelope guidance case from Phase 5.

---

## 2. Per-run-directory annotations

✓ = written verdict found · — = disk exists, no prose verdict recovered.

**Origin / head validation**
- `onset_density_400trk_crop1024` — ✓ the original 400-track head; corr +0.90
  @ gain1, THE pivot result.
- `onset_density_FULL_3000{,b,c}_crop1024` — — scaling to the full corpus, no
  numbers/verdict recovered.

**Optimizer/LR bracket**
- `onset_AdamW_lr1e-4` — ✓ COLLAPSED at step 43,200 (PQ 6.42 CE 4.76).
- `onset_AdamW_lr7.5e-5` (+continuous/randomcrop/randomcrop_20ep/randomcrop_b2)
  — — stopped mid-segment, outcome unknown.
- `onset_SFADAMW_lr1e4_5000_crop1024` — — SF-only bake-off arm, no verdict.
- `onset_FUSION_lr1e4_5000_{crop512,crop1024,ckpt,FIXED}` — — allocator-fix
  smoke tests.
- `onset_Fusion_lr1e-4_randomcrop` (+`_20ep`) — ✓ **the checkpoint behind the
  07-07 ear-verdict.** Plain FusionOpt, 54,000-step run; corr .574/.659/.794
  @ gains 1/2/3 (`E_fusion_v2`).
- `onset_FUSION_lr2e5_40epoch` — ✓ a separate, longer (40ep, lr2e-5) plain-
  Fusion run whose own `run_meta.json` calls it *"the favourite... by ear
  the most useful, closest to the Goa aesthetic."* **Never cross-examined
  against `onset_Fusion_lr1e-4_randomcrop`** (Gap #3).
- `onset_FUSION_lr8e5_{1epoch,1p2ep,10epoch}` — — lr8e-5 bracket arms, no
  specific verdict beyond generic sweep boilerplate.

**Cautious / FusionOpt component thread**
- `onset_eval_Fusion_baseline` — ✓ reference table: corr .496/.558/.584/.702
  @ gains .5/1/2/3.
- `onset_FusionCaut_lr1e-4_randomcrop` / `onset_eval_FusionCaut` — ✓ corr
  .491/.551/.574/.801 — bootstrap found no significant difference from
  baseline; the real finding is Kim's audition (drier/cleaner, muted-highs
  trade), not the table.

**Meter-in-the-gradient (FusionCC)**
- `onset_FusionCC_lr1e-4_randomcrop` / `onset_eval_FusionCC` — ✓ first
  bootstrap-significant win of the campaign (corr .042/.752/.88/.889).
  **Superseded in practice by Kim's 07-07 ear-verdict for plain Fusion** —
  metric win and audition preference point different directions (Gap #1).
- `onset_eval_fusfixed_s{1000..5000}` — — one-off "fixed-config Fusion"
  checkpoints, no specific verdict.
- `onset_eval_54000_{g11to20,inrange,lowgain}` — — targeted gain/density
  probes at the 54,000-step checkpoint, no verdict beyond boilerplate.
- `onset_eval_clean_ep15-30`, `onset_eval_refined_g08-12`,
  `onset_eval_ckpts_multiprompt`, `onset_ab_audition`, `onset_film_trajectory`
  — — no `run_meta.json` at all, bare clip dumps.

**Model soups**
- `onset_eval_soup_baseline` (+`_ep10`) — ✓ `soup25A75F`; corr
  .531/.508/.688/.783. Metric-flat across blend ratios; 25/75 preference is
  audition-only.
- `onset_eval_soup_caut` (+`_ep2,_ep5,_ep10`) — ✓ `soup25A75F_caut`; corr
  .529/−.266/.764/.837 (the g1 negative is unexplained in prose). Bootstrap:
  no significant authority difference vs. non-caut soup.
- `onset_eval_soups`, `onset_eval_soups_multiprompt` — — bare dumps.
- `soup_exppeak.pt` / `soup_asc_wide7` / `soup_peak_wide7` (inside the
  Fusion runs) — — trajectory/EMA-style soups across training steps, exact
  averaging recipe and verdict not documented in prose.

**Composed sweep (adapter × LatCH guidance)**
- `composed_sweep/E_fusion` / `E_fusion_v2` — ✓ plain-Fusion, latch-off; v2
  is the clip-fixed re-render and **is Kim's rated favorite.**
- `composed_sweep/A_cc` / `A_cc_v2` — ✓ FusionCC, latch-off; replicates the
  correlation advantage at low/mid gain, ties at gain 3.
- Calibration ladder (rho/mu 128-1024) — ✓ NEGATIVE, guidance destroys
  adapter authority monotonically at every setting tested.

**Infrastructure, not experiments**: `newcap8_density_control_g175` (the
calibrated-gain re-render, current) supersedes `newcap8_density_control`
(gain-6, style-flipped) per its own findings banner.

---

## 3. The verdict — is there a "use this checkpoint" answer?

**Yes, but contested between two instruments, and the record never resolves it.**

**By quantitative correlation metric:** `onset_FusionCC_lr1e-4_randomcrop`
wins decisively, with statistical significance — corr .584→.880 at gain 2
(P=.99), the campaign's only bootstrap-significant win.

**By Kim's ear, on record, dated 2026-07-07:** the reference recipe is
**`onset_Fusion_lr1e-4_randomcrop` (plain Fusion, NOT FusionCC), FiLM gain
≈1.75, calibrated per checkpoint.** The journal titles this finding
explicitly: *"the ear-approved density control is PLAIN-Fusion FiLM, not
FusionCC, not LatCH."*

**Not contested:** LatCH sample-space guidance for onset is dead — confirmed
negative by mechanism and by ear, twice. If choosing between the FiLM
adapter and gradient-guidance, the adapter is the only one that works at all.

**Unresolved (flagged, not decided):**
1. FusionCC vs. plain Fusion, on **clean, post-clip-fix audio, head-to-head**
   — never done. `composed_sweep/A_cc_v2` (clip-fixed FusionCC) exists; no
   record of Kim auditioning it against `E_fusion_v2` after both were fixed.
2. `onset_Fusion_lr1e-4_randomcrop` vs. `onset_FUSION_lr2e5_40epoch` — two
   different "favorite" claims in two different places, never cross-examined.
3. Which exact checkpoint tag — `riffer_final.pt` (step 54,000) is the
   disk-verifiable answer (what `E_fusion_v2` evaluated, what the ONNX
   export used) but no document explains why that step vs. an earlier one.

**Bottom line, if forced to name one recipe today:** plain-Fusion FiLM
control adapter, checkpoint `onset_Fusion_lr1e-4_randomcrop/riffer_final.pt`,
FiLM gain ≈1.75 (recalibrate per checkpoint), staying within the trained
conditioning range (~±2σ of mean density 7.1, roughly requests 4–10
onsets/s). This is Kim's own most recent, most specific, dated ear-verdict —
but it is explicitly not what the correlation metric would pick, and the
long lr2e-5/40-epoch run has its own unexamined "favorite" claim.

---

## 4. Open gaps — needs fleet memory / a fresh look

1. **FusionCC vs. plain-Fusion, clean-audio head-to-head — never done.**
   Highest priority; would actually resolve §3.
2. **`onset_AdamW_lr7.5e-5`'s outcome is unknown** — log stops mid-gate, no
   STATUS line, empty seg4. Collapsed silently? Killed for GPU time?
3. **`onset_FUSION_lr2e5_40epoch` "longer Fusion has vibe" claim is asserted,
   not argued** — no dated session log describing who listened or how it
   compares to the randomcrop run. Its own `eval_listen`/`eval_traj`
   sub-evals (with `pq_scores.json`) look like they contain the comparison
   data; nobody has interpreted it in prose.
4. **The FusionCC v1.3 candidate** (all-t consistency loss on noised
   latents, from an InnerControl deep-read) was designed 2026-07-03,
   apparently never trained.
5. **Every correlation number in this narrative used the old, now-flagged-
   as-noisy plain `librosa.onset_detect`** (over-fires ~3x on drones per the
   07-10 finding). Nobody has re-scored with the validated p95-gated
   peak-picker to see if it changes the FusionCC-vs-plain ranking.
6. **Cross-attn vs. self_attn+ff routing tension is unexamined** — the
   working adapter is wired as cross-attention; the causal-localization map
   says the base model's own onset representation lives in self_attn+ff with
   cross_attn ≈0. Possibly explains the saturation-band/ceiling behavior.
7. **The outro/silence-cheat fix** (RMS-gate the training scalar to active
   frames) — flagged by Kim 07-07, in `docs/todos.md`, never implemented.
8. **`onset_FUSION_lr2e5_40epoch/soup_exppeak.pt` (WORKLOG 06-27) vs. disk
   reality** — the file actually lives under `onset_Fusion_lr1e-4_randomcrop/`
   today. Which run actually produced the shipped ONNX control graph?
9. **No dedicated `FINDINGS.md` exists inside almost any individual run dir**
   (`composed_sweep` and `layer_map_2026-07-10` are the exceptions) — the
   `run_meta.json` "see WORKLOG/LATCH_RESULTS for specifics" boilerplate
   doesn't actually point anywhere specific for most of these.

---

## 5. CONTINUITY annotations (2026-07-12) — confirmations, one reconciliation, gap dispositions

*(Phase 4–5 are my work; reviewed the full draft against my journal + MASTER §4.
G's reconstruction of those phases is accurate — numbers, dates, and the scope
condition are all as recorded. Specific additions below.)*

**§3 verdict — endorse as written, with the deciding rule made explicit.** My
own channel nomination of FusionCC (corr .880) was metric-based; the standing
rule from 07-01 — *"numbers are instruments, audition is the verdict"* — was
minted in THIS campaign, so it governs here. Kim's dated 07-07 ear-verdict
(plain-Fusion FiLM @ gain≈1.75) is the correct named recipe until Gap #1 (the
clean-audio head-to-head) is actually run. A subtlety the head-to-head should
respect: FusionCC's measured advantage is concentrated in the SPARSE floor
(request-3: 5.7 vs ~6.0–6.9 onsets/s) — if Kim's 07-07 listening leaned on
mid/dense requests, both verdicts can be simultaneously true on different parts
of the request range. Recommend the A/B explicitly separates sparse (3–5) from
dense (8–10) requests.

**Gap #5 before any landing-page numbers.** W's re-scoring with the validated
p95-gated meter should run BEFORE the landing narrative quotes correlations —
the old detector's 3× drone over-fire is exactly the failure mode a "plays
sparse vs fools librosa" checkpoint difference would hide in (that was Phase
4's same-day open question, still the crux). One pass closes Gaps #1+#5
together (score `A_cc_v2` vs `E_fusion_v2` vs lr2e5_40epoch's best with the
new meter).

**Gap #4 (FusionCC v1.3) — confirmed status: designed, deliberately deferred,
not lost.** The all-t consistency variant (from the InnerControl deep-read,
07-03) was parked because the plain-CC scope condition needed validating first
and the avp/rarity work took the card. Design lives in my 07-03 journal entry +
the deep-read note. It only becomes worth training if the re-scored Gap #1
verdict says CC's mechanism survives the meter fix.

**Gap #6 (cross-attn adapter vs self_attn+ff localization) — proposed
reconciliation, interpretation not measurement.** These answer different
questions about a shared bus. The causal map localizes where the BASE model's
own computation carries onset density (late self_attn+ff readout); the adapter
doesn't need to inject there — cross-attn injection WRITES new signal into the
residual stream at every block, and the downstream self_attn+ff that computes
density can read it. Fresh corroboration from the 07-11/12 concept-direction
steering: simple additive writes into block outputs at mid-stack blocks
audibly steer (mt_dark 19× on the meter) even though those blocks' own
computation wasn't the target — write-site ≠ compute-site. What the tension
MAY explain is the ceiling: if density is finalized in late ff, a cross-attn
token that stops being read past ~±2σ (the gain_knee two-state attractor,
07-07) would saturate exactly the way the 6–9 onsets/s band does. Testable
cheaply: per-layer ablation of the adapter's 24 cross-attn injections (zero
them in groups at inference) — if authority survives with only L16–23
injections active, the routing story consolidates; my layered-strength
tooling (`eval/layered_lora_a2a.py` pattern) adapts directly.

**Gap #2 (lr7.5e-5 outcome) — recoverable from data, not memory.**
`onset_AdamW_lr7.5e-5_randomcrop_20ep` has 2,640 per-epoch eval clips on disk
(surfaced during G's 07-07 landing cleanup). Nobody needs to remember the
outcome; scoring those grids per epoch answers "collapsed vs killed" directly.
I have no memory of an explicit kill decision — consistent with "stopped for
GPU time and never revisited," but that is inference, not record.

**Gap #8 — no memory to add; don't guess.** The ONNX-bake provenance
(soup_exppeak's true parent run) should be settled from the export's own
metadata stamp (the exporter writes source-ckpt info into onnx metadata /
`.cond.npz`) rather than anyone's recollection.

**One factual nit in §2:** `onset_eval_FusionCC` corr is listed as
`.042/.752/.88/.889` — the .042 is gain 0.5 (noise floor at near-zero gain, same
as baseline's .496 → both heads are uncontrolled there); worth a parenthetical
so the landing page doesn't present it as a defect of CC specifically.

---

## 6. Gap resolutions (2026-07-12, same day) — WINTERMUTE's re-score + the layer ablation

**Gap #1 + #5 (FusionCC vs. plain-Fusion, and whether the old detector's 3×
drone over-fire tainted the ranking) — CLOSED on the metric axis, the ear
question stays open.** WINTERMUTE re-scored `A_cc_v2` and `E_fusion_v2` with
the validated p95-gated meter, same densities (1–12) and gains (1/2/3) for
both — a genuinely matched, apples-to-apples grid this time. Result:
**FusionCC (`A_cc_v2`) pooled corr 0.77 > plain Fusion (`E_fusion_v2`) 0.717**
(per-gain: CC .834/.761/.72 vs. plain .74/.702/.716 — CC's edge concentrates
at gain 1, matching CONTINUITY's §5 prediction that the advantage sits at the
sparse floor). **This is the real signal, not a measurement artifact** — the
old noisy detector is exonerated as a confound here. So: FusionCC's metric
win from Phase 4 stands, independently reconfirmed on the corrected meter.
What this does NOT do is override Kim's 07-07 ear-verdict — per the
campaign's own founding rule ("numbers are instruments, audition is the
verdict"), the open item is still an actual audition of `A_cc_v2` against
`E_fusion_v2` on this now-doubly-confirmed-accurate metric gap. The
correlation numbers are no longer in question; which one Kim would pick
today, on clean audio, still is.

**Gap #3 (`onset_FUSION_lr2e5_40epoch`'s "favourite by ear" claim) — DATA
LANDED, comparison still not apples-to-apples.** The re-score's lr2e5 sweep
puts step 183,600 at pooled corr **0.921** — higher than either Fusion or
FusionCC — but measured over a **wider grid** (densities 2–20 vs. the
matched pair's 1–12, gains 0.5–2 vs. 1/2/3), which mechanically inflates
correlation (a wider requested range is easier to track proportionally).
**Not directly comparable as-is.** Before this can settle the "two
favorites" question, someone needs to re-score lr2e5-183600 on the *same*
density/gain grid as `A_cc_v2`/`E_fusion_v2`. Full per-checkpoint sweep in
`eval/onset_rescore_p95.json`.

**Gap #6 (cross-attn adapter vs. self_attn+ff localization) — RESOLVED, with
a real mechanism, not just an interpretation.** CONTINUITY's task #44
per-layer-group ablation (gain 1.75, canonical plain-Fusion checkpoint, same
seed, 4 densities): gating which of the adapter's 24 cross-attn taps are
active at inference —
- ALL taps: corr +0.91, spread 8.1 (full control, baseline)
- NONE: flat 4.25 (sanity — confirms the taps are doing the work at all)
- **LATE-only (blocks 16–23): the only subset with real positive authority**
  (corr +0.45) — and it specifically renders the request-3 sparse floor down
  to 1.9, i.e. **the sparse-request control that FusionCC also targets lives
  in exactly the late taps the causal layer-map already flagged as where
  rhythm gets computed.**
- EARLY-only: dead (−0.30)
- MID-only: **actively anti-correlated** (−0.80) — partial injection is
  out-of-distribution for an adapter trained with all 24 taps writing
  together, not just "redundant."

So the write-site≠compute-site reconciliation from §5 holds, sharpened: the
adapter's cross-attn writes are read out downstream by the late self_attn+ff
blocks the causal map identified — but early/mid taps aren't decorative,
they're load-bearing for keeping the whole ensemble in-distribution.
Caveat stated by WINTERMUTE: n=4 densities, 1 seed/prompt, the OLD (not
p95-gated) meter — directional, not a settled law. Full manifest v2 run at
`sa3_control_runs/ablate_layers_2026-07-12/`.

**Updated bottom line:** the campaign's central tension (§3) is now better
characterized, not fully closed. FusionCC's metric advantage is confirmed
real (not a detector artifact) and its mechanism is now understood (late-tap
sparse-floor control). Kim's ear-verdict for plain Fusion still stands as
the only recorded direct audition — but it predates knowing FusionCC's
edge is genuine, not measurement noise. The single highest-value remaining
action is unchanged from §3/§4: an actual clean-audio listen of `A_cc_v2`
vs. `E_fusion_v2`, now armed with the knowledge that the metric gap between
them is real and concentrated at low/sparse requests specifically.
