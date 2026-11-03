---
name: lumi-supercomputer-access
description: "Kim has LUMI access (8x 64GB MI250X nodes) for heavy film_grain work — ROCm-native, code ports directly"
metadata: 
  node_type: memory
  type: project
  originSessionId: 12fdecac-006e-48d2-ad43-2e665f84dc62
  modified: 2026-08-08T10:53:56.592Z
---

Kim has access to the LUMI supercomputer: 8× MI250X nodes with 64 GB each (stated 2026-08-08). MI250X runs ROCm — film_grain's torch code is already ROCm-native, so it ports with no stack change.

**How to apply:** target LUMI for the heavy tiers: full-frame 36×24 mm packs (~4.6B crystals), restoration-training corpus generation (embarrassingly parallel over frames/stocks/seeds), Monte Carlo photon transport for the colour-stage PSF tables, and large reaction–diffusion grids. Local 16 GB GPU (kim-deepspace) stays the dev/iteration machine; the [[gpu-lockfile-convention]] applies locally, not on LUMI. Batch scheduling on LUMI is presumably SLURM — package runs as self-contained scripts (field cache dir configurable).
