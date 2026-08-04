# LUMI-G bundle — ready-to-run scaffolding for the LatCH + DoRA campaigns

*2026-07-07, WINTERMUTE. Companion to `docs/lumi-transition-plan.md` (read that first for
the why; this dir is the how). Prepared before access; **access granted 2026-07-09**.*

## Allocation — EHPC-AIF-2026PG01-756 · "Diffusion model creative steerability for musical AI"

- **LUMI project:** `project_465003186` (LUMI-G) · **user:** `akekim` · login via the EuroHPC
  Federation Platform (EFP): `akekim@efp.lumi.csc.fi` (cert-based, ~10 h validity — regenerate the cert).
  **⚠️ SSH gotcha (2026-07-14): 'Permission denied (publickey)' has TWO causes — check the cert
  first: `ssh-keygen -L -f ~/.ssh/id_efp.lumi.csc.fi-cert.pub | grep Valid`. (a) cert EXPIRED
  (~10 h validity → expires daily): download a fresh cert from the WebUI's SSH access section and
  overwrite `~/.ssh/id_efp.lumi.csc.fi-cert.pub` — key + ssh config stay unchanged. (b) cert
  valid but WebUI session stale: log in at workflows.my-eurohpc.eu again and SSH starts working.
  Also: the cert file name (`id_efp.lumi.csc.fi-cert.pub`) doesn't match the key (`id_EFP`), so
  ssh needs the `Host efp.lumi.csc.fi` block in `~/.ssh/config` (User/IdentityFile/CertificateFile
  — added 2026-07-14) or explicit -i/-o CertificateFile flags. Long rsync uploads: use
  `--partial` — a mid-transfer cert death resumes instead of restarting.**
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
| `sbatch/arc_rollout.sbatch` | **ARC-Forcing** (task #46) step 1: build the self-rollout dataset (`eval/arc_rollout_dataset.py`) — re-render contexts through the model so training sees its OWN drift. Writes `.npz` + `manifest.json`. |
| `sbatch/arc_train.sbatch` | **ARC-Forcing** step 2: `train_lora.py --arc-data` on the rollout dir (rank 128, alpha 128, lr 1e-4). Clamps the drifted context via the inpaint keys; loss on the free region. |
| `sbatch/longctx_t1024.sbatch` | **Task #50** goa long-context arm, `--frames 1024` (95.108 s); LoRA r128/α128, lr 1e-4, 8 ep. |
| `sbatch/longctx_t2048.sbatch` | **Task #50** goa long-context arm, `--frames 2048` (190.216 s); **LUMI-only** (local 16 GB can't hold it). Same recipe. |
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

## Run order — ARC-Forcing (task #46) + long-context arms (task #50)

*(EFP note: these are the `srun singularity exec …` bodies to port into WebUI Job Scripts +
Workflows, same as the rest of the bundle — see the ACCESS MODEL banner above. Partition/
account/resources go in the workflow config; the `--export=ALL,KEY=VAL` knobs map to the
workflow's env/parameter fields.)*

- **ARC-Forcing is a 2-step PIPELINE — rollout BEFORE train (hard dependency):**
  1. `arc_rollout.sbatch` builds the self-rollout dataset into `OUT` (default
     `/scratch/<proj>/runs/arc_rollout_ds`). Pre-stage the `LORA_CKPT` whose drift you want
     captured under `/project` (omit for base-model drift).
  2. `arc_train.sbatch` reads that SAME dir via `ARC_DS` — **set `ARC_DS` to the rollout's
     `OUT`**. Since `/scratch` auto-purges, keep both inside one retention window, or copy the
     dataset to `/project/<proj>/data/` and point `ARC_DS` there.
  - On EFP, chain them as two workflow executions (rollout → train) or gate the train on the
    rollout's completion; do not launch train until the rollout's `manifest.json` exists.
- **The long-context arms (`longctx_t1024`, `longctx_t2048`) are INDEPENDENT** — of each other
  and of the ARC jobs. Submit any/all concurrently (each takes one GCD). No ordering.
- **First-batch check for the longctx arms:** confirm the trainer logs the exact crop length
  (T=1024 / T=2048, not ±1) before letting a run go the night — the `--frames` path exists to
  dodge the seconds→ds-ratio rounding (MASTER §5, Kim DIRECT 2026-07-13).
- **Compare-across-run, don't take the last ckpt:** every training arm checkpoints per epoch
  (`--checkpoint_every_epochs 1`); pick the stability window across the run (dora_run header +
  MASTER §4). `--no_demos` is set on all four (skip the ~10-min inpaint-demo callback).

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
- **`MIOPEN_DISABLE_CACHE=1` — MANDATORY on LUMI, else training dies at the first conv.**
  *(first successful smoke, 2026-07-16 — cost 5 debug iterations.)* MIOpen's user kernel-cache
  is a SQLite file (`/…/gfx90a6e.ukdb`); its open fails with
  `Cannot open database file … → miopenStatusInternalError` at `dit.py preprocess_conv`
  **on every filesystem** (`/scratch`, `/flash` — both Lustre; and the container's baked-in
  `nodev /tmp`). Relocating the cache does NOT fix it (plain rollback-journal SQLite opens
  fine at those paths, so it's MIOpen's own SQLite open, not the FS). The fix is to **disable
  the on-disk kernel cache** — MIOpen then never opens the `.ukdb`; kernels recompile once per
  job (a few min on step 1, in-process cache holds after). Also **bind `/tmp`** into the
  container (`singularity exec --bind …,/tmp`) and point `MIOPEN_USER_DB_PATH`/
  `MIOPEN_CUSTOM_CACHE_DIR` at a job-scoped `/tmp/miopen-$SLURM_JOB_ID` as belt-and-suspenders.
  Live in both `lumi/sbatch/efp_smoke_r256.sbatch` and `efp_fp32_compare.sbatch`. Still-open
  question (post-mortem): whether our cotainr-from-plain-ROCm container simply lacks the gfx90a
  system perf-DB (forcing the write path) — if so a proper cache is recoverable later for the
  kernel-recompile speedup; not a blocker.
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
