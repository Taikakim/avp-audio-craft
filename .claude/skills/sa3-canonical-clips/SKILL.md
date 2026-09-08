---
name: sa3-canonical-clips
description: Use when rendering, checking, or auditioning the canonical/standard clip set for any SA3 checkpoint or training arm — "do we have clips for this run", "render the standard clips", adding an arm to the model matrix or a board, or judging whether a rendered clip is valid. Covers the two clip conventions and where each lives, the exact grid (prompts/cfg/strength/seeds), how to register an arm, and the render traps.
---

# Canonical clips — the concrete procedure

> Written 2026-09-08 (Kim direct: *"concrete steps for creating our canonical clips, their
> features etc should be in place because now I see this always takes discovery time from
> agents when they start"*). `MASTER.md`/`ARCHITECTURE.md` cover what the model matrix IS;
> this covers **how to make and verify the clips**.
>
> Companion: **`sa3-training`** (especially §1, the EMA trap — it decides what you render).

## ⛔ 0. FIRST: clips live in TWO places. Check BOTH before saying "there are none."

An arm can be fully rendered and still look unrendered if you check one location.
Cost this exact mistake twice: `lion_lr1e-5` was reported as having "no clips at all" when
it had 26, and a whole `_BROKEN` directory was believed all-broken when a third of it was fine.

| convention | where | what | for |
|---|---|---|---|
| **model matrix** (the board) | `/home/kim/evals_aac/model_matrix/` + `manifest.jsonl` | **109 cells** per LoRA ckpt, **36** per full-FT ckpt | the shared board, census, scoring |
| **standard_clips** (sanity listen) | **`<run_root>/<arm>/standard_clips/`** — inside the checkpoint dir | **13 clips** per ckpt | a campaign's own quick A/B, often rendered by whoever ran the campaign |

**Coverage check, both at once:**
```bash
# board cells per (arm, epoch)
ls /home/kim/evals_aac/model_matrix/ | sed -E 's/(.+)__(ep[0-9]+)__cfg.*/\1 \2/' | sort | uniq -c | grep <arm>
# the run's own sanity clips
find <run_root> -name standard_clips -type d -exec sh -c 'echo "$1: $(ls "$1" | wc -l)"' _ {} \;
```

## 1. The canonical grid

Source of truth: `eval/model_matrix_gen.py`. Constants: `CFGS = (1.0, 7.0, 16.0)`,
`STRENGTHS = (1.0, 1.5, 2.0)`, `STEPS = 24`, `DURATION = 20.0`, `FPS = 44100/4096 = 10.7666 Hz`.

**The 12 canonical prompts** (`build_prompts(n_per_band=3, n_kimlong=3)`) — 9 rarity-band +
3 long-form. Ids are stable and are what every board row keys on:
`rb_common_0/1/2`, `rb_mid_3/4/5`, `rb_rare_6/7/8`, `kl_0/1/2`.

**Cell counts — match the arm's SIBLINGS, don't invent a set:**
- **LoRA/DoRA arm:** 12 prompts × 3 cfgs × 3 strengths = **108**, **+1 native** = **109**
- **Full-FT arm:** 12 × 3 × **1** = **36** — no adapter, so no strength axis. Switched on by
  `label.startswith("fullft_")`, so **a full fine-tune's label MUST start with `fullft_`**
  or it gets a meaningless 3× strength sweep and a wrong cell count.
- **`_ptm` arm (adapter on the POST-TRAINED `medium`):** rendered at **8 steps, cfg 1,
  strength 1.0** — **not** the 24-step / cfg 1-7-16 grid. Stability post-trained/distilled
  `medium` to that operating point, so it is a property of the model, not a render choice
  (Kim direct 2026-09-08):
  ```
  model_matrix_gen.py --pt-medium --steps 8 --only-cfgs 1 --only-strengths 1.0
  ```
  **Both directions of getting this wrong are silent.** A ptm arm at 24 steps / cfg 7 is
  off-config — cfg>1 reportedly "cooks" PT output. A base or full-FT arm at 8 steps / cfg 1 is
  under-sampled, and the grainy percussion / bass it produces (like sample-rate reduction or
  quantisation) reads as a flaw in the *checkpoint* when it is really the step count. This has
  already caused one misattribution during an A/B audition.
  ⇒ **When comparing arms, each side must sit at ITS OWN native config.** Two clips whose names
  differ in `__st<N>` are therefore not automatically an unfair pair; a clip rendered off its
  model's native config is. And `medium` samples ping-pong (`rf_denoiser`) while `medium-base`
  samples euler (`rectified_flow`) — compare only within a sampler.

**The native cell** (`--native-grid`): one full trained-context-length render, `kl_0`, cfg 7,
w100. Length = `frames / FPS` → T512 = 47.55 s (files tagged `__d48`), T256 = 23.78 s,
T1024 = 95.1 s. The length comes from `--native-frames-file` or a `T=<frames>` string in the
arm's `Misc/models_index_overrides.json` recipe. **No `T=` ⇒ the native cell is silently
skipped** — that is the mechanism, not a bug; add the override if you want the cell.
T≥2048 natives are banned locally (Kim 2026-07-21).

## 2. Registering an arm (this is the step people miss)

Jobs come from **`eval/rarity_bracket_manifest.json` → `models`**, NOT from scanning disk.
An unregistered run renders nothing and reports nothing.

```json
"<label>": {
  "root": "/absolute/path/holding/<label>/",     // optional: omit if under Mantu sa3_lora_runs
  "picks": ["epoch=39-step=3000.ckpt"]
}
```
- Resolved path is **`root/<label>/<pick>`** — the label is a *directory component*. Runs
  saved outside Mantu (e.g. straight to the NVMe) need the `root` override.
- Convention here: **one pick per arm, the terminal checkpoint**, unless a trajectory is
  wanted. Add intermediate picks deliberately.
- Missing fat `.ckpt` falls back to `<name>.weights.ckpt` automatically (the LUMI pruner
  keeps advancing), so a pruned run needs no manifest edit.
- Non-existent picks print `[skip-missing]` and are skipped — harmless but noisy, so an arm
  whose weights were deliberately deleted should keep `"picks": []` **plus a note saying why**,
  not be silently dropped.

## 3. Rendering

```bash
Misc/gpu_guard.sh acquire <HANDLE> $$ || exit 1
trap "Misc/gpu_guard.sh release <HANDLE>" EXIT
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
.venv/bin/python eval/model_matrix_gen.py \
  --only-labels <a,b,c> --weights online --native-grid
```
- **Always `--dry-run` first.** It prints the job list, the resolved ckpt paths and the cell
  count — and it is how you catch a `[skip-missing]` before burning GPU time.
- **`--weights auto|ema|online` — see `sa3-training` §1.** `auto` = EMA when present, which
  on a short run renders something close to the base and makes every arm sound alike.
  Match the siblings: `grep -m1 '<label>' …/manifest.jsonl` → `"weights"`.
- **Resume is automatic**: existing manifest keys are skipped, so re-running only fills gaps.
  `clip_name()` appends `__stN`/`__dN` **only** for non-default steps/duration, so a
  different-steps pass lands as a sibling file and never overwrites.
- Useful narrowing: `--only-ckpts`, `--only-prompts`, `--only-cfgs`, `--only-strengths`,
  `--limit`, `--time-budget-hours`, `--terminal-only`.

## 4. ⛔ Verify the OUTPUT, not the exit code

- **Renders can segfault at teardown AFTER writing every file.** The exit code lies. **Count
  the files.**
- **Check duration against what was requested.** A whole quarantine dir
  (`_BROKEN_native_120s`) was condemned wholesale because 111 of 165 clips hit a **120.0 s
  render/encode cap** — but 54 short renders were intact and were hidden for seven weeks.
  ```bash
  for f in *.m4a; do echo "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f") $f"; done
  ```
- **The obvious audible test does NOT work.** Truncation removes the tail; it does not degrade
  the audio, so a broken clip's first 120 s sounds perfect. And an **abrupt full-amplitude
  ending proves nothing** — these are fixed-length generations, so intact renders also end
  mid-phrase (verified on a complete 47.55 s clip). **Duration-vs-declared is the only
  reliable discriminator.**
- A full-FT load asserts >99% tensor coverage and **fails loud** rather than rendering a
  half-loaded model. Do not weaken that.

## 5. The `standard_clips` sanity set (13 per checkpoint)

Used by optimizer/LR campaigns for a fast listen without touching the board. Written to
`<run_root>/<arm>/standard_clips/`:
- 12 × `std20s` (the same 12 canonical prompt ids) at **cfg 7, strength 1.0, 24 steps, 20 s**
- 1 × `native48s` at `kl_0`
- naming `<label>__<prompt_id>__std20s.wav` (**different** from the board's
  `<label>__<ckpt>__cfg<C>__w<NNN>__<pid>__s<seed>.wav`)
- ships its own **`run_meta.json`** recording `purpose`, `gen_config`, and an explicit
  `checkpoints` map label→ckpt path. **Write that file** — it is what makes the set
  interpretable later, and how this convention was reconstructed at all.

## 6. After rendering

- Clips stage to `evals_aac/` (AAC 192k, the serving codec); `manifest.jsonl` gains one line
  per cell. Boards derive per-model cfg/strength availability **from the manifest** — never
  hand-couple a board to a model.
- Scoring/eval pages: see `ARCHITECTURE.md` reuse index and the eval-tables spec
  `docs/superpowers/specs/2026-07-06-eval-tables-human-first.md` (three-audience standard:
  tool for Kim, reproducible resource for engineers, plain-language explainer).
- Anything public must go through `build_evals.redact()` — and reuse `PLAYER_JS` **by path**
  (`Misc/build_evals.py:21` prepends `Misc/` to `sys.path`, where a first-party `filelock.py`
  shadows the pip package importers need).
