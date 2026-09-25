# SAO — Audio Generation Pipeline

Meta-repo for the **mir + Stable Audio** pipeline. This is *just* the
coordination layer (docs, install orchestrator). The actual code lives in three
separate forks that this repo clones and sets up.

- `mir/` — MIR feature extraction, whole-track timeseries (acoustic + descriptive audio-feature extraction to enrich audio metadata for AI training)
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

## Manuals — what to read for what

This repo covers three different jobs (installing, running, training), so there isn't
one manual — there's a short one for each. Start with whichever matches what you're
trying to do:

- **Actually running something** — start/resume/kill a training run, render a batch of
  test clips, start the inference servers, score results → **[`RUNBOOK.md`](RUNBOOK.md)**.
  Every entry is a command you can copy-paste, with what it costs (roughly how long it
  takes) and how to tell whether it actually worked. No background reading required.

- **Training a LoRA** → **[`docs/train_lora_modular.md`](docs/train_lora_modular.md)**.
  What each training option does (plain-language, not just the flag name), a few
  known-good starting recipes to copy rather than guess at, and — once a run has some
  checkpoints, even before it finishes — a small toolkit for telling whether it actually
  learned something or quietly went wrong: does the generated audio have glitches, did
  the model's weights move a sane amount, is it still improving or just wandering.

- **Picking the right Python environment** → **[`docs/venvs.md`](docs/venvs.md)**. This
  project has three separate Python setups for three different jobs, and using the wrong
  one is the single biggest time-waster here. This doc says which one to use when.

- **Quick command lookup** → **[`docs/commands.md`](docs/commands.md)** — a flat list of
  the commands people actually run day to day, no explanation needed.

- **"Why did my training run blow up / sound wrong?"** →
  **[`docs/training-findings.md`](docs/training-findings.md)** — a running list of
  training failures we've already diagnosed (symptom → cause → fix). Worth a check
  before assuming you've found something new.

- **Going deeper** — **[`MASTER.md`](MASTER.md)** (facts shared across all three repos:
  data paths, hardware quirks) and **[`ARCHITECTURE.md`](ARCHITECTURE.md)** (how the
  three repos fit together, and its **doc map** at the bottom, which indexes everything
  else in `docs/` — build recipes, the steering/control-head pipeline, and more).

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
