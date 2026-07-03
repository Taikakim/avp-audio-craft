# Checkpoint trajectory — fusioncaut_lr1e-4

- checkpoints: **10** (steps 5400–54000)
- net displacement ||W_last−W_0||: **29.838**
- total path length Σ‖ΔW‖: **40.029**
- **path efficiency** (net/path): **0.745**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 5.0** (step 27000)
- peak learning velocity: epoch 2.0 (‖ΔW‖=7.172)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 157.59 | 0.000 | 0.000 | 29.838 | 0.9821 | 0.000 |
| 2.0 | 157.58 | 7.172 | 7.172 | 26.143 | 0.9862 | 0.000 |
| 3.0 | 157.55 | 11.649 | 5.670 | 22.683 | 0.9896 | 0.641 |
| 4.0 | 157.53 | 15.209 | 4.922 | 19.328 | 0.9925 | 0.747 |
| 5.0 | 157.51 | 18.248 | 4.411 | 16.031 | 0.9948 | 0.799 |
| 6.0 | 157.50 | 20.956 | 4.049 | 12.762 | 0.9967 | 0.834 |
| 7.0 | 157.50 | 23.426 | 3.777 | 9.522 | 0.9982 | 0.859 |
| 8.0 | 157.50 | 25.707 | 3.531 | 6.324 | 0.9992 | 0.875 |
| 9.0 | 157.50 | 27.831 | 3.327 | 3.170 | 0.9998 | 0.886 |
| 10.0 | 157.51 | 29.838 | 3.170 | 0.000 | 1.0000 | 0.895 |

## Top moving layers (total velocity)

- `conditioner.film.2.weight`: 14.051
- `adapter.19.to_out.weight`: 5.365
- `adapter.18.to_out.weight`: 5.347
- `adapter.15.to_out.weight`: 5.340
- `adapter.16.to_out.weight`: 5.326
- `adapter.17.to_out.weight`: 5.305
- `adapter.20.to_out.weight`: 5.253
- `adapter.14.to_out.weight`: 5.182