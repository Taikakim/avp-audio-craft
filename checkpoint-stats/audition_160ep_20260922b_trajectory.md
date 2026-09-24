# Checkpoint trajectory — audition_160ep_20260922b

- checkpoints: **6** (steps 240–1440)
- net displacement ||W_last−W_0||: **41.799**
- total path length Σ‖ΔW‖: **55.912**
- **path efficiency** (net/path): **0.748**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 80.0** (step 720)
- peak learning velocity: epoch 53.33 (‖ΔW‖=14.248)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 26.67 | 100.00 | 0.000 | 0.000 | 41.799 | 0.9233 | 0.000 |
| 53.33 | 101.63 | 14.248 | 14.248 | 33.913 | 0.9503 | 0.000 |
| 80.0 | 103.44 | 22.919 | 12.159 | 25.824 | 0.9716 | 0.503 |
| 106.67 | 105.25 | 30.041 | 10.755 | 17.548 | 0.9871 | 0.634 |
| 133.33 | 107.02 | 36.203 | 9.728 | 9.022 | 0.9966 | 0.703 |
| 160.0 | 108.79 | 41.799 | 9.022 | 0.000 | 1.0000 | 0.751 |

## Top moving layers (total velocity)

- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 7.308
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 7.298
- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 7.243
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 7.228
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 7.208
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 7.105
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 7.092
- `model.transformer.layers.9.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 6.922