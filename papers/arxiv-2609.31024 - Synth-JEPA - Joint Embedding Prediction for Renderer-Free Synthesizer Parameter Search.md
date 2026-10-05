# Synth-JEPA: Joint Embedding Prediction for Renderer-Free Synthesizer Parameter Search (2609.31024v1) — deep-read

Hayes, Tian, Lattner (Sony CSL Paris; QMUL). arXiv v1 25 Sep 2026, 5 pages (ICASSP format). Audio:
benhayes.net/synth-jepa. No code release linked. PDF beside this note. **Read in full by W 2026-10-06**,
together with a line-by-line check of our implementation (`stable-audio-tools/scripts/synth_inversion/`,
branch `feature/surge-xt-neural-inversion`).

## What it shows
- **Model.** Audio encoder E_a (transformer on stereo log-mel, 128 bands, 25 ms / 10 ms, stride-2 1D conv to
  150 tokens, summary token -> z_a in R^512) and parameter encoder E_p (per-parameter linear projection +
  parameter-specific bias; Perceiver with 32 latents, one cross-attention, 8 self-attention blocks, mean ->
  z_p). Two cross-domain predictors (3-block residual MLPs, width 1024). 53.3M params, d = 512, 8 heads.
- **Loss.** L_pred = MSE(f_a->p(z_a), sg(z_p)) + MSE(f_p->a(z_p), sg(z_a)), plus **SIGReg** (LeJEPA) on each
  encoder branch independently (LeVLJEPA). An EMA-teacher (SLAP-style) variant is strictly worse on every
  dataset and metric — the anti-collapse choice shapes the search geometry.
- **Data.** Surge XT, 139 parameters, uniform prior, effects off, non-deterministic modulators off; 3.0 s
  stereo rendered ONLINE. Input normalisation: channel-wise Welford mean/var over the first 8k spectrograms,
  then frozen. Training: 1M steps, batch 64, AdamW 3e-4, WSD schedule, wd 0.05.
- **Search (Eq. 4–5).** D_JEPA(y*, x) = MSE(z_a*, f_p->a(E_p(x))) — no synth calls. Half the budget: JADE,
  population 32 (categoricals copied or resampled); then the best 8 refined by Adam on continuous params
  (lr 0.1, cosine to 0), pruned by half three times; 2048 objective evaluations per target.
- **Results (Table 1, 1024 targets per set).** In-domain MSS 8.44 vs flow matching 12.75 vs log-mel
  renderer-in-the-loop search (2048 renders) 15.86; best or second-best out of domain (NSynth, FSD50K)
  except wMFCC. Keeps improving with search budget where flow matching saturates past ~16 ODE steps (Fig. 2).
  Optional best-of-k over RENDERED candidates using **log-mel L1** helps both, flow more steeply (its
  posterior holds good solutions it does not reliably sample) (Fig. 3). Listening test: Synth-JEPA
  preferred in 85% of pairwise trials (18 listeners).
- **Metrics** "following [1]" (Hayes et al. ISMIR 2025, synth-permutations): multi-scale log-mel L1 (MSS),
  DTW-warped MFCC (wMFCC), CLAP cosine.
- **Stated limit.** The parameter prior induces the audio geometry; "audio-aware sampling strategies" left
  to future work.

## Our implementation vs the paper (checked 2026-10-06)
Matches: E_a/E_p/predictor architecture, stop-gradient targets, SIGReg closed form (Epps–Pulley with a
N(0, 1) weight — verified against the derivation), Welford-then-freeze normaliser, JADE+Adam two-stage search
(v2 review), WSD-style schedule, batch 64.
Deliberate deviations (keep, but know they exist): 23 bass parameters from a **preset-derived prior** (not a
uniform 139-d prior) — the paper's own "future work" point, and the reason our searches land on sounds people
use; mono 0.8 s clips (41 tokens, not 150); n_fft 1024 (23.2 ms window); the mel is per-clip dB-normalised
BEFORE Welford; ff_dim is a guess (paper silent); ModularOptimizer instead of AdamW; ~78k steps, not 1M.
Gaps found:
1. **Metrics were not the paper's.** `audio_utils.MultiScaleSTFTLoss` and `audio_utils.compute_wmfcc` share
   the names but not the definitions, so our numbers are not comparable to Table 1. Exact ports now in
   `reference_metrics.py` (`mss`, `wmfcc`, `rms_env_cos`; wMFCC matches dtw-python to 6 decimals).
2. **The flow baseline is not the paper's.** [1] uses minibatch-OT coupling (Hungarian noise↔target matching,
   `synth-permutations/src/data/ot.py`) and a symmetry-aware flow; ours samples noise independently. OT
   coupling is a cheap add for the next retrain; symmetry only matters once oscillators are interchangeable
   (the 139-d space), not for the 23-d bass space.
3. **Best-of-k selector.** Paper: log-mel L1. Our reranker: composite led by MultiScaleSTFT. Human-timbre
   check (`timbre_alignment_check.py`, 21 datasets of Ben Hayes' timbre-dissimilarity-metrics): mean Spearman
   with listener dissimilarity — log-mel L1 0.473, paper MSS 0.470, our STFT 0.437, JEPA z_a 0.419 (bass-only
   model, out of domain), wMFCC 0.392, RMS envelope 0.307 (but best on envelope-driven sets). => use log-mel L1.
4. `--batch_schedule` can shrink the batch to 2; SIGReg is a batch statistic and is meaningless there. The
   current runs use constant 64 — keep it that way.
5. The mel front end has only 4 FFT bins below 131 Hz, which caps cutoff resolution in the low-bass region.

## FOR US / what stays ours
- Renderer-free search is the paper's contribution; **our renderer-in-the-loop refinement of salient axes
  (cutoff, envelopes) after flow/JEPA proposals is not in it** — it sits on the paper's Fig. 3 observation
  (rendered best-of-k helps flow most) and pushes it further into coordinate search.
- The preset-derived prior, pitch pinning, and the bass-specific reranker descriptors are ours.
- Next-retrain candidates from this read: OT minibatch coupling for the flow; low-band input resolution;
  ladder ("bracket") batches as audio-aware sampling — the paper names exactly this as open.
