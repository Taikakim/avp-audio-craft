#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-09-29, goa5k ablation work; confirmed by CONTINUITY 2026-10-12)
"""Live/post-hoc weight-velocity + direction report for a train_lora_modular.py run.

Same convention as the ad hoc VELOCITIES.md this fleet has been writing by hand for the
goa5k_fullft_* family: DoRA initialises lora_B to ZERO, so ||lora_B||_F at a checkpoint is
exactly the cumulative distance moved (no step-0 checkpoint needed). "Velocity" here is the
INTERVAL delta normalised to units-per-1000-steps, so runs with different checkpoint spacing
are comparable on the same scale Kim is reasoning about (e.g. "velocity should be 50-70 by
step 1500").

Extends the ad hoc version with a DIRECTION column: cosine similarity between consecutive
ΔB step vectors (flattened, float64 -- float32 accumulation error inflates cosines above 1,
see MASTER.md 2026-09-28 b-series note). A high-velocity run whose direction cosine keeps
flipping sign is moving fast without going anywhere -- "running in circles" -- which speed
alone can't show. Also flags the running path efficiency (net displacement / total path
length) once >=3 checkpoints exist, same read as control/sa3_control/checkpoint_trajectory_stats.py's
statistic but computed here so it's available while a run is still in flight.

Run (CPU is fine, mmap avoids loading unrelated tensors into RAM):
  .venv/bin/python eval/velocity_monitor.py --run-dir <path> [--out VELOCITIES.md]
"""
import argparse
import re
from pathlib import Path

import torch


def norms(ckpt_path):
    sd = torch.load(ckpt_path, map_location="cpu", mmap=True, weights_only=False)["state_dict"]
    b_vecs = []
    a_norm_sq = 0.0
    mag_norm_sq = 0.0
    for k, v in sd.items():
        if "lora_B" in k:
            b_vecs.append(v.float().flatten())
        elif "lora_A" in k:
            a_norm_sq += float(v.float().pow(2).sum())
        elif "magnitude" in k:
            mag_norm_sq += float(v.float().pow(2).sum())
    b_flat = torch.cat(b_vecs).double() if b_vecs else torch.zeros(0, dtype=torch.float64)
    return b_flat, a_norm_sq ** 0.5, mag_norm_sq ** 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--target-note", type=str, default=None,
                     help="Optional free text recorded in the report header (e.g. the target velocity range).")
    a = ap.parse_args()
    out = a.out or (a.run_dir / "VELOCITIES.md")

    ckpts = []
    for p in a.run_dir.glob("step=*.ckpt"):
        m = re.match(r"step=(\d+)\.ckpt$", p.name)
        if m:
            ckpts.append((int(m.group(1)), p))
    ckpts.sort()

    if not ckpts:
        out.write_text(f"# Checkpoint Displacement & Velocities\n\nNo step=N.ckpt found yet in {a.run_dir}.\n")
        print(f"no checkpoints yet in {a.run_dir}")
        return

    rows = ["| Step | Cumulative ||B||_F | Interval Δ||B||_F | Velocity (units / 1k steps) | "
            "Mean DoRA Mag | Direction cos(Δ_prev, Δ_this) | Path efficiency so far |",
            "|---|---|---|---|---|---|---|"]

    prev_step = 0
    prev_b_flat = None
    prev_delta = None
    b0 = None  # first checkpoint's flat B, for net-displacement / path-efficiency
    path_len = 0.0

    for step, path in ckpts:
        b_flat, a_norm, mag_norm = norms(path)
        cum_norm = float(torch.linalg.norm(b_flat))

        if prev_b_flat is None:
            interval_delta_vec = b_flat
        else:
            interval_delta_vec = b_flat - prev_b_flat
        interval_delta = float(torch.linalg.norm(interval_delta_vec))
        interval_steps = step - prev_step
        velocity = interval_delta / (interval_steps / 1000.0) if interval_steps > 0 else float("nan")
        path_len += interval_delta

        if prev_delta is None:
            cos_str = ""
        else:
            denom = float(torch.linalg.norm(prev_delta)) * float(torch.linalg.norm(interval_delta_vec))
            cos = float(torch.dot(prev_delta, interval_delta_vec) / denom) if denom > 0 else float("nan")
            cos_str = f"{cos:.3f}"

        if b0 is None:
            b0 = b_flat
            path_eff_str = ""
        else:
            net = float(torch.linalg.norm(b_flat - b0))
            path_eff_str = f"{(net / path_len):.3f}" if path_len > 0 else ""

        rows.append(f"| {step} | {cum_norm:.4f} | {interval_delta:.4f} | {velocity:.4f} | "
                     f"{mag_norm:.4f} | {cos_str} | {path_eff_str} |")

        prev_step, prev_b_flat, prev_delta = step, b_flat, interval_delta_vec

    header = "# Checkpoint Displacement & Velocities\n\n"
    if a.target_note:
        header += f"Target: {a.target_note}\n\n"
    header += ("Direction column: cosine between this interval's ΔB and the PREVIOUS interval's ΔB "
               "(flattened, float64). Near 1.0 = still heading the same way; near 0 = turned; "
               "negative = backtracking. Path efficiency = net displacement from the first checkpoint "
               "/ total path length so far -- low means the run is wandering (speed without direction).\n\n")
    out.write_text(header + "\n".join(rows) + "\n")
    print(header + "\n".join(rows))


if __name__ == "__main__":
    main()
