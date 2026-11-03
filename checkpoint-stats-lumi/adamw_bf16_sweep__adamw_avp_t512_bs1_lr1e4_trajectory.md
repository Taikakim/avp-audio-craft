# Checkpoint trajectory — adamw_bf16_sweep__adamw_avp_t512_bs1_lr1e4

- checkpoints: **10** (steps 2393–23930)
- net displacement ||W_last−W_0||: **151.622**
- total path length Σ‖ΔW‖: **455.391**
- **path efficiency** (net/path): **0.333**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 5.0** (step 11965)
- peak learning velocity: epoch 2.0 (‖ΔW‖=51.108)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 112.09 | 0.000 | 0.000 | 151.622 | 0.6005 | 0.000 |
| 2.0 | 123.69 | 51.108 | 51.108 | 140.974 | 0.6689 | 0.000 |
| 3.0 | 134.24 | 72.287 | 50.827 | 130.415 | 0.7261 | 0.006 |
| 4.0 | 144.00 | 88.607 | 50.785 | 119.678 | 0.7758 | -0.011 |
| 5.0 | 152.98 | 102.294 | 50.682 | 108.701 | 0.8194 | -0.020 |
| 6.0 | 161.21 | 114.117 | 50.397 | 97.186 | 0.8587 | -0.030 |
| 7.0 | 168.88 | 124.658 | 50.380 | 84.397 | 0.8955 | -0.036 |
| 8.0 | 176.27 | 134.448 | 50.474 | 69.585 | 0.9302 | -0.038 |
| 9.0 | 183.03 | 143.271 | 50.380 | 50.356 | 0.9641 | -0.043 |
| 10.0 | 189.60 | 151.622 | 50.356 | 0.000 | 1.0000 | -0.046 |

## Top moving layers (total velocity)

- `model.transformer.layers.21.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.764
- `model.transformer.layers.20.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.630
- `model.transformer.layers.17.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.573
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.491
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.387
- `model.transformer.layers.9.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.255
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.219
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 47.218