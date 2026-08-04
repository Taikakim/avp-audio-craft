# Clarity / HF-recovery plan (frozen SAME codec) — 2026-08-02

Derived from the four-report Gemini thread + our own measurements, after CONTINUITY
citation-verified the load-bearing planks (VoiceBridge 2509.25275, LatentFlowSR 2604.09188,
Audio-SR-LBM 2509.17609, Aliasing-Free-Neural-Audio-Synthesis 2512.20211, v-pred/ZTSNR
2305.08891). Supersedes the pre-report HF-repair plan in two ways: (1) the post-net must be
GENERATIVE not regression; (2) IFGD loss belongs on the adversarial net as a phase-stabilizer,
NOT on a regression net (where it is inert/harmful).

## The settled diagnosis
- Frozen SAME discards >7 kHz phase coherence at encode (round-trip phase-coh 0.045).
  Mutual info between original and decoded HF phase ≈ 0 → **deterministic regression cannot
  recover it** (regression-to-the-mean → magnitude restored, transients smeared). CONFIRMED
  GAP: no deterministic audio net has recovered phase from near-zero-coherence input.
- → HF phase must be **generatively hallucinated**, guided by the restored magnitude envelope.
- **Audio domain beats latent-bridge for us:** VoiceBridge shows a strictly-frozen decoder
  is a wall for latent bridges (they needed an Energy-Preserving VAE + decoder co-tuning);
  LatentFlowSR/AudioLBM use co-designed AEs. The frozen SAME decoder cannot interpret
  hallucinated HF phase from low-variance latent directions → operate on the decoded waveform.

## UPDATE 2026-08-02 (Gemini follow-up answers, Kim relayed)
- **Q1 latent-conditioning:** condition the generative post-net on the SAME LATENT in addition
  to the decoded waveform. Does NOT raise the deterministic ceiling (info gone) but gives the
  generator a pristine, unaliased structural prior (pre-decoder-nonlinearity) → more stable
  phase hallucination. Fold into Track A. (Cite "CodecFlow" = UNVERIFIED illustrative; mechanism
  is sound regardless.)
- **Q2 additivity:** whitening (spatial/capacity), ZTSNR (temporal/schedule leakage), v-pred
  (prevents zero-SNR collapse) are ADDITIVE not alternatives — three distinct angles on the same
  188 swamped directions. Implement all three together in #65 (supersedes the earlier
  "alternative to x0-target" framing). Confirmed by my own test_vpred_ztsnr + whitening probe.
- **Q3 audio-evidence gap:** confirmed — no audio ablation for this combo in a fixed music
  latent. Run our own: HF Log-Spectral-Distance delta on the psytrance corpus across
  {baseline, whiten, ztsnr+vpred, whiten+ztsnr+vpred}. New task #66.

## PRE-REGISTERED success criteria (Gemini's falsifiable predictions, locked 2026-08-02)
Recorded before the runs so we can't move goalposts. All three DiT-side fixes tagged by Gemini
as NOT requiring codec retraining (pass our hard constraint).
- **#62 latent-conditioning:** ADAA-post-net conditioned on {256-ch SAME latent + decoded audio}
  yields a statistically-significant HF-LSD improvement vs decoded-audio-alone. (CodecFlow
  2603.02022 = real supporting evidence; SPEECH BWE on the codec's own latent — adjacent, not
  a drop-in analogue for our frozen-foreign-codec + audio conditioning.)
- **#66 within-ablation:** DiT on whitened latent with standard-schedule + eps-pred has WORSE
  HF-FAD than same whitened space with ZTSNR + v-pred (proves the three are additive).
- **#66 headline target:** v-pred + ZTSNR on the 1.4B DiT (frozen SAME latent) reduces >8 kHz
  LSD by **>=10%** on the psytrance corpus vs the eps-prediction baseline.

## Track A — Generative pseudo-complex audio post-net (our main HF lever)
Architecture: real-valued **ADAA-SnakeBeta** conv backbone (2× oversampling — matches raw-Snake
4× aliasing suppression at feasible VRAM), **dual-branch pseudo-complex** (APNet2/MP-SENet
style: amplitude predictor + phase-proxy R/I predictor, **arctangent fusion** for correct
[-π,π] bounds) — the affordable complex handling without full CVCNN/Wirtinger cost, fits ~2.5M.
Objective (ranked by the report, verified reasoning):
1. Multi-res STFT **magnitude** loss (does the perceptual brightness lifting).
2. **Adversarial** (multi-period / MetricGAN-style discriminator on the waveform) — forces
   coherent phase hallucination instead of the safe smeared mean.
3. **Anti-wrapping GD/IAF** loss — ONLY as a GAN phase-STABILIZER (structural continuity of
   the hallucinated group delay), NOT to regress the original phase.
   AVOID: standalone RI-complex or standalone phase-derivative loss on a non-adversarial net.

## Track B — DiT-side, for the 188/256 sub-noise-floor directions (needs DiT retrain, allowed)
- **Post-hoc latent whitening:** estimate Σ over a corpus sample → Cholesky whiten (Σ→I)
  between frozen encoder and DiT; train DiT in whitened space; **un-whiten (exact inverse)
  before the frozen decoder.** Lifts low-variance HF directions to unit variance so the
  velocity-target noise floor no longer swamps them. Codec stays frozen (exact bijection).
  Complement/alternative to E1 x0-target — same disease, different cure.
- **v-prediction + zero-terminal-SNR** schedule: standard schedules leave residual signal
  leakage at T that the low-variance channels hide in → never learned → dull at inference.
  ZTSNR forces full destruction; must pair with v-pred (ε-pred degenerates at zero SNR).
  K-RNR NOT needed (pure text-to-audio, no inversion/editing).

## Track C — hardware (LUMI MI250X)
Triton via TorchInductor for the post-net + flow ODE (element-wise ADAA + dense DiT); map
processes to single GCDs (avoid cross-die Infinity-Fabric stalls). NB: connects to the E2
root-cause — the TunableOp/rocBLAS-mismatch path is what to avoid; the Triton path sidesteps it.

## Sequencing (cost-ordered — Kim's lightweight-first method)
1. **#64 regression-ceiling diagnostic** (1 eval, cheapest, GATING): measure >7 kHz phase-coh
   of input vs regression-postnet output vs target on the current ckpt. Confirms the ceiling
   empirically before we build the GAN. If output phase-coh stays ~0.045 → Track A generative
   is mandatory (expected). 
2. **#62 ADAA-SnakeBeta swap** (cheap activation change; helps regardless of the rest).
3. **Track A generative**: add multi-period discriminator + pseudo-complex dual-branch +
   anti-wrapping GD stabilizer. Medium cost, local.
4. **Latent whitening probe** (#65): compute Σ, Cholesky, inspect whitened eigenspectrum (free,
   no training) → small-DiT confirmation run → LUMI.
5. **v-pred + ZTSNR DiT arm** (#65, LUMI, expensive — bundle with whitening).

## Open questions worth a follow-up Gemini brief (if Kim wants)
- Does conditioning the audio post-net on the SAME LATENT (not just decoded audio) raise the
  generative ceiling (more context for phase hallucination)?
- Whitening vs x0-target vs v-pred+ZTSNR: are they redundant or additive for the 188 dirs?
- Measured audio deltas for v-pred+ZTSNR in a FIXED music latent (Gemini flagged this as sparse
  in the literature — a real gap; may need our own ablation to settle).
