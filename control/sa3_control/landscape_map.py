"""Trajectory-subspace landscape mapping (#4 in the perceptual-signal plan).

"Make a model of the model's landscape": take a training run's checkpoints, find the
2-D plane the trajectory actually explored (trajectory-PCA), quantify how planar the
run was AGAINST THE RANDOM-WALK NULL (a pure random walk also concentrates PCA variance
— arXiv:1806.08805 — so the null is mandatory), and emit a grid spec for loss-surface
sampling on that plane. The novel step for us: render the CC (control-consistency) loss
on the same plane as the RF loss — mapping the surface the training loss is blind to.

Research grounding (2026-07 pass, see the spec):
- Trajectory planes use RAW PC directions in native parameter units (filter
  normalization is for random directions only; it distorts trajectory embeddings).
- Grid: 25x25 exploration default, span 1.2x the trajectory extent per PC.
- Loss grids (GPU mode, later): ONE fixed batch + fixed stratified timesteps + fixed
  noise draws reused at every grid point — otherwise diffusion sampling variance
  swamps the structure. fp32 accumulation; log-loss rendering.

CPU usage (geometry now):
    python -m sa3_control.landscape_map --run-dir <dir with riffer_step*.pt> --out <dir>
"""
from __future__ import annotations

import argparse, glob, json, os, re

import numpy as np


# ---------- pure geometry (unit-tested) ----------

def trajectory_pca(traj: np.ndarray, k: int = 2):
    """PCA of a trajectory (T, D) around its mean. Returns (basis (k,D) raw/unit-norm,
    explained-variance ratios (k,), projections (T,k) in native parameter units).

    Gram trick: eigendecompose the T x T Gram matrix instead of SVD-ing T x D — at
    D ~ 1e8 (full adapter states) the naive route allocates ~10 GB and dies; the Gram
    route touches D only in dot products and two basis vectors."""
    X = traj.astype(np.float32, copy=False)
    mean = X.mean(axis=0, keepdims=True)
    Xc = X - mean                                     # (T, D) float32 — one copy
    G = (Xc @ Xc.T).astype(np.float64)                # (T, T)
    w, U = np.linalg.eigh(G)                          # ascending
    order = np.argsort(w)[::-1]
    w, U = np.clip(w[order], 0, None), U[:, order]
    evr = (w / max(w.sum(), 1e-30))[:k]
    basis = np.empty((k, X.shape[1]), np.float32)
    for i in range(k):
        s = np.sqrt(max(w[i], 1e-30))
        basis[i] = (Xc.T @ (U[:, i] / s)).astype(np.float32)   # unit-norm direction
    proj = Xc @ basis.T                               # native units
    return basis, evr.astype(np.float64), proj.astype(np.float32)


def random_walk_null(traj: np.ndarray, k: int = 2, n_draws: int = 0, seed: int = 0):
    """Antognini & Sohl-Dickstein null with the SAME per-step norms, computed in the
    D -> inf limit: random step directions are pairwise orthogonal, so the null walk's
    Gram matrix is exactly G[i,j] = sum_{s <= min(i,j)} norm_s^2 — no D-sized sampling
    (at D ~ 1e8 sampled walks would need tens of GB). n_draws/seed kept for API compat
    (the closed form is deterministic)."""
    steps = np.diff(traj.astype(np.float32, copy=False), axis=0)
    n2 = (np.linalg.norm(steps, axis=1) ** 2).astype(np.float64)
    T = traj.shape[0]
    cum = np.concatenate([[0.0], np.cumsum(n2)])      # walk_i . walk_j = cum[min(i,j)]
    G = np.minimum.outer(cum, cum)
    # center the Gram: Gc = (I - 1/T) G (I - 1/T)
    J = np.eye(T) - np.ones((T, T)) / T
    w = np.linalg.eigvalsh(J @ G @ J)[::-1]
    w = np.clip(w, 0, None)
    return (w / max(w.sum(), 1e-30))[:k]


def plane_grid_spec(proj: np.ndarray, n: int = 25, margin: float = 1.2) -> dict:
    """Deterministic grid over the trajectory's extent in the PC plane (x margin)."""
    lo, hi = proj.min(axis=0), proj.max(axis=0)
    c, half = (lo + hi) / 2, (hi - lo) / 2 * margin
    half = np.maximum(half, 1e-6)
    return {"alphas": np.linspace(c[0] - half[0], c[0] + half[0], n).astype(np.float32),
            "betas": np.linspace(c[1] - half[1], c[1] + half[1], n).astype(np.float32)}


# ---------- checkpoint plumbing ----------

def _flatten_state(state: dict) -> np.ndarray:
    keys = sorted(state.keys())
    return np.concatenate([np.asarray(state[k].float().reshape(-1)) for k in keys])


def load_run_trajectory(run_dir: str, pattern: str = "riffer_step*.pt"):
    """-> (steps list, (T,D) trajectory of the adapter+conditioner 'state' dicts)."""
    import torch
    paths = sorted(glob.glob(os.path.join(run_dir, pattern)),
                   key=lambda p: int(re.search(r"step(\d+)", p).group(1)))
    steps, vecs = [], []
    for p in paths:
        ck = torch.load(p, map_location="cpu", weights_only=False)
        vecs.append(_flatten_state(ck["state"]))
        steps.append(int(re.search(r"step(\d+)", p).group(1)))
    return steps, np.stack(vecs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, help="dir with riffer_step*.pt checkpoints")
    ap.add_argument("--out", required=True)
    ap.add_argument("--grid-n", type=int, default=25)
    ap.add_argument("--null-draws", type=int, default=5)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    steps, traj = load_run_trajectory(args.run_dir)
    print(f"[map] {len(steps)} checkpoints, D={traj.shape[1]:,}", flush=True)
    basis, evr, proj = trajectory_pca(traj, k=2)
    null_evr = random_walk_null(traj, k=2, n_draws=args.null_draws)
    spec = plane_grid_spec(proj, n=args.grid_n)

    planar = float(evr[:2].sum()); null_planar = float(null_evr[:2].sum())
    verdict = ("REAL low-dim structure" if planar > null_planar + 0.05
               else "indistinguishable from a random walk — do not over-read the plane")
    print(f"[map] top-2 EVR = {planar:.3f} vs random-walk null {null_planar:.3f} -> {verdict}",
          flush=True)

    # basis is huge (2 x D) — store npz; JSON holds the small stuff for the UI/notes.
    np.savez_compressed(os.path.join(args.out, "plane_basis.npz"),
                        basis=basis, center=traj.mean(axis=0).astype(np.float32))
    json.dump({
        "run_dir": args.run_dir, "steps": steps,
        "explained_variance_top2": [float(e) for e in evr],
        "random_walk_null_top2": [float(e) for e in null_evr],
        "verdict": verdict,
        "trajectory_projection": proj.tolist(),
        "grid": {"alphas": spec["alphas"].tolist(), "betas": spec["betas"].tolist()},
        "grid_protocol": {
            "note": "loss-grid eval (GPU): reuse ONE fixed batch, fixed stratified t set,"
                    " fixed noise draws at every grid point; fp32 accumulation;"
                    " render BOTH rf_loss and cc_loss fields on this same plane.",
            "fields": ["rf_loss", "cc_loss"],
        },
    }, open(os.path.join(args.out, "landscape_plane.json"), "w"), indent=2)
    print(f"[map] wrote {args.out}/landscape_plane.json + plane_basis.npz", flush=True)


if __name__ == "__main__":
    main()
