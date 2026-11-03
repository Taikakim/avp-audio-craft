---
name: lumi-project-purge-deadline
description: LUMI project 465003186 — compute ended 2026-08-23; /scratch data removal ~2026-11-20 (94 days from 2026-08-18), NOT late August — pull keep-worthy FAT ckpts before then
metadata: 
  node_type: memory
  type: project
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
  modified: 2026-08-07T06:54:50.641Z
---

**Kim, 2026-08-07:** the LUMI project (project_465003186) is expiring and **/scratch will be
PURGED a few weeks after 2026-08-07** (≈ late Aug 2026 — exact expiry date TBC).

**Consequence — the pull strategy flips to ARCHIVE-BEFORE-PURGE:**
- The usual "pull slim weights, not the fat ckpt" default is **overridden while the purge looms.**
  Kim is pulling the **FAT** `epoch=N.ckpt` (weights + EMA + FusionOpt/KL-Shampoo optimizer state,
  ~44 GB for a fp32 fullft even at T256) precisely because the ~35 GB of optimizer state is the ONE
  thing that can't be reconstructed after purge (needed to resume training). Slim (~9 GB, model+EMA)
  is fine only when LUMI is permanent.
- Applies to ALL keep-worthy scratch artifacts: run ckpts, `renders/`, `latents_sa3`, analysis
  outputs, logs. Anything left on `/scratch/project_465003186` when it purges is GONE.
- "Last checkpoints only" still holds for which EPOCH to pull (terminal fat, not every epoch), but
  **fat not slim** for the archive. See [[sao-lumi-live-jobs-2026-08]].

**Before the deadline:** sweep scratch for anything not yet mirrored locally (UUID drive
`lumi_runs/` is canonical). Landing runs (big-FT #68, v3sel A/B) must have their terminal fat ckpts
pulled once done. Fleet should treat scratch as ephemeral now, not a store.

**DATE CORRECTED 2026-08-24.** "A few weeks after 2026-08-07" was Kim's early estimate with the exact
date TBC, and it is wrong in the alarming direction. `lumi-allocations` on 2026-08-18 printed
**94 days to data removal** → **≈ 2026-11-20**. Compute is separately exhausted (allocation closed
2026-08-23 at 4765/5000 GPU-h), and **compute ending does NOT remove the data** — see the
`lumi-ops` skill, "Budget: check WALL CLOCK". So: still archive-before-purge, still fat-not-slim,
but there is no reason to pull under panic or to skip verification to save time. Anything still
unpulled by early November is what to worry about — e.g. `pianoroll_fullft/` and the `morphcond`
run dirs, which as of 2026-08-24 exist ONLY on scratch and block the pianoroll/contour plan.
