# Hook pilot P2: hmr vs CFG (mechanism-2 test) — 2026-07-22

M2 (conditional averaging) predicts hook_melodic_ratio FALLS as CFG rises; M1 (gradient
share) alone predicts flat. Result over the 10 families with both cells scored (w1.0):

**hmr falls cfg7→cfg16 in 8/10 families** — base .102→.000, base_ptm .101→.000,
dora16_newstack .254→.203, fp32cmp_avp .151→.039, fp32cmp_goa .137→.044,
fp32cmp_goa_PTM .260→.069, fullft_goa_t4096 .226→.163, longctx .120→.000.
Exceptions: fullft_avp flat (.084→.085), fullft_goa_t256 rises (.062→.284, n small).
Pedal occupancy RISES with cfg in 8/10 (melody collapses toward drone as guidance grows).
No-lead rate 32–84% across ALL cells (corpus: ~5%).

VERDICT: **M2 (CFG/conditional averaging) is the dominant, actionable mechanism** — the
higher the prompt-mean pull, the less melodic commitment survives. M1 (9.3% variance
share) remains the training-side floor. Full data: eval/hook_renders.jsonl (601 rows,
per-cell aggregation per Kim's convention).

