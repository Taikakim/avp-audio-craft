---
name: latents-saved-with-audio
description: Standing render directive — save the pre-decode latent z0 alongside every rendered audio file
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
---

Kim directive (2026-07-16): **every audio render must save its pre-decode latent `z0` next to the audio file** (e.g. `<clip>.z0.npy`), as a permanent default of the render tooling — not just for one study.

**Why:** latents are the substrate for mechanism work (decoder-vs-sampler isolation, latent-domain metrics, re-decoding through a fixed decoder, steering). Re-rendering later just to recover z0 is expensive GPU time; saving at render time is nearly free.

**How to apply:** SA3 `StableAudioModel.generate(return_latents=True)` returns z0 (B,C,T) and SKIPS peak-normalize + truncation — so the pattern is: get z0 → `np.save` it → `model.same.decode(z0.to(decode_dtype))` → peak-normalize → truncate to `int(duration*sample_rate)`. The SAME decoder (`model.same` / `pretransform`) is untouched by LoRA (adapters hit only DiT + conditioner), so base-latent and DoRA-latent decode through identical weights. Implemented first in `eval/model_matrix_gen.py`; propagate to other render entrypoints. Related: [[sa3-fulllength-control-render]].
