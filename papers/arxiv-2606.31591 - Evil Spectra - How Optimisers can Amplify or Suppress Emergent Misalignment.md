# Evil Spectra: How Optimisers can Amplify or Suppress Emergent Misalignment

- **arXiv:** 2606.31591v1 (2026-06-30, cs.LG)
- **Authors:** Jason R. Brown, Patrick Leask, Lev McKinney (Astra Fellows; Cambridge, Durham, Toronto)
- **PDF:** `papers/arxiv-2606.31591.pdf`
- **Read by:** KUANG, 2026-10-17: main text read; appendices (sweep tables, dynamics grids, regulariser details)
  skimmed.

## What it contains

- LoRA (rsLoRA rank 32, alpha 64) fine-tuning of Qwen3 / Gemma 3 / Llama 3 on "emergent misalignment" datasets
  (insecure code, bad medical / financial / extreme-sports advice); alignment judged by GPT-4o on 142 questions.
- Optimizer is the largest factor: misalignment 5.3% (Muon) to 37.0% (Lion), 7x; model scale and family barely matter.
  Log training loss explains 74% of alignment variance; stratifying by optimizer raises adjusted R^2 to 0.94.
- **Spectra of the effective adapter BA** (Qwen3-8B, 252 layers): Muon stable rank 17.1 of 32, condition number 1.9;
  Adam/AdamW 2.4 / 22; Lion 2.3 / 27; SGD 1.6 / 175. Among adaptive optimizers, flatter spectrum = better alignment.
- **Spectral regulariser** R = ||BA||_F / ||BA||_* - 1/sqrt(r) (scale-invariant), lambda 3.0: alignment recovers
  (Adam +6.6, Lion +8.0, Muon +2.1 points) for 0.000-0.013 nats of training loss; SGD gets slightly worse.
- Much of the damage happens after the training loss has converged.

## What it does not contain / caveats

- LLM safety, not audio; LoRA only (no full fine-tuning); one judge; the spectral analysis and regulariser on one model.
- Lion ran with fp32 state and at batch 32 (designed for 4096+), a confound the authors note.

## For us

- The transferable idea: an optimizer shapes the spectrum of the learned change, and a flat spectrum spreads the change
  instead of pushing a few directions hard, with less collateral damage to what the training did not target. Our
  analogues: FiLM leaking training-set style, LatCH being "transparent", F6 "the optimizer is a style tool".
- Cheap test, no training: stable rank / Frobenius-to-nuclear ratio of the effective adapter change (DoRA BA, FiLM
  adapter weights minus init) across existing checkpoints, against the CLAP style drift measured in E7-E11
  (test plan section P, adapter audit). Use BA, not A and B separately.
