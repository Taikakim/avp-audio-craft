---
name: lumi-ops
description: Use when working with LUMI/EuroHPC — checking or submitting jobs, writing/debugging sbatch or HyperQueue scripts, transferring files to/from /scratch or /project, diagnosing jobs that "completed" with missing outputs, or crafting ssh/rsync/scp commands for Kim to run against akekim@efp.lumi.csc.fi.
---

# LUMI operations (project_465003186)

> **OWNERSHIP (Kim direct, 2026-08-10): daily LUMI runs move to GHOST-NOTE (G).** Routine
> submit/monitor/pull/render ops are G's lane now (token economy — CONTINUITY stays on heavy
> theory). C/W still craft sbatch/theory-heavy configs; G drives the daily submit→check→pull loop
> and keeps this SKILL current on new issues. This doc is the shared source of truth for both.

## Access model — the #1 rule

**Agents never run ssh/scp/rsync to LUMI themselves.** Kim's key (`~/.ssh/id_EFP`) has an
interactive passphrase; an agent-run command hangs on the prompt, and handling the passphrase
is refused on principle. The working loop:

1. You **craft the exact command** (always `-i ~/.ssh/id_EFP`, host `akekim@efp.lumi.csc.fi`).
2. Kim pastes it in his terminal (or runs `! <cmd>` in-session) and pastes the output back.
3. For transfers: propose `-n` (dry-run) first; the dry-run listing doubles as a remote
   inventory check.

A double passphrase prompt on scp/rsync is normal, not an error.

**`uan18` (or similar) in Kim's prompt is the LOGIN NODE's own hostname, visible only once
he's already SSH'd in — it is NOT a resolvable hostname from his local machine (2026-08-15).**
Any `rsync`/`scp` command targeting LUMI must use `akekim@efp.lumi.csc.fi` and must be run from
Kim's **local** terminal — never pasted into an already-open LUMI session (`ssh: Could not
resolve hostname uan18`/`efp.lumi.csc.fi` from inside `uan18` are both real errors from mixing
up which terminal a command belongs in, not a broken SSH config). If a command you crafted comes
back with a hostname-resolution error, check whether Kim ran it in the right terminal before
assuming the command itself is wrong.

**PASTE SPEC (Kim direct 2026-07-23): every command crafted for Kim must be a SINGLE
LINE.** No backslash continuations, no heredocs, no multi-line loops — pasting those into
his terminal produces `>` continuation prompts and mangles the command. Long pipelines:
join with `&&`/`;` on one line. If a construct genuinely needs multiple lines (rare),
write it to a script file and give Kim a one-line `bash <path>` instead.

**`--export=` is comma-delimited — a comma INSIDE a value silently truncates it (2026-08-15).**
`sbatch --export=ALL,FOO="a, b, c"` looks shell-quoted-safe but isn't: `--export=`'s own
VAR=value-list parser splits on every comma in the whole argument, including ones inside a
quoted value, since the quotes only protected the string from the SHELL, not from sbatch's
internal parsing. Symptom: the value silently truncates at the first comma (`FOO` becomes `"a`
if that's what the script sees, or an empty/garbage tail) — no error, no warning, just a
shorter string than intended. Bit a genre-hint value ("suomisoundi, a finnish variant of
psychedelic trance" → truncated to just "suomisoundi"). **Fix: keep any comma-containing value
OUT of `--export=` entirely — prefix it as a normal env var instead, and let `--export=ALL`
inherit it**: `FOO="a, b, c" sbatch --export=ALL,OTHER=val ... script.sbatch` (the prefix-set
var is in the submitting shell's own environment by the time `--export=ALL` reads it, no comma
parsing involved). Verify by grepping the job's own log for the value it actually printed —
same "trust the artifact, not the launch command" reflex as everything else in this doc.

**The prefix-env-var fix above doesn't fully solve a SPACE-containing value — a second, separate
trap lives inside the sbatch script's own `bash -c '...'` quote-splicing (2026-08-15).** The
common idiom for threading an outer variable into the inner container's single-quoted command —
`export FOO='"${FOO:-}"'` — correctly protects the value from the SBATCH/shell layer, but if the
composed line doesn't ALSO wrap the value in literal quotes, the INNER bash word-splits it on
whitespace when it parses `export FOO=<value with spaces>`. Symptom: `export FOO=a b c` — inner
bash sees `export` with THREE arguments (`FOO=a`, `b`, `c`), assigns only `FOO=a`, and silently
tries (harmlessly) to export bare names `b`/`c`. Same genre-hint value, still truncated, this
time to just the first word, even after the `--export=` fix above. **Real fix: wrap the
interpolated value in literal quotes in the composed output** — `export FOO="'"${FOO}"'"` (note
the doubled quote character right after `FOO=`) — verified locally with `bash -c 'export
FOO="'"${FOO}"'" ; echo "[$FOO]"'` before trusting it on a real job. **More robust than fixing
the quoting by hand: skip env-vars/`--export=` entirely for any multi-word value and read it from
a file instead** — `FOO_FILE=/scratch/.../hint.txt` (a plain path, immune to both traps above),
`FOO=$(cat "${FOO_FILE}")` inside the top-level script (outside any nested quoting), then the
already-fixed splice pattern threads the now-known-good `$FOO` through safely. This is what
`goa_caption.sbatch`'s `GENRE_HINT_FILE` does — the file layer sidesteps the whole quoting class
of bug rather than getting it exactly right by hand.

**Reusing an output directory across two DIFFERENT extraction tools silently zeroes a resumable
run (2026-08-15).** A tool with skip-if-exists resumability (`_pending()`-style: job is "done" if
its output path already exists) can't tell the difference between "I already finished this" and
"something ELSE already wrote a file at this exact path." Ran an ad-hoc converter script into
`suomisoundi_timeseries/`, then pointed the REAL extractor's `--output-dir` at the same directory
— every one of 1260 jobs got silently filtered out of the pending queue before ever reaching a
worker, and because that filtering happens before the done/skipped/failed counters increment, the
job reports `0 written, 0 skipped, 0 failed` (not even a nonzero skip count) despite `Found 1260
track folders` printing correctly. Looks like the tool is broken; it's actually working exactly as
designed against stale data. **Fix: `--overwrite` (or a genuinely fresh output directory) whenever
two different tools/runs might have touched the same output path.** Same underlying lesson as the
`--overwrite` flag existing on nearly every batch tool in this codebase — resumability is a feature
that assumes ONE tool owns that directory, not a safe default across tool changes.

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

## Live-encode + multi-arm training gotchas (multitorch image — all bit #68/ladder 2026-08-04/05)
Five things bit the first `--data_dir` live-encode + fan-out launches; each recurs on ANY such job.

1. **torchaudio has NO torchcodec on the multitorch image → `torchaudio.load` dies.** torchaudio 2.10+rocm7
   delegates load/save to `torchcodec` (absent), and the `backend=` arg is **ignored** (torchcodec-only). So
   any `--data_dir` job that decodes raw mp3/flac crashes at first load; `--encoded_dir` (pre-encoded `.npy`)
   never hits it (no audio decode). **Fix (in-tree): the ffmpeg-subprocess loader in `dataset.py:load_file`**
   (ffmpeg 6.1.1 IS on the image → decode via ffmpeg when torchcodec missing). Do NOT `pip install torchcodec`
   blind — it's ABI-locked to torch + libav, fragile on rocm7 (our history needed source builds; `SAO/torchcodec`).
2. **N independent 1-GCD arms in one SLURM job collide on the DDP port (`EADDRINUSE`).** Lightning derives ONE
   rendezvous port from the shared `SLURM_JOB_ID` → every arm grabs the same one, arm 0 wins, the rest die at
   `TCPStore`. **Fix, per-arm in the container env block: `export SLURM_JOB_NAME=bash`** (→ PL
   `SLURMEnvironment.detect()` returns False → single-process `LightningEnvironment`, no shared port) **+ distinct
   `MASTER_PORT=$((29500+GCD))`** as backup. (First ladder run: only the fp32 arm survived without this.)
3. **A systemic failure surfaces as `RecursionError`, not the real error.** SA3's `LocalDataset.__getitem__`
   recursively retries `self[random_idx]` on load/reject failure — so a bad decoder OR a caption-key mismatch
   flooding `__reject__` recurses thousands deep → a 40k-line `RecursionError` that BURIES the root cause.
   **Read the FIRST traceback, not the recursion tail** (`ln=$(grep -n Traceback log|head -1|cut -d: -f1); sed -n
   "$ln,+40p" log`). We bounded the retry (cap 100 → clean raise) so future gaps fail loud.
4. **Live-encode caption sidecar = relpath-key contract; VERIFY layout before the run.** `--data_dir` +
   `--caption_sidecar` uses `make_data_dir_caption_fn`, keyed by `relpath` **relative to `--data_dir`**, and
   **rejects-on-miss** — a key mismatch silently drops EVERY caption (→ the reject-flood recursion above). Keys
   must match the on-disk layout under `BIGSET_DIR` (the corpus ROOT). Confirm with a definitive **per-path** test
   `ls "$BIGSET_DIR/<one exact sidecar rel key>"` — NOT a broad `find` (Lustre metadata made `find -maxdepth3 -name`
   miss dirs that per-path `ls` resolved). `LocalDataset` reads `${data_dir}/filelist.txt` (entries joined w/ data_dir).

5. **8-GCD DDP + live-encode exhausts `/dev/shm` → `unable to allocate shared memory(shm) … Resource
   temporarily unavailable (11)`.** With `--ntasks-per-node=8` and `--num_workers 6`, that's **48 DataLoader
   workers on one node** passing big decoded-audio tensors through the node's `/dev/shm` (PyTorch's default
   `file_descriptor` sharing). It exhausts mid-training and the run dies (crashed `fullft_bigset` #68 20687866
   after 1 ckpt, 2026-08-06; the SMOKE at `--steps 40` was too short to fill shm, so this slipped past it). The
   `--encoded_dir` ladder arms never hit it (no live decode, fewer ranks). **Fix (in-tree): `train_lora.py` sets
   `torch.multiprocessing.set_sharing_strategy("file_system")`** (shares via `/tmp` files, which the container
   binds, not `/dev/shm`) **+ raise `ulimit -n` in the sbatch before the python call** (file_system opens one fd
   per shared tensor). NB smoke-mode won't catch shm exhaustion — it's a slow fill; watch for it on the first
   real multi-hour DDP live-encode run.

**Standing rule — SMOKE every new live-encode/DDP config first** (`SMOKE=1` → `--steps 40`), then check the .out:
`Found N files` (filelist resolved), steps progressing (captions attaching — a reject-flood would raise), all GCDs
active, **0 `Couldn't load file`**, no OOM. The smoke caught all four above before the ~1-day node run.

## `pre_encode_dataset.py` parallel-shard OOM — UNRESOLVED after 3 fix attempts (2026-08-15)

Running 8 GCD-pinned shards of `pre_encode_dataset.py` on one node (the big-goa preencode,
`preencode_bigset.sbatch`) has OOM'd **three separate times in a row** (`21073662` →
`21148858` → `21149732`), each after a different round of fixes. **Do not assume this is
solved — the root cause is still open.** What's been tried, in order:
1. **Fix 1 (worker-count):** default `num_workers=min(4, cpu_count())` × 8 parallel shards = up
   to 32 DataLoader worker processes decoding audio simultaneously through `/dev/shm` on one
   node → kernel `oom_kill`. Added `torch.multiprocessing.set_sharing_strategy("file_system")`
   (routes IPC via `/tmp`, not `/dev/shm` — same fix as `train_lora.py`'s live-encode shm bug,
   §5 above) + an explicit `--num_workers` CLI flag, ran with `--num_workers 1`. **Resubmitted,
   still OOM'd** (`21148858`) — same kernel oom_kill signature.
2. **Fix 2 (visibility + duration cap):** the retried job's log showed only ONE truncated line at
   the point of the kill, because **Python's stdout is block-buffered when piped/redirected** —
   the real per-file error messages leading up to the OOM were lost, never flushed. Fixed with
   `python -u` (unbuffered). Separately, hypothesized that `goa_archive`'s "VA - ..." DJ-mix/
   compilation folders contain very long tracks, and `_ffmpeg_load`'s
   `subprocess.run(capture_output=True)` buffers the **entire decoded PCM stream** in memory
   before returning (an 80-min stereo f32 decode ≈ 1.7 GB just for the raw buffer; several
   shards each landing on one at once is a real node-RAM mechanism) — added a 30-minute decode
   duration cap to `dataset.py::_ffmpeg_load`. **Resubmitted, still OOM'd** (`21149732`), same
   truncated-line-at-kill signature, different file/shard. The duration-cap theory has **neither
   been confirmed nor refuted** — no clear log evidence of duration-cap rejections either way.
   Manual `ffprobe`/`ffmpeg` CLI tests on the specific reported-failing file (run directly on the
   login node, no job needed) decoded cleanly in isolation — rules out simple file corruption for
   that one file, but doesn't explain the OOM under parallel load.
3. **Not yet tried:** reducing shard parallelism below 8 (fewer simultaneous decodes per node),
   explicit periodic `/proc/self/status VmRSS` logging per shard to see which one balloons and
   when, or reconsidering whether ffmpeg buffering is the right theory at all given the lack of
   confirming log evidence.

**If you pick this up again: don't just resubmit and hope.** Add the RSS-logging instrumentation
BEFORE another blind resubmit — three OOMs on three different fixes means the actual mechanism
still isn't understood, only guessed at.

## Paths (always literal — `$SCRATCH` etc. are NOT set in login shells)

| what | path |
|---|---|
| code tree (mirror of SAO) | `/project/project_465003186/code` — NOT the stray top-level `/project/.../lumi` |
| container / models | `/project/.../containers/sa3.sif`; **`/project/.../models` is a SYMLINK → `/scratch/.../models`** (the real 38G HF hub cache lives on /scratch — see storage note below) |
| runs, renders, latent tarballs | `/scratch/project_465003186/{runs,renders,latents_*.tar.gz}` |
| node-local staging (in-job only) | `/flash/project_465003186` |
| local pull targets | `Mantu/lumi_runs/...` and the `9a410a1d-…` drive (`lumi_runs/runs/...`) — **land pulls where the existing `sa3_lora_runs` symlinks already resolve**; check `readlink` before inventing a new dir |

## Storage / quota — `/project` is TINY (50G) and code-only; models live on /scratch (2026-08-09)
- **`/projappl` (`/project`) hard quota ≈ 50–54G.** It holds only `code/` (~2G) + `containers/` (~15G).
  The HF model cache is **NOT** on /project — `/project/.../models` is a **symlink → `/scratch/.../models`**
  (~38G: `hub/models--stabilityai--{stable-audio-3-medium,-base,SAME-L}`, MuScriptor, music-flamingo, granite).
- **`du -sh /project/.../models/` LIES** — the trailing slash follows the symlink into /scratch and reports
  38G as if it were on /project, which makes /project look wildly over quota. Use `du -sh --exclude=models`
  or `readlink` the path first. The real /project usage is ~18G.
- **`lumi-ldap-projectinfo` block-quota % can be STALE/CACHED** (showed 124.9% / 62G when the live
  `lumi-quota` + `du` said 18G). Confirm with live `lumi-quota` and `du` before "freeing" anything.
- **NEVER `rm`/recreate the `/project/.../models` symlink blind.** If it's ever broken, repoint it at the
  real cache: `ln -s /scratch/project_465003186/models /project/project_465003186/models`. All sbatches use
  `MODELS=${PROJ}/models; export HF_HOME=${MODELS} HF_HUB_OFFLINE=1`, so a wrong/empty target = instant
  model-not-found on every job. (Cost me a scare 2026-08-09: rm'd the symlink, repointed it at an empty
  /flash dir; the /scratch cache was safe, repoint fixed it.)

## Job scripts — start from the proven skeletons, never from scratch

- Multi-arm one-task-per-GCD: `lumi/sbatch/efp_fp32_compare.sbatch` (srun + `SLURM_PROCID` arm table).
- Many short tasks / HQ packing: `lumi/sbatch/native_cells_hq.sbatch` or `fullft_cells_hq.sbatch`
  (post-2026-07-21 fixes) — older templates may still carry the bugs below; diff before reuse.

**Omitting `--epochs` in `train_lora.py` to get "open-ended, no cap" training is a trap
(2026-08-16, cost a 2h40m node allocation with 6/8 arms doing zero work).** The Trainer
construction is `max_steps=(-1 if args.epochs else args.steps)` — an omitted `--epochs`
does NOT mean unlimited, it falls through to `max_steps=args.steps`, and `--steps` defaults
to **10000**. Every arm gets capped at step 10000 regardless of epoch progress; worse, on a
**resumed** run any arm whose checkpoint already sits past step 10000 hits that check
immediately and trains for zero additional steps, silently, for the whole job (looks like a
normal `COMPLETED 0:0` in `sacct` — no error, no warning in the log). **Fix: pass an
explicit large `--epochs` (e.g. `100000`) instead of omitting it** — makes `args.epochs`
truthy (`max_steps=-1`, no step cap) and gives Lightning a concrete `max_epochs` instead of
`None`, which also sidesteps Lightning's own separate "both `max_epochs` and `max_steps`
unset → defaults to `max_epochs=1000`" fallback that an omitted `--epochs` would otherwise
land on ambiguously. **Verify:** after any "open-ended" resume, check that a NEW checkpoint
epoch actually appears past what was resumed from — a `sacct` `COMPLETED` in under an hour
on a job meant to run for the full walltime is the tell.

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
- **⚠️ CORRECTION (2026-08-09, multitorch image) — the "Pattern 1" recipe above OOMs on
  multitorch; use "Pattern 2" instead.** On `lumi-multitorch-full`, `train_lora.py`'s
  `load_model` does `model.to("cuda")` (=`cuda:0`) at line ~130 **before** Lightning
  assigns per-rank devices. With Pattern 1 (all 8 GCDs visible, `--devices 8`, no
  `--gpus-per-task`) **all 8 ranks load the model onto GPU 0 → HIP OOM** in ~3 min (job
  20869819: "GPU 0 … 0 bytes free", 8×~7 GiB piled on one card). **The working recipe on
  multitorch is Pattern 2 — EXACTLY what #68 fullft_bigset uses (8h+ clean):**
  `srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7` + train_lora with **NO
  `--devices`** — cgroup-pins each rank to its own GCD (so `model.to("cuda")` lands on the
  rank's own card), and Lightning's SLURMEnvironment forms the world_size=8 group from
  SLURM_NTASKS. #68 trains fine with **no `-vN` ckpts**, so on multitorch Pattern 2 forms a
  REAL coordinated group (the "Pattern 2 = N duplicate trainers" warning above was sa3.sif
  smoke 20413874; it does NOT hold on multitorch). **Rule: on multitorch, DDP = Pattern 2
  (`--gpus-per-task=1`, no `--devices`).** Templates fixed: `fullft_avp_aug.sbatch`,
  `multinode_ddp_smoke.sbatch`.
- **🔴 CORRECTION (2026-08-15) — "multi-node extends it" above is WRONG. Pattern 2 does NOT
  scale past one node without extra work; do not retry the naive version.** `--nodes=2
  --ntasks-per-node=8 --gpus-per-task=1`, no `--devices`, produces **two independent
  single-node 8-way groups, not one 16-way group** — silent, no crash. Diagnostic: each
  rank's Lightning logger reports its own `v_num` (`grep -h '\[rank:\|v_num' */train_rank*.log`);
  a real single group shows one shared `v_num` across every rank, a split shows **`v_num: 0` on
  node-0 ranks and `v_num: 1` on node-1 ranks** — two independent Trainer instances, each
  thinking it's the whole job. Adding `--devices 8 --num_nodes ${SLURM_NNODES}` to try to force
  it does NOT fix this and fails LOUDER instead: `MisconfigurationException: You requested gpu:
  [0..7] But your machine only has: [0]` — because Pattern 2's cgroup-pinning means every rank's
  process only ever sees **one** GPU (`torch.cuda.device_count()==1`), so telling Lightning
  `--devices 8` fails its own validation. **The fix was not built** (dropped for token budget,
  Kim 2026-08-15) — CSC's own docs (docs.csc.fi/support/tutorials/ml-multi/) prescribe `torchrun
  --nnodes=N --nproc_per_node=8 --rdzv_backend=c10d --rdzv_endpoint=<node0>:<port>` as the
  canonical multi-node launcher instead of raw `srun` + SLURMEnvironment auto-detect. **Until
  someone builds and verifies the torchrun path, treat multi-node SA3 training as unsolved and
  stick to single-node (8 GCD) runs.**
- **🔴 FULL-FT LATENT-SCALE RUNAWAY → SPECTRAL DRONE (2026-08-10, CONTINUITY). Do NOT re-chase
  DDP / live-encode / the decoder for this symptom.** Every multitorch FULL-finetune (#68
  `fullft_bigset`, `precision_ladder` — all FusionOpt) decoded to broadband spectral drone on
  every prompt+cfg. Root cause is NOT DDP (formed one group), NOT live-encode (the pre-encoded
  ladder droned too), NOT the decoder (known-good latents decode fine): the model's **latent
  OUTPUT scale runs away during training**. Measured from the saved `z0.npy` (local analysis, no
  GPU needed): global latent std **0.7 (good) → 1.3 (ep3) → 5.6 (ep7)**; #channels with std>2.0:
  **0 → ~4 → 166 of 256**; cfg16 inflates first (early-warning canary). Mechanism: FusionOpt's
  **`spectral_wd` defaults to 0.01** (`fusion_groups.py`), which is **too weak for the NS5/Muon
  orthogonalized update** (its step-norm is grad-magnitude-independent, so decay must be ~10×
  AdamW's) → weight norms, hence latent scale, grow unbounded. Adapters stay bounded (frozen base +
  tiny delta) → this is a **full-FT-only** failure. **FIX: pass `--weight_decay 0.1
  --gradient_clip_val 1.0`** to the full-FT (routes to `param_groups.spectral_wd`; the FusionOpt
  *constructor* `weight_decay` is OVERRIDDEN by the per-group value, so setting it there is a
  no-op — the group knob is the only one that works). **DIAGNOSE ANY future drone by loading the
  `z0.npy` and checking global std vs ~1.0 BEFORE suspecting anything else.** Deterministic
  mechanism test: `stable-audio-tools/tests/test_fusion_weight_decay.py`. A/B in flight (job
  20940322): `lumi/sbatch/fullft_wd_ab.sbatch`. NOTE this means #68/#69 as trained are dead — they
  must be relaunched with the fix once the A/B confirms.
- **🔴 `--use-ema` full-FT OOMs at batch sizes that "look small enough" on paper — the only
  proven-safe pattern is `batch_size=2` + `accumulate_grad_batches=N`, never a larger raw
  `--batch_size` (2026-08-15).** EMA holds a **second full-precision copy of the whole trainable
  model** (`SimpleEMA`/`diffusion_ema.ema_model.*`) alongside the training model — fixed memory
  overhead that doesn't scale down just because you picked a smaller batch or shorter sequence.
  Two separate EMA+full-FT jobs OOM'd this way in one night: `21148122` (AVP, T1024, `--batch_size
  8`, bf16) and, after the first OOM should have been generalized but wasn't, `21148584` (goa K20,
  T1024, `--batch_size 4` default, fp32) — confirming the failure is systematic to
  EMA-full-FT-any-nontrivial-batch, not one bad config. The only config that survived a full night
  of EMA+full-FT runs was `fullft_mixed_avp_goa_t4096.sbatch`'s **`--batch_size 2
  --accumulate_grad_batches 2`** (effective batch 4, T4096, bf16) — the exact pattern already
  proven earlier at `efp_fullft_t4096.sbatch`. **Rule: for any full-FT run with `--use-ema`, set
  `--batch_size 2` and reach your target effective batch via `--accumulate_grad_batches`, never by
  raising `--batch_size` directly** — even a config that "should" fit (shorter T, lower precision)
  is not evidence it will, until it's actually run to a checkpoint past the point the OOM'd runs
  died. `fullft_avp_aug.sbatch` and `subloss_goa_k20_fullft.sbatch` both now default to this
  pattern (`GA=` var wired to `--accumulate_grad_batches`, echoed in the startup config line).
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
  assert the critical package's `__file__` is NOT under /opt/venv.
  **COROLLARY (2026-08-17, ckpt_dup_delta.sbatch): the OVERLAY VENV DOESN'T HAVE torch (or
  probably anything heavy) IN ITS OWN site-packages — it relies on `/opt/venv`'s baseline
  PYTHONPATH (already set by the container, present even with NO manual PYTHONPATH export) for
  torch via system-site-packages inheritance.** So `export PYTHONPATH=$VENV/lib/.../site-packages`
  with NO `${PYTHONPATH:+:$PYTHONPATH}` suffix — i.e. REPLACING instead of appending — silently
  drops `/opt/venv` and produces `ModuleNotFoundError: No module named 'torch'`, not a wrong
  version. Confirmed via a diagnostic probe comparing `sys.path` with vs without the override.
  **Never write a bare `export PYTHONPATH=...` after activating this venv — always append.**
  Related: the READABLE
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
- **`VAR=val sbatch script.sh` env-var overrides give ZERO submit-time confirmation they
  landed** (2026-08-15, Kim: "I'm not sure if all of the arguments got passed" — a fair worry,
  `Submitted batch job N` tells you nothing about what config it's actually running). The
  mechanism itself is standard/reliable (sbatch defaults to `--export=ALL`, forwarding its own
  process env — which the bash prefix-assignment sets — to the job), but there's no built-in
  echo of it. **Every sbatch MUST echo its fully-resolved config (every overridable var, one
  line, near the top, before the srun)** so `tail`/`grep` on the `.out` is a real answer, not a
  guess — `fullft_avp_aug.sbatch`'s `echo "[avp-aug] BS=... WARMUP_FRAC=${WARMUP_FRAC:-off} ..."`
  is the pattern (note the `:-off`/`:-none` fallback on optional vars — an unset var still prints
  something, doesn't just vanish from the line). Check it FIRST, before waiting on training
  progress, whenever an override-heavy submit feels uncertain.

- **Sanity-checking a job that's still running (2026-08-15) — three checks, not "did it crash".**
  Kim will periodically ask "has it exploded" for a multi-hour training job; this is the recipe:
  1. **Checkpoint existence/freshness**: `ls -la <run>/*.ckpt` — but if the RUN dir was reused
     across a resubmit (same RUNTAG/NAME as a prior OOM'd job), an OLD checkpoint sitting there
     from BEFORE the resubmit will be auto-resumed and can look like suspiciously fast progress.
     Compare the ckpt mtime against the job's actual submit/start time before trusting it.
  2. **NaN/Inf loss — grep, but check the matches, don't trust a hit count.** `grep -Ein "nan|inf"
     <run>/train_rank0.log` throws false positives: the substrings "inf" and "nan" appear inside
     ordinary words — **"inference"** (from the ROCm profile warning that's in every log) and
     **"reinforce"** (a word that shows up in generated captions) both match `inf` with a bare
     substring grep. Read the matched lines, don't just count them.
  3. **DDP group health**: `grep -h "\[rank:\|v_num" <run>/train_rank*.log | sort -u` — for a
     healthy single N-way group you see each rank number (0..N-1) exactly once, no repeats. Rank
     numbers repeating (e.g. two separate `rank: 0` blocks) is the split-group signature from the
     multi-node section above. Also cross-check against `epoch=*-v[0-9]*.ckpt` (§ Job scripts
     above) — duplicate-versioned checkpoints at the SAME step are the other tell of uncoordinated
     writers, though (confirmed 2026-08-15) they can also occur even with a verified-healthy
     single group, apparently from the checkpoint callback re-firing — a real but lower-severity
     wasted-disk issue, not automatically proof of a split.

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
- **Never put a brace-expansion `{a,b}` in an rsync DESTINATION** (2026-08-15). The LOCAL bash
  shell expands `dest/{scripts,stable_audio_3}/` into TWO separate arguments before rsync ever
  sees them — and rsync's rule is "every arg except the last is a source." The intended
  destination silently becomes an extra bogus SOURCE, and the real destination shrinks to just
  the last brace element. Symptom: `sent N bytes` looks like success, but the file you actually
  needed (e.g. `train_lora.py`) never lands where you think — a sbatch's own code-freshness
  guard (`grep -q -- "--flag" .../train_lora.py || FATAL`) is what caught it, not the rsync
  output itself. Use one rsync command per destination directory, no braces, ever.
- Conditional pulls: epoch-range include patterns make rsync self-answering — the dry-run
  listing shows exactly what exists remotely (e.g. "did this run reach ep7?").
- A fat `epoch=N.ckpt` (vs slim `.weights.ckpt`) marks a run's **terminal** epoch; pull fat only
  for the last epoch (Kim's standing rule), slims elsewhere.
- **ALL rendered cells → ALWAYS pulled local, NO EXCEPTION (Kim direct 2026-08-07).** Every
  `renders/matrix_cells/*.wav` on LUMI scratch must be mirrored to the UUID drive
  `lumi_runs/renders/matrix_cells/`. `rsync -av --partial <scratch>/renders/matrix_cells/ <local>/`
  is incremental — re-run it freely; do it after EVERY render job and definitely before the purge
  ([[lumi-project-purge-deadline]]). Cells feed the board + every audio metric (hook_melodic_ratio,
  melody_wall, clip_metrics); a cell left only on scratch is a lost audition. Distinct from the ckpt
  rule above — ckpts are last-fat-only, **cells are ALL**.

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

5. **`sbatch: error: Unable to open file <script>` = wrong cwd, not a broken script (2026-08-15).**
   `sbatch <relative-path>.sbatch` resolves relative to the CURRENT directory — if Kim's shell is
   sitting in `/scratch/.../renders/lumi` (from a previous `cd`) instead of
   `/project/.../code`, the same relative path that worked minutes earlier now 404s. Fix: `cd
   /project/project_465003186/code && sbatch lumi/sbatch/<script>.sbatch` — prefix every submit
   command with the `cd` so it's cwd-independent, don't assume the shell is still where it was.
6. **MIOpen conv-solver HANG on sa3.sif / ROCm 6.2 (job R but frozen, no crash).** After the
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

## Official LUMI docs review (G, 2026-08-10 — Kim's reading list on the ownership handoff)

Reviewed docs.lumi-supercomputer.eu's install/storage/runjobs sections against our actual setup.
Most of it confirms current practice; four items are new and worth acting on.

- **NO BACKUPS, ANYWHERE, EVER — not a LUMI service.** Every storage tier (`/users`, `/project`,
  `/scratch`, `/flash`) has **zero backup**. After a project allocation ends, data stays
  **read-only for 90 days**, then is **permanently deleted**. This is the concrete deadline behind
  the "14 days left" budget conversation this week: whatever we want to keep past the project's
  end (final checkpoints, key renders, the melody-subspace artifacts, anything not already mirrored
  to Mantu/the UUID drive) needs an explicit pull plan, not an assumption that LUMI is safe storage
  even briefly after the project closes. Worth a standing checklist item once the end date is known.
- **Quotas, confirmed with real numbers** (was previously reconstructed from a stale-reading
  dispute, see the 08-09 WINTERMUTE/CONTINUITY exchange): home 20 GB/100k inodes; `/project` 50 GB
  (→500 GB) / 100k inodes, billed 1×; `/scratch` 50 TB (→500 TB) / 2M inodes, billed 1×; `/flash`
  2 TB (→100 TB) / 1M inodes, billed **3×** (matches our `--mem=0`/`$FLASH` node-local-staging-only
  convention — never park anything long-lived there).
- **CLI ARGUMENTS ARE VISIBLE TO OTHER USERS on shared LUMI nodes** (via `squeue`/`sacct`'s full
  submit command, and directly to anyone else on the same node). Audited our 54 `lumi/sbatch/*`
  scripts: **clean, zero CLI-passed secrets found** (everything sensitive already rides env vars
  — `HF_HOME`, etc.). Keep it that way for the wandb wiring (task below): API key via env
  (`WANDB_API_KEY` exported, or `wandb login` against a pre-staged `~/.netrc`-style credential
  file), never `--api-key` on a command line.
- **Auto-requeue — RECONCILED (2026-08-11) against the official LUMI batch-jobs page + Kim's
  operational experience: both are correct, they're about different failure modes.** The docs
  page states plainly: "The LUMI Slurm configuration has automatic requeuing of jobs upon node
  failure enabled" — same job ID, same-run resubmit, truncated output by default unless
  `--open-mode=append`. But that trigger is specifically **node hardware failure** (the compute
  node itself going down/unresponsive), NOT an application-level crash on an otherwise-healthy
  node. Kim's read ("failed jobs just fail") and C's two confirmed incidents — the OOM crash
  (`20869819`) and the shm-exhaustion crash (`20687866`), both application-level, neither a node
  failure — are exactly the case requeue does NOT cover, so all three observations are consistent
  once the trigger is understood correctly. **Net for us: requeue is a real, live safety net for
  the failure mode we've never hit (hardware), and inert for the ones we actually hit (OOM,
  asserts, non-zero exit) — so it's not "not an active risk," it's an active-but-narrow one.**
  ACTIONABLE gap this reopens: our multi-hour/multi-arm training sbatch scripts (`fullft_reg_ab`,
  `fullft_avp_regsweep`, `fullft_avp_surgical`, etc.) have none of `--no-requeue` set, none are
  checkpoint/resume-safe against a fresh from-scratch restart (SUBSET mode does `rm -rf` staging,
  RUN dirs assume a clean start), and their `--output=%x-%j.out` naming would silently truncate
  on a genuine node-failure requeue. A rare hardware fault mid-run on an expensive 8-GCD/24h job
  would currently either restart wastefully from zero or (with truncated output) restart
  invisibly. Worth adding `--no-requeue` (fail cleanly, let a human/agent decide whether to
  relaunch) or at minimum `--open-mode=append` to the long training templates — cheap either way.
  Also confirmed in the same doc read: `--gpus-per-task` is a real, first-class Slurm option (not
  a made-up flag) — validates C's 2026-08-11 GCD-pinning fix (`srun --ntasks=8 --gpus-per-task=1`)
  as the documented pattern, not a workaround.

Confirms current practice needs no change:
- **cotainr-built Singularity containers is the officially recommended path** (LUMI explicitly
  discourages direct conda/pip on any LUMI filesystem — "tens to hundreds of thousands of small
  files" strains Lustre metadata servers exactly the way our venv-overlay-inside-a-SIF pattern
  avoids). The **container-wrapper tool is explicitly NOT recommended for conda/pip management**
  (it wraps single binaries transparently; bulk package installs still want a rebuilt container) —
  so no reason to adopt it for anything we currently do with venv overlays.
- **56 usable cores per LUMI-G node, not 64** (low-noise mode reserves 1 + disables 1 per L3
  region) — explains, after the fact, why `--cpus-per-task=7 × 8 GCDs = 56` in our sbatch
  templates already lands exactly on the real ceiling.
- Official Python/MPI guidance is `srun singularity exec $CONTAINER python3 ...` (never
  `mpirun`/`mpiexec` under a container) — matches our `srun --ntasks=N ... singularity exec`
  pattern throughout `lumi/sbatch/`.
- LUMI-F (flash, 8 PB / 1740 GB/s aggregate) vs LUMI-P (20 PB ×4 / 240 GB/s each, spinning disk,
  optimized for large sequential I/O not many-small-files) — matches why we stage hot datasets to
  `$FLASH` for the duration of a job rather than reading crops directly off `$SCRATCH`.

Checked against real practice, mostly moot for us (C, 08-10):
- **Lustre striping** (`lfs setstripe --stripe-count 1 --stripe-size 1m <dir>`) is the textbook-
  correct tuning for a file-per-process many-small-files read pattern, which our per-crop latent
  dirs are — **but it doesn't apply to how we actually train**: latents are tarred once, extracted
  to `$FLASH` (node-local NVMe) at job start, and the per-crop random reads during training hit
  `$FLASH`, not Lustre. The only Lustre read is the single big sequential tar pull. Striping would
  only pay off if a future job ever reads latents directly off `$SCRATCH` without the `$FLASH`
  staging step — conditional, not an active win, don't spend effort on it under the current
  pipeline.

## Wandb: offline-on-LUMI → sync-at-home (G, 2026-08-10)

`train_lora.py --logger wandb` is already wired (`WandbLogger(project=args.name)`, no CLI
API-key flag — good, matches the CLI-args-are-visible-to-others rule above). Compute nodes have
no internet, so:

1. **On LUMI, every training arm exports `WANDB_MODE=offline` and a `WANDB_DIR` pointing inside
   its own `$SCRATCH` run dir** (never `$FLASH` — that's node-local/ephemeral). Zero network
   calls, zero credential ever touches LUMI. Pattern: `lumi/sbatch/fullft_reg_ab.sbatch`
   (`LOGGER=${LOGGER:-wandb}`, override-able back to `csv` for non-wandb reuse).
2. **Pull the run dir home** the normal way (rsync `$SCRATCH/runs/<run>/` → local mirror) — the
   wandb files ride along inside `<run_dir>/wandb/offline-run-*`.
3. **Sync locally**, where we already have a wandb login and real internet:
   `wandb sync <pulled_run_dir>/wandb/offline-run-*` (once per arm/run dir). This uploads the
   offline run to the actual wandb.ai project; from then on it's a normal synced run, visible
   on the site same as any other.
4. Not yet verified: whether LUMI **login** nodes (as opposed to compute nodes) have outbound
   internet, which would let `wandb sync` run there directly and skip step 3's local step. Untested
   — the offline→local-sync path above works regardless, so it wasn't a blocker; worth checking
   if syncing 8-arm batches locally becomes a bottleneck.

## Deeper docs

`lumi/README.md` (bring-up, cert/EFP details) · `docs/lumi-throughput-workflow-guide.md`
(HQ pattern rationale) · MASTER §5 (gotcha ledger).
