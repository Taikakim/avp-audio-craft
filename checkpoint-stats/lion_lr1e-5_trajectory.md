# Checkpoint trajectory — lion_lr1e-5

- checkpoints: **4** (steps 1000–4000)
- net displacement ||W_last−W_0||: **62.069**
- total path length Σ‖ΔW‖: **93.507**
- **path efficiency** (net/path): **0.664**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 0.37** (step 2000)
- peak learning velocity: epoch 0.56 (‖ΔW‖=32.037)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 0.19 | 106.04 | 0.000 | 0.000 | 62.069 | 0.8771 | 0.000 |
| 0.37 | 113.73 | 32.003 | 32.003 | 46.625 | 0.9331 | 0.000 |
| 0.56 | 121.46 | 49.352 | 32.037 | 29.467 | 0.9738 | 0.188 |
| 0.74 | 128.47 | 62.069 | 29.467 | 0.000 | 1.0000 | 0.148 |

## Top moving layers (total velocity)

- `model.transformer.layers.4.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 9.351
- `model.transformer.layers.3.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 9.303
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 9.289
- `model.transformer.layers.23.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 9.277
- `model.transformer.layers.2.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 9.231
- `model.transformer.layers.1.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 9.161
- `model.transformer.layers.21.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 9.052
- `model.transformer.layers.6.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 9.046