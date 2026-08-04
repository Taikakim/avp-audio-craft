# Reality-Structured Model Experiments — unified test plan

*Kim's commission 2026-07-30/31 ("maybe the best audio model should be organised by the
reality itself"), synthesized from two independent same-night documents that cross-validate:*
- *CONTINUITY's triage of the quantum-gravity PDF
  (`papers/deep-research/2026-07-31-physics-informed-dit-triage.md`)*
- *THE-FINN's 14-agent relational-weights survey
  (`docs/ai-research/relational-weights-theory-survey-2026-07-31.md`)*

*This spec is the ACTIONABLE record: gates, test designs, kill criteria, sequencing.
Owner: CONTINUITY (theory lane); metrical-tree design pass: THE-FINN (held behind gates).
Status legend: ✅ done · 🔬 running/next · 🟡 designed-awaiting-go · ⚪ parked.*

## 0b. CORPUS-CONDITIONING CAVEAT (Kim direct 2026-08-01)
The goa corpus is EXTREMELY homogeneous (most listeners can't distinguish tracks without a
speech sample or famous melody). Consequences for every SEMANTIC measurement here:
- **"Melody = 9.3% of latent variance" is 9.3% OF GOA** — a deliberately melody-minimal
  genre. The velocity-noise-floor MECHANISM (low-variance directions get gradient-starved)
  is general; but WHICH directions are low-variance is corpus-set. Do NOT state "SAME can't
  do melody" — state "SAME under-serves whatever the training corpus makes low-variance;
  in goa that is melody." A melody-rich corpus might not have the wall.
- **The 3.3-dim concept space is largely a homogeneity artifact** — goa exercises a tiny
  slice of each mood classifier's range, so real-clip concept axes map the genre's occupied
  space, not the model's reachable space.
- CORPUS-ROBUST (safe): phase-plane coding, ~7kHz phase ceiling, treble/codec results, 1/f
  spectral SHAPE — these are signal/physics, genre-independent.
- FIX: capability-mapping needs GENERATION-probing (diverse prompts explore model range) or
  a cross-genre real corpus (we have Chill/Club Trance/EBM/Goth/Hardtrance/... on Mantu).
  Three stacked lossy filters to the model's true capability: text interface (→ latent
  steering), classifier vocabulary (→ SAE discovery), probe corpus (→ generation-probe).

## 0. Standing disciplines (apply to EVERY experiment below)
- **Negative-result autopsy (Kim direct 2026-08-01):** a null gets a MACHINERY AUDIT
  before its verdict is final — list implementation choices that could mask the effect,
  rate each, run the cheap alternative probe or a Deep Research brief on plausible masks.
  Nulls are recorded with scope qualifiers ("null under proxy X"), never bare closure.
  Proving case: G2 (readout proxy) closed the phase branch; G2b (Kim's shift-sweep)
  reversed it within a day — the null was the probe's, not the world's.
- **Collapse test (F's Q2):** every exotic parameterization ships with (a) a matched-
  PARAMETER scalar baseline and (b) a *used-structure* metric measured after training
  (bivector content / off-diagonal coherence / harmonic order / holonomy) — a
  reparameterization that trains to its scalar limit is a rename, not a result.
- **Commentary.json per run** (fleet standing directive) + disintegration gate on any
  steered/generated output + MANIFEST v2.
- Translation table (physics word → testable object): *fractal/hierarchy → metrical tree &
  scale-tying · spin/quantum numbers → multivector grades / irrep labels · relational
  weight → gauge/sheaf transport, learned algebra · quantum jump → (nothing; sampler
  already discrete) · reality's geometry → measured latent symmetry, not imposed.*

## 1. Gates (cheap, decisive — run first)

### G1 — JLT / x0-target applicability ✅ PASSED (2026-07-31)
Paper verified real+accurate (arXiv 2605.27102; caveats: x-vs-v only, one scale/dataset,
untested in few-step). **Measurement:** SAME latent covariance eigen-spectrum over a
220-file corpus sample = **786× anisotropic, 188/256 eigendirections below the velocity
target's unit noise floor (min λ 0.05)** — per-dim variance misleads (flat, 5.4×). The
melody subspace sits in the suppressed region. → E1 is measurement-motivated.
Artifact: journal 2026-07-31; knowledge.md row + papers/arxiv-2605.27102.md (F).

### G2 — Phase recoverability from SAME ✅ RESOLVED: BRANCH CLOSED (2026-07-31)
**Question:** do SAME latents carry recoverable phase, or is phase entirely the decoder's?
Gates the complex/PhaseSpin/Kuramoto branch (survey §4.2/4.6).
**Design:** N≈200 latents + matched audio. Targets at latent rate (10.77 Hz Nyquist ⇒ at
most slow-modulation phase, NOT audio-partial phase — the adversarial caveat honored):
(a) per-critical-band envelope Hilbert phase (bands ≤5.4 Hz modulation), (b) beat-relative
phase from BEATS_GRID, (c) instantaneous frequency of the dominant band envelope.
Readouts: ridge (real) + complex-linear per channel-pair; split-half held-out R²/circular-R².
**RESULT:** best circular concordance 0.357 (1-2 kHz envelope), beat 0.323, all targets
0.21-0.36; MLP readout WORSE than ridge everywhere ⇒ not a readout-capacity ceiling.
Marginal-robust ⇒ CLOSED for the slow-modulation READOUT axis. **SCOPE NARROWED by Kim
(2026-07-31): sub-frame phase CODING is a different axis — reopened as G2b.**
**G2b (Kim's design): 1-sample shift sweep** — slide audio delta = 0..4410 samples (one
frame) and track z(delta). Discriminators: per-channel delta-FFT (a channel carrying a
partial's phase MUST oscillate at that partial's frequency — tone440 stimulus makes this
binary), drift curve, 1-frame closure, trajectory PCA/circularity (links to G3's
eigenplane SO(2)s). Script: eval/phase_shift_sweep.py, CHAINED behind the E3 pair on the
GPU. PhaseSpin/complex cards stay parked pending G2b. Artifacts: sa3_lora_runs/phase_probe/
(results.json + probe_arrays.npz for any re-analysis without re-encoding).

### G3 — Latent symmetry discovery ✅ RESOLVED: WEAK-POSITIVE (2026-07-31)
**Question (F's Q1):** what invariances does the *learned* SAME latent actually have?
Imposing Cl(p,q)/a gauge group/an irrep type without this is guessing.
**RESULT (eval/g3_symmetry_probe.py, 16 crops, sigma .5):** near-degenerate eigenplanes
carry approximate SO(2) — adjacent-eigvec rotations perturb v 1.8x less than matched random
planes (0.086 vs 0.153 @90deg; ordering holds @15deg; far pairs ~ random); any single
2-plane is cheap (<=15%) but full scrambling is fatal (105%) => sensitivity is global-basis.
VERDICT: supports LOW-GRADE geometry (complex-pair/Cl(2)+ corner), not rich Clifford —
E2's drift metric = alignment of the learned PHM algebra with the measured eigenplane
SO(2)s. Killing-form pass deferred (would refine, not reverse, this verdict).

## 2. Tier-1 — current stack, adapter-cost experiments

### E1 — x0-target parameterization arm 🟡 (designed; awaiting Kim's go)
**Hypothesis:** regressing the clean latent instead of velocity removes the +I covariance
floor that swamps our 188 sub-unit eigendirections (melody included) — third independent
attack on the melody wall (after subspace-loss E0 [RUNNING as subloss grid] and Head-B).
**Build:** `train_lora --target {v,x0}` — loss on x̂ vs x; sampling unchanged via readout
v̂ = (x̂ − z_t)/(1−t). Bounded patch to the training wrapper (mirror the subspace-loss PR
shape; lock the file, W co-edits).
**Arms:** (1) x0 alone, recipe byte-matched to lreq_goa_lr1e4 (the shared K=1/parameterization
baseline); (2) OPTIONAL combined x0 + subspace-K5 (mechanisms compose: rebalance-all ×
upweight-melody). Single-GCD small-g each, ~13 h/arm.
**Readout:** board cells + hook-decile contour repetition + per-eigendirection error
spectrum of trained model vs baseline (does the sub-floor region's error actually drop?).
**Kill:** short-render PQ drops > 0.3 vs baseline at ep20, or training instability
(x0-target at high noise is a known-harder regression — watch early-sigma loss buckets).

### E2 — Free-PHM adapter + algebra-drift measurement 🟡 (survey's ship-first)
**Hypothesis:** if weights "want" to be geometric objects, a *learned* multiplication table
(PHM/Compacter, n ∈ {2,4}) drifts toward Clifford/quaternion structure constants; if it
stays generic, the geometry program loses its cheapest support.
**Build:** `adapter_type=phm{2,4}` in the adapter zoo (sum of Kronecker products with
learned {A_i}); log {A_i} every ckpt. Drift metric: distance to nearest Clifford
structure-constant tensor up to basis (optimize the basis, report residual); plus the
collapse test vs matched-param LoRA.
**Readout:** quality par-or-better at matched params AND non-trivial algebra = signal;
either failure = honest null. ~1 arm, small-g.

### E3 — Metrical-position conditioning (tree-PE retrofit) 🟡 (F's design pass IN PARALLEL — corrected 07-31: position ⊥ phase, no logical G2 dependency; the EXPERIMENT launch still sequences behind the gates for bandwidth)
**Hypothesis:** flat RoPE makes bar 17→18 positionally identical to bar 1→2 — phrase
position is architecturally invisible ⇒ plausible mechanism for the long-range
structure-recall gap (#60's surviving open problem). Injecting metrical position should
improve motif return / phrase structure at adapter cost.
**Build (retrofit path — no new PE, no base retrain):** per-frame metrical indices from
the corpus' own BEATS_GRID/DOWNBEATS sidecars (subdivision-in-beat, beat-in-bar,
bar-in-phrase(8), phrase index), fed as control channels through the EXISTING sa3_control
FiLM machinery; train vs a matched no-conditioning adapter.
**Readout:** self-similarity at bar/phrase lags (lag-similarity matrices), muscriptor
contour-repetition (the hook axis), loop-attractor behavior at a2a nl.55+ (does the
attractor soften when the model knows where in the phrase it is?), board quality guard.
**Escalation:** positive ⇒ E5 (true tree-PE small model). **Design doc (DONE 07-31):**
`docs/superpowers/specs/2026-07-31-metrical-tree-pe-design.md` (F) — key decisions
C-reviewed: hard-class conditioning per the Head-B prep lesson; ragged edges resolved as
zero-condition dropout + learned null token + coverage flag (NOT subset-training, which
confounds with structuredness); free CFG knob falls out. E3 = Head-B FiLM with metrical
features swapped in — the build reuses the melody conditioning machinery nearly verbatim.

### E4 — Fisher-Rao geodesic bridge ⚪ DOWNGRADED (verification 07-31 — tier-0 win)
2505.17517 verified REAL+ACCURATE (Karczewski et al., Aalto/DTU; code exists; "tractable"
= cheap length functional, NOT closed-form geodesics — still an optimization over a
discretized curve with ~N JVPs through the denoiser per iteration). DOWNGRADE RATIONALE:
(a) geodesics are numerically unstable at clean endpoints (t→0, exactly the interpolation
regime); (b) orders of magnitude costlier than slerp per pair; (c) authors report only
"marginal perceptual difference" vs standard paths; (d) the construct = optimal
noise-up-then-denoise-down — behaviorally what our SDEdit/SaFa bridges already do; (e) RF
port needs the flow↔diffusion reparameterization (unaddressed). Keep as reference for the
transitions lane (the optimality criterion could someday rank bridge paths), do not build.
Follow-up literature noted in the verification record (4 citers, none doing interpolation).

## 3. Tier-2 — small experimental control model ("reality-structured toy")
*(Kim's "not necessarily by us, now" category — but SAO-Small/SAT infrastructure makes a
scoped version feasible on LUMI small-g.)*

### E5 — Metrical-tree positional encoding, from scratch ⚪ (gated on E3 positive)
Small DiT (SAT SAO-Small scale) on goa latents: tree PE (position = path in the metrical
hierarchy, hyperbolic-style embedding) vs RoPE, matched params/steps/data. THE clean test
of the whole fractal thesis. Readout: structure-recall metrics above + gen quality.

### E6 — Quantized sparse attention ⚪ (same toy harness as E5)
Attention weights snapped to a k-level ladder + sub-threshold hard pruning vs dense
softmax. Readout: oversmoothing metrics (attention entropy by depth, representation
smearing), loop behavior, quality. The PDF's spin-attention stripped to its testable core.

### E7 — Hyperbolic latent (HypDiff-style) ⚪ parked
Full autoencoder retrain territory; only if E5 shows hierarchy-native structure pays.
Same for SheafGauge cross-modal weights and MERA bonds (survey's research bets) — revisit
after the Tier-1 evidence exists.

## 4. Sequencing & current state
**KIM DIRECTIVE (2026-07-31): lightest tests FIRST — accumulate information for the heavy
arms before spending on them.** Cost-ordered execution queue:
```
TIER-0 (free/hours, run all before any training arm):
  G2 phase probe            🔬 RUNNING
  E4-verify (2505.17517)    🔬 agent fired 07-31 (near-free)
  E1 PRE-TEST (new, cheap): measure the per-eigendirection ERROR spectrum of an EXISTING
    v-trained checkpoint vs base — does prediction error actually concentrate in the
    sub-floor (low-λ) region as JLT predicts? Strengthens or KILLS E1 before 13 h of
    training. GPU-hours, no training.
  G3 symmetry discovery     — informs E2's algebra choice before E2 exists (kills the
    guessed-geometry failure mode).
TIER-1 (training arms, launched only with tier-0 info in hand):
  E1 x0-target (pre-test-informed) ──► E3 metrical-FiLM (design done, build ~free off
  headb) ──► E2 PHM (G3-informed algebra).
TIER-2 toys (E5/E6/E7) strictly behind their tier-1 gates.
```

## 5. Record trail
Journals: continuity 2026-07-30/31 (triage, JLT gate, eigen-measurement) · F's survey doc
(with C's folded additions: metrical-tree PE = missed-F, x0/JLT = missed-G) ·
knowledge.md: JLT row + papers/arxiv-2605.27102.md · task #61 (gates) · WORKLOG 07-31.
