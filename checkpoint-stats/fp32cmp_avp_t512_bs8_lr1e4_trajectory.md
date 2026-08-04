# Checkpoint trajectory — fp32cmp_avp_t512_bs8_lr1e4

- checkpoints: **8** (steps 299–2392)
- net displacement ||W_last−W_0||: **149.642**
- total path length Σ‖ΔW‖: **210.798**
- **path efficiency** (net/path): **0.710**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 1196)
- peak learning velocity: epoch 2.0 (‖ΔW‖=42.818)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 117.82 | 0.000 | 0.000 | 149.642 | 0.6614 | 0.000 |
| 2.0 | 132.50 | 42.818 | 42.818 | 128.300 | 0.7706 | 0.000 |
| 3.0 | 145.50 | 69.552 | 35.228 | 107.423 | 0.8494 | 0.585 |
| 4.0 | 157.49 | 90.342 | 31.079 | 86.427 | 0.9078 | 0.667 |
| 5.0 | 168.69 | 107.877 | 28.248 | 65.325 | 0.9498 | 0.709 |
| 6.0 | 179.26 | 123.270 | 26.245 | 43.988 | 0.9781 | 0.725 |
| 7.0 | 189.24 | 137.058 | 24.251 | 22.929 | 0.9942 | 0.742 |
| 8.0 | 198.70 | 149.642 | 22.929 | 0.000 | 1.0000 | 0.738 |

## Top moving layers (total velocity)

- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 25.272
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 25.240
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 25.144
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 25.118
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 25.013
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.910
- `model.transformer.layers.4.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.877
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.847