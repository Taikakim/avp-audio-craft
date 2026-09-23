# Triage — "Scale-aware optimization of DoRA magnitude parameters" (Gemini)

> **Provenance.** Reply to `briefs/2026-09-23-dora-magnitude-sign-step-brief.md`, received 2026-09-24 as
> `Scale-aware optimization of DoRA magnitude parameters.docx`. Triage: CONTINUITY same day.
> **⚠ This is NOT the deep-research report itself.** Its own "Evidence boundary" says the body of the
> earlier deep-research answer "was not exposed in the retrievable conversation export", and the
> document was "generated from the recoverable conversation record" and "saved artifact metadata".
> So it is a second-hand reconstruction. Several rows say "not recovered". **If the original Gemini
> deep-research output can be exported, it supersedes this file.**

## Citation check (from our own knowledge of the literature; PDFs not re-read)

| method | source given | verdict |
|---|---|---|
| LARS trust ratio | You et al., arXiv 1708.03888 | **real**; rule (‖w‖/‖g‖ layerwise scaling) correctly stated |
| LAMB trust ratio | You et al., arXiv 1904.00962, Alg. 1 | **real**; rule correctly stated |
| Adafactor relative step | Shazeer & Stern, arXiv 1804.04235 | **real**; update scaled by max(ε₂, RMS(X)), correctly stated |
| Fromage | Bernstein et al., arXiv 2002.03432 | **real**; relative update + 1/√(1+η²) correction, correctly stated |
| Exponentiated gradient | Kivinen & Warmuth (1997) | **real** (the family); rule correctly stated |
| exp / log-space parameterisation | "not recovered" | standard technique; the multiplicative consequence it states is correct algebra |
| softplus parameterisation, "MD Decoupling" | name only, "not recovered" | **unverified**; do not rely on |
| TVLARS (time-varying trust ratio) | name only, "not recovered" | **unverified** as given |
| separate magnitude LR + late decay/freeze | "not recovered" | no source; it's our own proposal |
| decay toward initial value | "not found" | correctly reported as inference only |
| failure reports matching ours | "not found" | honest null |

The evidence standard held: nothing invented. The report found **no published source applying any of
these to DoRA magnitudes, diffusion, or sign-type optimizers**. Every transfer to our case is inference.

## What it gives us (usable)

Two separate properties, and the report is right that they solve different halves of the failure:
1. **Positivity**: the magnitude cannot cross zero. Via log-space parameterisation (m = exp(u)), or a
   floor/clamp as a last-line guard.
2. **Scale-relative step**: the step is proportional to the parameter's own size. Via LARS/LAMB/Fromage
   trust ratios, or Adafactor's RMS scaling.

For OUR sign group, both collapse into one small change (our inference, the algebra is exact):
a sign step on u = log m is **m ← m · exp(−η · sign(momentum))**. This is multiplicative, so relative to
|m|, and it keeps m > 0 forever. With η = 6e-4, that's at most 0.06% change per step. That's the
same for a 0.13 scalar as for a 2.4 scalar, which is exactly the property the failure lacked.

"Free early, then constrained" (Kim's idea) has **no source**. Implementable as a schedule on the
magnitude group's multiplier. It's a design choice to test, not a literature result.

## Recommendation
Build `--modular-magnitude-update {additive,multiplicative}` (default additive = current behaviour) on
params named `*.magnitude`, optionally with a floor. Test against the exact modules that broke
(to_global_embed.*, global_cond_embedder.0, to_timestep_embed.2) by re-running the goa3 recipe past
step 6900. Then, separately, an early-free magnitude schedule.
