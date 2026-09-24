# arxiv-2609.02734 - LoRA-TSD - Tangent-Space Spectral Descent for LoRA via Muon-Style Updates

**Reading depth:** paper NOT read beyond the title; the official CODE was read in full (~/Projects/LoRA-TSD, src/optimizers/lora_tsd.py, rsvd_init.py, run scripts) (C 2026-09-22/23).

**What it contains:** Spectral (Muon-style) descent on the tangent space of the rank-r manifold, with steps sized on B·A itself; balance option keeps ‖A‖=‖B‖. MIT licence.

**For us / what stays ours:** Works with DoRA (loss depends on B·A only) and with zero-B init (finite on step 1, tested on our 229 adapters). But unbatched it costs 8.5 s/step (ball_iters=1), 31 s (5) on ROCm: QR 12–17 ms/call; CholeskyQR2 ~2 ms. A batched port is estimated at a session. Gate: EXPERIMENTS A14.
