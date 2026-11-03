---
name: model-and-data
description: "Small model config/dims/objective, dataset/encoding pipeline, conditioners, fine-tune training"
metadata: 
  node_type: memory
  type: project
  originSessionId: ccd33273-2ad9-4e1a-a571-5a74da061b46
---

## Model: Small variant
- Config: `models/checkpoints/small/base_model_config.json`; checkpoint: `models/checkpoints/small/base_model.ckpt`
- Fine-tune training config: `models/configs/base_model_finetune.json`
- `sample_rate=44100`, `sample_size=524288`, `downsampling_ratio=2048`, `latent_dim=64`
- `latent_length = 524288 // 2048 = 256` frames (~21.53 Hz, clip ~11.9 s)
- **`diffusion_objective = rectified_flow`** (NOT v). The base config's conditioning is just `prompt` (t5) + `seconds_total` (number). It has `distribution_shift_options`, but the RF sampler path uses the sigmoid logsnr schedule and does not apply dist_shift (passes pre-built sigmas).

## Custom conditioners (base_model_finetune.json)
Fine-tune adds numeric conditioners from MIR features beyond `seconds_total`: `lufs`, `spectral_flatness`, `bpm`, `release_year`, `roughness`, `production_complexity` — all from `.INFO` sidecars. `goa_metadata.py` builds the `prompt` from `track_metadata_artist`, `track_metadata_title`, `music_flamingo_short_*`.

## Dataset / encoding pipeline
- Source crops: `/run/media/kim/Mantu/ai-music/Goa_Separated_crops` — `Track Folder/Track_N.flac` (full mix) + `Track_N_{bass,drums,other,vocals}.flac` stems; sidecar `Track_N.INFO` (97+ MIR features from [[mir-project]]).
- SAT training data: `/run/media/kim/Lehto/goa-small` — `Track_N.npy` (latent [64,256]) + `Track_N.json` companion (seconds_total, padding_mask, all INFO fields). Full-mix only.
- LatCH training latents: `/run/media/kim/Lehto/latents` (202069 files). **Verified same VAE** as the base model's pretransform via decode-roundtrip (decoded audio is coherent music; latent round-trip error ~0.4 is just stochastic VAE encode + lossiness, not a mismatch).
- Encoders: `encode_dataset.py` (full-mix, unified single-pass), `encode_stems.py` (stems → `/run/media/kim/Lehto/goa-stems`, kept separate from goa-small). Both use `model.pretransform.encode`.

## Training (fine-tune)
- `python train.py --config-file train_finetune.ini` (sets `pretrained_ckpt_path`, `dataset_config=dataset_configs/goa_crops_training.json`, `logger=` no W&B, type `pre_encoded`).
- Custom metadata module: `goa_metadata.py`.

See [[environment]], [[latch-overview]], [[latent-player]].
