---
name: prune-resolve-best-epoch
description: "Before pruning checkpoints, resolve each run's best epoch from its log; never assume a _best.pt exists"
metadata:
  node_type: memory
  type: feedback
  originSessionId: b207d8c1-afa9-47b8-bbe0-60db9d0c4899
  modified: 2026-10-23T00:06:25.715Z
---

When pruning per-epoch checkpoints with a "keep _best.pt + every Nth + last" rule, first find each run's best-val epoch in its train log and keep that file too. Runs trained with `--save-every-epoch` and without `--save-best-only` never write a `_best.pt`.

**Why:** on 2026-10-23 the Mantu/latch_sweep prune deleted 884 files (89 GB, approved by the owner). 54 runs had no `_best.pt`, and 13 of them lost their best-val epoch for good. Real losses were the air O1–O4 and O6 heads; for example, O4's best was ep9 at 0.0272 and the best kept is ep5 at 0.0394. The deleted paths are listed in latch_sweep/PRUNED_2026-10-23.txt.

**How to apply:** for every run dir, parse val per epoch from the log (the `epoch N/M` line, then `val=`), add argmin to the keep set, and print the "no _best.pt" dirs before deleting. Btrfs drives (Mantu) report freed space only after `sync`.
