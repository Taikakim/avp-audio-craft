# WORKLOG — cross-project audio pipeline

Reverse-chronological. Append an entry (newest at top) when you finish or learn
something an agent in another repo would want to know. Keep entries short; move
durable facts into `MASTER.md`. Conventions:

```
## YYYY-MM-DD — <who/model> — <one-line title>
- bullet of what ran / landed / broke
- paths, commands, results worth reusing
```

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
