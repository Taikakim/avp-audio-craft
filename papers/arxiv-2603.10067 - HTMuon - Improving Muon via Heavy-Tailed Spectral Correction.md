# HTMuon: Improving Muon via Heavy-Tailed Spectral Correction (2603.10067v2) — read by CONTINUITY 2026-10-21

Pang, Fang, Liu, Deng, Hsiung, Yu, Yang. Dartmouth (Yaoqing Yang's group), Microsoft, ICSI / UC Berkeley, Meta. v2 dated 21 May 2026.
Funding: DARPA AIQ and DIAL, US DoE, Lambda AI. Code: github.com/TDCSZ327/HTmuon (MIT, last commit 2026-05-02).
PDF: `arxiv-2603.10067 - HTMuon - Improving Muon via Heavy-Tailed Spectral Correction.pdf`.
**Read:** pp. 1–18 and 24–31 (main text, theory statements, LLM/vision results, all ablations, appendix B, start of C). **NOT read:** the proofs
(pp. 19–23) and the hyperparameter tables 18–22 (pp. 32–37). The venue is not stated in the PDF; an external summary called it "ACL Findings", unverified.
The pedigree is the HT-SR (heavy-tailed self-regularization) line of Martin and Mahoney; Yang co-authors with Mahoney, but Mahoney is not an author here.

## What it contains
- **Idea:** Muon sets every singular value of the momentum to one. Under HT-SR theory better-trained nets have heavier-tailed weight spectra, so use
  `O = U S^p V^T` with `p = 0.125` (p=0 is Muon, p=1 is SGD with momentum). Exact SVD per step; cheaper forms are "every k steps" and `HTMuon_NS`
  (`NS5(M) @ (M^T M)^(p/2)` via Newton-Schulz roots).
- **Results (perplexity, lower is better, Muon → HTMuon):** LLaMA-60M 28.80 → 27.88, 135M 22.23 → 21.25, **350M 16.81 → 16.79**, 1B 14.33 → 14.17
  (HTMuon every 5 steps), GPT-2 small 22.46 → 22.20; CIFAR/ViT accuracy +0.1 to +0.3. The gain **shrinks with scale**. HTMuon + NorMuon adds a further 0.14–0.33.
- **Theory:** equivalent to steepest descent under a Schatten-q norm; convergence bound with the same O(eps^-4) sample complexity as Muon and SGDM.
  So theory promises no rate advantage over Muon; the case is empirical.
- **Cost:** 135M wall-clock Muon 1.40 h, HTMuon 6.57 h, HTMuon_NS 2.17 h (Table 10). Stated limitation: nothing above 1B.
- **Ablations worth keeping:** `HTMuon_HT` (replace the spectrum with a fixed `i^-0.25`, ignoring the data) still beats Muon by 0.28 / 0.58. Muon_NS beats Muon_SVD (Fig. 1),
  i.e. NS5's imperfect spectrum is already partly "soft". p grid (Table 14): p = 0.1 27.91, **0.125 27.88**, 0.2 28.56, **0.25 29.97 (worse than Muon's 28.80)** on 60M.

## FOR US — what to doubt, what stays ours
1. **Muon's baseline sits on the grid edge.** Table 11: Muon's best cell is the LOWEST learning rate tried (0.01) at both 60M (28.80) and 135M (22.23); NorMuon at 135M likewise.
   HTMuon's best cells are interior (0.03, 0.025). So Muon's own optimum may lie below the grid, and part of the headline gain could be a learning-rate effect. They also
   apply Muon to the embedding and output layers, which is not the usual recipe.
2. **Smaller steps are a plausible confound (my inference, untested).** `S^p` of raw singular values below one, and the fixed `i^-0.25` spectrum, both shrink the update relative to
   Muon; Fig. 7 shows HTMuon weights with smaller spectral and Frobenius norms, which they read as better generalisation but is also what smaller effective steps would produce.
   A Muon run at lower lr, or HTMuon with its update RMS matched to Muon's, is the control the paper lacks.
3. **No seeds or error bars** in the tables I read; the 350M gain is 0.02.
4. **The repo default is `--power 0.25`**, which their own Table 14 shows is worse than Muon. Check the p used by any reproduction.
5. **Regime mismatch.** All pretraining from scratch at LLM or CIFAR scale, nothing in fine-tuning, small heads or audio. The p was tuned on LLaMA only and reused elsewhere (ImageNet used 0.03125).
6. **At p = 0.125 the spread of singular values changes little:** 100^0.125 = 1.8x, about NS5's own 0.7–1.3 band. Our NorMuon row-unit mode also removes scale information, so how `S^p`
   would sit on top of it is an open design question; the paper adds HTMuon to NorMuon, but only for LLaMA.
- **Verdict:** a mild, plausible idea with mismatched evidence. Parked as **EXPERIMENTS E15**, gated on `docs/modular-opt-test-plan-2026-10-17.md` sec. P. First cheap check is a probe, not a run:
  apply `S^p` to the momentum and see whether the held-out loss moves at matched update RMS.
