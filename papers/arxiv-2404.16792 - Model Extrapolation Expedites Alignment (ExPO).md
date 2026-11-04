# Model Extrapolation Expedites Alignment (ExPO) (2404.16792)

Zheng (Tsinghua CoAI and UCLA), Wang (UIUC), Ji (UIUC), Huang (Tsinghua), Peng (UCLA). arXiv v5, May 30, 2025; no venue in the PDF.
Code: github.com/chujiezheng/LLM-Extrapolation (not reviewed).
PDF: `arxiv-2404.16792 - Model Extrapolation Expedites Alignment (ExPO).pdf` (gitignored; added locally on the desktop).
**Read:** the full PDF, by a subagent for KUANG on November 4, 2026. The text extraction dropped the Greek letters and interleaved some tables, so the tables were rebuilt from each row's "+delta" and the numbers the text quotes. One ablation multiplier is garbled and flagged.

## What it contains

**Method.**
- θ2 = θ0 + (1 + α)(θ1 − θ0), where θ0 is the supervised fine-tuned (SFT) model and θ1 the same model after "moderate" preference alignment (DPO, RLHF and others), started from θ0.
- In our notation, w = 1 + α, so our w ≈ 1.25 is their α ≈ 0.25.
- One uniform α for every parameter. Per-module α is left as future work.
- α is chosen by the best reward-model score on 1 000 UltraFeedback dev prompts: a grid over 0.1–0.5 for released models, a wider search in the controlled study.

**Argument.**
- Interpolation between θ0 and θ1 improves monotonically (figure 1). A first-order Taylor step says continuing along Δθ keeps improving while (1 + α)Δθ "stays small".
- There is no curvature term, and it does not explain why α = 8 (a 9x step) works.

**Controlled study** (zephyr-7b recipe, UltraFeedback, AdamW at 5e-7, 478 steps for a full run; AlpacaEval 2.0 with a GPT-4 Turbo judge):
- DPO stopped at 20 % of the steps, plus ExPO (α 2.5), reaches length-controlled (LC) win rate 21.3 %, against 17.3 % for the full run.
- The optimal α falls as training lengthens: 8.0 / 2.5 / 0.5 / 0.3 at 10 / 20 / 40 / 100 % of the steps. The paper reports about 75 % less compute.
- **Size of the change (table 1):** SFT→DPO normalized change 6.3e-6, against 2.0e-4 for pretrained→SFT.

**Released models.** Twelve aligned 1.8B–70B models (zephyr, tulu2, starling, internlm2, snorkel, llama3-iter):
- All improve.
- LC win-rate gains are small (+0.3 to +4.5 points) next to the raw win-rate gains (up to +10.1).
- Optimal α is 0.1–0.5, several of them at the edge of the 0.5 grid.
- Six other alignment algorithms (IPO, SimPO, KTO and others) mostly gain too. Mistral KTO gains nothing.

**Ablations.**
- **Length.** Training on length-biased preference data caps the gain, because ExPO amplifies the spurious direction. Even on clean data ExPO roughly doubles response length.
- **Training configuration.** More epochs or a higher learning rate shrink both α and the gain; 3 epochs gives none. AdaGrad, the slowest to converge, extrapolates best (α 15).

**Failures.**
- **Pretrained→SFT as the pair:** "usually cannot improve", and can collapse (no end-of-sequence token, special tokens in the output). The paper blames the larger learning rate and more steps, the changed chat template and knowledge injection.
- **Storm-7B** (3 rounds of iterative DPO) collapses at α = 0.1.
- Past the optimum, quality drops sharply and outputs run on.

**Alignment tax.** ExPO amplifies whatever alignment did to benchmarks: TruthfulQA rises further and GSM8K falls further.

## How far the evidence reaches

- **Statistics.** One training run per configuration, one sampling seed, no confidence intervals.
- **Judges.** α is chosen with a reward-model proxy and evaluated by GPT-4 judges, which reward length; raw win rates overstate the gain.
- **Scope.** Text LLMs only, full-weight changes only, no diffusion models, no other modalities.
- **Failures** are reported as anecdotes, not rates.

## For us

**EXPLAINS AND BOUNDS OUR WEIGHT-PUSH OBSERVATION.**

- **What their conditions predict.** ExPO helps when the two checkpoints share an initialization, the change is small, and training stopped short along a good direction. It fails on large changes and on over-trained or reward-overfit runs.
  - Our full fine-tunes are large changes: the drone-sweep online weights moved about 20 % of the base norm in under 6 000 steps (WORKLOG, October 16, 2026). That is the regime where ExPO's pretrained→SFT pair collapsed.
  - So a clean push at w ≈ 1.25 on SA3 is not what this paper predicts. The likely difference is architectural (pre-norm RMSNorm and per-head q/k RMS norm absorbing scale; see the Grokfast sidecar). This is inference and untested.
- **"Did not collapse" is not "better".** Their length result maps to whatever spurious direction our fine-tunes learned: loudness, brightness, artifacts, or the training-set style (E7). The w ladder needs a meter independent of the training signal: listening, onset density, CLAP style drift, loudness-matched comparison.
- **Per-group α is open.** Neither ExPO nor anything else indexed here tests which layers tolerate extrapolation. The group-restricted w ladder (the stream-writing layers vs the rest) would be a new result.
- **The optimal α shrinks with training length.** If the w ladder is run, run it on an early and a late checkpoint of the same fine-tune. A larger tolerable w on the early one would match ExPO.

## What stays ours

Model, objective and evaluation are ours. What we take: the formula and its α ≈ w − 1 mapping, the "shrinks with training length" prediction, and the warning that extrapolation amplifies spurious directions as well as wanted ones.
