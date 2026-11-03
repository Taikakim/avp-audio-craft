# Checkpoint trajectory — adamw_bf16_sweep__adamw_goa_t512_bs1_lr1e4

- checkpoints: **10** (steps 5400–54000)
- net displacement ||W_last−W_0||: **204.607**
- total path length Σ‖ΔW‖: **660.341**
- **path efficiency** (net/path): **0.310**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 5.0** (step 27000)
- peak learning velocity: epoch 10.0 (‖ΔW‖=74.235)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 122.91 | 0.000 | 0.000 | 204.607 | 0.4880 | 0.000 |
| 2.0 | 141.16 | 72.898 | 72.898 | 193.366 | 0.5655 | 0.000 |
| 3.0 | 156.81 | 101.138 | 72.866 | 181.551 | 0.6328 | -0.037 |
| 4.0 | 170.70 | 122.390 | 72.993 | 168.974 | 0.6934 | -0.042 |
| 5.0 | 183.18 | 140.068 | 73.210 | 155.277 | 0.7493 | -0.045 |
| 6.0 | 194.89 | 155.693 | 73.512 | 140.101 | 0.8019 | -0.045 |
| 7.0 | 205.57 | 169.459 | 73.346 | 122.901 | 0.8517 | -0.047 |
| 8.0 | 215.64 | 182.061 | 73.624 | 102.004 | 0.9004 | -0.048 |
| 9.0 | 225.12 | 193.671 | 73.658 | 74.235 | 0.9485 | -0.047 |
| 10.0 | 234.21 | 204.607 | 74.235 | 0.000 | 1.0000 | -0.049 |

## Top moving layers (total velocity)

- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 70.360
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 70.290
- `model.transformer.layers.17.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 70.280
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 69.992
- `model.transformer.layers.9.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 69.960
- `model.transformer.layers.21.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 69.929
- `model.transformer.layers.8.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 69.912
- `model.transformer.layers.7.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 69.844