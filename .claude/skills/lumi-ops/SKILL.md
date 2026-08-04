---
name: lumi-ops
description: Use when working with LUMI/EuroHPC — checking or submitting jobs, writing/debugging sbatch or HyperQueue scripts, transferring files to/from /scratch or /project, diagnosing jobs that "completed" with missing outputs, or crafting ssh/rsync/scp commands for Kim to run against akekim@efp.lumi.csc.fi.
---

# LUMI operations (project_465003186)

## Access model — the #1 rule

**Agents never run ssh/scp/rsync to LUMI themselves.** Kim's key (`~/.ssh/id_EFP`) has an
interactive passphrase; an agent-run command hangs on the prompt, and handling the passphrase
is refused on principle. The working loop:

1. You **craft the exact command** (always `-i ~/.ssh/id_EFP`, host `akekim@efp.lumi.csc.fi`).
2. Kim pastes it in his terminal (or runs `! <cmd>` in-session) and pastes the output back.
3. For transfers: propose `-n` (dry-run) first; the dry-run listing doubles as a remote
   inventory check.

A double passphrase prompt on scp/rsync is normal, not an error.

**PASTE SPEC (Kim direct 2026-07-23): every command crafted for Kim must be a SINGLE
LINE.** No backslash continuations, no heredocs, no multi-line loops — pasting those into
his terminal produces `>` continuation prompts and mangles the command. Long pipelines:
join with `&&`/`;` on one line. If a construct genuinely needs multiple lines (rare),
write it to a script file and give Kim a one-line `bash <path>` instead.

## Containers — READ THIS FIRST (a full day of debugging came from not knowing it, 2026-08-02)

Which SIF you train in decides whether MIOpen fights you.

- **`${PROJ}/containers/sa3.sif`** — our cotainr training build, but **ROCm 6.2.4, NO flash-attn**
  (FA absent by design: our CK wheel is gfx1201/RDNA4-only, no gfx90a FA was built). Its MIOpen's
  gfx90a FindDb has **per-shape gaps**, and on a gap `MIOPEN_FIND_MODE=2` (FAST) falls to the
  immediate-mode **AI heuristic**, which mispredicts a workspace-0 `ConvAsmImplicitGemm…Xdlops`
  solver and **hangs the first backward pass forever** (job stays R, GPU busy, `train.log` mtime
  frozen — NOT a crash). Precision-independent: **bf16 and fp32 both hit it.** If you must use
  this image: set **`MIOPEN_FIND_MODE=1`** (NORMAL, real benchmark) or **3** (HYBRID: db-hit=fast,
  miss=real-find) — **NEVER 2** for our shapes — and redirect ALL user MIOpen stores off `$HOME`
  (`MIOPEN_USER_DB_PATH=/tmp/…` = FindDb+PerfDb, `MIOPEN_CUSTOM_CACHE_DIR=/tmp/…` = kernel cache;
  else they refill the 100k home inode quota → failure mode #1). To pay the find ONCE, point
  `MIOPEN_USER_DB_PATH` at a persistent per-arm `/scratch` dir and reuse.

- **`/appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif`** — LUMI official
  AI image: **ROCm 7 + prebuilt gfx90a flash-attn** (+ bitsandbytes, vLLM). Newer MIOpen; the 6.2
  find-fallback hang does not occur, and FA2 speeds attention. **Preferred base for training and
  captioning.** Used via a `--system-site-packages` venv overlay on `/scratch` (pattern:
  `lumi/build_offload_venv_mt.sh` for captioning). **PYTHONPATH-prepend is load-bearing** — put the
  overlay's `site-packages` FIRST or the image's own `/opt/venv` shadows it. Readable path is
  `/appl/local/laifs/containers/`, NOT the `easybuild-sif-images` symlinks (those point into
  another project's non-world-readable scratch).

**Default going forward: train on `lumi-multitorch-full`.** `sa3.sif` (6.2) is legacy — only fall
back to it with `FIND_MODE=1/3`. The captioning + goa_caption jobs already run on multitorch.

## MANDATORY GPU-job env exports — EVERY LUMI GPU job (sbatch AND interactive srun)

Set these inside the container `bash -c`, before `python`, ALWAYS. A bare srun probe that skips
them **dies on the first GPU convolution** — this is not optional polish.

```
export MIOPEN_USER_DB_PATH=/tmp/miopen-$$ MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-$$
export TRITON_CACHE_DIR=/tmp/triton-$$
export PYTORCH_TUNABLEOP_ENABLED=0
mkdir -p /tmp/miopen-$$ /tmp/triton-$$
```
(Use `$SLURM_PROCID` instead of `$$` for per-rank isolation in a multi-task srun.)

Why each is load-bearing:
- **`MIOPEN_USER_DB_PATH` / `MIOPEN_CUSTOM_CACHE_DIR` → /tmp** — fixes TWO failures at once:
  (a) **`miopenStatusUnknownError` on the first conv.** Root cause: `stable_audio_3/__init__.py`
  runs `_apply_rocm_profile("inference")`, which **hardcodes the LOCAL desktop path
  `/home/kim/pytorch-tunings-7.2.3`** for MIOpen's user perf-db. On LUMI that path is read-only /
  absent → `MIOpen Error: cannot create directories: Read-only file system` → the encoder/DiT dies
  on its first convolution. (b) home 100k-inode quota (MIOpen db files pile up in `$HOME`).
  The exports **pre-empt** apply_profile (it setdefaults, so a pre-set env wins — proven: the
  training grids set these and run fine; a bench srun that omitted them crashed on same-l encode).
- **`TRITON_CACHE_DIR` → /tmp** — keeps torch.compile cache off `$HOME` (the 100k-inode death that
  stalled captions at 9%).
- **`PYTORCH_TUNABLEOP_ENABLED=0`** — the multitorch image enables TunableOp by default and points
  it at that same bogus `/home/kim/pytorch-tunings-7.2.3` csv → per-GEMM search cost + log spam.

The `rocm_env.apply_profile('inference') ran after torch import` warning in **every** LUMI log is
the same defect surfacing: the profile is both the WRONG one for training AND applied too late to
take effect. Standing code-fix (not yet done): move `apply_profile('training')` BEFORE `import
torch` in `train_lora.py`; until then, the /tmp exports above make it harmless.

## singularity needs `--bind` to WRITE /project or /scratch

`singularity exec <IMG>` mounts `/project` and `/scratch` **read-only** (or not at all) unless you
`--bind` them — an interactive one-liner that omits it fails with `OSError: [Errno 30] Read-only file
system: '/project'` (bit a Granite model-stage 2026-08-03). The sbatch templates all carry
`--bind ${PROJ},${SCRATCH},${FLASH},/tmp`; **replicate it on every ad-hoc `singularity exec`** (model
staging, quick probes): `singularity exec --bind /project/project_465003186,/scratch/project_465003186 <IMG> …`.

## Vendored `stable_audio_tools` on LUMI DRIFTS from the live SAT repo (2026-08-04)

SA3 training imports `build_fusion_param_groups` / FusionOpt from `stable_audio_tools`, which on LUMI
is a **vendored subset at `code/lumi/vendor/stable_audio_tools/`** (on the sbatch PYTHONPATH), NOT the
full SAT repo. It goes stale independently of the fork: the first LUMI **FusionOpt** run hit a July-15
`fusion_groups.py` predating W's `--fusion-split-qkv` → `TypeError: build_fusion_param_groups() got an
unexpected keyword argument 'split_qkv'` at `configure_optimizers`. The melody-wall grids missed it —
they used `--optimizer adamw`. **Any LUMI job using `--optimizer fusion` must refresh the vendor
alongside the fork:** `cp stable-audio-tools/stable_audio_tools/training/{fusion_groups,fusion_opt}.py
lumi/vendor/stable_audio_tools/training/` then rsync that dir up. (Leave the vendored `__init__.py` —
it's a curated subset; the full SAT one pulls unvendored modules.)

## Paths (always literal — `$SCRATCH` etc. are NOT set in login shells)

| what | path |
|---|---|
| code tree (mirror of SAO) | `/project/project_465003186/code` — NOT the stray top-level `/project/.../lumi` |
| container / models | `/project/.../containers/sa3.sif`, `/project/.../models` |
| runs, renders, latent tarballs | `/scratch/project_465003186/{runs,renders,latents_*.tar.gz}` |
| node-local staging (in-job only) | `/flash/project_465003186` |
| local pull targets | `Mantu/lumi_runs/...` and the `9a410a1d-…` drive (`lumi_runs/runs/...`) — **land pulls where the existing `sa3_lora_runs` symlinks already resolve**; check `readlink` before inventing a new dir |

## Job scripts — start from the proven skeletons, never from scratch

- Multi-arm one-task-per-GCD: `lumi/sbatch/efp_fp32_compare.sbatch` (srun + `SLURM_PROCID` arm table).
- Many short tasks / HQ packing: `lumi/sbatch/native_cells_hq.sbatch` or `fullft_cells_hq.sbatch`
  (post-2026-07-21 fixes) — older templates may still carry the bugs below; diff before reuse.

**Non-negotiables in any GPU sbatch** (each cost a real failure):
- GCD pinning is `export ROCR_VISIBLE_DEVICES=$SLURM_PROCID` **alone**. Adding
  `HIP_VISIBLE_DEVICES` stacks: HIP indexes into the ROCR-filtered 1-GPU list → "No HIP GPUs
  are available" on every worker but 0 (job 20068082: 7/8 workers dead).
- **The stacking trap has a SLURM layer too** (probe 20422524): `srun --gpus-per-task=1`
  ALREADY pins via cgroup (each task sees 1 GPU, renumbered index 0) — exporting
  `ROCR_VISIBLE_DEVICES=$RANK` on top indexes into that 1-GPU list → ranks 1-7 GPU-less,
  crash at `model.to(device)`. Two valid patterns, never mixed: (A) `--gpus-per-task=1`,
  NO env pinning (the efp training sbatches); (B) no per-task GPUs, `ROCR=$PROCID` alone
  (the HQ/muscriptor pattern). Pick one per job.
- **8-GPU Lightning DDP — VERIFIED recipe** (smoke 20422454, COMPLETED): `srun --ntasks=8
  --gpus-per-node=8` (no per-task GPUs, no ROCR) + `train_lora.py --devices 8` (passes
  Trainer devices=8 + strategy='ddp_find_unused_parameters_true' — never trust
  strategy="auto"). Proof-of-correctness checks: ckpts UN-versioned (one rank-0 writer)
  and steps/epoch = dataset ÷ (per-GCD bs × 8) — e.g. 5401 crops, global batch 8 → 675
  steps/epoch. Versioned `-vN` ckpts or N× the step count = you have N duplicate trainers.
  Template: `lumi/sbatch/aug8_train_ddp.sbatch`.
- **DDP inverts the pinning rules** (smoke 20413874): for a Lightning multi-GPU group, srun
  with `--gpus-per-node=8`, **NOT `--gpus-per-task=1`** — per-task cgroups isolate each rank
  to 1 GPU → `devices="auto"`→1 → SingleDeviceStrategy → **N uncoordinated duplicate
  trainers** silently burning the node (tell: `epoch=…-v1..-vN` versioned ckpts = N writers;
  no "Initializing distributed"/world-size lines; ~400 GB of duplicate ckpts before caught).
  Also no ROCR pinning for DDP — every rank must see all 8 GCDs; Lightning binds via
  SLURM_LOCALID. Per-GCD independent arms keep `--gpus-per-task=1` + ROCR as before.
- `hq job wait all || true` — under `set -e`, one failed task otherwise kills the script before
  the merge/success-check tail runs.
- HQ log names `j%{JOB_ID}-t%{TASK_ID}.*` — each `hq submit` is its own job, so `task-%{TASK_ID}`
  clobbers everything into `task-0`.
- MIOpen needs BOTH halves (each alone fails, 2026-07-29 probe): `MIOPEN_USER_DB_PATH`/
  `MIOPEN_CUSTOM_CACHE_DIR` → per-task `/tmp` dir (else it writes a read-only path) **AND**
  `MIOPEN_DISABLE_CACHE=1` (the SQLite user-db can't open even on /tmp:
  `Cannot open database file .../gfx90a6e.ukdb` → `miopenStatusInternalError`).
- `PYTORCH_TUNABLEOP_ENABLED=0` in EVERY GPU python — SA3's rocm_env points TunableOp results
  at a read-only `/home/kim/pytorch-tunings*` path; left on, it silently re-benchmarks every
  GEMM (job 20375990: ONE encode forward ate a 10-min wall). The tell in the log:
  `could not open .../tunableop_results0.csv`.
- `HF_HOME=/project/.../models HF_HUB_OFFLINE=1`; `--bind ${PROJ},${SCRATCH},${FLASH},/tmp`.
- **Every `singularity exec` that touches /scratch or /project needs its own `--bind`** — a
  bare exec sees the container's OWN read-only paths; symptom `[Errno 30] Read-only file
  system: '/scratch'` (build_offload_venv 2026-07-30: venv-create line lacked the bind that
  the sibling pip line had). Audit each exec in a script separately.
- **A venv created INSIDE the SIF has `bin/python` symlinked to the container's conda python**
  — a broken link on the host, so a prolog `[ -x $VENV/bin/python ]` false-reports the venv
  missing (probes 20422459/60 died on a venv that was fully built + verified). Host-side
  existence checks: `[ -f $VENV/bin/activate ]` (regular file). The venv itself only works
  inside `singularity exec` anyway.
- **Ad-hoc srun probes: copy the FULL env block from a proven sbatch, never reconstruct
  piecemeal** — the 2026-07-29 encode probe burned three sruns each missing one var
  (PYTHONPATH → MIOpen /tmp → TUNABLEOP). One block, verbatim, every time.
- **Outer-shell vars referenced inside the nested `srun … bash -c '…'` must be `export`ed**
  (or string-interpolated `'"${VAR}"'`). Un-exported + `set -u`, a reference inside a
  command substitution dies **silently empty** — the whole flag vanishes from the command
  line instead of erroring (job 20413874: `--epochs 2` dropped, smoke ran open-ended 3h+;
  the only tell was `environment: line N: VAR: unbound variable` scrolling past). After any
  sbatch edit, grep the inner script for `${` names and check each is exported or interpolated.
- Offline model deps: `ls $MODELS/hub/models--<org>--<name>/snapshots/*/` BEFORE submitting —
  a missing/half-staged HF cache fails as a clean `LocalEntryNotFoundError` deep into the job
  (aug8 20190474), and a submit racing an in-flight rsync fails the same way (20328856).

## Containers & venv overlays (running non-SA3 stacks on LUMI)

- **Official LUMI AI images live at `/appl/local/containers/sif-images/`** — no download:
  `lumi-pytorch-rocm-<r>-python-<p>-pytorch-<t>.sif` (plain torch; the 6.2.3/py3.12/t2.5.1
  one matches our sa3.sif base) and `lumi-multitorch-*.sif` (torch + **Flash Attention,
  bitsandbytes, DeepSpeed, vLLM prebuilt for gfx90a**). The multitorch image = the no-build
  FA2 path — never compile flash-attn into a cotainr SIF yourself. Docs:
  docs.lumi-supercomputer.eu/laif/software/ai-environment/.
- **Multitorch image — PROVEN IN PRODUCTION (goa captions, 2026-07-30).** Resolve the
  newest FULL variant with
  `ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif | sort | tail -1`
  (the `-full-` builds carry flash-attn; verified stack: torch 2.10+rocm7.0, flash_attn
  2.8.4, python 3.12). FA2 engages on gfx90a via HF
  `attn_implementation="flash_attention_2"` + **bf16/fp16 dtype (FA2 refuses fp32)** —
  probe 20431533: fa2=True on all 8 ranks, killed the 600 s-audio quadratic-attention
  OOMs that eager/sdpa-math hit (sdpa on ROCm fell back to the math backend, so the
  sdpa flag changed nothing — multitorch+FA2 is the real fix for long-sequence OOM).
  Venv overlay + PYTHONPATH prepend per the bullets below; template
  `lumi/build_offload_venv_mt.sh`, run recipe in `lumi/sbatch/goa_caption.sbatch`
  (`CAPTION_SIF=`/`CAPTION_VENV=`/`MF_USE_FA2=1` overrides).
- **Venv-overlay pattern** (proven, template `lumi/build_offload_venv.sh`): create the venv
  INSIDE the target SIF with `--system-site-packages` onto $SCRATCH (torch/ROCm comes from
  the image; pip adds the rest). Notes: venv is tied to that image's python — switching
  images = rebuild; `pip --no-deps` for heavy meta-packages (e.g. audio-separator), then
  satisfy the *import chain* (its package __init__ may need onnxruntime/ml_collections
  even if unused); NO C-extension pip builds (no gcc in the SIFs — a failing sdist aborts
  the whole pip call); static binaries (ffmpeg) can be dropped into `$VENV/bin`.
- **AIF/multitorch images ship their own `/opt/venv` and SHADOW an overlay venv** — imports
  silently resolve to the container's package versions even after `source $VENV/bin/activate`
  (2026-07-30: container transformers 4.57.6 won over the venv's 5.x; symptom = the wrong
  `__file__` under /opt/venv). After activate, always
  `export PYTHONPATH=$VENV/lib/python3.12/site-packages${PYTHONPATH:+:$PYTHONPATH}`, and
  assert the critical package's `__file__` is NOT under /opt/venv. Related: the READABLE
  AIF images live under `/appl/local/laifs/containers/` — the `easybuild-sif-images/`
  symlinks point into another project's scratch and are NOT world-readable. And
  `is_flash_attn_2_available()` is always False on the GPU-less login node (it checks
  `torch.cuda.is_available()`) — test FA2 engagement in a GPU probe, not at build time.
- **Long-audio/LLM inference OOM on a 64 GB GCD** (caption probe 20423099: 14-24 GiB attn
  allocs on ~15-min tracks): eager attention materializes L×L — load HF models with
  `attn_implementation="sdpa"` (or FA2 via multitorch); cap/chunk overlong inputs; and
  `PYTORCH_HIP_ALLOC_CONF=expandable_segments:True` for the fragmentation half (tell:
  huge "reserved but unallocated" in the OOM message).

## Verification — count artifacts, never trust rc

**A COMPLETED / exit-0 sbatch proves nothing about HQ tasks** (failures don't propagate).
Success = expected-vs-actual output count (`ls <outdir>/*.wav | wc -l`), stated by the job's
own tail. Per-task tracebacks: `<runroot>/hq_logs/j*-t*.err`. Same family: `$(date)` clobbers
`$?`, `pgrep -f 'a\|b'` never matches (MASTER §5).

- `%x-%j.out` lands in the **submit-time cwd** — a "missing" log usually means submitted from
  elsewhere: `sacct -j <id> --format=JobID,State,ExitCode,Elapsed,WorkDir%90` finds it (20206765).
- **HQ per-task stdout lives under `/tmp/hq-worker.*/logs` ON THE COMPUTE NODE — gone when the
  job ends.** Any timing/diagnostic you might need post-mortem must be printed to the main
  `.out` (or a $SCRATCH file) by the task itself (aug8 postmortem had no per-latent timings).
- A `COMPLETED` job that ran seconds (e.g. 33 s) = idempotent no-op or fast crash-with-rc-0 —
  check `sacct` Elapsed alongside State before celebrating.
- rc lies BOTH ways: a fully-successful job reports **FAILED** if the script's last command is
  a false `[ cond ] && echo warning` (probe 20422698: 72/72 artifacts perfect, state FAILED).
  End scripts with `if…fi` or an unconditional echo, never a bare conditional.

Budget: `lumi-allocations` on LUMI; standard-g bills **whole node × walltime** (8 GCD-h/h).

## Code refresh to LUMI — WORKING TREE, never `git archive`

`git archive HEAD` ships HEAD, silently dropping every uncommitted patch (job 20162280:
all 8 arms died in 53 s because the fp32 `train_lora.py` patch is working-tree-only and
the refresh used git archive). Build refresh tarballs from the working tree:
`tar -czf sa3_code.tar.gz --exclude='.git' --exclude='wandb' --exclude='*.ckpt'
--exclude='latents*' --exclude='__pycache__' -C <repo> <dirs>` — and BEFORE submitting
any job that depends on a patch, verify the SHIPPED file has it (e.g.
`grep -c "'fp32'" $CODE/stable-audio-3/scripts/train_lora.py` on LUMI, or parse-test the
flag in the SIF). A submit that argparse-rejects in seconds still burns a queue slot and
a node spin-up.

## Transfers

- **rsync ≥3.4 removed multi-path remote args** — one quoted remote string with two paths =
  "No such file or directory". Use ONE source dir + `--include`/`--exclude` filters
  (`--include='<dir>/' --include='epoch=[4-7]-*.ckpt' --exclude='*' --prune-empty-dirs`), or
  separate commands.
- Conditional pulls: epoch-range include patterns make rsync self-answering — the dry-run
  listing shows exactly what exists remotely (e.g. "did this run reach ep7?").
- A fat `epoch=N.ckpt` (vs slim `.weights.ckpt`) marks a run's **terminal** epoch; pull fat only
  for the last epoch (Kim's standing rule), slims elsewhere.

## Job-launch failure modes (2026-08-02 saga — all four bit in one session)

A fresh grid can die four distinct ways that ALL look like a fast/silent finish. Diagnose in
this order; the real error is almost never in the sacct state.

1. **Home inode quota → job dies at ~1s, often NO `.out` written.** `~/.triton` (torch.compile
   cache) fills the 100k home inode quota → SLURM can't create the output file → instant death.
   Diagnose: `lumi-quota` (home **Files used/max**), `find ~/.triton -type f | wc -l`.
   Fix (global, catches EVERY container job): `echo export APPTAINERENV_TRITON_CACHE_DIR=/tmp/triton_cache >> ~/.bashrc`.
   Per-sbatch: `export TRITON_CACHE_DIR=/tmp/triton-${ARM}` next to the MIOpen redirect.
   **"no MIOpen anchor ≠ safe"** — the caption job had no MIOpen line yet still wrote `~/.triton`
   via a HF model's internal compile. Any model-running job needs the redirect.
2. **Masked failures — sacct "COMPLETED 0:0" is a LIE for grid sbatches.** The
   `if python …; then render; else echo FAILED; fi` pattern makes a Python crash exit the script
   0 → SLURM reports COMPLETED. A 20-epoch job "COMPLETED" in 4-8 min = it CRASHED. **Real success
   = fat-ckpt count + `<run>/train.log` showing `epoch/step/loss` lines.** The traceback is tee'd
   into `train.log`, never the sbatch's echo.
3. **Sync ALL files of a feature, not just the entrypoints.** phm_n/x0-equiv spans
   `train_lora.py` + `training/diffusion.py` + `models/lora/model.py` (check matching mtime).
   Shipping 2 of 3 → `TypeError: LoRAParametrization.__init__() got an unexpected keyword 'phm_n'`
   in `add_lora` (~4 min in, before first ckpt). Sync the whole interdependent set.
4. **`#SBATCH --ntasks=N` breaks Lightning** → `RuntimeError: You set --ntasks=N … not supported.
   HINT: Use --ntasks-per-node`. Lightning's SLURM plugin rejects a bare `--ntasks`. Use
   `#SBATCH --ntasks-per-node=N` + `srun --nodes=1 --ntasks=N` (the working grids' template).
   This is the per-arm independent-trainer pattern (train_lora falls back to N single-GPU
   trainers under a valid SLURM env).

5. **MIOpen conv-solver HANG on sa3.sif / ROCm 6.2 (job R but frozen, no crash).** After the
   fit-loop starts: `MIOpen(HIP): Warning [IsEnoughWorkspace] … Solver <ConvAsmImplicitGemm…Xdlops…>,
   workspace required: 4194304, provided ptr: 0`, then **nothing** — job R, GPU busy, `train.log`
   mtime frozen 30-40+ min. **Root cause (definitive):** the 6.2 MIOpen gfx90a FindDb has a gap for
   our conv shape; `MIOPEN_FIND_MODE=2` (FAST) on a gap → immediate-mode **AI heuristic** → picks a
   workspace-0 Xdlops solver → hang. **Precision-independent — bf16 AND fp32 both hang** (fp32 is NOT
   a fix; that was a wrong guess). `MIOPEN_DEBUG_CONV_IMMED_FALLBACK=1` also does NOT fix it (another
   wrong guess — it only beat a *different*, local dilated-conv case). **Real fixes, in order:**
   (a) **train on `lumi-multitorch-full` (ROCm 7)** — newer MIOpen, hang doesn't occur, + FA2 (see
   Containers section — this is the right answer); (b) if stuck on sa3.sif, **`MIOPEN_FIND_MODE=1`**
   (NORMAL, real benchmark) or **3** (HYBRID) — never 2. Diagnose vs a true crash: mtime frozen
   >15 min at that MIOpen line = this hang; distinct from #1 (dies ~1s at submit, no data written).

Sanity after any relaunch: a job that stays **R for >10 min** (past the ~4-min crash band) is
NOT automatically training — check `train.log` **mtime is advancing** (mode #5 stays R while
frozen). Only advancing mtime + loss lines = real training.

## Deeper docs

`lumi/README.md` (bring-up, cert/EFP details) · `docs/lumi-throughput-workflow-guide.md`
(HQ pattern rationale) · MASTER §5 (gotcha ledger).
