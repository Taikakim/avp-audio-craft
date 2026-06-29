# Master-Repo Copy Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Duplicate (copy, not move) all first-party tooling into the `SAO/` master repo under `onnx/ control/ latch/ eval/`, make the copies self-consistent and smoke-clean, while leaving both fork checkouts 100% intact.

**Architecture:** Pure additive copy into the existing `SAO` (`avp-audio-craft`) repo. Files are `cp`'d from the forks; nothing is `git rm`'d or `git mv`'d from the forks. The forks remain the working source (and the historical record + fallback). Each component keeps the same-directory relative imports it has today, so it runs from its new dir exactly as it ran from the fork. One genuinely cross-directory import (`eval/ → control/`) is rewired in the copy.

**Tech Stack:** git; `cp`/`rsync`; the consolidated `SAO/.venv` (torch 2.14 / ROCm 7.15, py3.13); `stable_audio_3` + `stable_audio_tools` already installed editable.

## Global Constraints

- **COPY ONLY — never modify the forks.** No `git rm`, no `git mv`, no edits under `stable-audio-3/` or `stable-audio-tools/`. If a step would touch a fork, stop.
- **Out of scope (deferred to a later cutover plan):** fork-thinning, `git filter-repo` history extraction, the installable `SAO/pyproject.toml`, and full cross-dir packaging. Do NOT do these here.
- **`SAO/.gitignore` is a root-anchored allowlist** (`/*` then `!/…`). A new top-level dir/file is invisible to git until it has an explicit `!/name/` (or `!/name`) entry.
- **`FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE`** must prefix any command that imports torch/flash-attn (CK path; the shell may still export TRUE in old sessions).
- **Never run `uv sync`**; never alter the torch/ROCm stack. This plan installs nothing.
- **Commit trailers** (every commit in this plan):
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_013awkzb4ordqvrgsfW3KJMW`
- All commands run from `/home/kim/Projects/SAO` unless stated. `PY=/home/kim/Projects/SAO/.venv/bin/python`.

---

## File Structure

Created in this plan (all under `SAO/`, all tracked via new `.gitignore` allowlist entries):

- `onnx/` — SA3 ONNX suite (copies of the OURS files from `stable-audio-3/scripts/`).
- `control/` — `sa3_control/` package + control training tooling (copies from `stable-audio-tools/avp_sa3/`).
- `latch/` — SAT-native LatCH tooling (copies from `stable-audio-tools/scripts/`).
- `eval/` — dora/longform render + quality eval + riffer launcher (copies; spans two venvs).

Untouched: everything under `stable-audio-3/` and `stable-audio-tools/`.

---

### Task 1: SAO tracking setup (skeleton + .gitignore allowlist)

Make git able to track the four new dirs and the constraints file. No fork files touched.

**Files:**
- Modify: `/home/kim/Projects/SAO/.gitignore`
- Create: `/home/kim/Projects/SAO/onnx/.gitkeep`, `control/.gitkeep`, `latch/.gitkeep`, `eval/.gitkeep`

**Interfaces:**
- Produces: tracked top-level dirs `onnx/ control/ latch/ eval/` that later tasks copy into; `constraints-rocm-stack.txt` becomes tracked.

- [ ] **Step 1: Create the skeleton dirs**

```bash
cd /home/kim/Projects/SAO
mkdir -p onnx control latch eval
touch onnx/.gitkeep control/.gitkeep latch/.gitkeep eval/.gitkeep
```

- [ ] **Step 2: Add allowlist entries to `.gitignore`**

Append these lines to `/home/kim/Projects/SAO/.gitignore` (after the existing `!checkpoint-stats/` line):

```gitignore

# Master-repo tooling (copied from the forks; see docs/superpowers/plans/2026-06-29-master-repo-copy-stage.md)
!/onnx/
!/control/
!/latch/
!/eval/
!/constraints-rocm-stack.txt
```

- [ ] **Step 3: Verify git now sees the dirs and the constraints file**

Run:
```bash
cd /home/kim/Projects/SAO
git check-ignore -v onnx control latch eval constraints-rocm-stack.txt; echo "exit=$?"
git status --short onnx control latch eval constraints-rocm-stack.txt
```
Expected: `git check-ignore` prints **nothing** and `exit=1` (none ignored). `git status` lists `?? onnx/.gitkeep`, `?? control/.gitkeep`, `?? latch/.gitkeep`, `?? eval/.gitkeep`, `?? constraints-rocm-stack.txt`.

- [ ] **Step 4: Commit**

```bash
cd /home/kim/Projects/SAO
git add .gitignore onnx/.gitkeep control/.gitkeep latch/.gitkeep eval/.gitkeep constraints-rocm-stack.txt
git commit -m "chore: master-repo skeleton (onnx/control/latch/eval) + track constraints

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013awkzb4ordqvrgsfW3KJMW"
```

---

### Task 2: Copy the ONNX suite → `onnx/` (+ dora/longform eval scripts → `eval/`)

**Files:**
- Create (copies): `onnx/sa3_control_onnx.py`, `onnx/sa3_latch_onnx.py`, `onnx/control_eval_server.py`, `onnx/latch_eval_server.py`, `onnx/submit_control_job.py`, `onnx/submit_latch_job.py`, `onnx/decode_onnx.py`, `onnx/dit_onnx_infer.py`, `onnx/dit_control_onnx_infer.py`, `onnx/export_dit_onnx.py`, `onnx/export_dit_control_onnx.py`, `onnx/export_same_onnx.py`, `onnx/bench_dit_onnx.py`, `onnx/bench_same_onnx.py`, `onnx/latent_server_dit_onnx.py`, `onnx/make_text_cond.py`, `onnx/latch_validate.py`, `onnx/fifo_infinite_smoke.py`, `onnx/latch/` (subdir)
- Create (copies): `eval/eval_dora_cpu.py`, `eval/eval_dora_quality.py`, `eval/longform_render.py`
- Source (read-only, NOT modified): `stable-audio-3/scripts/`

**Interfaces:**
- Consumes: nothing from earlier tasks (Task 1 produced the dirs).
- Produces: `onnx/sa3_control_onnx.py` exposing `add_fractional_positions_np` (imported by `onnx/export_dit_control_onnx.py`); `onnx/make_text_cond.py`, `onnx/decode_onnx.py` (same-dir imports of the eval servers, preserved by co-location).

- [ ] **Step 1: Copy the ONNX-suite files (explicit list — excludes upstream `train_lora.py`/`pre_encode_dataset.py`/`precache_dit_cond.py`/`__init__.py`)**

```bash
cd /home/kim/Projects/SAO
SRC=stable-audio-3/scripts
for f in sa3_control_onnx.py sa3_latch_onnx.py control_eval_server.py latch_eval_server.py \
         submit_control_job.py submit_latch_job.py decode_onnx.py dit_onnx_infer.py \
         dit_control_onnx_infer.py export_dit_onnx.py export_dit_control_onnx.py export_same_onnx.py \
         bench_dit_onnx.py bench_same_onnx.py latent_server_dit_onnx.py make_text_cond.py \
         latch_validate.py fifo_infinite_smoke.py; do
  cp -p "$SRC/$f" onnx/ || { echo "MISSING: $f"; exit 1; }
done
rsync -a --exclude __pycache__ "$SRC/latch/" onnx/latch/
cp -p "$SRC/eval_dora_cpu.py" "$SRC/eval_dora_quality.py" "$SRC/longform_render.py" eval/
```

- [ ] **Step 2: Verify the copies are byte-identical and the forks are untouched**

Run:
```bash
cd /home/kim/Projects/SAO
diff <(cd stable-audio-3/scripts && cat sa3_control_onnx.py) onnx/sa3_control_onnx.py && echo "identical"
git -C stable-audio-3 status --short scripts/ | head    # expect: empty (fork unchanged)
ls onnx/ | wc -l                                        # expect: 18 files + latch/ dir + .gitkeep
```
Expected: `identical`; fork status **empty**; `onnx/` listing shows the 18 copied `.py` files, `latch/`, `.gitkeep`.

- [ ] **Step 3: Smoke — a representative ONNX module imports from its new home**

Run:
```bash
cd /home/kim/Projects/SAO
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTHONPATH=onnx $PY -c "import sa3_control_onnx; print('onnx import OK:', hasattr(sa3_control_onnx,'add_fractional_positions_np'))"
PYTHONPATH=onnx $PY -m py_compile onnx/control_eval_server.py onnx/latch_eval_server.py onnx/export_dit_control_onnx.py && echo "py_compile OK"
```
Expected: `onnx import OK: True` and `py_compile OK` (no traceback).

- [ ] **Step 4: Commit**

```bash
cd /home/kim/Projects/SAO
git add onnx/ eval/eval_dora_cpu.py eval/eval_dora_quality.py eval/longform_render.py
git commit -m "feat: copy SA3 ONNX suite into onnx/ (+ dora/longform evals into eval/)

Non-destructive copy from stable-audio-3/scripts/; fork left intact.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013awkzb4ordqvrgsfW3KJMW"
```

---

### Task 3: Copy `avp_sa3/` → `control/` (+ riffer launcher → `eval/`)

**Files:**
- Create (copies): `control/sa3_control/` (package), `control/scripts/`, `control/recipes/`, `control/run_control_train.sh`, `control/CONTROL_FINDINGS.md`, `control/RESEARCH_RADAR.md`, `control/ARCHITECTURE.md`, `control/CLAUDE.md`
- Create (copy): `eval/launch_riffer.sh`
- Source (read-only): `stable-audio-tools/avp_sa3/` (excluding `wandb/` run artifacts)

**Interfaces:**
- Produces: `control/sa3_control/mert_selector.py` exposing `MERTEmbedder` (rewired into `eval/eval_dora_quality.py` in Task 5).

- [ ] **Step 1: Copy avp_sa3 (excluding run artifacts) into control/, and the riffer launcher into eval/**

```bash
cd /home/kim/Projects/SAO
SRC=stable-audio-tools/avp_sa3
rsync -a --exclude __pycache__ --exclude wandb --exclude '*.pyc' \
  "$SRC/sa3_control" "$SRC/scripts" "$SRC/recipes" control/
cp -p "$SRC/run_control_train.sh" "$SRC/CONTROL_FINDINGS.md" "$SRC/RESEARCH_RADAR.md" \
      "$SRC/ARCHITECTURE.md" "$SRC/CLAUDE.md" control/
cp -p "$SRC/launch_riffer.sh" eval/
```

- [ ] **Step 2: Verify copy + fork untouched**

Run:
```bash
cd /home/kim/Projects/SAO
test -f control/sa3_control/mert_selector.py && echo "mert_selector present"
git -C stable-audio-tools status --short avp_sa3/ | head    # expect: empty
ls control/                                                  # expect: sa3_control scripts recipes *.md run_control_train.sh
```
Expected: `mert_selector present`; fork status **empty**.

- [ ] **Step 3: Smoke — the sa3_control package compiles from its new home**

Run:
```bash
cd /home/kim/Projects/SAO
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTHONPATH=control $PY -m py_compile control/sa3_control/*.py && echo "control py_compile OK"
```
Expected: `control py_compile OK` (no traceback). (Full runtime import is exercised at cutover; py_compile confirms the copy is intact and syntactically valid under py3.13.)

- [ ] **Step 4: Commit**

```bash
cd /home/kim/Projects/SAO
git add control/ eval/launch_riffer.sh
git commit -m "feat: copy avp_sa3 control tooling into control/ (+ riffer launcher into eval/)

Non-destructive copy from stable-audio-tools/avp_sa3/ (wandb/ excluded); fork left intact.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013awkzb4ordqvrgsfW3KJMW"
```

---

### Task 4: Copy SAT-native LatCH tooling → `latch/`

**Files:**
- Create (copies): `latch/` — `train_latch.py`, all `latch_*.py`, `render_audition*.py`, `eval_latch.py`, `generate_latch_guided.py`, `LATCH_FEATURE_TRAINING_PLAN.md` from `stable-audio-tools/scripts/`
- Source (read-only): `stable-audio-tools/scripts/`

**Interfaces:**
- Produces: `latch/train_latch.py` (CLI with `--help`); `latch/latch_dataset.py`, `latch/latch_model.py` (imported by `train_latch` via same-dir, preserved by co-location).

- [ ] **Step 1: Copy the LatCH tooling by explicit globs**

```bash
cd /home/kim/Projects/SAO
SRC=stable-audio-tools/scripts
cp -p "$SRC"/train_latch.py "$SRC"/latch_*.py "$SRC"/render_audition*.py "$SRC"/eval_latch.py \
      "$SRC"/generate_latch_guided.py "$SRC"/LATCH_FEATURE_TRAINING_PLAN.md latch/
echo "--- copied into latch/ ---"; ls latch/
```

- [ ] **Step 2: Verify copy + fork untouched**

Run:
```bash
cd /home/kim/Projects/SAO
for f in train_latch.py latch_dataset.py latch_model.py; do test -f "latch/$f" && echo "ok $f" || echo "MISSING $f"; done
git -C stable-audio-tools status --short scripts/ | head    # expect: empty
```
Expected: `ok train_latch.py`, `ok latch_dataset.py`, `ok latch_model.py`; fork status **empty**.

- [ ] **Step 3: Smoke — latch copies are syntactically intact (snapshot)**

Run:
```bash
cd /home/kim/Projects/SAO
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE $PY -m py_compile latch/*.py && echo "latch py_compile OK"
```
Expected: `latch py_compile OK`. (Runtime `--help` is deliberately NOT used: `train_latch.py:35` bootstraps `rocm_env.py` via a fork-relative `parent.parent` path that only resolves from the fork. Per the snapshot decision, path-rewiring is deferred to cutover — see the Deferred section.)

- [ ] **Step 4: Commit**

```bash
cd /home/kim/Projects/SAO
git add latch/
git commit -m "feat: copy SAT-native LatCH tooling into latch/

Non-destructive copy from stable-audio-tools/scripts/; fork left intact.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013awkzb4ordqvrgsfW3KJMW"
```

---

### Task 5: Snapshot validation + land session docs

**Snapshot decision (2026-06-29):** the Task 4 smoke surfaced that the copies carry
extensive fork-layout paths (absolute `/home/kim/Projects/SAO/stable-audio-{3,tools}/…`
and fork-relative `parent.parent` bootstraps) across ~20 files. Per the user's choice,
this stage stays a **byte-faithful snapshot** — NO rewiring (no `mert_selector` fix, no
venv headers). All path-rewiring moves to the cutover plan (see Deferred). Validation is
`py_compile` (syntactic integrity), not runtime-from-new-home.

**Files:**
- Modify: none of the copies (snapshot is byte-faithful).
- Commit (already edited this session): `docs/superpowers/specs/2026-06-29-single-master-repo-restructure-design.md`, `docs/superpowers/plans/2026-06-29-master-repo-copy-stage.md`, `docs/consolidated-venv-setup.md`, `MASTER.md`

- [ ] **Step 1: Validate — all copies compile, both stacks import, forks unchanged by the copy**

Run:
```bash
cd /home/kim/Projects/SAO
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE $PY -m compileall -q onnx control latch eval && echo "ALL py_compile OK"
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE $PY -c "import stable_audio_3, stable_audio_tools; from flash_attn import flash_attn_func; print('both stacks OK')"
git -C stable-audio-3 status --short scripts/ | head        # only PRE-EXISTING WIP, unchanged
git -C stable-audio-tools status --short avp_sa3/ scripts/  # empty
```
Expected: `ALL py_compile OK`; `both stacks OK`; the stable-audio-3 list shows ONLY the pre-existing DoRA WIP (`train_lora.py`, `latch/train_latch.py`, `eval_dora_*`) — identical to before this plan ran, proving the copy added nothing; stable-audio-tools empty.

- [ ] **Step 2: Commit the session docs (spec/plan/venv/MASTER)**

```bash
cd /home/kim/Projects/SAO
git add docs/superpowers/specs/2026-06-29-single-master-repo-restructure-design.md \
        docs/superpowers/plans/2026-06-29-master-repo-copy-stage.md \
        docs/consolidated-venv-setup.md MASTER.md
git commit -m "docs: land restructure spec + copy-stage plan + consolidated-venv setup

Copy stage complete (byte-faithful snapshot): tooling duplicated into onnx/control/latch/eval,
forks intact. Path-rewiring, thinning, filter-repo, pyproject, doc sweep deferred to cutover.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013awkzb4ordqvrgsfW3KJMW"
```

- [ ] **Step 3: Push the branch**

```bash
cd /home/kim/Projects/SAO
git push -u origin master-repo-copy-stage
```
Expected: push succeeds to the `avp-audio-craft` remote (branch `master-repo-copy-stage`).

---

## Deferred to a later cutover plan (NOT in this plan)

- **Fork-thinning** (`git rm` the now-duplicated tooling from both forks) — only after the copy is validated and exercised.
- **`git filter-repo` history extraction** — if SAO-local per-file history is wanted, install `git-filter-repo` and re-import at cutover; until then history lives in the (intact) forks.
- **Installable `SAO/pyproject.toml`** — declaring the forks as editable path deps + the curated dep set under `constraints-rocm-stack.txt`. Deferred because the venv already works and a deps-bearing pyproject is a footgun (`uv sync`/bare `-e .` could clobber the stack).
- **Full cross-dir packaging / import cutover** — making `onnx/control/latch/eval` first-class importable packages (note: `onnx` and `eval` are poor package names — `onnx` collides with the pip package, `eval` shadows a builtin; resolve naming at cutover).
- **Doc-path sweep** across `MASTER.md`/`ARCHITECTURE.md`/`docs/inference-servers.md`/per-repo `CLAUDE.md` — done at cutover, once paths are final.
- **Path-rewiring of the copies (discovered during this run — ~20 files, two categories).** The byte-faithful copies retain fork-layout paths that must be rewired before they run from `SAO/`:
  - **Hardcoded absolute paths** to the forks — `control/sa3_control/comprehensive_merit.py:18` (`sys.path.append(".../avp_sa3")`), `control/sa3_control/train.py:118,271`, `control/sa3_control/steered_longform.py:49`, `onnx/export_dit_control_onnx.py:49` (`AVP=…`), `onnx/latent_server_dit_onnx.py:69` (`_SCRIPTS_DIR=…`), `latch/render_audition.py:44` (`REPO=…`), `onnx/latch/verify_medium_heads.py:15,22`, plus `#!.../stable-audio-3/.venv/bin/python` **shebangs** on the eval servers.
  - **Fork-relative `parent.parent` bootstraps** — `latch/train_latch.py:35` (→ `stable_audio_tools/rocm_env.py`), `onnx/latch/train_latch.py:41` (the *separate SA3 variant* → `stable_audio_3/rocm_env.py`), `onnx/make_text_cond.py:30` (`HERE=…parent.parent  # stable-audio-3/`).
  - At cutover, resolve these from the **installed packages** (e.g. `rocm_env.py` via `importlib.util.find_spec("stable_audio_{tools,3}")` WITHOUT importing the package, to keep env-application before torch import) and from relative `SAO/` layout, then re-validate at runtime.
  - **Two distinct `train_latch.py`** exist by design: `latch/train_latch.py` (SAT-native) and `onnx/latch/train_latch.py` (SA3 LatCH variant). Keep both; do not dedupe.

## Cutover strategy & ordering (notes for the cutover instance — do at ep8)

Folded in from a second reviewer (2026-06-29). These reframe the deferred work above:

1. **Forks stay the runnable source until cutover — that is *why* deferral is correct, not a limitation.** The live DoRA run reads the fork originals (`train_lora.py` + the `stable_audio_3` package), and other instances are still committing to the forks (the ONNX WIP we saw as `M`/`??`). Rewiring the copies now would diverge them from still-evolving originals (instantly stale) and create a half-migrated limbo. Do **one tested rewire pass at cutover**, never piecemeal now.

2. **The ~20-file rewire is mostly DELETION, not repointing.** Once `stable_audio_3` / `stable_audio_tools` / `avp_sa3` are proper installed packages (via the master `pyproject.toml` editable installs), the `sys.path.append(...)` and `parent.parent` bootstraps become **unnecessary** — *delete* them rather than repoint them to new absolute paths. So the cutover strategy is the tractable, robust trio:
   - **delete** the path-bootstrap hacks (they resolve via normal imports once installed),
   - **fix the shebangs** (`#!.../stable-audio-3/.venv/bin/python` → `SAO/.venv`),
   - **fix the one `mert_selector` cross-dir import** (`eval/ → control/`).
   This replaces "rewrite 20 hardcoded paths" with "delete bootstraps + 2 small fixes." Order the master `pyproject.toml` editable installs BEFORE the deletions so imports resolve as the hacks come out.

3. **Two `train_latch.py` — do not conflate.** `latch/train_latch.py` (SAT-native) carries `--ema`/`--grad-accum`; `onnx/latch/train_latch.py` is the SA3 LatCH variant that MASTER §1 already flags as a duplication. Different files, different stacks — cutover keeps them distinct; the eventual latch-core dedup is a **separate later job**, not part of cutover.

4. **Ordering at ep8:** finish DoRA → run the post-DoRA eval (render + Audiobox + distance-to-Goa) **from the fork originals first** (the `eval_dora_*` still live there) → *then* cutover (move + rewire-by-deletion + thin). Eval-before-thin is already in the spec addenda; the delete-hacks strategy (#2) and the two-`train_latch` note (#3) are the new bits.
