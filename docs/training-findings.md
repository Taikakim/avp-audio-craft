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
- Data: `--encoded_dir /run/media/kim/Lehto/latents_sa3` (T=4096 beat-aligned crops).
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
