# Assessment — six EleutherAI repos as instruments for the SA3 melody wall and provenance work

*(KUANG, October 6, 2026. Source: Kim asked, in the "interpretability" session, whether six EleutherAI repos
could be implemented in the Stable Audio 3 (SA3) pipeline and what each could enable given our work. Method:
READMEs and file trees fetched from GitHub, one search per open question, plus the repo's own
`EXPERIMENTS.md` and the SA3 reference code. **No repo source was read, and nothing was run.** Cost figures
are my arithmetic and untested. The experiments are filed in `EXPERIMENTS.md` § H, entries H9–H14. Companion
to `sa3-attribution-report-assessment-2026-10-06.md`. Decision support, not a finding of fact.)*

## Verdict up front

Only the **ideas** are worth taking; none of the code drops into SA3. Two are cheap forward-only instruments
that share one harness and bear directly on the melody wall (tuned lens, features-across-time); one is cheap
insurance (red-teaming our meters); one is a reimplementation job (attention probes); one is a number for a
question we already ask (tyche); one is expensive and should stay gated (cross-layer transcoders).

| Repo | Verdict | What it would enable | Cost (my estimate) | Entry |
|---|---|---|---|---|
| `tuned-lens` | Port the idea | Layer × timestep map of where melody commits | ≈ 57M translator parameters; forward-only | H9 |
| `features-across-time` | Port the method | When in training each kind of structure is learned; arm triage without rendering | ≈ 4 min per checkpoint | H10 |
| `attention-probes` | Reimplement, do not vendor | Time-localized concept meters on SAME latents and DiT blocks | Low; storage-bound | H11 |
| `tyche` | Port later | A number for "healthier optimum" | ≈ 13 min per 1 000 perturbations | H12 |
| `clt-training` | Donor, gated | Cross-layer features, eventually circuits | Decoder of 1.4–5.7B parameters | H13 |
| `classifier-latent-diffusion` | Skip the repo, keep the idea | Red-team our meters before steering on them | Moderate | H14 |

Ranking by decision value per cost: H10 ≈ H9 > H14 > H11 > H12 > H13. All are read-only forward passes on
checkpoints and therefore reversible, except H13, which is a large build.

## The thread they pull on

The melody wall (`EXPERIMENTS.md` § B). B2 found melody recoverable only in a noise window (R²_melody
.995 / .744 / .011 at t = 0.05 / 0.5 / 0.95); its note says melody is "relational" and no linear channel
subspace captures it; the structural fix B4 costs "weeks + one LUMI run" and is gated on B1/B2 plateauing; and
B2's three checkpoints were reported as rendered but nothing exists. Cheap forward-only instruments could tell
us whether B4 is warranted before that is spent.

## What was read (verified) and what is inferred

- **SA3-Medium structure** comes from Stability's MLX reference port
  (`optimized/mlx/models/defs/dit_mlx_medium.py`), not the PyTorch training code; equivalence is assumed.
  24 blocks, d = 1 536, 24 heads of 64; per block: RMSNorm → differential self-attention → differential
  cross-attention → SiLU-gated feed-forward, with adaLN scale/shift/gate (gate form `sigmoid(1 − gate)`);
  a per-block local-conditioning MLP (257 → 1 536); 64 memory tokens added at entry and removed after;
  `project_in`/`project_out` Linear(256 ↔ 1 536) with 1×1 convs and residuals; no final norm stated.
- **clt-training:** README and tree. Fork of `sparsify`; MIT; HuggingFace decoder-only LMs (GPT-2, Llama,
  Pythia, SmolLM); tokenized `datasets` input; activations computed on the fly by hooks matched on module-name
  patterns; TopK; `torchrun` DDP or `--distribute_modules`; bf16; CUDA PyTorch; TODOs include caching
  activations; per-hookpoint hyperparameters unsupported. A search summary also credits it with DTensor tensor
  parallelism and input hookpoints before layernorm; I did not verify the sparse kernels or ROCm support.
  Another donor, CLT-Forge (arXiv 2603.21014), is also LLM-oriented.
- **tuned-lens:** README only. Per-layer affine translators, KL to the final output distribution, through
  the unembedding matrix; pre-1.0, unstable interface. That it is coupled to HuggingFace LMs is inferred.
  Original paper: arXiv 2303.08112. One search found a "Diffusion Logit Lens" for discrete diffusion language
  models (not opened) and nothing for continuous velocity prediction; that is not proof none exists.
- **attention-probes:** `train_probe()` and `AttentionProbeTrainConfig` take activation tensors
  `[N, T, D]` with mask and labels, so the training side is model-agnostic. Built on MOSAIC, which the README
  calls unlicensed; GitHub's license endpoint returned 404, which normally means no license file.
- **tyche:** Monte Carlo estimate of "behavioral basin" volume; adapters for HF CausalLM, Pythia and
  ConvNeXt on CIFAR-10 (so a non-token path exists); Apache-2.0; the README warns it "can lead to dramatic
  underestimates of basin size"; the more precise `palamedes` module is work in progress.
- **features-across-time:** Pythia n-gram scripts, plotting, vision scripts; MIT; authors call the code
  sloppy. That it accompanies "Neural Networks Learn Statistics of Increasing Complexity" (arXiv 2402.04362)
  is **inferred** from file names and a search; the method description (compare model behavior on real data
  against synthetic data matched to order-k statistics, per checkpoint) is my understanding of that paper,
  which I did not read here.
- **classifier-latent-diffusion:** DDIM inversion → classifier on reconstructions → adversarial search in
  latent space, to test whether diffusion latents resist adversarial attack. CIFAR-10 and MNIST only;
  8 files, 6 commits, 1 star, no stated license or dependencies; appears dormant.

## What each could enable, in light of our work (estimates)

1. **Tuned lens (H9).** Adds a depth axis to B2's timestep curve: R²_melody(block, t) through the linear
   chroma readout. If melody decodes only in the last few blocks, B4's early "melody-first" noising is better
   motivated; if it appears mid-network and is lost later, we learn where to inject, since every block has its
   own local-conditioning inlet, and B7's adapter placement could target those blocks. Speculative extras: a
   "decode at block ℓ" scrubber in Latent Forge; cheaper intermediate readouts for guidance. Dud: melody
   decodes only at the final block.
2. **Features-across-time (H10).** Judges arms without rendering, which matters because B2's checkpoints were
   never rendered. Tests B1–B5 as a family (does reweighting open a melody-level gap earlier?), can add a
   structure term to soup selection (C2 uses PQ × crest × whitening) and sharpens A12's "lightly-trained
   property" question across its 24 rungs. Dud: the gap opens early on low-level spectrum statistics and never
   discriminates.
3. **Attention probes (H11).** Concept meters independent of the audio path: a learned rhythm-integrity meter
   for G1, time-localized acid-sweep and bassline detection for H6, a readout for the Latent Forge statistics
   panel (M10). About 23 000 tracks of MIR features supply labels, with the classifier errors the repo has
   found before (genre-blind and ungrounded captions). A decodable feature is not necessarily a used one.
4. **Tyche (H12).** A quantitative proxy for A12's "healthier optimum" (5e-5 stays musical under cfg16/w2 push
   where 1e-4 and 2e-4 melt) and for the optimizer and rank comparisons (A1, A2, A6); possibly soupability
   (my inference). A loss-along-perturbation or interpolation curve gives most of that in about 50 lines.
5. **CLT (H13).** Cross-layer features and eventually circuits, but it decomposes feed-forward layers only.
   Melody is "relational" (B2) and feed-forward layers act per position, so I infer the relational structure
   sits in attention, which a CLT does not decompose. Feature knobs need only per-layer SAEs.
6. **Red-teaming meters (H14).** Our meters have failed before: the onset-timing metric read 0.795–1.000 on
   every arm including the foreign control, PQ has a sparse-material blind spot, and CE correlates about zero
   with Kim's judgment. The steering plans in the Gemini assessment (AID, FK-Flow) use the whitened-patch
   recurrence meter as a reward, which is exactly what a latent search will exploit.

## Cost arithmetic (assumptions stated; all untested)

Forward pass ≈ 2·N FLOP per token with N = 1.4B and 512 latent frames per crop: ≈ 1.43 TFLOP per crop. Ignores
the attention T² term and the 64 memory-token positions (about +12.5% positions). 30 TFLOP/s effective
throughput assumed.

- **H9 lens training:** 24 translators × 1 536² ≈ 56.6M parameters. 100 000 crops ≈ 143 PFLOP ≈ 1.3 h.
- **H10:** 256 crops × 4 timesteps × 5 conditions = 5 120 forwards ≈ 7.3 PFLOP ≈ 4.1 min per checkpoint;
  24 rungs ≈ 1.6 h.
- **H12:** 1 000 perturbations × 16 crops ≈ 22.9 PFLOP ≈ 13 min.
- **H11 storage:** 10 000 clips × 512 frames × 1 536 dimensions × 2 bytes ≈ 15.7 GB per (block, timestep).
- **H13 decoder:** F × 1 536 × 300 layer pairs (24 + 23 + … + 1 = 300): ≈ 1.42B parameters at F = 3 072,
  ≈ 5.66B at F = 12 288.

## Open questions

- Are the checkpoint ladders reachable after the `/py` move and the LUMI scratch purge? If not, H9 runs on the
  base model first and H10 waits.
- Surrogate construction for higher-order musical structure (H10) is the main open design problem.
- ROCm and kernel support for any CLT donor code is unverified; XPU reduced precision produces NaN for
  medium-class models, so lens and probe runs on the Arc laptop must use fp32.
- Licensing (attention-probes' unlicensed lineage, tyche's Apache-2.0 terms, Stability's Community License) is
  a Legal question if any of this leaves private use; not answered here.

## Sources

- [EleutherAI/clt-training](https://github.com/EleutherAI/clt-training) · [CLT-Forge, arXiv 2603.21014](https://arxiv.org/html/2603.21014v1)
- [EleutherAI/tuned-lens](https://github.com/EleutherAI/tuned-lens) · [Tuned Lens paper, arXiv 2303.08112](https://arxiv.org/pdf/2303.08112)
- [EleutherAI/attention-probes](https://github.com/EleutherAI/attention-probes)
- [EleutherAI/tyche](https://github.com/EleutherAI/tyche)
- [EleutherAI/features-across-time](https://github.com/EleutherAI/features-across-time) · [Neural Networks Learn Statistics of Increasing Complexity, arXiv 2402.04362](https://arxiv.org/pdf/2402.04362)
- [EleutherAI/classifier-latent-diffusion](https://github.com/EleutherAI/classifier-latent-diffusion)
- [SA3 MLX DiT definition](https://github.com/Stability-AI/stable-audio-3/blob/main/optimized/mlx/models/defs/dit_mlx_medium.py)
