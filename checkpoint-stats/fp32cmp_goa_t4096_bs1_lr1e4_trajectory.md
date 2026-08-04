# Checkpoint trajectory — fp32cmp_goa_t4096_bs1_lr1e4

- checkpoints: **7** (steps 5400–37800)
- net displacement ||W_last−W_0||: **458.186**
- total path length Σ‖ΔW‖: **704.045**
- **path efficiency** (net/path): **0.651**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 21600)
- peak learning velocity: epoch 2.0 (‖ΔW‖=165.025)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 250.07 | 0.000 | 0.000 | 458.186 | 0.5039 | 0.000 |
| 2.0 | 329.06 | 165.025 | 165.025 | 388.233 | 0.6838 | 0.000 |
| 3.0 | 386.80 | 258.985 | 134.639 | 315.959 | 0.8066 | 0.489 |
| 4.0 | 432.62 | 326.429 | 116.479 | 241.774 | 0.8933 | 0.578 |
| 5.0 | 470.51 | 379.089 | 104.323 | 165.754 | 0.9520 | 0.615 |
| 6.0 | 502.55 | 422.070 | 95.037 | 88.541 | 0.9867 | 0.632 |
| 7.0 | 530.10 | 458.186 | 88.541 | 0.000 | 1.0000 | 0.630 |

## Top moving layers (total velocity)

- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 84.822
- `model.transformer.layers.6.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 84.695
- `model.transformer.layers.4.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 84.600
- `model.transformer.layers.7.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 84.275
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 83.549
- `model.transformer.layers.3.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 83.186
- `model.transformer.layers.8.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 83.161
- `model.transformer.layers.9.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 83.131