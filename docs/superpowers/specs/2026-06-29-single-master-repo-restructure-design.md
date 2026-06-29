# Single master repo + thin forks — restructure design

**Goal:** Consolidate all first-party tooling into one master repo (`SAO/`, the
`avp-audio-craft` git repo) that imports `stable-audio-3` and `stable-audio-tools`
as editable, *thin* forks holding only genuine upstream deltas — so the forks stay
rebase-able on upstream and the tooling lives in one IP-clean, single-venv home.

**Architecture:** Promote the existing SAO-level repo into the lab/master repo. It
already holds the coordination docs (`MASTER.md`/`WORKLOG.md`/`ARCHITECTURE.md`),
`constraints-rocm-stack.txt`, `docs/`, and the consolidated `.venv`, and its
`.gitignore` already ignores the nested fork checkouts (allowlist style). Tooling
moves in via `git filter-repo` (history preserved); the forks are then thinned by
`git rm`-ing the moved files. One py3.13 venv (`SAO/.venv`, torch 2.14 / ROCm 7.15)
already serves both stacks — validated end-to-end, including a real SA3 DoRA *training*
run on native CK flash-attn, not just inference (see `docs/consolidated-venv-setup.md`).

**Tech stack:** git + git-filter-repo; uv (editable installs under
`constraints-rocm-stack.txt`); Python 3.13.

## Global Constraints

- **No physical moves while the SA3 training run is active.** The gating run is
  **`sa3-goa-dora-47s-b4`** (batch-4 beat-aware DoRA, ~4.5 h, running from **`SAO/.venv`
  on CK flash-attn**) — NOT the stopped `sa3-goa-dora-47s` / PID 640022. It runs
  `train_lora.py` from `stable-audio-3/scripts/` and imports `stable_audio_3` from the
  fork checkout, so Phases 1-4 are GATED until it finishes; Phase 0 (skeleton, no moves)
  is safe now. Liveness: `ps -eo cmd | grep '[t]rain_lora.py'` +
  `stable-audio-3/dora_goa_47s_b4.log`.
- **Never touch torch/ROCm stack or CK flash-attn** — all installs go through
  `uv pip install -c constraints-rocm-stack.txt`; never `uv sync`.
- **Preserve git history** of moved tooling (`git filter-repo`), not a flat copy.
- **Forks stay upstream-syncable** — only `stable_audio_3/*` / `stable_audio_tools/*`
  *package* edits remain in the forks; all tooling leaves.
- Commit trailers per the session convention; stage only intended files (forks have
  unrelated WIP).

## Target layout

```
SAO/  (avp-audio-craft = master/lab repo, allowlist .gitignore)
  pyproject.toml            # editable: ./stable-audio-3, ./stable-audio-tools; deps pinned by constraints
  constraints-rocm-stack.txt
  onnx/      # SA3 ONNX suite: export_*, *_onnx_infer, *_eval_server, submit_*, sa3_{control,latch}_onnx,
             #   decode_onnx, make_text_cond, latent_server_dit_onnx, bench_*_onnx, latch_validate, latch/
  control/   # sa3_control adapter training (from avp_sa3/sa3_control) + run_control_train.sh, recipes
  latch/     # LatCH training: train_latch, latch_dataset, latch_model, render_audition*, eval_latch,
             #   generate_latch_guided, latch_* probes  (from stable-audio-tools/scripts)
  eval/      # riffer (launch_riffer.sh), scoring, audition, eval_dora_*, longform_render, dora evals
  docs/  MASTER.md  WORKLOG.md  ARCHITECTURE.md
  stable-audio-3/       # FORK (nested, gitignored): stable_audio_3 pkg deltas only
  stable-audio-tools/   # FORK (nested, gitignored): stable_audio_tools pkg deltas only
  mir/    .venv/        # unchanged / already built
```

## Inventory — what moves vs. stays

**The line:** code that *imports* the model → master repo. Edits to the model
*packages* (`stable_audio_3/`, `stable_audio_tools/`) → stay in the forks.

### Moves to the master repo

- **`stable-audio-3/scripts/` (OURS only):** `sa3_control_onnx.py`, `sa3_latch_onnx.py`,
  `control_eval_server.py`, `latch_eval_server.py`, `submit_control_job.py`,
  `submit_latch_job.py`, `decode_onnx.py`, `dit_onnx_infer.py`,
  `dit_control_onnx_infer.py`, `export_dit_onnx.py`, `export_dit_control_onnx.py`,
  `export_same_onnx.py`, `bench_dit_onnx.py`, `bench_same_onnx.py`,
  `latent_server_dit_onnx.py`, `make_text_cond.py`, `latch_validate.py`,
  `fifo_infinite_smoke.py`, `longform_render.py`, `eval_dora_cpu.py`,
  `eval_dora_quality.py`, `latch/` → into `onnx/` (+ `eval/` for the dora/longform ones).
- **`stable-audio-tools/avp_sa3/`** (entire dir): `sa3_control/`, `scripts/`, `recipes/`,
  `run_control_train.sh`, `launch_riffer.sh`, `CONTROL_FINDINGS.md`, `RESEARCH_RADAR.md`,
  `ARCHITECTURE.md` → into `control/` + `eval/`.
- **`stable-audio-tools/scripts/` (OURS):** `train_latch.py`, `latch_dataset.py`,
  `latch_model.py`, `render_audition*.py`, `eval_latch.py`, `generate_latch_guided.py`,
  `latch_align_check.py`, `latch_decode.py`, `latch_head_sensitivity.py`,
  `latch_probe_encodability.py`, `latch_prototype_beat_density.py`,
  `LATCH_FEATURE_TRAINING_PLAN.md` → into `latch/`.

### Stays in the forks (genuine upstream deltas)

- **stable-audio-3:** the `stable_audio_3/` package edits (LatCH model `models/latch.py`,
  `inference/latch_guided.py` + `latch_targets.py`, ROCm env `rocm_env.py`, attn/APG
  patches in `models/dit.py`/`transformer.py`), the local ROCm wheels, and **upstream
  scripts**: `train_lora.py`, `pre_encode_dataset.py`, `precache_dit_cond.py`,
  `scripts/__init__.py`. **Two more OURS package deltas (2026-06-29 DoRA session) that
  thinning must keep, like the latch/dit patches:** `stable_audio_3/data/dataset.py`
  (`PreEncodedDataset(beat_aware_crop=…)` + `_get_downbeat_starts` — downbeat-aligned
  crop from per-latent `.TIMESERIES.npz`) and `stable_audio_3/training/diffusion.py`
  (`on_save_checkpoint` preserving `optimizer_states/lr_schedulers/epoch/global_step` —
  resumable, LoRA-scale).
- **stable-audio-tools:** the `stable_audio_tools/` package edits (LatCH, `rocm_env.py`,
  FA backward patch), `train_latch`/dataset only if they import from the package — they
  don't (verified: they import `stable_audio_tools.*` as a library), so they move.

> NOTE: `make_text_cond.py`, `sa3_control_onnx.py`, `decode_onnx.py` are imported by the
> eval servers via same-dir relative import — they move *together* into `onnx/`, so the
> imports stay intact. `export_dit_control_onnx.py` imports `add_fractional_positions_np`
> from `sa3_control_onnx` — same package, fine.

## Migration mechanics

1. **Per-source-repo `git filter-repo`** to extract the moving paths *with history* into
   a temporary repo, then merge into `SAO/` under the target subdir. Two extractions
   (one per fork) because filter-repo rewrites a single repo at a time.
2. **`.gitignore` allowlist:** add `!/onnx/ !/control/ !/latch/ !/eval/ !/pyproject.toml`
   so the new dirs are tracked (SAO ignores-all-but-allowlisted).
3. **Master `pyproject.toml`:** declares `stable-audio-3` + `stable-audio-tools` as
   editable path deps and the app dep set; all installs use `-c constraints-rocm-stack.txt`.
   (The venv is already populated; pyproject documents/reproduces it.)
4. **Fork thinning:** after a clean move + smoke, `git rm` the moved files from each fork
   and commit ("tooling moved to avp-audio-craft master repo"); push.
5. **Doc-path sweep:** update every reference from `stable-audio-3/scripts/…` and
   `stable-audio-tools/avp_sa3/…` to the new `onnx/`/`control/`/`latch/`/`eval/` paths —
   in `MASTER.md`, `ARCHITECTURE.md`, `docs/*` (notably `docs/inference-servers.md`,
   committed `015b610`, which references `stable-audio-3/scripts/…`), the per-repo
   `CLAUDE.md` files, and the recipe docs. (This also fixes the cross-repo notes written earlier.)

## Phasing (all phases except 0 GATED on training-run completion)

- **Phase 0 (safe now):** create `SAO/pyproject.toml`, empty `onnx/ control/ latch/ eval/`
  with `.gitkeep`, `.gitignore` allowlist entries. No fork files touched. Commit.
- **Phase 1:** move the ONNX suite (`stable-audio-3/scripts` OURS) → `onnx/` (+ dora/longform
  → `eval/`) via filter-repo. Fix the few cross-dir imports. Smoke: import + a CPU eval.
- **Phase 2:** move `avp_sa3/` → `control/` + `eval/`. Smoke: control train dry-run import.
- **Phase 3:** move SAT-native LatCH tooling (`stable-audio-tools/scripts` OURS) → `latch/`.
  Smoke: `train_latch --help`, dataset import.
- **Phase 4:** thin both forks (`git rm` moved files) + push; full doc-path sweep; final
  dual-stack smoke; update `docs/consolidated-venv-setup.md` + ARCHITECTURE.

## Verification (per phase)

- After each move: `SAO/.venv/bin/python` imports the moved modules from their new home;
  one representative run (e.g. an eval-server boot, a `--help`, or a CPU smoke).
- Final: both forks still import (`stable_audio_3`, `stable_audio_tools`); the eval
  servers + train drivers run from the master repo; forks contain no tooling.

## Risks / open items

- **filter-repo of a subset** must use exact path lists; a missed file breaks an import →
  caught by the per-phase smoke. Keep the fork `git rm` as a *separate later commit* so a
  bad move is trivially revertable (files still in fork history until Phase 4).
- **Mixed `scripts/` dirs** — the move lists above are explicit to avoid dragging upstream
  scripts (`train_lora.py`) out of the fork.
- **Re-point any absolute paths** in scripts/docs that hardcode `stable-audio-3/scripts/…`.
- The dora training run's eval tooling (`eval_dora_*`) moves in Phase 1/4 — run those
  evals against the current run *before* Phase 1, or from the new path after.
- **Cross-dir import on the move:** `eval_dora_quality.py` (→ `eval/`) imports `MERTEmbedder`
  from `avp_sa3/sa3_control/mert_selector.py` (→ `control/`). Fix that import (or hoist the
  embedder to a shared location) in Phase 1/2; the per-phase smoke catches it. (`eval_dora_cpu.py`
  ↔ `eval_dora_quality.py` clip-naming is already mutually compatible.)
- **`eval/` spans TWO venvs — add a per-script venv header:** `eval_dora_cpu.py` runs in
  `SAO/.venv` (SA3 CPU render); `eval_dora_quality.py` runs in the **mir venv** (Audiobox + MERT).
  The "single venv serves both stacks" premise holds for SA3+SAT only — **mir stays the
  measurement venv**, so `eval/` must not be assumed single-venv.

## Provenance

The 6 notes from the active DoRA/CK-FA session (committed `d78a7ed`) have been folded into
the sections above: gating run → Global Constraints; the two new package deltas
(`data/dataset.py` beat-aware crop, `training/diffusion.py` full-state checkpointing) →
Stays in the forks; the `mert_selector` cross-dir import and the two-venv `eval/` →
Risks; `inference-servers.md` → Migration mechanics §5 doc sweep; training-validated
single-venv → Architecture.
