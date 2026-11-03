---
name: latent-player
description: "Latent audio player + crossfader (canonical in the mir project), its HTTP endpoints, stem encoding, and the feature explorer UI"
metadata: 
  node_type: memory
  type: project
  originSessionId: ccd33273-2ad9-4e1a-a571-5a74da061b46
---

## Canonical location: the mir project
`/home/kim/Projects/mir/` — server `scripts/latent_server.py`, crossfader `scripts/latent_crossfader.py`, config `latent_player.ini` (mir root). Old copies remain in the SAO repo for reference but mir is authoritative.
- Run: `python scripts/latent_server.py` (env auto-applied now; no more sourcing rocm_env.sh — see [[environment]]).
- `latent_player.ini`: `latent_dir`, `stem_dir`, `port`, `sao_dir` (model_config/ckpt_path use `%(sao_dir)s` interpolation).
- Endpoints: `GET /status`, `/decode?track=NAME&position=0.5`, `/crops?track=NAME`, `/crossfade?track_a&track_b&pos_a&pos_b&drums/bass/other/vocals(α)&beta_a&beta_b&interp`.
- Stem latents from `_stem_dir`; full-mix β anchors from `_latent_dir`. Thread-safe via `_decode_lock`.
- `X-Audio-Source` response header on /decode & /crossfade: "raw" or "vae".

## Crossfader (`latent_crossfader.py`)
`setup_device()`, `slerp()`, `lerp()`, `reality_anchor()`, `crossfade_stems()`, `soft_clip()`, `load_latent()`.
Math: (1) `z_math = Interp(z_stem_A, z_stem_B, α)` (slerp/lerp); (2) optional dual β pulls toward A/B full-mix; (3) `sum(Decoder(z_i))` → tanh.
`STEMS = ["drums","bass","other","vocals"]` (order convention).

## Stem encoding
`encode_stems.py --track-dir <Goa_Separated_crops track> --stem-dir <root>`. Stem latents → `/run/media/kim/Lehto/goa-stems/<track>/<crop>_{bass,drums,other,vocals}.npy + .json` — kept separate from goa-small. Two tracks encoded: `0900 X - Dream - Radio` (144), `1843 MFG, Astral Projection - The Sleeper Must Awake` (180).

## Feature Explorer
- Live: `/run/media/kim/Lehto/feature_explorer.html` (+ committed `plots/feature_explorer.html`). Data JS: `/run/media/kim/Lehto/feature_explorer_data.js` (4494 tracks, 65 features). Generator: `plots/generate_explorer_data.py` (reads Mantu crops, writes Lehto). `statistical_analysis.py` is a reporter only.
- 🎵 Latent button → panel: Full Mix / Stem ×fader toggle; per-stem α, A/B β, Slerp/Lerp. Hover via plotly_hover + `.tl-item`/`.nn-row`/`.track-item` (data-lp-idx); position slider 400ms debounce; `removeCaptionHover` uses `pd.removeListener` to preserve the LP listener.
- A/B slots: A = white ring (`_lpHighlightIdx`, on hover); B = cyan ring (`_lpBHighlightIdx`, dbl-click → `lpSetB`). `_lpApplyHighlight()` handles `__lp_hl__`/`__lp_b_hl__`; `_lpFindXY(idx)` reads [x,y] from customdata.

See [[mir-project]], [[model-and-data]].
