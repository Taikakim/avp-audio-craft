# Melody turning via frame-level chroma steering — feasibility probe (2026-07-22)

**Ask (Kim direct):** "try to turn melodies to different ones with frame level chroma
steering." Can per-frame 12-d chroma targets, run through the existing LatCH
`target_raw` guidance stack, (A) impose a target melody on free generation and
(B) turn a source melody into a different one during SDEdit a2a?

**Verdict: NO — training-free frame-level chroma steering does not turn melodies at
the proven gain band (1536–2048).** Guidance authority is at the slow-harmonic-tint
level (consistent with the 07-19 chroma_steer grid's Δcos12 ≈ +0.03 @ g2048), roughly
an order of magnitude short of flipping per-frame pitch classes against either the
prompt prior (arm A) or an SDEdit source anchor (arm B). All 26 renders pass the
disintegration gate — we were nowhere near the authority ceiling; the head simply
isn't steering pitch at frame granularity.

## Setup
- Ground truth: `eval/musicology/test_midis` frame-locked patterns (BPM 161.499,
  one 16th == one latent frame @ 10.7666 fps) → EXACT per-frame pitch-class targets.
  Source melody pat1 (E3 pedal), targets pat2 (E/G seesaw), pat3 (E-G-B-E arp),
  pat6 (E pedal + F trill, last 4 steps/bar).
- Target streams: one-hot pc per frame → 384-d 3-band SAME expansion (the exact
  `build_target_raw` recipe from `eval/chroma_steer_render.py`), 256 frames (23.78 s).
- Heads: `latch_sa3_same_chroma_best.pt` (strongest measured chroma head) + 2-cell
  side-arm with the stem `chroma_other` head (the chroma-morph head). `hpcp` omitted
  (measured ~dead in the 07-19 grid). Cosine loss, rho=mu=gain, steps 24, cfg 7.
- Arms: **A** free gen (goa prompt) + target stream, gains {1536,2048} × seeds
  {1234,5678} + unguided baselines; **B** SDEdit from `pat1__sawlead` render,
  nl {0.45,0.6} × gains {1536,2048}, targets {pat2,pat6}; **Bx** chroma_other @
  nl0.6/g2048; **C** SDEdit control, no guidance. 26 renders, z0 saved per render.
- Verification: muscriptor-medium transcription (cached `.mid`, `hook_scores_midi/`)
  → per-frame skyline pc vs target and source (±1-frame slop; **nonmodal** = frames
  off the pattern's modal pc, so an E-drone scores 0 on pat6's trill, and **disc** =
  frames where target ≠ source); plus a transcription-free per-frame chroma-cosine
  (CQT hop 4096 = exactly 10.7666 fps); plus `disintegration_metrics` gate vs the
  proper unguided baseline. Pipeline validated on the raw source render:
  coverage 0.996, source recovery **1.000**.

## Turn-rate table (compressed)

Arm A — free generation: target-adoption on the melody's moving part (nonmodal,
best global shift ±16 f), steered vs same-seed unguided null:

| target | gain | s1234 (null) | s5678 (null) | chroma Δ vs null |
|---|---|---|---|---|
| pat2 | 1536 | 0.07 (0.00) | 0.56 (0.32) | +0.01 / ±0.00 |
| pat2 | 2048 | 0.18 (0.00) | 0.56 (0.32) | +0.02 / ±0.00 |
| pat3 | 1536/2048 | 0.07–0.09 (0.07) | 0.28 (0.16) | +0.01 / ±0.00 |
| pat6 | 1536/2048 | 0.00 (0.00) | 0.00 (0.00) | −0.04…−0.03 |

→ No reliable adoption: lifts are seed-idiosyncratic and the chroma-level delta is
≤ +0.02. The output follows the PROMPT, not the stream.

Arm B/Bx — melody turning (disc frames; control arm C gives the empirical null):

| cell | adoption (null) | src retention | tgt chroma (null) | src chroma (ctl) | gate |
|---|---|---|---|---|---|
| B pat2 nl.45 g1536/2048 | 0.00 (—) | ~1 by chroma | 0.06 (0.06) | 0.92 (0.91) | clean |
| B pat2 nl.60 g1536 | 0.172 (**0.172**) | 0.78 | 0.156 (0.145) | 0.54 (0.57) | clean |
| B pat2 nl.60 g2048 | 0.172 (**0.172**) | 0.80 | 0.153 (0.145) | 0.55 (0.57) | clean |
| B pat6 nl.60 g1536/2048 | 0.00 (0.00) | 0.44 disc/0.71 all | 0.08–0.09 (0.09) | 0.44–0.45 (0.57) | clean |
| Bx pat2 nl.60 g2048 (chroma_other) | 0.203 (0.172) | 0.84 | 0.193 (0.145) | 0.64 | clean |
| Bx pat6 nl.60 g2048 (chroma_other) | 0.00 (0.00) | 0.83 | 0.135 (0.093) | 0.77 | clean |

→ At nl 0.45 the output IS the source (chroma cos 0.92; transcription coverage
collapses to 0–0.47 because SDEdit washes the attacks — the raw source itself
transcribes perfectly, so that collapse is an SDEdit artifact, not a metric bug).
At nl 0.6 the steered adoption **equals the unguided control's** (0.172 vs 0.172 on
pat2; 0.0 vs 0.0 on pat6). No cell shows target-adoption high + source-retention low.
**Turn rate: 0/12 steered a2a cells.** chroma_other edges same_chroma slightly
(+0.03 adoption, +0.05 chroma on pat2) — still noise-level.

- Gate failures: **none** (26/26 clean vs proper baselines).
- Best (gain, nl): none achieves a turn; least-bad = **chroma_other, g2048, nl 0.6**.
- Gain/nl effects: gain 1536→2048 changes nothing measurable (Δ ≤ 0.02 everywhere);
  nl 0.45→0.6 trades source fidelity for prompt drift, not for target adoption.

## What it implies for Head B

Training-free chroma steering does NOT already solve melody turning, so **Head B's
bar and role stand — and sharpen**: per-frame pitch control has to come from a
forward-conditioned path (the Tier-2 d384 chroma ADAPTER, todos.md:24-25, or a
Head-B-class control head), not from inference-time guidance on the current heads.
Guidance-only chroma steering remains useful strictly for slow harmonic coloration
(the chroma-morph niche). This probe hands Head B its acceptance harness for free:
the frame-locked target streams + adoption/retention/gate metrics in `chromaturn.py`
are exactly the pass/fail instrument ("turn = target-adoption high AND
source-retention low AND gate clean") that the adapter should be graded with.

**One unexhausted lever:** this probe stayed in the task-specified 1536–2048 band and
every cell was gate-clean, i.e. far from the disintegration ceiling. GHOST-NOTE's
07-19 wide-ladder finding (continuous heads keep moving monotonically to gain 8192)
suggests a 4096–8192 follow-up is cheap (~10 renders) — but extrapolating the
observed ≤+0.05 per-doubling chroma delta, even 8192 lands ~0.3 cos short of a turn.

## Files
- Renders + z0 sidecars: `renders/` (26 wav + 26 z0.npy)
- Per-cell metrics: `results.json`; transcriptions: `hook_scores_midi/`;
  hook stats: `hook_scores.jsonl`; provenance: `run_meta.json`
- Tooling: `chromaturn.py` (targets / render / analyze), `run_gpu_phase.sh`
- Prior art this reused: `eval/chroma_steer_render.py` (target_raw slot + 384-d
  expansion), `eval/hook_eval_renders.py` (muscriptor pattern),
  `eval/disintegration_metrics.py` (gate), `eval/musicology/test_midis/` (ground truth)

## GAIN-EXTENSION (coordinator follow-up, same day): g4096 + g8192

The one lever the base probe left unexhausted. 9 extra renders (arm Bext:
same_chroma, pat1→{pat2,pat6}, nl 0.6, gains {4096, 8192}, seeds {1234, 5678}
+ an s5678 control), same lock discipline, same analyze pass. Dose-response
across the full ladder (disc adoption; null = same-seed unguided control):

| target | seed | null | g1536 | g2048 | g4096 | g8192 | gates |
|---|---|---|---|---|---|---|---|
| pat2 | 1234 | 0.172 | 0.172 | 0.172 | 0.188 | 0.172 | all clean |
| pat2 | 5678 | 0.094 | — | — | 0.094 | 0.062 | **g4096 BLOWN (zcr)** |
| pat6 | 1234 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | all clean |
| pat6 | 5678 | 0.109 | — | — | 0.344 | 0.281 | **g4096 BLOWN (zcr)** |

- 3 of 4 (target, seed) combos: adoption ≈ null at every gain up to 8192 —
  **completely flat dose-response**.
- The one riser (pat6/s5678: 0.28–0.34 vs null 0.11) is a single-seed outlier,
  not a turn: source retention stays 0.78, source chroma (0.49–0.59) still
  dominates target chroma (0.32–0.34), and its g4096 sibling cells are the run's
  only gate failures.
- **Quality does NOT reliably survive to 8192 for this head** (contra the 07-19
  continuous-scalar-heads finding): zcr blowouts appear at g4096 on seed 5678
  (both targets), and the g8192 s5678 cells lose transcription coverage
  (0.98 → 0.82) — the guidance starts degrading note salience before it ever
  moves pitch.

**Extension verdict: outcome (a) — the training-free lane is CLOSED at all
reachable gains.** Above 2048 the gain buys disintegration risk, not melody
adoption. Head B (forward-conditioned per-frame pitch) is the only remaining
path; this harness is its acceptance instrument.
