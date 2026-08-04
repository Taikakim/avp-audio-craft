# Checkpoint trajectory — fp32cmp_goa_t4096_bs4_lr1e4

- checkpoints: **8** (steps 1350–10800)
- net displacement ||W_last−W_0||: **288.482**
- total path length Σ‖ΔW‖: **423.440**
- **path efficiency** (net/path): **0.681**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 9.03** (step 5400)
- peak learning velocity: epoch 4.52 (‖ΔW‖=87.214)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 2.26 | 157.78 | 0.000 | 0.000 | 288.482 | 0.5417 | 0.000 |
| 4.52 | 197.02 | 87.214 | 87.214 | 248.011 | 0.6985 | 0.000 |
| 6.77 | 229.22 | 139.986 | 71.707 | 207.881 | 0.8048 | 0.547 |
| 9.03 | 256.87 | 180.001 | 62.596 | 167.595 | 0.8809 | 0.634 |
| 11.29 | 281.28 | 212.905 | 56.404 | 127.061 | 0.9350 | 0.674 |
| 13.55 | 303.30 | 241.212 | 51.873 | 86.339 | 0.9711 | 0.693 |
| 15.8 | 323.28 | 266.115 | 48.236 | 45.409 | 0.9922 | 0.699 |
| 18.06 | 341.66 | 288.482 | 45.409 | 0.000 | 1.0000 | 0.700 |

## Top moving layers (total velocity)

- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 51.451
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 51.448
- `model.transformer.layers.6.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 51.410
- `model.transformer.layers.4.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 51.327
- `model.transformer.layers.7.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 51.247
- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 51.211
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 51.138
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 51.086