# Reverb / Stereo Big-Picture Study

Source: `eval/reverb_matrix.jsonl` (10,584 SA3 gens: 36 base + 10,548 DoRA) vs
`eval/reverb_goa.jsonl` (1,116 real goa 20s crops = reference). 30 DoRA labels, 18 prompts,
strengths {0.6,1.0,1.5,2.0}, cfg {1,7,15,16,24}. Everything treated as data.

**Confounds up front:** (1) loudness NOT normalized — rt60/spectral-flatness/crest are level-sensitive.
(2) base tier is tiny & unconfirmed: only 36 clips, all cfg16/strength1.0, 12 prompts (no kimlong/bracket) —
treat base numbers as weak. (3) 382 degenerate clips (crest>50 or spectral_flatness>0.4 = near-silent /
white-noise-collapse) skew means → all aggregates below use **medians**. (4) `dora128_47s_cont_from5` and
`dora128adj_avp_aug10_lr1e4` include `iv` (interval-SDEdit) ckpt variants (900 clips) — a rendering-mode
confound, kept in label aggregates but excluded from the clean epoch trend.

## 1. Big picture — median [IQR 25–75]

| metric | GOA (real) | BASE | DoRA | read |
|---|---|---|---|---|
| rt60_s | **0.919** [0.63,1.02] | 0.671 [0.53,0.97] | 0.837 [0.50,1.02] | gen BELOW real; DoRA>base |
| reverb_prob | **0.782** [0.60,0.83] | 0.633 [0.53,0.81] | 0.738 [0.51,0.83] | gen BELOW real; DoRA>base |
| coh_broadband | 0.540 [0.36,0.72] | 0.632 [0.35,0.70] | 0.566 [0.37,0.73] | gen MORE mono-coherent, not decorrelated |
| width_mean | 0.219 [0.17,0.28] | 0.246 | 0.231 [0.17,0.29] | ~equal / gen slightly narrower |
| side_ratio_mean | 0.246 | 0.274 | 0.240 | ~equal |
| **spectral_flatness** | **0.0076** [0.003,0.017] | 0.0204 | 0.0163 [0.008,0.027] | **gen 2.1–2.7× real — the artifact** |
| env_decay_slope | ~0 (1.6e-5) | -0.00215 | -0.00040 | gen envelopes decay, real is flat |
| late/early_energy | **1.008** [0.92,1.11] | 0.392 | 0.890 [0.51,1.00] | gen has LESS late energy (no long tail) |
| env_crest | 3.41 | 4.32 | 4.22 | gen peakier |
| spectral_tilt_db | -27.7 | -28.7 | -28.8 | ~equal |
| comb_peak_median | 0.077 | 0.065 | 0.062 | gen slightly LESS comb/early-reflection |

**Verdict: the artifact is a MONO-DOMAIN SPECTRAL SMEAR, not stereo collapse and not a classic reverb tail.**
- Real reverb decorrelates L/R (↓coherence, ↑width, ↑late/early). Generations do the *opposite*: coherence is
  **higher** (more mono), width equal/narrower, late/early **lower** (no tail). The stereo meter literally cannot
  see the problem — by every stereo axis gen looks as-clean-or-narrower than real goa.
- The one axis where gen is strongly ELEVATED vs real is **spectral flatness (2–2.7×)** = a hazy/noisy/washed
  mono spectrum. That is the perceptual "reverb/wash," and it lives in the mono domain.
- By the rt60/reverb-classifier axes, generations are actually **below** real goa (real goa is genuinely dense/
  reverberant music). So "is gen reverb elevated?" — **No by rt60/reverb_prob; YES by mono spectral haze.**
- DoRA vs base: DoRA **raises** rt60 (0.67→0.84) and reverb_prob (0.63→0.74) toward but not past goa, while
  **lowering** the base spectral haze (0.020→0.016). Mixed, and base tier is too small to trust.

## 2. Dose-response (DoRA, median)

| strength | rt60 | reverb_prob | spec_flat | coh_bb |
|---|---|---|---|---|
| 0.6 | 0.836 | 0.737 | 0.0182 | 0.607 |
| 1.0 | 0.860 | 0.751 | 0.0161 | 0.582 |
| 1.5 | 0.811 | 0.723 | 0.0150 | 0.537 |
| 2.0 | 0.959 | 0.802 | 0.0085 | **0.284** |

- **rt60 / reverb_prob are NOT monotonic in strength** — they dip at 1.5× then jump at 2.0× → reverb is NOT
  cleanly adapter-strength-driven.
- **Spectral haze DECREASES monotonically with strength** (0.018→0.009) — cranking the adapter makes clips
  *more* tonal, not more washed. So the haze is largely a base/low-strength property, not adapter-injected.
- **Coherence collapses only at strength 2.0** (0.61→0.28) — extreme strength introduces genuine stereo
  decorrelation (a different failure mode from the haze).
- **cfg is a strong lever:** high cfg (15/24) pushes rt60 to ~0.95–1.0, crest up, coherence down.
- Confound: strength-2.0 cells only exist for cfg{7,15,24}; strength×cfg×label sampling is imbalanced, so the
  2.0 jump is partly a cfg/label artifact.

## 3. Worst offenders — TOP 12 (robust median, mono-haze-weighted severity)

severity = 1.5·z(spec_flat) + z(rt60) + z(reverb_prob) + 0.4·|z(late/early)| + 0.3·|z(crest)|, z vs goa median/IQR.
GOA ref median: rt60 0.919, reverb_prob 0.782, spec_flat 0.0076, late/early 1.008.

| # | label | tier | n | rt60 | rev | spec_flat | late/early | coh_bb | severity |
|---|---|---|---|---|---|---|---|---|---|
| 1 | dora64_avp_tiered_lr1e4 | avp | 432 | 0.970 | 0.807 | **0.0414** | 0.116 | 0.650 | 6.05 |
| 2 | sa3-goa-dora-47s-b4-cont | goa | 324 | 0.824 | 0.730 | 0.0245 | 0.585 | 0.647 | 2.42 |
| 3 | sa3-goa-dora-47s-b4 | goa | 216 | 0.766 | 0.695 | 0.0230 | 0.430 | 0.573 | 2.33 |
| 4 | sa3-goa-dora-47s-r128-adamw | goa | 216 | 0.866 | 0.754 | 0.0236 | 0.685 | 0.572 | 2.32 |
| 5 | dora128adj_avp_aug10_lr1e4 | avp | 882 | **1.012** | 0.826 | 0.0177 | 0.773 | 0.437 | 2.12 |
| 6 | dora16_avp_originals_earlyeps | avp | 432 | 0.894 | 0.770 | 0.0246 | 0.838 | 0.708 | 2.11 |
| 7 | dora16_glitchheal_5ep_2xlr | avp | 216 | 0.783 | 0.706 | 0.0205 | 0.462 | 0.578 | 1.96 |
| 8 | dora64_avp_tiered_lr2e4 | avp | 144 | 0.986 | 0.814 | 0.0182 | 0.832 | 0.555 | 1.95 |
| 9 | sa3-goa-dora-47s | goa | 108 | 0.799 | 0.716 | 0.0232 | 0.724 | 0.642 | 1.87 |
| 10 | dora256_avp_aug10_lr7e5 | avp | 144 | 0.797 | 0.715 | 0.0197 | 0.749 | 0.601 | 1.37 |
| 11 | sa3-goa-dora-47s-r128-fusion-caut | goa | 216 | 0.719 | 0.665 | 0.0230 | 0.794 | 0.665 | 1.36 |
| 12 | sa3-goa-dora-47s-r64 | goa | 324 | 0.642 | 0.612 | 0.0236 | 0.641 | 0.585 | 1.28 |

Tier pattern: **avp-trained and the early/small goa-47s adapters dominate the worst list.** `dora64_avp_tiered_lr1e4`
is in a class of its own (spec_flat 5× goa + it collapses at ep7, see §4). #5 `dora128adj_avp_aug10_lr1e4` is the only
label whose rt60 (1.01) actually exceeds real goa. No "everything"-trained label appears in the top 12.

**Cleanest (most goa-like):** `dora16_goa_newstack_8ep`, `dora128_everything_8ep_lr1x`,
`dora128_newcap_continued_3more`, `sa3-goa-dora-47s-r128-fusion`, `dora128_everything_8ep_lr0.5x_cont5`,
`dora128_47s_newcaptions_5ep` — low rt60 (~0.56–0.66), spec_flat ~0.011–0.014, late/early ~0.95–0.99 (goa-like sustain).
The **everything / newcaptions / r128-fusion** recipes are the clean ones.

## 4. Epoch trend

- **`dora64_avp_tiered_lr1e4` — catastrophic overtrain collapse:** spec_flat 0.023→0.041→**0.230** (ep0→3→7),
  late/early → **0.0** at ep7 (second half goes silent). Its late epochs are white-noise/degenerate. Worst by far.
- **avp-originals worsen with epochs:** `densewin` spec_flat 0.007→0.012→0.019 & rt60 rises; `earlyeps` 0.023→0.020→0.042;
  `win7` improves on haze but coherence drops. General pattern: avp adapters accumulate haze/instability.
- **"everything" adapters IMPROVE with epochs:** `everything_8ep_lr0.5x` rt60 0.92→0.68, late/early 0.73→0.99
  (converges toward goa); `lr1x` similar. Training cleans them up.
- **`sa3-goa-dora-47s-r128-fusion` IMPROVES:** rt60 0.59→0.53, spec_flat 0.019→0.009, late/early→0.96 (cleanest goa recipe).
- **`goa_newstack` and `47s-r64` worsen slightly** at the last epoch (rt60 rises). Mixed within goa family:
  fusion cleans up, b4/adamw/r64 stay hazy.

## 5. Isolation-render recommendation (48-step matched base+DoRA, latents)

8 worst labels (5 avp + 3 goa, spanning the collapse case, the rt60>goa case, and the hazy goa-47s cluster) ×
5 prompts (all base-covered → true matched base render; 3 kimlong-type + 2 worst-reverb) × 1 seed.
≈ 40 DoRA + 5 base ≈ 45 renders; at ~48 steps/20s on RDNA4 this is well under 2 GPU-h even with a second strength.

**--only-labels:**
```
dora64_avp_tiered_lr1e4,dora128adj_avp_aug10_lr1e4,dora16_avp_originals_earlyeps,dora16_glitchheal_5ep_2xlr,dora64_avp_tiered_lr2e4,sa3-goa-dora-47s-b4-cont,sa3-goa-dora-47s-r128-adamw,sa3-goa-dora-47s
```

**--only-prompts:**
```
kl_0,kl_2,rb_mid_3,rb_common_1,rb_rare_8
```
kl_0/kl_2 = kimlong-type (base covers these; `kimlong`/`kl_bracket_0` are NOT in base tier — use kl_* for a matched render).
rb_mid_3 = worst rt60+reverb_prob; rb_common_1 = highest mono haze (spec_flat 0.025, late/early 0.46 → decays);
rb_rare_8 = high rt60+reverb_prob. Suggested strengths: 1.0 (matched to base) + 2.0 (to test the coherence-collapse mode).
