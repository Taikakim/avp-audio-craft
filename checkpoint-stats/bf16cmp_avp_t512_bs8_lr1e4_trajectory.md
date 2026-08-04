# Checkpoint trajectory — bf16cmp_avp_t512_bs8_lr1e4

- checkpoints: **8** (steps 299–2392)
- net displacement ||W_last−W_0||: **149.126**
- total path length Σ‖ΔW‖: **209.798**
- **path efficiency** (net/path): **0.711**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 1196)
- peak learning velocity: epoch 2.0 (‖ΔW‖=42.500)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 118.21 | 0.000 | 0.000 | 149.126 | 0.6635 | 0.000 |
| 2.0 | 132.61 | 42.500 | 42.500 | 127.832 | 0.7721 | 0.000 |
| 3.0 | 145.55 | 69.224 | 35.133 | 106.811 | 0.8511 | 0.587 |
| 4.0 | 157.47 | 90.007 | 30.843 | 85.994 | 0.9086 | 0.674 |
| 5.0 | 168.60 | 107.465 | 28.030 | 65.138 | 0.9500 | 0.708 |
| 6.0 | 179.12 | 122.788 | 26.026 | 44.047 | 0.9780 | 0.726 |
| 7.0 | 189.06 | 136.561 | 24.234 | 23.033 | 0.9941 | 0.738 |
| 8.0 | 198.51 | 149.126 | 23.033 | 0.000 | 1.0000 | 0.737 |

## Top moving layers (total velocity)

- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 25.228
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 25.184
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 25.135
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 25.067
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.980
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.798
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.665
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 24.634