---
name: lumi-ops-docs
description: "Where the LUMI operational truth lives — field guide + SAO team bundle; EFP WebUI submission, standard-g whole-node billing, paste etiquette"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 12fdecac-006e-48d2-ad43-2e665f84dc62
  modified: 2026-08-11T08:10:14.471Z
---

For any LUMI work on film_grain (see [[lumi-supercomputer-access]]):
- **Field guide**: `/home/kim/Projects/SAO/docs/writing-lumi-sbatches.md` — containers/binds, MIOpen-cache inode killer, GCD pinning (one mechanism, never two), silent-failure defenses, self-grading jobs. Kim points to it explicitly when sbatches are being written.
- **SAO team bundle**: `/home/kim/Projects/SAO/lumi/` — READ-ONLY for this project (Kim: "do not write there"). Key files: `README.md` (allocation `project_465003186`, user akekim; cert expires ~10 h), `LUMI-OPS-CONVENTIONS.md` (commands for Kim = single-line paste-ready; `sacct` for outcomes, artifacts for truth; no `du` on Lustre), `env_lumi.sh`, `check_sbatch_python.py` (heredoc parse checker), **`sbatch/` — the working script collection, THE house style to copy** (env knobs via `--export=ALL,KEY=VAL`, doc headers with wallclock estimates, resumable outputs).
- **Submission is DIRECT `sbatch`** (Kim 2026-08-11) — the bundle README's "EFP WebUI-only" section is from 2026-07-09 and OUTDATED; single-GCD standard-g jobs are routine in the working scripts.
- **standard-g billing is WHOLE-NODE, verified 2026-08-11** via sacct AllocTRES: a --gpus-per-node=1 request was allocated+billed the full node (billing=112, 8×mi250). Always pack 8 workers/node; single-GCD only for short smokes.
- Conflict note: env_lumi.sh sets MIOPEN_FIND_MODE=2; the newer field guide says never 2 (conv-solver hang on ROCm 6.2 images) — use 1.
- **LOGIN NODE RUNS ONLY `sbatch`/`squeue`/`sacct`/`scancel`/`ls`** (2026-08-13, learned the hard way): a driver .sh that ran singularity + python on the login node dropped Kim's SSH session; `pip install --user` there is against CSC advice. ALL staging (prep, guards, container exec, stitching) goes INSIDE the sbatch on the compute node — copy the self-contained fleet pattern in `SAO/lumi/sbatch/fullft_avp_dronesweep.sbatch`. Kim: "LUMI runs sbatches".
- Task-farm, not DDP: our renders are 8 INDEPENDENT arms per node (ROCR_VISIBLE_DEVICES pinning), like the fleet; CSC ml-multi tutorial (DDP) does not apply.
- **Measured render rate on a MI250X GCD: ~1 h per 1920x1371 tile** (sacct: fg-still 8-parallel 1:06:45; fg-frames 24 tiles/3 waves 3:10:42). Not 30 min. The "40 h" Kim remembers was the one-time 1.9B flagship field pack.
- **Host-RAM OOM at 8-wide** (job 21072951): 22 GB field per worker as private copies + concurrent cache-miss field builds for new presets → OUT_OF_MEMORY. Fix shipped 2026-08-15: mmap field loads, atomic cache publish, `grain_stream.py --field-path` probe, and solo warm-build of a missing preset field BEFORE the 8-wide fan-out; smoke-first (`--array=1`) then the rest.
- film_grain's derived bundle: `renders/lumi/` (eval_node.sbatch packs 8 GCD-pinned workers, resumable, self-grading).
