# Checkpoint trajectory — goa3_avp_r128_20260923

- checkpoints: **3** (steps 1268–3804)
- net displacement ||W_last−W_0||: **85.324**
- total path length Σ‖ΔW‖: **106.009**
- **path efficiency** (net/path): **0.805**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 2536)
- peak learning velocity: epoch 4.0 (‖ΔW‖=58.530)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 2.0 | 121.89 | 0.000 | 0.000 | 85.324 | 0.8222 | 0.000 |
| 4.0 | 136.73 | 58.530 | 58.530 | 47.479 | 0.9492 | 0.000 |
| 6.0 | 149.87 | 85.324 | 47.479 | 0.000 | 1.0000 | 0.288 |

## Top moving layers (total velocity)

- `model.transformer.layers.4.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 13.041
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 13.011
- `model.transformer.layers.3.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 12.996
- `model.transformer.layers.7.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 12.939
- `model.transformer.layers.6.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 12.937
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 12.860
- `model.transformer.layers.8.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 12.818
- `model.transformer.layers.2.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 12.789