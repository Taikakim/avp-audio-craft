# Checkpoint trajectory — fp32cmp_avp_t4096_bs4_lr1e4

- checkpoints: **8** (steps 598–4784)
- net displacement ||W_last−W_0||: **217.437**
- total path length Σ‖ΔW‖: **302.368**
- **path efficiency** (net/path): **0.719**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 2392)
- peak learning velocity: epoch 2.0 (‖ΔW‖=61.092)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 131.59 | 0.000 | 0.000 | 217.436 | 0.5945 | 0.000 |
| 2.0 | 157.25 | 61.092 | 61.092 | 185.941 | 0.7360 | 0.000 |
| 3.0 | 179.93 | 99.909 | 50.796 | 155.068 | 0.8316 | 0.591 |
| 4.0 | 200.44 | 130.309 | 44.626 | 124.533 | 0.8984 | 0.674 |
| 5.0 | 219.20 | 155.958 | 40.562 | 93.959 | 0.9453 | 0.710 |
| 6.0 | 236.62 | 178.528 | 37.410 | 63.413 | 0.9762 | 0.733 |
| 7.0 | 252.86 | 198.822 | 34.848 | 33.035 | 0.9937 | 0.745 |
| 8.0 | 268.18 | 217.436 | 33.035 | 0.000 | 1.0000 | 0.745 |

## Top moving layers (total velocity)

- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.812
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.656
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.290
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.970
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.572
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.367
- `model.transformer.layers.18.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.314
- `model.transformer.layers.19.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.313