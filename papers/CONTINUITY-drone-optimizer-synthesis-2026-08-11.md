# Paper-grounded synthesis — optimizer / weight-decay / magnitude-preservation for the full-FT drone
CONTINUITY, 2026-08-11. Reading the papers Kim downloaded (not Gemini summaries). Order = build-up.
Status: IN PROGRESS. Each entry = what the PAPER actually says + what it means for OUR runaway.

## L1 — Baseline: is a matrix optimizer even worth it? [2509.02046 Fantastic Optimizers I, Wen/Hall/Ma/Liang, Stanford]
- Method: 10 optimizers × 4 scales (0.1–1.2B) × data-to-model 1–8× Chinchilla, EACH optimizer's HPs
  tuned separately, eval at END of training (not intermediate — rankings flip under LR decay).
- Matrix-preconditioner optimizers (Muon, Soap, Kron) DO consistently beat scalar ones (AdamW, Lion, Mars).
  So Muon-family genuinely wins — but the margin over a FAIRLY-tuned AdamW is **1.4× @0.1B → 1.1× @1.2B,
  inversely proportional to scale.** Extrapolated to our 1.4B: ~1.1× or less.
- Prior "2×" claims inflated by (i) under-tuned AdamW baseline, (ii) intermediate-checkpoint comparison.
- Real-world adoption of new optimizers ≈ nil except Kimi-K2 (Muon-clip).
- Figure aside: optimal wd differs wildly per optimizer (Lion wants wd≈0.6). => per-optimizer HP tuning is
  mandatory; blind transfer is unfair. (Directly validates our adamw_fair arm needing its OWN lr, not 8e-5.)
- **FOR US:** at 1.4B the Muon speed premium is marginal (~1.1×) AND Muon is what causes our runaway. So a
  fairly-tuned AdamW full-FT is the pragmatic front-runner; the Muon-repair stack must earn its ~10%.

## L2 — Mechanism: why weight decay bounds it [2305.17212 Rotational Equilibrium, Kosson/Messmer/Jaggi, EPFL]
- Core: with weight decay, a neuron's weight-norm E[‖ω‖] AND angular update E[∠(ω_t,ω_{t+1})] converge to a
  steady state ("rotational equilibrium"). The angular update ≈ the EFFECTIVE learning rate.
- For SCALE-INVARIANT weights (those followed by a norm layer), wd is NOT regularization — it's a knob on the
  effective LR (Van Laarhoven). Equilibrium ‖ω‖ balances update-growth vs decay-shrinkage; too-weak wd →
  large ‖ω‖ → collapsed effective LR (network stops rotating/learning direction).
- "Explicitly controlling the rotation gives wd's benefits while cutting LR-warmup need." => the conceptual
  ancestor of Hyperball (constrain ‖ω‖ directly instead of soft-decaying it).
- **IMPORTANT NUANCE the Gemini report blurred:** Kosson's clean theory is for SCALE-INVARIANT (normalized)
  weights, where growth shows up as effective-LR change. OUR runaway lives in the OUTPUT projection, whose
  scale is NOT invariant — there weight-norm growth is DIRECTLY output-magnitude growth (the drone), not just
  an effective-LR shift. So: the equilibrium-∝-1/wd framing explains why wd bounds the WEIGHT norm; the
  drone is the un-normalized-output consequence. This is why an OUTPUT-targeted fix (SFWN on the final proj,
  or the output-std penalty) is conceptually cleaner for us than global wd — it addresses the non-invariant
  layer where the harm actually lands. [to confirm against EDM2/MaP-DiT which normalize exactly there.]

## L3 — wd in practice / transfer
### [2510.19093 Weight Decay may matter more than µP for LR Transfer, Kosson et al., Amazon+EPFL, ICLR2026]
- µP's alignment assumptions hold only BRIEFLY at start of training. For the rest, **weight decay (not µP)
  stabilizes cross-width update dynamics → is what actually enables LR transfer.** µP ≈ implicit warmup.
- Explains why µP needs the INDEPENDENT (decoupled) wd variant for good transfer.
- **FOR US:** to transfer the small-T512-A/B's winning LR/wd to the big run, **wd is the key stabilizer, not
  µP**. FusionOpt already applies decoupled wd on the fast iterate → the transfer path is "get wd right,"
  which is exactly what the A/B finds. Good news for the small→large plan.
### [2607.23777 Scale Weight Decay and Train Better (Muon-SW), Apte, JPMorgan]
- Constant decoupled wd biases the target (weights shrink steadily). Fix: scale wd by η/η_max (Robbins-Monro);
  proven to preserve stationarity for SGD AND **Muon**; weight norm then settles ~constant instead of shrinking.
  Muon-SW = 30% faster to same loss (72–930M MoE, few LoC).
- **FOR US — the schedule-free caveat is REAL:** Muon-SW scales wd by η/η_max, but FusionOpt is Schedule-Free
  → η≡η_max (constant LR) → the η/η_max factor ≡ 1 → **Muon-SW collapses to constant wd for us; the scheduling
  trick is moot.** (Gemini flagged this correctly.) What DOES transfer: the steady-state result — with the
  right constant wd, Muon's weight norm SETTLES to a constant. Our runaway = under-decay (norm grows, never
  settles). So the fix is purely the wd MAGNITUDE (A/B), no scheduling. Confirms wd 0.1 direction; the value
  itself is what the A/B pins.

## L3-synthesis so far (L1–L3): the strategic picture is holding, sharpened
- Muon buys ~1.1× at 1.4B over a fairly-tuned AdamW, and CAUSES the runaway → AdamW is the pragmatic default;
  Muon-repair must earn its 10%. [2509]
- The runaway is under-decay: Muon's constant-norm update needs wd strong enough to reach the norm steady
  state; too weak → linear growth. Right wd → norm settles. [2305, 2607]
- Our A/B's wd should transfer small→large via decoupled wd (not µP). [2510]
- OPEN nuance to resolve in L5: for the OUTPUT projection (non-scale-invariant) the harm is direct output-mag
  growth, so an output-targeted structural fix may beat global wd — test against EDM2/MaP-DiT.
## L3b — Muon family & DiT fix
### [2608.02502 CMuon, Chen/Sun/Yuan, PKU/Westlake]
- Muon on DiTs → LATE-STAGE convergence plateaus. Root cause: DiTs fuse functionally-distinct weights
  (AdaLN scale/shift/gate α,γ,β + QKV) into single tensors; orthogonalizing the fused tensor = implicit
  SUBSPACE COUPLING → distorted update directions. Fix: chunk the fused matrices before NS5, orthogonalize
  each independently. 675M DiT: FID 1.18 ImageNet256 @200ep, >2× vs AdamW, kills the plateau.
- **FOR US:** confirms it. We have QKV chunking (`--fusion-split-qkv`); the missing piece is chunking the
  **AdaLN scale/shift/gate** projection. Retrofit-safe (optimizer-internal, never touches weights). Addresses
  CONVERGENCE/quality, ORTHOGONAL to the runaway. Low-risk adopt if we stay on Muon. (2× is vs AdamW baseline
  Part-I would call under-tuned — treat as "removes the plateau," not a literal 2×.)
### [2606.16899 Hyperball, Wen/Dang/Lyu/Ma/Liang, Stanford — the Part-I sequel]
- Motivation: Muon's edge over AdamW shrinks 30%→10% with scale UNDER constant decoupled wd. Hyperball keeps it.
- Mechanism (grounded from the method, not the abstract): wrapper that fixes ‖W‖_F AND ‖update‖_F to constants.
  **R = ‖W_0‖_F = the norm of the weights AT THE START OF THIS RUN**; each step W ← R·Normalize(W_updated).
  Theory: decoupled wd → equilibrium ‖W‖ set by HPs → wd really just sets the ANGULAR LR. Hyperball replaces
  that soft control with a hard constraint, decoupling magnitude from update direction. Result: Qwen3 ≤1.2B,
  Muon-Hyperball **20–30% speedup over wd baselines + BETTER LR transfer across width/depth.**
- **FOR US — this CORRECTS my earlier "retrofit-caveat" hedge, POSITIVELY:** R = ‖W_0‖ is the norm of the
  LOADED weights. For a FINE-TUNE, W_0 = the pretrained matrix → step 0 leaves W unchanged (it's already at
  its own norm) → **NO loss spike, retrofit-clean.** And it then PREVENTS the norm from growing → on the
  output projection this directly BOUNDS the output scale at the pretrained level = a structural cure for the
  drone, retrofit-safe. The one real subtlety = the L2 scale-invariance point: Hyperball is designed for
  scale-INVARIANT (normalized) layers where magnitude is "free"; the output proj is NOT scale-invariant, but
  since our target latent dist is ~unit-variance (≈ the pretrained regime), NOT adapting output scale is
  exactly what we want. So Hyperball fits our problem well. Also gives the LR-transfer we need for small→large.
- Net: Hyperball moves from "report-verified, caveated" to a STRONG paper-grounded candidate: retrofit-safe,
  bounds the runaway, drops wd tuning, better transfer — from the same group as the sober Part-I. [confirm the
  scale-invariance handling of non-normalized layers when reading EDM2/MaP-DiT.]
## L4 — clipping                 [PENDING: 2502.11034 AdaGC]
## ⚠️ AUTHOR GROUND-TRUTH (Zach Evans, SA Discord, relayed by Kim 2026-08-11) — CORRECTS the below
1. "Orthogonal updates only make sense for 2D matrices, hence norm layers and biases done with AdamW." =>
   the SA3 split is DIMENSIONALITY-based (2D→Muon, 1D→AdamW), which FusionOpt ALREADY does. The output proj
   is 2D → by this rule it was on MUON in SA3, NOT AdamW. So my "force_scalar the output to MATCH SA3" leg
   (below) is WRONG — it was an over-read of the paraphrased paper note. force_scalar-output survives only as
   a weaker "canonical-Muon-is-hidden-layers-only" hypothesis (Jordan excludes output/embeddings), NOT as
   "SA3's recipe." Demote it to a test-worthy arm, not the headline.
2. "I didn't discover Muon until later; we started with AdamW for MOST of pre-training, used Muon once we
   started variable-length training." => **SA3-base is overwhelmingly AdamW-shaped; Muon was a LATE, BRIEF
   finish.** Our full-FT runs Muon from step 0, at length, on AdamW-shaped weights, weak decay → SUSTAINED
   orthogonalized updates → runaway. SA3 never hit it (short/late Muon). AdamW full-FT is the faithful
   continuation of how the base was built AND has no runaway.
3. (Zach, more) "optimizer work is nebulous — so many HPs to search, hard to tell if a gain is your change or
   the randomness of a new training run." => METHODOLOGICAL WARNING for our sweep: the RUNAWAY-bounding signal
   is huge/unambiguous (std ~1 vs inf) — read it confidently. But FINE quality/creativity rankings among the
   BOUNDED arms are seed-sensitive at n=1/arm on the small AVP set — DON'T over-read single-seed deltas; use
   Kim's ears + replicate the top 1-2 arms on fresh seeds before declaring a winner (two-stage: sweep→replicate).
4. (Zach, the REBALANCER) "switched to Muon mostly for VRAM savings on larger models, but also noticed
   Muon-trained models seemed MORE CREATIVE." => this RE-OPENS the AdamW-vs-Muon call — it is NOT a slam-dunk
   for AdamW: Muon has (a) smaller optimizer state = VRAM win that matters for SCALING, (b) a qualitative
   CREATIVITY edge Zach observed — exactly what Kim weights, judging on his own music. So the sweep's real job
   shifts from "which bounds the runaway" (all the fixed arms will) to **"does fixed-Muon (wd0.1 / hyperball /
   surgical) sound MORE CREATIVE than well-tuned AdamW on Kim's music?"** — Kim's ears are the arbiter.
REVISED RANK (post all Zach input): the runaway is solved several ways; the CHOICE among bounded recipes is now
a CREATIVITY/quality call, not a safety one. adamw_fair = the safe, faithful, no-runaway baseline; fixed-Muon
(wd0.1, then hyperball/surgical) = genuine contenders that may WIN on creativity + VRAM. Let Kim's ear on the
AVP cells decide; the latent-std table only screens OUT the unbounded ones. Don't crown a fine winner off one seed.

## ⭐ EMERGENT HYPOTHESIS (SUPERSEDED by the Zach note above — kept for the record) — from the SA3 report
SA3-BASE was pretrained with **Muon on QKV/FFN projections, AdamW ELSEWHERE** (papers/arxiv-2605.17991.md:38).
"Elsewhere" = norms, embeddings, AND — critically — the **output projection + AdaLN modulation**. Our
FusionOpt full-FT routes EVERY 2D matrix with min(shape)≥128 to the Muon/spectral path
(build_fusion_param_groups) — which SWEEPS THE OUTPUT PROJECTION AND AdaLN INTO MUON, exactly the layers
SA3-base deliberately kept on AdamW, and exactly the non-scale-invariant layers where the drone lives (L2).
=> STRONG, CHEAP, PRINCIPLED FIX CANDIDATE: use FusionOpt's `force_scalar` regex to route the final output
projection (+ AdaLN scale/shift/gate) to the SCALAR/AdamW path (decoupled wd), matching SA3-base's own split.
This (a) matches the recipe the base was trained under (no OOD optimizer on those layers), (b) addresses the
non-scale-invariant output layer with AdamW's normal decoupled decay instead of raw NS5 orthogonalization,
(c) converges with CMuon (special-case the fused AdaLN/QKV), Hyperball/SFWN (exclude/normalize the output),
and the output-std penalty — ALL FOUR independently say: the output proj + AdaLN need bounded/normal
treatment, NOT unconstrained Muon. Add as an A/B arm: `force_scalar=[<final_proj>, <adaLN_mod>]`. VERY cheap
(a config regex), retrofit-safe. ALSO: chase whether the SA3 report states the base Muon's wd value — match it.

## L5 — architectural magnitude preservation
### [2303.06296 σReparam, Zhai et al., Apple 2023]
- Diagnoses ATTENTION ENTROPY COLLAPSE (low entropy → instability/divergence). Fix: reparam every linear as
  γ·W/σ(W) (spectral norm + learned scalar γ). Bounds the layer's Lipschitz constant. Enables ViT w/o
  warmup/wd/LN/adaptive-opt. Retrofit-safe (γ init = pretrained σ(W) → step-0 identity).
- FOR US: bounds SPECTRAL norm (largest SV) → good for the attention-entropy failure, adjacent to but NOT
  identical to our output-SCALE runaway (which is Frobenius/total-energy, better matched by Hyperball/EDM2).
  A safeguard arm, not the primary drone cure.
### [2312.02696 EDM2, Karras et al., NVIDIA 2024] — NAMES OUR PATHOLOGY
- "Uncontrolled magnitude changes and imbalances in both network ACTIVATIONS and WEIGHTS over training" in
  ADM → redesign layers to preserve activation/weight/update magnitude on expectation (forced weight-norm +
  MP-SiLU/MP-sum). FID 2.41→1.81 ImageNet512. + post-hoc EMA. This IS our drone, diagnosed + cured (from
  scratch). Frobenius-family (magnitude/energy) → the right frame for output-scale.
### [2505.19122 MaP-DiT, Bill/PerezJensen/Anagnostidis/vonRütte, ETH 2025] — CLOSEST TO US
- Extends EDM2 mag-preservation to a DiT. Key: the denoising target is UNIT-magnitude noise → "implicitly
  defines a magnitude constraint on the model's outputs" that most DiTs DON'T enforce architecturally = our
  exact problem stated. MP design stabilizes w/o norm layers, FID −12.8%.
- **AdaLN IS THE STICKING POINT (converges with our SA3-split find):** "Karras's methods can't be directly
  applied — AdaLN scale/shift is the only way conditioning reaches the output"; AdaLN's SCALE is inherently
  magnitude-NON-preserving. Their fix = **Rotation Modulation** (condition via learned ROTATIONS, which are
  magnitude-preserving, instead of AdaLN scale) — competitive with AdaLN, −5.4% params. NOT retrofittable
  (changes the conditioning mechanism a pretrained model relies on), BUT its insight — AdaLN scale is a prime
  magnitude-drift source — IS actionable for us via force_scalar / bounding AdaLN (the retrofit-compatible
  version). Third independent pointer at "AdaLN + output proj need special handling."
## L6 — objective-side
### [2605.27102 JLT: Clean-Latent Prediction, Fu et al.] — the x0 lever, ties to our #59
- Q: does predicting the CLEAN LATENT (x0) beat velocity/noise prediction even in a compressed latent space?
  (JiT showed clean images sit near a low-dim manifold; noise/velocity targets carry ambient off-manifold
  components; predicting clean lets the transformer focus on structured variation.) Compares JLT (clean) vs
  DiT (velocity) on a fixed FLUX.2 VAE, matched 130M.
- FOR US: the velocity target's ambient/isotropic component is exactly what pressures the model to inflate
  output-projection weights on low-variance directions (the runaway's objective-side driver). **Predicting x0
  removes that burden.** For our PRETRAINED velocity model, the retrofit-compatible form = an **x0-space loss
  weight** (σ²-weighted v-loss ≡ x0-MSE) — which IS our dormant x0equiv thread (#59, x0equiv_grid). JLT
  validates reviving it as the objective-side complement to the optimizer/architectural fixes.

## ⭐⭐ CONVERGENCE (L1–L6) — the answer is triangulating
FIVE independent sources now say the SAME thing: **the output projection + AdaLN modulation are where the
magnitude runs away, and they need bounded/normal treatment, not unconstrained Muon orthogonalization:**
  (1) SA3's own recipe (Muon on QKV/FFN, AdamW ELSEWHERE incl output/AdaLN);
  (2) rotational-equilibrium/Hyperball (scale-invariance holds for hidden layers, NOT the output proj);
  (3) MaP-DiT (AdaLN scale is the non-magnitude-preserving culprit);
  (4) EDM2 (control weight+activation magnitude, esp. at the output);
  (5) the output-std penalty & SFWN (target the output layer directly).
THREE complementary, retrofit-safe fix families, cheapest first:
  A. ROUTING (cheapest, matches SA3-base): FusionOpt `force_scalar` the output proj + AdaLN → AdamW path.
  B. STRUCTURAL: Hyperball-fix-norm or EDM2/SFWN forced-weight-norm on the output proj (learnable scalar
     init = pretrained norm → retrofit-clean). Hyperball also gives LR-transfer + drops wd tuning.
  C. OBJECTIVE: x0-space loss weighting (revive x0equiv, #59) — removes the isotropic driver.
Plus orthogonal quality/safety adds: CMuon (chunk AdaLN/QKV, kills late plateau), σReparam (attention-entropy
safeguard), AdaGC (adaptive clip). And the STRATEGIC prior (Part I): a fairly-tuned AdamW full-FT may make
most of this moot at 1.4B — test `adamw_fair` first.

## L4 — clipping [2502.11034 AdaGC, PaddlePaddle]
- Loss spikes = confluence (data outliers, HW faults, precision, HPs) → abnormal grads contaminate Adam
  1st/2nd moments. AdaGC = per-tensor clip relative to a tensor-wise EMA of historical CLIPPED grad norms.
  Optimizer-agnostic, tiny memory, device-local (less comm than GlobalGC), composes with Muon/Lion. Llama-2
  7B / Mixtral / ERNIE: spike score → 0, +1.3–2.5% downstream vs GlobalGC.
- FOR US: the clip to adopt (per-tensor EMA-relative, device-local = good for AMD DDP, Muon-compatible). BUT
  it targets transient SPIKES, not sustained DRIFT — our drone is drift, so AdaGC is a robustness ADD, not the
  cure. Keep a good clip regardless (both EDM2/NFNets lit agree clipping stays even with mag-preservation).

## L7 — context [2506.08210 Decoder-Only LLMs for T2I, Wang/Ge/Karras/Liu/Balaji, UW/UMD/NVIDIA]
- OUT OF SCOPE for the drone (it's about TEXT ENCODERS for T2I, not optimizer/magnitude). Finding: last-layer
  LLM embeddings (the de-facto conditioning) are INFERIOR; **layer-normalized averaging across ALL layers**
  markedly improves complex-prompt alignment; most decoder-only LLMs beat T5.
- SEPARATE LEAD worth banking (not drone): SA3 conditions on T5-Gemma — if it uses last-layer embeddings, a
  layer-averaged-embedding conditioning could improve PROMPT ADHERENCE. A distinct research thread; flag, don't
  chase now. (Karras co-authors — same group as EDM2.)

## ⭐⭐⭐ FINAL LOCKED RECOMMENDATION (all 12 papers read, paper-grounded)
Corrects the Gemini reports (which over-weighted Hyperball/CMuon and MISSED the routing fix + the
adamw-first framing). Priority, cheapest/highest-prior first:
- **ROUND 1 (cheap, test the priors):**
  (a) `adamw_fair` — fairly-tuned AdamW full-FT (own LR ~2e-4). Part I: Muon only ~1.1× at 1.4B, and AdamW
      has no runaway. If it just works, most of the rest is moot.
  (b) `force_scalar_output` — Muon on QKV/FFN, AdamW (scalar path) on OUTPUT PROJ + AdaLN. MATCHES SA3-base's
      own recipe; 5-source-convergent; a one-line config regex; retrofit-safe.
  Both vs `wd0.1` (fusion) + `anchor` controls.
- **ROUND 2 (elegant, if Round 1 leaves detail on the table):**
  (c) Hyperball wrapper (fix ‖W‖=pretrained-norm; retrofit-clean; drops wd tuning; better LR transfer).
  (d) x0-space loss weighting = revive #59 x0equiv (objective-side; removes the isotropic driver — JLT).
  (e) SFWN forced-weight-norm on the output proj (learnable scalar init = pretrained norm).
- **ORTHOGONAL ADDS (quality/robustness, any time):** CMuon (chunk AdaLN/QKV → kills late plateau),
  AdaGC (per-tensor clip), σReparam (attention-entropy safeguard).
- **SKIP for a fine-tune (from-scratch only):** MaP-DiT rotation-modulation, nGPT, MP-SiLU/MP-sum, NFNets WS.
- **Gate on quality, not just the z0-std number:** every fix must bound the runaway AND retain fine detail
  ≥ the wd baseline (Kim's ears + disintegration DSP) — the whole reason we're avoiding blunt global wd.
