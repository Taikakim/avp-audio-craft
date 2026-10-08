# Implementation Plan: Masked Drum Inpainting & Latent Stem Crossfades

Now that tempo locking (exact linear regression `1.03010`) and sub-millisecond kick phase alignment (`b_lo -= shift`) are established, we evaluate two targeted generative enhancements to replace the risky A2A full-mix pass:
1. **Masked Inpaint for the `drums` stem:** Retaining Track A's drum groove on the left and Track B's drum groove on the right, inpainting only a 2-bar or 4-bar rhythmic fill/bridge in the center.
2. **Latent Crossfade for the `other` stem:** Encoding `other_a` and `other_b` to latent space via the pretransform VAE, applying `slerp` interpolation, and decoding, eliminating time-domain comb filtering without generative hallucination.
3. **Full-Mix 3x Extension Roadmap:** Planning pre- and post- outpainting extensions of clips using the base model (`medium-base`) anchored by fine-tuned priors.

---

## User Review Required

> [!IMPORTANT]
> **Boundary Conditions for Drum Inpainting:**
> For the 8-bar transition window ($L = 14.08\text{ s}$ at $136.06\text{ BPM}$):
> - **Option 1 (2-bar fill bridge):** Keep Track A drums for Bars 1–3 ($0.0\text{–}5.3\text{ s}$), inpaint Bars 4–5 ($5.3\text{–}8.8\text{ s}$), keep Track B drums for Bars 6–8 ($8.8\text{–}14.1\text{ s}$).
> - **Option 2 (4-bar extended bridge):** Keep Track A drums for Bars 1–2 ($0.0\text{–}3.5\text{ s}$), inpaint Bars 3–6 ($3.5\text{–}10.6\text{ s}$), keep Track B drums for Bars 7–8 ($10.6\text{–}14.1\text{ s}$).
> We will generate and compare both on Transition 0.

---

## Proposed Changes

### Evaluation & Render Modules

#### [NEW] [eval/render_v7_inpaint_trans.py](file:///home/kim/Projects/SAO/eval/render_v7_inpaint_trans.py)
A standalone test script for Transition 0:
* **Tempo & Phase:** Uses exact Bungee stretch `1.03010` on Track 0 stems and `b_lo -= shift` on Track 1.
* **`drums` stem:**
  * Constructs `inpaint_audio` placing Track A's drums from $t = 0$ to $t_{start}$, silence/crossfade guide during $[t_{start}, t_{end}]$, and Track B's drums from $t_{end}$ to $L$.
  * Calls `model.generate` with `inpaint_audio`, `inpaint_mask_start_seconds=t_start`, `inpaint_mask_end_seconds=t_end`.
  * Tests both base model (`medium-base`) and destination LoRA adapter.
* **`other` stem:**
  * Computes latent slerp crossfade:
    $$z(t) = \text{slerp}(z_A, z_B, t)$$
    $$\text{other}_{\text{slerp}} = \text{pretransform.decode}(z(t))$$
* **`bass` stem:**
  * Preserves the Linkwitz-Riley 4th order 50ms hard handover (`lr4_split` + `bass_handover`).
* **`vocals` & `residual`:**
  * Clean crossfades.
* **Outputs:**
  * `trans0_inpaint_drums_2bar.wav` (with latent other + LR4 bass)
  * `trans0_inpaint_drums_4bar.wav` (with latent other + LR4 bass)
  * Isolated stems for inspection (`trans0_inpaint_drum_stem.wav`, `trans0_latent_other_stem.wav`)

---

## Verification Plan

### Automated Tests
1. Verify unit tests continue to pass:
   ```bash
   python -m pytest eval/tests/test_mixtape_v7_dsp.py eval/tests/test_render_v7_smoketest.py
   ```
2. Run `eval/render_v7_inpaint_trans.py` to produce the candidate WAV files.

### Physical & Perceptual Timing Checks
1. Measure kick drum intervals across the inpainted drum bridge to ensure the model preserved the $136.06\text{ BPM}$ grid throughout the masked region without galloping.
2. Spectral analysis on the latent crossfaded `other` stem to confirm smooth harmonic evolution without phase comb filtering.
3. Compare against [`v7_smoke_trans_FAST_0_clean_dsp.wav`](file:///home/kim/staging/kone-mixtape/smoke/kuang_smoke/v7_smoke_trans_FAST_0_clean_dsp.wav).
