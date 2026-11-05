# Layer by Layer: Uncovering Hidden Representations in Language Models

- **arXiv:** 2502.02013v2 (2025-06-15, cs.LG)
- **Conference:** ICML 2025 (Proceedings of the 42nd International Conference on Machine Learning, Vancouver, Canada. PMLR 267, 2025)
- **Authors:** Oscar Skean, Md Rifat Arefin, Dan Zhao, Niket Patel, Jalal Naghiyev, Yann LeCun, Ravid Shwartz-Ziv (Univ. Kentucky, Mila/U. Montreal, NYU, UCLA, Meta FAIR, Wand.AI)
- **PDF:** `papers/arxiv-2502.02013.pdf`
- **Code:** `C:\dev\private\information_flow` (laptop copy; unversioned / no LICENSE file)
- **Read by:** KUANG, 2026-10-16 (for the ModularOptimizer representation review); full text + appendices verified from PDF by ANTIGRAVITY, 2026-11-05.

## What it contains

- **Central finding: intermediate layers consistently outperform final layers** on downstream tasks across architectures, scales, and modalities. Evaluated across 32 tasks in the Massive Text Embedding Benchmark (MTEB: classification, clustering, reranking). Peak performance consistently resides at ~50–80% network depth, delivering +2% to +16% average absolute improvement over final-layer embeddings.
- **Unified evaluation framework based on matrix-based Rényi entropy:** Uses matrix entropy of the normalized Gram matrix $K = \frac{ZZ^\top}{\text{tr}(ZZ^\top)}$ for representations $Z \in \mathbb{R}^{N \times D}$:
  $$S_\alpha(Z) = \frac{1}{1 - \alpha} \log_2 \sum_{i=1}^r \left(\frac{\lambda_i(K)}{\text{tr}(K)}\right)^\alpha$$
  (with $\alpha \to 1$ yielding von Neumann / Shannon spectral entropy). Unifies three families of metrics:
  1. **Information-theoretic:** Prompt entropy (token diversity within sequence), Dataset entropy (diversity of mean prompt embeddings across corpus), and Effective Rank (bounded below $\exp(S_1(Z))$, Theorem 1).
  2. **Geometric:** Curvature (average angular deviation $\arccos \frac{v_k \cdot v_{k+1}}{\|v_k\|\|v_{k+1}\|}$ between consecutive token differences $v_k = z_{k+1} - z_k$; captures trajectory smoothness).
  3. **Augmentation invariance:** InfoNCE loss, LiDAR (linear discriminant within vs. between prompt cluster scatter), and DiME (matrix-entropy alignment of paired augmentations).
- **Architectural divide — autoregression drives the mid-layer compression valley:**
  - **Decoder-only autoregressive models (Pythia, Llama):** Exhibit a pronounced mid-network entropy dip ("compression valley") where redundant local context is aggressively filtered and abstract features are distilled.
  - **Encoder-only bidirectional models (BERT):** Maintain flat, high entropy across all layers because bidirectional attention sees all tokens simultaneously without having to compress.
  - **State-space models (Mamba):** Display flat, intermediate entropy curves without aggressive mid-depth bottlenecks.
  - **Autoregressive vision models (AIM):** Next-patch image prediction reproduces the exact same mid-layer entropy valley and downstream probe peak as LLMs, proving the valley is driven by the autoregressive predictive objective rather than data modality (whereas masked/self-supervised vision models like MAE, BEiT, DINOv2 show monotonically increasing accuracy toward final layers).
- **Sub-component dissection:** Residual connections drive the mid-network entropy drop; pre-residual sub-layers (pre-attention, raw MLP output) maintain higher entropy. Residual paths act as a regularizing filter.
- **Training dynamics & "detokenization":** Early layers stabilize very early in training (performing task-agnostic detokenization / embedding projection), while intermediate layers undergo the vast majority of representation changes throughout training (entropy valley deepens, curvature drops).
- **Chain-of-Thought (CoT) fine-tuning:** Models fine-tuned with CoT reasoning (e.g. Qwen 2.5-Math) maintain significantly higher prompt entropy across sequence lengths than standard models, preserving multi-step context without premature collapse.
- **Unsupervised layer selection:** Unsupervised metrics (especially DiME, LiDAR, and curvature) distance-correlate strongly with downstream performance, allowing optimal intermediate layers to be selected without task labels (+3% MTEB gain on Pythia-410M).

## What it does not contain / what remains ours

- **Language and vision classification/probing only:** Nothing on generative flow matching, diffusion transformers (DiTs), continuous-time diffusion trajectories ($\sigma \in [0, 1]$), AdaLN / FiLM conditioning, or audio.
- **No treatment of massive activation outliers:** Does not isolate extreme spike channels. Later work by Sun, Canziani, LeCun, Zhu (arXiv:2603.05498, *The Spike, the Sparse and the Sink*) showed that these mid-layer compression valleys coincide with massive activation spikes in pre-norm architectures, which skew uncentered Gram matrices if unhandled.
- **No steering / control intervention:** Demonstrates that intermediate representations are richer, but does not construct runtime steering vectors, directional adapters, or continuous generative controls from them.

## For us

- **Core theoretical foundation for DiT representation probing:** Direct motivation for probing intermediate DiT blocks (e.g., SA3 blocks L8–L15) rather than relying on final layers or late velocity outputs.
- **Adopted in ModularOptimizer Test Plan (§E):** Kuang directly used Skean et al.'s metric suite (matrix entropy, TwoNN intrinsic dimension, curvature across frames, dataset vs. prompt entropy) to define the 24 DiT block representation audit at $\sigma \in \{0.9, 0.5, 0.1\}$.
- **Spike-channel hygiene requirement:** Because uncentered Gram matrices $ZZ^\top$ are easily dominated by the massive activation spikes identified in Sun et al. 2026, any entropy or effective-rank measurement on SA3 DiT activations must project out or normalize top spike channels first.
- **Unsupervised checkpoint / adapter audit:** Effective rank and DiME provide a label-free diagnostic to verify whether fine-tuning (DoRA, FiLM, full-FT) causes representational collapse in intermediate blocks.
