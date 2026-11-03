---
name: board-representative-cells
description: "Which model-matrix cells count as \"representative\" when sampling for evals — Kim's convention"
metadata: 
  node_type: memory
  type: project
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
  modified: 2026-07-22T13:48:20.519Z
---

Kim (2026-07-22, correcting my cfg7/w100-only pilot sample): the representative cells of
a model on the matrix board are **(w1.0, cfg7) AND (w1.0, cfg16), and often also (w1.5,
cfg7) + (w1.5, cfg16)**. Any per-model summary stat or stratified eval sample should cover
those four cells, not just cfg7/w1.0 — cfg16 shows the prompt-locked behavior and w1.5 is
Kim's habitual listening strength (historically "almost universally better", see the
dora-alpha damping finding).

**And aggregate per CELL, never pooled per model** (Kim, same day): statistics are
reported per (model, weight, cfg) group — "one set of statistics for weight 1, cfg 7 for
each model, etc." — because the cfg/strength axes change behavior enough that pooling
across them hides exactly the differences the board exists to show.
Related: [[sao-agent-handle-continuity]].
