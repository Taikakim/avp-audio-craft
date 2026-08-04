# Checkpoint trajectory — longctx_t2048_r128

- checkpoints: **8** (steps 675–5400)
- net displacement ||W_last−W_0||: **215.012**
- total path length Σ‖ΔW‖: **308.383**
- **path efficiency** (net/path): **0.697**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 2700)
- peak learning velocity: epoch 2.0 (‖ΔW‖=62.784)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 132.09 | 0.000 | 0.000 | 215.012 | 0.5861 | 0.000 |
| 2.0 | 158.03 | 62.784 | 62.784 | 184.594 | 0.7258 | 0.000 |
| 3.0 | 180.28 | 101.523 | 51.821 | 154.684 | 0.8220 | 0.566 |
| 4.0 | 200.00 | 131.367 | 45.436 | 124.653 | 0.8915 | 0.650 |
| 5.0 | 217.88 | 156.280 | 41.164 | 94.484 | 0.9408 | 0.692 |
| 6.0 | 234.30 | 177.945 | 37.995 | 64.191 | 0.9738 | 0.710 |
| 7.0 | 249.56 | 197.328 | 35.541 | 33.641 | 0.9930 | 0.718 |
| 8.0 | 263.89 | 215.012 | 33.641 | 0.000 | 1.0000 | 0.722 |

## Top moving layers (total velocity)

- `model.transformer.layers.7.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.263
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.241
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.207
- `model.transformer.layers.6.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.175
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.164
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.149
- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.136
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 37.134