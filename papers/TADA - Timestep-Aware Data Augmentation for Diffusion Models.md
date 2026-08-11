# TADA: Timestep-Aware Data Augmentation for Diffusion Models (OpenReview U6Mb3CRuj8; no arXiv id)

*A "when-to-augment" thesis: modulate augmentation strength by diffusion timestep to get the regularization without the distribution shift — the idea ports to SA3, the DDPM plumbing needs re-derivation for rectified flow. NB a DISTINCT paper from the audio-steering "TADA!" (arxiv-2602.11910). ICLR-2024 submission / NeurIPS-2023 workshop, anonymous double-blind. Subagent deep-read, THE-FINN 2026-08-12.*

## What it contains

**Core claim.** Naively augmenting a diffusion model's training data (the standard "train on augmented samples at all noise levels") causes a *distribution shift*: the model starts generating augmented-*looking* outputs. The paper's central empirical finding is that this shift does **not** come from all timesteps uniformly — it originates almost exclusively from a specific *middle* band of timesteps, which they call **sensitive**. Initial/high-noise timesteps (**rough**) and final/low-noise timesteps (**fine**) are largely unaffected by augmentation.

**How they show it (two toy experiments, FFHQ 64×64).**
- Toy 1: for a base model (h-flip only) vs an aug model, measure LPIPS between input x₀ and the predicted x̂₀ at every timestep, plotted against log(SNR). The two models are indistinguishable at rough (low SNR — image is noise anyway) and fine (high SNR — data-agnostic refinement) timesteps; they diverge in the middle.
- Toy 2: swap the reverse trajectory between base and aug models over the middle interval only. Whichever model drives the *middle* timesteps determines whether the final sample lands on the real or the augmented distribution — confirming the middle band is causally "sensitive," while swaps elsewhere change nothing.

**The method (TADA).** Apply *strong* augmentation at rough and fine timesteps, *weak* augmentation in the sensitive band. Augmentation strength `w_t ∈ [0,1]` is a parabola in log-SNR:
`w_t = κ·(r_t − r_rough)·(r_t − r_fine) + δ`, where `r_t = log(SNR(t))`, `δ = 0.1` is the floor (minimum strength in the sensitive region), κ is auto-set so w_t hits 0 near the clip points, and w_t is clipped to [0,1]. The minimum of the parabola sits in the sensitive band between the two thresholds r_rough and r_fine (held fixed across all their experiments for robustness). It's an **online** scheme: each training step samples t, computes w_t, and augments that sample to strength w_t. A resolution calibration `SNR_calibrated(t) = SNR(t)/(d/64)²` (Hoogeboom et al. 2023) shifts the thresholds for resolutions other than 64×64, so the same r_rough/r_fine transfer across resolutions.

**Setup.** Built on ADM (Dhariwal & Nichol), ε-prediction, linear schedule T=1000. Augmentation ops = a subset of EDM/Karras-2020 geometric augmentations **plus color transforms** (which EDM found unhelpful but TADA uses). At each step apply n∼{1,…,M} augmentations with prob p=0.8, M=2; h-flip separately at p=0.5. Metrics FID/KID with *clean* (PIL-bicubic) resizing, 10k samples.

**Key quantitative results (cite-accurate).**
- **FFHQ 64×64, FID↓ / KID(×10³)↓** (best-FID iteration), vs h-flip and AR (augmentation-regularization, the conditioning-based method):
  - 1k: h-flip 17.46/11.18 · AR 22.98/17.11 · **TADA 14.37/8.91**
  - 2k: h-flip 36.22/30.10 · **AR 16.33/9.58** · TADA 18.83/14.39
  - 5k: h-flip 14.84/9.30 · AR 12.95/8.45 · **TADA 12.92/7.74**
  - 10k: h-flip 13.31/9.87 · **AR 11.34/7.79** · TADA 12.19/8.06
  - 30k: h-flip 12.00/7.79 · AR 10.82/7.56 · **TADA 10.39/6.80**
  - TADA beats h-flip consistently; roughly on par with AR but **without any conditioning module / extra inputs**.
- **256×256 FFHQ** (Table 2): TADA best at 2k (35.75/23.17); competitive elsewhere.
- **Transfer learning, AFHQ-v2 256×256, pretrained on FFHQ** (Table 3, TADA vs AR): TADA wins on all three domains — Cat 16.76/14.45 (AR 17.30/14.85), Dog 32.03/21.84 (AR 35.07/24.79), Wild 12.17/6.96 (AR 13.77/8.05).
- **Generalization** (Table 4, FID@50k): TADA > h-flip under linear (12.92 vs 14.84) and cosine (14.29 vs 14.70) schedules; across sampling steps 50/100/500/1000 (best at 1000); and on base(68M)/large(95M) models — but **loses on the small 17M model** (TADA 22.10 vs h-flip 20.78), i.e. the benefit scales with model size.
- **Ablations** (Table 5): augmenting only one band never beats full TADA at 250 steps; M=2 is optimal (larger M drifts the data distribution); the auto-κ default is beaten by hand-tuned κ but still beats h-flip.

## FOR US

**What genuinely transfers — the thesis, not the code.** The parabola is parametrized in **log-SNR**, not in DDPM's t. Log-SNR is well-defined for rectified flow too (for the linear RF path x_t = (1−t)x₀ + t·ε, SNR = ((1−t)/t)², monotonic in t), so the "strong at the log-SNR extremes, weak in a middle band" shape is schedule-agnostic and drops onto SA3's RF schedule without conceptual change. The high-level lesson — *don't apply full-strength augmentation across all noise levels; back it off in the sensitive middle to avoid teaching the model the augmentation distribution* — is directly relevant to how aggressively we push bungee stretch/pitch during training.

**RF-vs-DDPM caveats to re-derive (all light, none blocking):**
- **x̂₀ diagnostic.** Their sensitive-band identification measures LPIPS between x₀ and predicted x̂₀ along sampling. SA3 predicts **velocity**, but x̂₀ is algebraically recoverable from v and x_t, so the diagnostic survives — *except* LPIPS is an image metric. We'd need an audio-appropriate perceptual distance (in waveform or a perceptual audio embedding) to redo the toy-1 curve and find *our* r_rough/r_fine. **Do not reuse their image thresholds.**
- **Resolution calibration** `SNR/(d/64)²` is spatial-image-specific and does **not** apply to audio latents; the sensitive band must be located empirically on SA3's own latent, not calibrated from an image formula.
- **Objective.** None of TADA's core equations depend on ε- vs v-prediction — they depend on log-SNR and on recovering x̂₀. So the re-derivation is: (1) compute log-SNR from the RF schedule, (2) recover x̂₀ from velocity, (3) empirically find the sensitive band with an audio metric. No DDPM reverse-step assumption is load-bearing for the augmentation rule itself.

**The real cost — it's a training-loop change, not a data change.** TADA is fundamentally **online**: augmentation strength is a function of the timestep sampled *for that training example*. Our current pipeline is **offline** (289 base crops → 2394 with 8 fixed augmented variants, materialized ahead of time). Porting TADA means moving aug application into the training step and conditioning its strength on the sampled t — non-trivial plumbing in the dataloader/collate path, plus a `w_t → (stretch ratio range, pitch-shift semitone range)` mapping since our operators have natural continuous strength.

**Unverified assumption to test cheaply before any build.** TADA applies *strong* augmentation at **fine** (low-noise, near-clean) timesteps on the theory that final steps are "data-agnostic refinement." For audio that is not obviously true — heavy time-stretch/pitch-shift on a near-clean audio latent may well be perceptually load-bearing, not agnostic. The lightweight-first move (per our standing preference): run their toy-1 diagnostic once on SA3 to see whether audio even *has* a clean "fine = augmentation-safe" band before committing to an online TADA rewrite. If the fine band isn't safe for audio, the parabola shape itself needs revisiting (maybe monotone-decreasing strength toward clean, not a symmetric U).

## What stays ours

- **The augmentation operators and pipeline.** TADA is image-only (geometric + color transforms on pixels). Our **bungee time-stretch + pitch-shift** operators, the base **289-crop** set, and the **8× expansion (avp aug×8 → 2394)** are modality-correct and entirely ours; TADA says nothing about audio augmentation and doesn't argue we should drop offline augmentation. What it offers is the *scheduling* of strength, not the operators or the crop set.
- **The RF objective and SA3 latent.** Velocity/x0 rectified flow on the SA3 latent is the substrate; TADA slots on top of it, it doesn't replace anything.
- **Net:** adopt the *when* (timestep-aware strength modulation, re-derived in log-SNR with an audio-found sensitive band), keep the *what* (our operators and avp-aug set). Treat the fine-timestep "strong aug is safe" claim as image-specific and unproven for audio until we run the cheap x̂₀ diagnostic.

Sources: [OpenReview U6Mb3CRuj8](https://openreview.net/forum?id=U6Mb3CRuj8), [NeurIPS 2023 listing](https://neurips.cc/virtual/2023/74919)
