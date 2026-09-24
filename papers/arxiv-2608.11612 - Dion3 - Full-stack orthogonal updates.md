# arxiv-2608.11612 - Dion3 - Full-stack orthogonal updates

**Reading depth:** abstract + contents page only (C 2026-09-22).

**What it contains:** Gram Newton-Schulz, symmetric GEMM kernels, fractional updates: Muon step cost 26×→4× AdamW on a sharded 7B.

**For us / what stays ours:** The 26× is a distributed cost we don't pay. Gram-NS fits our 12288×128 shapes; measure the optimizer's share of step time first.
