# AxBench — Steering LLMs: Even Simple Baselines Outperform Sparse Autoencoders (2501.17148)

*Project-POV abstract, THE-FINN 2026-07-30 (deep-read pp.1-9). Stanford NLP (Wu, Arora, Geiger,
Manning, Potts). The benchmark behind "simple difference-of-means beats SAEs for steering" — a
result our own 2026-07-12 mood-steering work already acted on.*

**What it contains.** A large-scale benchmark (Concept500, synthetic LLM-generated data on
Gemma-2-2B/9B) comparing model-control methods on **two axes: concept DETECTION and model
STEERING** — prompting, finetuning (SFT / LoRA / LoReFT), and representation-based methods
(SAEs from GemmaScope, **difference-in-means / DiffMean**, PCA, LAT, linear probe, supervised
steering vector, and their new **ReFT-r1** = rank-1 representation finetuning). Headline results:
- **Steering:** prompting outperforms *every* method; finetuning next; **SAEs are not competitive**
  (far behind). Only ReFT-r1 approaches prompting; DiffMean is the best of the non-trained vectors.
- **Detection:** DiffMean / probe / ReFT-r1 are best; SAEs poor.
- **DiffMean** = `mean(positive activations) − mean(negative activations)`, unit-normed; steer by
  activation addition `h + α·w`. The α (steering factor) is a tuned hyperparameter.
- **Larger steering factor monotonically harms** instruct/fluency (capability cost) across all
  methods; ReFT-r1 traces a Pareto-optimal concept-vs-instruct path.
- Sobering conclusion: representation steering is *far behind* prompting/finetuning; SAEs at SAE
  scale underperform simple supervised baselines on both axes. Detection ≠ steering (a concept
  can be detectable yet not steerable).

**Status vs our work — this is a paper we FOLLOWED, and validated empirically.** The 2026-07-12
mood-steering pass **took AxBench's hint**: skipped SAE training entirely and used the
difference-of-means direction, which delivered ~19× "dark" steering on a closed-loop meter with
no training. Three of its findings replicated on SA3 audio: (a) **detection ≠ steering** — our
"relaxing" mood had the *best* separability yet refused to steer; (b) **big vectors harm** — our
"turn the knob too far → buzz," now formalized as the disintegration gate; (c) **SAEs
underperform** — bounds the SAE-steering lane we index (DC-SAE 2605.31295-adjacent, SAE-music
2505.18186, RT-SAEs) as the *cheaper-first-experiment-but-not-the-frontier* option. **ReFT-r1**
(rank-1 joint detect+steer finetune, Pareto-optimal) is the one method here worth a look against
our readout heads — a trained rank-1 intervention rather than a fixed vector. **What remains
ours:** the SA3 audio-domain application; the disintegration gate that makes over-steer *legible*
(AxBench notes the capability cost but has no buzz screen); and Head-B forward-**conditioning**
(train the model to USE a handed stream) — a distinct lane from all of AxBench's inference-time
readout-steering methods, and our answer to exactly the "steering is far behind" ceiling they hit.
