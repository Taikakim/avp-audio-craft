# Checkpoint trajectory — goa3_avp_r256_20260923

- checkpoints: **6** (steps 1268–6974)
- net displacement ||W_last−W_0||: **nan**
- total path length Σ‖ΔW‖: **nan**
- **path efficiency** (net/path): **nan**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 2.0** (step 1268)
- peak learning velocity: epoch 4.0 (‖ΔW‖=58.530)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 2.0 | 121.89 | 0.000 | 0.000 | nan | nan | 0.000 |
| 4.0 | 136.73 | 58.530 | 58.530 | nan | nan | 0.000 |
| 6.0 | 149.87 | 85.324 | 47.479 | nan | nan | 0.288 |
| 8.0 | 161.47 | 105.435 | 40.685 | nan | nan | 0.456 |
| 10.0 | 171.56 | 121.688 | 35.918 | nan | nan | 0.554 |
| 11.0 | nan | nan | nan | nan | nan | nan |

## Top moving layers (total velocity)

- `model.transformer.global_cond_embedder.2.parametrizations.weight.0.lora_B`: 15.515
- `model.preprocess_conv.parametrizations.weight.0.lora_A`: nan
- `model.preprocess_conv.parametrizations.weight.0.lora_B`: nan
- `model.postprocess_conv.parametrizations.weight.0.lora_A`: nan
- `model.postprocess_conv.parametrizations.weight.0.lora_B`: nan
- `conditioners.seconds_total.embedder.embedding.1.parametrizations.weight.0.lora_A`: nan
- `conditioners.seconds_total.embedder.embedding.1.parametrizations.weight.0.lora_B`: nan
- `model.to_timestep_embed.0.parametrizations.weight.0.lora_A`: nan