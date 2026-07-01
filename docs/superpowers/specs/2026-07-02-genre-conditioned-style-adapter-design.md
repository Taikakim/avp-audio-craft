# Genre-conditioned FiLM style adapter for SA3 — design

**Goal:** Capture "goa / melodic-goa" style in SA3 with a conditioning **adapter**
(forward-mod, frozen base), conditioned on an audio-derived **style fingerprint**
(genre softmax + release year + groove features) — not a weight finetune, and not the
text prompt.

**Architecture (one line):** Reuse the `sa3_control` decoupled-cross-attn adapter, swap
its scalar conditioner for a multi-input fingerprint conditioner, train on the goa corpus
with the rectified-flow loss, and pick the conditioning scope by a 3-variant benchmark.

**Tech stack:** SA3 medium-base, `sa3_control` adapter machinery, essentia discogs-400
genre head (`gmi_onnx`), NVMe latents mirror, `SAO/.venv` (torch 2.14 / ROCm 7.15, CK FA).

---

## Motivation — why an adapter, and why not the text prompt

- **The current SA3 training prompt is a noisy metadata string** — e.g.
  `genre: psytrance, title: contact…, artist: eat static, bpm: 142`. The genre is
  unreliable Spotify/MusicBrainz metadata (often wrong/missing, spanning house → acid
  techno), and there is **no sonic description** (Music Flamingo captions are too
  expensive to have generated for the crops). The DoRA finetune learned style through
  this broken text bottleneck → drifted toward modern psytrance and lost audio quality.
- **The FiLM control adapters condition on MIR features, not text.** Trained on the goa
  audio via the flow loss, they absorbed the goa distribution as an always-on forward
  bias, immune to the prompt noise → they produced **better goa than the DoRA despite not
  being a style model.** That is the empirical signal this design follows: forward-mod on
  audio + a consistent, audio-derived conditioning signal is the right vehicle for style.
- **Goa is within SA3's distribution**, so an adapter (frozen base) steers toward it while
  **preserving base audio quality**, unlike a weight finetune that drifts on limited noisy
  data. Adapters are also reversible, composable, and cheap — a style *library* can coexist.

## Core architecture

- Reuse the `sa3_control` decoupled cross-attn adapter: **24 DiT cross-attn blocks,
  `control_dim=768`, `n_tokens=256`, base frozen, ~30–40 M params** (the 24 cross-attns are
  ~90 %+ of the params; the conditioner is a ~1–5 % sliver). Rectified-flow training on the
  goa corpus. CFG mechanism unchanged (trained null = zeros) → **style rides CFG**.
- **Only structural change:** replace `ScalarAttributeEncoder` (scalar → control tokens)
  with a **`FingerprintEncoder`** (fingerprint vector → `n_tokens × 768` control tokens).
  Widening the conditioner input from 1-dim to ~15-dim adds negligible parameters — so the
  multi-input adapter is **the same size** as the existing scalar adapter. Size is *not* a
  reason to prefer one conditioning scope over another.
- Chroma is a **separate head** (different control paradigm) — out of scope here; it
  composes at inference.

## Conditioning fingerprint — per-feature granularity (the correctness core)

The fingerprint mixes three granularities, chosen per feature so the conditioning always
matches what the model is trained on:

- **Static (track-level, broadcast to every window):**
  - **Genre vector** — a **fixed vocabulary** of the K most-prevalent electronic
    discogs-400 genres (Goa Trance / Psy-Trance / Progressive Trance / Trance / Hard Trance
    / Ambient / Dark Ambient / Downtempo …; K chosen empirically from the corpus
    distribution). **Raw softmax probabilities** for the K genres **+ an
    `other = 1 − Σ(selected)` bucket** → a proper simplex with *no renormalization
    distortion*. (A track that is 0.3 goa with the rest spread over acoustic genres reads
    `[goa 0.3, …, other 0.7]` = correctly *weakly* goa, not 100 %.) Fixed vocab (not
    per-track top-5) keeps the FiLM dimensions stable.
  - **release_year** — normalized (e.g. `(year − 1990) / 30`). Included so era/production
    (90s goa vs modern melodic goa) is a dial, removing the need to differentiate by ear.
- **Stable style traits (track-level):** **BPM, syncopation** (optionally
  rhythmic-complexity), normalized. Essentia/audio-derived, consistent across a track, and
  not cheaply recomputable from the latent-frame timeseries (syncopation needs the beat
  grid) — track-level is coherent because they *describe the style*.
- **Volatile (window-computed — V-B only):** **onset density, energy (rms).** These swing
  hard within a track, so a crop-level value contradicts a windowed sample. Computed from
  the sliced `.TIMESERIES.npz` at dataload (mean rms for energy; onset-count / duration for
  density).

### Window alignment (a correctness bug that also affects the existing heads)

`LatentControlDataset.__getitem__` slices the per-frame timeseries controls to the
beat-aligned training window (`controls[k] = v[:, s:s+tw]`, `dataset.py:140`) **but reads
the scalar from the crop-level `.json`** (`raw = float(m.get(scalar_field))`,
`dataset.py:152`). So a 512-frame window is labeled with the whole-crop's density —
**misaligned**.

- **Fix:** for *volatile* features, aggregate the already-sliced timeseries in
  `__getitem__` instead of reading the `.json`. Static/stable features stay track-level
  (correct by design).
- **This fix also applies to the existing onset/energy scalar heads** and plausibly
  explains part of their weak/dead control in the head-sweep (they trained on labels that
  didn't match their windows). Re-check a small onset control-eval after the fix.

## The three-variant benchmark (empirical scope decision)

All three are the same ~30–40 M size. Train each **~5 epochs at the good settings →
compare → run detailed brackets on the winner** (the established methodology).

- **V-A — style + groove:** genre + year + BPM + syncopation (all track-level/stable).
  Existing onset/energy steering heads stay separate.
- **V-B — maximal:** V-A + **window-computed** onset-density + energy (subsumes the scalar
  heads into the joint conditioner).
- **V-C — style-only:** genre + year; BPM / sync / onset / energy stay as separate stacked
  heads.

## Good-settings baseline

From the established control brackets: `crop-frames 512` (beat-aligned random window),
`control-dim 768`, `n-tokens 256`, the fitted batch, LR ≈ 7.5e-5–1e-4, optimizer sweep
{AdamW, Fusion}, **EMA + grad-accum + early-stop** (standing recipe). fp32 base
(`model_half=False`, as control training). NVMe latents `/home/kim/Projects/latents_sa3`
(never Lehto for throughput).

## Eval — how "best" is judged (3-way compare + the winner's brackets)

- **MERT distance-to-Goa** (`cos_dist_mid`, the ranker) vs the cached goa reference.
- **Audiobox CE** (quality).
- **Genre-softmax-of-the-output** — re-run the discogs-400 head on generated audio: does it
  classify *more goa* (higher goa prob) than base? A cheap, objective style metric this
  design uniquely enables.
- **By-ear** (authoritative) via a riffer-evals playable same-playhead cell page.

## v2 telemetry hook (logged in v1, consumed later)

v1 instruments **per-region flow-loss + control-extreme failures** (existing telemetry
infra) → a coverage/importance map. **v2 = importance-weighted / coverage-guided training**
(allocate training steps ∝ style-relevance × data-density; "train the relevant manifold
regions 100 %, the less-useful ones less") consumes it. Deferred — v1 only logs the data
v2 needs.

## Data prep / plumbing (no latent re-encode)

- Run the essentia discogs-400 genre head (`gmi_onnx`) over the crops (or per-track,
  propagated) → store the **K-genre raw-prob vector + `other`** in each crop `.json`.
- BPM + syncopation + year already in the `.json`; onset/energy timeseries already in
  `.TIMESERIES.npz`.
- Build the fingerprint at dataload. **Latents are untouched — we only add conditioning.**

## Inference control surface

Dial the fingerprint — genre → goa, era via year, BPM / syncopation — for style steering
with base quality preserved; composable with the chroma head and (V-A / V-C) the onset /
energy heads.

## Scope guard (YAGNI — explicitly out of v1)

- v2 importance-weighted / coverage-guided training (v1 only logs telemetry).
- The separate chroma head.
- Per-frame **contour** conditioning for the volatile dims (v1 uses window-aggregated
  scalars; contour steering is a v-next head, not style capture).

## Risks / open items

- **Genre-head accuracy on the corpus:** a 10-track sanity check that the discogs head
  actually separates known 90s-goa from modern-psy (the year dim reduces reliance on this,
  but confirm it isn't noise).
- **K (genre-vocab size):** choose empirically from the corpus genre distribution.
- **Window-scalar fix must not regress existing heads:** re-run a small onset control-eval
  after.
- **Drive:** use the NVMe latents mirror, not Lehto (throughput + mount reliability).

## Provenance

Design from the 2026-07-02 brainstorming session. Builds on the DoRA finetune finding
(`mir` memory `sa3-dora-goa-finetune`), the SA3 LatCH head-sweep (`sa3-latch-head-sweep`),
the SA3 inference speed shootout (`SAO/docs/sa3-inference-speed-shootout.md`), and the
`sa3_control` adapter machinery (`SAO/control/sa3_control/`).
