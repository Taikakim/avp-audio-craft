# tests/test_landscape_map.py — trajectory-subspace landscape mapping (#4 in the
# perceptual-signal plan). Research grounding: trajectory-PCA planes use RAW directions
# (no filter norm); low-dim claims MUST beat the random-walk null (arXiv:1806.08805).
import numpy as np

from sa3_control.landscape_map import trajectory_pca, random_walk_null, plane_grid_spec


def _planted_trajectory(T=12, dim=400, seed=0):
    """A trajectory that mostly moves in a 2-D plane + small isotropic noise."""
    rng = np.random.default_rng(seed)
    u = rng.standard_normal(dim); u /= np.linalg.norm(u)
    w = rng.standard_normal(dim); w -= (w @ u) * u; w /= np.linalg.norm(w)
    pts = [np.zeros(dim, np.float32)]
    for t in range(1, T):
        step = (1.0 * u + 0.5 * np.sin(t / 2) * w + 0.02 * rng.standard_normal(dim))
        pts.append((pts[-1] + step).astype(np.float32))
    return np.stack(pts)


def test_pca_recovers_planted_plane():
    traj = _planted_trajectory()
    basis, evr, proj = trajectory_pca(traj, k=2)
    assert basis.shape == (2, traj.shape[1])
    assert evr[0] + evr[1] > 0.95                      # planted plane dominates
    assert proj.shape == (len(traj), 2)
    # projections must reproduce pairwise distances well within the plane
    d_full = np.linalg.norm(traj[-1] - traj[0])
    d_proj = np.linalg.norm(proj[-1] - proj[0])
    assert d_proj > 0.9 * d_full * 0.9

def test_directed_trajectory_beats_random_walk_null():
    traj = _planted_trajectory()
    _, evr, _ = trajectory_pca(traj, k=2)
    null_evr = random_walk_null(traj, k=2, n_draws=5, seed=1)
    # the planted trajectory's top-2 variance must exceed the matched random walk's
    assert evr[:2].sum() > null_evr[:2].sum() + 0.05, (evr[:2].sum(), null_evr[:2].sum())


def test_grid_spec_is_deterministic_and_in_plane():
    traj = _planted_trajectory()
    basis, _, proj = trajectory_pca(traj, k=2)
    spec = plane_grid_spec(proj, n=5, margin=1.2)
    assert spec["alphas"].shape == (5,) and spec["betas"].shape == (5,)
    # spans cover the trajectory extent with margin
    assert spec["alphas"][0] <= proj[:, 0].min() and spec["alphas"][-1] >= proj[:, 0].max()
    spec2 = plane_grid_spec(proj, n=5, margin=1.2)
    assert np.allclose(spec["alphas"], spec2["alphas"])  # deterministic
