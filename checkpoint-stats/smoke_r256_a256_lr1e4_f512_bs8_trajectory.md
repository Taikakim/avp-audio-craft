# Checkpoint trajectory — smoke_r256_a256_lr1e4_f512_bs8

- checkpoints: **3** (steps 100–300)
- net displacement ||W_last−W_0||: **39.484**
- total path length Σ‖ΔW‖: **43.907**
- **path efficiency** (net/path): **0.899**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 2.0** (step 200)
- peak learning velocity: epoch 2.0 (‖ΔW‖=24.165)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 144.70 | 0.000 | 0.000 | 39.484 | 0.9662 | 0.000 |
| 2.0 | 148.94 | 24.165 | 24.165 | 19.741 | 0.9917 | 0.000 |
| 3.0 | 152.68 | 39.484 | 19.741 | 0.000 | 1.0000 | 0.613 |

## Top moving layers (total velocity)

- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5.537
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5.511
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5.504
- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5.494
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5.470
- `model.transformer.layers.10.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5.466
- `model.transformer.layers.16.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5.429
- `model.transformer.layers.9.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 5.399