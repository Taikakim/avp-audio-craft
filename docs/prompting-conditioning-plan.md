# Prompting & conditioning plan for the next LoRA/DoRA run

*2026-07-04, CONTINUITY (design discussed with Kim; approved direction: finish current
data batch → analyse → split responsibilities between prompts and dataloader).*

## Philosophy

**Text for the neighborhood, lanes for the coordinates.** Captions carry the coarse
semantic address (genre, mood, era); precise numeric control (rhythm, energy, density,
year) lives in conditioning lanes. Grounding: density/envelope steering works through
the onset-adapter lane (weights-space), and the dead-walker result shows fine timing
is exactly what text/sample-space channels cannot carry.

## Pipeline

1. **MIR batch (GHOST-NOTE, running)** — organize + BS-RoFormer + track_analysis +
   timeseries on the 4 new Mantu corpora (574 tracks), Flamingo OFF at this stage;
   then SA3 T=4096 beat-aligned crops + encode into the NVMe `latents_sa3`.
   **Added output ask: per-track feature table** (one row per track: genre probs,
   mood probs, BPM, release year, energy stats, fp/style embedding if cheap) —
   the input to everything below.

   **Schema reality (W's review, 2026-07-04): the table is a cross-schema JOIN,
   not a read.** `latents_sa3/*.json` (index-named) carry top-12 discogs genre
   dicts + bpm + onset_density + year + mb_id but NO moods/energy; the
   `goa_crops/*.INFO` sidecars (track-named) carry top-5 essentia genre +
   top-2 mood dicts + rms_energy. Varying-k top-k dicts cannot be stacked for
   PCA — they must be aligned to canonical vocabularies (discogs labels for
   genre, essentia set for moods) and zero-filled. **WINTERMUTE builds the
   table builder** (his lane): fixed-dim aligned vectors, rows carry BOTH index
   key and track name, aggregated energy stats, year as sentinel + year_known
   flag (train-time: missing year = lane condition dropped via the CFG-dropout
   machinery, never fill-noise). W hands G the field map so the new-574 batch
   emits the aligned representation natively.

2. **Tag-vocabulary curation (CONTINUITY)** — on the merged corpus (old + new):
   - Merge near-synonym moods first (co-occurrence / embedding similarity;
     Kim vetoes the merge table).
   - Keep-band per tag: **>= ~75 absolute positive examples AND 3-50% prevalence.**
     (Absolute count gives the gradient signal; the ceiling preserves contrast —
     a tag in >50-60% of files stops differentiating. A percentage-only threshold
     like ">20%" is the wrong shape: it starves counts on small corpora and admits
     non-contrastive tags on big ones.)
   - Attach a mood to a track only above that tag's own ~P75 classifier-confidence
     across the corpus (adaptive per-tag threshold; fixed cutoffs fight the noisy,
     tag-specific probability distributions).

3. **Clustering (CONTINUITY)** — PCA-whiten -> k-means k~48 on genre/mood prob
   vectors (optionally + fp/style embedding). NOT raw SA3 latents (acoustic-local,
   mean-pooling blurs them). Name clusters by top-2 genres + top mood; eyeball.
   Purpose: **stratify the Flamingo budget** — 10% per cluster, not global random.

4. **Captions: three tiers per track, stored as a LIST in the latent json**
   - **T1 (all tracks)**: deterministic template from features, §3.5 comma-separated
     descriptor style: `"goa trance, psytechno, mystical spacey mood, 145 bpm, late 90s"`.
   - **T2 (stratified 10%)**: Music Flamingo (best prompts from the MIR yaml) ->
     Granite Small compression to 6-8 words.
   - **T3 (same 10%)**: raw long Flamingo caption, kept for free.

5. **Dataloader (CONTINUITY)** — prompt field string -> list; sample at train time
   T1 p=0.6 / T2 p=0.3 / T3 p=0.1 (fallback T1), CFG dropout on top. Cheap caption
   augmentation; a hallucinated caption can't poison a track it only narrates
   a third of the time.

6. **Numeric lanes**
   - **Release year**: era bucket rides free in T1; the proper version is a scalar
     FiLM lane (same machinery as the onset adapter's density scalar — config, not
     new architecture). Continuous normalized year = an era slider at inference.
   - **Rhythm timeseries**: the onset-envelope adapter IS the sample-accurate rhythm
     lane; inference-time "load an example" = MIR-extract the envelope from a
     reference track. Expand one lane at a time (beat grid, bass energy, brightness),
     gated on the pending interference-aware gain scheme and the RF-deaf list.

7. **Threshold-calibration probe (CONTINUITY, before the big run)** — quick throwaway
   LoRA on the extended corpus with the full tag set attached; probe steering strength
   per tag vs tag frequency. The curve replaces guessed thresholds with data.

## Sequencing / ownership

GHOST-NOTE: finish MIR batch + crops/encode + feature table (his lane, running).
CONTINUITY: steps 2-5 + 7 once the feature table lands; report tag table + cluster
naming to Kim for veto before caption generation. WINTERMUTE: looped in (training-data
lane). Flamingo pass is deliberately AFTER clustering — budget needs the strata.
