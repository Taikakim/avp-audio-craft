# WORKLOG — cross-project audio pipeline

Reverse-chronological. Append an entry (newest at top) when you finish or learn
something an agent in another repo would want to know. Keep entries short; move
durable facts into `MASTER.md`. Conventions:

```
## YYYY-MM-DD — <who/model> — <one-line title>
- bullet of what ran / landed / broke
- paths, commands, results worth reusing
```

---

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
