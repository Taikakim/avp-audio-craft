# Checkpoint trajectory — fp32cmp_avp_t4096_bs1_lr1e4

- checkpoints: **8** (steps 2393–19144)
- net displacement ||W_last−W_0||: **386.634**
- total path length Σ‖ΔW‖: **570.193**
- **path efficiency** (net/path): **0.678**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 4.0** (step 9572)
- peak learning velocity: epoch 2.0 (‖ΔW‖=117.755)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 190.54 | 0.000 | 0.000 | 386.634 | 0.5283 | 0.000 |
| 2.0 | 250.04 | 117.755 | 117.755 | 331.921 | 0.6926 | 0.000 |
| 3.0 | 296.94 | 189.149 | 96.841 | 277.746 | 0.8019 | 0.549 |
| 4.0 | 336.27 | 243.020 | 84.347 | 223.871 | 0.8790 | 0.633 |
| 5.0 | 370.34 | 287.067 | 75.754 | 170.146 | 0.9333 | 0.670 |
| 6.0 | 400.39 | 324.542 | 69.793 | 115.660 | 0.9703 | 0.681 |
| 7.0 | 427.39 | 357.413 | 64.919 | 60.784 | 0.9920 | 0.692 |
| 8.0 | 451.82 | 386.634 | 60.784 | 0.000 | 1.0000 | 0.693 |

## Top moving layers (total velocity)

- `model.transformer.layers.14.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 69.122
- `model.transformer.layers.13.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 68.448
- `model.transformer.layers.15.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 68.421
- `model.transformer.layers.12.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 68.034
- `model.transformer.layers.11.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 67.288
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 67.004
- `model.transformer.layers.4.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 66.908
- `model.transformer.layers.6.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 66.752