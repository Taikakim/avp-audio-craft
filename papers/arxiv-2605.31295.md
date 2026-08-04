# Latent Space Disentanglement via Activation Steering for Symbolic Music (2605.31295)

*Project-POV abstract, THE-FINN 2026-07-30. **Confirmation-based, not yet a full deep-read** —
written from CONTINUITY's replication (task #58, 2026-07-30) + the PDF title/scope; a proper
deep-read of the PDF is a tracked to-do. Graduated untested→CONFIRMED-strong on the
paper-verdicts page the same day.*

**What it contains.** A symbolic-music activation-steering method for **disentangling entangled
concept directions**: when you want to steer along concept A but A overlaps a second concept B in
the residual stream, project A **orthogonal to B** (Gram-Schmidt, per (σ, layer)) before adding
it, so steering A doesn't drag B along. The paper's domain is symbolic music; the mechanism is
architecture-agnostic (it's linear algebra on activation directions).

**Status vs our work — CONFIRMED strong-form on SA3 audio (C, task #58, 2026-07-30), stronger
than the paper.** Naively summing two anti-correlated directions (dark + onset, cos ≈ −0.3,
shared layer) **disintegrates** the clip; Gram-Schmidt-projecting one orthogonal to the other
strips ~5% of its norm and **100% of the buzz** → gate-clean **dual** steering with both axes
moving (dark ~79% of solo authority; onsets recovered 0.7→2.0/s). Mechanism insight: the
disintegrating "poison" lives in the **shared subspace**, and GS removes not just the
interference but the direction's entire disintegrating component. **Ports directly** to any
multi-concept `sa3_control` / LatCH steering — orthogonalize concept directions before summing
them. Full evidence: C's `concept_steering/orthogonal_ab` commentary.json + her 2026-07-30
journal. What remains ours: the disintegration-gate that made the win *legible* (naive-sum buzz
caught vs GS-arm clean), and the SA3-specific (σ, layer) placement.
