# Checkpoint trajectory — goa3_avp_r128_shampoo_b16_3e4_2026-09-25

- checkpoints: **4** (steps 1268–5072)
- net displacement ||W_last−W_0||: **12.214**
- total path length Σ‖ΔW‖: **15.584**
- **path efficiency** (net/path): **0.784**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 2.0** (step 2536)
- peak learning velocity: epoch 2.0 (‖ΔW‖=6.221)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 99.33 | 0.000 | 0.000 | 12.214 | 0.9926 | 0.000 |
| 2.0 | 99.71 | 6.221 | 6.221 | 8.331 | 0.9966 | 0.000 |
| 3.0 | 100.05 | 9.531 | 5.033 | 4.330 | 0.9991 | 0.428 |
| 4.0 | 100.42 | 12.214 | 4.330 | 0.000 | 1.0000 | 0.581 |

## Top moving layers (total velocity)

- `model.to_cond_embed.2.parametrizations.weight.0.lora_A`: 2.131
- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 1.913
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 1.893
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 1.890
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 1.877
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 1.862
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 1.843
- `model.transformer.layers.0.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 1.836