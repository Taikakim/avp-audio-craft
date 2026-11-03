---
name: sa3-latch-head-families
description: "SA3 LatCH head weights come in two families with different dirs, filenames, and checkpoint keys — picking the wrong one finds zero heads"
metadata: 
  node_type: memory
  type: project
  originSessionId: 085d95f2-1875-4707-ac4d-9d05b552b676
---

The SA3 LatCH head checkpoints live in two dirs under `/home/kim/Projects/SAO/stable-audio-3/` and are **not** interchangeable:

- `latch_weights_sa3/` — epoch-numbered files `latch_sa3_<feature>_ep<N>.pt` (e.g. `_ep1.pt`..`_ep10.pt`). **No `_best.pt` files.** Checkpoint non-state keys: `feature_name, noise_schedule, loss_type, in_channels, out_channels`.
- `latch_weights_sa3_medium/` — 14× `latch_sa3_<feature>_best.pt`. Richer checkpoint keys including `t_injection, standardized, std_mean, std_std, precision, epoch, avg_loss`.

Both families store `out_channels` and `state_dict` keys, so `LatCH(in_channels=256, out_channels=ckpt["out_channels"], dim=256, depth=6, num_heads=8); load_state_dict(ckpt["state_dict"])` works — **but** the medium heads carry `t_injection` (likely non-default, e.g. adaln_zero) and `standardized`/`std_mean`/`std_std`, so a correct loader must pass `t_injection` to the constructor and account for target standardization; constructing with defaults risks a state_dict-key mismatch or wrong-scale steering.

**Resolved (2026-06-19):** the canonical heads for the `same-l` `latents_sa3` are the **`latch_weights_sa3_medium`** family (SAME-L = SAME-Large = the medium model's autoencoder). The SA3 explorer player (`mir/scripts/latent_server_sa3.py`, branch `sa3-latent-explorer`) now defaults `latch_weights_dir` there, and `_load_head` reuses `stable_audio_3.models.latch.load_latch_from_checkpoint(path, device)` — the canonical loader that auto-detects in/out channels, dim, depth, num_heads, and t_injection from the state dict (works for both families) and attaches ckpt metadata (std_mean/std_std) as `head.metadata`. Do NOT hardcode `LatCH(dim=256, depth=6, num_heads=8)` — the medium heads are depth=4/adaln_zero and won't load. Validated on GPU: `/status` lists 14 heads, `/steer` produces steered audio. See [[sa3-latent-explorer-tool]].
