# arxiv-2608.11612 - Dion3 - Full-stack orthogonal updates

**Reading depth:** abstract + contents page (C 2026-09-22); **targeted read of sections 6-8 and appendix B.2
(update rule, finite precision, learning-rate transfer, model quality, fp16 vs bf16) + the microsoft/dion code
(`dion/nordion2.py`, `dion2.py`, `normuon.py`, origin/main 7692479) by KUANG 2026-10-16.** Kernel, Gram Newton-Schulz
proofs and megabatching benchmarks not re-read. PDF: `papers/arxiv-2608.11612.pdf`.

**What it contains:** Gram Newton-Schulz, symmetric GEMM kernels, fractional updates: Muon step cost 26×→4× AdamW on a
sharded 7B.

**Update rule (Dion3 = NorDion2), from the paper and the code:** momentum accumulates M <- M + G; select the top
fraction f of ROWS by L1 norm of M (or columns if smaller and unsharded); orthogonalise only that submatrix; NorMuon
row normalisation on the selected rows (fp32), rescaled to the input's Frobenius norm; update only those rows;
error feedback = decay only the selected rows of M by mu, so unselected rows keep accumulating until picked. lr scales
as 1/sqrt(f). Recommended f = 1/4 or 1/8; random selection was "not much worse". At 1B-14B (ClimbMix, MXFP8) f < 1
beat NorMuon slightly (best f = 1/8 at 1B; -0.027 val loss at 14B).

**Finite-precision lessons (section 6):** the initial implementation underperformed because row selection broke the
fused weight update into several bf16 up/down casts; fixed with one fp32 computation of (1 - eta*wd) W - eta O, cast
once (custom Triton kernel). NorMuon normalisation must run in fp32. Newton-Schulz itself runs fine in half precision;
they default to fp16 over bf16 (more mantissa, the range suffices). Naive Gram NS in half precision diverges (spurious
negative Gram eigenvalues) without restarts.

**For us / what stays ours:** The 26× is a distributed cost we don't pay. Gram-NS fits our 12288×128 shapes; measure
the optimizer's share of step time first. Since measured (WINTERMUTE 2026-10-16, FiLM, 73 matrices): ModularOptimizer
+320 ms per update vs FusionOpt +100 ms, the difference being fp32 NS one matrix at a time; bf16 NS and batching
same-shape matrices come before row selection. The precision lessons are the basis of docs/TRAINING.md F21 and of
ModularOptimizer `state_dtype="fp32"` (audio-tools-avp feature/modular-opt-c-series).
