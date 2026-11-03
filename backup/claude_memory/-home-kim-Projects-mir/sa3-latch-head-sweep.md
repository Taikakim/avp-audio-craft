---
name: sa3-latch-head-sweep
description: "SA3-medium LatCH guidance heads — which steer, at what gain (2026-06-28 sweep)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

Systematic sweep of all 14 SA3-medium LatCH **guidance** heads
(`stable-audio-3/latch_weights_sa3_medium/latch_sa3_<feat>_best.pt`), 2026-06-28.
14 heads × {low, mid, high} target (= head `std_mean` ± 2σ) × 3 prompts, measured with
**MERT** (steering magnitude) + **Audiobox CE** (quality) + the **target-feature follow**.

**Operating gain ≈ 512 — ~10× the documented "48–96".** At gain 128 the heads sit in a
**dead zone** (feature moves <1 dB, MERT Δ ~0.001, no audible change). A gain ladder
(128→1024) showed monotonic scaling: MERT Δ and feature spread grow ~40–47× from 128 to
1024. At **gain 512** (the clean operating point, CE holds):
- **STRONG**: `rms_energy_bass` (+5.1 dB, MERT 0.017), `rms_energy_mid` (+6.0 dB, 0.015).
- **MODERATE**: `rms_energy_body` (+2.4), `spectral_skewness` (+1.6), `rms_energy_air` (+1.1).
- **PERTURB-BUT-DON'T-FOLLOW**: `spectral_flux`/`flatness`/`kurtosis` (clip changes, target ~0),
  `onset_envelope` (moves but degrades CE).
- **DEAD at any weight**: `beat_activation`, `downbeat_activation`, `hpcp`, `spectral_kurtosis` —
  activation/structural heads don't respond to LatCH guidance, just lose CE.

Eval gotcha: use the **mid** MERT layer for energy/timbre heads (the upper layer carries
melody/harmony and is half-blind to a bass-RMS change — the first pass mislabeled the two
best heads "dead" by thresholding upper-MERT at 0.02). hpcp was targeted at **E Phrygian
dominant** (user's choice), still dead at 512 — but a better chroma control exists in a
different paradigm (not this LatCH head). kurtosis σ=521 is pathological → hand-clamped.

Recipe: `gen_one.py::gen_guided` → `sample_flow_euler_multi_latch_guided(inner.model, noise,
sigmas, guides, rho=gain, mu=gain, gamma=0.3, n_iter=4, cfg_scale=7)`, fp32, target = raw value
standardized via head `std_mean`/`std_std`. ~7 s/clip after a one-time ~340 s Triton flex-attn
autotune (guidance backprop forces FlexAttention, not CK flash-attn).

**CORRECTED 2026-07-01:** that ~7 s / flex-attn is the **fp32 verify path with flash OFF**, NOT the operating
path. The DiT forward in `latch_guided.py` is under `torch.no_grad()` → only the ~5–7 M-param head needs fp32;
the default `generate(latch_configs=…)` runs **fp16 + CK flash-attn at ~0.81 s/clip (RTF 24.8×, ≈ base), 0 flex
calls**, and still steers (fp16 keeps ~½ the authority of fp32 → recover via higher gain). So LATCH-guided gen is
NOT slow on GPU — use fp16 for evals (~8× faster than the verify default). See `SAO/docs/sa3-inference-speed-shootout.md`
cell 1C + the [[MASTER §5]] fp32 correction.

Artifacts: clips on Mantu (`latch_sweep/clips/` g128, `clips_g512/` g512, `ladder/`); pipeline
in `latch_sweep/` (`sweep_driver.py`, `measure_sweep.py`, `analyze_sweep.py`, `gen_one.py`);
page **riffer-evals `latch_sweep.html`** (commit 574453e, gain-response section + tiered
leaderboard + 30-clip AAC subset online, full 123×2 local). Refines [[MASTER §5 gain ≈48–96]]
which was the SAO-Small regime / a rank-corr mirage.

**Follow-on — `spectral_skewness` LR/batch optimizer sweep (2026-06-29):** swept LR 2×/4×/8× + batch
0.5×/0.25×/single vs the original recipe (AdamW lr 3e-4/bs32/20ep), eval at gain 512. **No config beats
the original** (best ties: lr4x 0.0082 ≈ orig 0.0083); smaller batch worst; 8× LR over-cooks. Per-layer
analysis (checkpoints + wandb `kim-ake/sa3-latch`): the winner **moved the least** (dist-from-init 30 vs
48–229; train loss is blind — spans only 0.053–0.055); all configs diverged from the original's low-movement
basin and never returned; K/V do move (0.6→3.4× init, MASTER §4 confirmed); the drift hypothesis **broke**
(lr4x moved a lot yet tied; bs1 moved most yet mid-pack; bs16/bs8 had ~no telemetry → partly eval noise).
**Conclusion: spectral_skewness control is architecture/target-limited, not optimizer-limited — optimizer
tuning for this head is DONE; do NOT run lower-LR/larger-batch (it would move *less* → tie at extra cost).**
Levers instead: EMA/late-soup (small upside), a different head architecture/target, or the energy heads
(steer 2–10× harder). Artifacts in `latch_sweep/` (`latch_weights_sweep/skew_*`, `skew_sweep_results.json`,
`skew_layer_analysis.md`, `skew_layer_heatmap.png`).

**REVERSAL (2026-06-29, same day) — EMA(+grad-accum) BEATS the original ~3×; the head was DAMPING-limited, NOT
architecture-limited.** EMA 0.999 at the best settings × {20ep, 40ep, 80ep, grad-accum2/eff-batch-64}: ALL four
beat the original at gain 512 — MERTmid Δ ema_ga2 0.0271 / ema40 0.0248 / ema20 0.0237 / ema80 0.0197 vs
**orig 0.0086** (~2.3–3.1×); skew-follow +2.4 vs +1.6; CE equal/better. So the "architecture-limited ceiling"
above was WRONG — EMA averaging (MASTER §4 drift-fix) unlocks the control the LR/batch sweep couldn't. Mechanism:
best head (ema_ga2) moved LEAST from init, worst (ema80) moved MOST → it's the averaging, not displacement;
>40ep erodes the gain. The 0.6 EMA train loss was decay-0.999 lag, not undertraining. **New default control-head
recipe: EMA + grad-accum + early-stop; ship `ema_ga2`.** `train_latch.py` now HAS `--ema` + `--grad-accum` (added
2026-06-29). Heads `latch_weights_ema_sweep/`; eval `latch_sweep/skew_ema_results.json`. Validates the MASTER §4
"EMA/averaging + early-stop, not lower LR" hypothesis on a real head.

**`spectral_skewness` is INVERSE brightness (2026-06-29, by-ear + measured centroid).** Eval clips: low-target →
spectral centroid ~7600–7900 Hz (BRIGHT), high-target → ~2400–3000 Hz (DARK), for BOTH original and ema_ga2 (same
direction — NOT a sign bug). High spectral skewness = spectral mass piled at low freq with a long high tail =
perceptually DARKER; low skewness = brighter. The strong EMA head makes it audible + pushes the dark end harder
(high-target centroid 2447 vs original's 3032 Hz). So the skew head is a spectral-tilt/**darkness** control, not
brightness — for an intuitive "brighter" knob use **`rms_energy_air`** (high-band energy) or invert the skewness
label (low-target = bright). The MERT-Δ magnitude metric is sign-agnostic so it never flagged this; the perceptual
direction must be checked by ear/centroid.
