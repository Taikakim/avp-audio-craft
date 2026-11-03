---
name: mir-project
description: Pointer to the sibling MIR project — only the bits this SAO/LatCH project consumes (the timeseries DB and the real feature extractors)
metadata: 
  node_type: memory
  type: reference
  originSessionId: ccd33273-2ad9-4e1a-a571-5a74da061b46
---

The MIR feature-extraction project lives at `/home/kim/Projects/mir` and has its **own memory + `CLAUDE.md`** — keep its generic internals there, not here. This entry only records what the SAO/LatCH work depends on.

- **TimeseriesDB** (LatCH training targets + verification): `/home/kim/Projects/mir/data/timeseries.db` (SQLite, ~209k entries). API: `from core.timeseries_db import TimeseriesDB; db.get("Artist - Title_0")` → `{field: np.ndarray}`. Add `/home/kim/Projects/mir/src` to `sys.path`. All fields are stored at **256 frames / ~21.53 Hz to match the SAO latent grid** (so target↔latent alignment is correct).
- **Real feature extractors** (use these when verifying LatCH control, not hand-rolled copies): `src/spectral/` — e.g. `multiband_rms.py`, `timeseries_features.py`. `librosa`/`scipy`/`PyYAML` are available in `sat-venv`. See [[latch-verification]].
- **Building the DB** (the published repo is `github.com/Taikakim/mir-feature-extraction` = the local mir): config-driven, `python src/master_pipeline.py --config config/master_pipeline.yaml`. The `crop_analysis` stage calls `timeseries_features.extract_timeseries`, which computes the 256-frame `_ts` arrays and writes them via `db.put(crop_stem, {...})`. DB = SQLite WAL, table `ts(key TEXT PRIMARY KEY, data BLOB)`; key = crop stem; data = `gzip(msgpack({field:{s:shape,b:float32 bytes}}))`. To repopulate only time-series on an existing crop set, run with `stages: crop_analysis: true` (others false). Bootstrap old `.INFO` time-series → DB: `scripts/migrate_timeseries_to_db.py`. mir has its OWN `src/core/rocm_env.py` (`setup_rocm_env()`), independent of SAO's `rocm_env.yaml`.
- **Stats / range-bracketing tools** (use these to set LatCH slider ranges, not ad-hoc DB queries): `plots/build_dataset_stats.py` (per-feature distributions), `plots/correlate_features.py`, `scripts/verify_features.py` (feature coverage). See [[feedback-use-mir-tools]].
- For INFO-file fields, the extraction pipeline, and anything else MIR-internal: read mir's own `CLAUDE.md` / memory — don't duplicate it here.

See [[latch-verification]], [[latent-player]], [[model-and-data]].
