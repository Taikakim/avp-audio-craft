# Training findings, recipes & parameters

Authoritative experiment log for LatCH heads is **`stable-audio-tools/LATCH_RESULTS.txt`**
(§1–23). This file holds (a) the cross-cutting/SA3 findings that don't live there yet,
and (b) the **why-T=4096** reasoning. Update it when a finding affects more than one repo.

---

## Why SA3 latents are cropped to a fixed T=4096 (the big one)

**Short version:** SA3 medium's max sequence is 4096 latent frames; encoding every
training crop to *exactly* that length (rather than variable lengths) keeps the ROCm
GEMM/Triton kernel cache from thrashing, which is the difference between ~2 s/step and
~24 s/step on this hardware.

**The chain of reasoning:**

1. **Frame math.** SA3 medium: `sample_rate=44100`, pretransform `downsampling_ratio=4096`.
   → latent frame rate = 44100/4096 = **10.767 Hz**. Max `sample_size=16,777,216` samples
   = 380.4 s = **4096 latent frames**. (Contrast SA Open Small: 2048 ratio → 21.53 Hz,
   T=256 / 11.9 s. The two grids are incompatible — see `lessons-learned.md`.)

2. **What variable-length training costs on ROCm.** SA3 supports variable-length training
   (§3.1 of the tech report: per-sample padding + masked loss + flash-varlen attention).
   With `batch_size=1`, each sample is padded only to *its own* length T. **Flash/varlen
   attention and the matmuls compute over the effective T, so every distinct T is a
   distinct GEMM shape.** TunableOp (GEMM autotuner) and torch.compile/Triton (kernel
   codegen) both cache *per shape*. A dataset with thousands of unique track lengths →
   thousands of unique shapes → the autotuner re-tunes mid-step, basically forever.

3. **Observed.** First SA3 LoRA attempt encoded one ~285 s window/track at the encoder's
   default `sample_size`; even those varied (short tracks, padding-mask edges). Result:
   TunableOp CSV grew ~200 entries/hr and Triton cache ~560 files/hr *during training*,
   step time stuck at ~24 s, and it would only have stabilised after ~3 epochs of seeing
   every length. (2026-05-31)

4. **The fix.** Encode every crop to **exactly T=4096** (`sample_size=16,777,216`). Now
   96–100 % of training samples share one shape; the kernel cache warms in <100 steps and
   step time drops toward the tuning-run rate. Short tracks (<380 s) are **dropped**, not
   padded — a padded short track is a *different* effective-T shape and reintroduces the
   thrash (and ROCm re-tunes on every minor toolchain bump, so the overhead recurs).

5. **Don't-lose-the-music corollary.** A single 380 s window throws away ~38 % of a median
   7.7-min track. So we **beat-aligned chunk**: first crop from song start, each next crop
   snaps back to the downbeat before the previous end (musically-aligned overlap), final
   crop end-anchored. 3149 sources → **5400 crops** (~2.0/track), full music coverage,
   all T=4096. Scripts: `/tmp/sa3_beat_manifest.py` → `/tmp/sa3_encode_from_manifest.py`.

**Trade-off accepted:** we lose native short-clip training diversity. A T=4096-only LoRA
still *infers* at shorter lengths (the base model's variable-length capability lives in the
frozen weights, not the LoRA), with mild expected degradation below ~T=1024. Multi-length
training is a deferred Phase-2 option if short-form inference disappoints. See `todos.md`.

---

## SA3 LoRA recipe (current)

- Model: `medium-base`. LoRA: `--rank 16 --adapter_type dora-rows --lora_alpha 16`
  (DoRA-rows is the trainer default; ~21.6 M trainable / 2.3 B frozen).
- `--base_precision bf16`, `--batch_size 1`, `--lr 1e-4`, `--compile`.
- Data: `--encoded_dir /home/kim/Projects/latents_sa3` (T=4096 beat-aligned crops; the
  **NVMe mirror**). Train off the NVMe, **never `Lehto/latents_sa3`** — cold random reads
  off the removable Lehto drive crawl (~2 MB/s) and are a known step-0 freeze cause
  (MASTER §5). Lehto stays the canonical/authoritative copy.
- ROCm env: **`MIOPEN_FIND_MODE=2`** (mode 6 crashes the SA3 DiT — see lessons-learned),
  `PYTORCH_TUNABLEOP_ENABLED=1 TUNING=1`, warm caches at `~/pytorch-tunings-7.2.3`.
- Trainer flags added this session: `--compile`, `--no_demos` (demos = 3 cfg × 50 ODE
  steps ≈ 10 min, fire even at step 1; disable for tuning runs).
- Measured: ~2.4 s/step training (mislabeled earlier as 0.42 it/s, which was *demo*
  generation). Demos dominate wall-clock at default `--demo_every 500`; use ≥1500.

## LatCH head recipe (validated — full detail in LATCH_RESULTS.txt §21)

- **Ship recipe:** SF-NorMuon (`--optimizer fusion --components ns5,normuon,sf`),
  **d256/dp4**, bf16, `--compile`, `--t-injection adaln_zero`, AdamW-equiv LR 3e-4,
  40 ep, full data, fixed seed (shootout-picked). Beats AdamW by −12…−20 % raw-MAE
  at the *same* wall-clock.
- **Full Fusion** (+mona+shampoo) buys ~1 % quality for +50 % wall-clock → not worth it.
- **Sweep (2026-05-30, rms_energy_bass, 10 ep / 50 % subset):** smaller batch wins
  monotonically (b16 > b32 > b64 > b128); **lr 1e-3 > 3e-4 > 1e-4** at short budgets.
  Best cell `b16/lr1e-3` → 3.198 dB, ~5 % off the full-data ship reference at 1/6 compute.
- **Don't:** scale dim past 256, trust subset≤0.3 rankings, train a beat-activations head
  (dead control), use `beat_weighted` smoothing. (LATCH_RESULTS §3, §9, §14, §22.)

## Methodology rule

Don't compare `val_median` across runs with different `--standardize` / `huber_beta` —
convert to **raw MAE** first (§18 caught a "347 % regression" that was a unit artifact).

## fp32 vs bf16 precision (Kim's ear, 2026-07-20 — PRELIMINARY)
The fp32/T=4096 campaign arms (#52) sound BETTER than their matched bf16 twins by ear (Kim's
listening verdict, relayed by W): cleaner sound separation, less noisy high end, better in many
ways; worse in very few (occasional less punch — likely source-faithfulness, not a real loss). The
`bf16_twin` was built precisely as the matched-precision control (avp/goa T512 bs8 lr1e4, same recipe,
bf16 vs fp32) to de-confound the precision axis from everything else in the 8-arm fp32 campaign, so
this is a clean precision read, not a confound. NOT yet a comprehensive audit. STILL OPEN (parked for
G's native-training-length eval cells, since fixed-20s evals can't show trained-context differences):
bs1-vs-bs4 and T4096-vs-T2048. Recorded to the 10 fp32cmp/bf16cmp run_meta kim_feedback + WORKLOG
(W, 2026-07-20). Precision-story lane; pairs with the checkpoint-trajectory practice (MASTER §4).

## 2026-07-23 — Kim's listening verdicts (policy-setting)
- **fp32 + fullft fine-tunes are just better, period** (vs bf16 / adapter-only). Rank helps.
- **15 epochs is the NEW DEFAULT training goal** — models "just about start to sound fine
  after ep5, and often 7 is the first really good one" (prior 8-ep runs were stopping at
  the threshold of good). All 8-ep-era verdicts should be re-read with this in mind.
- Augmentation SEEMS to help → aug×10 campaign drafted (docs/superpowers/specs/
  2026-07-23-aug10-15ep-campaign.md); fullft→extracted-adapter comparison assigned to G
  (extraction at r16/64/128 may beat straight-trained DoRAs — Kim's hypothesis).

---

## 2026-09-21 → 24 — Modular optimizer on DoRA: causes and effects of training failure (CONTINUITY)

*Kim's ask 2026-09-24: record the causes and effects of training failures. Each entry: **symptom →
cause → evidence → fix / status**. Operator manual for every flag named here: `docs/train_lora_modular.md`.
Runs: `/run/media/kim/Mantu/sa3_lora_runs/{audition_160ep_2026-09-22-b, audition_amult20_480_2026-09-23,
goa3_avp_r256_2026-09-23}`, each with `run_meta.json`. Stats: `checkpoint-stats/`.*

### A. Failures of the MODEL (the weights went bad)

1. **NaN loss at ~step 6900 after 9 healthy epochs: DoRA magnitudes crossed zero** (`goa3_avp_r256_2026-09-23`,
   rank 128, 3 corpora, lr 6e-4, b32).
   - *Cause:* the modular optimizer trains every 1-D parameter, DoRA magnitudes included, with a **sign
     step**: each element moves by lr every step, regardless of its size. The small global-conditioning
     magnitudes (init = W0 row norms ≈ 0.13–0.45) walked through zero; the transformer-block ones (≈2.4)
     did not move meaningfully.
   - *Evidence:* at step 6340, `to_global_embed.0` had 592 non-positive rows, with a worst relative change
     of 40,000×. Also `to_global_embed.2` (78 rows), `global_cond_embedder.0` (77), `to_timestep_embed.2`
     (18); rows down to |m| = 2.6e-5. The emergency checkpoint's magnitudes are FINITE; NaN is in A/B of
     all 228 modules. The likely chain: the conditioning output breaks, feeds every block's AdaLN, and
     NaN gradients spread everywhere.
   - *Effect timeline:* loss steady (epoch means ~0.74) → step 6340: both `rb_mid_4` renders all-NaN →
     ~6900: training loss NaN → loss guard stop + emergency checkpoint (all its clips NaN).
     **Best checkpoint: step 5072.**
   - *Fix:* `--modular-magnitude-update multiplicative` (m ← m·exp(−lr·sign), relative step, sign can
     never change; SAT 3197c28, 7 tests). **Retry pending** (same recipe + only this flag).
     Workaround: `--exclude to_global_embed global_cond_embedder to_timestep_embed`.
   - *Literature:* no source reports DoRA magnitudes crossing zero. Muown (2605.10797) trains row
     magnitudes as their own optimizer variable; LionVote (2607.09266) finds sign steps ~2× too large
     for normalization params. Triage: `papers/deep-research/2026-09-24-dora-magnitude-optimization-research-triage.md`.
   - *Generalises:* **any fixed-size-step optimizer (sign, Lion, normalised) is scale-blind on 1-D
     parameters. Small-valued gains are where it bites first.** AdamW is also ≈ ±lr per element for a
     consistent gradient, so "use AdamW for the scalars" alone is not a fix. Adaptive damping that
     watches gradient chaos (PsiLogic, 2607.16268) would not have fired: the drift happened in a
     STABLE phase.

2. **A long demo render diverging to NaN is an early warning of the weights getting too far out,
   while the training loss still looks fine.** Seen twice: `audition_amult20` step 240
   (`rb_mid_4_48s` all-NaN), and goa3 step 6340, ~600 steps before the training NaN.
   *Rule:* a `[DEMO WARNING] … NaN/Inf` line means stop or back off; don't wait for the loss guard.

3. **LoRA A barely moves under Muon-family steps; the adapter reads a random slice of its input.**
   - *Cause:* A starts large (norm ≈99 over 229 modules) and the steps are fixed-size, so each is a tiny
     fraction of A.
   - *Evidence:* A's row space was 99.2% unchanged from step 240 to 1440 (B's column space: 35%); A carries
     ~7% of step energy.
   - *Tried:* `--modular-lora-a-lr-mult 20` rotated A (overlap 0.67 at step 240), but also made
     ‖B·A‖ 2.3× larger and one 48 s render NaN. **Confounded** (A rotating vs the whole adapter moving
     further).
   - *Status:* LoRA-TSD (2609.02734) would size steps on B·A directly. Unbatched it costs 8.5 s/step on
     our 229 adapters: ROCm `torch.linalg.qr` takes 12–17 ms per call, CholeskyQR2 ~2 ms. A batched port
     is ~a session.

4. **Gauge drift (A and B moving without changing B·A) grows as the loss flattens.**
   - *Evidence:* 4.8% → 12.4% of step energy over `audition_160ep` (chance ~2%), concentrated in the
     conditioning embedders; goa3 was already at 12.8% by step 2536.
   - *Harm:* none audible so far. B's velocity equals B·A's velocity to 3 digits, so trajectory velocity
     numbers are real function motion.
   - *Tool:* `eval/lora_gauge_drift.py`. Source idea: 2608.07436 (Muon keeps full steps after the loss is
     solved).

5. **Crackle clusters in the 20 s renders of the rare prompt; all 48 s renders stay clean.**
   `rb_rare_7_20s` had 166 jumps (audition, gone by step 720) and 887–1202 (goa3, persistent). Crackling
   clips go with latent std 1.3–1.4, against 0.9–1.1 for clean ones. `--demo-latent-clamp 1.20` is aimed
   at this (untested). *Open hypothesis:* sidecars say seconds_total = 380 s, so training computes the
   timestep shift for 4096 frames while the 20 s demos render at 256.

6. **Healthy trajectory band (for comparison):** audition velocity 57 → 36 per 1k steps, cosine 0.51 → 0.76.
   goa3 velocity 46 → 37, cosine 0.29, path efficiency 0.81 (more turning: more varied data, higher LR).
   Band that sounds good: 30–50. The runaway that collapsed rhythm was at 142.

### B. Failures of the INSTRUMENTS (runs judged on wrong numbers)

7. **Loss monitor reported half the true loss:** Lightning divides by `accumulate_grad_batches` before
   callbacks see it. Fixed by multiplying back.
8. **Loss guard was NaN-blind:** `nan > 1.0` is False, so NaN took the "healthy" branch. Fixed with `isfinite`.
9. **Schedule-Free eval swap skipped ModularOptimizer** (an `isinstance(FusionOpt)` gate). Demos
   rendered the training iterate instead of the averaged one: wrong weights judged. Fixed with `_sf_opt()`.
10. **Inert mechanisms credited for results:**
    - Escape velocity: its multiplier stayed at 1.0, while its buffer added 0.6 GB per checkpoint.
    - VADD tier 2: never fired.
    - Schedule-Free: inert when `c_warmup ≥ total steps`.

    Now audited live: `[MECHANISM AUDIT]` every 500 steps.
11. **Caption traps (would have trained on placeholders):**
    - `latents_avp` stored prompts are the artist name only (3 distinct values over 2,393 items); its
      captions are in `lumi/avp_captions_tiered.json`.
    - `latents_goa_bigset` stored prompts are the string `"None"`, and its sidecar is keyed by source path,
      which the latent-stem lookup never matched; this holds in `train_lora.py` too, pre-encoded.
    - `--source_weights` in `train_lora.py` is inert: nothing consumes the dataset's sample weights.
    - The dataset dill-loads the metadata fn on every item, so a closure over a 54 MB table would be
      deserialised per sample.

    All fixed in `train_lora_modular.py` with a startup caption audit per source.
12. **Metadata:** `run_meta.json` was written to the PARENT output dir (each run overwrote the last), and a
    loss-guard stop was recorded as `done`. Both fixed.
13. **Checkpoint duplication:** Lightning's periodic save plus milestone saves wrote 9.3 GB of duplicates.
    Use `--checkpoint_every 100000` with milestones.

### C. Operational traps
14. `--lr` defaults to 5e-6 (AdamW era): the modular optimizer barely moves. Always set it (5e-4 clean).
15. Without `--eval_demos`, the stock demo callback crashes at step 1 (torchcodec).
16. `VAR=x && python` does not export; env vars must be `export`ed (a covariance probe never armed this way).
17. The run NAME is not the recipe: `goa3_avp_r256_*` is rank 128. Trust `run_meta.json`.
18. Two GPU jobs at once (e.g. a matrix render plus training) slow both and glitch the desktop.
    Capping the GPU at 220 W (from 300) barely changed the step time.
19. Full Kronecker whitening is not viable on 12288-wide LoRA factors: one eigh takes 7.23 s, ×24 tensors
    per step. Gradient-covariance effective rank is only 90–228 of 8192; 95% of the mass needs rank
    512–2048.
20. *Open, not fixed:* the demo callback calls `torch.manual_seed(seed)` per clip, which reseeds the
    GLOBAL RNG that training draws noise from. It's suspected in earlier NaN episodes. An RNG
    save/restore around the render is designed but not implemented.
