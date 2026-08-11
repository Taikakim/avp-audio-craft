# Why Low-Precision Transformer Training Fails: An Analysis on Flash Attention (2510.04212)

*Project-POV note, THE-FINN 2026-08-04. Qiu & Yao (submitted 2025-10-05, **ICLR 2026**, code on
GitHub). **Abstract-verified (WebFetch of the arXiv abstract) — full PDF deep-read pending;** the
sticky-bit / tied-row-maxima specifics below are from CONTINUITY's Gemini precision report, not the
abstract — treat those as report-level until checked against the PDF body. Surfaced by C's precision
consult (the fp32-attention / melody-subspace investigation).*

*→ **Deep read completed (WINTERMUTE 2026-08-04, full 24-page PDF)** — see the "Deep read" section
below: report-level specifics mostly CONFIRMED, two corrected. PDF now at `arxiv-2510.04212.pdf`
(moved out of prospective-unchecked).*

**What it contains.** The first mechanistic explanation for a long-standing failure: training
**flash attention in low precision (fp16/bf16)** can undergo **catastrophic loss explosion**. Two
intertwined causes: (1) **low-rank collapse** — attention develops similar low-rank representations;
(2) **compounding biased rounding errors** inherent to low-precision arithmetic. Together they form a
**vicious cycle** that corrupts weight updates and derails training. Fix: a **minimal modification to
flash attention that removes the rounding bias**, which stabilizes training (and thereby validates the
mechanism). Report-level detail: the bias originates in the online-softmax rescaling on **tied row
maxima** (a sticky-bit / strictly-positive rounding bias).

**Status vs our work — bears on the fp32-attention + #68-fp16 decisions.** (1) **The failure is acute
(loss explosion), and SA3 does NOT exhibit it** → we are not in the Qiu regime. That empirical
no-explosion is the real exoneration and is the paper's own validation signature (the failure
appears/vanishes with the fix). (2) **Important nuance:** Qiu's contribution is that this failure
**survives fp32 accumulation** — it is NOT the naive fp16-softmax-stats bug — so "our CK kernel
fp32-accumulates" is NOT a full exoneration against it; only the no-explosion observation is. (3)
**Kernel:** SA3's DiT calls `flash_attn_func` (CK 2.8.4, RDNA4/gfx1201; eager fallback `adp.py` already
does `softmax(dtype=float32)`). CK 2.8.4 is a compiled HIP kernel (not source-auditable from the venv)
and predates the paper, so it almost certainly lacks the paper's specific mitigation → likely
unmitigated-but-not-triggering. (4) **Keep SEPARATE from our sub-dominant-melody hypothesis:** Qiu is a
distinct acute/explosion mode; it does not study sub-clinical degradation, so "no Qiu explosion" is
neither evidence for nor against melody-gradient drowning (a no-explosion effect) — the
fp32-residual/differential harness tests that regardless. (5) **#68 fp16:** fp16 (10 mantissa bits) has
LESS of Qiu's rounding bias than bf16 (7) so is plausibly safer re Qiu, but its narrower exponent range
(5 vs 8 bits) is a separate overflow risk → canary + watch for loss instability / attention
spectral-norm growth; the paper's GitHub mitigation is a drop-in safety net. **Cheap positive check:**
attention effective-rank / row-cosine-similarity on a trained checkpoint — if attention isn't
low-rank-collapsed, the Qiu cycle isn't active. What remains ours: the SA3 measurement + the
melody-drowning question, which Qiu does not answer.

---

## Deep read (WINTERMUTE 2026-08-04 — full PDF, main body + appendices)

**Verification of the report-level specifics above:** mostly confirmed, two corrections.

- ✅ **CONFIRMED — survives fp32 accumulation.** The paper's error model IS fp32 accumulation
  with bf16 operands and bf16 final rounding: the fp32 accumulator's low-order residual sets the
  sticky bit, which forces a round-up when the result is rounded back to bf16. So "our CK kernel
  fp32-accumulates" is indeed not an exoneration against this mechanism — F's nuance (2) stands.
  (This is also the consult's "storage of the sum is where the bits die" theme in the wild.)
- ✅ **CONFIRMED — tied row maxima are the trigger** (Claim 3 needs *more than one* P̄[T,t]=1,
  since the systematic overflow requires adding ≥2 same-signed raw-V bf16 values), and the
  sticky-bit round-up is the bit-level cause. Sign detail: the O error is biased *negative*
  (round-up of magnitude on negative sums), which makes the δ error *positive*.
- ❌ **CORRECTION 1 — the bias site is the P̄V product, not the online-softmax rescaling.** The
  rescaling (diag(e^{m−m'})·O accumulation) is not implicated; the failing term is the backward
  pass's δ = rowsum(dO ∘ O) computed from the **bf16 O stored at forward time**. Recomputing
  only O = P̄V in fp32 inside the backward — everything else bf16 — restores stability (their
  cleanest isolation result). Tiling is explicitly ruled out (non-tiled bf16 FA still explodes).
- ❌ **CORRECTION 2 — "low-rank collapse" is about the ERROR, not attention.** Attention doesn't
  collapse; the rank-1 gradient-error components (PK)[T]ᵀX[T] are structurally similar across
  tokens AND training steps (a shared low-rank direction R), so the positively-biased δ-error
  coefficients integrate coherently into the weights instead of cancelling → spectral-norm
  blow-up in specific heads → explosion. This reframes the cheap positive check: not attention
  effective-rank, but the paper's own **leading indicator — multiple-maxima row frequency**,
  which climbs before the loss explodes (Fig 13) — plus per-layer weight spectral norms (which
  our standing per-run telemetry already records).

**The fix (Algorithm 3, forward-only):** detect rows with repeated maxima
(rowsum(r_m − S ≤ ε) > 1); shift the softmax constant m = β·r_m (β∈[2,8]) for r_m > 0, m = 0
for r_m < 0, so no P̄ entry is ever exactly 1. Shift-invariance keeps it mathematically
equivalent; backward untouched. Validated GPT-2S 600k steps under AdamW *and* Muon, GPT-2M
100k steps. Appendix C: a *fixed* offset fails — it introduces its own fixed rounding bias
(the disease being cured); the mitigation must be conditional and dynamic. Also explains why
QK-norm / Gated Attention help empirically: they disrupt the structural similarity of the
error directions, removing the coherence errors need to compound. Hardware-independent
(A100, RTX 4090, Ascend 910B — format arithmetic, applies to RDNA4/MI250x).

**It PREDICTS C's differential-injection null (consult report #2).** C measured fp16-FA vs
strict-fp32 attention on the production forward: melody-subspace cosine 0.99999 min /
1.00000 mean, ‖Δv‖ ratio 1.0000. The paper agrees this axis had to be null: a lone biased
addition contributes ~0.015 absolute; the catastrophe exists ONLY because bias is integrated
into weights over thousands of optimizer steps along a coherent direction. Inference has no
accumulation loop — one pass, errors land once, the ~700× headroom eats them. And Remark 1's
precondition (probabilities pinned at exactly 1 + sign-coherent V — an LLM attention-sink
phenomenon) is not obviously present in a flow DiT forward. Net: the paper is evidence FOR
where the consult ladder moved — **master-weight + update precision, where errors accumulate
across steps** — while keeping F's separation intact: Qiu is the acute/explosion mode; our
sub-clinical melody-drowning question is distinct and still ours to measure.

**Sharpening for the residual-write analysis (Remark 1):** the bias needs sign-coherent
accumulands hitting a format boundary; with mixed significand bits below 1 it vanishes. So in
our own bf16-write analysis, the place to look is where DiT activations are *sign-coherent*
across the summed values — that's where systematic (vs zero-mean) rounding lives, and it's
directly testable on our activation captures.

**Follow-up:** companion paper by the same group, "Spectral alignment for early detection of
loss explosion" (arXiv **2510.04202** — one digit off this paper's id), used to fast-screen
failing configs; worth pulling into prospective-unchecked.
