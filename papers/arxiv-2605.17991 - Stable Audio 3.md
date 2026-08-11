# Stable Audio 3 (2605.17991v1, technical report) — deep-read

Evans, Parker, Rice, Carr, Zukowski, Taylor, Pons (Stability AI), May 2026.
PDF: `2605.17991v1 Stable Audio 3.pdf`. **This is OUR model** (medium: 1.4B DiT,
24 blocks, dim 1536, differential attention, SAME-L latents).

## Architecture facts we should never re-derive
- **Conditioning enters by THREE pathways:** text (T5Gemma, 256 tokens + 1 duration
  token) via per-block **cross-attention**; timestep+duration via **AdaLN-Single**
  (shared cond embedding + 6 per-block bias terms, FLUX-style gates); inpainting via
  a per-block zero-init **local-additive MLP** (257-ch mask+masked-latent, added to the
  residual stream). Duration rides BOTH cross-attn and AdaLN.
- **64 memory embeddings** prepended as a global attention buffer (removed before loss).
  A steering/patching site Stable Audio Open never had.
- Blocks: RMSNorm pre-norm, QK-RMSNorm everywhere, partial RoPE (32 dims/head),
  differential attention in self- AND cross-attn (medium/large), SwiGLU FFN.
- **Discriminator taps layer 14 of medium's 24** for its feature head — Stability's own
  pick for where semantically-rich features live (mid-stack hint for our localization).

## Training facts with direct consequences for our fine-tuning
- **Timestep sampling truncated at t=0.075** (logit-normal, near-clean removed): the base
  model NEVER trained on the final ~7.5% of denoising — that region is extrapolation.
  Mechanistic support for "controls hurt crispness late" + the disable-controls-late idea.
- **Length-dependent timestep shift** (Eq 3, μ: 0.5→1.15 by sequence length): "low-noise"
  is length-relative. Any noise-band-targeted training (Axis-2 era=low-noise MVP) must
  define bands in SHIFTED t′, and our crop-length training should apply the same shift.
- **Prompt convention:** AudioSparx metadata prefixes present ~50% during training;
  **"TrackType: Music, VocalType: Instrumental," strongly recommended at inference**
  ("significantly improve generation quality"). Our T1 captions + eval prompts lacked it
  (now: `caption_tools.make_caption_sampler(track_type_prob=…)` / train_lora
  `--track_type_prob`; `interface/reprompt.py` had the prefixes defined but unused).
- CFG dropout p=0.1 on conditioning during base training; post-trained models need no CFG
  (baked in via distillation-warmup CFG-5 teacher + adversarial CLAP loss).
- **Inpainting trained 80/10/10** (full / random-segments / causal-continuation masks) —
  continuation is a first-class trained capability (what longform.py leans on).
- Silence augmentation: signal randomly extended with ~4s (exponential) of encoded-silence
  latent → the model learned clean endings.
- Optimizer: **Muon+AdamW hybrid** (Muon on QKV/FFN projections, AdamW elsewhere) — same
  spectral/scalar family split as our FusionOpt.
- Post-training pipeline: flow matching → distillation warmup (teacher DPM++ 15-step
  CFG-5 trajectories, student maps any x_t → x̂0) → adversarial post-training (relativistic
  D in x0-space at independent t_D + contrastive prompt-shuffle loss + CLAP-on-SAME-latents
  geodesic loss). Inference: 8-step ping-pong (denoise→renoise), logSNR-uniform schedule
  [−6.2, 2.0]. `medium-base` (our fine-tune target) = flow-matching stage only, 50-100 step
  Euler, CFG needed.
- Variable-length: latent length L ∝ duration + 6s silence pad; padding masked from
  self-attn+loss (cross-attn NOT masked).

## What remains ours
Control adapters/LatCH numeric lanes, era axis, meter-in-the-gradient scope law, noise-band
target-conditioned reweighting, activation-steering on SA3, layer×feature maps — the report
explicitly EXCLUDES inference-time/global/time-varying control ("can be included by
fine-tuning after release", i.e. our whole lane).

## Addenda from the repo guides (docs/guides/prompting.md + model-overview.md, 2026-07-06)
- **LoRA portability:** "LoRAs are trained on the base checkpoint. Once trained, they can
  be applied to the post-trained model and will work as expected" — untested by us; if it
  holds, audition renders move to 8-step ping-pong (no CFG) at ~6-10x less compute.
- **Full AudioSparx tag language:** `Genre:` (repeatable), `Instruments:`, `Format: Duo`,
  `TrackType: Instrument` (stems) / `SFX` — field identifiers present ~50% in training, so
  bare and prefixed forms both work; field-prefixed T1 variant = another caption axis.
- **init_noise_level sweet spots** (their numbers): timbre transfer 0.4-0.5, style
  transfer 0.6 — independently converges with our longform sigma_peak 0.4-0.6 finding.
  Their feature-stripping order: rising noise removes melody/rhythm first, timbre last.
- Guide discrepancies (paper is authoritative): overview claims SAME-S 266M / SAME-L 1.7B /
  medium ~4.75min; paper says 108M / 852M / 6m20s (T=4096 @10.767Hz = 6m20s confirms paper).

## CORRECTION 2026-07-07 (code-verified, supersedes the t=0.075 claim above)
The "timestep sampling truncated at t=0.075 → final ~7.5% of denoising is untrained
extrapolation" claim is WRONG in one important detail. The actual sampler
(`truncated_logistic_normal_rescaled`, sampling.py) truncates the logit-normal at
0.075 and then RESCALES the support back to [0,1] (then flips) — so the model DOES
train across the full t range including near-clean; the truncation reshapes the
DENSITY, not the support. Honest version: the finishing regime is trained-but-
UNDER-trained (thin mass near t=0). Consequences: (1) outputs contain NO residual
noise — samplers integrate to t=0 and RF velocity extrapolates smoothly; post-trained
ckpts end on a direct x̂0 prediction anyway; (2) the crispness-late mechanism survives
in weakened form (thin practice at the polish regime → soft transients plausible,
controls-off-late still supported); (3) cheap experiments: denser step schedule near
t=0, or a micro-SDEdit finisher pass (nl 0.05-0.1) — inference speed is not a
constraint for musician tools (Kim).
