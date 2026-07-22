# DoRA hyperparameter × metric analysis — full model_matrix

**WINTERMUTE, 2026-07-22.** Joins the full CLAP genre-adherence scan (31,639 cells) with
`clip_metrics.db` (Audiobox CE/PQ/CU/PC + DSP: zcr/flatness/flux/hf_ratio/centroid/onset/crest/rms)
and the per-checkpoint training recipes (real hyperparameters THE-FINN extracted from the
checkpoints). Fp32-fullft native cells still pending from LUMI — this covers everything else.

**Tables:** `clap_full_table.csv` (per-cell, every hyperparam + every metric — the one you asked for),
`clap_dora_aggregate.csv` (per model×checkpoint). Builder: `eval/build_clap_hyperparam_table.py`.

> **Read this first — confounds.** The runs were not a clean factorial sweep, so several
> hyperparameters travel together (T=4096 ⇄ fp32 ⇄ bs1/4; T=1024 ⇄ bs16; aug10 ⇄ alpha<rank;
> AdamW ⇄ a few specific runs). A raw "marginal" mean over one parameter therefore mixes the
> others. Below I separate **marginal** (all cells, confounded) from **controlled** (within one
> campaign, only the named knob moves). Trust the controlled ones; treat marginals as hints.
> `clap_matched` = CLAP cos(audio, its own prompt) — genre-adherence, low = drifted off-genre.

---

## 1. Metric structure — what actually co-varies (Spearman, 30k cells)

Three near-independent families fall out of the correlation matrix:

- **Semantic adherence:** `clap_matched`. Correlates moderately with quality — PQ **0.57**, CU 0.55,
  CE **0.44**, onset_p95 0.48 — but is NOT redundant with any of them.
- **Audiobox quality:** CE / PQ / CU are highly collinear (**PQ↔CU 0.96**, CE↔CU 0.85). *PQ and CU are
  almost the same number — carry one, not both.* PC is a separate axis (CE↔PC 0.53, PQ↔PC only 0.22).
- **Brightness / noise (the DSP disintegration family):** zcr, flatness, hf_ratio, centroid all move
  together (flatness↔centroid **0.88**, hf_ratio↔centroid 0.86, zcr↔flatness 0.82).
- **Dynamics:** crest ↔ rms **−0.91**, flux ↔ rms 0.86 (peaky/transient ⇄ low sustained energy).
- `bpm` correlates with **nothing** (|r|≤0.08) — independent of quality and adherence.

**The single most useful structural fact:** `clap_matched` is nearly *uncorrelated* with the
DSP-noise family (CLAP↔zcr 0.01, ↔hf_ratio 0.10, ↔flatness 0.22). **Semantic degeneration and DSP
buzz/whitening are different failure modes** — a clip can be on-genre but buzzy, or clean but
off-genre. This is the data justification for running BOTH the CLAP degeneration flag AND the DSP
disintegration gate: neither predicts the other. (Genre-adherent output does trend denser-onset and
less peaky: CLAP↔onset_p95 0.48, ↔crest −0.34.)

## 2. Parameter effects (strongest → weakest)

### rank — r16 is the clear loser; ≥64 is a plateau
Marginal CLAP: r16 **0.244**, r64 0.311, r128 0.302, r256 0.312. r16 is also the *buzziest* (zcr 0.114,
hf_ratio 0.046 — both the worst) and lowest quality (CE 5.15 vs ~5.8–6.3). So **rank-16 fails on both
axes at once** (off-genre AND noisy). Above r64 it plateaus — r64≈r128≈r256 on adherence; r256 edges
CE (6.29) but on thin n. **Takeaway: never r16; r64 already captures most of the benefit, r128 the safe default.**

### DoRA strength (inference knob) — monotone, the strongest single lever
CLAP by weight: w0.6 **0.343** → w1.0 0.304 → w1.5 0.284 → w2.0 **0.222**. CE tracks it (7.70→6.87 PQ).
**Over-applying the adapter degrades both adherence and quality, monotonically.** w2.0 is genuinely
bad; the sweet spot is w0.6–1.0. This is an *inference-time* free lunch — no retraining needed.

### cfg (inference knob) — cfg1 is the degeneration zone
CLAP: cfg1 **0.225** → cfg7 0.328 → cfg16 0.333, cfg24 0.305. Weak prompt steering (cfg1) drifts
off-genre; cfg7–16 is the plateau. Combined with strength: **best cell = cfg7–16 × w0.6–1.0.**

### lr — safe to 2e-4, catastrophic at 3× (CONTROLLED)
Clean `everything`-sweep (r128, all else fixed): lr 1e-4 → CLAP 0.308, 2e-4 → 0.309, **6e-4 → 0.224**
(CE 5.70→5.72→**4.94**). So **1e-4 and 2e-4 are equivalent; 6e-4 collapses.** (The marginal table's
"2e-4 worse than 1e-4" was a confound — different runs — the controlled sweep clears it.) Within the
fp32 campaign, 5e-5 edges 1e-4 slightly. **Keep lr ≤ 2e-4; 3× is off the table.**

### augmentation — a real, clean win
aug10 vs aug0: CLAP **0.332 vs 0.295**, CE **6.49 vs 5.86**, PQ 7.83 vs 7.34, and *lower* buzz
(hf 0.021 vs 0.032). Augmentation improves adherence, quality, AND cleanliness together — the only
parameter that helps on every axis. Pairs with the epoch finding below.

### epochs — overtraining collapses the un-augmented, augmented keeps climbing
ep0–7 are flat (~0.29–0.30). Then it forks: the un-augmented r16 originals **collapse** (ep15 0.161,
ep31 0.232, CE 4.1–4.9), while the **aug10** run keeps *improving* (ep37 0.324, **ep74 0.344 / CE
6.53 / PQ 7.96** — the single best checkpoint in the corpus). **Overtraining is only harmful without
augmentation; with aug10 more epochs is pure gain.** Quantifies the standing hypothesis exactly.

### alpha/rank ratio — lower α than rank is BETTER (non-obvious)
alpha_over_rank 0.25–0.35 (the `dora128adj α45`, `dora64 α32`, `dora256 α64` configs) → CLAP 0.314–0.320,
CE ~6.4; ratio **1.0** (the standard α=rank) → 0.288, CE 5.87. **Reducing alpha below rank improves both
adherence and quality.** This is a lever we have not been using systematically — the "adj" runs stumbled
into it. Worth a deliberate α/rank sweep. (Caveat: partly travels with aug10 — the aug10 run is α45 —
but dora64-tiered α32 is un-augmented and also scores well, so the effect is not purely the aug confound.)

### frames_T (context length) — optimum ~1024, long context (4096) is worse
Marginal CLAP: T256 0.313, T512 0.311, **T1024 0.329**, T2048 0.313, T4096 0.289. Longer context does
NOT help and T4096 is the worst of the ladder (also buzziest: hf 0.044). *Confounded* (T1024 = the bs16
run; T4096 = fp32/bs1-4), so treat the peak location as soft — but the direction "T4096 ≤ shorter" is
consistent across cuts. The pending fp32-fullft T256→4096 ladder from LUMI is the clean test of this.

### batch — the marginal LIES; controlled says bs1 ≥ bs4 at T4096
Marginal shows bs16 best (0.329) — but bs16 **is** the T1024 run, so that's the frames effect, not batch.
CONTROLLED (fp32cmp T4096, lr1e-4): bs1 CLAP 0.294 / hf **0.024** vs bs4 0.287 / hf 0.053. **At matched
context, small batch is cleaner, not worse.** Do not read "bigger batch better" from the marginal.

### precision — fp32 doesn't buy genre-adherence or lower buzz (but a DIFFERENT axis is Kim's ear's)
Marginal: CLAP 0.296 both; fp32 CE 6.07 vs bf16 5.76 (a small Audiobox-CE bump), identical adherence and
buzz. **On the axes measured here — genre-adherence and DSP-buzz — fp32 ≈ bf16.** ⚠️ This does NOT
contradict Kim's 2026-07-20 by-ear "fp32 > bf16" (WORKLOG 07-20 02:32): he judged **fidelity — sound
separation, less noisy high-end** — which CLAP and clip_metrics explicitly do NOT capture (THE-FINN
patrol flag, 2026-07-22). So the honest statement is "fp32 doesn't buy adherence or lower buzz," NOT
"fp32 buys nothing." **The fp32-campaign go/kill still hangs on Kim's ear on the fidelity axis — this
finding retires one axis, not the arm.**

### optimizer — AdamW ≥ FusionOpt in this cut (flag, not conclusion)
AdamW CLAP 0.328 / CE 6.22 vs FusionOpt 0.292 / CE 5.93. BUT AdamW n=882 (a few specific runs, heavily
confounded) vs FusionOpt n=23k. **This does not show the FusionOpt advantage we assume** — worth a
controlled AdamW-vs-FusionOpt pair at matched everything before trusting either direction.

### base vs post-trained medium (same adapter) — a genuine tradeoff
Applying the *identical* goa adapter to the post-trained medium (`_ptm`) vs medium-base: ptm is **more
on-genre** (CLAP 0.288 vs 0.271) but **lower Audiobox quality** (CE 5.05 vs 5.80) and noisier (zcr 0.127
vs 0.108). So post-training pulls output toward genre at a fidelity cost — directly relevant to the #55
`_ptm` listening verdict: the feature space says ptm ≠ base, and this quantifies *how* (genre↑, polish↓).

## 3. Knowledge we didn't have before (the headline list)
1. **Semantic (CLAP) and DSP-buzz degeneration are independent** (r≈0.01–0.22) → both screens are needed; neither substitutes.
2. **PQ and CU are 0.96-collinear** → one is redundant; report PQ (or CU), CE, and PC.
3. **α < rank beats α = rank** on adherence AND quality — an unused recipe lever.
4. **fp32 ≈ bf16 on the axes measured here (adherence + buzz)** — but these do NOT capture the fidelity/high-end-noise axis Kim judged by ear on 07-20 ("fp32 > bf16"). Both true, different axes; the fp32 go/kill stays his ear's call (THE-FINN patrol flag).
5. **lr is flat 1e-4↔2e-4 and cliffs at 6e-4** (controlled) — the usable LR band is wider than "1e-4 only," but 3× is a wall.
6. **Overtraining is conditional on augmentation** — un-aug collapses by ep15; aug10 improves to ep74 (best in corpus).
7. **Small batch is cleaner at long context** (controlled) — opposite of the naive marginal.
8. **Post-training trades fidelity for genre-adherence** (same adapter) — quantifies the _ptm question.
9. **DoRA strength w0.6–1.0 × cfg7–16 is the operating box** — the two inference knobs dominate everything, and cost nothing to set right.

## 4. What needs a clean sweep to confirm (confounded here)
- α/rank ratio (disentangle from aug10): a matched α-sweep at fixed rank/data/epochs.
- frames_T optimum (disentangle from batch/precision): the pending LUMI fp32-fullft T256→4096 ladder is exactly this.
- AdamW vs FusionOpt at matched everything.
- batch at matched T (T4096 bs1/4 is a start; add bs8/16 at T4096).

*(Regenerate all of the above after the LUMI fp32-fullft native clips land: rerun `clap_score.py`
on the new cells, then `build_clap_hyperparam_table.py` — the fullft rows will fill in and the
frames_T ladder becomes clean.)*
