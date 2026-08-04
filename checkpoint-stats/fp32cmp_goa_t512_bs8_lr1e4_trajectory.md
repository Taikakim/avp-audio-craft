# Checkpoint trajectory — fp32cmp_goa_t512_bs8_lr1e4

- checkpoints: **8** (steps 675–5400)
- net displacement ||W_last−W_0||: **206.948**
- total path length Σ‖ΔW‖: **302.173**
- **path efficiency** (net/path): **0.685**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 2700)
- peak learning velocity: epoch 2.0 (‖ΔW‖=62.075)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 134.35 | 0.000 | 0.000 | 206.948 | 0.5902 | 0.000 |
| 2.0 | 159.01 | 62.075 | 62.075 | 178.099 | 0.7244 | 0.000 |
| 3.0 | 179.57 | 99.714 | 50.975 | 149.389 | 0.8197 | 0.552 |
| 4.0 | 197.66 | 128.351 | 44.724 | 120.334 | 0.8898 | 0.635 |
| 5.0 | 213.96 | 152.003 | 40.262 | 91.192 | 0.9398 | 0.679 |
| 6.0 | 228.87 | 172.402 | 37.027 | 61.925 | 0.9733 | 0.698 |
| 7.0 | 242.68 | 190.557 | 34.508 | 32.603 | 0.9928 | 0.708 |
| 8.0 | 255.55 | 206.948 | 32.603 | 0.000 | 1.0000 | 0.703 |

## Top moving layers (total velocity)

- `model.transformer.layers.4.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.503
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.434
- `model.transformer.layers.6.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.335
- `model.transformer.layers.3.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.274
- `model.transformer.layers.7.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.225
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.000
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.942
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.914