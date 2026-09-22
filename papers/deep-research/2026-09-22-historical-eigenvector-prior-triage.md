# Triage — "Spectral Geometry and Curvature-Aware Preconditioning: Enhancing the Mousse Optimizer via Historical Eigenvector Trust Regions"

> **Provenance.** Kim's research agent, on Kim's idea (2026-09-22): can the hundreds of checkpoints
> we have already trained on the same corpora serve as a prior for the optimizer, giving "more
> trust" to some eigendirections? Raw report: `Historical Eigenvector Trust Regions for Mousse.pdf`
> (12 pp.). Triage: CONTINUITY same day, full read.
> **Citations: not verified, and weak** — 6 works cited: the Mousse arXiv page, an OpenReview PDF, a
> ResearchGate upload ("Pro-KLShampoo"), a personal blog, a Connected Papers graph, and a GitHub README.

## Verdict
The premise is plausible and worth one cheap test. The report is **not safe to implement from**:
its core formula is inverted, its main theoretical link does not hold for our checkpoints, and its
results table describes experiments nobody ran.

## What is wrong (load-bearing first)
1. **Unwhitening exponent inverted.** §4.2 unwhitens with L^{+1/2}…R^{+1/2}; §7.2 with L^{+1/4}…R^{+1/4}.
   Mousse unwhitens with the SAME NEGATIVE power: dW = −L^{-1/4} msign(L^{-1/4} G R^{-1/4}) R^{-1/4}
   (Algorithm 1 line 9, checked against the PDF 2026-09-22; `../arxiv-2603.09697 - Mousse*.md`).
   A positive power undoes the damping and makes steps BIGGER in high-curvature directions, the
   opposite of the method. §4.2 and §7.2 also disagree with each other (1/2 vs 1/4).
2. **Cov(θ) ∝ H⁻¹ misapplied (§5.2, §6.3).** That relation describes the spread of iterates around
   ONE minimum (Laplace / SGD stationary noise). The spread of *final-minus-init displacements across
   different runs* records where each run went (the task direction), not the curvature. So the report's
   "high historical variance = flat, safe valley" does not follow.
3. **Our own data says an uncurated prior points at the pathology.** 2026-08-18 `eval/task_vector_gram.py`
   on the goa arms: healthy arms agree (consensus cosine 0.72); degraded arms put 20–30% of every
   matrix's ΔW energy into ONE direction, and it is the SAME direction across bad arms
   (`lumi_runs/analysis/task_vector_gram_goa_2026-08-18/`). A prior built from "hundreds of checkpoints"
   would give the most trust to exactly that direction. Any prior must be built from arms judged good by ear.
4. **Heterogeneous history.** Our checkpoints differ in corpus, rank, optimizer, LR, LoRA vs DoRA vs
   full-FT. LoRA factors are not comparable across runs (random A init; B·A = (BX)(X⁻¹A) gauge), so the
   history must be expressed as ΔW = B·A (or DoRA's ΔW_eff), which is what task_vector_gram.py uses.
5. **Memory as written is impossible for us** (L_hist is m×m; our LoRA tensors are up to 12288 wide —
   a 12288² eigh measured 7.23 s, ×24 tensors per step). But the history has rank ≤ K (number of
   checkpoints), so a truncated basis from an SVD of the stacked ΔW is cheap. That part is fixable.
6. **§9 / Table 2 are invented.** "Prior-Informed Mousse: Maximum speed / High fidelity / Robust
   stability" on MLIP force supervision — no such experiment exists in the cited sources or anywhere
   we know of. §8's account of NorMuon (as "stripping soft-augmentation") also misdescribes it:
   NorMuon is per-row normalisation after Newton-Schulz, and it was ACTIVE and well-behaved in
   audition_160ep_2026-09-22-b.

## What survives — the cheap falsifiable test (not yet built)
For one layer: take the top-k left singular subspace of stacked ΔW = B·A from GOOD historical arms of the
same base; compute a new run's gradient-covariance top-k subspace (`stable-audio-3/scripts/wide_covariance_probe.py`
already produces the spectrum); measure subspace overlap (mean squared cosine of principal angles)
against the random baseline k/n. Overlap ≫ k/n ⇒ the history carries curvature-relevant signal and a
subspace prior (initialising the preconditioner, or a subspace-weighted step) is worth an arm.
Overlap ≈ k/n ⇒ the idea dies for ~1 h of CPU. Note the soups/task-vector work already exploits the
"where good runs went" information as a WARM START; the test is whether it also says something about
the optimizer's geometry.
