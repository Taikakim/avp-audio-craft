# LUMI-G bundle — ready-to-run scaffolding for the LatCH + DoRA campaigns

*2026-07-07, WINTERMUTE. Companion to `docs/lumi-transition-plan.md` (read that first for
the why; this dir is the how). Everything here is prepared BEFORE access — the only edits
needed on day 1 are the project number and the base-image ROCm version.*

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
   EuroHPC Federation Platform → accept ToS → note `project_465NNNNN`.
3. **SSH key**: upload your PUBLIC key in MyAccessID/portal profile. Propagation to LUMI is
   **not instant** (up to ~an hour). MFA per portal instructions.
4. **Login**: `ssh -i ~/.ssh/<key> <username>@lumi.csc.fi` (username assigned by the portal,
   not your email). You land on a login node — internet, no GPUs, shared: build/stage here,
   never compute.
5. **Hello world** (`sbatch/hello_world.sbatch` — needs nothing of ours):
   `sbatch --account=project_465NNNNN sbatch/hello_world.sbatch` → `squeue --me` →
   `cat hello-*.out` should end with "HELLO LUMI, the stack is alive". That proves
   account + queue + GCD + torch in one 10-minute job.
6. Then the Day-1 checklist below (container build, weights, data, parity).

## Day-1 checklist (when the project number arrives)

1. `sed -i s/project_465XXXXX/project_465NNNNN/` across this dir (or export `SA3_PROJECT`).
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
