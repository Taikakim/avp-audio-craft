# Checkpoint trajectory — adamw_bf16_sweep__adamw_avp_t512_bs4_lr5e5

- checkpoints: **10** (steps 598–5980)
- net displacement ||W_last−W_0||: **45.832**
- total path length Σ‖ΔW‖: **119.194**
- **path efficiency** (net/path): **0.385**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 5.0** (step 2990)
- peak learning velocity: epoch 2.0 (‖ΔW‖=13.846)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 100.40 | 0.000 | 0.000 | 45.832 | 0.9122 | 0.000 |
| 2.0 | 101.68 | 13.846 | 13.846 | 41.889 | 0.9273 | 0.000 |
| 3.0 | 102.89 | 19.965 | 13.361 | 38.100 | 0.9404 | 0.077 |
| 4.0 | 104.15 | 24.892 | 13.216 | 34.420 | 0.9516 | 0.055 |
| 5.0 | 105.36 | 29.076 | 13.092 | 30.808 | 0.9615 | 0.033 |
| 6.0 | 106.67 | 32.960 | 13.163 | 27.067 | 0.9704 | 0.027 |
| 7.0 | 107.90 | 36.400 | 13.055 | 23.091 | 0.9785 | 0.015 |
| 8.0 | 109.17 | 39.677 | 13.120 | 18.663 | 0.9860 | 0.010 |
| 9.0 | 110.47 | 42.830 | 13.213 | 13.128 | 0.9931 | 0.005 |
| 10.0 | 111.80 | 45.832 | 13.128 | 0.000 | 1.0000 | 0.004 |

## Top moving layers (total velocity)

- `model.transformer.layers.21.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 12.256
- `model.transformer.layers.23.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 12.235
- `model.transformer.layers.22.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 12.189
- `model.transformer.layers.20.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 12.181
- `model.transformer.layers.17.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 11.998
- `model.transformer.layers.8.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 11.956
- `model.transformer.layers.9.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 11.845
- `model.transformer.layers.2.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 11.744