# Checkpoint-stats — weight-space trajectory library

**Standing practice:** every time a training run finishes, record its weight-space
trajectory here. We don't (yet) know what individual layers/dimensions *do* — but the
*shape of the journey* (how fast weights move, whether they converge or wander, which
layers keep changing) is cheap to collect, comparable across runs, and one day we'll
want it. Collect it by default; interpret later.

This is the **saved-checkpoint (post-hoc) view**. Its in-flight counterpart is the
per-run tiered telemetry (`avp_sa3/sa3_control/telemetry.py`, wired into `train.py` →
wandb), which logs the live weight-space trajectory + per-layer norms during training.
Both are standing requirements on every control-head run — collect both.

## How to add a run

```
/home/kim/Projects/mir/mir/bin/python \
  /home/kim/Projects/SAO/stable-audio-tools/avp_sa3/sa3_control/checkpoint_trajectory_stats.py \
  --ckpt-dir <run_dir_with_riffer_step*.pt> --label <short_label> --out-dir /home/kim/Projects/SAO/checkpoint-stats
```
CPU-only (loads each checkpoint once). Produces `<label>_trajectory.{json,md,png}`.

## What's recorded (per checkpoint, over the concatenated weight vector)

| metric | meaning |
|---|---|
| `global_norm` | overall weight magnitude |
| `d_from_init` | how far from the start (total progress) |
| `d_from_prev` | **learning velocity** ‖ΔW‖ per checkpoint |
| `d_from_final` | convergence toward the last checkpoint |
| `cos_to_final` | directional alignment to the end state |
| `step_cos` | cos of consecutive step directions — **path straightness** (~1 straight, ~0 turning, <0 doubling back) |
| `layer_vel` | per-tensor velocity (which layers move late vs freeze) |

**Summary metrics** — `path_length` (Σ velocity), `net_displacement` (‖W_last−W_0‖),
`path_efficiency = net/path` (**low ⇒ wandering/oscillating in a basin → weight-averaging/EMA
should help; high ⇒ moving directly**), `centroid_checkpoint` (the natural model-soup center),
`peak_velocity`, `top_moving_layers`.

## Why this matters (the working hypothesis)

For the onset-density head at lr 2e-5, *control authority* (the eval-measured slope) peaks
~epoch 24 then **declines**, while the rectified-flow training loss stays flat the whole time.
A flat/uninformative loss means the optimizer keeps nudging the weights in directions that
don't change the loss but *erode* control — i.e. **drift in an under-determined landscape**,
not classic overfitting and not a sharp minimum. The trajectory metrics here are how we
tell drift (velocity stays high, path efficiency low) from convergence (velocity → 0), and
the model-soups (`/run/media/kim/Mantu/sa3_control_runs/soups/`) are the post-hoc test of
whether averaging recovers a better, flatter point than any single late checkpoint. If it
does, the recipe lesson is **EMA / weight-averaging (damping), not just a lower LR**.

## Library

- `lr2e5_trajectory.*` — onset-density FUSION, lr 2e-5, 40 epochs (the main run)
- `lr8e5_trajectory.*` — onset-density FUSION, lr 8e-5, 10 epochs (higher LR)
- `lr1e4_trajectory.*` — onset-density FUSION, lr 1e-4 (highest; "peaks early then declines")
