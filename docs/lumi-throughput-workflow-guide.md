# LUMI Throughput & Workflow Orchestration Guide (EFP edition)

*Written 2026-07-15 by THE-FINN for CONTINUITY, sourced from 9 docs.csc.fi pages fetched and
summarized this session: `computing/running/throughput/`, `support/tutorials/lustre_performance/`,
`apps/hyperqueue/`, `apps/fireworks/`, `apps/nextflow/`, `support/tutorials/ml-starting/`,
`support/tutorials/gpu-ml/`, `support/tutorials/hyperparameter_search/`,
`support/tutorials/ml-workflows/`. This assumes the reader already has `docs/lumi-transition-plan.md`
and `lumi/README.md` open — it does not re-explain LUMI/Slurm/container basics, only the parts
those docs got wrong or left unresolved: how to get parallel sweep throughput when the EFP
WebUI only lets you submit one workflow execution at a time, on a `standard-g` partition that
bills whole nodes.**

> **⚠️ Read the ADDENDUM at the bottom first.** The EFP-WebUI-only-submission premise this
> guide was built on turned out to be stale as of the same day (direct `sbatch` now works) —
> §1's HyperQueue-as-submission-workaround framing is void, though HQ's short-task-packing
> rationale and the Lustre section still stand. The addendum says exactly what changes.

> **⭐ STANDING DIRECTIVE — every LUMI training run creates its OWN full evals, on LUMI, as
> part of the run** (Kim, re-affirmed 2026-07-24). A run is **not "done" until its eval suite
> exists**: render + score on LUMI so each checkpoint lands audit-ready and comparable, and
> nothing waits on the scarce local card. Build the eval stage into the run's workflow (the
> same HQ/sbatch pipeline this guide describes — queue the eval renders behind the training
> task), don't leave it as a manual local afterthought. **"Full evals" =** the correct family
> in `docs/canonical-eval-spec.md` (§1 control-adapter gain×density grid **or** §2 plain-DoRA
> prompt/seed/strength/length sweep — not interchangeable) **+** the MANDATORY
> `eval/control_head_disintegration_eval.py` gate for any control-adapter checkpoint **+** the
> semantic columns (`eval/mood_drift.py` retention + `eval/clap_score.py` genre-hold). Full
> text + which-family-when: the ⭐ block atop `docs/canonical-eval-spec.md`.

---

## 1. Direct answer to the core problem

**Your working hypothesis is correct, and CSC's own docs describe almost exactly this pattern
— it just isn't written with EFP in mind, because CSC's docs assume you can call `sbatch`
directly.** The bridge is: *the body of a HyperQueue-wrapped batch script is just shell script
contents*. Whatever you'd normally hand to `sbatch` is instead pasted into an EFP **Job
Script**, and one **Workflow Execution** of that Job Script *is* your one outer Slurm
allocation. Everything HyperQueue does after that (`hq server start`, `hq worker start`,
`hq submit --array=...`, `hq job wait all`) runs *inside* that single allocation's walltime,
with zero further WebUI interaction. (Source: `apps/hyperqueue/`, `computing/running/throughput/`.)

This directly resolves both halves of the problem:

- **"One workflow execution at a time" friction** → you're not submitting 20–32 workflow
  executions per sweep anymore, you're submitting **one**, which internally fans out to 8 (or
  more, queued) tasks without going back to `workflows.my-eurohpc.eu`.
- **Whole-node-exclusive billing on `standard-g`** → if a 1-GCD job bills a full node anyway
  (per your README's noted caveat), then requesting the **full node's 8 GCDs in that one
  workflow execution** and packing 8 sweep cells into it costs you the *same* node-bill you'd
  have paid for a single GCD, but gets 8x the work done. This turns whole-node billing from a
  waste into the mechanism that makes the throughput math work.

CSC's own heuristic (`computing/running/throughput/`, verbatim): *"if you are running more
than 20 short tasks (under ~30 minutes) that run on a single node, you should consider packing
them into a single slurm job."* Your sweeps (20–32 single-GCD configs) sit almost exactly at
this threshold — this is the textbook case the tool is for, not an edge case.

**One correction to the existing transition plan:** `lumi-transition-plan.md` §Phase 3 and
`lumi/README.md`'s `latch_all_features.sbatch` both assume `sbatch --array=0-19` will work.
Per the README's own EFP banner, it will not — `default_no_jobs`/`MaxSubmit=0` blocks it
regardless of whether it's a single job or an array. The fix isn't a different Slurm flag,
it's moving the array *inside* HyperQueue's `hq submit --array=...`, which runs inside the one
allocation the WebUI grants you. Treat every `--array=` in the existing `.sbatch` files as
"port this number into an `hq submit --array=` line," not as literal `sbatch` syntax to paste
into the EFP Job Script field.

### Concrete adapted pattern for Campaign A (20 LatCH heads)

This is the CSC-documented single-node HyperQueue skeleton (`apps/hyperqueue/`,
`computing/running/throughput/`) adapted to your paths, project number, and container:

```bash
#!/bin/bash
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8       # one HyperQueue worker per GCD
#SBATCH --cpus-per-task=7         # matches env_lumi.sh's 7-cores/GCD budget
#SBATCH --gpus-per-node=8         # take the whole node since it's billed that way anyway
#SBATCH --time=04:00:00

module use /appl/local/csc/modulefiles
module load hyperqueue             # LUMI build is 0.18.0

export HQ_SERVER_DIR="$PWD/hq-server/$SLURM_JOB_ID"
mkdir -p "$HQ_SERVER_DIR"

hq server start &
until hq job list &> /dev/null; do sleep 1; done

# One worker per Slurm task == one worker per GCD. Each worker's SLURM_PROCID
# becomes the GCD index its subprocesses see (see GCD-binding note below).
srun --overlap --cpu-bind=none --mpi=none bash -c '
  export ROCR_VISIBLE_DEVICES=$SLURM_PROCID
  export HIP_VISIBLE_DEVICES=$SLURM_PROCID
  hq worker start --manager slurm --on-server-lost finish-running --cpus=7
' &
hq worker wait "$SLURM_NTASKS"

# 20 feature heads queued against 8 workers; HQ drains the queue as workers free up
# — no need for #tasks == #GCDs, and no re-submission when a wave finishes.
hq submit --stdout=logs/%{TASK_ID}.out --stderr=logs/%{TASK_ID}.err \
  --cpus=7 --array=0-19 \
  singularity exec --bind /scratch/project_465003186:/data,/project/project_465003186:/models \
    sa3-train.sif python train_latch.py \
    --encoded-dir /data/latents_sa3 --feature-index "$HQ_TASK_ID" ...

hq job wait all
hq worker stop all
hq server stop
```

**This whole file is what you paste as the EFP Job Script body; one Workflow Execution of it
is the entire 20-head campaign.**

**Flag — needs verification on LUMI:** none of the 9 fetched CSC pages document GPU/GCD-aware
task assignment inside HyperQueue. The `ROCR_VISIBLE_DEVICES=$SLURM_PROCID` /
`HIP_VISIBLE_DEVICES=$SLURM_PROCID` trick above is **our own inference** (worker processes
started via `srun --ntasks=8` each get a distinct `SLURM_PROCID`, and env set before `hq worker
start` should be inherited by that worker's own subprocess tasks) — it is not stated in any
CSC doc and should be smoke-tested with a trivial 8-task `rocm-smi`/`echo $HIP_VISIBLE_DEVICES`
job before trusting it for a real campaign. Similarly, **whether `standard-g` actually charges
per-GCD or always whole-node** is stated as "typical" in your own README, not confirmed by
these CSC pages (which don't discuss billing granularity at all) — verify with `sacctmgr show
assoc user=$USER format=Account,Partition,MaxJobs,MaxSubmit -p` (`computing/running/throughput/`)
and by comparing the GCD-hours actually deducted after a full-node vs. partial-node test job.

### Quicker path for flat command lists: `sbatch-hq`

If a sweep is just "N independent commands, no shared server logic," CSC's wrapper is simpler
than hand-rolling the server/worker dance (`apps/hyperqueue/`):

```bash
module use /appl/local/csc/modulefiles
module load hyperqueue
module load sbatch-hq
sbatch-hq --cores=56 --nodes=1 --account=project_465003186 \
  --partition=standard-g --time=04:00:00 dora_sweep_commands.txt
```

where `dora_sweep_commands.txt` is one fully-formed command per line — e.g. one line per DoRA
bracket cell, generated by the same for-loop that currently drives `dora_run.sbatch`'s manual
`sbatch` calls:

```bash
singularity exec --bind /scratch/project_465003186:/data sa3-train.sif \
  python train_lora.py --export=ALL,ENC=vae,RANK=16,LR=2e-4 ...
```

**Needs verification:** whether `sbatch-hq`-launched tasks get a usable per-task GCD-binding
handle equivalent to `$HQ_TASK_ID`/`$SLURM_PROCID` — this isn't documented on the page. Treat
`sbatch-hq` as the fast path for a first smoke test, and the manual pattern above as the one to
use once GCD-binding matters.

---

## 2. Tool recommendation matrix

Your two needs are genuinely different shapes, and the CSC docs support treating them
differently:

| Need | Best fit | Why | Avoid |
|---|---|---|---|
| **Sweep cells** — 20–32 independent single-GCD configs (LatCH-per-feature, DoRA rank/LR/crop brackets), no dependencies between them | **HyperQueue**, one EFP workflow execution, `hq submit --array=` (or `sbatch-hq` for the flat-command case) | This is literally the case CSC's throughput page and HyperQueue page are written for: "allocate a large resource block and let HyperQueue schedule your tasks into it" (`computing/running/throughput/`, `apps/hyperqueue/`). Sub-node granularity, scales to many nodes if you ever need >1 node for a bigger bracket. | **FireWorks** — its Slurm integration requires "all subtasks must use identical resources" and repeated `srun` calls bloat the Slurm log at your task counts (`apps/fireworks/`); also needs a MongoDB instance on Rahti, a *different* CSC system than LUMI, adding a cross-system dependency the docs never confirm works from LUMI compute nodes (air-gapped) anyway. **Nextflow's plain `slurm` executor** — explicitly warned against for short tasks ("Please do not use SLURM executor, if your workflow includes a lot of short processes. It would overload SLURM. Use HyperQueue executor instead," `apps/nextflow/`), and it submits one *real* Slurm job per process, which would hit the same `default_no_jobs` wall as raw `sbatch --array` — needs verification, but almost certainly broken under EFP for the same reason your three failed `sbatch` attempts were. |
| **ARC-Forcing** — strict 2-step rollout→train pipeline, hard dependency, currently two manual workflow executions | **Nextflow, local executor**, two `process` blocks connected by a channel, run inside **one** EFP workflow execution | Nextflow's "batch job + local executor" mode runs the *entire* pipeline inside one `sbatch`-equivalent allocation ("Useful for small and medium size workflows," `apps/nextflow/`) — no child Slurm jobs are spawned, so it never touches the `default_no_jobs` restriction. The rollout→train dependency is expressed natively: `train` process declares an `input` channel fed by `rollout`'s `output` channel, so Nextflow won't start `train` until `rollout`'s output exists — replacing your manual "wait for `manifest.json`, then launch the second workflow execution by hand" with one submission. | **FireWorks's `links:` graph** is the most literal match for "B waits for A" (`apps/fireworks/`'s `hello_wf.yaml` example is almost exactly your rollout→train shape with a `FileTransferTask` moving A's output to where B expects it) — but it costs you a standing MongoDB on Rahti, a steep setup, and is never mentioned as tested against LUMI in any of these pages (all its examples are Puhti/Mahti). Given ARC-Forcing is *only* 2 steps, the operational cost of standing up FireWorks's MongoDB dependency is disproportionate. **Keep FireWorks off the table for both needs** unless a future pipeline genuinely needs complex multi-branch dependencies that Nextflow's simpler channel model can't express. |

**Bottom line: HyperQueue for the sweep-cell fan-out, Nextflow (local executor) for the
ARC-Forcing dependency, no role for FireWorks given your current pipeline shapes.** Both
HyperQueue and Nextflow are already available as LUMI modules per CSC (`apps/hyperqueue/`:
LUMI 0.18.0; `apps/nextflow/`: LUMI 22.10.4, loaded the same way:
`module use /appl/local/csc/modulefiles && module load nextflow`).

**Two Nextflow gotchas carried over from the docs, both worth flagging before you build on it:**
1. LUMI's only offered Nextflow version (22.10.4) predates the "23.04.3+ is DSL2-only" cutoff
   — meaning DSL1 is likely still the default there; **needs verification** whether DSL2
   syntax (the `workflow { }` / channel style shown in the docs) actually works on LUMI's
   22.10.4, or whether you need explicit `nextflow.enable.dsl=2` at the top of the script.
2. Nextflow can *also* use HyperQueue as its executor for cases where a single pipeline step
   needs to fan out internally (`apps/nextflow/`'s HyperQueue-executor example) — you don't
   need this for the 2-step ARC-Forcing pipeline today, but it's the escape hatch if a future
   pipeline needs both a dependency DAG *and* per-step fan-out in one workflow execution.

---

## 3. Lustre I/O: do's and don'ts for your actual read/write pattern

Your pattern: **~13 GB `latents_sa3` + ~21 GB `timeseries` reads per run**, **many small
per-epoch checkpoint writes**, **wandb-offline log files**, all potentially happening **8x
concurrently per node** once HyperQueue is packing GCDs.

**Do (confirmed by `computing/running/throughput/`):**
- **Stage the dataset once per node, not once per task.** The throughput page's explicit
  warning: *"A common bottleneck occurs at task startup, when many tasks simultaneously open
  the same set of files, which can overload the file system."* Eight GCD-tasks each
  independently opening the same `latents_sa3`/`timeseries` files from `/scratch` or `/project`
  at job start is exactly this anti-pattern. Adapt the HyperQueue multi-node example's staging
  idiom (`apps/hyperqueue/`'s `extract.sh`/`archive.sh`, run once via
  `srun -m arbitrary -w "$SLURM_JOB_NODELIST"` before `hq submit`): copy `latents_sa3` +
  `timeseries` to **`/flash/project_465003186`** (2 TiB NVMe, per your README) once at the top
  of the workflow execution, then point every sweep cell's `--encoded-dir` at the flash copy,
  not the Lustre path.
- **Write per-epoch checkpoints to `/flash` (or node-local), not directly to `/scratch`.**
  Same throughput-page principle: *"direct heavy I/O to local disk areas instead of the shared
  parallel file system."* Consolidate/copy the final (or best) checkpoint(s) back to
  `/scratch/project_465003186` or `/project/project_465003186` once at the end of each task,
  rather than every epoch's save hitting Lustre directly. With 8 concurrent tasks × per-epoch
  saves, this is the difference between one Lustre metadata storm and none.
- **Same for wandb-offline run directories.** Point `WANDB_DIR` at `/flash` during the run;
  `wandb sync` from the login node afterward (per your existing offline-then-sync plan) reads
  from flash, not from 8 concurrently-written Lustre directories.
- **Keep the container as one `.sif` file.** The throughput page validates your existing
  cotainr approach directly: *"Packaging such software into a single container image collapses
  these many small files into one file, which the parallel file system handles much more
  efficiently."* No change needed here — this confirms `sa3-train.sif` is the right shape, not
  just a Lustre-inode workaround for `pip install`.
- **Launch the container once per allocation, not once per sweep cell**, where practical. The
  throughput page: *"run the task-farming or workflow tool inside a single long-running
  container rather than launching a separate container for each individual task, as starting
  many containers adds significant overhead."* In practice, your sweep cells are multi-minute
  training runs, so 20–32 `singularity exec` invocations' startup overhead is likely negligible
  relative to run length — this matters far more for sub-second/sub-minute tasks than yours.
  Not a blocker, just don't assume it's free at larger sweep counts.

**Don't (and note what's *not* confirmed):**
- Don't assume the fetched Lustre tutorial (`support/tutorials/lustre_performance/`) gives you
  striping (`lfs setstripe`) or checkpoint-pattern guidance — **it doesn't**. That page is
  entirely ROMIO/MPI-IO collective-buffering hints for Puhti/Mahti Fortran/C codes, has zero
  LUMI, container, or checkpoint content, and its only real transferable idea is "avoid
  file-per-process I/O," which is the same principle as above, not new information. If you
  need actual striping tuning for large checkpoint files on LUMI, that's a genuine gap — pull
  it from LUMI's own docs, not from this CSC page.
- Don't take "many small per-epoch checkpoint writes are bad" as literally sourced from the
  Lustre tutorial — it isn't (that page never says it). It's an application of the *throughput
  page's* general "reduce number of files / avoid many small files" principle, which is CSC's
  own stated guidance, just from a different page than the one that sounds most relevant by
  title.

---

## 4. Corrections/improvements from the GPU-ML, hyperparameter-search, and ml-workflows pages

- **`support/tutorials/gpu-ml/` confirms your existing LUMI conventions are correct** —
  useful as validation, not new information: LUMI partitions are `dev-g`/`small-g`/`standard-g`
  (matches your README's "standard-g only" finding), GPU request syntax on LUMI is
  `--gpus-per-node=N` (**not** `--gres=gpu:...`, which is Puhti/Mahti/Roihu syntax) — your
  existing `.sbatch` files already use `--gpus-per-node`, so no change needed there, just
  confirmation you had it right. CSC's recommended CPU budget is **7 cores/GCD** on LUMI
  ("as there are 63 cores for 8 GPUs") — matches `env_lumi.sh`'s already-set 7-cores/GCD,
  another confirmation rather than a correction.
- **GPU monitoring on a live job**: `srun --interactive --pty --jobid=<jobid> rocm-smi` (or
  `watch rocm-smi`) works against any running Slurm job, including ones the EFP WebUI
  submitted on your behalf — get `<jobid>` via `squeue --me` over SSH. This is a genuinely
  useful addition: even though you can't submit via SSH, you *can* still inspect and monitor
  an in-flight EFP-launched job from the login node once it's running.
- **GPU-energy accounting gotcha, directly relevant to your 5000-GCD-hour budget tracking**:
  CSC's `gpu-energy` tool (`/appl/local/csc/soft/ai/bin/gpu-energy`) explicitly warns *"Always
  measure GPU usage for a full node on LUMI!"* — because the MI250X energy counter reports
  per-*card* (2 GCDs), not per-GCD, so a partial-node reservation gives you an unreliable
  number if another job is using the card's other GCD. Convenient side effect of the
  HyperQueue-packs-the-whole-node design above: since you're now reserving full nodes anyway
  for sweep throughput, your energy/GCD-hour measurements will already satisfy this constraint
  — one less thing to get wrong separately.
- **`support/tutorials/hyperparameter_search/` doesn't apply to your sweep design, and that's
  informative in itself.** That page is about classical hyperparameter search
  (GridSearchCV/Optuna/Ray-Tune-`tune-sklearn`) over scikit-learn-style estimators on
  Puhti/Mahti CPUs — it's a different problem shape from yours (you have a fixed, enumerated
  set of 20–32 independent training configs, not an adaptive search over a continuous space).
  Its confirmation is negative-but-useful: nothing on that page suggests Ray Tune / Optuna is a
  better fit than task-farming for your case — your sweep is squarely task-farming
  (HyperQueue), not hyperparameter search in CSC's sense of the term.
- **`support/tutorials/ml-workflows/` turned out to be a red herring for orchestration** — its
  entire content is MLflow experiment tracking (`mlflow.set_tracking_uri`,
  `mlflow.log_metric()` against a Rahti-hosted server), not workflow/job orchestration despite
  the page name. Not directly useful given you already have wandb-offline-then-sync working,
  and MLflow's tracking server would face the same air-gapped-compute-node constraint wandb
  does, with no stated advantage over your current setup. No action needed here — just don't
  expect this page to contain what its title implies.
- **`support/tutorials/ml-starting/` is Puhti 101 onboarding** (V100 GPUs, `--gres=gpu:v100:1`
  syntax, `gputest`/`gpu` partitions) — none of it is LUMI-specific or applicable; skip it
  entirely, you're past this level already.

---

## 5. Open items — needs verification on LUMI before trusting this in production

1. **GCD-binding via `$SLURM_PROCID`/`$HQ_TASK_ID`** inside HyperQueue workers (§1) — our
   inference, not CSC-documented. Smoke-test with a trivial `rocm-smi`/env-var-echo array job
   before running a real sweep on it.
2. **Whether `standard-g` bills per-GCD or always whole-node** — your README calls this
   "typical," not confirmed; verify via `sacctmgr` and an actual post-job GCD-hour deduction
   check.
3. **Whether LUMI's Nextflow 22.10.4 supports DSL2** syntax as shown in the docs' examples, or
   requires an explicit DSL1/DSL2 pragma — the version-vs-DSL2-cutoff note in `apps/nextflow/`
   implies it might not be default-DSL2.
4. **Whether `sbatch-hq`-launched tasks expose a per-task index** usable for GCD binding the
   same way the manual `hq worker`/`$HQ_TASK_ID` pattern does — not documented either way.
5. **Lustre striping tuning for large checkpoint files**, if per-epoch checkpoint I/O turns out
   to still be a bottleneck even after moving it to `/flash` — none of the 9 fetched pages give
   LUMI-applicable striping guidance; would require a separate LUMI-docs lookup, not CSC's
   general Lustre tutorial (which is Puhti/Mahti MPI-IO specific).

---

## Sources

- https://docs.csc.fi/computing/running/throughput/
- https://docs.csc.fi/support/tutorials/lustre_performance/
- https://docs.csc.fi/apps/hyperqueue/
- https://docs.csc.fi/apps/fireworks/
- https://docs.csc.fi/apps/nextflow/
- https://docs.csc.fi/support/tutorials/ml-starting/
- https://docs.csc.fi/support/tutorials/gpu-ml/
- https://docs.csc.fi/support/tutorials/hyperparameter_search/
- https://docs.csc.fi/support/tutorials/ml-workflows/

---

## ADDENDUM 2026-07-15 (CONTINUITY) — the EFP-only-WebUI premise this guide was built on is STALE

**While the fetch/synthesis agents above were running, the premise changed: direct `sbatch`
now works on this LUMI/EFP project.** Proven ~10:30 today — Kim submitted a smoke test
straight from the login shell (job `19904641`), it ran instantly with the header honored, no
WebUI involved. The WebUI-only-submission restriction (`default_no_jobs`/`MaxSubmit=0`) that
motivated §1 above is gone; **treat this as a normal Slurm site now**, not an EFP-WebUI-only
one. Per house convention this section is added, not a rewrite — §1–5 above stay as the
history of the EFP-constrained analysis and the fallback plan if WebUI-only submission is
ever re-imposed.

**What this changes, concretely:**

1. **The HyperQueue-as-EFP-workaround motivation in §1 is void** — you no longer need HQ to
   get around a one-submission-at-a-time restriction, because that restriction doesn't exist
   right now. **HQ's OTHER rationale still stands on its own merits**: CSC's own
   pack-more-than-20-short-tasks-per-node advice (§1, `computing/running/throughput/`) and the
   Lustre-stampede-avoidance guidance (§3) are about scheduler overhead and shared-filesystem
   load, not about EFP's submission model — those reasons to use HQ for the LatCH-head sweeps
   are unaffected. Reframe HQ in your head as "the short-task packer," not "the EFP escape
   hatch."
2. **The correction in §1 telling `lumi-transition-plan.md`/`lumi/README.md` that
   `sbatch --array=0-19` "does not work" is now itself stale.** Plain `sbatch --array=0-19`
   most likely just works today — **worth a 2-minute test (a trivial 2-task array job)
   before trusting this either way or rewriting the older docs.** Don't assume-and-ship;
   verify like everything else flagged in §5.
3. **For the ARC-Forcing rollout→train dependency (§2's Nextflow recommendation):** plain
   `sbatch --dependency=afterok:<rollout_jobid> arc_train.sbatch` now also works and is
   simpler than standing up Nextflow for a 2-step pipeline — **default to this**, and keep
   Nextflow in reserve for when a pipeline's dependency shape gets more complex than a single
   `afterok` edge.
4. **Net effect on the tool recommendation matrix (§2):** HyperQueue's row stands (short-task
   packing is still real), Nextflow's row downgrades from "recommended now" to "reserve for
   future complex DAGs," FireWorks's exclusion is unaffected either way.

The unconfirmed-item discipline in §5 still matters — if HyperQueue survives this reframe for
the sweep-packing use case, the `SLURM_PROCID`-based GCD-binding trick is still our own
inference, not CSC-documented, and still needs the smoke test before a real campaign relies
on it.

## 6. DDP (single-model data-parallel) launch — the multitorch OOM gotcha (2026-08-09, CONTINUITY)

This section is about **one model trained data-parallel across the 8 GCDs** (full-FT / big DoRA
runs), NOT the HyperQueue independent-task packing above. The launch pattern is a real trap on
the `lumi-multitorch-full` image — it cost job 20869819 (a ~3-min HIP OOM at model load).

**Two candidate patterns (only one works on multitorch):**

- **Pattern 1 — all GCDs visible + `--devices 8`** (`srun --ntasks-per-node=8 --gpus-per-node=8`,
  NO `--gpus-per-task`; `train_lora.py --devices 8`). **OOMs on multitorch.** `train_lora.py`'s
  `load_model` calls `model.to("cuda")` (= `cuda:0`) *before* Lightning assigns per-rank devices,
  so **all 8 ranks load the ~7 GiB model onto GPU 0** → `HIP out of memory … GPU 0 … 0 bytes free`
  while GPUs 1–7 sit idle. (This pattern was "verified" only on the old `sa3.sif` with tiny smokes;
  it does not survive a real model load on multitorch.)

- **Pattern 2 — one GCD per task + NO `--devices`** (`srun --nodes=1 --ntasks=8 --gpus-per-task=1
  --cpus-per-task=7`; `train_lora.py` with **no `--devices` flag**). **This is the working recipe**
  and is exactly what #68 `fullft_bigset` runs (8h+ clean, no `-vN` ckpts). `--gpus-per-task=1`
  cgroup-pins each rank to its own GCD, so `model.to("cuda")` lands on that rank's own card;
  Lightning's `SLURMEnvironment` forms the `world_size=8` group from `SLURM_NTASKS`. The old
  "`--gpus-per-task=1` → SingleDeviceStrategy → N duplicate trainers" warning was an `sa3.sif`
  smoke (20413874) and does **not** hold on multitorch — #68 proves Pattern 2 forms a real
  coordinated group there.

**Rule (multitorch): DDP = Pattern 2 — `--gpus-per-task=1`, no `--devices`, no ROCR pinning.**

**Multi-node** extends Pattern 2 directly: `--nodes=N --ntasks-per-node=8 --gpus-per-task=1`, still
no `--devices` (SLURMEnvironment derives `world_size = N*8` and `MASTER_ADDR` from node 0; export
the LUMI Slingshot/RCCL env — `NCCL_SOCKET_IFNAME=hsn0,hsn1,hsn2,hsn3`, `CXI_FORK_SAFE=1`, etc.).
A `train_lora.py --num_nodes` hook exists for the Lightning-spawns (Pattern 1) style but is not
needed on the Pattern-2 SLURM-launch path.

**Verify (read the artifact, never the rc):** rank-0 log shows `MEMBER: 1/8` (or `/32`) and
`initializing distributed`; loss ticks once per global step; **no `epoch=…-vN` ckpts** (versioned
files = N uncoordinated writers). Templates: `lumi/sbatch/fullft_avp_aug.sbatch` (single-node),
`lumi/sbatch/multinode_ddp_smoke.sbatch` (4-node rendezvous smoke), `lumi/sbatch/fullft_bigset.sbatch`
(#68, the reference Pattern-2 launch). Full operational note: lumi-ops SKILL, DDP section.

## 7. Full-FT latent-scale runaway → spectral drone (2026-08-10, CONTINUITY)

Every multitorch **full fine-tune** (#68 `fullft_bigset`, `precision_ladder` — all FusionOpt)
decoded to broadband **spectral drone** on every prompt+cfg. NOT
live-encode (the pre-encoded ladder droned too), NOT the decoder (known-good latents decode fine).

> 🔴 **CORRECTION (C, 2026-08-17) — the original text here said "It is NOT DDP (formed one group)".
> That parenthetical was FALSE for #68 and is struck.** #68 launched with
> `srun --ntasks=8 --gpus-per-task=1` and no `--devices`, which we now know **silently fails to
> form a DDP group** — all 8 ranks log `LOCAL_RANK: 0` and train as 8 uncoordinated single-GPU
> copies (see the Multi-GPU DDP section of `.claude/skills/lumi-ops/SKILL.md`). So #68's specific
> numbers ARE confounded. **The MECHANISM below is not**, and this is the important part: the
> runaway was also measured on `precision_ladder`, whose arms run
> `srun --exclusive -N1 -n1 --gpus=1` with `SLURM_JOB_NAME=bash` set precisely so Lightning does
> NOT detect SLURM — i.e. each ladder arm is a **single-GPU trainer by construction**, where the
> DDP bug cannot apply. The ladder droned with the full signature, so weak `spectral_wd` stands as
> the cause on evidence the bug cannot touch. Lesson for future exclusions: "it's not DDP" needs
> the `grep -h LOCAL_RANK` check, not an assumption.
>
> ✅ **AND THE FIX IS CONFIRMED WORKING (C, 2026-08-17).** The `--weight_decay` full-FT
> (`fullft_mixed_..._wdfix`) measures at ep7: global z0 std **1.134**, channels with std>2.0
> **0/256** — versus the runaway's 5.6 and 166/256. Mildly elevated vs the 0.7 ideal, nowhere near
> blow-up. NOTE this run ALSO had the DDP bug and still sounded droning/thin to Kim, which — with a
> healthy latent scale — means that audio complaint is a **SEPARATE failure from the scale
> runaway**, most plausibly the 8-uncoordinated-trainers bug itself. Do not re-diagnose the two as
> one thing.
The model's **latent output scale runs away during training**. Measured from the saved `z0.npy`
(purely local, no GPU): global latent std **0.7 (good) → 1.3 (ep3) → 5.6 (ep7)**; #latent channels
with std>2.0 **0 → ~4 → 166/256**; **cfg16 inflates first** (early-warning canary). Diverse latents
(low cross-clip cosine) rule out mode-collapse — it's a scale blow-up.

**Cause:** FusionOpt's per-group `spectral_wd` **defaults to 0.01** (`fusion_groups.py`), too weak
for the NS5/Muon orthogonalized update (step-norm is grad-magnitude-independent, so decay must be
~10× AdamW's). Adapters stay bounded (frozen base) → **full-FT-only**. Schedule-Free removes the LR
*schedule*, NOT weight decay — orthogonal knobs; don't conflate them.

**Fix:** `--weight_decay 0.1 --gradient_clip_val 1.0` on the full-FT. `--weight_decay` routes to
`param_groups.spectral_wd` (the effective knob); the FusionOpt *constructor* `weight_decay` is
overridden by the per-group value, so setting it there is a no-op. `scalar_wd` stays 0.0 (never
decay norms/biases).

**First diagnostic for ANY future drone:** load the `z0.npy` and check global std vs ~1.0 BEFORE
suspecting DDP/live-encode/decoder. Deterministic mechanism test (CPU, seconds):
`stable-audio-tools/tests/test_fusion_weight_decay.py`. Confirming A/B on the real model: job
20940322, `lumi/sbatch/fullft_wd_ab.sbatch` (arms wd0p01 / wd0p1 / adamw_wd0p1). Consequence:
#68 and #69 (AVP) as trained are dead — relaunch with the fix once the A/B confirms.

### CSC ml-multi tutorial cross-check (re-read 2026-08-10)
`docs.csc.fi/support/tutorials/ml-multi` confirms our node-shape (7 cores + ~60 GB per GCD; full
node = `--cpus-per-task=56 --mem=480G` or `--mem=0`) and the "reserve full nodes for multi-node"
rule. Two deltas vs our Pattern-2 SLURM launch, noted in `multinode_ddp_smoke.sbatch`: (1) CSC wires
the Slingshot fabric via **`module load lumi-aif-singularity-bindings`** rather than hand-set
`NCCL_SOCKET_IFNAME`/`CXI_FORK_SAFE` — try it if the OFI provider isn't picked up; (2) their launch
topology is `srun --ntasks-per-node=1 … torchrun --rdzv_backend=c10d --nproc_per_node=8` (1 task/node,
torchrun forks 8) — a valid alternative to our srun-8-tasks + Lightning `SLURMEnvironment`. The
tutorial gives **no** low-level RCCL env (we have more detail there from other LUMI sources).
