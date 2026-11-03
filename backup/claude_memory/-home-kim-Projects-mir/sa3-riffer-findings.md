---
name: sa3-riffer-findings
description: "Hard-won lessons from training the SA3 riffer control-adapter — the chroma-metric trap, mode-collapse vs LR, the gain knob, the audio-save gotcha."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

Training the SA3 decoupled-cross-attn control adapter (`avp_sa3/sa3_control/`, the "riffer")
surfaced reusable lessons. (2026-06-19)

- **Chroma correlation is a TRAP for reference-specificity — it can't see mode collapse.** A
  collapsed adapter (same output for every reference) still scores chroma≈0.9 against any goa
  reference (shared keys). It fooled me into declaring wins twice. **Use cross-reference AUDIO
  difference**: generate with ref A vs ref B (same seed/prompt) → RMS-diff of the outputs. Low
  (<5%) = collapsed/generic; high (16–88%) = genuinely reference-specific. The user's ear was
  right every time the metric wasn't. **The real fix is `merit_eval.py`** (MERT-330M + 3 MERIT
  heads): disentangled `S_mel/S_rhy/S_tim` says *which* factor transferred (`merit_margin` =
  out-vs-own-ref − out-vs-other-ref per factor; >0 = specific). Wired into the bracket via `MERIT_EVAL=1`.
- **Heavier LR mode-collapses.** lr1e-4 stays reference-specific (peaks step~6000, ~88% cross-ref
  diff, then mildly declines — the "elbow"); lr1e-3 starts weaker and fully collapses by step6000.
  Loss is a *non-metric* here (flat 0.735 for both working and collapsed — RF loss is
  noise-dominated). Judge by cross-ref-diff + ears, never loss.
- **Gain knob (generation-time):** SA3-medium's 256-d latent needs control gain >1 (the LatCH
  lesson). By ear: ~1–2 clean, >4 progressive spectral artifacts/clipping. `generate.py --gain`
  default 2.
- **Audio save:** `torchaudio.save` routes through **torchcodec** — *absent* on the 7.14 venv
  (ImportError) and clips fp16 where present. Use `soundfile` PCM_16 via
  `sa3_control.audio_io.save_audio` (peak-norm + int16). Also in MASTER §5.
- **FusionOpt OOMs** at crop 2048 no-checkpoint (spectral state) → run crop≤1024. **Fusion tax
  (matched-crop):** SF-AdamW 1.46 > SF-NorMuon 1.31 it/s (NS5/NorMuon) — slower per-step than AdamW, as in LatCH.

Next direction: [[attribute-branches-milestone]] (explicit feature control > opaque reference).
