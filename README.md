# SAO — Audio Generation Pipeline

Meta-repo for the **mir + Stable Audio** pipeline. This is *just* the
coordination layer (docs, install orchestrator). The actual code lives in three
separate forks that this repo clones and sets up.

- `mir/` — MIR feature extraction, whole-track timeseries (My framework for extracting various acoustic and descriptive audio features from audio in order to enrich audio metadata for AI training`)
- `stable-audio-tools/` — LatCH heads, FusionOpt, audition renders (Kim's
  `audio-tools-AVP` fork)
- `stable-audio-3/` — SA3 medium, LoRA fine-tune, SA3 LatCH (Kim's fork of
  `Stability-AI/stable-audio-3`)

**Hardware target**: AMD RX 9070 XT (RDNA4, gfx1201), Ryzen 9 9900X, ROCm.

---

## Quick start (new machine)

```bash
# 1. clone the meta-repo
git clone git@github.com:Taikakim/avp-audio-craft.git ~/Projects/SAO
cd ~/Projects/SAO

# 2. run the orchestrator — clones the 3 forks, sets up each venv per its own
#    install.sh
./install.sh

# 3. (optional) only do a subset
./install.sh --only stable-audio-3      # just SA3
./install.sh --clone-only               # clone repos, skip venvs
./install.sh --help                     # all options
```

The orchestrator reads `projects.toml`, clones each repo to the configured
path, then runs `./install.sh` inside each clone. Re-running picks up new
commits via `git pull`.

---

## Read the docs first

- **`MASTER.md`** — single source of truth for cross-repo facts (data paths,
  venv-per-task table, gotchas). Imported by each repo's `CLAUDE.md`.
- **`WORKLOG.md`** — reverse-chronological "what landed / what broke" log.
- **`ARCHITECTURE.md`** — how the three repos fit together.
- **`docs/`** —
  - `venvs.md` — which venv to use for which task (the #1 source of wasted time)
  - `commands.md` — copy-paste reference for the commands you actually run
  - `flash-attn-ck-rdna4.md` — building FA with the CK backend on RDNA4 (the
    real ROCm 7.14 path, no aiter/Triton workaround)
  - `latch.md` — LatCH heads pipeline, end-to-end
  - `training-findings.md` — what we've learned from training runs
  - `lessons-learned.md` — cross-cutting gotchas worth remembering
  - `todos.md` — open work items

---

## Per-repo install scripts

Each fork carries its own `install.sh` that knows its specific stack. They
work standalone (clone the fork alone, `./install.sh` → working venv) and
they're what the meta orchestrator delegates to:

| Repo | Stack | Notes |
|---|---|---|
| `stable-audio-3/install.sh` | **TheRock 7.14 / Python 3.13 / CK flash-attn** | Migrating from 2.10/7.2.3 to the official ROCm-CK path; see `docs/flash-attn-ck-rdna4.md`. Builds flash-attn from source (~70 min on Ryzen 9 9900X). |
| `stable-audio-tools/install.sh` | **torch 2.10 ROCm 7.2.3 / Python 3.10** | Stable, known-good. Don't migrate to 3.13 until FusionOpt + LatCH training stack has been verified there. |
| `mir/install.sh` | **torch 2.9 ROCm 7.2 / Python 3.12 + essentia + madmom + ONNX-MIGraphX** | Particular setup; wraps mir's existing `requirements.distributable.txt` (8-step install). Uses Kim's custom torch wheels in `mir/`. Install order is meaningful — script handles it. |

---

## What is *not* in this repo

The three working forks themselves (they're git-cloned by `install.sh`),
their venvs, their build artifacts, and the ROCm wheels (`my_wheels/`). All
of that is `.gitignore`d.

If you need to add new files at the SAO/ root that you *do* want versioned,
add an explicit `!/your-file` to `.gitignore` (the root-anchored `/*` pattern
makes inclusion opt-in).
