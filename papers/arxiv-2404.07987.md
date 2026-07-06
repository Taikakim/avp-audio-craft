# ControlNet++ (arXiv:2404.07987, ECCV 2024) — Li et al.

**Relevance to SAO: PRIOR ART for the FusionCC loss mechanism — we independently reinvented it.**
**Status: DEEP-READ (method sections, 2026-07-03, THE-FINN).**

Cycle-consistency training for controllable diffusion (vision). Mechanism, confirmed
mechanism-identical to FusionCC:

- **Disturb consistency** (their Fig 4b): add small noise to *training* images (not
  sampling from scratch), **single-step denoise** to x0' (Eq 7 ≡ our `rf_z0_hat`), pass
  through a **frozen discriminative reward model**, penalize disagreement with the input
  condition (Eq 8). Rationale: naive full-trajectory reward needs ~340 GB grad storage
  at 50 steps — the one-step trick is what makes it trainable. Same economics drove ours.
- **t-gated exactly like C's cc block** (Eq 9): `L_total = L_train + λ·L_reward if
  t ≤ t_thre, else L_train`. Their windows: **200/1000 steps for edges, 400/1000 for
  depth** (per InnerControl's recap) vs our `t < 0.5`. Note the scaling: the more
  *structural/global* the metered property, the *wider* (noisier) the window needed.
- **Frozen meter + frozen base model, train only the adapter** — same as ours. They also
  note reward-loss-alone causes distortion; diffusion loss must stay in the mix (ours does).
- Metering happens in **pixel space after decoding x0'** (UperNet/DPT etc. as meters);
  our FusionCC decodes to audio for librosa onset, and C's genre distillation moved the
  meter into **latent space** (`cc_probe`) — a variant they don't have.

**What it does NOT contain:** (1) the blind-vs-redundant boundary condition (2026-07-03,
MASTER §4) — they never ask whether the meter carries information the training loss
lacks; all their conditions (seg/edge/depth) are RF-invisible-fine-grained, so they only
ever saw wins. (2) Any probe-hack guard — no held-out-dim monitoring. (3) The
compliance-vs-cheating distinction. Our unpublished contribution stands; their paper is
the mechanism's origin + our two wins are confirmations in RF/audio.

*Cite with InnerControl (arXiv:2507.02321; extends to all-timestep via feature probes)
and Ctrl-U (uncertainty-aware reward weighting — unread, see knowledge.md).*
