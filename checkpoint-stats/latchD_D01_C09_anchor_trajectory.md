# Checkpoint trajectory — latchD_D01_C09_anchor

- checkpoints: **10** (steps 743–7430)
- net displacement ||W_last−W_0||: **244.256**
- total path length Σ‖ΔW‖: **582.879**
- **path efficiency** (net/path): **0.419**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 6.0** (step 4458)
- peak learning velocity: epoch 2.0 (‖ΔW‖=123.418)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 125.90 | 0.000 | 0.000 | 244.256 | 0.3388 | 0.000 |
| 2.0 | 176.07 | 123.418 | 123.418 | 232.073 | 0.4744 | 0.000 |
| 3.0 | 192.63 | 152.770 | 88.668 | 214.741 | 0.5739 | 0.011 |
| 4.0 | 207.97 | 175.072 | 72.914 | 194.347 | 0.6675 | 0.279 |
| 5.0 | 220.44 | 192.453 | 62.350 | 170.587 | 0.7538 | 0.448 |
| 6.0 | 230.21 | 206.274 | 55.283 | 143.206 | 0.8319 | 0.545 |
| 7.0 | 237.39 | 217.471 | 50.661 | 111.755 | 0.9003 | 0.614 |
| 8.0 | 244.12 | 227.388 | 46.453 | 77.325 | 0.9534 | 0.670 |
| 9.0 | 250.27 | 236.343 | 43.162 | 39.969 | 0.9878 | 0.709 |
| 10.0 | 256.26 | 244.256 | 39.969 | 0.000 | 1.0000 | 0.730 |

## Top moving layers (total velocity)

- `blocks.1.adaLN_mod.1.weight`: 171.280
- `blocks.2.adaLN_mod.1.weight`: 170.608
- `blocks.0.adaLN_mod.1.weight`: 170.197
- `blocks.3.adaLN_mod.1.weight`: 168.172
- `blocks.3.mlp.0.weight`: 137.611
- `blocks.2.mlp.0.weight`: 129.466
- `blocks.0.mlp.0.weight`: 128.458
- `blocks.1.mlp.0.weight`: 127.495