# Checkpoint trajectory — modular_sfswap_20260921

- checkpoints: **6** (steps 100–2500)
- net displacement ||W_last−W_0||: **71.264**
- total path length Σ‖ΔW‖: **107.569**
- **path efficiency** (net/path): **0.662**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 100.0** (step 1000)
- peak learning velocity: epoch 50.0 (‖ΔW‖=27.162)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 10.0 | 99.27 | 0.000 | 0.000 | 71.264 | 0.7932 | 0.000 |
| 50.0 | 102.30 | 27.162 | 27.162 | 59.987 | 0.8575 | 0.000 |
| 100.0 | 106.44 | 42.049 | 24.497 | 46.262 | 0.9178 | 0.323 |
| 150.0 | 110.35 | 53.834 | 21.082 | 31.688 | 0.9624 | 0.498 |
| 200.0 | 113.74 | 63.419 | 18.441 | 16.387 | 0.9901 | 0.600 |
| 250.0 | 116.49 | 71.264 | 16.387 | 0.000 | 1.0000 | 0.654 |

## Top moving layers (total velocity)

- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 13.728
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 13.679
- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 13.651
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 13.643
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 13.527
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 13.355
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 13.324
- `model.transformer.layers.9.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 13.029