# LionMuon: Alternating Spectral and Sign Descent for Efficient Training (2605.19811v3) — deep-read

Bolatov, Riabinin, Kornilov, Veprikov, Horváth, Takáč, Beznosikov (MBZUAI / BRAIn Lab / AIRI / Innopolis).
arXiv v3 19 Aug 2026. Code: github.com/brain-lab-research/lion-muon. PDF beside this note. **Read by C
2026-09-26 (§1, §3–§5 in full; proofs skimmed).**

## What it shows
- **LionMuon:** one momentum buffer per 2-D matrix; every step forms a Lion-style direction
  `Ĝ_t = β1·M_{t−1} + (1−β1)·G_t` (β1 = 0.9) and updates the buffer on a slower timescale (β2 = 0.99,
  "dual-EMA"). Every P-th step applies a Muon step (Newton–Schulz msign of Ĝ), all others an element-wise
  sign step. Needs a large lr ratio η_Muon/η_Lion ≈ 100 so the two step types have comparable effect.
  1-D params on AdamW. Optimizer state = Lion's (half of AdamW's).
- **SignMuon** (β1 = β2, single EMA) with alternation already beats pure Muon.
- **Results (LLM pretraining):** 124M GPT-2 and LLaMA on FineWeb / SlimPajama / WikiText-103, 64k steps:
  LionMuon P = 2 best or tied on all six (e.g. FineWeb GPT-2 3.501 vs Muon 3.526 vs Lion 3.579). 355M:
  SignMuon/LionMuon P = 2 3.045/3.054 vs Muon 3.063. 720M (under-trained, 5 tokens/param): SignMuon
  3.271 vs Muon 3.291; the dual-EMA edge did NOT reproduce there ("TPP, tuning, or seed effect").
  Gains 0.01–0.04 nats; single runs; gradient clipping kept on for all methods.
- **Analysis:** "alternation is what does the work; dual-EMA gives a small additional boost", and the
  dual-EMA benefit is "most visible when gradient noise is larger".
- **Theory:** convergence under **heavy-tailed noise** (bounded κ-th moment, κ ∈ (1, 2]); bounds
  interpolate between Muon's (nuclear-norm noise) and Lion's (ℓ1 noise) constants and predict the best P.

## FOR US / what stays ours
- **The dual-EMA momentum is the transferable piece, as a spike dampener.** Ours is single-EMA,
  β1 = 0.9 (optimizer.py:421). A 42× spike enters at weight 0.1 (4.2 vs ~0.9 from the rest) and dominates
  the step direction for ~15 steps. With dual-EMA (0.9/0.99) it dominates only the step it arrives on:
  0.01 of it enters the buffer (0.42 vs 0.99). Complements AdaGC (clip the input) rather than replacing it;
  cheap to implement and to A/B (β2 ∈ {0.99, 0.95} vs single-EMA 0.9).
- **Alternation with sign steps: low priority for us.** LLM pretraining from scratch, small gains, and it
  needs a second lr (×100 ratio) tuned; sign steps on LoRA factors are untested, and our DoRA magnitude
  history shows sign steps are risky on small-valued parameters. The FLOP saving is irrelevant at our
  scale (Newton–Schulz on rank-128 factors is cheap).
- **Heavy-tailed-noise assumption** is the right noise model for our flight-recorder spikes (lone,
  5–42×), and supports robustness mechanisms (clipping, slow buffers) over variance-based gating.
- Not diffusion, not fine-tuning, not an adapter setting: evidence of mechanism, not a validated recipe.
