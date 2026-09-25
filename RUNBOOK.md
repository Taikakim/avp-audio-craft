# RUNBOOK — the operator manual

**Audience: Kim, running the machine himself, with no agent in the loop.** Every routine operation,
as a copy-pasteable command with its cwd, its venv, the env vars that must be exported first, how long
it should take, and — the important part — **how to tell it actually worked.**

*Why this file exists (Kim direct 2026-09-08): the token budget runs out by mid-week, and an
agent-only operating path means the lab stops when it does. It must not. The fleet's job is now to
document the scaffolding and hand over ready-to-run tasks. Standing rules: `CLAUDE.md` §8, `MASTER.md` §8.*

**For agents:** when you change a script's interface, or find a command here is wrong, **fix it in the
same session**. A stale runbook costs the operator his time instead of yours. Link to a section here
from `KIM-TASKLIST.md` rather than retyping an invocation.

---

## The three rules that make everything else work

1. **VERIFY THE ARTIFACT, NEVER THE EXIT CODE.** This is not pedantry, it is our most expensive
   recurring bug. Renders segfault in ROCm teardown *after* writing every file (rc=134/139 on both
   good scoring runs this codebase has ever had). `sbatch` returns 0 for jobs whose tasks OOM'd.
   `echo "$(date): rc=$?"` prints rc=0 for a crashed process, because the `$(date)` runs first and
   resets `$?`. So: **count the files.** Every section below ends with a VERIFY line — that line is
   the answer to "did it work", not the terminal's silence.
2. **Invoke every venv by absolute path.** Three Python versions (3.10 / 3.12 / 3.13) that cannot be
   merged. `python` is essentially never the one you want.
3. **Your handle is `KIM`.** Verified working for `filelock.py` and `gpu_guard.sh` — they accept any
   string. The one exception is `Misc/agent_commit.sh`, which hard-rejects `KIM` by design; you do not
   need it (see §13).

## Which venv

| Task | Interpreter |
|---|---|
| SA3 train / render / inference / pre-encode — **default** | `/home/kim/Projects/SAO/.venv/bin/python` |
| SA3, stable reference (7.2.3 — what the old eval corpus was rendered on) | `/home/kim/Projects/SAO/stable-audio-3/.venv/bin/python` |
| MIR features, Audiobox scoring, essentia | `/home/kim/Projects/mir/mir/bin/python` |
| LatCH heads (SAO-Small), FusionOpt, CLAP | `/home/kim/Projects/SAO/stable-audio-tools/sat-venv/bin/python` |
| The explorer Dash app | `/home/kim/Projects/mir/mir/bin/python` (note: `mir/bin/python` does **not** exist) |

Before any SA3 GPU work, in the same shell:

```bash
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE     # MUST precede `import torch`; without it, 30-100% slower
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
```

`MIOPEN_FIND_MODE=6` **crashes** the SA3-medium DiT. TunableOp **freezes** on RDNA4. Never set
`HIP_VISIBLE_DEVICES=""` — flash_attn probes a Triton driver at import and crashes with zero devices.

---

## 1. The GPU lock

One 16 GB card, shared with the desktop. Two concurrent jobs crashed the box twice in one night.

```bash
cd /home/kim/Projects/SAO
Misc/gpu_guard.sh who                                   # who holds it, and can they yield?
Misc/gpu_guard.sh acquire KIM $$ || echo "BUSY - do not start"
Misc/gpu_guard.sh release KIM
```

For something resident that you can stop on request (a server), announce it as yieldable:

```bash
KIND=server NOTE="render server on :8056, ask me to yield" Misc/gpu_guard.sh acquire KIM $$
```

- `kind=server` ⇒ someone waiting knows to ask you. `kind=batch` (default) ⇒ they wait it out.
- **An empty or absent lockfile does not mean the card is free.** `rocm-smi --showpids` is ground
  truth; the lock is a *claim*. A 6-hour job once held the card with an empty lockfile.
- Pass `$$` so the lock records your shell's pid, not the transient helper's.
- **After a `nohup`/background launch the launching shell exits** — re-point the lock at the real pid,
  or the next person sees a dead holder and takes the card out from under your job.

VERIFY: `Misc/gpu_guard.sh who` lists your pid as ALIVE.

---

## 2. Launch a LoRA / DoRA training run

```bash
cd /home/kim/Projects/SAO/stable-audio-3
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
cd /home/kim/Projects/SAO && Misc/gpu_guard.sh acquire KIM $$ || exit 1
cd /home/kim/Projects/SAO/stable-audio-3

LABEL=my_run_2026-09-08
/home/kim/Projects/SAO/.venv/bin/python scripts/train_lora.py --model medium-base \
  --encoded_dir /home/kim/Projects/latents_sa3 --beat-aware-crop --frames 512 \
  --adapter_type dora-rows --rank 16 --lora_alpha 16 --base_precision bf16 \
  --optimizer adamw --lr 1e-4 --batch_size 1 --accumulate_grad_batches 4 \
  --epochs 40 --checkpoint_every_epochs 1 --gradient_clip_val 1.0 --no_demos \
  --num_workers 6 --seed 42 --logger csv \
  --save_dir /run/media/kim/Mantu/sa3_lora_runs/$LABEL --name $LABEL
```

**The one trap that costs a night:** crops are specified in **`--frames`** (a multiple of 256 —
512 / 1024 / 2048), **never `--duration`**. `--duration` defaults to 380 s = T4096 — an 8× sequence,
~65× attention cost, a ~45 s/step crawl that looks like a hang. If a run is "14× slower than
expected", check this first.

The first step takes several minutes of kernel compilation with no log line. **Do not kill it** for
~10 minutes.

EMA is force-disabled for LoRA/DoRA (it applies to full fine-tunes only).

**Write `run_meta.json` into the run dir at launch** — see §14. A run whose purpose was never recorded
is one somebody has to reverse-engineer later; this is how we lost track of 111 sbatch scripts.

TAKES: minutes to days. VERIFY, a few minutes in:

```bash
ls -la /run/media/kim/Mantu/sa3_lora_runs/$LABEL/*.ckpt
tail -5 /run/media/kim/Mantu/sa3_lora_runs/$LABEL/lightning_logs/version_*/metrics.csv
```

A `.ckpt` whose mtime advances = it is really training. tqdm is silent when not on a TTY, so an empty
terminal is normal and tells you nothing.

## 3. Full fine-tune

Same script, same env. Differences:

- `--full-finetune` — no adapter, the whole 1.4B DiT.
- `--use-ema --ema-beta <b> --ema-update-every <n> --ema-warmup-steps 100`.
- **The label MUST start with `fullft_`**, or the clip grid renders a meaningless 3× strength sweep
  (strength is an adapter concept; a full-FT has none).
- Memory on 16 GB is tight: AdamW OOMs. FusionOpt needs `hyperball` plus `ns5,normuon`. Checkpoints
  are 9.7 GB each — check free space before setting `--checkpoint_every_epochs 1`.

VERIFY the EMA weights actually landed (they are what you must render from later):

```bash
/home/kim/Projects/SAO/.venv/bin/python -c "
import zipfile,sys; z=zipfile.ZipFile(sys.argv[1])
pk=[n for n in z.namelist() if n.endswith('data.pkl')][0]
print('diffusion_ema entries:', z.read(pk).count(b'diffusion_ema'))" <ckpt>
```

Greater than 0, or the run had no EMA and you will be rendering the online weights.

## 4. Resume

| Flag | Restores | `--epochs` means |
|---|---|---|
| `--resume_ckpt <full .ckpt>` | optimizer + scheduler + epoch | the **total** target |
| `--warm_start_ckpt <ckpt>` | weights (old-format ckpts) | **additional** epochs |
| `--init_state_ckpt <ckpt>` | weights only | additional |

⚠ `--init_state_ckpt` **silently prefers the EMA shadow when the checkpoint carries one.** So does
`model_matrix_gen --weights auto`. A low-turnover run rendered that way is largely a render of its
own starting point.

VERIFY: the first logged epoch is (resumed epoch + 1), **and** the checkpoint mtime is newer than the
job start. A reused run dir auto-resumes an old checkpoint and fakes fast progress convincingly.

## 5. Check on a running job

```bash
ls -la <save_dir>/*.ckpt                                  # mtime advancing?
tail -5 <save_dir>/lightning_logs/version_*/metrics.csv
rocm-smi --showuse ; rocm-smi --showmeminfo vram
pgrep -x python3.13                                       # NOT pgrep -f train_lora
grep -Ein "nan|inf" <save_dir>/train_rank0.log            # read the matches; a hit count lies
```

**`pgrep -f train_lora` matches its own wrapper's command line** and reports "alive" forever, including
after the real process died. Match the executable (`-x`) or check the pid directly.

**Deeper diagnostic pass** — trajectory velocity/path-efficiency, LoRA A/B gauge drift, a DSP
disintegration spot-check, and how to read the `[MECHANISM AUDIT]` log lines. No GPU needed, works
on a partial or finished checkpoint set: `docs/train_lora_modular.md` §8 (finished run) / §8b
(while it's still running) has the exact commands and how to read the numbers.

## 6. Kill a run cleanly

**Kill the process group, not the pid.** Orphaned Lightning dataloader workers keep GPU contexts
alive, block bus resets, and masquerade as a wedged card — this caused three failed relaunches and a
needless GPU reset before it was diagnosed.

```bash
setsid nohup <command> &      # launch this way, then:
kill -- -<pgid>
# or, if it wasn't launched under setsid — list first, then kill explicitly:
pgrep -x python3.13
kill <pid> [<pid> ...]
```

**Never `pkill -f '<pattern>'`** — the pattern can match your own shell and kill your session.

VERIFY: `rocm-smi --showpids` is empty. Then `Misc/gpu_guard.sh release KIM`.

---

## 7. Render the canonical clip set

*(§7 + §12 together are the render→score→publish pipeline; `docs/render-analyze-publish.md` walks
through both in order with the why attached, if you want the full picture in one read.)*

**First register the arm** in `eval/rarity_bracket_manifest.json` under `models` — an unregistered arm
renders nothing at all, silently:

```json
"<label>": {"root": "/run/media/kim/Mantu/sa3_lora_runs/<label>", "picks": ["epoch=39-step=3000.ckpt"]}
```

```bash
cd /home/kim/Projects/SAO
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
Misc/gpu_guard.sh acquire KIM $$ || exit 1
.venv/bin/python eval/model_matrix_gen.py --only-labels <label> --weights online --native-grid --dry-run
.venv/bin/python eval/model_matrix_gen.py --only-labels <label> --weights online --native-grid
Misc/gpu_guard.sh release KIM
```

Grid: **109 cells per LoRA checkpoint, 36 per full-FT** (12 prompts × cfg 1/7/16 × strength 1/1.5/2,
24 steps, 20 s).

**⚠ The post-trained `medium` (`_ptm` labels) is the exception: it runs at 8 steps and cfg 1.**
That is the model's native operating point, set by Stability — not a render preference. Use:

```bash
.venv/bin/python eval/model_matrix_gen.py --pt-medium --steps 8 --only-cfgs 1 --only-strengths 1.0
```

`clip_name()` appends `__st8` only because 8 differs from the default 24, so ptm clips land as
siblings and never overwrite. Rendering a ptm arm at 24 steps / cfg 7 is off-config (cfg>1
reportedly "cooks" PT output); rendering a base or full-FT arm at 8 steps / cfg 1 is under-sampled
and produces grainy percussion and bass that is easy to mistake for a flaw in the checkpoint.
`medium` also samples ping-pong (`rf_denoiser`) while `medium-base` samples euler
(`rectified_flow`) — compare only within a sampler.

⚠ **Never render native-length cells (T≥2048) locally** — those go to LUMI. A native-length render on
the card that is also driving the display corrupted the compositor's GL context and required a
plasmashell restart. The renderer carries a hard guard, but do not go looking for a way around it.

VERIFY (**the exit code is meaningless here — it segfaults at teardown after writing everything**):

```bash
ls /home/kim/evals_aac/model_matrix/ | grep -c '^<label>'          # expect 109 or 36
ffprobe -v error -show_entries format=duration -of csv=p=0 <one file>
```

Clips live in **two** places — `evals_aac/model_matrix/` **and** `<run_root>/<arm>/standard_clips/`.
Checking one and concluding "no clips exist" has been wrong twice.

## 8. The three servers

Each from its own repo root, each under a different interpreter:

```bash
cd /home/kim/Projects/SAO && .venv/bin/python eval/explorer_render_server.py
cd /home/kim/Projects/mir && /home/kim/Projects/SAO/stable-audio-3/.venv/bin/python scripts/latent_server_sa3.py
cd /home/kim/Projects/mir && /home/kim/Projects/mir/mir/bin/python -m plots.explorer_sa3.app
```

- **:8056 is the generation path** and holds `medium-base` resident — take the lock with `KIND=server`
  so a waiting agent knows it can ask you to yield.
- The latent server runs under **`stable-audio-3/.venv`**, not `SAO/.venv`.
- The Dash app on **:8051** is the UI. Its interpreter is `mir/mir/bin/python`; `mir/bin/python` does
  not exist.

VERIFY: `curl -s localhost:8056/status` and `curl -s localhost:8051 | head -1`.

## 9. Rebuild the model census

**Mount every drive first.** A scan taken with a drive down reports that drive's arms as *absent*,
not as unknown — this has produced a false "deleted everywhere" twice.

```bash
cd /home/kim/Projects/SAO
.venv/bin/python eval/build_model_census.py --census eval/lumi_ckpt_census.tsv --rescan \
  --html eval/model_census.html --csv eval/model_census.csv
```

`--census` or `--no-census` is mandatory. **`--rescan` after any pull, new recipe source, or drive
remount** — without it the builder reuses a cache, and a stale cache silently reproduces its own old
numbers while the new data never appears.

**Never hand-edit `model_census.html` / `.csv`** — they are generated; the next build erases your
edit. Verdicts go in `Misc/models_index_overrides.json` instead.

VERIFY: the html mtime is now, and the row count / LUMI arm count in the page header are non-zero.

---

## 10. LUMI transfers

**Agents never run ssh/scp/rsync — they hand you the command and you run it here.** Compute and login
nodes are air-gapped: no `git pull`, no internet at all. Code reaches LUMI only by rsync.

**Push code** (allowlist, ~15 MB — the old `tar --exclude=…` form makes a 30+ GB tarball into a
50 GB quota):

```bash
rsync -avR -e "ssh -i ~/.ssh/id_EFP" \
  stable-audio-3/scripts stable-audio-3/stable_audio_3 lumi control \
  akekim@efp.lumi.csc.fi:/project/project_465003186/code/
```

Run it from `/home/kim/Projects/SAO`. **Dry-run with `-n` first**, always.

**Pull** over one multiplexed connection — a connection per file trips LUMI's throttle and the failure
looks exactly like a bad key:

```bash
CP=/tmp/ssh-lumi-pull.sock
MUX="ssh -i $HOME/.ssh/id_EFP -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=4 -o ControlMaster=auto -o ControlPath=$CP -o ControlPersist=900"
$MUX -N -f akekim@efp.lumi.csc.fi
rsync -a --partial --append-verify --timeout=900 -e "$MUX" \
  akekim@efp.lumi.csc.fi:/scratch/project_465003186/renders/matrix_cells/ \
  /run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/renders/matrix_cells/
$MUX -O exit akekim@efp.lumi.csc.fi
```

Canonical pull target is the **UUID drive** (`.../9a410a1d-.../lumi_runs/`), not Mantu — Mantu is the
source-audio drive and is nearly full. **Check free space before a large pull**; the number in
MASTER.md drifts.

Never brace-expand an rsync destination. Never pipe rsync into grep to test success.

VERIFY: `find <dest> -name '*.wav' | wc -l` against the remote dry-run's count.

## 10b. Pull the LUMI TRAINING LOGS (not the checkpoints)

The logs are ~27 MB against terabytes of weights, and LUMI has **no backups on any tier** —
after the allocation ends data is read-only for 90 days, then deleted. Pull them early and often.

```bash
ssh-add ~/.ssh/id_EFP          # once per boot; without it every connection is Permission denied
CP=/tmp/ssh-lumi-logs.sock
MUX="ssh -i $HOME/.ssh/id_EFP -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=4 -o ControlMaster=auto -o ControlPath=$CP -o ControlPersist=1800"
$MUX -N -f akekim@efp.lumi.csc.fi
DEST=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs
rsync -a --partial --append-verify --timeout=900 --prune-empty-dirs --max-size=200M --include='*/' --include='run_meta.json' --include='*.log' --include='metrics.csv' --include='hparams.yaml' --include='*.yaml' --include='*.txt' --include='wandb/***' --exclude='*' -e "$MUX" akekim@efp.lumi.csc.fi:/scratch/project_465003186/runs/ "$DEST/runs/"
rsync -a --partial --append-verify --timeout=900 --prune-empty-dirs --include='*/' --include='*.out' --include='*.err' --exclude='*' -e "$MUX" akekim@efp.lumi.csc.fi:/project/project_465003186/code/ "$DEST/job_logs/"
$MUX -O exit akekim@efp.lumi.csc.fi
```

**The sbatch job logs are the second rsync and they are NOT under `runs/`** — `%x-%j.out` lands in
the SUBMIT cwd, which is `/project/.../code`. 342 files / 159 MB, and they hold the launch config
echo, the first traceback, and the DDP rank lines. Easy to forget precisely because they are not
where the run is.

TAKES: a minute or two. VERIFY by counting artifacts, and compare against the remote count rather
than a guess:
```bash
find $DEST/runs -type d -name lightning_logs | wc -l ; find $DEST/runs -name metrics.csv | wc -l
```
2026-09-09 baseline after the first full pull: **103 lightning_logs, 123 metrics.csv, 248 train
logs, 342 job .out/.err** (from 14 / 6 / 63 / 0). `hparams.yaml` legitimately comes back **0** —
there are none on LUMI at all; that is not a missed filter. 21 of the 120 remote `lightning_logs`
dirs hold no `metrics.csv`, and `--prune-empty-dirs` correctly skips them.

## 11. sbatch on LUMI

```bash
ssh -i ~/.ssh/id_EFP akekim@efp.lumi.csc.fi
cd /project/project_465003186/code/lumi/sbatch && sbatch <name>.sbatch
sacct -u $USER -S <YYYY-MM-DD> --format=JobID,JobName%20,State,Elapsed,ExitCode | grep -i <name>
sacct -j <id> --format=JobID,State,ExitCode,Elapsed,WorkDir%90
tail -100 <submit-cwd>/<jobname>-<id>.out
scancel <id>
```

`squeue` **cannot distinguish "finished" from "never submitted"** — always use `sacct -S <date>`.
`sacct --name` matches the SLURM job name, not our run label.

VERIFY on disk: `ls <RUNROOT>/<arm>/epoch=*.ckpt | wc -l`. A COMPLETED job with exit 0 proves nothing
about whether its HyperQueue tasks produced anything — one family was marked DONE rc=0 while every
sibling OOM'd.

⚠ The allocation was **closed** at 4765/5000 GPU-h (2026-08-23). Transfers only until a new one lands.

## 12. Score clips

*(continues from §7 — see `docs/render-analyze-publish.md` for the full walkthrough)*

```bash
cd /home/kim/Projects/SAO
.venv/bin/python eval/score_and_publish.py --pattern <campaign> --dry-run
.venv/bin/python eval/score_and_publish.py --pattern <campaign> [--src /path/to/pulled/renders]
#   --skip-gpu     DSP + tables only
#   --no-publish   local only
```

`--pattern` is mandatory — unscoped, it pulls into a 59k-clip backlog. The script shells out to the
mir venv itself for the Audiobox leg; you do not need to switch venvs. It gates each step on its
artifact, which is what makes it survivable: **both successful scoring runs this codebase has had
exited rc=134/139** in ROCm teardown after writing everything.

VERIFY: the script reports rows-in-db for the pattern and bytes-on-host for the publish leg. Those two
numbers are the result; the exit code is not.

Standalone Audiobox on one directory: `/home/kim/Projects/mir/mir/bin/python`, **single-file mode
only** — batch mode OOMs WavLM at 16 GB.

## 12b. MIDI-transcribe clips and fold the features into the metrics DB

```bash
cd /home/kim/Projects/SAO
python3 Misc/filelock.py acquire /home/kim/Projects/SAO/.gpu.lock --handle KIM --pid-aware --pid $$
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
# 1. transcribe (GPU). --wavs takes a glob OR a file of paths, one per line. Resumable twice
#    over: clips already in --out are skipped, and clips with a saved .mid are re-scored on CPU.
.venv/bin/python eval/hook_eval_renders.py \
  --wavs '/run/media/kim/Mantu/sa3_lora_runs/model_matrix/<label>*__cfg7__w100__*.wav' \
  --out  /run/media/kim/Mantu/sa3_lora_runs/muscriptor_<campaign>/hook_metrics.jsonl \
  --midi-dir /run/media/kim/Mantu/sa3_lora_runs/muscriptor_<campaign>/midi
python3 Misc/filelock.py release /home/kim/Projects/SAO/.gpu.lock --handle KIM
# 2. fold into clip_metrics.db (CPU, instant, idempotent)
.venv/bin/python eval/midi_metrics_ingest.py \
  /run/media/kim/Mantu/sa3_lora_runs/muscriptor_<campaign>/hook_metrics.jsonl
```

Restrict to **cfg7 / w100** — the operating point — so the set is comparable across arms instead
of mixing guidance settings.

TAKES: ~4 s per 20 s clip, ~10 s per native-length one. VERIFY the artifact:
`wc -l <hook_metrics.jsonl>` and `ls <midi-dir> | wc -l` should match the clip count, and the
ingest prints `midi_metrics now N rows, M of them joinable to metrics.path` — **M is the number
that matters**; rows that do not join are invisible to every page.

⚠ `has_lead` and `n_lead` are defined for every clip; the melodic features are NULL whenever
there is no lead voice (~66% of clips), which is a real property, not a failed measurement.

## 13. Commit and push

**As yourself: plain `git commit`.** The tree's `user.name` is already Kim. `Misc/agent_commit.sh`
hard-rejects the handle `KIM` by design — that script exists to give *agents* a distinguishable author,
which you do not need.

Push targets, because getting this wrong publishes to Stability:

| Repo | Push to |
|---|---|
| SAO (`avp-audio-craft`) | `origin` |
| **stable-audio-3** | **`fork`** — its `upstream` is `Stability-AI/stable-audio-3` **with a push URL** |
| stable-audio-tools, mir, fusion-optimiser | `origin` |

**Never `git push` bare, and never name `upstream`.** Always `git push <remote> <branch>`.

VERIFY: `git log -5 --format='%h %an %s'` — not `--oneline`, which hides the author.

---

## 14. Other routine operations

**Record a run's purpose at launch** — into `run_meta.json` in the run dir, from the submit script
itself (copy the pattern at `lumi/sbatch/fullft_fleet.sbatch:91`). The fields nothing else can
reconstruct: `purpose` (what question this answers, and the EXPERIMENTS.md id), `hypothesis` and its
kill-criterion, `status` (running | done | **abandoned, and why**), and `recipe.notes` (the traps a
future renderer needs, e.g. "must load the EMA weights").

**Full flag-by-flag manual for `train_lora_modular.py`, with recipes and the after-run analysis commands: `docs/train_lora_modular.md`.**

**Local `train_lora_modular.py` does this for you (since 2026-09-22):** it writes
`<output-dir>/<name>/run_meta.json` at launch. Pass `--purpose '...' --hypothesis '...'` (and
optionally `--run-notes '...'`); on a terminal it ASKS if you leave them out, unattended it records
null with a warning. `status` flips to `done` or `crashed` by itself when the run ends. VERIFY:
`python3 -c "import json;d=json.load(open('<run_dir>/run_meta.json'));print(d['status'],d['purpose'])"`.
Other trainer flags added the same day: `--modular-lora-a-lr-mult X` (multiply the step size of every
LoRA/DoRA `lora_A`; default 1.0). Always pass `--eval_demos` to this script: without it the stock
demo callback dies on the torchcodec import at step 1.
Captions, several corpora at once (2026-09-23): `--encoded_dir a,b,c --caption_sidecar ,<avp json>,<bigset json>`
(empty entry = stored prompts) `--caption_probs "0,0.9,0.1;0,0.9,0.1;0.5,0.5,0"` (per source, in order)
`[--source_weights 1,1,0.5] [--track_type_prob 0.5]`. VERIFY in the first minute of the log: one
`[captions] source N ...: audit of 200: X rejected, Y distinct prompts` line per source — 0 rejected and
many distinct prompts is healthy; a WARNING line means that corpus would train on a placeholder or a
constant. Sidecars: avp `SAO/lumi/avp_captions_tiered.json`; goa bigset
`Kosmos/latents_goa_bigset/goa_archive_caption_sidecar.json` (v5; T1 70% genre-correct, T2 48%, T3 1.2%).

```bash
# Pre-encode a dataset to latents
cd /home/kim/Projects/SAO/stable-audio-3
.venv/bin/python scripts/pre_encode_dataset.py --model same-l --data_dir DIR --output_path OUT --model_half

# Gradio UI
.venv/bin/python run_gradio.py --model medium [--lora-ckpt-path P]      # --no-flash-attn, --no-flash-varlen

# CPU-only eval servers — never touch the GPU, so they run while the card is busy
.venv/bin/python scripts/control_eval_server.py        # + submit_control_job.py
.venv/bin/python scripts/latch_eval_server.py          # + submit_latch_job.py

# LatCH head training (SAO-Small)
cd /home/kim/Projects/SAO/stable-audio-tools
sat-venv/bin/python scripts/train_latch.py …           # see docs/commands.md

# Lock a shared file before editing (MASTER.md, EXPERIMENTS.md, KIM-TASKLIST.md)
cd /home/kim/Projects/SAO
python3 Misc/filelock.py acquire <path> --handle KIM
python3 Misc/filelock.py release <path> --handle KIM
python3 Misc/filelock.py check <path>
```

---

## 15. Known-broken — do NOT use these, they are still printed in older docs

| Where | What's wrong |
|---|---|
| `docs/commands.md` LoRA example | sets `PYTORCH_TUNABLEOP_ENABLED=1` — **freezes on RDNA4**; must be `0` |
| `docs/commands.md` LoRA example | uses `--steps` with no `--frames` ⇒ silently trains at T=4096 (the 65× trap) |
| `docs/commands.md` encode path | `/tmp/sa3_beat_manifest.py`, `/tmp/sa3_encode_from_manifest.py` — **gone**, `/tmp` was cleared (see gap G4) |
| `docs/INFERENCE-SURFACE.md` launch block | starts the latent server, **retired 2026-08-25** and folded into :8056 — redundant, not harmful |
| `lumi-ops` skill, old form | `tar --exclude=…` → 30+ GB tarball into a 50 GB quota; use the allowlist form in §10 |
| `launch_dora.sh` (repo root, untracked) | uses `--duration 120`, pre-dates the frames convention — don't copy verbatim |

## 16. Gaps — no command exists for these yet

These are the places where you will still need an agent, or where one owes you a script. Listed so the
absence is visible rather than discovered mid-task.

- **G2. Killing a run** — the process-group rule is in §6, but there is no wrapper script.
- **G3. Regenerating `eval/lumi_ckpt_census.tsv`** (the census's own LUMI input) — the `find` pattern is
  documented, the command is not scripted anywhere. Last regenerated by hand 2026-09-02. Match
  `\( -name '*.ckpt' -o -name '*.pt' \)`; a `.ckpt`-only find drops 528 files and 85 arms and looks
  exactly like a deletion on LUMI.
- **G4. The beat-aligned T=4096 encode pipeline** — the only copies were the `/tmp` scripts above. Not
  recoverable from any doc; needs rebuilding.
- **G5. The 13-clip `standard_clips` sanity set** — convention and naming are documented, the producing
  script is not named anywhere.
- **G6. Publishing to aavepyora** — only reachable via `score_and_publish.py`'s publish leg; no
  standalone command, and server access is WINTERMUTE's lane.
- **G7. `lumi/run_params_extracted.json`** was hand-read from the sbatch corpus. **There is no
  extractor and it cannot be regenerated — do not delete it.** Extend it by hand.
