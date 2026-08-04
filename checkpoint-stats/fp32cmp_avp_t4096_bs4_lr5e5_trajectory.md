# Checkpoint trajectory — fp32cmp_avp_t4096_bs4_lr5e5

- checkpoints: **8** (steps 598–4784)
- net displacement ||W_last−W_0||: **122.090**
- total path length Σ‖ΔW‖: **162.877**
- **path efficiency** (net/path): **0.750**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 2392)
- peak learning velocity: epoch 2.0 (‖ΔW‖=32.679)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 109.59 | 0.000 | 0.000 | 122.090 | 0.7091 | 0.000 |
| 2.0 | 119.39 | 32.679 | 32.679 | 103.977 | 0.8050 | 0.000 |
| 3.0 | 128.92 | 54.078 | 27.243 | 86.252 | 0.8748 | 0.626 |
| 4.0 | 138.21 | 71.255 | 23.976 | 68.985 | 0.9244 | 0.714 |
| 5.0 | 147.14 | 85.921 | 21.818 | 51.889 | 0.9593 | 0.744 |
| 6.0 | 155.76 | 99.018 | 20.204 | 34.894 | 0.9824 | 0.767 |
| 7.0 | 164.11 | 110.974 | 18.980 | 17.977 | 0.9954 | 0.778 |
| 8.0 | 172.24 | 122.090 | 17.977 | 0.000 | 1.0000 | 0.783 |

## Top moving layers (total velocity)

- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 20.909
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 20.845
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 20.568
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 20.334
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 20.129
- `model.transformer.layers.19.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 20.080
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 20.067
- `model.transformer.layers.18.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 19.979