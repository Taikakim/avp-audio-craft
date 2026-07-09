# LUMI-G bundle — ready-to-run scaffolding for the LatCH + DoRA campaigns

*2026-07-07, WINTERMUTE. Companion to `docs/lumi-transition-plan.md` (read that first for
the why; this dir is the how). Prepared before access; **access granted 2026-07-09**.*

## Allocation — EHPC-AIF-2026PG01-756 · "Diffusion model creative steerability for musical AI"

- **LUMI project:** `project_465003186` (LUMI-G) · **user:** `akekim` · login via the EuroHPC
  Federation Platform (EFP): `akekim@efp.lumi.csc.fi` (cert-based, ~10 h validity — regenerate the cert).
- **Budget (from `lumi-workspaces` 2026-07-09):** **5000 GPU(GCD)-hours** (0 used), 1000 CPU-Khours,
  20000 storage-TBhours; storage 134 days to removal (~26% of project time elapsed). 5000 GCD-h is a
  real allocation — the campaigns are cheap, and the **clean-room dataset regen is now affordable**
  (not just a stretch): full goa (4470) fits with margin, avp (~313) is trivial. Still estimate the
  encode GCD-h before the big run, but budget is no longer the binding constraint (calendar is).
- **Storage tiers:** `/project/project_465003186` **50 GiB** (code + models, permanent) ·
  `/scratch/project_465003186` **50 TiB** (data + runs) · `/flash/project_465003186` **2 TiB** NVMe
  (hot data during a run). Big latents/tarballs → scratch; models/HF cache → project (watch the 50 GiB).
- **Hardware:** MI250X (gfx90a), 2 GCDs/module, **64 GB/GCD**, 8 GCDs + 64-core EPYC per node →
  1 GCD/run + 7 cores/GCD (already set in `env_lumi.sh`). Stock images top out at **ROCm 6.2.4 /
  torch 2.7.1** (`lumi-pytorch-rocm-6.2.4-python-3.12-pytorch-v2.7.1.sif`) — SIF base, not 6.3.4.
- **Partition (from `sacctmgr` 2026-07-09):** the project is associated with **`standard-g` ONLY**
  — NOT dev-g/small-g (submitting there → `default_no_jobs` assoc, MaxSubmit=0 → `AssocMaxSubmitJobLimit`).
  All sbatch scripts use `--partition=standard-g` (MaxSubmit 210). **⚠️ Billing caveat:** standard-g is
  typically **whole-node-exclusive** (a 1-GCD job may bill all 8 GCDs). Fine for the hello test; before
  the campaigns, **either pack 8 GCDs/job or verify partial billing** — else single-GCD runs cost 8×.
- **Compliance (account-sharing ToU, LUMI MOTD 2026-07-09):** no third-party service or agent runs
  *under* this account; no server/tunnel exposed. Division of labour: **WINTERMUTE prepares locally,
  Kim executes on LUMI.**

*Project-number wiring is DONE (`project_465003186` sed across the bundle 2026-07-09). The one
remaining prep edit is the base-image ROCm version in `sa3-env.yml` — see Day-1 step 2.*

> ## 🚨 ACCESS MODEL — EFP is WebUI-submitted, NOT raw `sbatch` (2026-07-09)
> This project is accessed via the **EuroHPC Federation Platform (EFP)**. **Jobs are submitted
> ONLY through the web platform `https://workflows.my-eurohpc.eu`**, never via terminal `sbatch`
> — the SSH default account is `default_no_jobs` (MaxSubmit=0) precisely because direct Slurm
> submission is disabled. Confirmed against `docs.my-eurohpc.eu/workflows/quickstart` + three failed
> `sbatch` attempts (AssocMaxSubmitJobLimit → Invalid account/partition combination).
> **WebUI flow:** Data Management → *Job Scripts* (Create Jobscript) **or** *Containers* (Create
> Container) → *Workflows* → Create Workflow (name · cluster · **Partition** dropdown → `standard-g`
> · dataset staging · advanced) → *Create Workflow Execution*.
> **What this means for the bundle:** the `sbatch/*.sbatch` **script bodies** (the `srun singularity
> exec … python …` command + resources) still carry over, but they are **registered as EFP Job
> Scripts and launched via Workflows**, with partition/account/resources set in the workflow config
> (dropdowns) rather than executed by `sbatch`. SSH stays useful for data staging (`/scratch`),
> container build/upload, and fetching results. The Day-0/Day-1 `sbatch …` lines below are the
> *direct-LUMI* path and DO NOT apply on EFP — treat them as the logic to port into the WebUI.

## Contents

| File | What |
|---|---|
| `sa3-env.yml` | cotainr conda env → `sa3-train.sif`. **Edit the rocm index to match the chosen base image.** |
| `env_lumi.sh` | gfx90a env profile (air-gap offline modes, 7 cores/GCD, conservative MIOpen). Replaces our local `rocm_env` on LUMI. |
| `sbatch/latch_parity.sbatch` | Phase-5 step 1: one head (`rms_energy_bass`), 1 GCD, dev-g. Gate everything on this. |
| `sbatch/latch_all_features.sbatch` | **Campaign A**: job array, one LatCH head per feature × the full trick stack (EMA 0.999, grad-accum 2, ~20 ep early-stop, standardize, save-best-only). `sbatch --array=0-19`. |
| `sbatch/dora_run.sbatch` | **Campaign B**: parameterized DoRA runs (`--export=ALL,ENC=…,RANK=…`). One GCD each; brackets = a for-loop of sbatch calls. |
| `pack_data.sh` | Local staging: tarballs of `latents_sa3` + `latents_avp` (doubles as the overdue cold backup) + git-archive code snapshots + this dir. |

## Day-0: from passport to first job (the human steps, in order)

1. **Identity**: MyAccessID (EuroHPC's identity broker) — login via your home org or eIDAS;
   for a private person that's the national e-ID/passport-verified route. One-time.
2. **Project**: when the B&D application is approved, the project invite arrives through the
   EuroHPC Federation Platform → accept ToS → note the LUMI number (ours: `project_465003186`).
3. **SSH key**: upload your PUBLIC key in MyAccessID/portal profile. Propagation to LUMI is
   **not instant** (up to ~an hour). MFA per portal instructions.
4. **Login**: `ssh -i ~/.ssh/<key> <username>@lumi.csc.fi` (username assigned by the portal,
   not your email). You land on a login node — internet, no GPUs, shared: build/stage here,
   never compute.
5. **Hello world** (`sbatch/hello_world.sbatch` — needs nothing of ours):
   `sbatch --account=project_465003186 sbatch/hello_world.sbatch` → `squeue --me` →
   `cat hello-*.out` should end with "HELLO LUMI, the stack is alive". That proves
   account + queue + GCD + torch in one 10-minute job.
6. Then the Day-1 checklist below (container build, weights, data, parity).

## Day-1 checklist (when the project number arrives)

1. ~~sed the project number~~ **DONE** — `project_465003186` is wired across the bundle.
2. Pick the base image: `ls /appl/local/containers/sif-images/` → copy (don't symlink) the
   newest `lumi-rocm-*` → set the matching `--index-url` rocm version in `sa3-env.yml` →
   `cotainr build`.
3. Login-node (has internet): populate `HF_HOME=/project/<proj>/models/hf` — SA3
   `medium-base` + T5-Gemma (**gated**; `HF_HUB_DISABLE_XET=1`).
4. Upload + extract the `pack_data.sh` tarballs into `/project/<proj>/data/`.
5. `sbatch sbatch/latch_parity.sbatch` → compare the checkpoint against the local
   `rms_energy_bass` EMA reference (loads via `load_latch_from_checkpoint`, steers at
   gain ≈512 on the energy family).
6. Only then: `sbatch --array=0-19 sbatch/latch_all_features.sbatch` and the DoRA brackets.

## Decisions encoded here (so nobody re-derives them)

- **Trainer = the `--ema`/`--grad-accum` lineage** (`stable-audio-3/scripts/latch/train_latch.py`
  == `onnx/latch/train_latch.py`, the two have drifted slightly — the code tarball ships the
  stable-audio-3 copy; the latch-core unification remains the clean fix, MASTER §1).
- **Recipe = the validated damping stack** (EMA 0.999 + ga2 + early-stop ~20 ep,
  WORKLOG 2026-06-29): all four EMA variants beat non-EMA; ship `_best` (save-best-only).
- **Feature set = the 20 whole-track timeseries fields** (npz companions in `latents_sa3`),
  `relative_position_ts` excluded (position ramp, not a control). The dataset strips `_ts`.
- **Full telemetry on every run** (MASTER §4): wandb offline per run, synced from the login
  node — the DiT-block × feature controllability map needs every run logged.
- **1 GCD per run** — a LatCH head is ~5–7 M params, a DoRA r16 fits comfortably; the win is
  20 heads *in parallel*, not one head faster. No multi-GCD plumbing needed for these.
- **No flash-attn in v1** — SDPA parity first; FA on gfx90a is an optimization decision after
  profiling, not a blocker.
- **MIOPEN_FIND_MODE=2, TunableOp off** for first runs (mode-6 killed SA3-medium's DiT
  locally; tuning caches are per-arch and can't be carried over).
- **avp-DoRA lessons (local bracket, 2026-07-08)** — full block in the `dora_run.sbatch`
  header; the short version: **tempo instability is optimization-phase-driven, not aug-driven**
  (the no-aug arm was the *least* stable, refuting the earlier multimodality theory) — each
  config has a **stability window** in training (r16@lr2e-4 locks ~steps 1152-1440, collages
  after ~1700), so ckpt/300 and **compare ckpts across the whole run to pick the window**, not
  the last one; higher rank + lower LR push the window later/wider (prefer r128/r256 @
  lr~1e-4); augs **largely exonerated on tempo** — keep a 10% sample mainly to bound the Bungee
  *timbre* artifact (transient softening), not for tempo; familiarity-weighting's harm is now
  unproven (LR-phase vs aug-tail) — avoid until isolated; and `train_lora.py --source_weights`
  is a **silent NO-OP**. Plus the launch trap: **always pass `--duration 47`** (default 380s =
  8× sequence ≈ 45s/step, looks like a hung card) and kill process *groups*.
