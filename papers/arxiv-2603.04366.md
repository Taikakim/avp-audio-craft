# Low-Resource Guidance for Controllable Latent Audio Diffusion (2603.04366)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). Stability AI + UCSD (Novack,
Zukowski, Carr, Parker, **Zach Evans**, Taylor, Berg-Kirkpatrick, McAuley, Pons), built on
**Stable Audio Open**. ⚠️ **This is the origin/formalization of "LatCH"** — and it means something
different here than in our tree. Reconcile before porting claims.*

**What it contains.** Two inference-time control tricks, no base retraining. (1) **Latent-Control
Heads (LatCHs)** = lightweight regressors mapping the diffusion *latent* directly to a target
control feature (`C(D(z₀)) ≈ c_φ(z₀)`), so guidance gradients **skip the expensive VAE-decoder
backprop** end-to-end guidance needs. Noise-conditioned to match inference-time noisy latents,
trained either by forward-diffusion (**LatCH-F**) or on **generated reverse-trajectory latents
(LatCH-B**, the winner). (2) **Selective TFG** = apply Training-Free Guidance gradients only on the
first ~20% of steps (cheaper, less off-manifold drift). Results: LatCH-B ≈ end-to-end control at
**~6× faster, ~5× less VRAM**; 1D low-freq controls (intensity/RMS, beats/onset) **succeed**,
sparse high-dim (pitch 160-bin, chroma 12) **fail** across all methods. ~7M params (<1% of base),
~4 h on one H100, same 970 h corpus as SAO. **v-parameterization, 100-step DDIM, CFG 7** — not
flow-matching; VAE latent at **21.5 Hz / 64-ch**.

**Status vs our work — the namesake paper, with a terminology fork to settle.** Here **LatCH is a
guidance READOUT head** (predicts a control feature so you can take a distance-gradient at
inference), **not** a training-time FiLM/conditioning adapter. If our "LatCH" injects control, the
two sit on opposite sides of the **guidance-vs-conditioning axis** — same name, different mechanism
— and any claim ported between them must be re-checked (flag for C, whose lane this is). What ports
cleanly: **(a)** the **1D-low-freq-works / sparse-high-dim-fails** finding directly constrains our
control-adapter targets — favors onset/RMS/intensity, cautions against pitch/chroma control, and
**gets worse at our coarser 10.77 Hz SAME** (they're already at 21.5 Hz); it independently predicts
our Head-A pitch-readout ceiling. **(b)** **LatCH-B's train-on-generated-reverse-trajectories** is
the transferable discipline — match any latent regressor's training noise to inference latents (we
half-know this from Head-B). **(c)** **Selective-TFG (steer early window only)** = a compute/manifold
lever, but the 20% figure needs re-tuning for our step schedule. What needs re-derivation / remains
ours: the **TFG variance/mean guidance math is DDIM/score-based** — porting to SA3's rectified-flow
requires re-deriving against the flow velocity; and our SAME domain + the disintegration gate.
Cheap (<1%-params, ~4 h, same-corpus) heads also make **per-genre (goa) control heads feasible
under data limits** — the paper's whole "low-resource" premise, directly on-point for our niche.
