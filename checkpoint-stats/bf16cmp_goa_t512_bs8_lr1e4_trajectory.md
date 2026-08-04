# Checkpoint trajectory — bf16cmp_goa_t512_bs8_lr1e4

- checkpoints: **8** (steps 675–5400)
- net displacement ||W_last−W_0||: **205.997**
- total path length Σ‖ΔW‖: **300.875**
- **path efficiency** (net/path): **0.685**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 2700)
- peak learning velocity: epoch 2.0 (‖ΔW‖=61.951)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 134.35 | 0.000 | 0.000 | 205.997 | 0.5920 | 0.000 |
| 2.0 | 158.87 | 61.951 | 61.951 | 177.142 | 0.7260 | 0.000 |
| 3.0 | 179.33 | 99.378 | 50.779 | 148.547 | 0.8208 | 0.550 |
| 4.0 | 197.31 | 127.827 | 44.371 | 119.761 | 0.8902 | 0.637 |
| 5.0 | 213.47 | 151.316 | 39.922 | 90.913 | 0.9397 | 0.681 |
| 6.0 | 228.24 | 171.587 | 36.775 | 61.931 | 0.9731 | 0.698 |
| 7.0 | 241.97 | 189.654 | 34.499 | 32.579 | 0.9927 | 0.703 |
| 8.0 | 254.79 | 205.997 | 32.579 | 0.000 | 1.0000 | 0.705 |

## Top moving layers (total velocity)

- `model.transformer.layers.4.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.158
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.143
- `model.transformer.layers.7.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.089
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.043
- `model.transformer.layers.6.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.022
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 36.015
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.920
- `model.transformer.layers.3.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 35.913