# Audio synthesizer inversion in symmetric parameter spaces with approximately equivariant flow matching (2506.07199v1) — deep-read

Hayes, Saitis, Fazekas (QMUL C4DM). ISMIR 2025 (Daejeon), 23 pages incl. appendices. Code:
github.com/ben-hayes/synth-permutations; audio benhayes.net/synth-perm. **Read in full by W 2026-10-07.**
This is reference [11] of Synth-JDF and the source of **Param2Tok** and of the metric suite we ported
(`synth_inversion/reference_metrics.py`).

## What it shows
- **Problem.** Synths with repeated units (oscillators, filters, LFOs) are permutation-symmetric: many
  parameter vectors give the same sound, so the inverse is multi-modal. Regression (even with Chamfer /
  sort / permutation-invariant losses) averages across modes — the "responsibility problem".
- **Theory.** p(x|y) factorises into orbit x symmetry x stabiliser; if likelihood and prior are G-invariant
  (true for uniform random parameters, NOT for preset-based data) the symmetry factor is uniform, so a
  G-invariant density is the right target -> an equivariant CNF (Köhler et al.).
- **Param2Tok.** P2T(x) = A · h_theta(diag(x) Z): each parameter scales its learned embedding row z_i, a
  row-wise FFN, then a learned SPARSE assignment matrix A (k params -> n tokens, L1-penalised, initialised
  near-invariant) MIXES parameters into n learned tokens (n=128 for Surge). Inverse via weight-tied A^T and a
  second embedding Z'. The idea: let the model discover which parameters form interchangeable groups
  (e.g. one token per oscillator), and break the symmetry where the synth is not symmetric. Proof that it can
  represent a conditional symmetry (Appendix A.4). Learned A on Surge shows repeated per-oscillator / per-LFO
  structure (Figs. 10–13).
- **k-osc toy (k identical oscillators, symmetric vs frequency-split asymmetric variant).** The predicted
  crossover is clean: the fully equivariant CNF wins symmetric / loses asymmetric, MSE regression the
  reverse; CNF(Param2Tok) matches the best in both.
- **Surge XT (2M random samples each; Simple 92 params, Full 165 incl. routing + FX).** In-domain MSS:
  CNF(Param2Tok) 3.18 / 6.13, CNF(MLP) 3.53 / 7.35, AST regression 6.51 / 14.73, VAE+RealNVP 26.23 / 28.86
  (collapses to averages). Out of domain (trained on Full): NSynth 11.04, FSD50K 15.40 for the best model —
  every model degrades heavily (the gap Synth-JDF later attacks).
- **Recipe.** Rectified flow + minibatch OT coupling (Hungarian), 10% conditioning dropout, CFG 2.0, RK4
  100 steps; DiT with AdaLN (Ada-LN-ZERO init found to HURT); AST encoder with 8 learned per-layer query
  tokens; Adam 1e-4 cosine to 1e-6, 1M steps, batch 128, bf16, clip 0.5. Notes pitch and on/off times are
  predicted parameters (pitch uniform over 2 octaves around C4).
- **Metrics (Appendix C), our port matches:** MSS = L1 of log-mel at (10/25/100 ms windows, 5/10/50 ms hops,
  32/64/128 mels) averaged; wMFCC = 20 MFCCs, 10 ms hop, DTW with L1; SOT = Wasserstein-1 between normalised
  magnitude spectra (NOT ported by us); RMS = cosine of frame RMS envelopes.

## Caveats
1. One training seed per model; the 95% intervals are over test examples, not seeds.
2. Param2Tok initialisation/regularisation hand-tuned ("still warrant ablation" per the authors).
3. No listening test; uniform-random training data makes in-domain numbers say little about real patches.
4. Surge *Full* renders chorus/delay/reverb through pedalboard. In OUR setup (pedalboard + Surge XT) chorus
   and delay state persisted across renders in one instance (`synth-inversion-fx-leak`, fixed 2026-10-06). The
   paper does not say whether instances were reset; Synth-JDF later turned FX off. Unknown, worth asking.

## Relevance to us
- Our 23-parameter bass spec (one osc, one filter, one each of the envelopes) has almost no permutation
  symmetry, so equivariance buys little NOW; it matters for H3 (parameter extension) / the 139-param spec.
- Directly reusable: OT coupling (H1 has it), CFG with conditioning dropout (our inverter has none), RK4
  sampling, SOT metric.
- **Ben Hayes' comment (2026-10-06, relayed by Kim):** his newer one-token-per-parameter tokenizer (Synth-JDF
  supplement §3.1.2) behaves better than Param2Tok for Synth-JEPA. Our Synth-JEPA encoder already uses that
  per-parameter form, not Param2Tok.
