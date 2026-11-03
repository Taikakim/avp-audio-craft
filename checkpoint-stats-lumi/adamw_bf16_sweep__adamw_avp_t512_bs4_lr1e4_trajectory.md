# Checkpoint trajectory — adamw_bf16_sweep__adamw_avp_t512_bs4_lr1e4

- checkpoints: **10** (steps 598–5980)
- net displacement ||W_last−W_0||: **83.797**
- total path length Σ‖ΔW‖: **235.557**
- **path efficiency** (net/path): **0.356**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 5.0** (step 2990)
- peak learning velocity: epoch 2.0 (‖ΔW‖=26.638)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 102.90 | 0.000 | 0.000 | 83.797 | 0.7820 | 0.000 |
| 2.0 | 106.69 | 26.638 | 26.638 | 77.564 | 0.8169 | 0.000 |
| 3.0 | 110.33 | 37.832 | 26.170 | 71.392 | 0.8476 | 0.026 |
| 4.0 | 113.96 | 46.753 | 26.085 | 65.168 | 0.8750 | 0.015 |
| 5.0 | 117.57 | 54.458 | 26.191 | 58.746 | 0.8997 | 0.006 |
| 6.0 | 121.14 | 61.345 | 26.223 | 52.011 | 0.9223 | -0.003 |
| 7.0 | 124.48 | 67.506 | 25.841 | 44.856 | 0.9428 | -0.006 |
| 8.0 | 127.93 | 73.380 | 26.160 | 36.591 | 0.9623 | -0.006 |
| 9.0 | 131.14 | 78.678 | 26.095 | 26.153 | 0.9809 | -0.016 |
| 10.0 | 134.39 | 83.797 | 26.153 | 0.000 | 1.0000 | -0.019 |

## Top moving layers (total velocity)

- `model.transformer.layers.21.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.534
- `model.transformer.layers.20.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.392
- `model.transformer.layers.22.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.273
- `model.transformer.layers.17.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.219
- `model.transformer.layers.8.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.034
- `model.transformer.layers.9.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 23.889
- `model.transformer.layers.2.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 23.835
- `model.transformer.layers.18.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 23.753