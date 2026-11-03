---
name: latch-sa3-phase1
description: LatCH (latent-control head) ported to Stable Audio 3 and verified controlling bass RMS on small-music-base
metadata: 
  node_type: memory
  type: project
  originSessionId: a76bbe73-5250-4a70-accd-5324dfe52aa8
---

LatCH (Latent-Control Heads — TFG guidance from a small transformer head that predicts an MIR
feature from noisy latents) was ported from stable-audio-tools (SAO Small) to **stable-audio-3**.
The full cross-repo context (paper, the SAO bug-fix chain, sigma/window analysis) lives in the
sibling project's memory at `/home/kim/.claude/projects/-home-kim-Projects-SAO-stable-audio-tools/`.

**Status (2026-05-26): Phase 1 implemented AND empirically verified.**
- Branch `latch-sa3-phase1`. Code under `scripts/latch/` (head, dataset, encode, train, verify) +
  `stable_audio_3/inference/latch_guided.py` (grad-enabled Euler guided sampler). README at
  `scripts/latch/README.md`; plan at `docs/superpowers/plans/2026-05-26-latch-sa3-phase1.md`.
- Closed-loop result: `rms_energy_bass` head (10 epochs, 3000 same-s-encoded crops) controlling
  `small-music-base` → requested −50/−30/−10 dB measured −58.6/−26.6/−15.0, **corr 0.965, monotonic**.
  Operating point: gain 8, window [0.4, 1.0], 50-step Euler, fp32.

**Why these choices:** SA3 base models are flow-matching (= the `rectified_flow` linear forward
noise the head trains on); `small-music-base` uses the `same-s` 256-dim latent space (~10.76 Hz),
which is why the corpus had to be re-encoded (old SAO latents are 64-dim @ 21.53 Hz, unusable).

**How to apply / gotchas worth remembering:**
- The base model id is **`small-music-base`** (or `small-sfx-base`) — there is NO `small-base`.
- Guidance must run in **fp32**: TFG backprops through the model+head, and SA3's default fp16
  (model_half=True on CUDA) makes the grad dtypes clash.
- Data: corpus audio is `/run/media/kim/Mantu/goa_crops` (`<Artist - Title>_N.flac`, stems skipped);
  its stems match the mir TimeseriesDB crop keys, so encode→train target lookup just works.
- scipy + librosa are required for the verify extractor and are not in pyproject (a `uv sync` drops them).

**Out of scope (Phase 2):** ping-pong guidance for the post-trained `small`/`medium` models,
SAME-L/medium heads, σ-relative-window transfer. See [[shared-framework-multi-version]].
