# Assessment — "Stable Audio 3 Medium Base: attribution, provenance and interpretability architecture" report

*(KUANG, October 6, 2026. Source: a research report Kim pasted into a session on October 5, 2026. It is not
archived verbatim in the repo (it arrived with stray CSS and garbled math), so its load-bearing content is
summarized in §1. Verify-first applied: the 2026 references it leans on were checked against primary or
secondary pages where they would open; §3 separates what was verified, inferred and left unchecked. The
experiments this produced are filed in `EXPERIMENTS.md` § H. This is decision support for Kim's review, not a
finding of fact about any model or dataset.)*

## Verdict up front

**A sound research plan, largely orthogonal to the Latent Forge integration, and its literature holds up where
checked.** But it was written without sight of this repo, and five of its premises differ from what the repo
records (§4). Three additions matter more than its 40/30/15/15 effort split:

1. **Log training events in the next run (H1).** It is the only item whose value is lost by waiting; a finished
   run without logs can only ever be explained by retrieval and probes.
2. **The existing 8-replica DoRA ladders (A10) may already give the retrain-noise floor (H2)** that the report
   never measures. Without a noise floor no removal experiment can be interpreted.
3. **Make every attribution claim a delta against the un-fine-tuned model (H4).** The base model's pretraining
   data is not in any corpus we hold, so "nothing in the corpus resembles this" does not mean "novel".

## 1. What the report proposes (summary)

- **Four evidence layers, kept separate until calibrated:** retrieval and memorization; representation analysis
  (probes, SAEs — sparse autoencoders — and activation patching); formal influence (EK-FAC, Eigenvalue-corrected
  Kronecker-Factored Approximate Curvature; TRAK; TracIn; SOURCE; MAGIC); controlled retraining. Effort split
  40/30/15/15 against Kim's prior of 75/20/5 (retrieval / representation / formal influence).
- **The causal estimand is counterfactual influence** Δᵢ = m(θ_{D∖i}) − m(θ_D); everything else is an
  approximation or a candidate generator. A report must never say "Track X contributed 12%"; the defensible form
  is a rank plus an effect under intervention, with an interval, against matched controls.
- **Retrieval over four indices** (SAME latents, CLAP/MERT embeddings, factor-specific MIR descriptors,
  fingerprints). Rank segments first, aggregate to tracks by max, top-k mean and coverage.
- **Validation tiers:** canary concepts; duplicate injection; controlled upweighting at 1×/4×/16×;
  leave-cluster-out; top-k versus matched-random removal; subset retraining scored by LDS (linear datamodeling
  score).
- **Hardware tiers:** Tier 1 workstation (RX 9070 XT) for retrieval, probes and small SAEs; Tier 2 mixed; Tier 3
  LUMI for gradient stores, K-FAC across checkpoints, SOURCE, MAGIC, LDS ensembles and the attribution-decay
  experiment.
- **Instrumentation for the next full fine-tune:** exact crop, augmentation, prompt, loss weight, timestep and
  noise seeds; data order and batch membership; optimizer state; 8–16 checkpoints; projected gradient sketches
  (1 024–4 096 dimensions); periodic curvature factors.

## 2. Verdict on the method families (the report's, with this session's adjustments)

- **EK-FAC / influence functions:** local sensitivity estimates, not literal deletion effects. Best retrospective
  formal baseline, but see the unconfirmed ρ≈0.3 figure in §3.
- **TRAK / Journey-TRAK / D-TRAK:** strongest lineage for diffusion attribution, though the published studies
  use much smaller image models.
- **TracIn / SOURCE:** need intermediate checkpoints. We keep dense ladders (A10, A12), which makes them more
  feasible here than the report assumes.
- **MAGIC:** effectively part of the training algorithm; not an afterthought for a finished run.
- **MUCS / GUDA-style group unlearning:** relevant when the unit is a duplicate cluster, artist or concept.
- **Retrieval:** not causal, but the right candidate generator and memorization detector.

## 3. What was verified, inferred and left unchecked

**Verified (page opened or search result seen, October 5–6, 2026):**

| Claim | Status |
|---|---|
| Attribution decay (individual-example removal effects vanish with data scale) | Paper exists: Nature Communications 2026, "Outputs of generative diffusion models are often unattributable". The paper itself would not open (login redirect). Details below are from MIT News coverage: 24 ensemble diffusion models, seven public image collections (CIFAR-10, CelebA, MetFaces, ArtBench among them), 256 to over 160 000 images; removal by switching off the ensemble members that saw an example. Image diffusion only. The coverage says nothing about fine-tuning, small datasets or duplicated data. A caution for our setting, not a verdict. |
| MUCS | arXiv 2605.17938 (Serrà et al.); mirrored unlearning plus noise-consistent skew; CIFAR10, ArtBench10, COCO — matches the report. |
| TIDE | arXiv 2503.07050, in the AAAI 2026 proceedings (image DiT). |
| MusicGen SAE study | ICLR 2026; code at `PapayaResearch/musicdiscovery`. License not checked. |
| Bergson | EleutherAI library (arXiv 2606.11660; MIT license per a search summary). The README states "~17% performance overhead" for the Hugging Face Trainer gradient-collection callback; its experiments are GPT-2/WikiText and it mentions no diffusion support. The 17% is LLM-only, as the report itself warns. |
| Stable Audio 3 README | Medium is 1.4B parameters; Medium needs CUDA and FlashAttention 2; SAME is stereo 44.1 kHz with 256-dimensional latents; LoRA fine-tuning is documented. The README does not state the compression ratio; `docs/ai-research/gemini-report-assessment-2026-07-15.md` gives 256 channels at 10.767 Hz, which matches 44 100 ÷ 4096. |
| Storage arithmetic | Recomputed October 6: 19.85 MB per audio-hour in FP16; 23.8–31.8 GB for 12 000 tracks of 6–8 minutes; 168 000 half-minute segments give 344 MB per 1 024-dimensional sketch per checkpoint and 5.51 GB for 16 checkpoints; 2.8 GB / 5.6 GB for BF16 / FP32 weights. All match the report. |

**Not verified or conflicting:**

- **MAGIC's cost.** The report says roughly 2–3× training. A search summary of Bergson's paper said 3–5 training
  runs; the Bergson README states no figure. The same summary quoted ρ>0.9 against leave-k-out retraining for
  MAGIC in well-behaved settings versus about 0.3 for EK-FAC and TrackStar. **Unconfirmed — read arXiv
  2606.11660 before relying on any of it.** If the 0.3 holds, it argues against spending 15% of effort on
  post-hoc formal influence of a finished run.
- Concept-TRAK; the Kronfluence, dattri and Captum capability claims; Essentia's AGPLv3 and model-license
  claims; the report's 1–10 relevance scores and the 40/30/15/15 split (author judgment, no derivation shown).
- Older methods (TRAK, Journey-TRAK, D-TRAK, DataInf, SOURCE, TrackStar, EK-FAC influence) are known from prior
  knowledge and were not rechecked.

## 4. Where the report and this repo disagree

1. **Full fine-tune and adapters both exist here.** `EXPERIMENTS.md` shows DoRA/LoRA arms (A3, A5, A11, the
   `wfleet` arms) and full fine-tune arms (A4, A13, B9, F2); `docs/lumi-transition-plan.md` covers LATCH heads,
   FiLM adapters and DoRA. The report's full-fine-tune assumptions (optimizer state for 1.4B parameters, DataInf's
   regime "violated") hold for some arms and not others, so plan attribution per family. Adapter arms have a
   small trainable set: cheaper sketches, curvature and dense checkpointing, and DataInf's favorable regime
   applies. Compute shrinks less than storage, since backprop still traverses the frozen network (roughly 4N
   rather than 6N FLOPs per token — an inference, not measured).
2. **The training sets are pre-encoded crops, not tracks.** A12 documents the mix: goa `latents_sa3` 5 400
   crops, `latents_goa_bigset` 12 524 crops (down-weighted to 0.18, mostly mp3 sources), `latents_avp`,
   suomi 1 261, plus `latents_goa_aug8` 3 941 bungee crops; live augmentation is unavailable on the pre-encoded
   path. Consequences: crop identity is static, so the report's "the actual crop drawn" requirement is largely
   met by the dataset manifests; there are no per-step augmentation seeds on this path; per-source sampling
   weights and caption tiers are the analogue of "loss weight". The report's "about 12 000 tracks" may
   correspond to `latents_goa_bigset`'s 12 524 — but those are crops, and which set was meant is unconfirmed. The
   separate 23 232-track archive (19 834 past the encode gate; `docs/goa-archive-buildout-plan.md`) is a
   different object again.
3. **Duplicates are already clustered, and deliberately kept.** Curation clusters by MAEST cosine at 0.97
   (same work) and 0.995 (near-identical) and keeps differently mastered copies as augmentation. Removing one
   track changes little while its twin remains — attribution decay in miniature — so the unit of removal should
   be the cluster. F3 (avp/avpaug duplicate split) is a natural duplicate-control set.
4. **ROCm is already the stack.** The README says Medium needs CUDA and FlashAttention 2, but this project runs
   on ROCm (RX 9070 XT locally, MI250X on LUMI), FlashAttention 2 runs on the LUMI image, and on the RDNA4 venvs
   it is inactive by default with an SDPA fallback that is 30–100% slower (`docs/lessons-learned.md`). A speed
   cost, not a blocker. (This corrects a statement made earlier in the session that nothing in-session spoke to
   the 9070 XT.)
5. **Crop length.** The report sketches 30 s segments; training crops here run from T256 to T4096 (T4096 ≈
   6.3 min; T512 beat-aware in A12). Segment-level gradient sketches would be a retrospective re-slicing of what
   the model saw, not training events.

**Also missing from the report:** the repo's standing reviewer briefing (`EXPERIMENTS.md` header) — the chroma
readout is a linear `Conv1d(256→128, k=1)`; SA3 attention is differential, so attention maps are signed and
thresholding is invalid; 64 learned memory tokens act as global hubs. The report's hook list names
differential-attention outputs, so any SAE, probe or patching design must handle signed maps and the
memory-token hubs.

## 5. Gaps in the report itself

- **No compute budget.** My estimate, untested: 6·N·tokens with N = 1.4B and 323 latent frames per 30 s clip
  (assumes no further patchification), full backward, 30 TFLOP/s effective throughput. That is 456 PFLOP per
  checkpoint and timestep draw over 168 000 segments, about 4.2 GPU-hours; 16 checkpoints × 8 timestep draws is
  about 540 GPU-hours. LUMI-scale for the full fine-tune arms, not 9070 XT-scale.
- **No null baseline for retraining.** Retrain-to-retrain variation sets the smallest detectable effect (H2).
  The attribution-decay study itself shows single-example effects can sit below it.
- **No base-model control** (H4).
- **Notation.** The report writes the flow target as v⋆(z_t, t). The training loss uses a target conditional on
  the clean sample and the noise, not the marginal field; this matters when implementing common-noise gradients.
  SA3's exact parametrization and sign convention were not checked.
- **Cross-device determinism.** Measured on Kim's P14s laptop on October 1, 2026: the same seed gives
  correlation 0.65 between fp32 and fp16 on CUDA and 0.39 on XPU (Intel); XPU fp16 and bf16 produce NaN for
  medium-class models. Any regenerate-and-compare design must pin one device and precision. The relevant
  cross-device pair here is RDNA4 against MI250X, which is unmeasured. (The measurement files are local to that
  laptop and not in the repo.)

## 6. What to do — options

| Option | Benefit | Cost | Risk | Reversible |
|---|---|---|---|---|
| A. Log training events in the next run (H1) | Preserves evidence that cannot be recovered later | Small code change | Low | Yes |
| B. Retrieval and cluster index from existing curation outputs (H3), with H2 and H4 | Answers "what resembles this output" now | CPU-scale, plus latent caching | Low | Yes |
| C. EK-FAC or TRAK on a finished run (H7) | The formal-influence layer | Hundreds of GPU-hours (my estimate) | Weakly validated | Yes, but expensive |

**Recommendation: A, then B.** A is the only option whose value is lost by waiting. The assumption that would
change this: if logs for existing runs already exist, B goes first; if the next training run is not planned for
weeks, B goes first.

## 7. Open questions

- Which run or family is to be attributed — an adapter family or a full fine-tune — and which corpus did it see
  (`latents_sa3` 5 400, `latents_goa_bigset` 12 524, the 23 232-track archive)?
- Do the existing training scripts already log batch membership and timestep/noise seeds? Not inspected in this
  pass; check before building H1.
- Did the 8-replica ladders survive the LUMI scratch purge (A10 noted they needed slimming before the pull), and
  do the replicas differ in data order or only in seed? Unconfirmed.
- Rights and licensing (corpus rights, the Stability AI Community License, Essentia's terms) are Legal
  questions and are not answered here. An attribution output is a ranking of evidence, not a finding of use.

## Sources

- [Outputs of generative diffusion models are often unattributable (Nature Communications)](https://www.nature.com/articles/s41467-026-75667-5)
- [MIT News coverage, August 18, 2026](https://news.mit.edu/2026/when-ai-art-has-no-author-generated-images-often-cant-be-traced-to-training-data-0818)
- [MUCS, arXiv 2605.17938](https://arxiv.org/abs/2605.17938)
- [TIDE, arXiv 2503.07050](https://arxiv.org/abs/2503.07050)
- [PapayaResearch/musicdiscovery](https://github.com/PapayaResearch/musicdiscovery)
- [EleutherAI/bergson](https://github.com/EleutherAI/bergson)
- [Bergson paper, arXiv 2606.11660](https://arxiv.org/abs/2606.11660)
- [Stability-AI/stable-audio-3](https://github.com/Stability-AI/stable-audio-3)
