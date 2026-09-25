# Checkpoint trajectory — goa3_avp_r128_shampoo_b16_3e4_2026-09-25

- checkpoints: **8** (steps 1268–10144)
- net displacement ||W_last−W_0||: **19.994**
- total path length Σ‖ΔW‖: **29.290**
- **path efficiency** (net/path): **0.683**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 5072)
- peak learning velocity: epoch 2.0 (‖ΔW‖=6.221)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 99.33 | 0.000 | 0.000 | 19.994 | 0.9805 | 0.000 |
| 2.0 | 99.71 | 6.221 | 6.221 | 17.053 | 0.9859 | 0.000 |
| 3.0 | 100.05 | 9.531 | 5.033 | 14.224 | 0.9902 | 0.428 |
| 4.0 | 100.42 | 12.214 | 4.330 | 11.489 | 0.9936 | 0.581 |
| 5.0 | 100.78 | 14.505 | 3.845 | 8.755 | 0.9963 | 0.664 |
| 6.0 | 101.10 | 16.550 | 3.579 | 5.910 | 0.9983 | 0.702 |
| 7.0 | 101.44 | 18.331 | 3.249 | 3.033 | 0.9996 | 0.734 |
| 8.0 | 101.78 | 19.994 | 3.033 | 0.000 | 1.0000 | 0.770 |

## Top moving layers (total velocity)

- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 3.654
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 3.637
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 3.600
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 3.580
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 3.565
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 3.499
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 3.467
- `model.transformer.layers.19.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 3.399