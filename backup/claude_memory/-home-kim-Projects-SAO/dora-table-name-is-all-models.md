---
name: dora-table-name-is-all-models
description: The "DoRA table"/"DoRA rows" covers ALL models, not just DoRA arms — the misleading name is deliberate, never rename it
metadata:
  type: project
---

`eval/dora_table.html` + `eval/clap_dora_aggregate.csv` (built by
`eval/build_dora_table_page.py`) are **the all-models hyperparameter × metric table** —
adapter_type spans dora / lora / full-FT, ~972 model×checkpoint rows, 60+ columns
(hyperparams + CLAP degeneration + Audiobox + DSP), with a pinned dataset-baseline strip.

**The "DoRA" in the name is a misnomer, and it is deliberate. Do NOT rename it.**
Kim direct, 2026-09-02: *"it's actually all models, but changing the name might cause
issues with conversation histories and fact-finding."* Months of chat logs, journals, DMs
and DISCOVERIES entries call it "the DoRA table" / "the DoRA rows"; renaming the file, the
page, the CSV or the phrasing breaks every one of those references — and breaks the
symbol-based log search that attribution and fact-finding depend on
([[run-params-provenance]] leg 3 of the three-leg search).

**How to apply:** when asked to review, extend or tidy this table, keep every existing
name. If the misleading name needs addressing, add a SUBTITLE on the page saying it covers
all models — never a rename. Same reasoning applies to any long-lived artifact whose name
appears throughout the logs.

Companion surface: the big **model matrix** (`~/evals_aac/model_matrix.html`, rendered
clips per checkpoint) and `eval/model_census.html` (every checkpoint we own, local + LUMI).
