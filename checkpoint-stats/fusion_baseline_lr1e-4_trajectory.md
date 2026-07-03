# Checkpoint trajectory — fusion_baseline_lr1e-4

- checkpoints: **10** (steps 5400–54000)
- net displacement ||W_last−W_0||: **28.561**
- total path length Σ‖ΔW‖: **38.681**
- **path efficiency** (net/path): **0.738**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 5.0** (step 27000)
- peak learning velocity: epoch 2.0 (‖ΔW‖=7.023)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 157.71 | 0.000 | 0.000 | 28.561 | 0.9836 | 0.000 |
| 2.0 | 157.66 | 7.023 | 7.023 | 25.008 | 0.9874 | 0.000 |
| 3.0 | 157.57 | 11.321 | 5.486 | 21.718 | 0.9905 | 0.633 |
| 4.0 | 157.49 | 14.692 | 4.731 | 18.539 | 0.9931 | 0.739 |
| 5.0 | 157.42 | 17.568 | 4.234 | 15.406 | 0.9952 | 0.793 |
| 6.0 | 157.36 | 20.122 | 3.885 | 12.292 | 0.9970 | 0.827 |
| 7.0 | 157.31 | 22.460 | 3.633 | 9.189 | 0.9983 | 0.855 |
| 8.0 | 157.26 | 24.625 | 3.406 | 6.111 | 0.9992 | 0.871 |
| 9.0 | 157.22 | 26.646 | 3.217 | 3.066 | 0.9998 | 0.883 |
| 10.0 | 157.18 | 28.561 | 3.066 | 0.000 | 1.0000 | 0.892 |

## Top moving layers (total velocity)

- `conditioner.film.2.weight`: 14.527
- `adapter.19.to_out.weight`: 5.280
- `adapter.18.to_out.weight`: 5.265
- `adapter.16.to_out.weight`: 5.232
- `adapter.15.to_out.weight`: 5.219
- `adapter.17.to_out.weight`: 5.210
- `adapter.20.to_out.weight`: 5.154
- `adapter.14.to_out.weight`: 5.061