# Eval board: 20s + native + ptm length variants — render + board design

**Date:** 2026-08-02
**Author:** WINTERMUTE (Kim-directed)
**Status:** design (awaiting Kim sign-off on one open item, §11)
**Scope:** the SA3 model-matrix / dora_table eval boards + the `model_matrix_gen.py` render pass that feeds them.

---

## 1. Goal

Make every eval cell **comparable** (uniform 20 s grid) while still letting you **audition** a
checkpoint at its **native trained length**, and A/B the **post-trained (ptm) base** — all as
switchable variants on the board, without re-rendering the whole corpus or letting disk spiral.

## 2. Motivation (the bug that triggered this)

Within a single model (`winning_goa_t512_a45_fp32`) some cells are 47.55 s and others 20 s —
specifically the **cfg7 × ep10/ep15** cells were rendered at **native T512 length** (512 frames ÷
10.7666 Hz = 47.55 s) and leaked into the 20 s grid slots, while the rest are 20 s. Mixed lengths
make epoch/cfg comparison meaningless. Root fix: **the 20 s grid is the comparison surface; native
is a separate, explicitly-marked artifact** — never sharing a filename with its 20 s sibling.

## 3. What already exists (reuse, don't rebuild)

`eval/model_matrix_gen.py` is the render driver and already carries most of the machinery:

- **Resumable / idempotent.** `load_existing_keys()` + `manifest_key(e)` skip both wav generation
  and manifest append when a `(model, ckpt, cfg, strength, prompt_id, steps, duration)` cell is
  already present. **`duration` is part of the key**, so a native clip (different duration) is a
  distinct cell from its 20 s sibling — no collision, fully resumable per-variant.
- **Native-length filename marker.** `clip_name(...)` appends `__d<duration>` **only when duration
  ≠ default (20 s)**. So 20 s clips keep their existing names byte-for-byte; native clips land as a
  sibling `…__d47.wav` / `…__d95.wav` / etc. This is the collision-safe encoding the leak lacked.
- **`native_len_seconds(label)`** parses the trained context `T=<frames>` from the recipe override
  and returns the native seconds (or None → skip).
- **ptm labels.** The post-trained base is the `<label>_ptm` model convention, already in the
  manifest + board.

Today native is **one cell per (model,ckpt)** at `NATIVE_LEN_CFG=7.0 / NATIVE_LEN_STRENGTH=1.0`
(lines 63–64). This run **extends** that to a full grid at the terminal checkpoint. Nothing about
the naming/resume/skip design changes — only the *set of cells* enumerated.

## 4. Prompt set (9)

Down from 18. **Existing clips for all 18 prompts are kept** (never deleted); the new render pass
only enumerates these 9:

| id | source | text |
|---|---|---|
| `kimlong` | EXTRA_PROMPTS | bittersweet synth … goa trance and 80s retro videogame … BPM 138 … |
| `techno` | EXTRA_PROMPTS | "techno music" (kept as a minimal-prompt **spill** probe) |
| `kl_0` | kl pool | high-energy psytrance, Goa+techno, polished, wide stereo … |
| `rb_bracket_0` | BRACKET_PROMPTS | "2020s goa trance, melodic mood, 148 bpm" (seed 1102008041) |
| `rb_common_1` | rarity band | "mid 90s goa trance, melodic space mood, 140 bpm" |
| `rb_common_2` | rarity band | "mid 90s goa trance, 148 bpm" |
| `rb_rare_7` | rarity band | "2010s psy-trance, progressive trance, 136 bpm" |
| `rb_rare_8` | rarity band | "mid 90s goa trance, techno, space dark mood, 140 bpm" |
| `goa_organic` **(new)** | this spec | see below |

**New prompt `goa_organic`** (typo "crips"→**crisp** fixed):

> This track is a high-energy psychedelic 90s goatrance piece that blends the driving pulse of
> classic Goa trance with organic and crisp sound of analog synthesizers. It sits at 143 BPM in a
> 4/4 time signature and is rooted in F minor. Instrumentation & production: The arrangement is
> built around a relentless four-on-the-floor kick and a thick, side-chain-compressed synth bass
> that anchors the low end, together with moody pads and distorted roland tb303-style acid riffs
> and resonant filtered saw wave legato synth lead with a rubbery portamento

Seed: **2026** (fixed); id `goa_organic`. **Rendered for the terminal checkpoint of each model only**
(all other 8 prompts keep their existing multi-checkpoint coverage).

Dropped from active rendering (existing clips retained, still visible on the board): `housestyle`,
`trig2`, `kl_1`, `kl_2`, `kl_bracket_0`, `rb_common_0` (byte-dup of `rb_bracket_0`), `rb_mid_3/4/5`,
`rb_rare_6`.

## 5. Render matrix

Grid: **cfg {1, 7, 16} × strength {0.6, 1.0, 1.5, 2.0}** (all four strengths already exist in the
corpus — no new weight axis). cfg15/cfg24 are non-standard (2 stray models) and are **dropped from
the board dropdown** (already shipped, commit 76a53a6); not rendered here.

| variant | base | cfg × w | checkpoints | prompts | filename marker |
|---|---|---|---|---|---|
| **20s** | medium | full grid | all (existing) | 8 kept (existing) + `goa_organic` @terminal | none (default) |
| **native** | medium | full grid | **terminal only** | all 9 | `__d<native_s>` |
| **ptm** | post-trained | **cfg1 / w1 only** | all ckpts (20 s) | all 9 | `_ptm` on label |
| **ptm+native** | post-trained | **cfg1 / w1 only** | **terminal only** | all 9 | `_ptm` + `__d<native_s>` |

**Why these scopes** (Kim's calls):
- **native @ terminal only** — you compare epochs on the 20 s grid; you audition the *final* model
  at native. Confines the expensive long-clip renders (T4096 native = 380 s) to one checkpoint per
  model. All-epochs native would be dominated by the few 8–28-checkpoint models and spiral disk.
- **ptm @ cfg1/w1 only** — the post-trained base only renders cleanly at cfg1/w1/8-step; higher cfg
  "cooks" it (glitches). A full ptm grid would be 11/12 broken cells. cfg1/w1 is its native config.

## 6. Filename + manifest schema

Reuse the existing orthogonal encoding — **no new filename grammar**:

```
20s medium :  <label>__<ckpt>__cfg<C>__w<W>__<pid>__s<seed>.wav              (→ .m4a)
native med :  <label>__<ckpt>__cfg<C>__w<W>__<pid>__s<seed>__d<native_s>.wav
ptm 20s    :  <label>_ptm__<ckpt>__cfg1__w100__<pid>__s<seed>.wav
ptm native :  <label>_ptm__<ckpt>__cfg1__w100__<pid>__s<seed>__d<native_s>.wav
```

- `_ptm` suffix on `<label>` = post-trained base (existing convention).
- `__d<native_s>` = native length (existing non-default-duration convention; absent = 20 s).
- `native_s` from `native_len_seconds(label)`; if None (unknown T), **skip native for that model**
  and log it (no silent drop).

Manifest (`manifest.jsonl` / `manifest_live.jsonl`) already carries `model` (with `_ptm`), `ckpt`,
`cfg`, `strength`, `prompt_id`, `steps`, `duration`. **The board derives the two variant axes from
existing fields** — `base = "ptm" if model.endswith("_ptm") else "medium"`, `length = "native" if
duration != 20 else "20s"` — so **no manifest schema change is required**. (The board strips the
`_ptm` suffix to group a base model and its ptm sibling under one row/coordinate.)

## 7. Idempotency / existing-file check (required)

The driver already skips cells present in the manifest via `manifest_key` (which includes duration).
Requirements for this run:
- **Skip on manifest key AND on-disk artifact.** Before rendering a cell, skip if its `manifest_key`
  is known *or* the target `.m4a` already exists on disk (guards the case where the manifest and the
  clip dir drift — see task #71). Log skips in aggregate (`[skip-existing] N cells`), not per-line.
- Native cells key on their non-default `duration`, so they never collide with the 20 s siblings and
  a re-run only fills genuine gaps.
- Restartable across GPU-card resets / job requeues with zero duplicate renders.

## 8. Execution: split LUMI + local (checkpoint availability)

**LUMI does not hold checkpoints that were not trained on it.** Older, locally-trained checkpoints
are absent there. So the job list partitions by checkpoint location:

1. **Partition step (run first).** From `build_jobs()` (CONTINUITY's `rarity_bracket_manifest.json`),
   for each `(label, ckpt_path, ckpt_tag)` resolve whether the checkpoint exists on LUMI.
   → **LUMI queue** (present) vs **local queue** (local-only).
2. **LUMI queue → 8-GCD job.** The bulk (esp. the long-context T2048/T4096 models trained on LUMI).
3. **Local queue → overnight GPU pass** on the desktop RX 9070 XT (Kim: "later tonight").

**Hard edge case — local-only × T≥2048 native.** A local-only checkpoint that is T2048/T4096 **cannot
render native locally** (the 16 GB display card OOM/plasmashell-crash rule — MASTER §5, task #65) and
its checkpoint isn't on LUMI either. The partition step MUST flag any such job. Options, per flagged
job (Kim decides if any appear): (a) push that checkpoint to LUMI and render its native there;
(b) render only its 20 s + ptm-cfg1 locally, skip native. **In practice the split likely aligns
cleanly** — LUMI-trained models are the long-context ones (native on LUMI), local-only models are the
older short-T ones (native = 47.5 s or less, safe locally) — but the guard must exist, not be assumed.
Local native renders are capped at **T ≤ 1024** (≤ 95 s); anything larger is a partition error.

## 9. LUMI 8-GCD harness notes (from MASTER §5 — these bit us before)

- **GCD pinning = `ROCR_VISIBLE_DEVICES=$SLURM_PROCID` ALONE.** Never also set `HIP_VISIBLE_DEVICES`
  — they stack and left 7/8 workers GPU-less on the last native run (job 20068082, 4/100 cells).
- **Verify by counting output clips, not the sbatch return code** (the `rc=0`-on-crash and
  `pgrep -f 'a\|b'` traps). Gate completion on artifact count == expected.
- Wall-clock is dominated by T2048/T4096 native (380 s clips generate ~15–20× slower than 20 s). A
  **one-model T4096 pilot timing** should precede the full submit to pin the total.
- Outputs land on LUMI scratch → pull the keep-set to the UUID drive (MASTER §2); only a
  representative subset goes online (redaction seam / Pages size).

## 10. Board changes (dora_table + model_matrix)

- **Two checkboxes: `native` and `ptm`.** They select among up to 4 files per cell coordinate
  `(base-label, ckpt, cfg, w, pid)`: `{medium-20s, medium-native, ptm-20s, ptm-native}`.
- **Context-aware disable** (reuse the coverage/graceful-resolve logic just shipped): `native` greys
  out where no native clip exists (non-terminal checkpoints); `ptm` greys out outside cfg1/w1. The
  combination `ptm+native` is simply both boxes checked.
- Board builds a per-coordinate variant map from the manifest (deriving base/length per §6). The
  existing same-playhead A/B applies across variant switches too (switch native↔20s keeps position).
- dora_table's existing `pptm` checkbox is superseded by this generalized `ptm` toggle.

## 11. Open item (needs Kim sign-off)

- **ptm checkpoint scope.** This spec assumes **ptm-20s at cfg1/w1 across all checkpoints** (cheap,
  20 s) so the ptm switch works on every epoch's cfg1/w1 cell, and **ptm-native at cfg1/w1 terminal
  only** (matching native). Alternative: confine ptm entirely to the terminal checkpoint. Confirm.

## 12. Volume / disk estimate (final scopes)

- native @ terminal: 92 models × 9 prompts × 3 cfg × 4 w = **9,936 native renders ≈ ~19 GB**
  (T-weighted; the 17 T4096 terminals at ~6 MB/clip dominate).
- ptm-20s @ cfg1/w1 (61 ptm-capable models, all ckpts) ≈ ~2 k renders (tiny, 20 s).
- ptm-native @ cfg1/w1 terminal (61 models × 9) ≈ 549 native renders.
- `goa_organic` @ terminal, all variants ≈ ~2.3 k renders.
- **Total ≈ ~15 k renders / ~22 GB** — contained. (Existing corpus 63 k cells / ~16 GB untouched.)

## 13. Task breakdown

1. **Partition script** — enumerate `build_jobs()`, resolve LUMI vs local per checkpoint, flag any
   local-only × T≥2048, emit `render_jobs_lumi.jsonl` + `render_jobs_local.jsonl`.
2. **`model_matrix_gen.py` extension** — restrict the prompt set to the 9 (add `goa_organic`);
   native from single-cell → full grid @ terminal; ptm cfg1/w1 (20 s all-ckpt + native terminal);
   keep the resume/skip + `__d`/`_ptm` naming; add the on-disk existence guard (§7).
3. **LUMI 8-GCD submit** (G's harness lane) — hand off `render_jobs_lumi.jsonl` + the pinning note.
4. **Local overnight pass** — `render_jobs_local.jsonl` on the desktop card, T≤1024 native cap.
5. **Board variant checkboxes** (WINTERMUTE) — native/ptm toggles + context-aware disable, deriving
   variants from the manifest per §6.
6. **Sync + board rebuild** — pull keep-set, regenerate + deploy both boards.
