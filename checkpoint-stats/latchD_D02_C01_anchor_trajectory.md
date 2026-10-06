# Checkpoint trajectory — latchD_D02_C01_anchor

- checkpoints: **10** (steps 743–7430)
- net displacement ||W_last−W_0||: **289.622**
- total path length Σ‖ΔW‖: **617.630**
- **path efficiency** (net/path): **0.469**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 6.0** (step 4458)
- peak learning velocity: epoch 2.0 (‖ΔW‖=131.669)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 138.17 | 0.000 | 0.000 | 289.622 | 0.3902 | 0.000 |
| 2.0 | 197.25 | 131.669 | 131.669 | 266.333 | 0.5377 | 0.000 |
| 3.0 | 219.58 | 166.448 | 93.122 | 242.925 | 0.6369 | 0.069 |
| 4.0 | 238.54 | 192.919 | 76.480 | 217.213 | 0.7232 | 0.324 |
| 5.0 | 255.14 | 214.828 | 65.807 | 188.604 | 0.7997 | 0.489 |
| 6.0 | 269.25 | 233.187 | 58.371 | 156.898 | 0.8663 | 0.583 |
| 7.0 | 281.91 | 249.233 | 53.320 | 122.048 | 0.9217 | 0.650 |
| 8.0 | 293.20 | 263.842 | 49.535 | 83.886 | 0.9642 | 0.699 |
| 9.0 | 303.98 | 277.237 | 45.959 | 43.367 | 0.9907 | 0.739 |
| 10.0 | 314.09 | 289.622 | 43.367 | 0.000 | 1.0000 | 0.764 |

## Top moving layers (total velocity)

- `blocks.2.adaLN_mod.1.weight`: 176.941
- `blocks.1.adaLN_mod.1.weight`: 176.248
- `blocks.0.adaLN_mod.1.weight`: 176.005
- `blocks.3.adaLN_mod.1.weight`: 172.946
- `blocks.3.mlp.0.weight`: 145.012
- `blocks.0.mlp.0.weight`: 133.586
- `blocks.1.mlp.0.weight`: 133.579
- `blocks.2.mlp.0.weight`: 131.558