---
name: air-head-epoch-listening
description: Kim's 2026-10-15 listening verdict on air-head epochs: early epochs / short low-lr training sound best; click meter and val loss miss the glitches
metadata:
  type: feedback
---

Air-RMS head (modular optimiser): O5 (lr 1e-2, d512) is glitch-free only through epoch 3; later epochs have sub-second "spectral smoothing" dropouts. A2 ep7 (1000 steps, EMA half-life 0.5 ep) is the brightest and nearly clean. lr 3e-2 arms glitch from ep4-5. The fadeout glitch comes from the bass/mid heads, not air.

**Why:** the 8-sigma click meter and validation loss both pointed the wrong way (click rate lowest at the glitchy epochs' neighbours, val still improving to ep17), so they cannot select a head.

**How to apply:** pick air heads by listening to early/short-training checkpoints; do not select by val loss or click rate; compare any glitch meter against the bass+body clip of the same seed. See [[steering-improvement-criteria]].
