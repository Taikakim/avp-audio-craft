---
name: git-fork
description: "Git remotes (upstream vs the user's avp fork), the latch-rms-control branch, and staging discipline for this repo"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ccd33273-2ad9-4e1a-a571-5a74da061b46
---

- **`origin` = `https://github.com/Stability-AI/stable-audio-tools.git`** — the public *upstream*. Do NOT push here.
- **`avp`** = the user's fork; this is where work goes (added 2026-05-25, SSH `git@github.com:...`). **RENAMED 2026-05-27: `stable-audio-tools-avp` → `audio-tools-avp`** (`git@github.com:Taikakim/audio-tools-avp.git`). GitHub still redirects the old URL (pushes succeed with a "repository moved" notice), but the local `avp` remote URL is stale — update with `git remote set-url avp git@github.com:Taikakim/audio-tools-avp.git`. Privacy depends on the repo's GitHub visibility.
- **`latch-density` branch (avp)** — this session's LatCH work beyond the 2026-05-25 merge: `7e87410` (smoothing/density bake-off, 10× GUI ranges, beat-head downgrade, spec, verify scripts) + `7f70eb9` (preload, shared-holdout, `--dim/--depth/--num-heads`, **chroma_major/minor target for hpcp**, `latch_shape_bench.py`, `run-dim-ablation.sh`/`run-tests.sh`, config 7.2.2→rocm_env.yaml cleanup, test-inference disables) + `68dfda1` (`--optimizer {adamw,lion,prodigy,adam8bit,schedulefree}`, `--scheduler cosine`, `--save-best-only`; `run-optim-matrix.sh`/`run-optim-extra.sh`). Based on `e3839f5`; avp/main has since moved to `117638f` — merge later (code files mostly disjoint from main's doc/attribution commits). Weights/logs deliberately NOT pushed (code-only).
- Local `main` is **ahead 13 / behind 9** of upstream — the 9 behind are SA3/upstream commits the user deliberately did NOT merge (the `git pull` divergence was left unresolved on purpose).

## LatCH work → fork (2026-05-25)
Branch `latch-rms-control` (off `main` @ faa1fa7), **pushed to `avp`**, 3 commits:
- `dbae528` env: rocm_env.yaml system (see [[environment]]).
- `5c9d801` latch: train/inference fixes + verification tooling (see [[latch-overview]]).
- `7f8f855` feat: robust Huber loss, dB-floor clamp, held-out val split + per-feature docs.

`avp/main` had **diverged** (7 commits — upstream Stability-AI merges, an operator-precedence fix, and a dist-shift fix; common ancestor `3193234`). Merged `latch-rms-control` via a `merge-latch` branch (merge `af0ed92`, **clean — no conflicts**; the dist-shift fix `450bddd` was a trivial `seq_len` clamp in `DistributionShift.time_shift`, unrelated to the LatCH sampler), which fast-forwarded onto main.

**DONE (2026-05-25): `avp/main` is now at `af0ed92`** — all LatCH work merged. The `latch-rms-control` and `merge-latch` *remote* branches were deleted; `master` and `Gradio_Lab` left alone. The user's **local** `latch-rms-control` branch still exists with unrelated WIP (only the remote was removed).
Note: the agent can't open PRs or push via GitHub HTTPS (no creds/`gh`); only SSH works for `git push` (prefix `GIT_SSH_COMMAND=/usr/bin/ssh PATH="/usr/bin:$PATH"`). Promoting a fast-forwardable branch is just `git push avp <branch>:main`.

## Staging discipline (important)
This repo has ~50+ uncommitted/untracked files unrelated to any given task — wheels (`*.whl`, hundreds of MB), data dirs, model weights (`latch_weights/*.pt`, `models/exported_model/*.onnx`), sweep outputs (`*.wav`), and prior local edits. **Always stage specific files by name; never `git add -A`/`.`** Commits should be code-only (no `.pt/.npy/.whl/.wav/.onnx/.ckpt`).

Also note: `git` and many coreutils are not on the agent's restricted Bash PATH — use absolute paths (`/usr/bin/git`, `/usr/bin/cat`, etc.).

See [[latch-overview]], [[environment]].
