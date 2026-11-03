---
name: sao-checkpoint-analysis-vs-votes
description: "Concordance table built joining trajectory/descriptor/vote data; 113 fully-joined rows, ~204 real gaps remain, design and location"
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-09-22T07:06:57.560Z
---

Built and committed `eval/build_concordance.py` (commit `4d7d2b3`, THE-FINN, pushed
2026-09-22), joining three previously-unlinked evaluation data sources for the SAO model
fleet:

- `checkpoint_analysis_summary.csv`/`.jsonl` — Antigravity's 2000-checkpoint trajectory
  sweep, keyed by `run_name`+`epoch` (`frob_norm_B`, `velocity_per_1k`,
  `directional_cosine`, `nan_count`)
- `eval/clap_dora_aggregate.csv` — acoustic/algorithmic descriptors, keyed by
  `model`+`ckpt`
- `eval/ratings_export_*.jsonl` + `eval/curated_votes_2026-09-08.jsonl` — pairwise A/B
  votes, keyed by `model_a/ckpt_a` vs `model_b/ckpt_b`, tagged per `question_id` axis
  (production/interesting/spectral_image/structure/clarity_meaning/top_end/preference)

Join is exact-match only on `(model, ckpt)`, following the model census's "false
presence is worse than false absence" philosophy (`eval/build_model_census.py`) — a
wrongly-matched arm is worse than an unmatched one. Output: `eval/concordance_table.csv`
and `.html`, 2069 total rows, 299 with trajectory+descriptors, **113 with all three
sources**. The remaining ~204 gaps are genuine coverage gaps, reported loudly rather than
guessed at.

**Wandb-hash resolution:** 10 of ~212 unmatched `run_name` wandb hashes were resolved to
human-readable run names by Antigravity (see [[external-agent-antigravity-modular-trainer]])
in response to a targeted question relayed from Kim, and are hardcoded as
`RUN_NAME_ALIASES` in `build_concordance.py` (e.g. `2ankrkoh` → `sa3-goa-dora-47s`,
`z18fy24b`/`e3hun0v6` → `dora128_mix3_nodas_20260918_231801`). This gained +14/+6 joined
rows. The remaining ~200 unmatched hashes are still an open gap — if more of Antigravity's
run-name mapping becomes available, extend `RUN_NAME_ALIASES` rather than re-deriving it.

**Why it matters:** this is the tool for Kim's stated goal of cross-referencing checkpoint
trajectory behavior (fast-learn / glitch-boundary signals) against vote outcomes and
descriptors. See [[sao-modular-trainer-flags-unverified]] for a caveat that affects any
conclusions drawn from it involving certain modular-trainer flags.

**How to apply:** point Kim or a fleet member at `eval/concordance_table.html` for any
"how do checkpoint dynamics line up with votes/descriptors" question rather than
re-deriving the join. Don't assume full coverage — check `has_trajectory`/
`has_descriptors`/`has_votes` columns before treating a row's absence as meaningful.
