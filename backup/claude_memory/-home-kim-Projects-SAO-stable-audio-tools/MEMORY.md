# SAO stable-audio-tools Memory

Index of topic files. Each entry is a pointer — open the file for detail.

## Project & environment
- [Environment](environment.md) — venv, AMD/ROCm, the `rocm_env.yaml` profile system (replaces `rocm_env.sh`), 7.2.2 tunings dir.
- [Model & data](model-and-data.md) — Small model (rectified_flow, 64×256 latents), dataset/encoding pipeline, conditioners, fine-tune training.
- [SAO finetune dev guidance](sao-finetune-dev-guidance.md) — Stable Audio devs' Discord tips: LR 5e-5, demo VRAM (chunked), ARC is hard, overfitting, AdamW8bit.

## LatCH (latent-control heads / TFG guidance)
- [LatCH overview](latch-overview.md) — what it is, code layout, the 2026-05 train/inference bug-fix chain, current state (rms ep10 works).
- [Sigmas & schedule](latch-sigmas-schedule.md) — **KEY**: σ trajectories, the `s_t` weighting, where guidance has power, why the window must be set per-sampler.
- [Paper interpretation](latch-paper.md) — **KEY**: how to map arXiv 2603.04366 (Selective TFG, LatCH-F/B, ρ/μ/γ) onto this code, and the pitfalls.
- [Verification](latch-verification.md) — closed-loop control check via mir's real extractor; pluggable torch/onnx decoder + benchmark.

## Tooling & infra
- [Latent player](latent-player.md) — player/crossfader/explorer (canonical in the mir project), endpoints, stem encoding.
- [Git & fork](git-fork.md) — `origin`=upstream vs `avp`=user's fork, the `latch-rms-control` branch, staging discipline.
- [MIR project](mir-project.md) — pointer to the sibling project (timeseries DB + real extractors only; its generics stay in mir's own memory).

## Workflow
- [Use MIR tools](feedback-use-mir-tools.md) — bracket ranges & verify LatCH results with MIR's existing tools, not bespoke SAO scripts.
