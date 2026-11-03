# Checkpoint trajectory — adamw_bf16_sweep__adamw_goa_t512_bs4_lr1e4

- checkpoints: **10** (steps 1350–13500)
- net displacement ||W_last−W_0||: **112.286**
- total path length Σ‖ΔW‖: **342.545**
- **path efficiency** (net/path): **0.328**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 5.0** (step 6750)
- peak learning velocity: epoch 2.0 (‖ΔW‖=38.468)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 106.63 | 0.000 | 0.000 | 112.286 | 0.6863 | 0.000 |
| 2.0 | 113.20 | 38.468 | 38.468 | 104.758 | 0.7346 | 0.000 |
| 3.0 | 119.29 | 53.837 | 38.038 | 97.459 | 0.7756 | -0.010 |
| 4.0 | 125.07 | 65.609 | 37.873 | 90.002 | 0.8125 | -0.020 |
| 5.0 | 130.48 | 75.581 | 38.042 | 82.081 | 0.8470 | -0.027 |
| 6.0 | 135.67 | 84.254 | 38.045 | 73.513 | 0.8794 | -0.032 |
| 7.0 | 140.61 | 92.108 | 37.967 | 64.030 | 0.9099 | -0.034 |
| 8.0 | 145.32 | 99.246 | 37.823 | 52.933 | 0.9394 | -0.035 |
| 9.0 | 149.93 | 106.019 | 38.287 | 38.001 | 0.9692 | -0.038 |
| 10.0 | 154.39 | 112.286 | 38.001 | 0.000 | 1.0000 | -0.037 |

## Top moving layers (total velocity)

- `model.transformer.layers.21.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.457
- `model.transformer.layers.20.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.275
- `model.transformer.layers.17.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.197
- `model.transformer.layers.22.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.002
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.985
- `model.transformer.layers.8.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.955
- `model.transformer.layers.19.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.945
- `model.transformer.layers.18.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.936