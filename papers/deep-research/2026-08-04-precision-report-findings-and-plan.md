# Sub-dominant-signal precision: Gemini report findings + fleet action plan
*CONTINUITY 2026-08-04. Report: `Sub-Dominant Signal Precision Methods.txt`. Brief: `briefs/2026-08-04-precision-requirement-melody-signal-brief.md`.*

## What the report established (ranked interventions)
1. **Stochastic Rounding (SR) for the weight update — #1, the actual fix for LEARNING melody.**
   Spectral bias τ∝1/λ (arXiv 2503.03206) forces the melody-direction gradient microscopically
   small; deterministic round-to-nearest then truncates `w+δ→w` when δ is below the weight's
   mantissa ULP → learning permanently stalls. SR is unbiased → sub-dominant updates ACCUMULATE
   over thousands of steps, recovering fp32 convergence at bf16 speed/memory. Lib: `torchastic`
   (lodestone-rock) / custom AdamW step. **Bites only the bf16-MASTER rung** (fp32/bf16-mixed
   master already accumulate in fp32). So SR = what makes bf16-master training viable for melody
   (half memory) — relevant if long-T/big-batch forces bf16 master.
2. **Differential signal injection — #2, the decisive cheap forward test.** Run the REAL fp16
   Flash kernel vs strict fp32 attention on the synthetic-MIDI deviants, project Δ onto the melody
   eigenbasis, cosine. Upgrades our SQNR estimate (uses the real kernel). Vehicle: `SA3_DISABLE_FLASH_ATTN=1`
   already gives fp32 SDPA on an fp32 model — no new flag. → `eval/precision_injection_ab.py` (running).
3. **Flash-Attention low-precision training failure (Qiu et al. arXiv 2510.04212).** Online-softmax
   sticky-bit rounding bias on tied row-maxima → strictly-positive bias → low-rank collapse →
   spectral-norm explosion → drowns sub-dominant gradients. **This means "forward is fine → fp32
   attention won't help" is INCOMPLETE** — it's a training-dynamics failure, not a representation-
   magnitude one, so our 700× forward headroom does NOT rule it out. Mitigation = "safe softmax"/
   dynamic-max. → audit our CK flash_attn 2.8.4 (F).
- Lower-ranked: diffusion spectral-bias modeling (#3, diagnostic), FIM/RSAVQ directional sensitivity
  (#4), gradient-noise-scale (#5), HAWQ Hessian (#6, layer-avg = blind to the subspace), plain
  SQNR/rate-distortion (#7 — "actively hostile", allocates ZERO bits to sub-floor dirs → false
  positives; our measurement dodged this by being DIRECTIONAL, projected onto the melody basis).

## Reconciliation (F's a-priori + our forward measurement + the report all agree)
- Forward representation: precision NOT the bottleneck — one note = ~700× bf16 headroom in the
  melody subspace (our measurement). → fp32 *attention* unlikely to help the forward.
- Weight/update storage: 786× anisotropy = 9.6 bits > bf16's 8 mantissa (F) → bf16-MASTER can't
  hold the melody update. → fp32 (or bf16-mixed, or bf16-master+SR) TRAINING matters.
- The report adds the one caveat both missed: fp16 Flash *training dynamics* (Qiu) can harm melody
  even when the forward representation is fine.

## CORRECTIONS (2026-08-04, after code audit + weight-diff probe)
- **FusionOpt-SF keeps an fp32 MASTER** (`z`/`x` = `p.detach().clone().float()`, update in fp32).
  So the F/Gemini weight round-away NEVER occurred in ANY of our fusion runs. **SR is moot for us**
  → it became the separate DESKTOP deliverable (SHIPPED: `stochastic_rounding.py` + AdamWSR +
  `--stochastic-rounding`; TDD-proven unbiased; caveat: fixes the STALL not the bf16 storage FLOOR
  ~(2^-8)²).
- **The real axis is COMPUTE precision, tested as FORMATS** — and the interesting rung is **fp16-mixed**:
  the winning fp32 arm's attention was already fp16 (flash cast), so fp16-mixed (10 mantissa bits +
  GradScaler) matches the winner's attention precision AND beats bf16's 7-bit compute. fp16 forward is
  proven fine (whole eval corpus renders fp16); only risk = small-grad underflow, handled by 16-mixed's
  loss-scaling. fp32-attn is settled (injection null cos ~1) → fp32 attention buys nothing.
- **#52's `fp32cmp`/`bf16cmp` are DoRA adapters, not full-FT** — so Kim's ear-verdict was on adapters,
  and DoRA GAUGE FREEDOM (~1.2 reldiff everywhere = equal-norm gauge-rotated solutions) dominates the
  weight divergence → the weight-diff probe CANNOT isolate precision on them. What it says gauge-invariantly:
  NO Qiu attention inflation (spec ratio ~0.99, mag ratio 1.0000) → the audible gap is NOT weight-norm
  inflation; it's inference/compute-time or fine-direction. The full-FT ladder is the first CLEAN test.

## Three-rung FORMAT ladder + what settles each (in flight 2026-08-04)
| rung | master | compute + attn core | note | test |
|---|---|---|---|---|
| `fp32` (32-true) | fp32 | fp32 + fp16 attn (10-bit) | quality ceiling | ladder arm 0 |
| `bf16-mixed` | fp32 | bf16 autocast + bf16 attn (7-bit) | ≈ old bf16cmp sound (bf16 compute) | ladder arm 1 |
| `fp16-mixed` | fp32 | fp16 autocast + fp16 attn (10-bit) + GradScaler | matches fp32-arm attn precision; likely sweet spot | ladder arm 2 |

- **`lumi/sbatch/precision_ladder.sbatch`** — 3 arms, T256/10ep/full-FT/Fusion/EMA, matched seed,
  pre-encoded latents (clean precision contrast, no adapter gauge freedom). fp16-mixed vs bf16-mixed =
  "is fp16 or bf16 better for us"; fp16-mixed vs fp32 = "does the more-precise 16-bit format recover the
  fp32 sound". If fp16-mixed ≈ fp32 → the cheap-and-good rung for the #68 big-FT AND desktop.
- **`eval/precision_injection_ab.py`** — DONE: fp16-flash vs fp32-SDPA forward, melody cosine 0.99999
  (null) → fp32 attention buys nothing in the forward.
- **F**: CK flash_attn 2.8.4 safe-softmax audit vs Qiu 2510.04212 — now the DIRECT Qiu probe (the
  weight-diff couldn't check it on DoRA). **G**: melody-recurrence re-score of the DoRA fp32/bf16 clips
  (caveat: gauge freedom limits what it can attribute).
