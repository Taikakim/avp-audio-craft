<!-- Provenance: THE-FINN, 2026-07-31. Ultracode research run (14 subagents: 8 parallel theory-domain surveys → cross-theme synthesis → adversarial pressure-test of each model sketch → assembled brief). Commissioned by Kim ("weights organized like reality itself"). Audience: CONTINUITY (theory), as brainstorm fuel. Citations are agent-gathered — spot-verify post-2024 arXiv ids before building (house verify-before-build rule). Contains no corpus/checkpoint/infra specifics (public-literature survey); safe surface. -->

# Relational Weights — a theory survey for brainstorming
*Prepared for CONTINUITY (theory). Fuel for a brainstorm, not a paper. Maturity and adversarial verdicts are honest; speculative bridges are marked.*

---

## 1. Framing

**The vision.** Our lead's intuition: if reality is fundamentally fractal, quantum, and *relational*, then the best generative audio model may be organized "like reality itself." Concretely, stop treating a weight as a **point scalar** and reify it as a **relational object**:

- **Interaction-defined** — its identity is the set of interactions it can *perform*, not a magnitude it *stores*;
- **Area of influence** — it carries an explicit field / support / neighborhood, not just a fan-out;
- **Multi-dof / spin-like** — it has more internal dimensions than one value, analogous to a particle's spin / internal quantum numbers.

**The substrate: SA3.** A rectified-flow (RF) multimodal DiT audio diffusion model operating on a ~10.77 Hz semantically-aligned latent (SAME). The targets for reparameterization are transformer weights: attention Q/K/V/O, FFN projections, and LoRA/adapter blocks. Whatever we propose must land on a *learned semantic latent* — not a raw STFT — which is the recurring make-or-break caveat below.

**The honest through-line of the whole survey.** Almost every mature idea here already exists as a *structured reparameterization of a real matrix*. The relational framing is genuine and generative, but for any given card the central discipline is the same: **prove the relational structure did work a matched-parameter scalar baseline could not**, rather than renaming a matmul. Where a card's physics is load-bearing vs. decorative is flagged throughout.

---

## 2. The theory landscape

*Maturity ∈ {established, emerging, speculative}. Promise is the source card's 1–5 self-rating. Only strong cards shown; filler dropped. Heavily-duplicated cards (Clifford, complex, tensor-network) are listed under a home theme and cross-referenced.*

### A. Hypercomplex & geometric-algebra weights — the "spins" axis
Reify a scalar as a multi-component algebraic object whose identity is the set of geometric/hypercomplex *products* it can perform; grades/phases act as spin-like internal numbers.

| Card | One-line | Maturity | Relational-weight mapping | Key cite | P |
|---|---|---|---|---|---|
| **PHM / Compacter** | Don't fix the algebra — *learn* the multiplication rule: `W = Σ Aᵢ⊗Sᵢ` | established | The n small `Aᵢ` **are** the learned interaction/multiplication table; `Sᵢ` is content. The single strongest "interaction-defined weight" anchor. | Zhang 2021 (arXiv:2102.08597); Mahabadi 2021 (arXiv:2106.04647) | 4 |
| **Clifford Neural Layers** | Weight = multivector with scalar+vector+bivector+… grades; geometric product mixes grades | emerging | A multivector is meaningful only through the geometric product it enters; bivectors are literal spin/rotation-plane carriers. Closest grade=spin match. | Brandstetter/Ruhe 2023 (arXiv:2209.04934) | 4 |
| **GCAN — rotors/bivectors** | Weight = a rotor `R=exp(bivector)` applied as sandwich `x→RxR⁻¹` | emerging | Purest "weight = capability, not content": a rotor stores *no* magnitude, only an oriented rotation. | Ruhe 2023 (arXiv:2302.06594) | 4 |
| **Clifford Group Equivariant NNs (CGENN)** | Weight collapses to scalars `φ_ijk` gating which grade×grade→grade products fire | emerging | Weight can *only* encode "how strongly interaction (i,j→k) participates"; content migrates into multivector activations. Sharpest "defined by interactions." | Ruhe/Brandstetter/Forré 2023 (arXiv:2305.11141); + Clifford diffusion (arXiv:2504.15773) | 4 |
| **GATr** | A DiT whose tokens are 16-dim projective-GA multivectors; layers are equivariant geometric products | emerging | Weights parameterize *permissible geometric interactions*, not free content. Most "plug-into-SA3-shaped." | Brehmer 2023 (arXiv:2305.18415) | 4 |
| *Complex / quaternion (low-grade corners)* | `w=re^{iθ}` / Hamilton product | established | The even subalgebra Cl(2)⁺ **is** ℂ; quaternions are a Cl special case — the safe corners of the same object. | Trabelsi 2018 (arXiv:1705.09792); Parcollet 2018 (arXiv:1806.04418) | 3 |
| *[SPEC] Rotor-valued RF velocity on a Clifford SAME latent* | Denoising as a learned rotation of latent spin-states | speculative | DiT FFN/LoRA weights become bivector generators `B(t)`; RF integrates a rotor-valued field. No audio precedent. | Novel synthesis (Liu 2209.03003; +2302.06594, +2305.18415) | 3 |

### B. Group-equivariant & Lie-theoretic weights — parameters that store group *actions*

| Card | One-line | Maturity | Relational-weight mapping | Key cite | P |
|---|---|---|---|---|---|
| **Connection-as-weight (gauge)** | Weight = a connection `g_ij` that parallel-transports j's frame into i's before mixing | emerging | The parameter has *no* gauge-invariant meaning alone; only holonomy/curvature is physical. Best area-of-influence story in the set. | Cohen/Weiler 2019 (arXiv:1902.04615); de Haan 2020 (arXiv:2003.05425) | **5** |
| **Irrep-typed / steerable weights** | Every feature/weight carries a rep-type (irrep `l`); Clebsch–Gordan selection rules dictate couplings | established | The most literal "internal quantum numbers + interaction rules": a `(2l+1)` multiplet + allowed-coupling selection rules. | Weiler/Cesa 2019 (arXiv:1911.08251); Thomas 2018 (arXiv:1802.08219); Fuchs 2020 (arXiv:2006.10503) | 4 |
| **Vector-neuron / Lie-algebra units** | Promote each unit to a vector in a rep-space (ℝ³ or a Lie algebra 𝔤) | established | Unit is characterized by how it transforms and the equivariant/bracket ops it enters; +dim(𝔤)−1 internal dof. | Deng 2021 (arXiv:2104.12229); Lin 2023 (arXiv:2310.04521) | 4 |
| **LieConv / LieTransformer** | Weight = a learned kernel *function* over a Lie group | established | Kernel encodes response to relative group elements `g⁻¹h` — capability-over-transformations. Affine time-warp/scale is a plausible audio group. | Finzi 2020 (arXiv:2002.12880); Hutchinson 2021 (arXiv:2012.10885) | 4 |
| **Harmonic Nets / complex-steerable** | Complex weight (mag, phase, harmonic order m) with SO(2) equivariance | emerging | Harmonic orders add under multiplication (`m_out=m_in+m_kernel`) — a real selection rule; the audio-native SO(2) corner. | Worrall 2017 (arXiv:1612.04642); Harmformer (arXiv:2411.03794); PHALAR (arXiv:2605.03929) | 4 |

### C. Tensor-network & quantum weight parameterizations

| Card | One-line | Maturity | Relational-weight mapping | Key cite | P |
|---|---|---|---|---|---|
| **MERA layer** | Weights = renormalization tree of disentanglers + isometries; the extra axis **is scale** | established | A weight lives at a `(position, scale)` node; causal cone widens one scale/layer → power-law (fractal, critical) decay. Most literal "organized like reality itself." | Vidal (quant-ph/0610099); Hallam 2017 (arXiv:1711.03357); Swingle 2009 (arXiv:0905.1317) | **5** |
| **Tensor-Train / MPS** | Dense `W` → 1-D chain of cores linked by bonds | established | A core exists only relationally; bond dimension χ = tunable "how entangled with neighbors" dof. Up to 10⁵× compression. | Novikov 2015 (arXiv:1509.06569); Stoudenmire 2016 (arXiv:1605.05775) | 4 |
| **MPO transformer weights** | Attention/FFN matrices as matrix-product operators; central + auxiliary cores | established | Core/auxiliary split = natural adapter geometry (train the small central tensor). Transformer-specific. | Gao 2020 (arXiv:1904.06194); CompactifAI (arXiv:2401.14109) | 4 |
| **Parameterized quantum circuit (PQC) weight** | Weight = rotation angle `θ` in `U(θ)=exp(−iθG)`; entanglers couple neighbors | emerging | Weight IS the unitary interaction it performs; PQCs compute truncated Fourier series (frequencies set by encoding, coeffs by angles) — apt for a spectral latent. | Pérez-Salinas 2020 (arXiv:1907.02085); Schuld 2021 (arXiv:2008.08605) | 4 |
| *Unitary / Lie-group weight matrix* | `W=exp(A)`, A skew-Hermitian — the classically-tractable core of the PQC idea | established | Norm-preserving, non-commutative composition; stable long-horizon RF ODE integration. The honest deployable *floor*. | Arjovsky 2016 (arXiv:1511.06464); Lezcano-Casado 2019 (arXiv:1901.08428) | 3 |
| *[SPEC] Density-matrix weight* | Weight = small k×k PSD ρ; readout only as `Tr(ρᵢ·O(ρⱼ))` | speculative | Off-diagonal coherences = internal spin-like dof; purity = per-weight uncertainty. Warns it collapses to low-rank PSD / Bayesian ensemble. | Novel bridge (Torlai 2018 arXiv:1801.09684; Reh 2021 arXiv:2305.13992) | 3 |

### D. Relational / structural-realist ontology — the "no absolute value" cards

| Card | One-line | Maturity | Relational-weight mapping | Key cite | P |
|---|---|---|---|---|---|
| **Cellular-sheaf weights** | Weight = restriction map `F(v⊴e): stalk(v)→stalk(e)` gluing local pieces | established | Pure "how these two neighbors are allowed to talk"; native cells give an explicit neighborhood. Trainable *today*. | Bodnar 2022 (arXiv:2202.04579); Hansen/Gebhart 2020 | 4 |
| **KAN — function-valued weights** | Each scalar `W_ij` → a learnable univariate spline `φ_ij(x)` on the edge | established | Weight = a transfer *capacity* realized only when a signal passes (dispositional). Spline grid = soft support. | Liu 2024 (arXiv:2404.19756) | 4 |
| **Yoneda / categorical weights** | Weight = a morphism; Yoneda makes "an object *is* its interactions" a theorem | emerging | The only card where "defined by interaction" is a *proved* equivalence, not analogy. Best as a discipline/regularizer on the others. | Bradley 2021 (arXiv:2103.14770); Gavranović 2024 (arXiv:2402.15332) | 4 |
| *Bundle/connection weights* | Weight = parallel transport between fibers (cross-refs B: gauge) | established | Content is purely relational; holonomy is the only gauge-invariant. | Cohen/Weiler 2019 (arXiv:1902.04615) | 3 |
| *[SPEC] RQM / density-matrix weights* | "No state except relative to an interaction" as the update rule | speculative | Operationalizes Rovelli RQM as arithmetic; needs a locality scaffold (sheaf/TN). | Rovelli (quant-ph/9609002) | 3 |
| *Structural-realist rubric* | Not a kernel — the acceptance test the other cards must pass | speculative | (i) no basis-absolute identity, (ii) individuated by capacity, (iii) updated as process. Use as collapse-detector. | Ladyman & Ross 2007; Whitehead 1929 | 2 |

### E. Field-theoretic weights & explicit area of influence

| Card | One-line | Maturity | Relational-weight mapping | Key cite | P |
|---|---|---|---|---|---|
| **CKConv / FlexConv** | Weight = a hypernet `g_θ(τ)` emitting the kernel, times a Gaussian mask of **learnable radius σ** | established | The cleanest existing reification: σ **is** a differentiable area of influence, trained end-to-end. Param count decoupled from receptive field. | Romero 2021 (arXiv:2102.02611); FlexConv (arXiv:2110.08059); CCNN (arXiv:2301.10540) | **5** |
| **Steerable / equivariant feature fields** | Feature maps become fields with an irrep type ρ (literal "spin"); kernels solve a steerability constraint | established | Weight = coefficients on a symmetry-adapted (spherical/circular-harmonic) basis; couplings fixed by symmetry. | Weiler/Cesa 2019 (arXiv:1911.08251); Weiler 2018 (arXiv:1807.02547) | 4 |
| **NN↔QFT correspondence** | Network output as a field theory; weights → couplings, interactions → non-Gaussian vertices | emerging | A weight becomes a coupling constant with RG-defined relevance/locality; a design language for correlation structure. | Halverson 2020 (arXiv:2008.08601); Demirtas 2024 | 4 |
| *NNGP / NTK* | Infinite width: the individual weight dissolves; the *kernel* carries everything | established | Effective weight = a 2-point function `K(x,x')`; kernel decay = area of influence. But the pure limit under-performs (loses feature learning). | Lee 2018 (arXiv:1711.00165); Jacot 2018 (arXiv:1806.07572) | 3 |
| *Free-Energy / Markov-blanket units* | A unit's area of influence = its Markov blanket (conditional-independence boundary) | speculative | Strongest *formal* grounding for "area of influence"; but may collapse to learned sparse + precision-weighted attention. | Friston 2019 (arXiv:1906.10184) | 3 |

### F. Spin-glass, Ising/Potts & energy-based couplings

| Card | One-line | Maturity | Relational-weight mapping | Key cite | P |
|---|---|---|---|---|---|
| **Weight-as-coupling `J_ij` (Hopfield→attention)** | The archetype: weight = pairwise coupling in `E=−ΣJ s_i s_j`; modern Hopfield = softmax attention | established | The relational thesis is **already latent inside SA3's attention**. Legitimizes the program; adds no dof alone. | Hopfield 1982; Ramsauer 2020 (arXiv:2008.02217) | 3 |
| **Potts-coupling weights** | Scalar `J_ij` → q×q table `J_ij(a,b)` over discrete internal "colors" | established | Cleanest literal "more than one value per weight": an interaction *table*, not a strength. q² blow-up risk. | Kanter 1988; CRF/MRF potentials | 4 |
| **Vector-spin / quaternion couplings** | Weight = a rotation (SO(2)/SO(3)/quaternion) acting on vector units | established | Coupling rotates rather than scales; carries an orientation. Audio is phase-bearing. | Parcollet 2018 (arXiv:1806.04418); hypercomplex UAT (arXiv:2401.02277) | 4 |
| **Kuramoto phase-oscillator weights** | Weight = 2-dof edge `(K_ij coupling, α_ij phase-lag)`; synchronization = computation | emerging | Phase-locking is unusually apt for pitch/rhythm; synchronized clusters = a *dynamic* area of influence. | AKOrN (Miyato 2024); higher-order Kuramoto memory (arXiv:2507.21984) | 4 |
| *Dense associative memory / hyperedges* | Pairwise `J_ij` → k-ary tensor `J_{i…k}` binding k units | established | Weight = a hyperedge; its k-tuple support is an explicit neighborhood. Combinatorial growth forces low rank. | Krotov/Hopfield 2016 (arXiv:1606.01164) | 3 |

### G. Fractal, RG & holographic organization — "like reality itself," made concrete
Unifying claim: *"organized like reality itself" = the **same** relational rule tied across scales (RG-covariance / self-similarity), so parameter count decouples from depth/resolution.*

| Card | One-line | Maturity | Relational-weight mapping | Key cite | P |
|---|---|---|---|---|---|
| **RG-covariant couplings (deep net as RG flow)** | Weight = a Wilsonian coupling obeying *one* flow rule reused at every coarse-graining scale; depth = RG time | emerging | Store a few couplings + a blocking rule; per-scale weights are *generated*, not stored. RG-covariant tie generalizes ALBERT-style sharing. | Mehta/Schwab 2014 (arXiv:1410.3831); Li/Wang 2018 (arXiv:1802.02840) | **5** |
| **Wavelet scattering** | Weight = a dilation+rotation of one mother wavelet — a self-similar template | established | Coefficient defined by the wavelet-convolution+modulus it performs; support dilates with scale. Most directly audio-proven. | Mallat 2012 (arXiv:1203.1513); Andén/Mallat 2013 (arXiv:1304.6763) | 4 |
| **Scale-equivariant steerable nets** | Same learned filter transported across a scale group | established | Weight = `(coefficients, scale-group element)`; scale index = explicit internal number. Audio ≈ transposition/tempo covariant. | Sosnovik 2020 (arXiv:1910.11093); Worrall/Welling 2019 | 4 |
| *Holographic / emergent-geometry weights* | Depth = radial bulk coordinate; layer weight = local metric | emerging | UV(fine timbre)/IR(coarse form) split; can collapse to "a NeuralODE with a fancy interpretation." | Hashimoto 2018 (arXiv:1802.08313) | 3 |
| *Hyperbolic weights* | Negative-curvature space; radius = hierarchy depth | established | Geodesic ball whose reach grows exponentially with radius; good only if data is tree-dominated. | Nickel/Kiela 2017 (arXiv:1705.08039); Ganea 2018 | 3 |
| *[SPEC] Fractal weight-sharing hypernetwork* | One generator emits all weights by recursive self-similar expansion | speculative | The learned object is the *rule*, not the weights. Highest upside / risk of collapsing to layer-sharing. | Synthesis (FractalNet arXiv:1605.07648 + hypernets) | 3 |

### H. Interaction-first computation & emergence

| Card | One-line | Maturity | Relational-weight mapping | Key cite | P |
|---|---|---|---|---|---|
| **Edge-resident KAN / message-passing** | Move the weight onto the edge and promote it to a learnable *function/operator* | established | Weight only exists as the transformation it applies to a message; spline grid = spectral area of influence. | Liu 2024 (arXiv:2404.19756); Gilmer 2017 (arXiv:1704.01212) | **5** |
| **Dynamic / fast-weight programmers** | The weight isn't stored — it's computed from token interactions (attention = a computed weight) | established | Weight `a_ij=softmax(q_i·k_j)` is literally a relation. Novelty = a *persistent* fast-weight state the RF flow writes to. | Schlag 2021 (arXiv:2102.11174); Katharopoulos 2020 (arXiv:2006.16236) | 4 |
| **Hypernetworks / conditioned weight fields** | Every weight emitted by a generator from a context/coordinate code | established | Weight = "what the generator does here, now"; codes tie weights into relational families; condition on `(t, pos, modality)`. | Ha 2016 (arXiv:1609.09106) | 4 |
| **Neural cellular automata** | One shared local update rule tiled over a field; global structure emerges | emerging | Purest "area of influence" (the CA neighborhood) + "weight = what it does to neighbors." Unproven at audio quality. | Mordvintsev 2020 (Distill); HyperNCA (arXiv:2204.11674) | 4 |
| *Physical reservoirs at self-organized criticality* | Don't parameterize weights; hold a coupled medium at the edge of chaos | speculative | Correlation length diverges at criticality → scale-free (fractal) reach. Soft form may reduce to "tune the spectral radius." | Tanaka 2019; Bertschinger/Natschläger 2004 | 3 |

---

## 3. Convergences — where multiple independent themes agree (the real signal)

Eight distinct starting points repeatedly land on the same handful of objects. That coincidence is the strongest evidence about what "relational weight" *naturally* wants to be.

1. **Geometric-algebra multivectors + the geometric product** *(strongest, most cross-theme).* Five themes (A, B, C, D, H) converge here. A graded multivector in Cl(p,q); the geometric product mixes grades; bivectors are literal rotation generators (spin sectors); Cl(2)⁺=ℂ and quaternions are the low-grade corners. **Why it matters:** simultaneously (a) the most literal "internal quantum numbers + interaction-defined weight," (b) already trained at transformer scale (GATr, CGENN), and (c) reachable by a *cheap honest first experiment* — PHM/Compacter, which **learns** the algebra instead of imposing it.

2. **Tensor-network bonds as area-of-influence + entanglement dof, with MERA as the fractal form.** χ gives graded internal dof; bond *topology* (chain/tree/MERA) gives explicit support; MERA's widening causal cone gives power-law (critical, holographic) decay matching audio's 1/f structure. The one cluster that supplies *both* requested properties with a single knob.

3. **Gauge connection / sheaf restriction map = weight as pure relation.** The weight IS a comparison/transport between two frames; no gauge-invariant value alone, only holonomy is physical. Purest realization of the brief, comes with a native neighborhood, is trainable today (Neural Sheaf Diffusion), and is the natural home for the survey's most under-used angle: **cross-modal (text↔audio) weights**.

4. **Steerable irrep "spin label" + complex phase (the SO(2) audio bridge).** Explicit rep-type → `(2l+1)` multiplet + selection-rule couplings; the SO(2)/phase corner (= Cl(2)⁺) is audio-native and the *lowest-risk* experiment because complex audio nets already work.

5. **Weight-as-function-field with an explicit, differentiable support.** CKConv's σ, KAN's splines, hypernet-emitted weights: the *only* cluster that turns "area of influence" into a single trainable scalar, trainable at scale today, and makes weights time-varying along the RF trajectory without inflating stored params.

6. **RG-covariance / scale-tying = the concrete meaning of "organized like reality itself."** One relational rule tied across scales. Audio is approximately scale/transposition/tempo-covariant, so this is both motivated and *cheap to falsify* (does ALBERT-style depth/scale-tying help audio FID/CLAP?).

7. **Weight-as-coupling on an energy landscape.** Attention ↔ Hopfield ↔ spin-glass ↔ dynamic weights. Shows the thesis is *already inside SA3*, so the minimal honest extensions are: add spin dof to the units, add a few relaxation steps, make the fast-weight state persistent across RF steps — not a from-scratch rebuild.

8. **[Speculative sibling] Density-matrix / RQM weights.** Highest conceptual fidelity to the relational/quantum anchor and a natural home for calibrated stochasticity in the RF field — but *every* card in the cluster independently warns it collapses to low-rank PSD (rank-1 = a complex weight) or a Bayesian posterior. Ship only as a small ablation whose burden is "prove the off-diagonal coherences do work an ensemble mean cannot." *[Independent corroboration, 2026-07-31: a separate physics synthesis Kim shared with CONTINUITY lands on the same density-matrix idea with the same collapse warning — two independent routes agree this is the weakest card.]*

---

## 4. Candidate model sketches (with adversarial verdicts)

*Each: the design, what it buys, then the honest verdict — strongest defensible version, hardest problem, what it reduces to. Four were adversarially reviewed; two (SheafGauge, SyncGlass) carry synthesis-level analysis only, flagged as such.*

### 4.1 GeoProduct-DiT — PHM-anchored multivector weights → **SHIP FIRST (as an ablation, not a physics claim)**
**Design.** Replace SA3 LoRA/FFN/attention projections with small multivector operators in two stages: (1) PHM/Compacter, `W = Σᵢ Aᵢ⊗Sᵢ`, where the learned `Aᵢ` are the shared multiplication table and `Sᵢ` (rank-1) is content; (2) anneal `Aᵢ` toward the structure constants of a chosen Cl(p,q) so blocks become genuine multivectors, with grades read as spin dof and denoising reframed as rotor-valued flow.
**What it buys.** Directly instruments the fleet's core hypothesis ("weight = the interactions it can perform") on the real substrate at ~0.05–1% of params; phase/rotation-aware channel mixing; parameter efficiency from shared interaction rules.

> **Adversarial verdict — *needs-work; genuinely useful reframed.***
> - **Reduces to:** pre-anneal it **is** PHM/Compacter (structured real matmul); post-anneal it **is** a Clifford/hypercomplex linear layer (Cl(2)⁺ = deep-complex net / complex LoRA). Geometric-product left-mult is a fixed real 2ᵐ×2ᵐ tied-sign matrix — a strict subset of dense matmuls. Only the anneal schedule and rotor-RF are non-reducible — and those are the *unsupported* parts.
> - **Coherence breaks:** the design conflates Clifford vector-dim `m` with algebra-dim `2ᵐ` ("n modes AND 2ⁿ components" can't share one n); grade/rotor/spin readings hold *only* at the frozen λ=1 endpoint; "attention = ⟨q,rev(k)⟩₀" reduces to *exactly* standard dot-product attention in Euclidean signature.
> - **Trainability:** bilinear gradients scale with the co-operand (init *at* Clifford constants with a learnable residual beats anneal-*toward*); gated-grade norm nonlinearity has a 1/‖·‖ singularity; rotor-valued RF fights RF's straight-line transport objective (rotor flow is a curved geodesic) unless the data has that symmetry.
> - **Audio fit:** physics is largely **cosmetic** on a learned semantic latent — nothing there is a spinor, so "grade-2 = the literal spin dof" is metaphor. The non-cosmetic part is PHM's shared `{Aᵢ}` as a real operationalization of "weight = its interactions."
> - **Strongest version:** strip the physics from the load-bearing path. Ship free-PHM/Compacter as a *learned-algebra* ablation; for phase-plausible projections **initialize at Cl(2)⁺ with a learnable residual** and let the model relax away; treat the signature as *learned/searched*; **always benchmark against a matched-parameter free-PHM baseline**; drop rotor-RF and the spin framing from anything load-bearing.
> - **Decisive cheap experiment:** train free-PHM adapters on SA3 and measure whether the learned `{Aᵢ}` **spontaneously drift toward a Clifford/complex structure-constant tensor**. If yes → geometry is *discovered*, program validated for one adapter run. If no, and fixed-Clifford never beats matched-param free-PHM → geometry is cosmetic and only known PHM efficiency survives.

**Honest status: the most promising, because it is the cheapest honest instrument of the whole thesis.**

### 4.2 PhaseSpin — steerable complex / circular-harmonic weights on pitch-time SO(2) → **RUN AS THE DE-RISKING CONTROL**
**Design.** Each weight = a complex coefficient `(r,θ)` typed by discrete harmonic order `m`; complex multiply (scale+rotate+interference) is the interaction; `m_out=m_in+m_kernel` is a U(1) "which-couplings-permitted" typing. SO(2)-steerable complex convs/attention on SAME.
**What it buys.** Phase-coherent generation + native transposition equivariance at the *lowest reinvention gamble* of any sketch (complex audio nets already work: DCCRN, PHALAR).

> **Adversarial verdict — *needs-work; least speculative.***
> - **Reduces to:** Deep Complex Networks + 1-D SO(2) Harmonic/E(2)-steerable CNNs + complex attention. A complex-linear layer = a real layer constrained to scaled-rotation blocks — a weight-shared 2-channel real net, *not* a richer object. No new primitive; novelty is empirical only.
> - **Coherence breaks:** "`(2l+1)`-dim SO(2) multiplet" is a category error (SO(2) is abelian, its complex irreps are 1-D; `2l+1` is SO(3)); "pitch-time SO(2)" conflates the pitch-class circle with time-translation. `m` is a *designer-chosen* label, undercutting "defined by *learned* interactions."
> - **Audio fit — the killer:** signal-domain phase wins do **not** transfer to a 10.77 Hz semantic latent whose Nyquist (~5.4 Hz) can carry only slow modulation phase, not audio-partial phase (owned by the decoder). The narrow real benefit — approximate transposition-equivariance — is only approximate (timbre/formants break it) and *assumes a clean cyclic pitch axis the learned latent may lack*.
> - **Strongest version:** keep the single honest bridge — a weight **typed by its permitted couplings** (`m_in→m_out` under charge conservation) is literally "a weight defined by the interactions it is capable of." Ship it as the least-speculative *control* for the entire group-equivariant program — valued because complex nets are known-good — **gated behind a symmetry probe.**
> - **The transferable payload for CONTINUITY:** "relational weight" = "weight acts via a *representation of a symmetry group*." Every sketch in this program (gauge, capsule, PhaseSpin) lives or dies on the same prerequisite: **a real, identifiable group action on the SAME latent.** PhaseSpin's job is to test that prerequisite cheaply before anyone builds heavy non-abelian machinery.

**Honest status: promising *as a control/probe*, not as a phase engine — its main value is testing the symmetry prerequisite for the whole program.**
> **→ STATUS REVISED — REOPENED (G2b, 2026-08-01).** G2 (2026-07-31) *preliminarily* read the phase branch CLOSED — SAME's envelope-phase readout was weak (circ-concordance 0.357 on 1-2kHz, 0.323 beat-relative; MLP-not-better-than-ridge), consistent with "phase is the decoder's." **G2b overnight REVERSED that: carrier phase IS present in SAME, as literal 2-plane rotations in the code — a direct measurement vindication of Convergence-4 (steerable-irrep / SO(2) phase weights).** So the earlier null was a measurement-scope artifact (the envelope-phase readout missed the carrier's 2-plane rotation structure), not a real absence — phase-native weights are back on the table for this latent, pending C's full G2b write-up. *Meta-caution (F): the phase story revised once inside a day (G2→G2b) — treat as LIVE, not settled; do not act on a single-gate "closed"/"open" verdict. This annotation itself corrected a same-day "TESTED-CLOSED" edit that G2b invalidated.*

### 4.3 SheafGauge — cellular-sheaf / gauge-connection attention → **HIGHEST-UPSIDE RESEARCH BET (push on cross-modal edges)**
**Design.** Attach a d-dim stalk to each token/edge; the weight is a restriction map `F(v⊴e): stalk(v)→stalk(e)` (equivalently a connection `g_ij` transporting j's frame into i's before mixing). Value vectors are parallel-transported before aggregation; a learned sheaf Laplacian governs diffusion; holonomy is the only physical observable.
**What it buys.** Heterophily-aware, anti-oversmoothing token mixing (a real deep-DiT failure mode); the purest "weight = capability not information" that is *nonetheless trainable* (Neural Sheaf Diffusion is benchmarked); a native area of influence; and — the survey's most under-used angle — **cross-modal coupling as parallel transport between representation-types** (text↔audio), with a U(1) connection = literal phase transport.

> **Verdict — synthesis-level (no separate adversarial pass yet).**
> - **Hardest problem:** no gauge-equivariant audio-DiT precedent; needs a *posited* base-space + structure group for SAME; with a flat/trivial connection it collapses to ordinary attention; learning non-trivial holonomy without a real base-space symmetry may be underconstrained. A research program, not a drop-in.
> - **Reduces to:** with trivial stalks/flat connection → standard attention / a weighted GNN. The gain requires stalk_dim > 1 and learned non-diagonal restriction maps.
> - **Where to push:** start with the trainable sheaf variant on the token lattice *plus cross-modal edges*; escalate to a full gauge connection only with a posited audio structure group (pitch U(1) / time-warp). Same symmetry prerequisite as PhaseSpin gates it.

**Honest status: the most conceptually faithful to "weights organized like reality itself," best on cross-modal edges — but unproven; treat as a program.**

### 4.4 HoloMERA — hierarchical tensor-network (MERA) weights → **HIGH-UPSIDE, OVERSOLD; de-hype before use**
**Design.** Replace attention/FFN matrices with a MERA tree (disentanglers + isometries), each core defined by its bonds χ, scale index, and causal-cone position; scale-invariant tying reuses one core per scale.
**What it buys.** Principled log-depth multi-resolution mixing matched to audio's 1/f structure; ~10⁴× compression; and the fractal/holographic framing backed by AdS/CFT rather than metaphor.

> **Adversarial verdict — *needs-work; oversold.***
> - **Category slip:** MERA is an ansatz for a quantum **state** (a vector, budgeted by entanglement entropy across a cut); a weight is an **operator** (a map). Read as an operator it is a well-defined hierarchical-Tucker/tree tensor network + disentanglers — but MERA's physics efficiency guarantees (area/log-law entanglement of critical *states*) **do not transfer** to weight matrices; no low-operator-entanglement theorem exists for them.
> - **Substrate mismatch:** the load-bearing content is a learned multi-resolution isometric filterbank with local decorrelation; the chosen substrate (short SAME latent) is close to the *worst case* for its actual advantage. Holographic apparatus is **decorative**.
> - **Trainability/cost:** isometry/unitarity constraints make gradients finicky (needs Cayley/exp on the Stiefel manifold); contraction is expensive. Without disentanglers + unitarity it degenerates to a wavelet/U-Net.
> - **Strongest version:** hand over the de-hyped core as three *separable* levers — (1) **disentanglers** as the one genuinely-novel ingredient, ablated head-to-head vs. an identical no-disentangler wavelet/tree-TN at matched param/FLOP; (2) **scale-invariant tying** as an optional strong sharing prior; (3) the actually-promising smuggled idea: **per-scale RF velocity integrated coarse-to-fine** (a multigrid/cascaded RF schedule). Sell as inductive biases, *not* "organized like reality itself."
> - **Decisive experiment:** at matched param+FLOP, does MERA-with-disentanglers beat MERA-without (= a learnable orthogonal-wavelet / tree-TN U-Net) on audio FID/CLAP? Null gap → the whole MERA/holography apparatus is dead weight and the tree structure alone did the work.

**Honest status: the best fractal narrative fit, but narrative fit ≠ task fit; only the disentangler and per-scale-RF ideas may earn their keep.**

### 4.5 FieldWeights — CKConv/FlexConv + KAN + hypernet(t) → **TRIM HARD to one idea**
**Design.** Weights = a generator emitting `w(τ)=g_θ(τ)·exp(−τ²/2σ²)` (learnable support σ), optionally KAN edge splines, optionally hypernet-emitted `ΔW(t, pos, modality)`.
**What it buys (as pitched).** "Explicit differentiable area of influence" as a trainable scalar; per-head timescale adaptivity; time-varying condition-relational weights along the RF trajectory.

> **Adversarial verdict — *needs-work; three glued methods, one keeper.***
> - **What it actually is:** (1) CKConv+FlexConv, (2) HyperNetworks/hyper-LoRA, (3) KANs — glued by a slogan; the field/spin ontology is decoration.
> - **Incoherence #1:** the stated mixing pass `y_i=Σ_j w(τ_i−τ_j)(Vx_j)` is *content-independent* — a long/dynamic **convolution** (Hyena/CKConv family) or a learnable-scale ALiBi/Gaussian bias, **not attention**. It silently swaps the model, not the weights.
> - **Incoherence #2:** KAN per-edge splines *explode* params (`G·d²`), contradicting the "no inflated params" headline. Two mechanisms fused only by metaphor.
> - **Incoherence #3:** the ontology is a change of basis — `g_θ` is scalar-weighted, `w(τ)` is still a number; "defined by interactions not information" is true of *every* weight. No new mechanism, no algebra, no conserved number → not "spin," not "fractal," not "quantum."
> - **Reduces to:** FlexConv/CKConv/CCNN; the data-independent long-conv family; a learnable-width ALiBi bias; SchNet-style continuous-filter (RBF) convolutions (Schütt 2017 — the *honest* physics-ML precedent to cite); adaLN-zero timestep conditioning in weak form.
> - **Cost:** the FFT win that motivates CKConv needs *long* sequences; SA3's ~10.77 Hz latent is *short* (10 s ≈ 108 tokens), so the MLP kernel-gen overhead likely erases it.
> - **Strongest version (the one keeper):** **keep SA3's attention**; add to each head a learnable-width locality envelope on the *logits* — `σ_h(t)`, a small function of diffusion-time (essentially learnable-scale ALiBi with timestep conditioning). Cheap, stable, foldable; literally the brief's "explicit differentiable area of influence" as a per-head scalar; audio-motivated (multi-timescale) and diffusion-motivated (broad at high noise, narrow near data). If "fractal" must mean something, make σ dyadic/wavelet.
> - **Key open question / kill switch:** is a time-varying-support head provably distinct from a fixed-support head **+ existing adaLN feature modulation**? Exhibit a SAME-latent function the former represents efficiently and the latter cannot. If not, it collapses to a "fancy weight-tying prior."

**Honest status: mostly a repackage; the single surviving idea — `σ_h(t)` broad→narrow across denoising — is genuinely worth a quick, falsifiable test.**

### 4.6 SyncGlass — Kuramoto / Potts coupling weights → **INTERESTING BUT COSTLY; scope narrowly**
**Design.** Weight = a relational coupling: a Potts table `J_ij(a,b)`, or a Kuramoto edge `(K_ij, α_ij)`, or a persistent fast-weight matrix the RF trajectory writes to. Computation = a few relaxation/synchronization steps, not one multiply.
**What it buys.** Native periodicity/harmonicity and phase-locking priors (apt for pitch/rhythm at ~10.77 Hz); an energy-relaxation auxiliary sampler/refiner; a *dynamic*, input-dependent area of influence (synchronized clusters = binding-by-synchrony).

> **Verdict — synthesis-level (no separate adversarial pass yet).**
> - **Hardest problem:** iterative relaxation costs FLOPs against RF's few-step sampling budget; `(strength, phase-lag)` risks collapsing to **complex-valued attention** unless the nonlinear collective dynamics (sync/desync, hysteresis) are genuinely exploited; backprop-through-dynamics stability at audio scale is unproven.
> - **Reduces to:** modern Hopfield = one attention step; the distinctive value requires *R* > 1 relaxation steps that measurably beat the 1-step (attention) limit.
> - **Where to scope:** a Kuramoto/Potts block on a *subset* of heads devoted to periodic/harmonic structure; and/or a persistent fast-weight state the RF integrator updates across denoising steps (the under-explored "weight-as-process" angle).

**Honest status: physically apt for pitch/rhythm and the cleanest "living area of influence," but the relaxation cost and complex-attention collapse risk make it a scoped experiment, not a backbone.**
> **→ Phase status REVISED — REOPENED by G2b (see 4.2): carrier phase IS present in SAME as 2-plane rotations.** The Kuramoto phase-oscillator reading is back on the table with the rest of the phase branch (a phase signal to lock to now exists); the non-phase Potts-coupling core remains untested/low-priority. *(Was briefly marked "phase half CLOSED" on the G2 prelim; G2b invalidated that — treat as live.)*

**Overall ranking for CONTINUITY:** GeoProduct-DiT (PHM form) is the honest, cheap thesis-instrument to **ship first**; PhaseSpin is the **de-risking control** for the symmetry prerequisite; SheafGauge (esp. cross-modal) and HoloMERA (disentangler + per-scale-RF) are the **higher-upside research bets**; FieldWeights should be **trimmed to `σ_h(t)`**; SyncGlass is a **scoped harmonic-head experiment**. Likely dead-ends as *load-bearing* physics: rotor-valued RF, the spin/quantum framings on a learned latent, dense density-matrix weights, and any card whose "relational" content trains back to its own scalar/diagonal/flat limit.

---

## 5. For CONTINUITY — sharpest open questions + what to chase next

### The six questions to brainstorm (roughly in dependency order)

1. **What is the RIGHT geometry/symmetry over a *learned* SAME latent?** *(The make-or-break question shared by every geometric/gauge/steerable card.)* Positing Cl(p,q), a gauge group, or an irrep type is a *guess* — wrong, it costs capacity for no invariance. Can we **discover** the latent's approximate symmetry from data (learned Killing-form metric à la Metric-Learning-for-CGENN arXiv:2407.09926; LieGAN-style discovery; or probing which channel rotations leave the RF velocity ~invariant) instead of guessing? **This de-risks half the survey and should be chased FIRST.**

2. **The universal collapse test.** Nearly every card warns it may reduce to low-rank/LoRA, a complex net, a structured linear layer, or gated attention. Make *"prove it didn't collapse"* the central experimental discipline: (a) always compare against a matched-**parameter**-budget scalar baseline, not just final loss; (b) measure the *used* relational structure after training — does bivector / off-diagonal-coherence / holonomy / harmonic-order content stay non-trivial, or decay to the scalar/diagonal/flat fixed point? A reparameterization that trains to its own scalar limit is a rename; we need a metric that catches this.

3. **Does SA3's semantic SAME latent retain recoverable PHASE?** The complex, Kuramoto, Harmonic-Net, and Born-machine cards all hinge on this. **Cheap probe (zero architecture change):** can a linear or complex readout recover STFT phase / instantaneous frequency from SAME? Note the adversarial caveat — Nyquist ~5.4 Hz means SAME can at most carry *slow modulation* phase, not audio-partial phase (owned by the decoder). If not recoverable, phase-native weights are redundant. **Run before PhaseSpin.**

4. **Area of influence ALONG THE FLOW.** No card fully exploits that a weight in an RF-DiT has a *diffusion-time* axis. Should a weight's support be `(t-slice) × (token neighborhood) × (grades/scales)`, with a principled schedule — coarse/global/high-grade structure at high noise, fine/local/low-grade near data? The rotor-RF, hypernet(t), and `σ_h(t)` ideas all gesture at this; nobody has *designed the schedule*.

5. **Turn the philosophy into a loss.** The Yoneda / structural-realist / RQM cards argue a genuine relational weight must (a) compose functorially and (b) expose only gauge/basis-invariant readouts. Can these become **regularizers** — penalize non-invariant content, require typed composition — that both force the sketches to be truly relational *and* serve as the collapse-detector of Q2?

6. **Unify the two strongest convergences.** Several cards suggest but nobody has built: multivector-valued *stalks* on a sheaf; geometric-algebra restriction maps; function-valued *multivector* weights; MERA with *multivector bonds*. Is the product more than the parts — does a MERA-of-Clifford-tensors give both the fractal area-of-influence *and* the spin dof at once, or do the constraints fight?

### What the survey missed / chase next

- **A. Cross-modal relational weights.** SA3 is *multimodal*, yet almost every card reifies weights *within* a single audio stream. The relational idea is most natural on **cross-modal edges** — text↔audio as a typed morphism (Yoneda), a sheaf restriction map between different stalks, or a connection transporting between representation-types. **Highest-value under-explored angle; push SheafGauge and categorical weights here.**
- **B. The generative-trajectory / process dimension.** The survey is heavy on spatial/algebraic structure, light on the fact that SA3 *generates* over an RF ODE. Weight-as-process (Whitehead) → an RF-trajectory-indexed, write-addressable weight field (persistent fast-weights, hypernet(t), RG-time depth). Under-developed and cheap to prototype.
- **C. Empirical symmetry-discovery for audio latents** — the missing modality that grounds the group choice half the geometric cards *guess* at (see Q1). Without it the geometric program stays speculation.
- **D. Perceptual / psychoacoustic grounding.** No card asks what relational structure human hearing uses (critical bands, harmonic templates, temporal masking, roughness). "Area of influence" could be **perceptually** defined (a critical-band support, a harmonic-comb neighborhood) — plausibly a better inductive bias for a generative audio model than borrowed 3D-Euclidean equivariance.
- **E. Criticality / edge-of-chaos as a cheap stability tool.** Tuning SA3's RF-DiT spectral radius toward the edge of chaos (or a criticality regularizer) is a low-cost lever for stable long-horizon propagation over long SAME sequences — worth a quick look independent of the exotic parameterizations.
- **F. Metrical-tree positional encoding — the most audio-native fractal transplant.** *(Added 2026-07-31 by CONTINUITY, cross-mapping this survey against a physics PDF from Kim.)* Music's position structure IS a tree (16th → beat → bar → phrase); we currently flatten it into a line via RoPE. A hierarchy-native PE is Theme G's fractal/self-similarity thesis applied exactly where audio *has* self-similar structure — and it is a concrete candidate structural fix for our standing **long-range-structure-recall / prompt-arc gap** (the gap the RoPE loop-collapse null, task #60, left open: RoPE-flatness is plausibly *why* long-range musical form fails to recall). No card in the survey had it; likely the single most concrete audio-native lever in the whole document.
- **G. x0-vs-velocity target parameterization (belongs under B, the process dimension).** *(Added 2026-07-31 by CONTINUITY, from the same physics PDF — cite "JLT", VERIFY before building.)* The RF/diffusion prediction target (x0 vs velocity) is a genuinely cheap lever whose claimed mechanism — velocity regression amplifies low-variance *ambient* directions — speaks directly to our melody / spectral-bias thread. A process-dimension lever that needs no exotic weight object; cheap to A/B.

### Recommended sequencing
1. **Prerequisites (cheap, decisive):** run the **phase-recoverability probe** (Q3) and a **symmetry-discovery pass** (Q1/C) — including the free-PHM "does it drift toward Clifford?" measurement — *before* building any exotic layer.
2. **Ship the honest instrument:** **GeoProduct-DiT in its PHM/Compacter form**, with the **collapse test (Q2)** wired in from day one and a matched-parameter free-PHM baseline.
3. **De-risk with the control:** **PhaseSpin** as a relaxed-complex adapter, gated behind the symmetry probe.
4. **Escalate the upside bets:** **SheafGauge on cross-modal edges (A)** and **HoloMERA's disentangler + per-scale-RF levers**, each with its own kill-switch ablation.

*Design rubric to keep everyone honest (from the structural-realist card): a proposal earns the word "relational" only if its extra dof (i) carry no basis-absolute identity, (ii) individuate the weight by its capacity to interact, and (iii) survive the matched-budget collapse test with non-trivial, used structure. Everything else is a renamed matrix.*