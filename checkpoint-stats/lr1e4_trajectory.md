# Checkpoint trajectory — lr1e4

- checkpoints: **5** (steps 1000–5000)
- net displacement ||W_last−W_0||: **8.937**
- total path length Σ‖ΔW‖: **10.837**
- **path efficiency** (net/path): **0.825**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 0.56** (step 3000)
- peak learning velocity: epoch 0.37 (‖ΔW‖=3.728)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 0.19 | 157.46 | 0.000 | 0.000 | 8.937 | 0.9984 | 0.000 |
| 0.37 | 157.54 | 3.728 | 3.728 | 6.324 | 0.9992 | 0.000 |
| 0.56 | 157.57 | 5.937 | 2.775 | 4.086 | 0.9997 | 0.660 |
| 0.74 | 157.59 | 7.580 | 2.308 | 2.026 | 0.9999 | 0.740 |
| 0.93 | 157.60 | 8.937 | 2.026 | 0.000 | 1.0000 | 0.777 |

## Top moving layers (total velocity)

- `conditioner.film.2.weight`: 3.760
- `adapter.0.to_v.weight`: 1.656
- `conditioner.film.2.bias`: 1.495
- `adapter.1.to_v.weight`: 1.447
- `adapter.2.to_v.weight`: 1.395
- `adapter.0.to_k.weight`: 1.388
- `conditioner.tokens`: 1.322
- `adapter.0.to_out.weight`: 1.317