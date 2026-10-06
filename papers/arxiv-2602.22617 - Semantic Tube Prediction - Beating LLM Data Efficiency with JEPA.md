# Semantic Tube Prediction: Beating LLM Data Efficiency with JEPA (2602.22617v1) — read

Hai Huang (Atlassian), Yann LeCun (NYU), Randall Balestriero (Brown). arXiv v1 26 Feb 2026, 21 pages.
Code: github.com/galilai-group/llm-jepa#stp. Same group as LeJEPA/SIGReg (which our Synth-JEPA uses).
PDF beside this note. **Read by W 2026-10-06 (method, experiments §4, λ tuning; proofs skimmed).**

## What it shows
- **Geodesic Hypothesis:** with teacher forcing, a converged autoregressive LM's hidden-state trajectory
  over a token sequence behaves like an ODE solution; error-free trajectories are geodesics on a smooth
  manifold, hence locally straight. Deviations perpendicular to the straight line = noise; the parallel
  component = signal.
- **STP loss:** for random token positions s < r < t of the last-layer hidden states,
  `L_STP = 1 − cos(h_t − h_r, h_r − h_s)`, added as `L = L_NTP + λ·L_STP`. Identity predictor (a learned
  projection P was worse), no extra forward passes, no hand-made multi-view augmentation.
- **Results:** fine-tuning Llama-3 1B/3B/8B, Gemma-2, Qwen3, OLMo, OpenELM on structured text tasks
  (NL-RX-SYNTH regex synthesis and similar). Matches full-data baseline accuracy with 1/16 of the
  training data on NL-RX-SYNTH; negligible drop when data is halved where plain fine-tuning drops.
  λ curve concave, best 0.01–0.08 across models/datasets. Claims better SNR and diversity (fewer
  trajectory collisions / mode collapse).

## What it does NOT show
- No audio, no images, no diffusion or flow models, no non-autoregressive model. Accuracy metrics only,
  on synthetic/structured text. Data-efficiency claim ("violates Chinchilla's data term") is from
  fine-tuning sweeps, not pretraining scaling.

## FOR US
- **Synth-inversion JEPA: worth testing.** The ladder batches in `training_controls.py` sweep one Surge
  control with everything else fixed; the current ordinal loss only asks that distance from the first
  step grows monotonically. STP's collinearity is the stronger prior: along a single-control sweep the
  audio embeddings should lie on a locally straight path, which is exactly what the JEPA search's Adam
  stage and the bracketed refinement assume. Test: add `1 − cos(z_t − z_r, z_r − z_s)` on random ladder
  triples at λ ≈ 0.02 in the next run; judge on the held-out ladder metrics (per-axis Spearman) and
  real-stem refinement. Caveat: perceived timbre is not linear along a whole cutoff sweep — mild prior.
- **SA3 DiT / LoRA fine-tunes: not applicable as is.** The premise needs causal, teacher-forced
  next-token prediction; the DiT denoises all frames jointly, and musical hidden states SHOULD revisit
  earlier states (loops, sections), contradicting "trajectories never cross". The analogous straightness
  that matters there — along noise time — rectified flow already enforces.
- **Any future token model** (MIDI/chord LM on MuScriptor transcriptions) can take it directly.
