# UltraViCo — Breaking Extrapolation Limits in Video Diffusion Transformers (2511.20123)

*Project-POV abstract, THE-FINN 2026-07-30 (subagent deep-read). ICLR 2026 (Zhao, Zhu et al.;
Tsinghua/ShengShu/RUC/UT-Austin/Princeton). Video, but it hands us a **concrete, testable
mechanism + diagnostic for loop-collapse** — the most actionable lead in the whole sprint.*

**What it contains.** Video **length extrapolation**: make a pretrained DiT generate longer than its
trained length L in one forward pass. Both failure modes (general quality degradation; special-case
periodic *repetition*) share one root cause: **attention dispersion** — tokens beyond the training
window dilute learned attention. The repetition special case is proven (Prop. 1) to arise when
**RoPE frequencies form harmonics** (φ_i/φ_{N-1} ∈ ℕ⁺): the dominant frequency + harmonics accumulate
amplitude → **periodic attention at alignment positions mT** → periodic output. Fix **UltraViCo**
(training-free): multiply out-of-window *positive* attention logits by a constant decay α<1 (in-window
pairs stay 1), plus a stronger decay β<α at the harmonic positions mT — softmax renormalization
re-sharpens attention onto the trained window. Extends the practical limit 2×→4×; +233% dynamics /
+40% quality at 4×; **decay *shape* barely matters** (constant≈linear≈parabolic) — only in- vs
out-of-window distinction does; α=0.9, β=0.6 robust. **Orthogonal to** sliding-window/FIFO/FreeNoise
(stacks on top, +consistency at 6×). Diagnostic: looping model had one RoPE frequency = **79.6%** of
attention amplitude vs **31.6%** in the non-looping model.

**Status vs our work — a testable loop-collapse experiment, not just a citation.** The **harmonic-RoPE
→ periodic-attention → periodic-output chain directly names a candidate mechanism for SA3
loop-collapse**, and RF-vs-diffusion is *irrelevant* to it — this is attention/RoPE geometry inside
the transformer, shared by our MM-DiT. **Concrete lead for the fleet (worth a probe):** compute SA3's
statistical row-wise temporal-attention pattern S̄(Δt) and check whether **one frequency dominates
the amplitude** (their 79.6%-vs-31.6% split) — a *measurable predictor* of whether a checkpoint will
loop. If yes, the **training-free attention-concentration fix** (down-scale out-of-window logits;
stronger suppression at the loop period) is a candidate cure that preserves long-range musical
structure (the two-tier α/β is exactly "kill the loop without flattening form"), and it's **additive**
to any windowed long-form scheme we run. What does NOT transfer (honest): (a) their evidence is 3D
M-RoPE (d_T/d_H/d_W); SA3 is **1D-temporal**, so the harmonic analysis must be redone on SA3's actual
frequencies (harmonic alignment is model-specific — their Wan model showed *none*); (b) every metric
is visual, no audio analog — audio dispersion may show as timbral smearing/transient loss, needs its
own meter; (c) whether RF's straighter trajectories change how dispersion accumulates over steps is
untested. Treat the harmonic hypothesis as a **testable lead, not a confirmed result** — but it's the
cheapest loop-collapse experiment on the table (a diagnostic, no retraining). What remains ours: the
SA3 harmonic measurement, an audio dispersion metric, and the disintegration gate.
