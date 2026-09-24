# arxiv-2607.16268 - PsiLogic - Chaos-Aware Active Cancellation for Adam with a Fair Cross-Domain Benchmark

**Reading depth:** abstract only (C 2026-09-24).

**What it contains:** Adam plus an active cancellation term, gated by a dual-EMA 'chaos detector' on scale-normalised gradient norms: strong damping while unstable, fading as training stabilises. Wins 3 of 4 arenas; diffusion tied with Adam/AdamW (p=0.49); 1.2–1.8× wall-clock.

**For us / what stays ours:** Kim recalled it as our 'adaptive damping for AdamW'. Would NOT have prevented the goa3 NaN: the magnitude drift happened in a stable phase, when its detector is quiet.
