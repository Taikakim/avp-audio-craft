# Checkpoint trajectory — longctx_t1024_r128

- checkpoints: **8** (steps 337–2696)
- net displacement ||W_last−W_0||: **154.176**
- total path length Σ‖ΔW‖: **218.613**
- **path efficiency** (net/path): **0.705**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 1348)
- peak learning velocity: epoch 2.0 (‖ΔW‖=44.361)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 116.81 | 0.000 | 0.000 | 154.176 | 0.6457 | 0.000 |
| 2.0 | 132.00 | 44.361 | 44.361 | 132.351 | 0.7603 | 0.000 |
| 3.0 | 145.65 | 72.010 | 36.806 | 110.709 | 0.8435 | 0.571 |
| 4.0 | 158.21 | 93.414 | 32.347 | 89.023 | 0.9045 | 0.656 |
| 5.0 | 169.90 | 111.371 | 29.120 | 67.390 | 0.9479 | 0.702 |
| 6.0 | 180.89 | 127.097 | 26.911 | 45.691 | 0.9770 | 0.723 |
| 7.0 | 191.29 | 141.236 | 25.226 | 23.841 | 0.9939 | 0.731 |
| 8.0 | 201.17 | 154.176 | 23.841 | 0.000 | 1.0000 | 0.734 |

## Top moving layers (total velocity)

- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 26.541
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 26.475
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 26.429
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 26.380
- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 26.374
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 26.338
- `model.transformer.layers.7.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 26.195
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 26.180