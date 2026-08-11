# Head A ceiling — melody contour readout from SAME z0 of full goa mixes

**2026-07-23, overnight run (via subagent for CONTINUITY).** Question (spec
`docs/superpowers/specs/2026-07-22-melodic-latch-film.md` §0/§1/§8): how well can the
per-frame contour class stream be read MIX-NATIVE from clean SAME latents (z0) of real
corpus crops — the ceiling for a latent-space Head A, before any DiT activations.

## THE CEILING NUMBER

**Held-out macro-F1 0.273, balanced accuracy 0.280** (folded 8-label set: rest, pedal,
|1|,|2|,|3|,|5|,|7|,|12|; chance bacc = 0.125), best variant `mlp_ctx2`
(256→512 GELU→8, ±2-frame context), on an **ARTIST-DISJOINT split** (393 artists;
train/val/test = 2110/266/273 files, 319/35/39 artists, 0 files missing artist metadata —
the strong split was achieved, no artist leakage).

**This is LOW — below the 0.4 bar named in the tasking.** The plain reading: melody
contour is only weakly decodable by shallow readouts from mix z0. Latent-level contour
reading appears to need the DiT's processing — pushing Head A toward **activation taps
(L8–15) as the spec already planned**, not raw-latent probes. (Implication noted, not
chased tonight.)

Directional 14-label variant (needed for signed-interval gram mining): macro-F1 0.221,
bacc 0.234 (chance 0.071), same arch.

## Experiment log (all runs; no silent retries — full table also in results.json)

| variant | target | test bacc | test macro-F1 | note |
|---|---|---|---|---|
| lin_ctx0 | y8 | 0.172 | 0.166 | 2-ep smoke logged too (0.173/0.165) |
| lin_ctx1 | y8 | 0.163 | 0.165 | linear flat in context |
| lin_ctx2 | y8 | 0.179 | 0.173 | linear ceiling ≈0.17 |
| mlp_ctx1 | y8 | 0.273 | 0.274 | nonlinearity ≈ doubles linear |
| **mlp_ctx2** | y8 | **0.280** | **0.273** | **ceiling model** |
| mlp_ctx4 | y8 | 0.265 | 0.256 | context saturates at ±2 |
| mlp_ctx2 | y14 | 0.234 | 0.221 | directional (acceptance decoder) |
| mlp_ctx4 | y14 | 0.224 | 0.208 | |
| mlp_ctx2+t-cond | y8 | — | — | noise arm, t-curve below |
| mlp_ctx1 shift {0,±1,±2,±3} | y8 | 0.245 @s0 | — | alignment diag, 10-ep runs |
| mlp2_ctx2 hidden1024 | y8 | 0.278 | 0.273 | capacity probe: saturated |

**Alignment diagnostic** (global target shift, 10-epoch mlp_ctx1): s0 0.245, s−1 0.255,
s+1 0.212, s±2 ≈0.19–0.23, s±3 ≈0.19. Peak at −1 frame (+1 pt over s0) → alignment is
essentially correct (sub-frame offset at most); the quoted ceiling might be ~1 pt
conservative, and gross misalignment is ruled out as the explanation for the low number.

**Capacity probe**: deeper+wider MLP (2×1024) = identical macro-F1 (0.273) — the shallow
readout family is saturated on z0; more probe capacity is not the missing ingredient.

## Confusion structure (best folded model, artist-disjoint test)

Dominant failure is **lead presence, not move identity**: pedal→rest 0.45, every move
class →rest 0.24–0.36, moves→pedal 0.21–0.23. Within moves, small intervals survive best
(m1 recall 0.268, m2 0.229, m3 0.242) and large leaps worst (m5 0.129, m7 0.132,
m12 0.125). Rest recall 0.794. Confident-frames-only (target weight ≥0.6) barely helps
(bacc 0.283 vs 0.280) — boundary-frame softness is NOT the limiter.

## Noise robustness (guidance-usability curve)

z_t = (1−t)·z0 + t·ε (RF convention, mirrors `latch/train_latch.py`), t-conditioned
mlp_ctx2 fine-tuned from the clean ckpt, evaluated on artist-disjoint test:

| t | 0.0 | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 |
|---|---|---|---|---|---|---|---|---|---|---|
| bacc | 0.245 | 0.273 | 0.275 | 0.265 | 0.246 | 0.221 | 0.187 | 0.154 | 0.132 | 0.125 |
| macro-F1 | 0.183 | 0.264 | 0.259 | 0.253 | 0.242 | 0.225 | 0.195 | 0.154 | 0.115 | 0.097 |

Graceful to t≈0.4–0.5, chance by t≥0.8. The t-conditioned model holds the clean ceiling
through t≈0.3 — IF the clean ceiling were high enough to guide with, mid-trajectory
guidance would be feasible. (t=0.0 dip is a t-embed edge effect; use the clean model at t=0.)

## Acceptance test (spec §3 gate: r > 0.7) — FAILED, coherently with the ceiling

Clean directional readout applied to 1,226 render z0s (`eval/hook_renders.jsonl`
siblings); frame≈16th-slot decode, contour 4-6-gram mining verbatim via
`eval/musicology/hook_metric.py`. Over 480 clips with hmr on both sides:
**Pearson r = 0.083, Spearman ρ = 0.190** vs wav-side muscriptor hmr.
No-lead agreement 0.778 (tp 474 / tn 480 / fp 100 / fn 172). A 0.22-F1 frame decoder
compounds through 4-6-gram exact-match mining → near-noise hook stats. The free z0-side
melody metric is NOT usable from raw latents at this readout quality.

## Verdict + implications

- **Mix-native z0 ceiling ≈ 0.27 macro-F1 — the finding itself.** Contrast: the v2
  battery read lone-lead synthetic latents at ≥91% frame detection, and corpus melody
  share is 9.3% of latent energy — the information is present but shallow readouts on
  full-mix z0 cannot separate the lead from the mix. This firms the M1 gradient-share
  story and moves Head A to DiT activations (spec §1 taps L8–15), where the LatCH sweep
  harness already goes next.
- Acceptance metric should be re-run when an activation-tap Head A exists; the machinery
  (decode + gram mining + correlation) is ready in `eval_acceptance.py`.

## Iteration lessons

1. Linear probes plateau immediately (best epoch ≤2); the MLP needs ~15–30 epochs.
2. Context beyond ±2 frames hurts (ctx4 < ctx2) — contour info is local, mirroring the
   v2 "onset+sustain microstates" picture.
3. Grid-phase recovery from source MIDI mattered for target quality: melodies.jsonl
   lacks the kick phase (up to ~0.4 s) and durations; re-slotting the MIDI reproduced
   the stored streams EXACTLY (match 1.000 on all 2,649 files), so targets are
   phase-correct with true note durations (prep_summary.json).
4. Class-count note: spec §0 says "11 classes"; the enumerated set folds to 8 labels
   (direction folded, per tasking) / 14 directional. Implemented as 8 + 14; naming kept.

## Files

- `prep_targets.py` → `targets/<id>.npz` (y8/y14 soft frame targets, 2,649 files),
  `prep_summary.json`
- `train_readout.py` → `results.json` (all runs), `splits.json` (artist-disjoint),
  checkpoints `readout_*.pt` (best: `readout_mlp_ctx2_y8.pt`; each embeds normalization
  mu/sd, class names/priors, frame rate, noise convention, slider-range metadata — spec
  §8 W-review 4a)
- `eval_acceptance.py` → `acceptance.json` (per-clip z0 vs wav hook stats)
- Logs: `prep.log`, `sweep.log`, `diag.log`; runners `run_sweep.sh`, `run_diag.sh`

## SYNTH-XEVAL — representation-limited vs target-noise-limited (2026-07-23, CPU, no GPU/lock)

Question: is the mix-native z0 ceiling (bacc 0.280 / macro-F1 0.273 above) capped by the
**representation** (shallow readout genuinely can't decode contour from z0) or by
**target noise** (corpus targets are skyline/muscriptor-derived, imperfect vs the exact
MIDI ground truth used here)? Frozen `readout_mlp_ctx2_y8.pt` — no retraining — applied
to synthetic material with exact note-grid GT, same 8-class folded set, same input
pipeline (`(z0-mu)/sd` per checkpoint, Conv1d ctx±2 mlp head; reused `train_readout.Readout`
+ `scores_from_cm` verbatim, and `prep_targets`'s `ALLOWED`/`_MAG_MAP`/`FRAME_DUR`/soft
time-overlap math for the GT builders). Harness sanity-checked against 40 real corpus
held-out files first: reproduced bacc 0.277 / F1 0.275 — matches the reported ceiling, so
the eval code itself is not the source of the numbers below.

| set | n files | n frames | bacc | Δ vs corpus | macro-F1 | Δ vs corpus |
|---|---|---|---|---|---|---|
| **corpus** (reference) | 273 | — | **0.280** | — | **0.273** | — |
| synthetic-solo v1 (`test_midis`, 65 renders, 5 timbres) | 65 | 33,385 | 0.272 | −0.008 | 0.191 | −0.082 |
| synthetic-solo gm (`gm_multifont`, 100/640 timbres, balanced) | 100 | 29,963 | **0.148** | −0.132 | 0.067 | −0.206 |
| synthetic-mix (32 lead+bass mixes, vs LEAD gt) | 32 | 9,412 | 0.243 | −0.037 | 0.207 | −0.066 |
| synthetic-solo pure-sine (`battery__sine`) | 1 | 262 | 0.125 | −0.155 | 0.006 | −0.267 |

**Verdict: Branch B — representation-limited, confirmed, and more starkly than the
tasking's own "solo ≈ 0.28" bar anticipated.** No synthetic-solo cell beats the noisy
corpus ceiling; the most rigorous one (`gm_multifont`, all 8 classes evenly represented
by design, 640-timbre battery) scores *worse* than corpus (bacc 0.148 vs 0.280) and the
pure-sine cell collapses to exact chance (0.125 = predicts rest for every single frame).
If target noise were the binding constraint, clean solo GT should have unlocked a
materially higher number somewhere — it doesn't, anywhere.

Per-class notes:
- **`test_midis`'s 0.272 bacc is misleadingly close to corpus** — the 6-pattern battery
  never emits a `m2` (2-semitone) move (support 0, excluded from the nanmean), so bacc is
  effectively averaged over 7 classes dominated by rest (recall 0.949) and pedal (0.607);
  `m3`/`m5`/`m7`/`m12` recall are 0.00–0.03. `gm_multifont`'s battery is the fair
  comparison — it visits all 6 interval magnitudes with equal support (3,400 frames
  each) by design, and there the collapse is total: `m5`/`m7`/`m12` recall = 0.000,
  `m1`/`m2`/`m3` recall 0.0003–0.026, rest recall 0.995 (i.e. the head predicts "rest"
  almost everywhere on isolated single-instrument synthetic audio).
- **Solo vs mix is the interesting reversal**: mix (lead+bass, no drums) scores *higher*
  than solo-alone on the identical balanced-battery melody (bacc 0.243 vs 0.148) despite
  having MORE energy in the latent to separate the lead from. This is the opposite of a
  naive "masking hurts" story — it reads as **out-of-distribution collapse**: the head was
  trained exclusively on full-mix corpus latents (drums+bass+harmony), and an isolated
  solo-lead z0 is further outside that training distribution than a lead+bass mix is,
  so it degrades harder. Domain shift, not target-label noise, is doing the damage here.
- **Pure sine (cleanest possible signal, zero timbral distraction) is the worst score of
  all** (bacc = exact chance) — directly contradicts the naive expectation that a
  cleaner/simpler signal should be easier; instead it's the most OOD input (no instrument
  ever contributes a sine-only voice to the training corpus) and the head falls back to
  its majority-class prior entirely.

Implication: the spec's existing pivot toward **DiT activation taps** (L8–15, already in
progress per the `head_a_ceiling_act/` sibling run) is reinforced from a second, independent
angle — this rules out "retrain on better/cleaner targets" as a fix, since better targets
alone would not have helped a representation that can't read isolated-instrument z0 at all.

Files: `synthetic_cross_eval.py` (harness + GT builders, reuses `prep_targets`/`train_readout`
verbatim), `synthetic_cross_eval.json` (full per-set confusion matrices + per-class scores).
