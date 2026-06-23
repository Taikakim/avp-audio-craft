# Checkpoint trajectory — lr8e5

- checkpoints: **10** (steps 5400–54000)
- net displacement ||W_last−W_0||: **25.120**
- total path length Σ‖ΔW‖: **33.024**
- **path efficiency** (net/path): **0.761**  (low ⇒ wandering/oscillating in a basin → averaging should help)
- centroid (soup-center) checkpoint: **epoch 5.0** (step 27000)
- peak learning velocity: epoch 2.0 (‖ΔW‖=5.835)

## Per-checkpoint

| epoch | global_norm | d_from_init | velocity ‖ΔW‖ | d_from_final | cos_to_final | step_cos |
|---|---|---|---|---|---|---|
| 1.0 | 157.60 | 0.000 | 0.000 | 25.120 | 0.9873 | 0.000 |
| 2.0 | 157.56 | 5.835 | 5.835 | 22.042 | 0.9902 | 0.000 |
| 3.0 | 157.51 | 9.537 | 4.626 | 19.164 | 0.9926 | 0.657 |
| 4.0 | 157.47 | 12.470 | 3.986 | 16.361 | 0.9946 | 0.755 |
| 5.0 | 157.44 | 15.012 | 3.619 | 13.576 | 0.9963 | 0.812 |
| 6.0 | 157.42 | 17.293 | 3.349 | 10.816 | 0.9976 | 0.841 |
| 7.0 | 157.41 | 19.415 | 3.131 | 8.090 | 0.9987 | 0.869 |
| 8.0 | 157.42 | 21.416 | 2.962 | 5.377 | 0.9994 | 0.879 |
| 9.0 | 157.44 | 23.312 | 2.818 | 2.697 | 0.9999 | 0.893 |
| 10.0 | 157.46 | 25.120 | 2.697 | 0.000 | 1.0000 | 0.901 |

## Top moving layers (total velocity)

- `conditioner.film.2.weight`: 12.723
- `adapter.19.to_out.weight`: 4.356
- `adapter.18.to_out.weight`: 4.317
- `adapter.15.to_out.weight`: 4.297
- `adapter.20.to_out.weight`: 4.275
- `adapter.17.to_out.weight`: 4.275
- `adapter.16.to_out.weight`: 4.274
- `adapter.21.to_out.weight`: 4.243