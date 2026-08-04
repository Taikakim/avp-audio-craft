# Checkpoint trajectory — fp32cmp_goa_t4096_bs4_lr5e5

- checkpoints: **8** (steps 1350–10800)
- net displacement ||W_last−W_0||: **161.201**
- total path length Σ‖ΔW‖: **225.845**
- **path efficiency** (net/path): **0.714**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 5400)
- peak learning velocity: epoch 2.0 (‖ΔW‖=45.954)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 119.08 | 0.000 | 0.000 | 161.201 | 0.6407 | 0.000 |
| 2.0 | 135.07 | 45.954 | 45.954 | 137.913 | 0.7601 | 0.000 |
| 3.0 | 149.76 | 74.871 | 38.231 | 114.886 | 0.8454 | 0.578 |
| 4.0 | 163.33 | 97.422 | 33.446 | 92.046 | 0.9066 | 0.667 |
| 5.0 | 175.90 | 116.344 | 30.109 | 69.465 | 0.9493 | 0.711 |
| 6.0 | 187.66 | 132.893 | 27.799 | 46.893 | 0.9778 | 0.726 |
| 7.0 | 198.67 | 147.699 | 25.875 | 24.433 | 0.9941 | 0.737 |
| 8.0 | 209.06 | 161.201 | 24.433 | 0.000 | 1.0000 | 0.738 |

## Top moving layers (total velocity)

- `model.transformer.layers.22.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 28.417
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 28.290
- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 28.030
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 27.841
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 27.761
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 27.691
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 27.634
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 27.600