# Lessons learned — mistakes to not repeat

Cross-project, with the *reasoning* so they don't get re-litigated. The terse
list is MASTER §5; this is the explained version.

## Environment / venv

- **Wrong mir python.** `mir/.venv` lacks essentia and silently degrades madmom→librosa,
  so features come out subtly wrong with no error. Use `mir/bin/python`.
- **Three Python versions can't share a venv** (3.10/3.12/3.13). Name the venv by absolute
  path in every command; never trust bare `python`.
- **Stale `rocm_env.sh` shell env.** The YAML applies via `setdefault`, so a terminal with
  old exports silently pins wrong tunings dir / inference profile (disabling tuning even in
  training). Check `env | grep -iE 'tunableop|miopen|triton'` first when perf looks off.
- **Tunings dir is torch-version-specific.** `~/pytorch-tunings-7.2.3` is for torch 2.10;
  the `-7.2.2` CSV fails TunableOp's `PT_VERSION` validator under 2.10 and silently no-ops.
- **SA3 deps not in pyproject:** `dill`, `pytorch-lightning`, `wandb` had to be pip-installed
  into `.venv` for the trainer. `uv sync` (without `--inexact`) strips hand-installed pkgs.

## ROCm / kernels

- **`MIOPEN_FIND_MODE=6` crashes SA3 medium's DiT** — MIOpen `std::vector` assertion →
  coredump. (Fine for the tiny LatCH heads; it's a large-conv-shape issue.) Use mode 2 for
  SA3 medium. The yaml's "training profile" default of 6 is wrong for this model.
- **batch=1 variable-length → kernel-cache thrash.** Every unique sequence length is a new
  GEMM/Triton shape; the autotuner never settles. Fix: fixed T=4096 crops
  (`training-findings.md` has the full chain). Don't pad short tracks — that's just another
  shape; drop them.
- **A coredump cascades.** Killing a crashed multi-GB GPU process triggers `systemd-coredump`
  to write a multi-GB dump → load average spikes to 40+, other apps get OOM-killed. If a
  GPU job dies hard, `sudo coredumpctl` / clear `/var/lib/systemd/coredump` and consider
  masking coredumps during heavy GPU work.
- **fp16 NS5 diverges** (FusionOpt); **fp16_safe** (rescale+fp32 accum) is half the speed of
  bf16 for ~0.5 % quality. **bf16 is the hot-dtype.** (LATCH_RESULTS §20D/E.)
- **INT8/INT4 quant is non-functional on ROCm.** Use bf16 + FA2.
- **Flash-Attention is built but INACTIVE by default on the torch-2.10/2.12 ROCm venvs.** The
  CK `flash_attn 2.8.4` wrapper auto-routes to the `aiter` Triton path unless
  `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` is exported *before* `import torch` — forgetting it
  logs `No module named 'aiter'` + disables FA → SDPA/flex fallback, **30–100% slower**. Set it on
  every train and inference run (`sat-venv`, `stable-audio-3/.venv`, `sa3-rocm7.13-test`). mir's
  own rocm-7.2 venv is the exception: it runs Triton FA2 with `=TRUE`. (`docs/flash-attn-ck-rdna4.md`.)
- **TunableOp freezes on RDNA4 + torch-2.12.** Pointing it at the `pytorch-tunings-7.14` cache hangs
  the kernel-selection path (trips even when the validator *passes*); set
  `PYTORCH_TUNABLEOP_ENABLED=0` + `MIOPEN_FIND_MODE=2` (with CK FA, GEMM tuning is marginal anyway).
  This is the torch-2.12 case — distinct from the torch-2.10 tunings-dir lesson above, where tuning
  is wanted.

## Audio I/O

- **Audio writers CLIP fp16 / out-of-range floats.** `torchaudio.save` (especially the new
  torchcodec backend) and most WAV writers expect samples in [-1, 1]; feeding fp16 or SA3's raw
  >1.0 peaks clips/distorts (this bit the riffer auditions). Always **float32 → peak-normalize (or
  clamp) → int16 PCM** before writing. Use the shared helper `sa3_control.audio_io.save_audio()`,
  never `torchaudio.save(x.float().cpu(), …)` raw.

## Data / latents

- **Two incompatible latent grids.** SAO-Small/SA1 = 64-dim @ 21.53 Hz (T=256). SA3 = 256-dim
  @ 10.767 Hz (T=4096, SAME-L encoder). They are different VAEs; never feed one model the
  other's latents. Both dirs are confusingly called `latents*` on Lehto.
- **Stale paths in old memories.** `Mantu/.../Goa_Separated_crops`, `Lehto/goa-small`,
  `Lehto/goa-stems` are **gone**. Verify paths against the filesystem; MASTER §2 is current.
- **Removable drives.** Mantu + Lehto unmount; a 404 means unmounted, not deleted. Work stalls.
- **Don't train off Lehto's removable `latents_sa3`.** Cold random reads off the removable drive
  crawl (~2 MB/s) and were one cause of the SA3 control-adapter step-0 hang. Use the non-removable
  NVMe mirror `/home/kim/Projects/latents_sa3` (13 G, complete copy) for throughput-bound work;
  Lehto stays the canonical copy.
- **The encoder default `sample_size` (~285 s) silently crops long tracks** and picks one
  random window — throws away ~38 % of a median track. Use beat-aligned chunking to T=4096.

## Training methodology

- **Don't compare val_median across different loss settings.** Convert to raw MAE first;
  `--standardize`/`huber_beta` change the units (§18 "347 % regression" was a unit artifact).
- **Subset ≤ 0.3 rankings are noise.** Cross-seed std at 30 % data > the entire optimizer
  spread. Use ≥0.6 (ideally full) for production decisions; subsets for coarse screening only.
- **Demos fire at step 1** regardless of `--demo_every` (the `(step-1) % every == 0`
  condition), and each is ~10 min. Disable for short/tuning runs.
- **Guidance must run fp32 on SA3** — TFG backprops through model+head; SA3's default fp16
  clashes with grad dtypes.
- **TunableOp/torch.compile autotune on the FIRST step** of a new shape — that step can take
  20+ min. Don't set a tight timeout and conclude it hung.

## Process / coordination

- **Per-project Claude memory is siloed by cwd** — a fact learned in one repo is invisible in
  another. That's why this `docs/` + `MASTER.md` layer exists. Put cross-cutting findings here.
- **Branch drift.** Trained checkpoints can require model code that only exists on a feature
  branch (e.g. adaln_zero LatCH was on `latch-rms-control` while `main` lagged → loaders
  failed). Note merges in `WORKLOG.md`.
- **Branch switches wipe untracked work.** `git switch` on a repo with untracked scripts/
  renders can lose them (recoverable via `git stash` trees if you're lucky). Commit or stash
  before switching.
- **One GPU, multiple instances.** A long GPU job holds VRAM (the SA3 encode held 14/16 GB)
  and hard-blocks parallel work. Encodes are resumable (skip-existing) → cheap to pause.
  Note GPU-holding jobs in `WORKLOG.md`.
