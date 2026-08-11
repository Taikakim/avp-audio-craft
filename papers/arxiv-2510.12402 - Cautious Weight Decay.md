# modded-nanogpt cautious work (arXiv:2510.12402)

**Relevance to SAO: bounds the prior art around our CautiousMuon finding (claim 2) —
their cautious mechanism is weight-decay-only, NOT the mask interaction we found.**

The speedrun-community cautious-optimizer work formalized here applies caution to
**weight decay only**. Our claim 2 (keep≈0.53 + the 1/√keep gain-inflation correction,
the cautious-mask × Muon-orthogonalization incompatibility and its degradation
mechanism) is "highly novel, currently unpublished" per the verified Gemini verdict —
and CONTINUITY's citation pass found Gemini's "community reported decreased sample
efficiency" line was MISREMEMBERED: the real discussions (C-Optim PR #11,
parameter-golf PR #1381) report *gains*, and live outside modded-nanogpt. Nobody
reported our degradation mechanism at all → claim 2 *strengthened* by verification.
The before/after-Newton-Schulz mask-placement dilemma is real in the community.

**What it does NOT contain:** the keep-fraction statistic, the 1/√keep correction, the
mask×orthogonalization analysis (all ours, in the fusion_opt cautious component +
sonar work, SAT fork).

— Abstract written from CONTINUITY's verified citation pass (2026-07-03); PDF not yet
deep-read. Verified: cautious scope is weight-decay-only.
