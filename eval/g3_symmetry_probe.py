#!/usr/bin/env python
"""g3_symmetry_probe.py — G3: latent symmetry discovery (reality-structured plan; the
geometric program's make-or-break gate).

Question (F's Q1): what channel-space invariances does the LEARNED SAME latent + trained
RF field actually have? Every geometric card (Clifford/gauge/steerable) GUESSES a
symmetry; this measures instead. Test: equivariance error of the base model's velocity
field under channel-space rotations R:  err(R) = ||v(Rz,t) - R v(z,t)|| / ||v(z,t)||,
averaged over crops/frames, at sigma 0.5.

Rotation families compared:
  identity          control (floor; measures forward determinism)
  eig_adjacent      rotation in the plane of ADJACENT covariance eigenvectors (i,i+1) —
                    if the latent has approximate SO(2) structure anywhere, near-degenerate
                    eigen-pairs are where it hides
  eig_far           plane of eigvecs (i, i+128) — matched-construction control
  random_pair       random orthogonal 2-plane rotations
  random_full       random SO(256) rotation (maximal scrambling; ceiling)
Angles: 15 deg (near-identity behavior) and 90 deg (max discrimination).

Verdict: any family with err << random_pair at matched angle = discovered approximate
symmetry -> selects E2's algebra. All families ~ random = no channel-space symmetry ->
the imposed-geometry branch closes honestly.

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/g3_symmetry_probe.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import glob
import json
import random
from pathlib import Path

import numpy as np
import torch

from stable_audio_3 import StableAudioModel

LATENTS = Path("/home/kim/Projects/latents_sa3")
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/g3_symmetry")
EIG = Path("/run/media/kim/Mantu/sa3_lora_runs/e1_pretest/corpus_eigbasis.npz")
SIGMA = 0.5
N_CROPS = 16
T_SLICE = 512
ANGLES = [15.0, 90.0]
N_PER_FAMILY = 8


def rot_in_plane(u, w, theta):
    """256x256 rotation by theta in the plane spanned by orthonormal u,w."""
    c, s = np.cos(theta), np.sin(theta)
    R = np.eye(256, dtype=np.float32)
    R += (c - 1) * (np.outer(u, u) + np.outer(w, w)) + s * (np.outer(w, u) - np.outer(u, w))
    return R


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    z = np.load(EIG)
    vecs = np.ascontiguousarray(z["vecs"]).astype(np.float32)   # cols = eigvecs desc
    rng = np.random.default_rng(3)

    fams = {}
    for th_deg in ANGLES:
        th = np.deg2rad(th_deg)
        fams[f"identity_{th_deg}"] = [np.eye(256, dtype=np.float32)]
        fams[f"eig_adjacent_{th_deg}"] = [
            rot_in_plane(vecs[:, i], vecs[:, i + 1], th)
            for i in rng.choice(255, N_PER_FAMILY, replace=False)]
        fams[f"eig_far_{th_deg}"] = [
            rot_in_plane(vecs[:, i], vecs[:, i + 128], th)
            for i in rng.choice(127, N_PER_FAMILY, replace=False)]
        rp = []
        for _ in range(N_PER_FAMILY):
            u = rng.standard_normal(256); u /= np.linalg.norm(u)
            w = rng.standard_normal(256); w -= (w @ u) * u; w /= np.linalg.norm(w)
            rp.append(rot_in_plane(u.astype(np.float32), w.astype(np.float32), th))
        fams[f"random_pair_{th_deg}"] = rp
        rf = []
        for _ in range(3):
            A = rng.standard_normal((256, 256)).astype(np.float32)
            Q, _ = np.linalg.qr(A)
            # blend toward identity for the small angle: geodesic fraction via matrix power
            rf.append(Q if th_deg == 90.0 else
                      np.real(scipy_fractional(Q, th_deg / 90.0)))
        fams[f"random_full_{th_deg}"] = rf

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype

    files = sorted(glob.glob(str(LATENTS / "*.npy")))
    random.seed(11)
    picks = random.sample(files, N_CROPS)

    errs = {f: [] for f in fams}
    for fi, f in enumerate(picks):
        x = np.squeeze(np.load(f)).astype(np.float32)
        if x.shape[0] != 256:
            x = x.T
        x = x[:, :T_SLICE]
        meta = json.loads(Path(f.replace(".npy", ".json")).read_text())
        prompt = meta.get("prompt") or meta.get("caption") or "goa trance"
        T = x.shape[1]
        seconds = T / 10.7666015625
        xt_ = torch.tensor(x[None]).to(device, mdtype)
        tensors = cdm.conditioner([{"prompt": prompt, "seconds_total": seconds}], str(device))
        tensors["inpaint_mask"] = [torch.zeros((1, 1, T), device=device)]
        tensors["inpaint_masked_input"] = [torch.zeros_like(xt_, device=device)]
        cond = cdm.get_conditioning_inputs(tensors)
        cond = {k: (v.type(mdtype) if torch.is_tensor(v) else v) for k, v in cond.items()}

        g = torch.Generator(device="cpu").manual_seed(500 + fi)
        eps = torch.randn(xt_.shape, generator=g).to(device, mdtype)
        zs = (1 - SIGMA) * xt_ + SIGMA * eps
        t = torch.full((1,), SIGMA, device=device, dtype=mdtype)
        with torch.no_grad():
            v0 = cdm.model(zs, t, **cond)[0].float()             # [256,T]
        v0n = v0.norm()

        for fam, Rs in fams.items():
            for R in Rs:
                Rt = torch.tensor(np.ascontiguousarray(R, dtype=np.float32), device=device)
                zR = (Rt.to(mdtype) @ zs[0]).unsqueeze(0)
                with torch.no_grad():
                    vR = cdm.model(zR, t, **cond)[0].float()
                err = (vR - Rt @ v0).norm() / v0n
                errs[fam].append(float(err))
        if (fi + 1) % 4 == 0:
            print(f"[crop] {fi+1}/{N_CROPS}", flush=True)

    print(f"\n{'family':<22} {'median err':>11} {'iqr':>13}")
    summary = {}
    for fam in sorted(errs):
        a = np.array(errs[fam])
        summary[fam] = {"median": round(float(np.median(a)), 4),
                        "q25": round(float(np.quantile(a, .25)), 4),
                        "q75": round(float(np.quantile(a, .75)), 4)}
        print(f"{fam:<22} {summary[fam]['median']:>11.4f} "
              f"[{summary[fam]['q25']:.3f},{summary[fam]['q75']:.3f}]")

    (OUT / "results.json").write_text(json.dumps(
        {"summary": summary, "n_crops": N_CROPS, "sigma": SIGMA, "t_slice": T_SLICE,
         "angles_deg": ANGLES, "n_per_family": N_PER_FAMILY,
         "verdict_rule": "a family with median err substantially below random_pair at the "
                         "same angle = discovered approximate symmetry (selects E2 algebra); "
                         "all ~ random_pair = no channel-space symmetry, imposed-geometry "
                         "branch closes.",
         "result": None, "kim_feedback": None}, indent=2))
    print(f"[done] -> {OUT}/results.json")


def scipy_fractional(Q, frac):
    """Fractional power of a rotation matrix via eigendecomposition (for small-angle
    versions of a random full rotation)."""
    from scipy.linalg import fractional_matrix_power
    return fractional_matrix_power(Q, frac)


if __name__ == "__main__":
    main()
