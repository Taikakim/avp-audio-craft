# LoL — Longer than Longer: Scaling Video Generation to Hour (2601.16914)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). UCLA / ByteDance Seed / UCF (Cui,
Wu et al.). Video, but it **independently corroborates UltraViCo (2511.20123): RoPE periodicity →
collapse** — two papers, same root cause, two different training-free fixes. Together they're the
strongest loop-collapse lead in the sprint.*

**What it contains.** A training-free fix layered on AR streaming video generators. Failure mode
they name **"sink-collapse"**: at long horizons content abruptly reverts to the retained initial
("sink") frames, causing scene resets / cyclic motion. Root cause traced to **RoPE's periodic
structure**: at long horizons trigonometric phase **re-aligns** ("phase concentration" hits local
maxima), distant frames get near-identical embeddings, and **multiple attention heads homogenize**
(simultaneously over-weight sink frames). Fix: **multi-head RoPE jitter** — perturb each head's RoPE
base θ by a head-wise random factor `(1+σ·ε)`, breaking simultaneous cross-head phase overlap
(σ=0.8 best; jitter *all* heads). Enables ~12 h continuous video. Collapse occurs at *fixed latent
indices* regardless of prompt/noise; sink-collapse metric 73→17 (max), 30→4 (avg). Ablations:
repetition is **not** one RoPE dim; changing θ only *shifts* collapse, jitter *cures* it.

**Status vs our work — corroboration + a second fix.** LoL and **UltraViCo independently converge**:
long-horizon collapse coincides with **RoPE phase re-alignment**, prompt-independent, and both fix
it training-free (LoL breaks *inter-head* phase sync via jitter; UltraViCo re-concentrates attention
via logit decay). For SA3 this is a **two-pronged testable loop-collapse program**: (1) **diagnose** —
compute LoL's phase-coherence kernel `C(Δ)=|1/K Σ e^{jω_iΔ}|` over our sequence length and test
whether **loop points land on RoPE phase maxima** (prompt-independent structural cause), alongside
UltraViCo's dominant-amplitude-fraction check; (2) **fix** — try **per-head RoPE jitter** and/or
UltraViCo's attention-concentration, both inference-time, no retraining, with a σ/α-sweep. LoL's
**attention-head-diversity-as-early-warning** metric is also instrumentable on SA3. **The honest
limit (LoL's own):** it suppresses collapse at *local* phase maxima but provides **no long-term
memory** — it would *not* help SA3 recall long-range musical structure (motif return, key
relationships); that gap is exactly our "prompt arc" problem, which LoL leaves to future work. What
does NOT transfer: their AR streaming / KV-cache / causal-VAE sliding-window machinery is video-AR
specific (SA3 is non-AR full-sequence RF) — only the **RoPE-periodicity diagnosis + per-head jitter
remedy** port, and only if SA3 in fact uses RoPE (verify first). What remains ours: the SA3 phase
measurement, an audio collapse metric, long-range structure memory, and the disintegration gate.
