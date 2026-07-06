# "Backbone" trajectory-PCA paper (arXiv:2602.23696)

**Relevance to SAO: the nearest prior art to our checkpoint-trajectory PCA — and
measurably a DIFFERENT (weaker) statement than ours.**

Reports that 60–80% of optimizer *displacement* concentrates in a low-dim subspace under
**uncentered** PCA, and attributes it to optimizer-induced structure. Our finding
(checkpoint-stats library, claim 5 of the novelty brief): **centered** PCA, 88% of
*variance*, and the **PC2-turnover as a loss-blind drift proxy / geometric early-stopping
signal** — Gemini's report misdescribed our PCA as uncentered; it is centered, which makes
the planarity claim stronger, not weaker (CONTINUITY, 2026-07-03 11:09).

**What it does NOT contain:** the PC2-turnover early-stop signal ("exceptional empirical
finding, not documented" per the verified verdict); any connection to control-head
drift/EMA damping (MASTER §4, 2026-06-29).

— Abstract written from CONTINUITY's verified citation pass (2026-07-03); PDF not yet
deep-read. Verified: paper is real; uncentered-displacement vs our centered-variance
distinction confirmed.
