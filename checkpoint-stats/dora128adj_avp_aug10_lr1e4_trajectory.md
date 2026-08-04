# Checkpoint trajectory — dora128adj_avp_aug10_lr1e4

- checkpoints: **10** (steps 300–3000)
- net displacement ||W_last−W_0||: **190.911**
- total path length Σ‖ΔW‖: **269.042**
- **path efficiency** (net/path): **0.710**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 0.28** (step 1500)
- peak learning velocity: epoch 0.11 (‖ΔW‖=45.667)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 0.06 | 120.25 | 0.000 | 0.000 | 190.911 | 0.6092 | 0.000 |
| 0.11 | 138.43 | 45.667 | 45.667 | 168.353 | 0.7230 | 0.000 |
| 0.17 | 153.98 | 74.946 | 37.549 | 146.668 | 0.8048 | 0.619 |
| 0.22 | 168.28 | 97.974 | 33.036 | 125.374 | 0.8659 | 0.700 |
| 0.28 | 181.72 | 117.569 | 29.790 | 104.492 | 0.9115 | 0.736 |
| 0.33 | 194.23 | 134.800 | 27.363 | 83.922 | 0.9453 | 0.758 |
| 0.39 | 206.06 | 150.406 | 25.747 | 63.313 | 0.9700 | 0.767 |
| 0.44 | 217.40 | 164.832 | 24.367 | 42.788 | 0.9867 | 0.768 |
| 0.5 | 228.23 | 178.258 | 23.139 | 22.384 | 0.9964 | 0.774 |
| 0.56 | 238.65 | 190.911 | 22.384 | 0.000 | 1.0000 | 0.767 |

## Top moving layers (total velocity)

- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.272
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.238
- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.229
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.097
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.673
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.578
- `model.transformer.layers.19.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.076
- `model.transformer.layers.18.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.023