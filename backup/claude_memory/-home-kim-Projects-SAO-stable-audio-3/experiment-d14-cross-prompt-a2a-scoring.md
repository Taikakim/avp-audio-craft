---
name: experiment-d14-cross-prompt-a2a-scoring
description: EXPERIMENTS D14 cross-prompt a2a bracket needs non-standard scoring — never merge into the main model_matrix/dora_table ranking as-is
metadata:
  type: project
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
  modified: 2026-08-23T08:01:58.321Z
---

CONTINUITY registered EXPERIMENTS D14 (2026-08-22, via cross-session message): a cross-prompt
a2a bracket — T4096 crops re-noised at a random level in [0.5, 0.9], denoised against a prompt
stolen from a DIFFERENT clip, across model families (melody-subspace, morph, midi/pianoroll
control, baseline). LUMI allocation ends 2026-08-23 with ~111 node-h free; a sizeable version
may fire same-day and land in a NEW `renders/` dir. CONTINUITY will ping with the dir name once
it exists — do not ingest/score anything speculatively before that ping.

**Why: [0.5, 0.9] is deliberately inside the mid-band a2a collapse zone.** Per WINTERMUTE's
2026-07-30 finding (`Misc/latent_noise_fragility.py`): mid-band a2a loss is the DiT abandoning
harmony, not input fragility. This noise range is chosen ON PURPOSE to be hard.

**How to apply when these clips land:**
1. **Never let D14 cells merge into the main model_matrix/`dora_table` ranking.** Low CE / poor
   DSP metrics at this noise band is the EXPECTED baseline, not a broken render — every family
   will look like a failure if compared against normal t2a cells on the same board/ranking. The
   valid read is the DELTA between model families AT MATCHED NOISE LEVEL, never absolute quality.
2. **CLAP is actively misleading here, not just noisy.** The prompt is deliberately stolen from a
   different clip, so `clap_matched` measures adherence to a caption describing DIFFERENT audio.
   A HIGH clap score here likely means the model threw away the init audio and followed the
   (wrong) caption — that's the FAILURE mode, not success, for this experiment's whole point
   (forcing a choice between init-audio fidelity and caption-following). Score/display CLAP in a
   separate column or flag it, don't fold it into a "higher is better" ranking like every other
   campaign.
3. **NOT the `.mmline.json` convention — do NOT use `eval/ingest_matrix_cells.py`.** Own sidecar
   schema per clip (`.json` + `.z0.npy` beside each `.wav`). Filename:
   `a2a__<label>__<stem>__sig<sigma>__from_<corpus>_<donor>__cfg7.wav`.

**LANDED 2026-08-22/23 as `renders/a2a_bracket/` (job 21457563, Kim pulling to the UUID drive
now).** CONTINUITY's full scoring brief, 2026-08-23:

1. **`refs/` subdirectory = NOT model output — EXCLUDE explicitly, never glob `**/*.wav`
   blindly.** These are untouched source crops decoded straight from stored latents (the clean
   A/B reference for listening). Scoring them as generations pollutes every comparison with
   real-music clips sitting in the same table as deliberately-degraded cells.
2. **Eight families, one per rank:** `baseline` (medium-base, no adapter) · `sub_v3sel_k5` ·
   `sub_v3sel_k12` · `sub_k24_bigmix` · `a12_warm` · `a12_warmwsd` · `a13_fullft_avp` (a FULL-FT
   backbone, not an adapter — first-ever adapter-vs-fullFT-under-renoising datapoint here) ·
   `morph_L3_ft` (control adapter, conditioned on contour tokens).
3. **PAIRED comparison is the intended read, not distribution comparison.** All 8 families
   rendered the IDENTICAL grid (same source crops/donor prompts/sigmas, shared `--plan-seed`) —
   match cells on `(src_stem, sigma, donor_stem)` and diff cell-for-cell. Far more sensitive than
   comparing aggregate stats per family.
4. **Three strata that must NOT be pooled** (all in each cell's `.json` sidecar):
   - `band`: `"kim"` (sigma in [0.5,0.9], the real experiment) vs `"anchor"` (~15% of cells at
     sigma 0.3/0.4 — a deliberate low-noise yardstick, included because D1 — the survival-curve
     measurement twin — never actually ran, so there's no independently-measured baseline for
     "what should survive at low noise"). Pooling kim+anchor makes the hard band look better than
     it is.
   - `cross_corpus`: true/false, 50/50 split — donor prompt from a DIFFERENT corpus vs same
     corpus. Cross-corpus is the harsher test; don't average across this split either.
   - `sigma` is continuous, not a fixed ladder — BIN it, don't treat as discrete factor levels.
5. **One real confound: `morph_L3_ft` ran GOA-ONLY** (contour sidecars only exist for goa stems)
   — the other 7 families span goa/avpaug/suomi/biggoa. Morph is NOT on the same crop set and
   cannot be ranked against the other 7 directly — compare it only within its own goa cells,
   against the other families' goa-only cells.
6. **Verify per-family cell counts before trusting any of it** — CONTINUITY confirmed the job
   completed (~21 GB, about right for the full 8×32 grid) but has NOT verified which arms
   actually succeeded end-to-end. A family with a cell count well short of the others died
   partway and its numbers are not trustworthy. The job log (`a2a_bracket-21457563.out`) has a
   per-cell `[a2a:<label>]` line and an explicit FAILED line on any arm that died — check this
   BEFORE scoring if cell counts look uneven across families.

See [[filelock-shared-files-and-pipe-exit-codes]] for the concurrent-ingest lock convention this
also needs when it lands (another shared-manifest write) — though since this isn't
`ingest_matrix_cells.py`-based, the relevant shared resource is more likely a bespoke D14 board
page than `manifest_live.jsonl` itself.
