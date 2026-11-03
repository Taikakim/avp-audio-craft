---
name: sa3-kim-steering-package
description: Handoff package of SA3 steering models for Kevin Griffing (gary4juce/gary4local VST integration) — at /home/kim/sa3-kim-steering
metadata: 
  node_type: memory
  type: project
  originSessionId: a76bbe73-5250-4a70-accd-5324dfe52aa8
---

External collaboration: **Kevin Griffing** (gary4juce / gary4local SA3 backend,
gary-localhost-installer, sa3-ableton-extension, sa3.cpp GGML) is testing Kim's SA3
steering models in his VST. Handoff package built 2026-06-28 at
**`/home/kim/sa3-kim-steering/`** (+ `sa3-kim-steering.tar`, 720M, 34 files).

Two mechanisms, packaged separately with full docs (`docs/01–04`):
- **`control_adapters/`** — density steering (`onset_density.pt`, `onset_per_beat.pt`,
  stripped to inference-only `state`+meta, ~229M each fp32). Forward-only decoupled
  cross-attn; the `sa3_control` inference subset (adapters/inject/conditioner/generate/
  density_schedule/audio_io). **Validated end-to-end from the packaged code**: density
  3→7→11 → measured 4.88→8.12→9.25 onsets/sec. UI must use `ridge_gain` (NOT a fixed
  gain — fixed over-steers the busy end → glitch/RMS-collapse; A/B confirmed, see
  [[infinite-audio-fifo-sa3]] sibling longform work).
- **`latch_guidance/`** — 14 LatCH heads incl. hpcp=chroma (the `latch_weights_sa3_medium`
  set). Autograd-at-inference (TFG) via `generate(latch_configs=[...], latch_hparams=...)`;
  ships the 3 SA3 modules (models/latch.py, inference/latch_guided.py, latch_targets.py)
  + `reference/model.py.kim` for the generate() branch diff. **PyTorch-only** (won't run
  on Kevin's GGML/MLX). Medium needs rho/mu≈64 (10× less sensitive than small).

Key handoff caveats documented: the **fork-Attention diff** (adapter assumes Kim's
`models/transformer.py` Attention attr names), CFG token ordering `[cond, uncond=zeros]`,
n_tokens capped to 16, fp32 for LatCH. Base DiT/AE NOT included (Kevin already ships it).
Kevin offered to spin up an `sa3-kim` custom backend + separate UI tab for the steering
controls. Related: [[latch-sa3-phase1]].
