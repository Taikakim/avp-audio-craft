# Lessons learned — mistakes to not repeat

Cross-project, with the *reasoning* so they don't get re-litigated. The terse
list is MASTER §5; this is the explained version.

## Environment / venv

- **Wrong mir python.** `mir/.venv` lacks essentia and silently degrades madmom→librosa,
  so features come out subtly wrong with no error. Use `mir/bin/python`.
- **Three Python versions can't share a venv** (3.10/3.12/3.13). Name the venv by absolute
  path in every command; never trust bare `python`.
- **Stale `rocm_env.sh` shell env.** The YAML applies via `setdefault`, so a terminal with
  old exports silently pins wrong tunings dir / inference profile (disabling tuning even in
  training). Check `env | grep -iE 'tunableop|miopen|triton'` first when perf looks off.
- **Tunings dir is torch-version-specific.** `~/pytorch-tunings-7.2.3` is for torch 2.10;
  the `-7.2.2` CSV fails TunableOp's `PT_VERSION` validator under 2.10 and silently no-ops.
- **SA3 deps not in pyproject:** `dill`, `pytorch-lightning`, `wandb` had to be pip-installed
  into `.venv` for the trainer. `uv sync` (without `--inexact`) strips hand-installed pkgs.

## ROCm / kernels

- **`MIOPEN_FIND_MODE=6` crashes SA3 medium's DiT** — MIOpen `std::vector` assertion →
  coredump. (Fine for the tiny LatCH heads; it's a large-conv-shape issue.) Use mode 2 for
  SA3 medium. The yaml's "training profile" default of 6 is wrong for this model.
- **batch=1 variable-length → kernel-cache thrash.** Every unique sequence length is a new
  GEMM/Triton shape; the autotuner never settles. Fix: fixed T=4096 crops
  (`training-findings.md` has the full chain). Don't pad short tracks — that's just another
  shape; drop them.
- **A coredump cascades.** Killing a crashed multi-GB GPU process triggers `systemd-coredump`
  to write a multi-GB dump → load average spikes to 40+, other apps get OOM-killed. If a
  GPU job dies hard, `sudo coredumpctl` / clear `/var/lib/systemd/coredump` and consider
  masking coredumps during heavy GPU work.
- **fp16 NS5 diverges** (FusionOpt); **fp16_safe** (rescale+fp32 accum) is half the speed of
  bf16 for ~0.5 % quality. **bf16 is the hot-dtype.** (LATCH_RESULTS §20D/E.)
- **INT8/INT4 quant is non-functional on ROCm.** Use bf16 + FA2.
- **Flash-Attention is built but INACTIVE by default on the torch-2.10/2.12 ROCm venvs.** The
  CK `flash_attn 2.8.4` wrapper auto-routes to the `aiter` Triton path unless
  `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` is exported *before* `import torch` — forgetting it
  logs `No module named 'aiter'` + disables FA → SDPA/flex fallback, **30–100% slower**. Set it on
  every train and inference run (`sat-venv`, `stable-audio-3/.venv`, `sa3-rocm7.13-test`). mir's
  own rocm-7.2 venv is the exception: it runs Triton FA2 with `=TRUE`. (`docs/flash-attn-ck-rdna4.md`.)
- **TunableOp freezes on RDNA4 + torch-2.12.** Pointing it at the `pytorch-tunings-7.14` cache hangs
  the kernel-selection path (trips even when the validator *passes*); set
  `PYTORCH_TUNABLEOP_ENABLED=0` + `MIOPEN_FIND_MODE=2` (with CK FA, GEMM tuning is marginal anyway).
  This is the torch-2.12 case — distinct from the torch-2.10 tunings-dir lesson above, where tuning
  is wanted.

## Audio I/O

- **Audio writers CLIP fp16 / out-of-range floats.** `torchaudio.save` (especially the new
  torchcodec backend) and most WAV writers expect samples in [-1, 1]; feeding fp16 or SA3's raw
  >1.0 peaks clips/distorts (this bit the riffer auditions). Always **float32 → peak-normalize (or
  clamp) → int16 PCM** before writing. Use the shared helper `sa3_control.audio_io.save_audio()`,
  never `torchaudio.save(x.float().cpu(), …)` raw.

## Data / latents

- **Two incompatible latent grids.** SAO-Small/SA1 = 64-dim @ 21.53 Hz (T=256). SA3 = 256-dim
  @ 10.767 Hz (T=4096, SAME-L encoder). They are different VAEs; never feed one model the
  other's latents. Both dirs are confusingly called `latents*` on Lehto.
- **Stale paths in old memories.** `Mantu/.../Goa_Separated_crops`, `Lehto/goa-small`,
  `Lehto/goa-stems` are **gone**. Verify paths against the filesystem; MASTER §2 is current.
- **Removable drives.** Mantu + Lehto unmount; a 404 means unmounted, not deleted. Work stalls.
- **Don't train off Lehto's removable `latents_sa3`.** Cold random reads off the removable drive
  crawl (~2 MB/s) and were one cause of the SA3 control-adapter step-0 hang. Use the non-removable
  NVMe mirror `/home/kim/Projects/latents_sa3` (13 G, complete copy) for throughput-bound work;
  Lehto stays the canonical copy.
- **The encoder default `sample_size` (~285 s) silently crops long tracks** and picks one
  random window — throws away ~38 % of a median track. Use beat-aligned chunking to T=4096.
- **A hinting mechanism that DEFAULTS TO EMPTY records its own absence — check, don't assume.**
  `goa_caption_task.py` writes a `genre_hint` field into every caption JSON, and MF genre
  accuracy tracks it almost perfectly: suomisoundi (real hint) 97.4% goa/psy in its MF-prose
  tier vs the goa big-set (hint defaulted to empty/None) at 1.2% — MF guessed techno/industrial
  for a 23,231-track goa corpus with no anchor (W's genre-scan + C's `genre_hint` check,
  2026-08-18, cost two running LUMI jobs killed mid-flight). **Before trusting any caption
  tier's genre content, check whether `genre_hint`/`GENRE_HINT_FILE` was actually populated for
  that corpus** — a capability that exists, defaults off, and silently records its own state is
  exactly the shape that goes unnoticed for months. A second, richer per-track hint path already
  exists and was never wired to this captioner: `mir/`'s `pipeline.py:154 _interpolate_genres()`
  (weighted Essentia genre distribution + ID3 metadata) — `lumi/goa_caption_task.py` is a
  separate code path that never calls it.

## Training methodology

- **Don't compare val_median across different loss settings.** Convert to raw MAE first;
  `--standardize`/`huber_beta` change the units (§18 "347 % regression" was a unit artifact).
- **Subset ≤ 0.3 rankings are noise.** Cross-seed std at 30 % data > the entire optimizer
  spread. Use ≥0.6 (ideally full) for production decisions; subsets for coarse screening only.
- **Demos fire at step 1** regardless of `--demo_every` (the `(step-1) % every == 0`
  condition), and each is ~10 min. Disable for short/tuning runs.
- **Guidance must run fp32 on SA3** — TFG backprops through model+head; SA3's default fp16
  clashes with grad dtypes.
- **TunableOp/torch.compile autotune on the FIRST step** of a new shape — that step can take
  20+ min. Don't set a tight timeout and conclude it hung.

## Attributing uncommitted work (the three-leg search)

*(C + W, 2026-09-01, after a 16-file multi-author diff in `stable-audio-3` had to be split
by author before anyone could commit. Six of those files came back to CONTINUITY after
being filed as "not mine" or "nobody wrote it down".)*

**THE PREMISE: git cannot answer authorship in this repo AT ALL, committed or not.**
Every instance commits under Kim's `git user.name`, so **all 200 of the last 200 commits
are authored "Kim <kim.ake@gmail.com>" — one distinct author name across the entire
history** (verified 2026-09-01). `git blame`, `git log --format=%an` and every tool built
on them cannot distinguish CONTINUITY from WINTERMUTE from GHOST-NOTE from THE-FINN, even
for work that landed months ago. Uncommitted work is worse still — no author field exists
at all.

So authorship lives ONLY in what someone wrote about the work at the time: WORKLOG,
journals, the dialogue log, specs, and comments in the code itself. Attribution is
therefore a SEARCH problem over prose, and the search's namespace is the whole game. That
is why the three legs below exist; it is not a workaround for a missing commit, it is the
only instrument there is.

**Run all three legs. They are complementary, not ranked substitutes.**

1. **File basename in the logs.** Weakest. Blind to anything ever discussed by another
   name — which is most work. On the last three files of the SA3 split it returned nothing
   at all.
2. **Spec/paper/doc references INSIDE the diff**, then attribute the SPEC. Grep the diff
   for spec filenames, arXiv ids, `docs/` paths; open what it cites and read the owner
   line. Found a four-file PHM adapter unit whose only trace was a code comment reading
   `spec E2, 2026-07-31-reality-structured-model-experiments` — and that spec's header
   names its owner. Specced work is NEVER discussed by filename in the channel; it is
   discussed by spec name, so leg 1 cannot see it by construction.
3. **The SYMBOLS the diff introduces** — env vars, class names, constants, flag names —
   grepped across the logs, **preferring `WORKLOG.md` hits**. Strongest. A new symbol is
   coined once, by its author, and survives in whatever they wrote about the work.
   `SA3_ENABLE_CROSS_ATTN_MASK` resolved a two-file coupled change in one query after legs
   1 and 2 both returned nothing.

**Leg 3 works because of a DOCUMENTATION HABIT, not because of git.** `WORKLOG.md` entries
carry an explicit `(handle)` author tag; dialogue entries do not. That tag was adopted for
readability and turns out to be the only authorship record that exists for uncommitted
work. **Do not "clean it up".**

### Two confounds that will recur

- **Policy origin is not code authorship.** A guard that enforces someone's rule looks like
  their code. `sa3_encode_from_manifest.py`'s pristine-corpus guard pointed at WINTERMUTE
  for three rounds because W originated the "latents_sa3 stays pristine" constraint on
  07-04. W ruled themselves out twice from their own records before the real author was
  found.
- **A date in a comment is not an authorship date.** A comment reading "2026-07-15 POOL
  item, closed 2026-07-22" was read as evidence of a different author; the file was in fact
  the reader's own work, proven by a DM review from 07-22 approving it. Dates say when, not
  who.

### The prior that matters

**When the search comes back empty on a file, that is evidence the search cannot see the
link — not evidence the work is unowned.** Every "orphan" in the SA3 split had an owner.
The failure mode is not over-disowning by any individual; it is that **the instrument
searched the wrong namespace**, and both agents running it had the same blind spot.

Publish CONFIDENCE, not verdicts. The claim-map that resolved this labelled each row
strong / weak / no-evidence and stated its own method's limits; that is what made the gaps
findable within minutes. A map asserting owners would have committed six files to the wrong
people silently.

### Splitting a mixed file when `git add -p` is unavailable

Interactive git flags are blocked in this environment, and mixing can be **intra-hunk** —
`lora/model.py` had one hunk containing both a dict-mutation fix and a `try/except
AdapterShapeError` whose exception class exists only in the *other* author's uncommitted
diff. Staging that hunk whole would have committed a reference to a class that is not
there, and it would have compiled clean, because the name only resolves at call time.

**The recipes — hunk-level patch surgery, sub-hunk blob surgery, and how to verify the
STAGED blob — live in `docs/GIT-PROTOCOL.md` §5**, together with the rest of the
operational git rules (identity, push targets, the never-commit list). Kept in one place
so the two copies cannot drift; this file keeps the analysis, that one keeps the commands.

## Process / coordination

- **Git authorship in this repo is not evidence of who did the work.** Every agent commit
  shows author "Kim" — it's his `git user.name` on the machine, so `git log --format=%an`
  cannot distinguish who wrote anything. The only reliable attribution is the
  `Co-Authored-By` trailer, the `Claude-Session` line, and the chat record. Cost: a
  status doc attributed a commit to Kim by reading the author field; it was actually C's
  (C's correction, 2026-08-18). Check the trailer, not the author, before crediting anyone.
  **Fixed at the source 2026-09-01: commit via `Misc/agent_commit.sh <HANDLE> …`, which
  sets the AUTHOR to your handle and leaves the committer as Kim.** It is easy to forget —
  the nine commits made the day it was adopted all landed as "Kim" anyway. Verify with
  `git log -5 --format='%h %an %s'`; `--oneline` hides the author field. See
  `docs/GIT-PROTOCOL.md` §2.
- **Per-project Claude memory is siloed by cwd** — a fact learned in one repo is invisible in
  another. That's why this `docs/` + `MASTER.md` layer exists. Put cross-cutting findings here.
- **Branch drift.** Trained checkpoints can require model code that only exists on a feature
  branch (e.g. adaln_zero LatCH was on `latch-rms-control` while `main` lagged → loaders
  failed). Note merges in `WORKLOG.md`.
- **Branch switches wipe untracked work.** `git switch` on a repo with untracked scripts/
  renders can lose them (recoverable via `git stash` trees if you're lucky). Commit or stash
  before switching.
- **One GPU, multiple instances.** A long GPU job holds VRAM (the SA3 encode held 14/16 GB)
  and hard-blocks parallel work. Encodes are resumable (skip-existing) → cheap to pause.
  Note GPU-holding jobs in `WORKLOG.md`.
- **A derivative does not know its source changed.** Sidecars built from captions, captions
  built from audio, eval aggregates built from manifests — each one silently keeps serving
  stale content while the upstream looks fresh, because nothing compares build-time-of-derivative
  against mtime-of-source. Hit twice in two days (2026-08-18): the dora-table page reading a
  stale `clap_dora_aggregate.csv`, and a goa caption sidecar that kept serving pre-fix Granite
  text because regenerating the captions never rebuilt the sidecar from them — an audit run
  against the stale sidecar read as "the fix failed" when the fix had actually worked. **The
  cheap general fix is printing/checking timestamps at build time**, not per-incident patching:
  `build_goa_archive_sidecar.py` now prints the newest mtime of each input tier so mixed
  freshness is visible where it's actionable (commit `83936a1`). Before trusting ANY derived
  artifact (sidecar, aggregate, index, cache), ask whether it has a build-time-vs-source-mtime
  check — if not, assume it can be stale and verify by hand.
