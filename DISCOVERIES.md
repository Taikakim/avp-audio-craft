# DISCOVERIES — the "have we already figured this out / built this?" index

*The discovery-phase search target (CLAUDE.md ⛔ DISCOVERY PHASE). Grouped by topic;
each entry = **what we found** + **where it lives** (folder/file links) + status/gotcha.
Search here FIRST before starting new work.*

**Owner: THE-FINN** — keeps this **generated from the instance journals**
(`profiles/*.journal.md`) + `WORKLOG.md`. When you land a finding or build a tool, drop a
journal line; it flows into here. This is not hand-curated prose to bit-rot — it's an index
regenerated from the journals. (Kim, 2026-07-06: instances keep forgetting; this is the fix.)

> Format per entry: `- **finding.** → path/to/code, path/to/doc — status/gotcha`

---

## Long-form generation · transitions · crossfade · blending two clips
- **Longform = SDEdit re-anchor + latent-space slerp crossfade + inpaint-continuation, drift-free by clamping to the previous tail's latents.** Fully implemented + 20 tests. Based on **SDEdit** (Meng 2021). `sigma_peak ≈ 0.4–0.6` is the tuned refine sweet spot; transitions morph under a *blended* prompt; best-of-N candidate windows scored by MERT+Audiobox.
  → `stable-audio-3/stable_audio_3/inference/longform.py` (`CrossfadeStitcher`, `SDEditReanchor`, `InpaintContinuationGenerator`, `LongFormRenderer`, `DriftMonitor`); spec `stable-audio-3/docs/superpowers/specs/2026-06-19-longform-sdedit-reanchor-crossfade-design.md`; steered/best-of-N `control/sa3_control/steered_longform.py`; docs `stable-audio-3/docs/workflows/longform.md`; tests `stable-audio-3/tests/test_longform.py`.
- **Latent beat-matching (downbeat phase-align + geometric-mean tempo stretch + slerp).** → `mir/scripts/latent_server.py` (`beatmatch_crossfade_to_wav`), `mir/scripts/latent_crossfader.py` (`slerp`/`crossfade_stems`), UI `mir/plots/explorer/tabs/viewer.py`. Needs `raw_audio_dir`+stems+`latent_player.ini` for the full path.
- **Audio-space bridge experiments (2026-07-06, CONTINUITY):** inpaint bridge + audio2audio-refine + beat-aligned crossfade in a 1-min arrangement; and the **failed** activation-crossfade (off-manifold → spectral artifacts; the dead-walker lesson). → `onnx/beat_bridge.py`, `onnx/bridge_crossfade.py`, `onnx/steered_layer_crossfade.py` (+ tests). **Reuse the longform latent-space version, not these audio-space scripts.**

## Control adapters · FusionCC · guidance
- **Dead walker / contractive denoising:** sample-space TFG gradients move the head's *prediction*, not onset timing — off-manifold perturbations get erased. Energy steers (on-manifold, locally-linear); onset-timing does not. FusionCC ≈ ControlNet++ reinvented; our novel bit = the blind-vs-redundant boundary condition. → `control/` findings, `docs/research-brief-*`, journals.

## LatCH · probing · layer↔feature mapping
- **Layer×feature encodability map scaffold** (which DiT layer's per-frame activations encode which audio feature — the target-conditioned localizer). CPU-tested; GPU activation-extraction deferred. → `latch/probe_layer_feature_map.py` (+ test). Features come free from `*.TIMESERIES.npz` (21 per-frame fields @ 4096 = latent grid). Prior probes: `latch/latch_probe_encodability.py`, `latch/latch_trajectory_probe.py`.

## Weight garden · model mutation
- **Value-preserving weight *shuffle* = musical "rewired mind" (not noise); value-changing ops (drift/blur/contrast/tilt) = damage.** Blur-attn = temporal smearing / dried transients. Seeded/reproducible; DiT blocks are `layers.N` (NOT `blocks.N`). → `stable-audio-3/scripts/weight_mutations.py` (+ test), `stable-audio-3/scripts/mutate_weights.py`, `docs/weight-garden-audition-notes.md`.

## Captions · conditioning · training data
- **Tiered caption system** (era-fronted T1 template / Granite-compressed Flamingo T2 / raw T3), sampled via `PreEncodedDataset` custom_metadata_fn; sidecars keep latents pristine. Multi-source + resume in train_lora. Feature tables + 36-cluster map. → `stable-audio-3/scripts/caption_tools.py` (+ test), `stable-audio-3/scripts/train_lora.py` (`--caption-sidecar`/`--source_weights`/`--resume_ckpt`), plan `docs/prompting-conditioning-plan.md`, tables `mir/data/feature_tables/`.
- **Relevance-routed / target-aware DoRA (research):** measurement must be target-conditioned (RF-loss gradient is deaf to control — W's rigor). Axis-2 noise-band reweighting = the MVP. → `docs/research-brief-relevance-routed-dora.md`, `docs/rigor-review-relevance-routed-dora.md`.

## Infra gotchas (the expensive ones)
- **Two venvs:** SA3 training belongs in `SAO/.venv` (torch 2.14/ROCm 7.15) OR `stable-audio-3/.venv` (torch 2.10, now has CK too) — but torch-2.14 alpha measured *slower* than torch-2.10+CK for training. CK flash-attn `.so` must be present (G's from-source build, pinned in pyproject). CPU inference needs `SA3_DISABLE_FLASH_ATTN=1` (flash-attn has no CPU backend). Never `HIP_VISIBLE_DEVICES=""`. → MASTER §3/§5, `docs/flash-attn-ck-rdna4.md`.
- **Clip fix:** CPU eval servers `np.clip`-flat-topped SA3's >1.0 peaks; fix = normalize-down. → `onnx/control_eval_server.py`, `onnx/latch_eval_server.py`.
- **Storage:** Lehto = training data only; evals+ckpts on Mantu; `latents_sa3` single copy on NVMe (`/home/kim/Projects/latents_sa3`). Watch for symlink-farm subsets dangling after moves (`find <root> -xtype l`).

---
*Seeded 2026-07-06 by CONTINUITY. THE-FINN: expand from all journals + add a generator
(aggregate `profiles/*.journal.md` → topic index) so this stays current, not stale.*
