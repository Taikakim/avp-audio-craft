# Render → analyze → publish — the standard-clips pipeline

How to take one trained checkpoint from "sits on disk" to "has a row on the local eval boards,
scored and ranked against everything else." Three steps, two scripts. No agent needed — every
command here is copy-paste, same as `RUNBOOK.md` §7/§12 (this doc is the walkthrough version of
those two sections, in order, with the why attached; if the two ever disagree, trust `RUNBOOK.md`).

This is a different question from "did my training run go well?" — for that (crackle scan, did
the weights move a sane amount, is it still improving), see `docs/train_lora_modular.md` §8/§8b.
This doc is about turning a finished checkpoint into something you can see and hear ranked
against the rest of the board.

## Step 0 — register the arm

The renderer only touches checkpoints it's told about. An unregistered arm renders **nothing, with
no error** — this is the single most common "why did nothing happen" cause. Add it to
`eval/rarity_bracket_manifest.json` under `"models"`:

```json
"<label>": {"root": "/run/media/kim/Mantu/sa3_lora_runs/<label>", "picks": ["epoch=39-step=3000.ckpt"]}
```

`<label>` is whatever short name you want this arm to show up as everywhere downstream (the
board, the score command's `--pattern`, the tables). `picks` is a list — you can register more
than one checkpoint from the same run (e.g. a pre-collapse checkpoint alongside the final one).

## Step 1 — render the canonical clip set

```bash
cd /home/kim/Projects/SAO
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
Misc/gpu_guard.sh acquire KIM $$ || exit 1
.venv/bin/python eval/model_matrix_gen.py --only-labels <label> --weights online --native-grid --dry-run
.venv/bin/python eval/model_matrix_gen.py --only-labels <label> --weights online --native-grid
Misc/gpu_guard.sh release KIM
```

This is the **canonical grid**: 12 fixed prompts × cfg {1, 7, 16} × LoRA strength {1, 1.5, 2},
24 diffusion steps, 20 seconds each — **109 cells for a LoRA/DoRA checkpoint, 36 for a full
fine-tune**. Same prompts and settings every time, which is what makes different checkpoints
comparable to each other on the board.

**Two exceptions worth knowing before you render:**

- **A post-trained `medium` checkpoint (label ends `_ptm`) is NOT rendered at the settings
  above.** Stability tuned it to run at 8 steps / cfg 1 specifically — that's its correct
  operating point, not a shortcut. Use:
  ```bash
  .venv/bin/python eval/model_matrix_gen.py --pt-medium --steps 8 --only-cfgs 1 --only-strengths 1.0
  ```
  Rendering a `_ptm` arm at 24 steps / cfg 7 "cooks" it (reportedly worse with higher cfg);
  rendering a base or full-FT arm at 8 steps / cfg 1 under-samples it and produces grainy
  percussion/bass that looks like a checkpoint flaw but is really just too few steps.
- **Never render clips ≥190s (T≥2048 frames) on this machine** — that length of attention on the
  same GPU that drives the display has corrupted the desktop compositor before (needed a restart
  to recover). The renderer refuses this itself; don't go looking for a way around it. Long clips
  render on LUMI instead (`.claude/skills/lumi-ops/SKILL.md`).

**How to tell it worked** — the exit code is meaningless here (it segfaults at teardown *after*
writing every file, every time):

```bash
ls /home/kim/evals_aac/model_matrix/ | grep -c '^<label>'      # expect 109, or 36 for full-FT
ffprobe -v error -show_entries format=duration -of csv=p=0 <one file>
```

Clips actually land in **two** places — `/home/kim/evals_aac/model_matrix/` and
`<run_root>/<arm>/standard_clips/`. Checking only one of them and concluding "nothing rendered"
has been wrong before.

## Step 2 — score, and publish locally

One command does the rest: it stages the rendered clips, sanity-checks the audio (refuses to
score anything decoded from a blown-up/NaN latent), runs the DSP + Audiobox/CLAP metrics, and
rebuilds the local board pages.

```bash
cd /home/kim/Projects/SAO
.venv/bin/python eval/score_and_publish.py --pattern <label> --dry-run
.venv/bin/python eval/score_and_publish.py --pattern <label> --no-publish
```

`--pattern` is a **required** label prefix (it's the same `<label>` from step 0) — leaving it off
tries to score the entire multi-year backlog (tens of thousands of clips). `--no-publish` is what
makes this "locally": it stops after rebuilding the board pages, before the step that ships
anything to the public site.

**What actually happens, in order** (you can watch it print each one):
1. **ingest** — ties the clips you just rendered into the shared manifest
2. **sanity** — throws out any cell whose latent std says the model blew up before you waste
   Audiobox time scoring garbage audio
3. **DSP** — cheap waveform-level metrics (spectral flatness, HF-blowout, discontinuities)
4. **Audiobox/CLAP** — the GPU-side aesthetic + prompt-adherence scoring (this leg shells out to
   the `mir` venv itself; you don't need to switch)
5. **tables** — rebuilds the board pages from everything now in the metrics database

The exit code lies here too (both scoring runs that ever produced good data exited with a ROCm
teardown crash *after* writing everything) — trust what it prints: rows added to the database and
which pages got rebuilt, not the return code.

Optional GPU-free single-directory check (no ranking, just raw DSP numbers for one folder):
`/home/kim/Projects/mir/mir/bin/python`, single-file mode only — batch mode OOMs at 16 GB.

## Where the results actually land

| What | Path |
|---|---|
| Rendered clips (wav + m4a + `.z0.npy` latents) | `/home/kim/evals_aac/model_matrix/` |
| The main board (every arm, every cell) | `/home/kim/evals_aac/model_matrix.html` |
| The DoRA/LoRA ranking table | `/home/kim/Projects/SAO/eval/dora_table.html` |
| Redacted twin of the above (what would ship publicly) | `/home/kim/Projects/SAO/eval/dora_table_public.html` |
| Raw metrics, if you want to query them yourself | `/home/kim/Projects/SAO/eval/clip_metrics.db` (SQLite) |

Open the HTML files directly in a browser — they're static pages, nothing needs to be served.

## Optional — also ship it to the public site

Drop `--no-publish` and the same command's last leg rsyncs the rebuilt pages and any new clips to
the public site (aavepyora.online). It re-scans with `rsync --itemize` first so a bulk rebuild
doesn't re-upload hundreds of byte-identical files, and does a leak-scan (no checkpoint filenames,
paths, or internal names) before anything goes out. Only do this once you actually want the arm
public — there's no un-ship.

## If something looks wrong

- **Nothing rendered, no error** → the arm isn't registered (Step 0), or the label in
  `--only-labels`/`--pattern` doesn't match what's in the manifest exactly.
- **The clip count is short of 109/36** → check `Misc/gpu_guard.sh` didn't hand the GPU to
  something else mid-render, and re-run `model_matrix_gen.py` — it skips cells that already exist.
- **Audio sounds wrong but scored fine / not sure if the checkpoint itself is bad** → that's a
  per-run diagnosis question, not a scoring question. See `docs/train_lora_modular.md` §8/§8b
  (clip crackle scan, trajectory velocity/path-efficiency, LoRA gauge drift, a DSP disintegration
  spot-check).
- **A whole arm is missing from the board even though clips exist** → re-run
  `score_and_publish.py --pattern <label> --dry-run` first; it prints a preflight plan without
  writing anything, so you can see where it thinks the arm currently stands.

## Traps, in one place

- Register the arm before rendering — an unregistered arm renders nothing, silently.
- `_ptm` checkpoints render at 8 steps / cfg 1, nothing else.
- Never render ≥190s clips on this machine.
- Ignore the exit code on both scripts — check the artifact (file count / rows / rebuilt pages).
- `--pattern` on `score_and_publish.py` is mandatory, not optional.
- `--no-publish` = local only. Publishing is a one-way door — only do it on purpose.
