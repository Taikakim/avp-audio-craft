# Checkpoint trajectory — goa5k_r128_shampoo_subloss_k5_2026-09-26

- checkpoints: **6** (steps 1011–6066)
- net displacement ||W_last−W_0||: **15.330**
- total path length Σ‖ΔW‖: **21.582**
- **path efficiency** (net/path): **0.710**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 9.0** (step 3033)
- peak learning velocity: epoch 6.0 (‖ΔW‖=6.074)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 3.0 | 99.29 | 0.000 | 0.000 | 15.330 | 0.9884 | 0.000 |
| 6.0 | 99.68 | 6.074 | 6.074 | 12.250 | 0.9926 | 0.000 |
| 9.0 | 99.99 | 9.023 | 4.675 | 9.326 | 0.9957 | 0.399 |
| 12.0 | 100.28 | 11.366 | 3.988 | 6.351 | 0.9980 | 0.563 |
| 15.0 | 100.56 | 13.449 | 3.584 | 3.260 | 0.9995 | 0.666 |
| 18.0 | 100.86 | 15.330 | 3.260 | 0.000 | 1.0000 | 0.721 |

## Top moving layers (total velocity)

- `model.to_cond_embed.2.parametrizations.weight.0.lora_A`: 2.718
- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 2.709
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 2.681
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 2.672
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 2.671
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 2.644
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 2.628
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 2.596