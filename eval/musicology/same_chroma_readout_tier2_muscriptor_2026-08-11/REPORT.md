# same_chroma readout — Tier 2 (real goa via MuScriptor pairing) — REPORT

**2026-08-11.** Tier-2 of the `same_chroma` readout validation. Tier-1 (synthetic MIDI-latent pairs,
`../same_chroma_readout_2026-08-11/`) found the head reads bass/mid chroma strongly + timbre-invariantly
(cos12 0.79–0.86) but the **air/treble (melody, oct-9) band pooled near-null (0.054)** — diagnosed as
*register-content-limited* (synthetic patterns sat in bass/mid register). Tier-2 tests the open question on
**real goa, which genuinely occupies the treble register**: does the head read the air/melody band there?
*(Pipeline code + numbers: `predict_head.py`, `score_and_report.py`, `results.json`. Subagent-built,
C-reviewed + numbers verified against results.json before broadcast.)*

## Headline — YES, and air is the STRONGEST-reading band, once you correct a real chroma trap

**The chroma trap (this test surfaced it, single-track sanity check caught it):** goa is genre-homogeneous
(minor-key, tonic-heavy rolling bass, shared lead grammar — per the 2026-07-22 musicology study), so BOTH
the head's prediction and the true audio-GT are pulled toward a generic "goa chroma shape." That inflates
**raw** cosine for *any* pairing, matched or not:

| PRIMARY (audio-GT), timeavg median | bass | mid | air |
|---|---|---|---|
| matched (raw) | 0.987 | 0.996 | 0.997 |
| null / mismatched (raw) | 0.983 | 0.994 | 0.995 |
| **Δ (raw is meaningless)** | +0.004 | +0.002 | +0.002 |

Raw matched ≈ raw null in every band → raw cosine measures the shared genre profile, not per-track fidelity.
Same trap already documented in `eval/melody_wall_analysis.py`'s whitening note + WORKLOG 2026-07-12
("thin absolute margin"). Fix added: 5-derangement **null** controls + a corpus-**demeaned** variant
(subtract the corpus-mean 12-d profile per band before cosine → isolate track-specific signal).

**Debiased PRIMARY (audio-GT, n=1200 paired, 0 dropped) — demeaned cos12 median:**

| band | demeaned median | vs Tier-1 |
|---|---|---|
| **air (melody)** | **0.918** | Tier-1 air ≈ 0.054 (register-limited) → **categorical reversal** |
| mid | 0.536 | |
| bass | 0.214 | |

Air is **4.3× bass, 1.7× mid** on the debiased metric. Real goa confirms Tier-1's diagnosis: **air was never
a head weakness — it was a synthetic-test-material artifact.** The head reads the melody/harmony that lives
in the treble register when that register is actually occupied.

**Independent corroboration — SECONDARY (MuScriptor-MIDI GT, n=752 paired, 448 dropped on
`integrity_flag && integrity_pc_corr>=0.30`):** here the *raw matched-vs-null gap* is the trustworthy
number (demeaned is polluted — ~366/752 tracks have zero transcribed air notes = data-sparsity, not a
finding). **Air is the ONLY band with a real per-track gap:** matched 0.403 vs null 0.207 (Δ+0.196,
n_with_notes=386/752). Bass/mid are matched≈null (Δ~0.01) — consistent with WORKLOG's known finding that
full-mix MuScriptor collapses to a generic rolling bassline, so bass/mid "signal" there is genre-grammar,
not per-track fidelity. So the head tracks the transcribed **melody** specifically.

## Method (worth keeping)
- **PRIMARY GT** = `compute_same_chroma` (mir-same-chroma) on the **exact source-audio segment** via
  `source_path`/`start_sample`/`end_sample` from the MuScriptor `stats.json` (`end-start = 16,777,216`
  samples = exactly 4096 frames × 4096 hop on every pair → sample-accurate, no resampling).
- **Deliberately NOT** `latents_sa3_chroma/*.npz` as GT — that store is `W@z+b`, a *linear readout of the
  latent itself*, so scoring against it would be circular against the head's likely training-target family.
  (`build_muscriptor_ref_profiles.py` profiles that store → unrelated, correctly avoided.)
- Reused verbatim: Tier-1's `predict_head.py`/`score_and_report.py` (head-forward at t=0, band-major
  (3,128,T) reshape, `cos12`/`fold_to_12`).
- Stage A (predict, SAO/.venv, CPU) forwarded the head on **all 5400** real goa latents (single-process
  batched; a ProcessPool attempt thrashed on `rocm_env.apply_profile` contention — killed, replaced;
  ~19 min, cached). Stage B (mir venv) scored a fixed-seed 1200/5400 sample (~18 min).

## Caveats (flagged, not glossed)
- Demeaned/null metrics need a same-flavor cohort baseline; PRIMARY's is clean, SECONDARY's air-band
  *demeaned* number is unreliable (use its raw matched-vs-null gap instead).
- Chroma is a **harmonic proxy, not a lead-isolated** measure (same caveat Tier-1 + the 2026-08-04
  melody-wall work carry).
- The demeaned distributions are **bimodal** (strong majority + a near-null/negative minority);
  uncharacterized here — natural follow-up: join `features.jsonl`'s `has_lead`/`lead_rate` (2026-07-22
  study) to see if the minority is the lead-absent tracks.

## Why this matters for the melody-conditioning plan (C)
The trap IS the design lesson: **raw band-chroma encodes the copyable genre-generic shape; the
track-specific melodic IDENTITY lives in the demeaned/whitened residual.** So the conditioning signal
should be the **demeaned (corpus-whitened) chroma**, not raw — conditioning on raw would hand the model the
overfittable "generic goa" vector, exactly the equivariant-vs-invariant / whitening insight (melody-selective
subspace v3), now empirically grounded on real audio. Net: Tier-1 (bass/mid, timbre-invariant) + Tier-2
(air/melody, on real goa, debiased) validate the head end-to-end as a usable melodic-movement readout.
