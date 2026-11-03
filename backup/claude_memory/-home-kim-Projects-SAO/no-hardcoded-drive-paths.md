---
name: no-hardcoded-drive-paths
description: Standing directive — no hardcoded /run/media drive paths in scripts; use a config file. Lehto = captions/latents (small files) for local training.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
  modified: 2026-08-17T18:32:19.979Z
---

**Kim direct, 2026-08-17: stop hardcoding drive folders. Use config files instead — both for new
scripts and whenever revising an existing one.**

**Why:** the absolute paths rot silently. Audit on 2026-08-17 found **144 files** hardcoding
`/run/media/kim/...`, including **9 files pointing at `/run/media/kim/Mantu1`, a drive label that
no longer exists** (`onnx/beat_bridge.py`, `onnx/bridge_crossfade.py`, `eval/eval_prompt_styles.py`,
`eval/density_control_eval.py`, `eval/transition_lab.py`, `eval/chroma_morph_transitions.py`,
`eval/explorer_render_server.py`, `Misc/build_evals.py`, `lumi/pack_data.sh`). `Misc/build_evals.py`
already works around it by trying `("Mantu", "Mantu1")` in turn — a workaround someone invented
locally instead of fixing the cause. Drive labels also change when a disk is remounted or replaced,
and a moved directory breaks every script that named it (moving `goa_archive_features` broke
`eval/build_goa_archive_sidecar.py:46`, `eval/caption_corpus_sample.py:15`).

**How to apply:** when touching a script that names a drive path, lift the path into a config file
and read it from there; don't add a new hardcoded path even "temporarily." Prefer one shared config
over per-script constants. Label counts as of the audit: Mantu 167, UUID drive 43, Mantu1 17
(broken), Lehto 15.

**Intended drive roles (Kim, same conversation):**
- **Lehto** — captions, latents, timeseries: **lots of small files**, because this is what local
  training reads with random access. Keep small-file corpora here.
- **UUID drive `9a410a1d-a4a8-4faf-8298-bcaa2576ea9d`** — the single home for **all LUMI content**
  ("everything from LUMI at one location"): `lumi_runs/` runs + renders.
- **Mantu** — non-LUMI bulk (`ai-music2`, `goa_archive_features`) + the `model_matrix` cell archive
  and `sa3_lora_runs`.

Related: [[sao-lumi-live-jobs-2026-08]], [[latents-saved-with-audio]].
