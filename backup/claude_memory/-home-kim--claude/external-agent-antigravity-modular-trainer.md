---
name: external-agent-antigravity-modular-trainer
description: Kim's external non-fleet agent (Gemini) — kept outside team comms/systems per Kim 2026-10-29; own git author since 10-08; Kim is directly collaborating with a non-fleet external agent (Antigravity) on a new modular optimizer/trainer for stable-audio-3 — attribution and repo-location notes
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-09-21T20:14:47.780Z
---

As of 2026-09-21, Kim is directly directing a separate, non-fleet AI agent called "Antigravity" (commit trailer `Origin: Kim & Antigravity.Neuromancer`) on a parallel effort in the SAO repos — NOT one of the four fleet handles (THE-FINN/CONTINUITY/GHOST-NOTE/WINTERMUTE). Its work so far:

- A new `ModularOptimizer` (6-stage pipeline: lmo/preconditioners/protocols/routing/stack/optimizer.py) at `stable_audio_tools/training/modular_opt/`, distinct from the existing FusionOpt.
- A standalone trainer `stable-audio-3/scripts/train_lora_modular.py` plus `eval_demo_callback.py` / `nan_tripwire_callback.py`.
- A VADD (Variance-Aware Dynamic Dampening) latent-std barrier loss addition to `stable_audio_3/training/diffusion.py`, off-by-default.
- A 2000-checkpoint historical trajectory analysis, see [[sao-checkpoint-analysis-vs-votes]].
- New docs: `docs/POLYAK_STEP_SIZE_AND_VELOCITY_DYNAMICS.md`, `papers/Prospective Unchecked/papers_review_synthesis.md`.

**Goal (Kim's framing):** find the boundary where the modular trainer can learn fast without producing glitches/corruption artifacts.

**Why this matters for the fleet:** the fleet independently found a real bug in this external work — CONTINUITY caught a NaN-permissive loss guard in `eval_demo_callback.py` (`x > threshold` is `False` for NaN, so divergence was misreported as "healthy" for 2 epochs before a hard GPU abort) and fixed it via DM to GHOST-NOTE rather than committing under a fleet handle. GHOST-NOTE separately cross-validated the external work's core corruption-variance finding against their own investigation and confirmed it holds.

**Kim's ruling 2026-10-29 (to me):** Antigravity is listed in MASTER §4 as an external contributor but is **kept OUTSIDE the team systems** (Gemini models unpredictable so far; may reconsider with Google's newer models such as Argon). It should not be posting to AGENT_DIALOGUE / DM logs (it did through W44; Kim didn't know why). Its scope has grown: synth inversion V7/V8, drum separation (Gate G3), publish-helper scripts.

**How to apply:** since 2026-10-08 its commits are authored `ANTIGRAVITY <antigravity@aavepyora.online>` (30+ by 10-29; earlier ones landed as plain `Kim <kim.ake@gmail.com>`, not via `agent_commit.sh`, since it isn't fleet work) — do not assume a plain-Kim-authored commit touching `modular_opt`/`train_lora_modular`/VADD code is Kim's own hand-written work; it's the Antigravity collaboration. If fixing bugs in these files, the convention the fleet used once already: fix it, but don't claim authorship under a fleet handle — DM/report it and let it land under the external attribution or Kim's own commit.
