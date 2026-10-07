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
     *Correction 2026-09-26 (CONTINUITY):* the step-6340 NaN was the RENDER fault (13e), not the model.
     Re-rendered merged from the averaged iterate: 24/24 clips finite, `rb_mid_4` clean at 6340
     (`<run>/cfg_sweep/`, README beside it). So the model was healthy at 6340, and step 6340 is a usable
     checkpoint too (5 of 6 clips clean, as at 5072). The failure is the training NaN at ~6900 only.
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

2. ~~**A long demo render diverging to NaN is an early warning of the weights getting too far out,
   while the training loss still looks fine.**~~ **WITHDRAWN 2026-09-26 (CONTINUITY).** Its two cases
   were both in-training demos of a LIVE DoRA adapter, which on this machine return NaN at random
   (13e). goa3 step 6340 re-renders clean when merged, so that case was the render fault; the other
   (`audition_amult20` step 240, `rb_mid_4_48s`) is untested but has the same exposure. *Rule now:* a
   `[DEMO WARNING] … NaN/Inf` from an in-training demo is NOT evidence about the weights. Re-render the
   checkpoint merged (`demo_cfg_sweep.py`) before drawing any conclusion.

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
13a. **`train/lr` is stale during warmup (CONTINUITY/worker C, 2026-09-24).** ModularOptimizer, FusionOpt
    and LoRA-TSD all apply their warmup ramp inside `step()` and never write it back to
    `param_groups`, so the logged lr sits at the target value from step 0. Fixed for LoRA-TSD only
    (`diffusion.py::_optimizer_current_lr`, which also reads the lr of the step about to run, not
    the previous one). **Still open for modular/FusionOpt:** don't read warmup behaviour off `train/lr`.
13b. **The update norm cannot see a bad batch (CONTINUITY, 2026-09-25).** Under normalised optimizers
    (Muon/NS, sign steps, LoRA-TSD's msign), `comp/spectral_update_norm` is set by lr and layer shapes;
    a gradient spike is normalised away before it reaches the step. So a flat update norm is no
    evidence that batches are well behaved. That was the flaw in the P95 step-governor proposal
    (`docs/PROPOSAL_ADAPTIVE_P95_STEP_GOVERNOR.md`, reviewed). Where a spike does act is the momentum
    buffer (~1/(1−β) steps of steered direction). *Fix:* raw pre-clip grad norms are now logged
    per kind (`grad/raw_norm_*`), and a flight recorder dumps the batch on a spike
    (`stable_audio_3/training/flight_recorder.py`, `--flight-recorder`, on by default). *Status:*
    built and CPU-tested, **not yet run on a real training**. Whether our batches spike at all is
    still unknown.
13c. **LoRA-TSD silently ignored an LR scheduler (cloud review, 2026-09-25).** `BatchedLoRATSD.step()`
    read lr, momentum, clip and the other settings from copies made in `__init__`, not from
    `param_groups`. A torch scheduler writes `param_groups[i]["lr"]`, so a warmup or decay schedule
    would have been accepted and done nothing, and so would changed settings restored by
    `load_state_dict`: the run trains at the starting lr with no error. *Status:* latent, never
    hit, because `train_lora_modular.py` attaches no scheduler. Fixed in stable-audio-tools `018ae1a`,
    which reads them from `param_groups[0]` every step. Test: half the lr gives exactly half the step,
    zero lr gives no step. Rule: a custom optimizer must read its hyperparameters from
    `param_groups` in `step()`, or schedulers are placebo.
13d. **A resumed optimizer could rewrite the checkpoint it was loaded from (2026-09-25).** torch's
    `Optimizer.load_state_dict` deep-copies `param_groups` but adopts same-device/dtype state tensors
    BY REFERENCE, so an optimizer that updates momentum in place then writes into the caller's
    state dict. It was found in `BatchedLoRATSD` by the second Opus critic and then in
    `LoRATSDReference` by the cloud review; both now clone on load (`fdff0ea`, `018ae1a`). A real
    Lightning GPU resume is not affected, because the CPU checkpoint tensors get copied to the GPU.
    It bites when one state dict is loaded twice (CPU tests, A/B from one snapshot). Same class of
    trap as the aliasing that `state_dict()` needed a deepcopy for.
13e. **Live-DoRA renders are history-dependent on our ROCm stack; the shampoo run's "step-6340 crash"
    was that, not the model (CONTINUITY, 2026-09-25).**
    *Symptom:* `goa3_avp_r128_shampoo_b16_3e4_2026-09-25` demos went to pre-clamp std 1.7e10 / 4.3e8 /
    6.6e6 / 3.7e6 on 5 of 6 clips at step 3804 (`--demo-latent-clamp` scaled them to 1.25 before decode,
    so they looked survivable), were fine at 5072, and were all-NaN at 6340, followed by a GPU page
    fault in `exponential_` (`training/utils.py:372`) as training resumed.
    *Evidence the model is healthy:* all 687 adapter tensors finite at 3804/5072/6340; `|lora_B|`
    11.46 → 13.64 → 15.54, `|lora_A|` ~99.5, `|magnitude|` ~2323, smooth. Re-rendering the same six
    demo clips offline from the averaged iterate x with the adapter MERGED: **54/54 finite, std
    0.78–1.41 at cfg 1, 3 and 7, at all three checkpoints** (`<run>/cfg_sweep/`).
    *Cause, isolated on a solo card:* with the DoRA parametrization live (weight rebuilt from B·A on
    every forward), the first render in a process is bit-exact (std 0.9581015706 every time) and
    same-shape repeats stay exact, but once calls of different shapes interleave (cfg 1 = batch 1,
    cfg ≠ 1 = batch 2, a decode) later renders of IDENTICAL inputs come back NaN, 1e11, or clean at
    random, differing between two runs of the same script. Base model: deterministic on the same
    sequence. Same adapter merged once (`parametrize.remove_parametrizations(..., leave_parametrized=True)`):
    deterministic and clean. CK flash-attention on or off makes no difference. Plain ops returning
    history-dependent values means a backend fault (ROCm 7.15-alpha / torch 2.14a stack: kernel,
    allocator or stream ordering), not our maths; hardware is unlikely, since the fault follows one
    code path and a fresh process is always exact. The op is not yet narrowed.
    *What it touches:* every in-training demo of a DoRA run (the callback renders a live adapter
    after training steps: exactly the interleaving that triggers it), and plausibly the unexplained
    non-deterministic NaN cells in MASTER §5 (`lion_lr1e-5` "rendered finite in a direct probe, not
    in batches"). Whether TRAINING steps are also hit is **open**: training is the same live path.
    *Also learned:* (a) a milestone `.ckpt`'s state_dict holds the Schedule-Free training point y
    (|y−x|/|x| on lora_B = 0.047 at 3804), while the demos render x from `optimizer_states`: offline
    renderers see different weights than the demos did. (b) The clamp at the renderer is a censor,
    not a guard: the 1e10 reading was in the log 2,500 steps early. (c) The P95 step governor and a
    rewired VADD tier 2 would both have been blind to this, since neither sees the render.
    *Fix / status:* `stable-audio-3/scripts/demo_cfg_sweep.py` merges by default (runnable block on
    KIM-TASKLIST); `train_lora_modular.py --no-inline-demos` (6b0238f) keeps milestone checkpoints and
    the loss guard but renders nothing in-process. Not yet done: merge-before-render in
    `model_matrix_gen` and the :8056 server.
    *Narrowing, same day (repro: `stable-audio-3/scripts/diag_dora_render_determinism.py`, exit 1 = fault):*
    exact with `PYTORCH_NO_CUDA_MEMORY_CACHING=1`; still faulty under expandable_segments, launch
    blocking, `parametrize.cached()`, rocBLAS instead of hipBLASLt, SDPA math backend, CK flash-attn,
    FlexAttention disabled, the ROCm 7.2.3 venv, and linux 7.2.6-arch (was -zen) with the display moved
    to the iGPU. NaN-poisoning free memory does NOT trigger it, so it is not a read of never-written
    memory. A per-layer checksum trace (exact process vs normal process) puts the first divergence at
    the DoRA weight of `layers.0.ff.ff.0.proj` (12288x1536), which then CHANGES between two hooks on the
    same tensor: something writes into it after it is produced. Rebuilding that weight standalone is
    exact (600 iterations), so it is the victim. Failing runs GPU-fault ("page not present") in
    unrelated kernels: a hipBLASLt bf16 bias GEMM, a PyTorch fp32 elementwise mul, `exponential_` in
    training. A 6-pass VRAM pattern test over 11.9 GB is clean. No unsafe tensor ops (as_strided,
    set_, untyped_storage, data_ptr, cpp extensions) in the SA3 render path. Remaining suspects: the
    amdgpu driver or HIP runtime memory management (shared by both ROCm stacks), or GPU page tables.
    The display-crash episodes (2026-09-25 12:38 and 14:34) were both triggered by these repro runs
    faulting on the card that also drove the display.
    *When it started (2026-09-26):* 0 NaN latents in 48,606 board renders before 2026-07-27, including
    many rank-128 adapter arms; 2.6–7 % on adapter arms after it; 0 % on full fine-tunes in every period
    (retroactive scan, so not a detection artefact). First NaN 07-29; the kernel went linux-zen 7.1.3 →
    7.1.5 on 07-27, and no other compute-relevant change (same ROCm 7.2.3 venv until 08-02, no renderer
    or adapter commits 07-21..07-30). Likely an amdgpu kernel regression; `linux-lts` 6.18.53 is the
    test. It also explains the 2026-09-08 `lion_lr1e-5` anomaly in MASTER §5 (NaN in batches, finite in
    a direct probe): that was this, not a marginal model.

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
    save/restore around the render is designed but not implemented. (`--no-inline-demos`, 13e,
    sidesteps it too: no render, no reseed.)
20a. **A Shampoo (or SOAP) modular run could not be resumed, twice over (CONTINUITY, 2026-09-25).**
    Found resuming `goa3_avp_r128_shampoo_b16_3e4_2026-09-25` at step 6340, the first such resume.
    (1) `UnpicklingError: Weights only load failed ... ShampooPreconditioner`: torch's safe loader
    refuses the optimizer state's own classes. Fix: `trainer.fit(..., weights_only=False)` on resume
    (stable-audio-3 `7073a14`). (2) Then `Expected all tensors to be on the same device` at
    `preconditioners.py:155` on the first step: torch's `Optimizer.load_state_dict` moves tensors held
    directly in the state, not tensors that are attributes of objects stored there, so Shampoo `C`/`P`
    and SOAP `L`/`R` stayed on the CPU. Fix: `ModularOptimizer.load_state_dict` moves them
    (stable-audio-tools `3449d4b`, `tests/test_modular_resume_device.py`, fails on the old code for
    both preconditioners). Any new optimizer state held as an OBJECT needs the same care.
    (3) Then it trained, but WRONGLY: `ModularOptimizer._step_count` was a plain attribute, not
    saved state, so the resume restarted it at 0. It drives LR warmup, the Schedule-Free
    `sf_c_warmup` burn-in and the momentum bias corrections. The step-6500 mechanism audit caught it:
    Schedule-Free averaging INERT (ck = 1, the averaged iterate overwritten by the fast one every
    step) where it had read ACTIVE 0.9996 before the crash, NorMuon deviation 0.42 against 0.24.
    Stopped after ~160 steps, nothing saved past 6340. Fix: `state_dict` now carries
    `modular_step_count` (stable-audio-tools `646259b`), and `ModularTrainingWrapper.on_train_start`
    sets the counter from Lightning's `global_step` for older checkpoints (stable-audio-3 `cb5517d`,
    log line `[resume] ModularOptimizer step count 0 -> 6340`). Verified on the relaunch: audit at
    6500 reads Schedule-Free ACTIVE 0.9996, NorMuon 0.2396. The mechanism audit is what made this
    visible at all: a silent resume would have handed back a "step 7608" checkpoint whose averaged
    weights were ~1300 steps old.

21. **DoRA rank-128 `dora128_mix3` lineage: TWO runs ran away, a THIRD (drop D-Adaptation
    entirely) genuinely fixed it — a 4-attempt story, not a single bad checkpoint (GHOST-NOTE,
    2026-09-24, revised same day after checking the run everyone had walked past).**
    - *Symptom:* `score_and_publish.py`'s latent-sanity gate halted on the `dora128_mix3` pattern
      — 12/36 (33%) of `dora128_mix3_nodas_20260918_231123`'s cfg7/w1 operating-point cells came
      back with z0 std 3.9–4.4 against a healthy ~1.1–1.3. Not the NaN/DC-file failure (§
      MASTER.md §5) — finite but blown-up, the milder cousin.
    - **Attempt 1 — `dora128_mix3_overnight_20260918_084329` (spectral_lr 1e-4, autoscale on):
      collapses hardest and earliest.** global_norm already 4085 at step 500, 9575 by step 1000
      (velocity 8705, the run's largest single-step move), plateaus ~10,200–10,470 through step
      4000 where the checkpoint sequence stops dead. This is the run the sibling `_conservative`
      restart's own `run_meta.json` describes (past tense) as having "collapsed."
    - **Attempt 2 — `dora128_mix3_conservative_20260918_143724` (spectral_lr 1e-5, autoscale
      STILL on): produced no checkpoints at all** (dir doesn't exist, only a launch log — crashed
      or was killed before step 500).
    - **Attempt 3, mislabeled `_nodas` despite NOT dropping D-Adaptation —
      `dora128_mix3_nodas_20260918_231123` (spectral_lr 1e-5, scalar 5e-6, `fusion_autoscale:
      true` per its own recipe): runs away later, not less.** `checkpoint_trajectory_stats.py`
      across all 15 checkpoints: global_norm 712 (step 500) → 1349 (1000) → 1716 (1500) →
      **7851 (step 2000, velocity 7652)** → peaks 12189 (~step 4200) → subsides to 8918 by the
      board-picked step 7500. Path efficiency 0.141 (wandering, not converging). Every
      transformer FFN's `lora_B` moved in near lockstep (8270–8358 velocity, layers 1–9) —
      uniform, non-selective. Same fingerprint as the 2026-08-10 full-FT/DoRA latent-scale-runaway
      family (`MASTER.md` §5), independent occurrence.
    - **Attempt 4, the REAL no-D-Adaptation run — `dora128_mix3_nodas_20260918_231801`
      (`fusion_autoscale: false`, spectral_lr 5e-6, scalar_lr 1e-5, cosine decay): genuinely
      converges, all 22,000 steps.** Its own `run_meta.json` (written at launch, unlike the
      other three) says so directly: "Run 3: drop D-Adaptation entirely (root cause of step-1599
      collapse in run 2 and ~step-600 in run 1)." Trajectory over all 44 checkpoints confirms it —
      global_norm stays in **99–114 for the ENTIRE run** (a 15% total increase vs the failed
      runs' 10–17×), cos-to-final climbs smoothly 0.89→1.0, path efficiency 0.216. **One resume
      artifact, not an instability:** at the step 3500→4000 boundary — exactly where the run's
      two wandb sub-sessions (`z18fy24b` then `e3hun0v6`) meet — d_from_init briefly drops from
      23.3 back to 1.9 (velocity spikes to 23.4, the run's peak) before resuming the same smooth
      climb for the remaining 18,000 steps. Reads as a checkpoint-reload quirk at the resume
      boundary, not a training problem — the run recovers on the very next checkpoint and never
      deviates again. **This checkpoint (`epoch=10-step=22000.ckpt`) was already the registered
      board pick and already passed the z0-std sanity gate cleanly** — it just hadn't been
      trajectory-checked, so nobody had confirmed WHY it passed until this session.
    - **So: dropping D-Adaptation/fusion_autoscale is the actual fix, not "an LR cut that delays
      the runaway."** My own first pass at this entry (same day) concluded "two LR reductions
      slowed the runaway, neither stopped it" from attempts 1 and 3 alone — true of those two, but
      wrong as a verdict on the RECIPE, because attempt 4 (checked later, after Kim asked to look
      for an earlier checkpoint) shows the mechanism-level fix works cleanly. Lesson: when a
      lineage has more than one restart, check the LATEST one's trajectory before concluding the
      recipe doesn't converge — the fix may already be sitting on the board, unverified.
    - *Evidence:* `checkpoint-stats/dora128_mix3_{nodas,overnight,nodas_231801_run3}_trajectory.
      {md,json,png}` (glob override needed on the flat-dir runs: `--glob "epoch=*-step=*.ckpt"`;
      the nested-wandb-id run needs `--glob "*/checkpoints/epoch=*-step=*.ckpt"`).
    - *Compounding instrument bugs:* `dora128_mix3_nodas_20260918_231123`'s `run_meta.json` was a
      stale copy of the `_conservative` restart's metadata (name, purpose, hypothesis all
      described the WRONG run — including claiming `fusion_autoscale` was off when its own recipe
      block said `true`). `dora128_mix3_overnight` had no `run_meta.json` at all. Only attempt 4
      (`_231801`) got real AT-LAUNCH notes, and it's exactly the one that turned out to matter —
      not a coincidence: writing the notes forces stating the hypothesis clearly enough to check
      later. The two undocumented runs cost real time here (had to reconstruct their recipes from
      training logs, which don't dump full argv).
    - *Fix / status:* **`dora128_mix3_nodas_20260918_231801`'s step-22000 checkpoint is the
      working arm; no swap needed there.** For the mislabeled attempt-3 run, its pre-runaway
      `epoch=0-step=1500.ckpt` (norm 1716) was added as a second manifest pick, rendered
      (12/12 cfg7/w1 cells, z0 std 0.52–1.52, 0 amplitude-jump corruption, 100% finite), and
      `score_and_publish.py --pattern dora128_mix3` now passes 36/36. The known-bad `epoch=3-
      step=7500.ckpt` pick stays registered as a documented witness, not removed. Sidecar notes
      (`recipe.notes`) added to both `_nodas_231123` and `_overnight`'s `run_meta.json` (a fresh
      file for `_overnight`, which had none) recording the diagnosis and pointing at `_231801` as
      the arm that actually works.

## 2026-09-27 — Melody-subspace loss WORKS by ear (Kim's first listen across all his models)

**Verdict (Kim, 2026-09-27 ~03:00, verbatim):** "now that I listened for the first time across all of my
models, I have to say the subspace stuff really seems to work." Earlier in the same pass: "the subspace thingy
actually seems to work, although at the cost of bass sometimes"; `goa5k_r128_shampoo_subloss_k5_2026-09-26`
step 8088 "has the most distinct melody" and on kl_2 "can also have a punchy beat and still melodies, it is
noticeably more melodic than of the ablation runs"; `subloss_v3sel_k5` ep19 "This just... Superb",
`subloss_v3sel_k2` ep19 "also just superb, more aggressive", `subloss_v3sel_k12` ep15/19 "coool";
`subloss_v3sel_k5_tgate` ep11 "very cool goa sound".

**Known cost:** the kick/bass tends to get thinner ("the kick is also very weak like with some subloss
tracks"; several renders read as a buildup/kickless section). Worth a counter-measure (e.g. a low-band term or a
lower K) rather than abandoning the loss.

**Measurement agrees but is weak:** in generated latents the v3 melody-subspace energy share is 0.029 ± 0.011
for the 24-epoch K=5 run vs 0.023-0.025 for every 3-epoch ablation arm (`eval/latent_stats_by_arm.py`); at 3
epochs the loss changes WHERE lora_B ends up (cos 0.93 vs no-subspace) but not yet the generated melody energy.
**Policy consequence:** keep the subspace loss in the recipe going forward (K=5, v3 basis
`lumi/melody_subspace15_selective_v3.npz`); it is now available in `train_lora_modular.py` (stable-audio-3
`6223be1`, manual §5f). Also: `subloss_*` arms deserve ptm renders (queued 2026-09-27).

## 2026-09-28 — melody-subspace loss's raw diffusion MSE is unchanged; the higher "loss" is pure arithmetic

Antigravity measured the decomposition directly (relayed by Kim), W cross-checked against
`ablation_goa5k_a00_full`'s own metrics.csv: `train/loss` = `train/mse_loss` + (K-1) x
`train/subspace_loss` + `train/var_barrier_loss` -- confirmed to within rounding (0.9565
reported vs 0.9558 = mse 0.804 + 4x0.0379, the residual being var_barrier_loss).

**So the raw generative objective (`mse_loss`) is essentially IDENTICAL with K=5 on (0.805) vs
off (0.808, a08_no_subspace) or plain AdamW (0.798)** -- every "K=5 runs read ~0.16 higher" number
anyone has looked at (a00 0.957 vs a08 0.811, goa5k subloss 0.971, the new 3e-3 warm-start
continuation 0.959) is the additive (K-1) x subspace penalty inflating the REPORTED total, not
the model fitting the denoising objective worse. Confirms/quantifies the qualitative note already
in `docs/train_lora_modular.md` 5f ("runs with different K are not loss-comparable") -- this is
that caveat with real numbers, not a correction to it.

**Practical consequence:** when reading any table that includes a bare `loss` column across a mix
of subspace-on and subspace-off arms (e.g. `ablation_goa5k_2026-09-26/REPORT.md`), subtract
(K-1) x subspace_loss before comparing, or compare `mse_loss` directly. Worth a header note on
that report and any future one; not fixing retroactively here, flagging so nobody re-derives it.

## 2026-09-28 — b0x AdaGC/gate ablation arms by ear against Base itself, and a jump at b04

**First direct A/B against Base (Kim, 2026-09-28):** listening to the recent goa5k ablation
arms, Kim "just now realised I should check against [Base]." At `kl_2 cfg7 w1`, `step=1011`:
`ablation_goa5k_b01_adagc104`, `b02_adagc3`, `b03_nogate_6e-5` all sound **close to Base itself**
— not just to each other. At `rb_rare_7 cfg7 w1` the same three arms have "a more snappy
psytrancey sound compared to base," so the closeness is **prompt-dependent**, not a blanket "b01-03
haven't moved."

**b04 is where the sound leaves Base's neighbourhood:** `ablation_goa5k_b04_nogate_6e-4` at the
same `kl_2 cfg7 w1` "takes a jump in a new direction." `b05_nogate_6e-4_adagc3` "sounds identical"
to b04 rhythmically/spectrally at that prompt. `b06_full_3e-3` "sounds rhythmically etc similar to
b05, but has lusher, richer sound with more of atmospheres and pads, whereas 05 is often more
constrained" — and b04 is in turn "even more constrained" than b05. So on the
constrained-to-lush axis: **b04 < b05 < b06(full_3e-3)**, while b04/b05/b06 share the same rhythmic
identity and all three sit apart from the close-to-Base b01/b02/b03 cluster.

Cross-reference with CONTINUITY's quantitative b0x direction/velocity read
(`ablation_goa5k_2026-09-26/REPORT.md`) is open — this session flagged it to CONTINUITY
(2026-09-28 DM) as a qualitative complement to check against whatever distance/direction the
b01-b06 series shows numerically; not yet reconciled here.

**Standing anomaly, cross-cutting (not b0x-specific):** the `kl_1` prompt is persistently odd.
Base renders it as fast psytrance; every other model tested, **including `base_ptm`**, renders it
as chill downbeat material. Recorded on `base`'s `kim_feedback` (`Misc/models_index_overrides.json`)
rather than here alone, since it isn't a training-recipe finding — it's a prompt/model interaction
nobody has explained yet.

**Also this pass, unrelated one-offs worth a note:** `e2_phm` (the PHM-adapter tier-1 experiment)
sounds "quite good" already at `ep0`/step 0 — early for a from-scratch adapter architecture to
sound coherent at all. `stereo_sweep_w0.0` (the w=0 control arm of the mid/side stereo-loss
sweep, whose treatment siblings OOM'd on launch per `docs/fleet-audit-2026-07-19.md`) is "not too
bad" at `ep1 x kl_2 cfg7 w1` — the first independent listening confirmation that this control arm's
own checkpoint is usable, separate from the provenance question about its treatment siblings.

**Open question from Kim, not yet answered:** the two new 3e-3 warm-started DoRA runs (plain and
K=5-subspace, both off `fullft_avp_t4096` ep7) are "overtrained already" by ~step 1516-2022 at
this 3e-3 / no-SNR-gate recipe, but Kim called the run itself "interesting" and floated a target
shape for a slower version: velocity around 50-70 by step ~1500, dropping below 50 by step ~3000.
Whether the b0x/a0x trajectory data already collected (`checkpoint-trajectory-stats`,
`ablation_velocity_report.py`) is enough to back out an lr/gate/AdaGC combination that would hit
that curve is open — referred to CONTINUITY (2026-09-28 DM) as an analysis question, not answered
here.

## 2026-09-29 — full-FT online-vs-EMA audit: a real code bug found along the way, and the results

Kim's question, "did we check that all our full-FTs are rendered from online, not EMA weights?",
had never been checked. Full audit: every full-FT/fp32cmp checkpoint on disk (107 across 40 run
dirs) scanned for EMA presence (23 carry one — only runs from 2026-08-04 onward, when EMA was
added to the trainer), then every full-FT arm (25 labels, fp32cmp excluded once found to actually
be DoRA adapters, not full-FTs — see `eval/rarity_bracket_manifest.json`'s commit history)
rendered at cfg7 both online and EMA (where available), so both sit on the board side by side.

**A real bug surfaced doing this, now fixed (`model_matrix_gen.py`, commit `b3db38a`).** The
2026-09-11 fix that taught `manifest_key()` to treat weights (online/ema) as part of a cell's
identity only touched the READ side — every live skip-check in the render loop still built its
own bare key with no weights suffix, so once an online cell existed for a (label,ckpt,cfg,w,
prompt), an `--weights ema` request for the SAME combo silently collided with it and skip-all'd,
reporting success while rendering nothing. All 11 first-pass EMA renders in this audit did
exactly that before the fix landed. Added `cell_key()` as the one place the key format is
defined; every skip-check and `manifest_key()` itself now call it.

**A second, unrelated process gap also bit this pass** (see the `sa3-canonical-clips` skill,
2026-09-29 note): local renders don't auto-stage their `.m4a` into the served copy, so ~640 of
the ~1860 rendered cells sat on Mantu unpublished until caught by spot-checking the live site.

**Results.** `fullft_avp_t256` (ep153) and `fullft_goa_t256` (ep38/69) both compare cleanly.
Two arms hit a **legitimate, guard-caught failure mode, not a rendering bug**: `fullft_avpaug_
t1024_fp32_lr1e-4_s1` ep11 and `fullft_suomi_t1024_fp32_lr1e-4_s1` ep11 both have an EMA shadow
at only ~1-2 half-lives (24% and 47% still its starting weights) — rendering with it produced
non-finite latents, and `z0_is_finite()` correctly dropped those cells rather than publish
garbage. This is exactly the "UNCONVERGED EMA" hazard `sa3-training` skill §1c/1d already warns
about, now with a concrete instance: an early-epoch EMA shadow isn't just "not fully learned
yet," it can be numerically unstable to sample from at all. The later epoch of both arms (ep19,
3.45 and 1.82 half-lives respectively) rendered clean.

Per-arm online-vs-EMA availability is now on the board for: `fullft_avp_t256`,
`fullft_goa_t256`, `fullft_avpaug_t1024_fp32_lr1e-4_s1`, `fullft_biggoa_t1024_fp32_lr1e-4_s1`,
`fullft_mix3_t1024_fp32_lr1e-4_s1`, `fullft_mixed_avp_goa_t4096`, `fullft_mixed_wd03`,
`fullft_mixed_wdfix_ddpbug`, `fullft_suomi_t1024_fp32_lr1e-4_s1`, `fullft_suomift_warm_
avpaug19_t1024_bf16_k5_s1`, `fullft_suomift_warm_goaft_t1024_bf16_k5_s1` — use the dora_table
`weights` filter or the model_matrix picker to A/B any of them by ear.

## 2026-09-29 — an epoch soup across a regime change renders broken (CONTINUITY)

**Symptom.** Merged soups of `fp32cmp_avp_t4096_bs1_lr1e4` (DoRA r128) over ep3/7/14/21/35 (`fullft_soup_fp32cmp_avp_t4096_bs1`:
`soup_mean`, and `soup_filtered` with a per-value outlier filter) render with z0 std **2.2–2.7** at every cfg. Every single
epoch of the run sits at 0.75–1.1 at w1, and the ep14+ep21 pair soup is 0.82–0.89.
**Cause.** ep35 is in a different regime in the latent-facing layers. ||ΔW_eff|| at ep14 / ep21 / ep35 is:
- `preprocess_conv`: 1.2 / 3.3 / **29.0**
- `postprocess_conv`: 0.35 / 1.34 / **9.8**
- L22 `to_local_embed`: 3.8 / 4.8 / **33.3**

The median matrix only doubles (30 → 63). ep35 renders normally on its own, so the rest of the network compensates for those
edge changes. A 1/5 share of them mixed into epochs without the compensation does not.
**Evidence.** `eval/ladder_soup_fullft.py` `soup_stats.json` (per-matrix epoch norms), and the z0 files in `Mantu/sa3_lora_runs/model_matrix/`.
The within-run direction check also flagged ep21→ep35 as the least coherent step (lora_B cos 0.80, versus 0.88–0.92 before).
**Why the filter did not help.** It drops single values that are outliers against the trend. A whole layer that moved is the trend.
**Fix / rule.** Average only within one regime. Check per-matrix ||ΔW_eff|| across the ladder first, especially
pre/postprocess_conv. A jump of several times the neighbouring growth marks a boundary. Rebuilt without ep35 as
`fullft_soup_fp32cmp_avp_t4096_bs1_no35`. There, filtered vs mean differs by a median of 0.06% per matrix (22% in preprocess_conv),
so nearly all of the first filter's effect had been ep35.

## 2026-09-30 — the `onset_per_beat` density target is doubled on 45% of latents_sa3's goa crops (madmom half-tempo) (CONTINUITY)

**Symptom.** Found while building density targets for the goa bigset: madmom's top tempo candidate came back as 65.9–69 BPM
on three of four goa tracks. In `latents_sa3`, **2,430 of 5,401** crops have `bpm_madmom` < 95; `bpm_essentia` has only 122 under 95 (median 142). madmom and essentia
disagree by more than 20% on 2,437 crops.
**Cause.** `mir/src/rhythm/bpm.py::estimate_bpm_madmom` returns `tempos[0,0]`, the STRONGEST candidate. On goa the strongest
RNN tempo peak is often the half-tempo one (e.g. [68.97, 0.267] above [136.4, 0.205]).
**Effect.** `onset_per_beat = onset_density * 60 / bpm_madmom` (the crop .json scalar) is **2x too large** on those crops. The
June density control runs (`onset_Fusion_opb_*`) trained on it. W's 2026-06-26 corr(onset_per_beat, bpm) = −0.81 is
plausibly dominated by this: a halved bpm and a doubled opb on the same crop is a built-in negative correlation.
**Evidence.** A count over `latents_sa3/*.json` (bpm_madmom vs bpm_essentia). The candidate lists come from `madmom.features.tempo.TempoEstimationProcessor`.
**Fix / status.** New targets (`latch/extract_density_targets.py`) take the strongest candidate inside [95,190) BPM, else
octave-fold. The existing `latents_sa3` scalars are NOT rewritten — whoever next trains on `onset_per_beat` there should
recompute it from `bpm_essentia`, or from the folded madmom value. Not yet checked: whether the June opb heads' learned
behaviour reflects the doubling.

## 2026-10-07 — LatCH head bracket: the "noise floor" was 20x too small, because the data-worker count changes the run (CONTINUITY)

**Symptom.** Phase C (density head on the goa bigset, 10 epochs, 9 arms; `Mantu/latch_sweep/modular_2026-09-30/REPORT.md`) ranked arms by
differences of 0.003–0.006 against a seed-to-seed spread of 0.0002 (C01 0.1955 vs C02 other seed 0.1953) and concluded "the plain
recipe wins": radial brake 0.1986, escape velocity 0.1995, brake+EV (C09) 0.1991, burn-in 0 / 3000 0.1997 / 0.2017, sf_r=2 0.1976.
Phase D's anchor re-run D02 (the C01 recipe again) scored **0.1995**.
**Cause (narrowed, mechanism not found).** D02 differed from C01 in exactly two things: `--num-workers 16` (C01: 8) and `SAVE_ALL=1` (a
checkpoint per epoch instead of best-only). **D16 = C01 with 8 workers and SAVE_ALL=1 reproduced C01 at every epoch** (val 0.3382, 0.2583,
0.2350 … 0.1987, 0.1955), so SAVE_ALL and the new Lion / `--mod-late-from` code are innocent, runs are bit-reproducible at a fixed worker
count, and **the worker count changes the realisation**. Why (per-worker data order / augmentation draws?) is NOT established.
The 0.0002 "noise floor" compared two seeds at the SAME worker count: it measured one source of variation and was read as all of it.
**Evidence.** Per-epoch val curves of C01 / D02 / D16 (`phaseC/C01_recipe/train.log`, `phaseD/D02_C01_anchor`, `phaseD/D16_C01_w8_audit`).
The worker effect is arm-dependent: C09 moved 0.1991 → 0.1986 (8 → 16 workers) but the plain recipe moved 0.1955 → 0.1995. Within one
worker count the brake+EV effect flips sign: 8 workers C09 − C01 = +0.0036; 16 workers = −0.0009. Phase D so far (all 16 workers):
D01 C09 0.1986, D02 C01 0.1995, D03 late-switch@2000 0.1969, D04 late@4000 0.1984, D05 lr 3e-3 0.1969, D06 lr 6e-3 0.1993 — all inside ±0.004.
**Effect.** Phase C's ranking of brake / escape velocity / burn-in / sf_r is **not established** below ~0.004; Phase B's single-seed b16
0.194 likewise. What stands: effects well above 0.004 — modular-vs-AdamW (Phase A 0.357 vs 0.408), Schedule-Free on/off (0.203 vs 0.255).
**Fix / status.** Hold `--num-workers` fixed within a comparison and record it in the run meta; treat Δ < 0.004 as noise until repeats at ≥ 2
worker counts say otherwise; Phase D arms D03+ compare only against D01 / D02 (same 16 workers), not against Phase C. Instrument rule
(CLAUDE.md "audit the instrument"): a noise floor must be measured under every nuisance setting a comparison may differ in, not only the seed.

## 2026-10-07 — two operational traps from re-rendering the mixtape corpus (CONTINUITY)

**C1. A re-render at the default duration is a DIFFERENT clip, not a re-render.** *Symptom:* merged-adapter re-renders of the
mixtape's `d48` clips came out 26 s long (z0 T280) instead of 47.55 s (T512), and a "688 -> 13 jumps" win looked like proof the
merge fix works. *Cause:* `model_matrix_gen.py` renders at `DURATION` unless `--duration-seconds 47.55` is given; the sample size
changes the noise tensor, so the same seed gives a different clip, and jump counts scale with clip length. *Evidence:* 45 of 47
new latents were T280, the 2 T512 ones were the only true re-renders. *Fix:* pass `--duration-seconds 47.55` for any `d48` clip
and check `z0.shape[-1] == 512` before comparing; only then is old-vs-new latent a paired test of the render fault.

**C2. A render started beside a training run can OOM the TRAINING.** *Symptom:* LatCH Phase D arm D13 (dim 512) died after 7 s,
rc=1, CUDA OOM, while a model_matrix_gen render of mine held ~7 GB on the same 16 GB card. *Cause:* `SHARE_GPU=1` skips the GPU
lock, and my launch guard only checked free VRAM once, at start; the other process grows later (D13/D15 reach 9 GB), so whichever
allocates last fails, and here that was the training. *Evidence:* `phaseD/D13_dim512/train.log` OutOfMemoryError at `latch.py:130`;
my own groups failed the same way ("0 bytes free", 7.14 GB allocated by PyTorch). *Fix / status:* D13 re-run alone (0.1908, the
number in EXPERIMENTS E5); rule: when a run has an unattended arm list, do not start a second GPU job beside it, serialise behind it.
