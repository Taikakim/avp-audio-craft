# Prospective Papers Review & Synthesis: The Geometric Optimization & Audio DiT Frontier

**Date:** September 20, 2026 (Updated from September 19, 2026 baseline)  
**Source Directory:** `/home/kim/Projects/SAO/papers/Prospective Unchecked/` (41 documents total: 35 arXiv/journal PDFs, 3 musicology/theory PDFs, 3 external markdown assessment notes).  
**Target Context:** SAO Project (Stable Audio 3 DiT Backbone, LoRA / DoRA Fine-Tuning, Continuous Flow Matching, and the Modular Norm-Constrained Optimizer Framework `modular_opt`).

---

## 1. Executive Taxonomy & Relevance Map

The prospective literature collection encompasses 41 documents structured across three major domains:
1. **Core Optimizer Theory & Architecture (28 papers — 23 HIGH / 4 MEDIUM relevance):** Mathematical and algorithmic foundations for the modular, preconditioned, norm-constrained optimizer framework (`modular_opt`), covering spectral LMOs, preconditioner stacks, DiT-specific scaling, angular velocity decoupling, and low-rank adapter descent.
2. **Audio/Music DiT & Flow Matching (4 papers — 4 HIGH/MEDIUM relevance):** Continuous flow matching architectures, continuous audio VAE latents, duration conditioning, and whole-trajectory RL alignment.
3. **Discrete Musicology, Combinatorics & Applied PDEs (9 documents — LOW / NONE):** Symbolic pitch-class combinatorics, avant-garde tape musicology, and mathematical PDE diagnostics.

| Category | File / Identifier | Title / Topic | SAO Relevance | Core Architectural Impact |
|---|---|---|:---:|---|
| **Opt: Foundations** | `2409.20325v2` | *Old Optimizer, New Norm: An Anthology* (Bernstein & Newhouse) | **HIGH** | Theoretical bedrock of modular norms; operator norm assignment per layer role; cubic NS polar factor. |
| **Opt: Foundations** | `2502.07529v2` | *Training Deep Learning Models with Norm-Constrained LMOs* (SCION) | **HIGH** | Direct blueprint for `modular_opt`: uSCG/SCG, radius scaling $\rho = \max(1, \sqrt{d_{out}/d_{in}})$, $\mu$P zero-shot transfer. |
| **Opt: Foundations** | `2601.08393v3` | *Controlled LLM Training on Spectral Sphere* (SSO / MuonSphere) | **HIGH** | Manifold norm bounds on both weights and updates; atomic QKV head-splitting; eliminates activation spikes. |
| **Opt: Foundations** | `2601.21487v2` | *Manifold Constrained Steepest Descent...* (MCSD / SPEL) | **HIGH** | Ambient LMOs on Stiefel manifold ($X^T X = I$); metric projections; non-smooth safe regions. |
| **Opt: DiT Scaling** | `2608.20818v3` | *Scaling Muon for Diffusion Transformers* (Li & Han et al.) | **HIGH** | **Directly targets DiTs:** Periodic Row-wise Muon (NS5 refresh every $K$ steps + intermediate per-neuron RowNorm); cuts compute 50%, bounds row velocity, prevents high-frequency acoustic distortion. |
| **Opt: Spectral Geometry** | `2608.25990v1` | *Spectral Allocation: Why Muon Outperforms Adam...* (SAMuon) | **HIGH** | **Explains Muon overshooting vs underfitting:** Uniform singular values overdrive the volatile head (Edge of Stability / harsh timbres) while starving the bulk; SAMuon-lite clamps top singular component via rank-1 power iteration. |
| **Opt: Angular Decoupling** | `2608.21024v1` | *RODE: Radial-Orthogonal Decoupled Engine* | **HIGH** | Decouples Frobenius norm growth from angular descent; Newton-Schulz on tangent space of sphere; eliminates runaway angular velocity $\Delta \theta$. |
| **Opt: Angular Decoupling** | `2608.28442v1` | *Curvature-Conditioned Multiscale Momentum with Sphere Constraints* | **HIGH** | Dual-timescale momentum (slow noise-filtering + fast curvature-adaptive) paired with spherical constraints to prevent weight inflation and velocity decay. |
| **Opt: Adapter / LoRA** | `2609.02734v1` | *LoRA-TSD: Tangent-Space Spectral Descent for LoRA* | **HIGH** | Spectral descent on the tangent space of the rank-$r$ matrix manifold with native retraction to factors $A$ and $B$; exact bounded spectral norm on $\Delta(BA)$. |
| **Opt: Adapter / LoRA** | `2608.14492v1` | *Approximate Muon with Low-Rank Adapters* (sMuon) | **HIGH** | Linearized least-squares approximation to Muon objective for low-rank factors using standard matmuls only. |
| **Opt: Adapter / LoRA** | `2609.05885v1` | *One Rate Is Not Enough: Adaptive Anisotropic LRs for LoRA* (AnLR-LoRA) | **HIGH** | Online tracking of function-space velocity and gradient SNR per rank-1 slice; mean-normalized module-level scaling prevents dominant slice overshooting. |
| **Opt: Regularization** | `2609.04577v1` | *Optimizer Memory Schedules for Outscaling the Overtraining Axis* (Everett & Qiu) | **HIGH** | Discovers optimal weight decay scales with $\sqrt{\text{OT}}$ ($E = T/\text{steps\_per\_epoch}$); momentum cooldown schedule eliminates terminal jitter and mode collapse in extended fine-tuning. |
| **Opt: Preconditioning** | `2603.09697v2` | *Mousse: Rectifying Geometry of Muon with Curvature Preconditioning* | **HIGH** | Exact analytical validation of our Transform-Solve-Invert pipeline: $L^{-1/4} \text{msign}(L^{-1/4} G R^{-1/4}) R^{-1/4}$. |
| **Opt: Preconditioning** | `2604.01472v1` | *The Newton–Muon Optimizer* | **HIGH** | Quadratic surrogate model; right-side preconditioning by activation Gramian $(ZZ^T)^{-1}$ to suppress input feature explosions. |
| **Opt: Preconditioning** | `2509.03378v10` | *Understanding and Improving Shampoo and SOAP via KL Minimization* | **HIGH** | Eliminates Adam grafting; two-sided KL covariance updates; proves short-sided KL-Shampoo recovers Muon as $\beta \to 0$. |
| **Opt: Preconditioning** | `2607.20548v1` | *SOAP, Muon, and Beyond: Pushing LLM Pretraining Scales* (NVIDIA) | **HIGH** | Update-RMS matching across AdamW/Muon/SOAP; KL-SOAP stability; warning on LoRA vs full-rank preconditioning. |
| **Opt: Preconditioning** | `2602.02016v2` | *DASH: Faster Shampoo via Batched Block Preconditioning...* | **HIGH** | 3D tensor stacking for GPU batched GEMMs; multi-Power-Iteration Newton-Denman-Beavers inverse roots. |
| **Opt: Hybrid / LMO** | `2605.19811v3` | *LionMuon: Alternating Spectral and Sign Descent* | **HIGH** | Alternates Muon ($P=1$) and Lion ($P=2$) with shared dual-EMA; acts as natural velocity damper, cuts NS5 FLOPs by 50%. |
| **Opt: Hybrid / LMO** | `2605.31371v1` | *Softsign: Smooth Sign in Your Optimizer...* (SoftMuon) | **HIGH** | Algebraic soft-sign $\frac{s_i}{\|s_i\| + \tau}$ via Newton-Schulz; cures Muon terminal-phase oscillation, buzzing, and transient clicks near convergence. |
| **Opt: Hybrid / LMO** | `2605.16311v1` | *SignMuon: Communication-Efficient Distributed Muon* | **HIGH** | 1-bit majority vote Muon; formal nuclear/spectral duality proof for polar factor. |
| **Opt: Mechanics** | `2609.07017v1` | *HyperTransfer: Understanding Equivalence...* | **HIGH** | Dynamic equivalence between Hyperball and unconstrained optimizers; effective angular learning rate schedule $\eta^{eff}_t$. |
| **Opt: Mechanics** | `2608.26288v1` | *Muon with Finite Newton–Schulz: The Smoothing Benefit...* | **MEDIUM** | Truncated NS5 is an implicit regularizing smoother on small singular values, preventing step discontinuities that cause audio clicks. |
| **Opt: Mechanics** | `2608.27518v1` | *When Muon Meets Task Interference: Spectral Continual Learning* | **MEDIUM** | Formal bound showing spectral norm bound $\|\Delta W\|_2 \le \eta$ minimizes representation forgetting during continual fine-tuning. |
| **Opt: Mechanics** | `2608.22129v2` | *Blockwise Stabilized Adaptive Cubic Regularization* | **MEDIUM** | Per-block adaptive cubic penalty $M_b$ as a local curvature guard against ill-conditioned tensor overshooting. |
| **Opt: Mechanics** | `2510.14717v2` | *Seesaw: Accelerating Training by Balancing LR and Batch Size* | **MEDIUM** | Dynamic batch ramping ($1/\sqrt{\alpha}$ LR, $\alpha$ batch size) saves 36% steps at constant compute. |
| **Opt: Mechanics** | `2603.09923v4` | *OptEMA: Adaptive Exponential Moving Average...* | **MEDIUM** | Closed-loop adaptive moment scheduling ($\beta_1, \beta_2$) without manual retuning. |
| **Opt: Damping** | `2607.16268v1` | *PsiLogic: Chaos-Aware Active Cancellation for Adam* | **MEDIUM** | Dual-EMA gradient turbulence detector injecting an automated damping cancellation vector during high-chaos phases. |
| **Opt: Mechanics** | `2608.15665v1` | *SubZero+: Efficient Zeroth-Order LLM Fine-Tuning* | **NONE** | Black-box zeroth-order optimization; inapplicable to first-order backpropagation. |
| **Opt: Foundations** | `2609.00870v1` | *Stochastic Optimization of Tree Tensor Networks* | **LOW** | Quotient Riemannian geometry specific to tree tensor networks; inapplicable to standard DiTs. |
| **Audio / DiT** | `2603.12893v2` | *Finite Difference Flow Optimization (FDFO) for RL Post-Training* | **HIGH** | Whole-trajectory finite difference flow matching optimization; replaces noisy multi-step Flow-GRPO. |
| **Audio / DiT** | `2510.18416v2` | *SegTune: Structured and Fine-Grained Control for Song Generation* | **HIGH** | 1.1B DiT + Conditional Flow Matching; segment-level prompt conditioning; LoRA duration predictor. |
| **Audio / DiT** | `2510.22950v3` | *DiffRhythm 2: Block Flow Matching for Song Generation* | **HIGH** | 5 Hz music VAE (derived from SA2); semi-AR block flow matching; stochastic block REPA loss; CPPO. |
| **Audio / DiT** | `2506.08210v1` | *Comprehensive Study of Decoder-Only LLMs for Text-to-Image* | **MEDIUM** | Layer-normalized averaging of LLM representations vs last-layer conditioning; prompt cross-attention. |
| **Music / Math** | `17459737` | *Discovering Distorted Repeating Patterns in Polyphonic Music* | **LOW** | $O(n^2 \log n)$ 2D Longest Increasing Subsequence on symbolic pitch/onset pairs. |
| **Musicology** | `Choi` | *Composing Degree Zero: Luciano Berio's Thema (Omaggio a Joyce)* | **NONE** | Historical analysis of tape splicing, musical phonology, and semantic matrices. |
| **Music Theory** | `Gainey` | *Three Approaches to Modularity in Contemporary Music* | **NONE** | Pitch-class sets, metric modulation, and physical string gestures in Carter, Adès, Saariaho. |
| **Combinatorics** | `Quarles` | *All-Trichordal Saturated M-Chain Cycles* | **NONE** | Hamiltonian cycle generation over trichords under $Z_{12}$ multiplication. |
| **External Note** | `2607.14796` | *Carbone & Servidio: 2D Turbulence Sparse Triadic Interactions* | **LOW–MED** | Network sparsification; informs melody intermittency metrics across diffusion steps (D10). |
| **External Note** | `2608.04970` | *Liu & Purohit: Time-Dependent Coefficients on CTA Manifolds* | **LOW** | Diagnostic prompt for control fields: conservativeness $\nabla \times F = 0$, commutation (D9), rotation (D8). |
| **External Note** | `2608.05696` | *Garain: Mixed Local/Nonlocal Quasilinear Elliptic Problem* | **LOW** | Dirichlet smoothness prior on chroma readouts (D7); anti-loop recurrence matching. |

---

## 2. Core Breakthroughs for the SAO Modular Optimizer

### A. Mathematical Validation of the Transform-Solve-Invert Pipeline
In `stable_audio_tools/training/modular_opt/`, we designed the 6-stage canonical execution pipeline:
$$\text{Grad } G \longrightarrow \text{Precondition } P_L G P_R \longrightarrow \text{LMO } M = \text{msign}(\tilde{G}) \longrightarrow \text{Pullback } U = P_L M P_R \longrightarrow \text{Update}$$

Two foundational papers provide closed-form proofs:
1. **Mousse (`2603.09697v2`):** Proves that steepest descent under the Mahalanobis matrix norm induced by Shampoo's Kronecker covariances $\|P \Delta W Q\|_{\text{op}} \le 1$ (with $P = L^{1/4}, Q = R^{1/4}$) has the **exact closed-form solution**:
   $$\Delta W^* = - L^{-1/4} \text{msign}\left(L^{-1/4} G R^{-1/4}\right) R^{-1/4}$$
   This confirms that our `KLShampooPreconditioner` forward whitening combined with the LIFO stack's reverse pullback is the **exact analytical Riemannian pullback** for preconditioned spectral steepest descent.
2. **KL-Shampoo & KL-SOAP (`2509.03378v10`):** Proves that estimating covariances under KL divergence minimization on the SPD cone avoids the loss spikes of Frobenius-norm Shampoo and eliminates the need for Adam step grafting. Furthermore, Wu Lin et al. prove that:
   $$\lim_{\beta \to 0} (G G^T)^{-1/4} G (G^T G)^{-1/4} \equiv U V^T = \text{msign}(G)$$
   Muon is the instantaneous limit of Shampoo.

### B. Role-Based Parameter Routing (SCION & Old Optimizer New Norm)
Both **SCION (`2502.07529v2`)** and **Bernstein & Newhouse (`2409.20325v2`)** establish the theoretical framework implemented in `routing.py`:
- **Linear / Attention / MLP matrices ($\mathbb{R}^{d_{out} \times d_{in}}$):** Map RMS to RMS $\implies$ Spectral Norm ($\ell_2 \to \ell_2$). Polar factor $U V^T$ via Newton-Schulz quintic iteration, scaled by geometric radius:
  $$\rho_\ell = \max\left(1, \sqrt{\frac{d_{out}}{d_{in}}}\right)$$
  SCION proves this width-scaling guarantees **Maximal Update Parametrization ($\mu$P)**: layer preactivation variances remain invariant across model widths, enabling zero-shot hyperparameter transfer.
- **Input Embeddings ($\mathbb{R}^{V \times d}$):** Map one-hot inputs ($\ell_1$) to latent vectors ($\ell_2$) $\implies$ **ColNorm** ($(2, \infty)$ operator norm). Normalizes columns independently at $O(V d)$ cost instead of $O(V d^2)$ SVD cost.
- **Output Projections / Modulation Emitters / Biases:** Map to unconstrained logits or scale shifts $\implies$ **Sign** ($\ell_\infty$ norm with $\ell_1$ dual).

### C. Curing Muon’s Terminal Oscillation: SoftMuon (`2605.31371v1`)
A primary root cause of audio artifacts (buzzing, hiss, and click transients near convergence): hard LMOs force singular values to 1 ($\sigma_i(\Delta W) = 1$). Near narrow local minima, the optimizer cannot take small steps, causing persistent limit-cycle bouncing across the valley floor.
- **SoftMuon** introduces an algebraic soft-sign regularizer:
  $$\Delta W = - \delta M \left(M^T M + \tau^{-2} I\right)^{-1/2}, \quad \text{or equivalently on singular values } \sigma_i \leftarrow \frac{\sigma_i}{\|\sigma_i\| + \tau}$$
  Computed efficiently via Newton-Schulz iterations without explicit SVD.
- Controlled by an online quantile temperature schedule $\tau_t$, the update smoothly transitions from rigid spectral descent early in training to magnitude-sensitive, smooth SGD-like steps near convergence, completely eliminating terminal-phase chatter.

### D. Weight Manifold Retraction & Atomic Splitting (SSO `2601.08393v3`)
1. **Atomic Granularity:** Fused projections (like QKV in attention, or gate/up in MLPs) exhibit distinct subspace dynamics. Orthogonalizing the entire concatenated matrix causes cross-talk between attention heads. Splitting QKV into 3 blocks and Adaln into $k$ blocks (implemented in `routing.py` via `split_qkv` and `split_adaln`) significantly outperforms monolithic matrix updates.
2. **Spectral Sphere Retraction:** Enforcing a bound on the weight norm itself ($\|W\|_2 = R = c\sqrt{d_{out}/d_{in}}$) via tangent projection eliminates loss spikes and replaces weight decay.

### E. Scaling Muon for Diffusion Transformers & Periodic RowNorm (`2608.20818v3`)
Directly addresses DiT architectures (the exact backbone of Stable Audio 3):
- Running full 5-step Newton-Schulz (NS5) every single step across all DiT projection layers is computationally heavy and can introduce high-frequency step chatter in generative diffusion models.
- Li & Han et al. introduce **Periodic Row-wise Muon**:
  1. Full NS5 spectral orthogonalization is executed only once every $K$ steps (the refresh step).
  2. On the intermediate $K-1$ steps, the optimizer applies **RowNorm** (per-neuron row normalization on momentum, identical to NorMuon).
- This cuts optimizer wall-clock time by ~50%, stabilizes latent flow trajectories, and strictly bounds per-neuron update velocity, avoiding high-frequency timbre distortion in generated audio.

### F. Spectral Allocation: Volatile Head vs. Tolerant Bulk (SAMuon `2608.25990v1`)
Identifies the theoretical mechanism behind the optimizer dilemma (why standard Muon runs either too hot or too cold):
- Deep neural loss landscapes exhibit an anisotropic spectral profile: a "volatile head" operating at the Edge of Stability (EoS) that easily destabilizes under large steps, and a "tolerant bulk" that requires substantial step sizes to learn effectively.
- Standard Muon projects all singular values uniformly to 1. This over-drives the volatile head (causing loss spikes, instability, and harsh timbre glitches) while simultaneously under-stepping the bulk (causing sluggish, inaudible learning on subtle acoustic features).
- **SAMuon-lite:** Uses a single rank-1 power iteration to isolate the top singular component $\sigma_1$, clamps this volatile head update to prevent EoS blowup, and scales up the bulk update according to a static spectral prior. Near-zero FLOP overhead with major stability gains.

### G. Decoupling Radial Scale from Angular Velocity: RODE & Spherical Constraints (`2608.21024v1`, `2608.28442v1`)
In standard optimizers, updating $W_{t+1} = W_t - \eta U_t$ simultaneously alters both the Frobenius norm $\|W\|_F$ and the direction $W / \|W\|_F$. As weight norms fluctuate during fine-tuning, the effective angular velocity $\Delta \theta \approx \|\Delta W\|_F / \|W\|_F$ drifts unpredictably.
- **RODE (`2608.21024v1`):** Decouples updates into independent radial and directional channels. Frobenius norm is governed by an explicit scalar rule, while Newton-Schulz updates are restricted to the tangent space of the sphere ($T_W \mathcal{M}$). Momentum is reprojected after each step to guarantee strict orthogonality to $W$, preventing runaway angular velocities that produce harsh acoustic timbres.
- **Multiscale Spherical Momentum (`2608.28442v1`):** Combines dual-timescale momentum (slow-decay noise filter + fast-decay curvature tracker) with hypersphere weight constraints, preventing weight inflation and preserving a steady, calibrated travel velocity throughout the run.

### H. Native Low-Rank Spectral Descent: LoRA-TSD, sMuon, & AnLR-LoRA (`2609.02734v1`, `2608.14492v1`, `2609.05885v1`)
Standard optimizers optimize LoRA factors $A \in \mathbb{R}^{r \times d_{in}}$ and $B \in \mathbb{R}^{d_{out} \times r}$ independently. This produces erratic composite updates $\Delta W = \Delta(B A) = (\Delta B) A + B (\Delta A) + \Delta B \Delta A$, causing rank collapse and unconstrained spectral growth.
- **LoRA-TSD (`2609.02734v1`):** Formulates spectral descent on the tangent space of the fixed-rank matrix manifold $\mathcal{M}_r$. Performs spectral normalization directly on the composite tangent vector and retracts natively back to factors $A$ and $B$, guaranteeing bounded spectral norm $\|\Delta W\|_2 \le \eta$ without full base model SVD.
- **sMuon (`2608.14492v1`):** Solves a relaxed Muon objective in the low-rank subspace using linearization and least-squares, implemented purely via standard matrix multiplications.
- **AnLR-LoRA (`2609.05885v1`):** Tracks online function-space velocity and gradient SNR per rank-1 adapter component, applying dynamic per-slice learning rate multipliers that are mean-normalized per module. This prevents dominant adapter slices from overshooting while keeping low-velocity slices moving.

### I. Overtraining-Aware Regularization & Velocity Cooldown (`2609.04577v1`)
- **Everett & Qiu (2026):** Proves empirically across extensive LLM and vision runs that optimal weight decay scales with the square root of the overtraining factor:
  $$\lambda_{\text{WD}}(E) = \lambda_{\text{base}} \sqrt{\max(1.0, E)}, \quad \text{where } E = \frac{\text{current\_step}}{\text{steps\_per\_epoch}}$$
  *(Now integrated into `modular_opt` via `--wd-overtraining`)*.
- **Momentum Cooldown:** In extended fine-tuning runs, smoothly cooling down momentum coefficients ($\beta_1 \to 0$) in the final 10–20% of training eliminates late-stage trajectory jitter, preventing mode collapse and ensuring pristine acoustic fidelity at checkpoint milestones.

### J. Truncated Newton-Schulz Smoothing & Representation Drift (`2608.26288v1`, `2608.27518v1`)
- **Finite NS Smoothing (`2608.26288v1`):** Demonstrates that 5-step Newton-Schulz (NS5) acts as an implicit regularizing smoother on the discontinuous polar map. Truncated quintic polynomials soften updates on small singular values rather than forcing them to $\pm 1$, suppressing high-frequency parameter chatter.
- **Task Interference Bound (`2608.27518v1`):** Proves that enforcing a strict spectral norm bound $\|\Delta W\|_2 \le \eta$ minimizes representation drift. For audio fine-tuning, this ensures the foundational audio decoder and latent space representations remain intact while acquiring new stylistic control.

---

## 3. Core Breakthroughs for SAO Flow Matching & DiT Training

### A. Finite Difference Flow Optimization (FDFO `2603.12893v2`)
Stable Audio 3 is an ODE-based rectified flow / flow matching model. Standard reinforcement learning post-training (RLHF/RLAIF) uses Flow-GRPO or DDPO, which treat every continuous denoising step as a Markov Decision Process action. Because noise is 100,000-dimensional, per-step policy gradient updates suffer from extreme variance, causing policy collapse and grid-like visual/audio artifacts.
- **FDFO's Solution:** Treat the entire reverse trajectory as a single action. Generate paired trajectories $(x, \hat{x})$ from the same initial seed with calibrated stochastic perturbations.
- Pull velocity predictions along the entire trajectory towards the endpoint reward gradient:
  $$\Delta x = \frac{\hat{x}_T - x_T}{\|\hat{x}_T - x_T\|_{\text{RMS}}^2 + 10^{-6}}, \quad \Delta R = R(\hat{x}_T) - R(x_T)$$
- FDFO converges **5–19× faster** than Flow-GRPO, completely eliminates reward-hacking artifacts, and enables on-policy preference alignment using non-differentiable audio rewards (e.g. Audiobox Aesthetics, rhythm/beat consistency, or CLAP alignment).

### B. SegTune (`2510.18416v2`) & DiffRhythm 2 (`2510.22950v3`)
Both papers demonstrate production-grade music generation using continuous flow matching DiTs:
- **SegTune:** Employs a 1.1B DiT with Conditional Flow Matching on 1D continuous audio latents. Uses a LoRA-fine-tuned duration predictor (rank 32) to generate timestamped lyric conditioning, combined with segment-level prompt broadcasting across time frames.
- **DiffRhythm 2:** Solves full-length song generation (up to 210s) by partitioning audio latents into fixed blocks and running **semi-autoregressive block flow matching** with block-causal attention and KV caching ($\text{RTF} = 0.213$). It trains on latents from a **5 Hz music VAE derived directly from the Stable Audio 2 VAE architecture**.

---

## 4. Synthesis: Roadmap for the SAO Optimization & DiT Pipeline

```
[Phase 1: Optimizer Velocity Calibration & Stabilization — ACTIVE NOW]
  ├── NorMuon per-neuron row normalization in Stage 3b (amplifies wide layers safely 3-5x)
  ├── Enable Schedule-Free (SF) averaging by default (steady fast-iterate z_t velocity)
  ├── Everett & Qiu overtraining-aware weight decay scaling: wd_t = wd_0 * sqrt(epoch)
  └── Target effective velocity: ~30-50 units/1k steps (AdamW/Lion good-audio band)

[Phase 2: Terminal Quality & DiT Stability Upgrades — IMMEDIATE NEXT]
  ├── SoftMuon algebraic relaxation in lmo.py (soft-sign on singular values; cures terminal oscillation)
  ├── Periodic Row-wise Muon (arXiv:2608.20818): NS5 refresh every K steps + RowNorm on intermediates
  ├── SAMuon-lite volatile head clamping via rank-1 power iteration (stops Edge-of-Stability harshness)
  └── Tangent-space LoRA descent (LoRA-TSD / sMuon) for clean composite adapter updates

[Phase 3: Preconditioner & Curvature Accelerations — SHORT TERM]
  ├── Integrate DASH batched 3D GEMM blocks for multi-layer preconditioner speedup
  ├── Benchmark Shampoo vs SOAP vs Identity whitening under calibrated velocity
  └── Evaluate RODE radial-angular decoupling to fix effective spherical travel distance

[Phase 4: Flow Matching Preference Alignment — FUTURE]
  ├── Implement FDFO (Finite Difference Flow Optimization) for trajectory-level preference tuning
  ├── Replace noisy multi-step RL with trajectory-level finite difference updates
  └── Use Audiobox Aesthetics + CLAP alignment as non-differentiable reward oracles
```
