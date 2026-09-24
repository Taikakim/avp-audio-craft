# Checkpoint trajectory — dora128_mix3_nodas

- checkpoints: **15** (steps 500–7500)
- net displacement ||W_last−W_0||: **8933.482**
- total path length Σ‖ΔW‖: **63326.825**
- **path efficiency** (net/path): **0.141**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 1.3** (step 7000)
- peak learning velocity: epoch 0.37 (‖ΔW‖=7652.150)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 0.09 | 712.29 | 0.000 | 0.000 | 8933.482 | 0.0180 | 0.000 |
| 0.19 | 1349.26 | 1217.792 | 1217.792 | 8965.253 | 0.0404 | 0.000 |
| 0.28 | 1715.93 | 1646.150 | 1255.668 | 8980.532 | 0.0596 | -0.114 |
| 0.37 | 7851.43 | 7835.609 | 7652.150 | 10416.098 | 0.2334 | 0.005 |
| 0.46 | 8812.09 | 8800.328 | 4543.119 | 10655.173 | 0.2777 | -0.062 |
| 0.56 | 8754.19 | 8746.551 | 4056.295 | 10271.949 | 0.3244 | -0.096 |
| 0.65 | 10658.58 | 10655.037 | 6874.106 | 10498.068 | 0.4362 | 0.091 |
| 0.74 | 11806.80 | 11805.836 | 5850.455 | 10614.329 | 0.5046 | 0.091 |
| 0.83 | 12189.54 | 12191.257 | 6526.838 | 10016.795 | 0.5877 | -0.055 |
| 0.93 | 11193.82 | 11198.068 | 4194.268 | 8835.755 | 0.6349 | -0.130 |
| 1.02 | 11490.44 | 11496.665 | 6280.021 | 7680.320 | 0.7445 | 0.027 |
| 1.11 | 10670.66 | 10679.353 | 3933.075 | 6386.365 | 0.8018 | -0.096 |
| 1.2 | 9905.90 | 9917.129 | 3733.993 | 5057.914 | 0.8607 | 0.047 |
| 1.3 | 9343.88 | 9357.394 | 3635.361 | 3573.683 | 0.9245 | 0.026 |
| 1.39 | 8917.87 | 8933.482 | 3573.683 | 0.000 | 1.0000 | -0.016 |

## Top moving layers (total velocity)

- `model.transformer.layers.3.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 8357.918
- `model.transformer.layers.5.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 8357.352
- `model.transformer.layers.1.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 8352.691
- `model.transformer.layers.7.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 8343.255
- `model.transformer.layers.4.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 8331.517
- `model.transformer.layers.2.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 8321.691
- `model.transformer.layers.6.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 8321.233
- `model.transformer.layers.9.ff.ff.0.proj.parametrizations.weight.0.lora_B`: 8270.887