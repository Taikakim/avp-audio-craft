# Checkpoint trajectory — dora128_mix3_overnight

- checkpoints: **8** (steps 500–4000)
- net displacement ||W_last−W_0||: **10402.573**
- total path length Σ‖ΔW‖: **45295.391**
- **path efficiency** (net/path): **0.230**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 0.46** (step 2500)
- peak learning velocity: epoch 0.19 (‖ΔW‖=8705.141)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 0.09 | 4085.26 | 0.000 | 0.000 | 10402.574 | 0.1492 | 0.000 |
| 0.19 | 9575.44 | 8705.141 | 8705.141 | 11363.142 | 0.3407 | 0.000 |
| 0.28 | 10390.78 | 9847.529 | 6661.707 | 10941.100 | 0.4352 | -0.200 |
| 0.37 | 10471.33 | 10142.441 | 6093.564 | 10146.268 | 0.5182 | -0.124 |
| 0.46 | 10432.15 | 10276.937 | 5993.208 | 9148.162 | 0.6069 | -0.103 |
| 0.56 | 10357.48 | 10347.233 | 5976.777 | 7847.292 | 0.7086 | -0.109 |
| 0.65 | 10315.72 | 10420.999 | 5954.876 | 5910.118 | 0.8340 | -0.117 |
| 0.74 | 10195.70 | 10402.574 | 5910.118 | 0.000 | 1.0000 | -0.125 |

## Top moving layers (total velocity)

- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5809.323
- `model.transformer.layers.4.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5800.891
- `model.transformer.layers.3.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5747.169
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5733.445
- `model.transformer.layers.8.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5721.992
- `model.transformer.layers.6.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5717.417
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5714.830
- `model.transformer.layers.0.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5701.488