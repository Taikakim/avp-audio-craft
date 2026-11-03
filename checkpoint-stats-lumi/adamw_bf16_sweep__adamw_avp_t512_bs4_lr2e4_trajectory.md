# Checkpoint trajectory — adamw_bf16_sweep__adamw_avp_t512_bs4_lr2e4

- checkpoints: **10** (steps 598–5980)
- net displacement ||W_last−W_0||: **153.141**
- total path length Σ‖ΔW‖: **462.642**
- **path efficiency** (net/path): **0.331**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 5.0** (step 2990)
- peak learning velocity: epoch 2.0 (‖ΔW‖=51.798)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 112.20 | 0.000 | 0.000 | 153.141 | 0.5945 | 0.000 |
| 2.0 | 123.65 | 51.798 | 51.798 | 143.090 | 0.6600 | 0.000 |
| 3.0 | 133.97 | 72.544 | 51.016 | 133.048 | 0.7156 | -0.004 |
| 4.0 | 143.73 | 88.917 | 51.318 | 122.514 | 0.7657 | -0.009 |
| 5.0 | 152.73 | 102.647 | 51.370 | 111.593 | 0.8104 | -0.018 |
| 6.0 | 161.26 | 114.805 | 51.528 | 99.810 | 0.8517 | -0.023 |
| 7.0 | 168.99 | 125.460 | 51.151 | 86.858 | 0.8899 | -0.031 |
| 8.0 | 176.61 | 135.473 | 51.461 | 71.460 | 0.9269 | -0.029 |
| 9.0 | 183.57 | 144.499 | 51.372 | 51.628 | 0.9626 | -0.033 |
| 10.0 | 190.44 | 153.141 | 51.628 | 0.000 | 1.0000 | -0.037 |

## Top moving layers (total velocity)

- `model.transformer.layers.17.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 48.188
- `model.transformer.layers.21.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 48.186
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 48.068
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 48.020
- `model.transformer.layers.20.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 48.018
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.895
- `model.transformer.layers.8.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.803
- `model.transformer.layers.9.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.782