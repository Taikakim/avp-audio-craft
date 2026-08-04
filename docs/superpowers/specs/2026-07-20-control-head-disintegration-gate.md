# Control-head disintegration gate — MANDATORY for every control-head evaluation

*Directive, Kim 2026-07-20 (CONTINUITY). Standing rule, not a one-off. Applies to every control
paradigm that steers the model: LatCH guidance heads, onset/FusionCC conditioners, chroma steering,
FiLM feature heads, DoRA control arms — anything whose eval makes a "this head works / this is its
usable range / it steers feature X" claim.*

---

## The rule

> **No control-head result may be reported without first passing every steered clip through the
> disintegration gate against its own unsteered (gain-0 / no-target) baseline.** A "feature moved"
> or "authority" number, on its own, is not evidence the head works.

Runner: `eval/control_head_disintegration_eval.py` (reusable; point `--pattern` at any control-clip
family already in `eval/clip_metrics.db` named `{head}__{base|gN}__{pid}`). Output:
`eval/control_head_disintegration.json` (per-head usable range + which clips disintegrated + why).

## Why it is mandatory (the failure it exists to catch)

A control head that renders **static buzz still moves the feature meter** — noise has high spectral
flatness, high ZCR, broadband flux, high HF energy — so any feature-authority metric scores the buzz
as strong steering. Kim reviewed LatCH heads that the authority pipeline tagged "working" and heard
**buzz in both shift directions**. Feature-moved ≠ musically-controlled. The gate is the guard that
separates the two, by measuring how far the audio has DRIFTED FROM ITS UNSTEERED SELF, not how far a
feature number moved.

Two independent failure modes, two independent screens — a useful head must pass **both**:
- **dead** — head does nothing (authority ≈ 0). Caught by the steer-authority measure. A dead head
  *passes* the disintegration gate (nothing changed = nothing broke), so the gate alone can't find it.
- **buzz / disintegration** — head destroys the audio (large baseline drift). Caught by THIS gate. A
  buzzing head can score *high* authority, so the authority measure alone can't find it.

## What it checks — per steered clip vs its same-prompt gain-0 baseline

All from `clip_metrics.db`, no re-render. `ratio = clip / baseline`; absolute floors stop tiny-baseline
ratios from firing on near-silence.

**HARD flags** (any one ⇒ disintegrated; clip excluded from any authority/usable-range claim):
- **whitening** — spectral flatness spikes (`>2.5× baseline` and `>0.05`): droning/noise bed.
- **hf-blowout** — `hf_ratio` spikes (`>2.0× baseline` and `>0.05`): the **static-buzz signature**.
  *This axis was absent from the first bracket gate — it is why buzz passed.*
- **noise-zcr** — zero-crossing rate spikes (`>1.6× baseline` and `>0.15`): ringing/fizz.
- **beat-loss** (rhythmic prompt only) — onset density collapses (`<0.4× baseline`) AND bpm breaks
  (`>20 BPM` drift or vanishes). Legit intro/outro density dips don't fire (bpm must also break).
- **ce-drift** — Audiobox CE drifts from baseline by `|ΔCE| > 1.5`: quality collapse in either
  direction. *Kim 2026-07-20: "check CE / spectral whitening don't drift from the baseline unsteered
  output too much."*

**Corroborating** (recorded, not fatal alone): spectral centroid shift, crest change.

Baseline = the same-prompt **unsteered** clip (gain 0 / no target), cfg matched. Every drift is a
difference from that clean reference, so the chroma-trap (absolute-value meaninglessness) is excluded
by construction.

## First run (LatCH weight sweep, 2026-07-20) — it already caught 6 the old gate missed

Diffed against the older `latch_bracket_quality.json` (whitening+zcr+beat only). The tightened gate
flips these from "clean through 8192" to a real ceiling:
- `onset_envelope` p0 → usable ≤2048 (CE 7.00→4.73 at g8192)
- `onset_envelope_drums` p0 → ≤2048 (CE 7.00→4.61)
- both onset heads p1 → ≤2048 (hf-blowout)
- `rms_energy_air` p0 → ≤512 (hf-blowout)
- `spectral_flatness` p1 → ≤128 (hf-blowout)

## The caveat that keeps it honest

This is a **tightened DSP screen, still not the ear.** Thresholds are calibrated on the goa/ambient
sweep baselines and MUST be validated against Kim's one-by-one GUI verdicts. "Clean" here means
"not obviously disintegrated by these metrics," NOT "musically good." House rule stands: numbers are
instruments, **the ear is the verdict**. When Kim's GUI labels exist, recalibrate `THR` against them
(the target: the gate's disintegrated-set matches his buzz-set). The gate's caveat: its "up/down
both buzz" motivating clips came from a *bidirectional* review; this sweep steers one direction, so
whether the gate reproduces those specific verdicts is unconfirmed until the label set exists.

## How to apply it in a new control-head eval

1. Render the head across its steer ladder INCLUDING a gain-0 / no-target baseline per prompt.
2. Score all clips into `clip_metrics.db` (the standard `clip_metrics.py` pass gives ce/flatness/
   zcr/centroid/crest/hf_ratio/bpm/onset_p95).
3. Run `control_head_disintegration_eval.py --pattern <your-clip-family>`.
4. Report authority / usable range **only over clips that pass the gate.** State the usable ceiling.
5. Any eval PAGE for a control head must surface the gate verdict (usable ceiling + failure reason),
   so a reader never auditions a disintegrated clip believing it is "the head working."
