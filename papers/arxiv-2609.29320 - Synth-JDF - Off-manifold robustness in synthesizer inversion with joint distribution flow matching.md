# Off-manifold robustness in synthesizer inversion with joint distribution flow matching ("Synth-JDF", 2609.29320v1) — deep-read

Ben Hayes (Sony CSL Paris). ISMIR 2026 (Abu Dhabi), arXiv v1 24 Sep 2026, 8 pages + a 3-page supplement
(`... - supplementary.pdf` beside this note, fetched from benhayes.net/synth-jdf/static/pdfs/sup.pdf on
2026-10-07 after the author pointed us to its §3.1.2). Audio: benhayes.net/synth-jdf. No code linked.
**Read in full by W 2026-10-07**, paper and supplement.

## What it shows
- **Idea.** Model the JOINT distribution of synth parameters x and audio y with one multi-modal rectified
  flow, each modality with its own time variable t = (t_x, t_y) on the unit square (OmniFlow / UniDiffuser
  construction). The square's edges are the special cases: top edge t_y=1 = ordinary conditional inversion
  p(x|y); left edge t_x=0 = audio marginal p(y), trainable on UNLABELLED real audio; bottom edge = parameter
  marginal, which gives classifier-free guidance for free (no conditioning dropout).
- **Mechanism claimed.** Trained over the full square, the model mostly sees PARTIALLY NOISED spectrograms,
  so its velocity field is learned in a neighbourhood of the synth's audio manifold; real (off-manifold)
  audio is then less of an extrapolation. At inference, conditioning on partially noised reference audio
  Y_tau = (1-tau)Y0 + tau*y* acts as a smoothed posterior.
- **Architecture.** One DiT (8 blocks, d 768, 12 heads) over concatenated mel-patch tokens (stereo log-mel,
  128 bands, 25/10 ms; 1-D conv k2 s2 over time, full spectrum per token) and per-parameter tokens; two
  sinusoidal time embeddings -> AdaLN; per-modality output heads. Baseline "Conditional" = AST encoder ->
  per-layer conditioning of a parameter DiT (the 2025 Param2Tok paper's model).
- **Parameter tokenizer (supplement §3.1.2), the one the author recommended to us:** feature tokenisation
  from tabular DL (Gorishniy et al. 2021). Scalars in [0,1], categoricals one-hot; element-wise multiply by
  a learned W (d_vec x d_model), sum within each parameter's entry/one-hot block -> ONE token per parameter,
  plus a learned per-parameter bias. Inverse projection follows the same grouping (each token broadcast to
  its block, then a learned output matrix). MIDI pitch (discrete, 36-84) and note duration (1-4 s) appended
  as parameters. Surge XT N=140 params (d_vec 290), Dexed N=105 (226).
- **Data.** Uniform random parameters rendered ONLINE, FX off, non-deterministic modulators off, samples
  below -60 dBFS rejected. Off-manifold set: 617k Freesound single-event files + a proprietary one-shot
  library, padded/trimmed to 3 s, used only on the audio-marginal edge.
- **Results (Surge XT, Table 1, 10k test each).** Real audio MSS: Conditional 15.50 -> JDF 7.68 (JDF-A 7.69);
  in-domain 10.38 -> 6.30. Ablation Unif-ParamOnly (same DiT, conditional edge only) 11.35 real / 9.13
  in-domain -> architecture contributes a little, the joint objective most. Dexed (JDF-A vs Conditional only):
  real 13.03 -> 7.98. Adding 617k real recordings (JDF-A) changes nothing (7.68 vs 7.69) — honest negative.
  CFG helps all JDF models; it HURTS the Conditional baseline off-manifold.
- **Recipe.** Rectified flow, linear interpolants, logit-normal times, Euler 20 steps, CFG on interval
  [0.15, 0.95]; Adam 2e-4, 2k warm-up, cosine to 0.01x, clip 1.0, bf16, batch 64, NO EMA; MAE velocity loss
  slightly better than MSE (supplement). Metrics: MSS, wMFCC, SOT (spectral optimal transport), RMS-envelope cos.

## Caveats (W's read — check before citing a number)
1. **Which tau / CFG the tables use is never stated.** Both are swept on the TEST sets (Figs. 4–5). Read off
   the plots (approximate): the Conditional baseline is ~20 MSS on real audio with clean conditioning vs 15.50
   in Table 1, and JDF's best is near tau ~0.1 (90% noise). If table values are per-model best points chosen
   on test, every number is optimistic (baseline included).
2. **Best at 90% conditioning noise + a non-monotonic curve** (good at 0.1, worse ~0.3, middling clean)
   suggests MSS rewards coarse matching (loudness envelope, overall spectrum), helped by the test material:
   one-shots padded to 3 s, many with silent tails.
3. **SOT, the frame-energy-invariant metric, goes the OTHER way off-manifold on Surge** (Conditional 0.232 vs
   JDF 0.317). Part of the headline gain may be envelope/silence matching rather than timbre.
4. **Paper vs supplement disagree:** 1.5M vs 500k steps; 3.0 s audio vs a 4 s / 401-frame spectrogram;
   continuous params in [-1,1] vs [0,1].
5. No seeds/CIs, no human evaluation (author says it is needed), Dexed without the full ablation, test
   material = isolated one-shots (easier than bass phrases from separated mixes).

## Relevance to us (synth inversion, `stable-audio-tools/scripts/synth_inversion/`)
- Our flow inverter (`models.py::FlowMatchingResMLP`) is the paper's WEAK case: conditional-only, trained on
  clean conditioning, and its parameter vector enters through ONE linear layer (mixes all parameters).
- Our Synth-JEPA parameter encoder already uses the per-parameter tokenizer form (+ Perceiver); see the
  2025 Param2Tok sidecar for what Param2Tok is.
- Ideas logged as **H5–H7** in `EXPERIMENTS.md` (noisy-conditioning test with no training; noisy-conditioning
  augmentation vs joint objective; per-parameter tokens + MAE + CFG for the inverter).
