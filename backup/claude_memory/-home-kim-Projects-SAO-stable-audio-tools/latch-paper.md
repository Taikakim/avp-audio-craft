---
name: latch-paper
description: "KEY — how to interpret the LatCH paper (arXiv 2603.04366) and map its Selective-TFG spec onto this codebase, with the pitfalls"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ccd33273-2ad9-4e1a-a571-5a74da061b46
---

**Paper:** "Low-Resource Guidance for Controllable Latent Audio Diffusion" (Novack et al.), arXiv **2603.04366v1**. Local PDF: `/home/kim/Documents/2603.04366v1.pdf`. Orchestration ref: `scripts/LATCH_README.md` and `/home/kim/Projects/mir/LATCH_CONTROL.md`.

## LatCH-F vs LatCH-B
- **LatCH-F (forward-simulated noise)** — implemented. The head is trained on latents noised by a *forward* schedule. **That schedule MUST match the diffusion model's objective** (rectified_flow linear for Small, NOT VP cosine — the original code's bug). See [[latch-overview]].
- **LatCH-B (backward / trajectory-simulated noise)** — NOT implemented. The paper reports it performs better; it noises by simulating the actual sampling trajectory. Candidate future work.

## Selective TFG components (map to `sample_euler_latch_guided`)
- **Variance guidance (ρ):** gradient of the head's loss w.r.t. the noisy latent `z_t`, applied as `x ← x − rho_t·∇`. Query the head at the latent's true timestep.
- **Mean guidance (μ):** iterate `N_iter` times on the clean estimate `z_{0|t}`: `z0 ← z0 − mu_t·∇loss(head(z0+noise·γ), target)`. Query head at t=0.
- **γ noise augmentation:** perturbs the **INPUT** estimate (`head(z0 + ε·γ)`) to smooth the guidance — NOT added to the head's output. (Original code added it to the output and scaled by s_t → did nothing.)
- **Time weighting `s(t)=α_t/Σα_t`:** down-weights high-noise steps — see [[latch-sigmas-schedule]] for why this makes the early-window default inaudible.
- **N_recur:** recurrence (re-noise and redo a step); paper uses 1.
- Loss is feature-specific: BCE-logits (beat/onset), cosine (hpcp/chroma), MSE (rms/spectral/tonic) — must match at guidance time too.

## Paper hyperparameters & the big caveat
- Paper: ρ=μ=0.03, γ=0.3, N_iter=4, N_recur=1, 100-step stochastic DDIM, CFG=7.
- **CAVEAT: ρ=μ=0.03 is essentially inaudible on this Small/RF setup.** Don't trust the paper's absolute gains here — they targeted a different model/schedule. On Small you need gain ~1–10 and the window in the back half. Verify control empirically (see [[latch-verification]]), don't assume the paper's numbers transfer.

## Interpretation pitfalls (learned the hard way)
1. Match the **forward-noising schedule** to the model objective.
2. Query the head at the **actual σ/timestep**, not a linear step fraction (RF schedule is nonlinear).
3. The **window/`s(t)`** interaction means "first 20% of steps" is a dead zone for RF — put guidance where α is large.
4. γ augments the **input**, not the output.
5. Use the **training-matched loss** during guidance.

See [[latch-overview]], [[latch-sigmas-schedule]], [[latch-verification]].
