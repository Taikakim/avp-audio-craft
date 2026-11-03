---
name: sa3-latent-explorer-tool
description: SA3-only latent viewer+player tool built on mir branch sa3-latent-explorer for reviewing SAME-L encoder quality + latent-space workflows
metadata: 
  node_type: memory
  type: project
  originSessionId: 085d95f2-1875-4707-ac4d-9d05b552b676
---

A two-process latent explorer for the **SA3 / SAME-L** latents (256-dim, T=4096, 10.767 Hz), built 2026-06-19 on the **`sa3-latent-explorer` branch of `mir`** (the old 64-dim Stable Audio Small viewer at `mir/plots/explorer/` + `mir/scripts/latent_server.py` stays on other branches as a reference — intentionally untouched). Purpose: review SAME-L encoder quality on the Goa dataset + drive latent-space workflows (experimental DJ-style mixing, auditioning LatCH control-head recipes).

Architecture (spec: `mir/docs/superpowers/specs/2026-06-19-sa3-latent-explorer-design.md`, plan: `.../plans/2026-06-19-sa3-latent-explorer.md`):
- **Viewer** `mir/plots/explorer_sa3/` (Dash, runs in mir venv 3.12) — reads `.json` + `.TIMESERIES.npz` sidecars directly (sidecars are the only feature source; no DB). Tabs: per-crop latent heatmap + timeseries overlay, dataset scatter, live analysis (PCA/256×256 dim-xcorr/dim↔feature-corr on a ≤400-crop sample, no precompute).
- **Player — two interchangeable, same HTTP shape:** (A) torch `mir/scripts/latent_server_sa3.py` + `latent_player_sa3.ini` (port **7892**, **SA3 venv** 3.13, ~5 GB; loads `AutoencoderModel.from_pretrained("same-l")`; `/status /crops /meta /decode /source /mix /steer`; `/steer` = fp32 autograd LatCH nudge). (B) low-VRAM `mir/scripts/latent_server_onnx.py` (port **7893**, **mir venv**, ~2 GB GPU; the exported SAME ONNX decoder on ORT-MIGraphX, compiles once at boot, RTF ~39×; `/decode /mix /source`, NO `/steer`→501; see [[sa3-onnx-amd-inference]]). Viewer targets either via `SA3_PLAYER_PORT` (`player_client` env-configurable).

Latents: `/home/kim/Projects/latents_sa3` (local copy of `Lehto/latents_sa3`), flat `NNNNNN.{npy,json,TIMESERIES.npz}`, npy is `[256,4096]` **float16**.

Status (2026-06-19): code-complete, 24/24 non-GPU tests pass, full SDD review done, **GPU-validated**. `/decode` (380s reconstruction), `/mix` (slerp latent interp), `/meta`, `/status`, and `/steer` (14 medium heads, steering changes audio) all work on the RX 9070 XT. `/source` works only when the **Mantu** drive (removable, holds source audio) is mounted — it correctly errors otherwise. Head family resolved → `latch_weights_sa3_medium`, loaded via `load_latch_from_checkpoint` (see [[sa3-latch-head-families]]). Branch not yet merged.
