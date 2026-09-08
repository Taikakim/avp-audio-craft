---
name: sa3-training
description: Use BEFORE launching, resuming, or interpreting any SA3/SAME training run (train_lora.py, full fine-tunes, LoRA/DoRA, optimizer or LR brackets) — the local, hard-won facts about EMA, optimizers, LR decoupling, the GPU lock, venvs, and what a run must record at launch. Read it when an agent trains, before choosing an optimizer or LR, and before loading a trained checkpoint for rendering or warm-start.
---

# SA3 training — what we know locally

> Written 2026-09-08 (Kim direct: *"everything useful and locally we know should go there,
> read whenever an agent trains"*). This exists because the same facts kept being
> re-derived, and because two of them — the EMA time constant and the GPU lock — silently
> produce **wrong results rather than errors**.
>
> Companion skill: **`sa3-canonical-clips`** — how to render the standard clip set for a run
> once it is trained. Cluster work: **`lumi-ops`**. Cross-repo facts: `MASTER.md`.
> Experiment registry: `EXPERIMENTS.md`. Never duplicate those here; point at them.

## ⛔ 1. THE EMA TRAP — the one that silently destroys a comparison

**`--use_ema` keeps an EMA shadow of the DiT weights (full-finetune ONLY — LoRA/DoRA
force-disable it). Default `--ema-beta 0.9999`. That is a time constant of roughly
10,000 optimizer steps.**

⇒ **On a short run the EMA is still mostly its own starting point.** A 3,000-step run's EMA
is ~74% the weights it started from. A 6,000-step run's is still heavily weighted toward
early training.

**Why this is dangerous rather than merely suboptimal:** anything that loads a checkpoint
**prefers the EMA shadow when one is present**, and does so silently:

- **Rendering** — `eval/model_matrix_gen.py --weights auto` (the DEFAULT) = EMA if the
  checkpoint carries one. Render a 3-arm 3,000-step ladder this way and **every arm sounds
  like the base model**, because you mostly rendered the base. The arms look identical and
  the experiment reads as a null.
- **Warm-start** — `train_lora.py --init_state_ckpt` uses
  `("diffusion_ema.ema_model.",) if _has_ema else ("diffusion.model.", "model.")`. Same
  preference, same silence. You can warm-start from what is nearly the base and think you
  continued a run.

**Practice:**
- **Short run (≲10k steps) ⇒ render with `--weights online`.** State it in the run's notes.
- **Long run ⇒ EMA is genuinely better** (damps late-training drift; ~0.9999 tracks late
  sharpening). This is why `run_meta.recipe.notes` on some LUMI arms says *"RENDERING MUST
  LOAD THE EMA WEIGHTS"* — that is correct **for those long arms** and wrong for a 3k-step
  local bracket. **The rule is not "always EMA" or "never EMA" — it is a function of step
  count against a 10k-step time constant.**
- **Check what the siblings used** before adding cells to an existing arm, so one board row
  isn't half EMA and half online: the staged manifest records it —
  `grep -m1 '<label>' /home/kim/evals_aac/model_matrix/manifest.jsonl` → `"weights"` field.
- A checkpoint carries BOTH sets: `diffusion.model.*` (online, where the optimizer is) and
  `diffusion_ema.ema_model.*` (the shadow). Presence of the EMA keys is not a recommendation.
- `--ema-warmup-steps` (default 100) hard-tracks the online weights first so the EMA starts
  from a real point rather than init. It does **not** rescue the time-constant problem.

## 2. The GPU lock — `rocm-smi` is ground truth, lockfiles are claims

- **Always** `Misc/gpu_guard.sh acquire <HANDLE> $$` / `release <HANDLE>`, with a
  `trap ... EXIT`. Never hand-write `/tmp/gpu.lock` — filelock owns its format and a
  hand-written one strands the lock for the whole fleet. `gpu_guard` reclaims dead locks by
  itself; do not "clean up" by deleting the file.
- **A job can hold the card with NO lock.** Observed 2026-09-08: a 6-hour `train_lora.py`
  (Lion 5e-5) held 87% VRAM with `/tmp/gpu.lock` empty. Only the guard's `rocm-smi` check
  refused the second job. **So: never infer the card is free from an empty lockfile.**
- **`pgrep -f <pattern>` matches its own wrapper's cmdline.** `until ! pgrep -f render_x`
  never becomes true, and `pgrep -f train_lora` "finds" a training that is not running. Both
  have cost real time. Match on the interpreter (`pgrep -x python3.13`) or exclude the shell.
- To queue behind someone else's job, retry `gpu_guard acquire` on a timer. Do not preempt.

## 3. Venvs and env — absolute paths, always

- SA3 / SAT / consolidated → **`/home/kim/Projects/SAO/.venv/bin/python`**
- MIR features / Audiobox / MERT → **`/home/kim/Projects/mir/mir/bin/python`** (note the
  doubled `mir/mir` — `mir/bin/python` does not exist)
- The latent player runs under **`stable-audio-3/.venv`**, not `SAO/.venv`.
- `export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` **before** `import torch`.
- Never `HIP_VISIBLE_DEVICES=""` — flash_attn/aiter probes a Triton driver at import and crashes.
- If a run dies on `librocm-openblas.so.0`, it is **not** missing — it ships under
  `_rocm_sdk_core/lib/host-math/lib/`. Prepend that to `LD_LIBRARY_PATH`. (A non-recursive
  `ls` "proved" it absent once; the conclusion was wrong.)
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` fixes fragmentation OOMs on the 16 GB
  card that look exactly like a hard capacity limit.

## 4. Optimizers — what has actually been measured here

**The optimizer is a STYLE tool, not just a convergence tool (Kim direct, 2026-09-08).**
On the fusion-vs-adamw campaign, Lion clips are *fine* but **stylistically distinct** from
both AdamW and Fusion, which over a long run converge toward sounding like each other more
than either does with Lion. Kim reports the same effect independently on **SDXL and Flux**.
⇒ Treat optimizer choice as a *creative* axis worth auditioning, not only a loss-curve
decision — and never assume two optimizers at matched loss produce interchangeable models.

- **The base is AdamW-shaped.** SA3's pretrain used Muon on 2D matrices (QKV/FFN) and AdamW
  on norms/biases, but Muon was adopted late and briefly ⇒ the released base is
  overwhelmingly AdamW-shaped. Relevant to any full-FT optimizer choice.
- **Zach (Stability) on Muon:** *"I run Muon at 1e-3 for pretraining… around 10x what I would
  use for AdamW"*, with *"a quick warmup and basically no decay"*, and *"keep the AdamW
  parameters at normal AdamW LR."* The **ratio** is the transferable part.
- **FusionOpt has TWO parameter groups** — spectral (matrix/Muon-side) and scalar
  (AdamW-side) — via `build_fusion_param_groups(spectral_lr=…, scalar_lr=…)`. Both group-step
  functions read `group["lr"]`. **Until 2026-09-05 nothing ever passed them**, so every
  historical Fusion run used ONE LR for both groups. `train_lora.py` now takes
  `--spectral-lr` / `--scalar-lr`; omitting both threads no key and reproduces old runs
  byte-identically.
- **Measured LR facts (local, 16 GB):** best local Fusion ≈ **5e-6**. The usable
  **spectral-group ceiling is below 1e-3** — a dual arm at spectral 1e-3 / scalar 1e-4
  destabilised and never recovered (median train loss 2.1–2.7 vs 0.79 baseline, 38% of
  logged steps spiking >5, peak 15832.9, `gradient_clip_val 1.0` did not contain it), and
  **Kim confirmed by ear that its clips were "utterly degraded"**. Evidence supports only
  1e-4 > 1e-5 so far.
- **Reduced Fusion is not the same optimizer.** The default component set
  (`mona,ns5,normuon,sf`) OOMs a 1.5B-trainable full-FT on 16 GB, and so does `--hyperball`
  alone. Dropping `sf`+`mona` fits — but such a run **cannot speak to MONA's or
  Schedule-Free's contribution**, and Schedule-Free is the component Kim associates with the
  weight-growth pathology. Say so in `run_meta.recipe.notes`.

## 5. Multi-GPU (LUMI) — read `lumi-ops` first

One fact too expensive to re-learn: **`srun --gpus-per-task=1` + Lightning's
`SLURMEnvironment` auto-detect is UNRELIABLE.** It has silently produced **8 uncoordinated
single-GPU trainers** writing `-vN` collision filenames into one dir — every rank logged
`LOCAL_RANK: 0`, and each `-vN` is a **separately trained model** (521/522 tensors differ),
not a duplicate. Use `srun --ntasks=1` + `torchrun --standalone --nproc-per-node=N`, and
**verify with `grep -h LOCAL_RANK <log> | sort -u`** (want 0..7) before trusting any run.

## 6. What a run MUST record — at launch, not afterwards

Full rule in `CLAUDE.md` ("Training runs — write the notes AT LAUNCH"). The short version:

- The sbatch/launch script writes **`run_meta.json` into the run dir** via heredoc, so a run
  cannot start without one. Proven pattern: `lumi/sbatch/fullft_fleet.sbatch:91`.
- Fields nothing else can reconstruct: **`purpose`** (what question, who asked, EXPERIMENTS
  id), **`hypothesis`** + kill-criterion, **`status`** (running|done|abandoned **and why**),
  **`recipe.notes`** (the operational traps — EMA choice, precision, reduced-optimizer
  caveats), and `result` / `kim_feedback` pre-seeded `null`.
- **A local run with no `run_meta.json` is the normal failure.** `lion_lr1e-5` has none; its
  purpose had to be reconstructed after the fact from the run dir, and that reconstruction is
  flagged as such in `Misc/models_index_overrides.json`. Do the same rather than let a guess
  read as a record.
- Register the experiment in **`EXPERIMENTS.md`** the same session. `run_meta` says what the
  arm IS; EXPERIMENTS says why it exists.
- Verdicts afterwards go in **`Misc/models_index_overrides.json`** (`note`, `recipe`) and in
  the run's own `run_meta.result` / `kim_feedback`. **`run_meta.json` may outlive the
  weights** — when Kim deletes a failed run's checkpoints, it becomes the entire record.
- **Never hand-edit `eval/model_census.html`/`.csv`** — generated. Rebuild with
  `eval/build_model_census.py --rescan`, every drive mounted.

## 7. Reading a training result

- **Audit the meter before believing a null or a win.** A broken measurement fails toward
  "no effect"; a saturated one can fail toward a false positive. The dual-LR run's bin
  **means** read 405→84 and looked like convergence — outlier-dominated. **Median + spike
  count** was the correct meter. Ask: does this metric have dynamic range here, what does a
  trivial baseline score, and has this tool ever produced a positive result?
- **Listen before you build measurement.** Kim's ears have closed two experiments in a day
  that descriptor suites could not. Cost-order the LISTEN, not just the compute.
- `--no_demos` on every multitorch LUMI training job (the demo callback needs torchcodec and
  crashes the run ~4 min in).
