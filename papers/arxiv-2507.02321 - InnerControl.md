# InnerControl (arXiv:2507.02321) — Konovalova et al., AIRI

**Relevance to SAO: the direct successor to ControlNet++ — and its core lesson maps
onto machinery we ALREADY have (t-conditioned probes).**
**Status: DEEP-READ (full 7 pages, 2026-07-03, THE-FINN).**

Problem they solve: ControlNet++'s one-step-z0 metering only works at LOW noise
(t ≤ 200–400/1000); *extending it to early/noisy steps improves alignment (RMSE↓) but
craters quality (FID↑, visible artifacts)* — their Fig 1 — because the meter (DPT etc.)
reads a blurry, out-of-domain one-step estimate. **Fix:** train lightweight
**t-conditioned convolutional probes H(·,t) on intermediate UNet features** (inspired by
Readout Guidance) that predict the control signal accurately *even at high noise*
(verified vs DPT, their Figs 2–3); then apply an alignment loss over nearly the whole
trajectory ([920→0]) alongside ControlNet++'s late-step reward loss (Eq 8:
`L = L_diff + α·L_reward + β·L_alignment`). Result: depth RMSE 26.09 vs C++ 28.32
(−7.9%) at guidance 7.5, quality held.

**Mappings to our stack:**
1. Our LatCH heads are *already* t-conditioned probes (`t_injection`) on the latent —
   the InnerControl ingredient exists in-house. C's latent `cc_probe` (genre distill)
   meters z0_hat in latent space; if onset authority ever needs all-step supervision,
   the InnerControl move is: train the probe on **noised latents with t-conditioning**
   (or DiT intermediate features) and widen the gate — don't just raise `t_max` on a
   clean-z0 probe (that's the exact failure their Fig 1 documents).
2. Their FID-vs-RMSE tradeoff is a **third failure mode**, distinct from ours: meter
   *unreliable* at high noise (estimation problem) vs our meter *redundant* with the RF
   loss (information problem, the genre negative) vs probe-*hacking* (gaming, caught by
   the held-out guard). Three-way taxonomy worth keeping.
3. They note prior work finds **self-attention features best for structure estimation**
   — relevant to the DiT-block × feature controllability-map ambition (MASTER §4).

**What it does NOT contain:** the blind-vs-redundant boundary (their properties are all
RF-invisible spatial ones — they only see wins); any probe-hack guard; audio/RF domain.
Also names **Ctrl-U** (uncertainty-aware reward weighting) as the third family member —
unread, row in knowledge.md.
