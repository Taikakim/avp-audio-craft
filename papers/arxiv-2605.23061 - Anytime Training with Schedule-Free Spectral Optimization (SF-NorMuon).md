# Anytime Training with Schedule-Free Spectral Optimization (SF-NorMuon)

- **arXiv:** 2605.23061v2 (2026-09-25, cs.LG)
- **Authors:** Anuj Apte, Pranav Deshpande, Niraj Kumar, Shouvanik Chakrabarti, Junhyung Lyle Kim (JPMorganChase)
- **PDF:** `papers/arxiv-2605.23061.pdf`
- **Read by:** KUANG, 2026-10-16/17: read in full (main text, appendices A, B, C.5, D-G incl. the reference
  implementation); convergence proofs C.1-C.4 skimmed.

## What it contains

- **SF-NorMuon (Algorithm 1):** momentum M (mu), polar factor P, NorMuon row second moment v = EMA_beta2(mean over
  columns of P^2), P / (sqrt(v) + eps), then step eta_hat = 0.2 * eta * sqrt(m*n) / ||P||_F (update RMS 0.2*eta per
  element, Adam-matched), **weight decay at the fast iterate z**, Schedule-Free averaging with c = gamma_t^2 / sum
  gamma^2. 1-D parameters on Schedule-Free AdamW. Reference code has NS in bf16.
- **Results:** 125M and 772M LLaMA-style LMs (FineWeb, batch 512 x 1024), 1-8x Chinchilla: matches per-horizon tuned
  AdamW with one configuration; within 0.025-0.036 nats of cosine NorMuon; 35-52% fewer steps than SF-AdamW. ViT-B/16
  on ImageNet: best at every milestone. ~2% step overhead.
- **Ablations:** no momentum (mu = 0) 3.28 vs 3.14 loss (large); no row normalisation ~12% slower.
- **Weight decay:** without it, or with decay at y, Schedule-Free runs diverge over long horizons; decay at z is stable
  (Lemma 3.1 bound, Lemma 3.2 steady-state weight RMS).
- **Appendix D, best settings (125M):** lr 0.01; 2-D (beta1, beta2) = (0.9, 0.95) where beta1 is the SF interpolation;
  mu 0.8 (ViT 0.9); 1-D (0.95, 0.99); wd 0.05 at z (ViT 0.25); warmup 2000 steps; grad clip 1.0; no schedule.

## What it does not contain / what remains ours

- No small-batch regime (batch size not swept), no fine-tuning, no audio, no Shampoo, no from-scratch small heads.

## For us

- Basis of docs/TRAINING.md §2e F24 (our sign group steps ~sqrt(d_in) faster relative to matrices than this recipe)
  and of ModularOptimizer `update_scale="rms0.2"` + `scalar_opt="adam"` (audio-tools-avp feature/modular-opt-c-series).
  Our spectral weight decay is already applied at z. Test plan sections B and D.
