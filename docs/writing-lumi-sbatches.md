# Writing Correct LUMI sbatch Scripts — a field guide

A self-contained, portable guide for anyone (human or agent) who has to write SLURM
`sbatch` scripts on **LUMI** (or a similar EuroHPC AMD-GPU / LUMI-G cluster) and wants them
to *actually produce their outputs* instead of failing in one of the many ways that look
like success. Every rule below cost a real wasted job to learn.

> **How to read this.** Everything here is general LUMI/SLURM/ROCm/PyTorch-Lightning
> knowledge unless it is tagged **`[ADAPT]`** — those lines describe a choice a project makes
> (image, entrypoint, paths) and you substitute your own. Placeholders: `<proj>` = your
> project allocation id (e.g. `project_465000000`), `<login>` = the cluster login host,
> `<IMG>` = your container. Concrete LUMI facts (filesystem quotas, image locations, core
> counts, billing) are stated as of 2026 — re-check them against the current
> `docs.lumi-supercomputer.eu` if much time has passed.

---

## 0. The one meta-lesson: a `COMPLETED` job proves nothing

SLURM state `COMPLETED` / exit code `0` is a **completeness** signal, not a **success**
signal. The single most expensive class of LUMI failure is the job that exits green,
writes *some* artifacts, and quietly omits the one thing you launched it for. Everything in
§6 is defense against this. Internalize it first: **success = the expected number of correct
output artifacts exists**, asserted by the job itself, not the scheduler's rc.

---

## 1. Filesystem & budget model

Four storage tiers, and using the wrong one for the wrong thing is a real failure mode:

| Tier | Size / inodes | Billed | Use for | Never |
|---|---|---|---|---|
| `/users/<you>` (home) | 20 GB / **100k inodes** | — | dotfiles, tiny configs | caches, package installs (the inode cap is the #1 silent killer — see §3) |
| `/project/<proj>` | 50 GB / 100k inodes | 1× | **code + containers only** | datasets, model caches, run outputs |
| `/scratch/<proj>` | 50 TB / 2M inodes | 1× | **main I/O** — datasets, runs, renders, model cache | long-term storage (see backups below) |
| `/flash/<proj>` | 2 TB / 1M inodes | **3×** | node-local hot staging *for the duration of a job* | anything long-lived (billed triple) |

- **`$SCRATCH`, `$FLASH`, `$PROJECT` etc. are NOT set in a login shell.** Use literal paths,
  or set them yourself at the top of the script. A script that assumes `$SCRATCH` is exported
  writes to an empty path.
- **NO BACKUPS, on any tier, ever.** After an allocation ends, data goes **read-only for 90
  days, then is permanently deleted**. Anything you want to keep past the project's end needs
  an explicit pull-home plan; LUMI is not safe storage even briefly after close.
- **Billing:** `standard-g` bills the **whole node × walltime** (8 GCDs = 8 GPU-hours per
  wall-hour) *regardless of how many GCDs you use*. A 1-GCD job on a full node still bills 8×.
  Check remaining budget with `lumi-allocations`.
- **56 usable cores per LUMI-G node, not 64** (low-noise mode reserves/disables cores per L3
  region). That is why `--cpus-per-task=7 × 8 tasks = 56` is the natural full-node layout.
- **Lustre hates many small files.** A file-per-process read pattern (e.g. one file per data
  sample) strains the metadata servers. The fix is to **stage hot data to node-local `$FLASH`
  at job start** (one big sequential read: pull a tar, extract to `/flash`) and do the random
  per-sample reads there, not off `/scratch`.

---

## 2. Containers

LUMI **discourages** direct conda/pip on its filesystems (it produces the many-small-files
pattern above). The recommended path is a **Singularity/Apptainer container**, ideally built
with `cotainr`. You rarely need to build one:

- **Official AI images ship ready to use** under `/appl/local/containers/sif-images/` (and the
  readable LAIF path `/appl/local/laifs/containers/`). Two families:
  - `lumi-pytorch-rocm-*.sif` — plain torch + ROCm.
  - `lumi-multitorch-*.sif` — torch + **prebuilt Flash-Attention (gfx90a), bitsandbytes,
    DeepSpeed, vLLM**. **This is the no-build FA2 path — never compile flash-attn into your own
    SIF.** Resolve the newest full build:
    `ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif | sort | tail -1`.
  - Avoid the `easybuild-sif-images/` symlinks — they point into another project's
    non-world-readable scratch.
- **`singularity exec <IMG>` mounts `/project` and `/scratch` read-only (or not at all) unless
  you `--bind` them.** The symptom of forgetting is `OSError: [Errno 30] Read-only file system`.
  **Every** `singularity exec` needs its own bind — a script with two exec calls must bind on
  both: `singularity exec --bind /project/<proj>,/scratch/<proj>,/tmp <IMG> …`.
- **Venv overlay** (adding packages on top of an image): create the venv **inside** the target
  SIF with `--system-site-packages` onto `/scratch` (torch/ROCm come from the image; pip adds the
  rest). Two traps:
  - **The image's own `/opt/venv` shadows your overlay.** After `source $VENV/bin/activate` you
    must also `export PYTHONPATH=$VENV/lib/python3.X/site-packages${PYTHONPATH:+:$PYTHONPATH}`,
    or imports silently resolve to the container's versions. Assert a critical package's
    `__file__` is *not* under `/opt/venv`.
    **That `${PYTHONPATH:+:$PYTHONPATH}` suffix is load-bearing, not decorative (2026-08-17).**
    A `--system-site-packages` overlay venv never actually installs heavy packages (torch
    included) into its *own* site-packages — it relies on the image's baseline `PYTHONPATH`
    (already pointing at `/opt/venv/lib/python3.X/site-packages`, present with **no** manual
    export at all) for them via system-site-packages inheritance. Writing a bare
    `export PYTHONPATH=$VENV/lib/python3.X/site-packages` (replacing instead of appending)
    silently drops `/opt/venv` from the path entirely — symptom is `ModuleNotFoundError: No
    module named 'torch'`, not a wrong version. Confirmed via a `sys.path` probe comparing
    with/without the override (`lumi/sbatch/diag_venv_probe.sbatch`).
  - No C-extension pip builds (no compiler in the SIFs — one failing sdist aborts the whole pip
    call); use `--no-deps` for heavy meta-packages and satisfy the import chain manually. A venv
    created inside a SIF has `bin/python` symlinked to the container's python — a *broken* link
    on the host, so host-side existence checks must test `bin/activate` (a real file), not
    `bin/python`.

---

## 3. The env exports every AMD-GPU job needs (the home-inode killer)

The single most common "job dies at ~1 s, sometimes with no `.out` at all" cause is the
**100k home-inode quota** filling with per-user cache files, so SLURM can't even create the
output file. Redirect **every** per-user cache off `$HOME`, inside the container, before
`python`:

```bash
export MIOPEN_USER_DB_PATH=/tmp/miopen-$$ MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-$$
export TRITON_CACHE_DIR=/tmp/triton-$$
export PYTORCH_TUNABLEOP_ENABLED=0
mkdir -p /tmp/miopen-$$ /tmp/triton-$$
```
(Use `$SLURM_PROCID` instead of `$$` for per-rank isolation in a multi-task `srun`.)

Why each matters:
- **MIOpen DBs → `/tmp`.** MIOpen (ROCm's conv library) writes a per-user perf/find database. If
  its target is a read-only or absent path it dies on the **first GPU convolution**
  (`cannot create directories: Read-only file system`); if it writes to `$HOME` it fills the
  inode quota. On some images the SQLite DB also can't open even on `/tmp` — then also set
  `MIOPEN_DISABLE_CACHE=1`. **[ADAPT]** Some frameworks hardcode a MIOpen path in a profile
  applied at import; pre-setting the env wins because such profiles use `setdefault`.
- **`TRITON_CACHE_DIR` → `/tmp`.** `torch.compile`'s cache otherwise fills `$HOME/.triton`. A job
  with *no explicit MIOpen use at all* still triggers this via a model's internal compile — so
  **any** model-running job needs it. Global belt-and-braces:
  `echo 'export APPTAINERENV_TRITON_CACHE_DIR=/tmp/triton_cache' >> ~/.bashrc`.
- **`PYTORCH_TUNABLEOP_ENABLED=0`.** Multitorch enables TunableOp by default; if it points at a
  bad results path it silently **re-benchmarks every GEMM** (one encode forward can eat 10
  minutes of wall). Tell in the log: `could not open .../tunableop_results0.csv`.

**MIOpen conv-solver HANG (older ROCm 6.2 images):** if a job stays `R` with GPU busy but the
training log's mtime is frozen for >15 min at a
`MIOpen(HIP): Warning [IsEnoughWorkspace] … workspace required … provided ptr: 0` line, that's
the FindDb-gap → immediate-mode heuristic → workspace-0 solver hang. It is **precision-independent
(bf16 and fp32 both hang — fp32 is not a fix)**. Real fixes: prefer a **ROCm-7 image** (the hang
doesn't occur), or on the old image set `MIOPEN_FIND_MODE=1` (or `3`), **never `2`**.

---

## 4. Compute nodes have NO internet

- **Pre-stage all model/dataset downloads.** For HuggingFace: pre-fetch on a **login** node,
  point the job at the cache, and force offline: `export HF_HOME=/scratch/<proj>/models
  HF_HUB_OFFLINE=1`. **Verify the cache is complete before submitting** —
  `ls $HF_HOME/hub/models--<org>--<name>/snapshots/*/`. A *partial* cache (e.g. an interrupted
  download, or a submit racing an in-flight rsync) fails as a clean `LocalEntryNotFoundError`
  deep into the job, after you've paid the queue wait and node spin-up.
- **Existence of a `snapshots/` dir is not proof of a usable model** — check the actual file
  sizes, not just that the directory exists.
- **Weights & Biases / any telemetry:** run **offline on LUMI** (`export WANDB_MODE=offline`,
  `WANDB_DIR` inside the run's `/scratch` dir — never `/flash`), pull the run dir home, then
  `wandb sync <run_dir>/wandb/offline-run-*` where you have real internet. Never put an API key
  on the command line (see §8).

---

## 5. The multi-GPU (DDP) launch — the trap that keeps biting

This is where most avoidable node-hours die. LUMI-G nodes have **8 GCDs** (each a separate GPU
to the software). For a single data-parallel model across them:

- **PyTorch-Lightning rejects a bare `#SBATCH --ntasks=N`** (`RuntimeError: You set --ntasks …
  not supported. HINT: Use --ntasks-per-node`). Use `--ntasks-per-node=N` + `srun --nodes=1
  --ntasks=N`.
- **GCD pinning — pick ONE mechanism, never stack two.** Stacking silently starves ranks 1–7 of
  a GPU (`No HIP GPUs are available`, or a crash at `model.to(device)`):
  - `ROCR_VISIBLE_DEVICES=$SLURM_PROCID` **alone** (do NOT also set `HIP_VISIBLE_DEVICES` — HIP
    then indexes into the already-filtered 1-GPU list), **or**
  - `srun --gpus-per-task=1` (cgroup-pins each task to one GCD, renumbered to index 0) **with NO
    env pinning** (adding `ROCR=$RANK` on top indexes into a 1-GPU list → GPU-less ranks).

**The two launch patterns for one DDP group — and the one that silently corrupts:**

| | Pattern A (per-task pin) | Pattern B (all-visible) |
|---|---|---|
| `srun` | `--ntasks=8 --gpus-per-task=1 --cpus-per-task=7` | `--ntasks=8 --gpus-per-node=8` (no per-task GPUs, no ROCR) |
| framework | **no `--devices` flag** (let SLURM env form the group) | `--devices 8` |
| each rank sees | its own 1 GCD (cgroup) | all 8 GCDs |

- **Prefer Pattern A on any image whose code does `model.to("cuda")` (=`cuda:0`) *before* the
  framework assigns per-rank devices.** Under Pattern B in that case, **all 8 ranks load the
  model onto GPU 0 → HIP OOM in ~3 min** (`GPU 0 … 0 bytes free`). Pattern A cgroup-pins each
  rank first, so `cuda:0` *is* the rank's own card. This is image-dependent and has bitten
  real jobs both ways, so **[ADAPT]**: check where your entrypoint calls `.to(cuda)` relative to
  the Lightning device assignment, and smoke-test the launch you chose.
- **⚠️ Multi-node does NOT reliably extend Pattern A by just adding `--nodes=N` — verified the
  hard way (2026-08-15).** The naive extension (`--nodes=N --ntasks-per-node=8
  --gpus-per-task=1`, still no `--devices`) does not crash or hang — it **silently forms N
  independent single-node groups instead of one N×8 group**, which is worse than a hang because
  it looks like it's training. Tell: each rank's framework-level run/logger id (e.g. Lightning's
  `v_num`) repeats per node instead of being shared cluster-wide — `grep -h 'v_num'
  */train_rank*.log | sort -u` showing `v_num: 0` on every node-0 rank and `v_num: 1` on every
  node-1 rank (instead of one value shared by all ranks) is the silent-split signature. Trying to
  force it by adding `--devices 8 --num_nodes N` fails **louder** instead of fixing it —
  `MisconfigurationException: You requested gpu: [0..7] But your machine only has: [0]` — because
  under per-task cgroup pinning every rank's process only ever sees ONE GPU, so `--devices 8` is
  simply the wrong number to hand the framework in this pattern. **The verified fix path is the
  `torchrun`/c10d launcher** (`torchrun --nnodes=N --nproc_per_node=8 --rdzv_backend=c10d
  --rdzv_endpoint=<node0>:<port>` in place of raw `srun` + framework SLURM-env auto-detect — this
  is CSC's own documented pattern for LUMI multi-node, not something we invented), which was
  identified but **not yet built/verified** in our stack — treat multi-node as unsolved until it
  is. If the inter-node fabric itself is the problem (a real hang at rendezvous, not a silent
  split), check `NCCL_SOCKET_IFNAME` matches the node's Slingshot NICs (`ip -o link | grep hsn`
  on a compute node) — but confirm you're not looking at the silent-split case first, since that
  one doesn't hang at all.

**Verify you actually formed ONE coordinated group — do not assume it:**
- **Un-versioned checkpoints** (a single rank-0 writer). If you see `epoch=…-v1 … -vN` versioned
  files, you have **N uncoordinated duplicate trainers** each writing its own — burning the node
  for nothing.
- The log prints `initializing distributed … MEMBER: 1/<world>` and a world-size line. No such
  line = no group formed.
- `steps/epoch = dataset_size ÷ (per-GCD_batch × world_size)`. If it's `N×` what you expect,
  that's N duplicate trainers again.

**⚠️ The inverse case — running N INDEPENDENT arms in one allocation (an A/B or sweep, NOT one
DDP model) — must PREVENT a group from forming.** If you launch N different configs (different
optimizer/hyperparams) as separate processes in one job and do nothing to isolate them, two things
bite, and they look like different bugs:
- **GPU collision → OOM.** N backgrounded `srun … --gpus=1` steps, each *also* setting a manual
  `ROCR_VISIBLE_DEVICES`, compose two device filters and can land all N arms on **one** card — they
  OOM each other at a fraction of a single run's real footprint (the tell: an OOM far below the
  memory a single run needs for its optimizer state alone). Fix: **one** pinning mechanism (see the
  Pattern-A/B table above), not two stacked.
- **Rendezvous collision → NCCL deadlock.** The frameworks derive a single distributed rendezvous
  from `SLURM_JOB_ID`, so the N *independent* arms accidentally join **one** process group and then
  **hang forever on a collective** (`ALLGATHER`/barrier) — because they're different configs
  progressing at different speeds, one rank hits the collective and waits out the ~30-min NCCL
  watchdog timeout, killing the group. The tell: `Watchdog caught collective operation timeout …
  OpType=ALLGATHER, NumelOut=N`, and a `world_size` = N when you meant N standalone runs. **Fix:
  force each arm to be a standalone single-process run** — `export SLURM_JOB_NAME=bash` (makes
  PyTorch-Lightning's SLURM detector return false → single-process `LightningEnvironment`, no shared
  rendezvous), plus a distinct `MASTER_PORT` per arm as belt-and-braces. Without this, an A/B whose
  arms *look* like they ran can be silently corrupted, or the deciding arm can die on the timeout
  and leave you with no verdict.

---

## 6. The silent-failure family, and how to defend

Every one of these exits `COMPLETED`. Defend against all of them:

- **`if python …; then …; else echo FAILED; fi` masks a crash as success.** A Python exception
  makes the branch fall through and the script exits 0 → SLURM says COMPLETED. A 20-epoch job
  that "COMPLETED" in 4 minutes *crashed*. **Real success = artifact count + a log with real
  progress lines** (`epoch/step/loss`). End scripts with an explicit assertion, e.g.
  `n=$(ls "$OUT"/*.ckpt | wc -l); [ "$n" -ge "$EXPECTED" ] || { echo "SHORT: $n/$EXPECTED"; exit 1; }`.
- **`rc` lies both ways.** A fully-successful job reports **FAILED** if the script's last command
  is a bare false conditional (`[ cond ] && echo warn`). End on an `if…fi` or an unconditional
  `echo`, never a trailing bare `&&`.
- **A python-heredoc's quoting error is invisible until runtime.** A `python3 <<'PY' … PY` block
  embedded in a shell script is not parsed until the job runs that line — so a bad quote (classic:
  escaped double-quotes inside an f-string, inside a single-quoted heredoc) makes the step it
  guards **silently die while the job continues and exits COMPLETED**. Defend with a **pre-submit
  parse check**: extract every embedded python block and `ast.parse` it (a ~40-line script;
  mind that an outer `bash -c '...'` splices shell values with the `'"${VAR}"'` idiom, which is
  gone by the time python sees the line — a naive checker cries wolf on that correct pattern).
- **Un-exported outer-shell vars vanish silently inside `srun … bash -c '…'` under `set -u`.** A
  reference to an un-exported var inside the nested command substitution dies *empty* — the whole
  flag disappears from the command line instead of erroring (e.g. `--epochs 2` silently dropped,
  a smoke ran open-ended for hours). After editing an sbatch, grep the inner script for `${…}`
  names and confirm each is `export`ed or string-interpolated.
- **HQ / job-array task failures do NOT propagate to the job rc.** If you fan out with HyperQueue
  or a task array, the *job* reports COMPLETED even if half the tasks crashed. Count outputs;
  read per-task `*.err` logs; guard `hq job wait all || true` so one failed task doesn't kill your
  merge/verify tail under `set -e`.
- **`/dev/shm` exhaustion on many DataLoader workers.** 8 ranks × 6 workers = 48 workers passing
  tensors through the node's `/dev/shm` → `unable to allocate shared memory … (11)` **mid-run**.
  Fix: `torch.multiprocessing.set_sharing_strategy("file_system")` (shares via `/tmp` files —
  bind `/tmp`) **+ raise `ulimit -n`** in the sbatch. This is a *slow fill* — a short smoke will
  not catch it.

- **EMA (or any technique that holds a second full-precision copy of the model) OOMs at batch
  sizes that "look small enough" on paper — verified 2026-08-15.** If your training loop keeps
  an EMA shadow of a full-finetuned model, that is fixed memory overhead **on top of** the
  training model, independent of batch size or sequence length — a smaller batch or shorter
  sequence does not shrink it. Two separate EMA+full-finetune jobs OOM'd on plausible-looking
  configs in one project before this generalized: don't assume the first OOM was a one-off,
  fix the pattern everywhere the technique is used, not just where it first failed. **The
  robust fix is `batch_size=2` + gradient accumulation to reach your target effective batch,
  not a larger raw batch size** — accumulation adds compute time, not a second resident
  optimizer-adjacent copy, so it's the dimension that's actually free to raise.
- **A `COMPLETED`/still-running job with an old-looking checkpoint may just be an auto-resume,
  not real progress (2026-08-15).** If your script auto-resumes from the newest checkpoint in
  its output dir, and you reuse the same output-dir name across a resubmit after a crash, the
  "newest checkpoint" you see moments after resubmitting can be a **leftover from the crashed
  predecessor run**, not new output — check its mtime against the resubmit's actual start time
  before reading progress into it.
- **Grepping logs for `nan`/`inf` throws false positives from ordinary words.** Both substrings
  appear inside common English words that show up in normal log output or generated text —
  "**inf**erence", "re**inf**orce", etc. A bare `grep -i "nan\|inf"` hit count is not evidence of
  a real numeric explosion; read the matched lines before concluding anything.

**SMOKE-first discipline.** Run every new config at a tiny step count (e.g. `--steps 40`) and
read the `.out` for the success markers — files found, steps progressing, all GCDs active, no
OOM, no `Couldn't load` — **before** betting node-hours. It catches most of the above in minutes.
(Exceptions: slow-fill failures like `/dev/shm` and inode exhaustion won't show in a short smoke.)

---

## 7. Shipping code & data to LUMI

- **Ship the working tree, never `git archive HEAD`.** `git archive` silently drops every
  uncommitted change — a job depending on an unstaged patch dies argparse-rejecting in seconds
  (and still burns a queue slot + node spin-up). Build the tarball from the working tree
  (`tar --exclude='.git' --exclude='__pycache__' …`), and **before submitting, verify the shipped
  file actually contains your patch** (`grep` the flag on the remote copy).
- **⚠️ Grep your code for HARDCODED LOCAL ABSOLUTE PATHS before shipping — a perfect sbatch can't
  save code that hardcodes your laptop's paths.** The single sneakiest failure: your job runs fine
  locally and imports/opens nothing on the cluster, because the Python has
  `sys.path.insert(0, '/home/you/project')` or a subprocess call to `/home/you/project/tool.py`.
  On LUMI the code lives at `/scratch/<proj>/…`, so those paths silently don't exist and the import
  or subprocess fails deep in the job — while the sbatch itself looks flawless. **Derive paths from
  the file's own location, never hardcode:** `ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`
  then `sys.path.insert(0, ROOT)`. Pre-flight check before every ship:
  `grep -rn "/home/" your_code/ --include='*.py'` — every hit is a portability bug. (This one cost a
  real cross-project debugging session: the sbatch followed every rule below and still failed because
  `eval_point.py` hardcoded `/home/<user>/project` in three places.)
- **Sync the whole interdependent file set**, not just the entrypoint. Shipping 2 of 3 files a
  feature spans yields a `TypeError: … unexpected keyword` a few minutes in. Check matching mtimes.
- **`rsync ≥ 3.4` removed multi-path remote args** — one quoted remote string with two paths gives
  "No such file or directory". Use one source dir + `--include`/`--exclude` filters, or separate
  commands. Epoch-range include patterns make a `-n` dry-run self-answering (it lists exactly what
  exists remotely).
- **[ADAPT] agents don't run interactive-passphrase ssh/scp/rsync themselves** — if a key has a
  passphrase, an agent-run transfer hangs on the prompt. Craft the exact one-line command and have
  the human paste it; propose `-n` first (the dry-run doubles as a remote inventory).

---

## 8. Security on a shared cluster

**CLI arguments are visible to other users** — `squeue`/`sacct` expose the full submit command,
and anyone on the same node can see it. **Never pass a secret on the command line** (`--api-key`,
tokens, passwords). Route everything sensitive through **env vars** (`WANDB_API_KEY` exported
inside the job) or a pre-staged credential file. Audit your scripts for CLI-passed secrets before
first submit.

---

## 9. A minimal working skeleton (Pattern A DDP training)

Genericized from a production launch. Substitute the **[ADAPT]** lines.

```bash
#!/bin/bash
#SBATCH --account=project_465000000        # [ADAPT] your <proj>
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8                 # Lightning: per-node, NOT bare --ntasks
#SBATCH --cpus-per-task=7                   # 7×8 = 56 = the real usable-core ceiling
#SBATCH --mem=0                             # all node RAM
#SBATCH --time=48:00:00                     # LUMI standard-g max is 2 days — see §10
#SBATCH --job-name=my_ddp_run
#SBATCH --output=%x-%j.out                  # lands in the SUBMIT-TIME cwd
#SBATCH --open-mode=append                  # cheap insurance if a job ever requeues

set -euo pipefail

PROJ=project_465000000                      # [ADAPT]
IMG=$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif | sort | tail -1)
CODE=/project/$PROJ/code                    # [ADAPT] your code tree
OUT=/scratch/$PROJ/runs/$SLURM_JOB_NAME-$SLURM_JOB_ID
mkdir -p "$OUT"
EXPECTED_CKPTS=${EXPECTED_CKPTS:-60}        # [ADAPT] what "done" means for you

# Pattern A: one GCD per task, NO --devices flag on the trainer.
srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind /project/$PROJ,/scratch/$PROJ,/tmp "$IMG" bash -c '
    export MIOPEN_USER_DB_PATH=/tmp/miopen-$SLURM_PROCID MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-$SLURM_PROCID
    export TRITON_CACHE_DIR=/tmp/triton-$SLURM_PROCID
    export PYTORCH_TUNABLEOP_ENABLED=0
    export HF_HOME=/scratch/'"$PROJ"'/models HF_HUB_OFFLINE=1
    export WANDB_MODE=offline WANDB_DIR='"$OUT"'
    mkdir -p /tmp/miopen-$SLURM_PROCID /tmp/triton-$SLURM_PROCID
    ulimit -n 131072
    cd '"$CODE"'
    python3 train.py --out '"$OUT"' '"${SMOKE:+--steps 40}"'    # [ADAPT] your entrypoint; no --devices
  '

# §0 / §6: assert artifacts, never trust rc.
n=$(ls "$OUT"/*.ckpt 2>/dev/null | wc -l)
if [ "$n" -ge "$EXPECTED_CKPTS" ]; then echo "OK: $n/$EXPECTED_CKPTS checkpoints"; else
  echo "SHORT: $n/$EXPECTED_CKPTS — job is NOT done regardless of SLURM state"; exit 1; fi
```

Note the `${SMOKE:+--steps 40}` — submit once with `SMOKE=1 sbatch script` for the smoke, then
without it for the real run. And note the last lines: the job grades *itself* on artifact count.

---

## 10. Pre-submit checklist

1. **Image:** multitorch (ROCm 7, prebuilt FA2) unless you have a reason not to. `--bind` on every
   `singularity exec`.
2. **Env block** present and inside the container `bash -c`: MIOpen + Triton → `/tmp`, TunableOp
   off, `HF_HUB_OFFLINE=1`, `ulimit -n` raised.
3. **Caches pre-staged** on a login node and **verified complete** (`ls snapshots/*`).
4. **DDP launch** is one pattern, not two stacked; no bare `--ntasks`; you know how you'll verify
   one group formed (un-versioned ckpts / world-size line / steps-per-epoch math).
5. **Code shipped from the working tree**, patch verified present on the remote copy.
6. **Every embedded python heredoc parses** (run the pre-submit parse check).
7. **Inner-script vars exported/interpolated** (grep `${…}` under `set -u`).
8. **No secrets on any command line.**
9. **The script grades itself** at the end on artifact count and `exit 1` on a shortfall.
10. **Walltime:** LUMI `standard-g` caps at **2 days (48 h)**. A run longer than that MUST
    checkpoint and be resumable — and **[ADAPT]** confirm your resume starts from the checkpoint
    you mean: many launchers auto-resume from the newest checkpoint in the run dir, so re-launching
    into the same dir silently resumes a bad/old state. Use a fresh run dir (new tag) when you
    intend a clean start.
11. **SMOKE first** (tiny step count), read the `.out`, then submit the real run.

---

## Appendix — diagnosing a job that "finished wrong"

- `%x-%j.out` lands in the **submit-time cwd**. A "missing" log usually means you submitted from
  elsewhere: `sacct -j <id> --format=JobID,State,ExitCode,Elapsed,WorkDir%90`.
- A `COMPLETED` job with a tiny `Elapsed` (e.g. 33 s) = an idempotent no-op or a fast
  crash-with-rc-0. Check `Elapsed` alongside `State`.
- A job that stays `R` past the ~4-min crash band is **not automatically training** — confirm the
  training log's **mtime is advancing** (a conv-solver hang stays `R` while frozen).
- A framework that recursively retries failed data loads can turn one bad file into a 40k-line
  `RecursionError` that buries the root cause — **read the FIRST traceback, not the recursion
  tail**: `ln=$(grep -n Traceback log | head -1 | cut -d: -f1); sed -n "$ln,+40p" log`.

---

*This guide distills operational lessons from an SA3/PyTorch-Lightning training project on LUMI-G.
The project-internal source (with the SA3-specific entrypoint, optimizer, and dataset gotchas that
are out of scope here) lives in that project's `lumi-ops` skill and throughput-workflow guide.*
