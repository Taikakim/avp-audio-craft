#!/usr/bin/env python3
"""lora_gauge_drift.py — how much of a LoRA/DoRA run's motion is GAUGE drift (A and B changing
while their product B·A does not)?

WHY (C, 2026-09-22, from arXiv:2608.07436 "Post-Grokking Collapse ... Muon-Trained Transformers").
That paper finds Muon keeps taking full-size steps after the loss is solved (step-size elasticity
−0.03 on gradient magnitude vs AdamW's +1.5) and spends them drifting along a direction the loss
cannot see: the representation/readout pair, identified only up to an invertible map. LoRA has
the same symmetry exactly: B·A = (B·X)(X⁻¹·A) for any invertible r×r X. We run Muon-family
updates on A and B SEPARATELY, and our trajectory instrument reads ‖B‖ only — so ‖B‖ growth or
"velocity" could partly be motion along this orbit, invisible to the model's function.

WHAT IT MEASURES, per adapted matrix, between consecutive checkpoints (finite step, linearised at
the midpoint (Ā, B̄)):
  The gauge-orbit tangent at (A,B) is {(B·X, −X·A) : X ∈ R^{r×r}}. Project the displacement
  (ΔB, ΔA) onto it by least squares — the normal equations are the Sylvester equation
      (BᵀB) X + X (A Aᵀ) = Bᵀ ΔB − ΔA Aᵀ
  solved in the joint eigenbasis of the two r×r Grams. gauge_frac = ‖(BX, −XA)‖² / ‖(ΔB, ΔA)‖².
  Pure gauge motion → 1.0, pure function-changing motion → 0.0. A RANDOM displacement of the
  same size lands near r²/(r·(m+n)) — reported per run as the chance baseline, so the number is
  read against something (CLAUDE.md "audit the instrument").
  Also: relative velocities ‖ΔB‖/‖B‖ vs ‖Δ(BA)‖/‖BA‖ and the coupling ‖BA‖/(‖B‖‖A‖).

SELF-TEST: `--selftest` checks a synthetic pure-gauge step reads ≈1 and a random step reads
≈ the baseline before anything is believed.

USAGE
  .venv/bin/python eval/lora_gauge_drift.py <run_dir_with_step=*.ckpt> [--out file.json]
"""
import argparse, json, re, sys
from pathlib import Path

import torch


def gauge_fraction(A, B, dA, dB):
    """A: r×n, B: m×r (midpoint), dA/dB displacements. Returns (gauge_energy, total_energy)."""
    GB = B.T @ B
    GA = A @ A.T
    lb, VB = torch.linalg.eigh(GB)
    la, VA = torch.linalg.eigh(GA)
    C = B.T @ dB - dA @ A.T
    Ct = VB.T @ C @ VA
    denom = lb[:, None] + la[None, :]
    Xt = Ct / denom.clamp_min(1e-12 * float(denom.max()))
    X = VB @ Xt @ VA.T
    gB = B @ X
    gA = -X @ A
    g = gB.pow(2).sum() + gA.pow(2).sum()
    tot = dB.pow(2).sum() + dA.pow(2).sum()
    return float(g), float(tot)


def load_factors(path):
    ck = torch.load(path, map_location="cpu", mmap=True, weights_only=False)
    sd = ck["state_dict"]
    out = {}
    for k, v in sd.items():
        if k.endswith(".lora_A"):
            base = k[: -len(".lora_A")]
            out[base] = (v.double(), sd[base + ".lora_B"].double())
    return out, int(ck.get("global_step", -1))


def selftest():
    torch.manual_seed(0)
    m, n, r = 300, 200, 16
    A, B = torch.randn(r, n, dtype=torch.float64), torch.randn(m, r, dtype=torch.float64)
    X = 1e-3 * torch.randn(r, r, dtype=torch.float64)
    g, t = gauge_fraction(A, B, -X @ A, B @ X)
    pure = g / t
    g, t = gauge_fraction(A, B, torch.randn(r, n, dtype=torch.float64), torch.randn(m, r, dtype=torch.float64))
    rnd = g / t
    base = r * r / (r * (m + n))
    print(f"selftest: pure-gauge {pure:.4f} (want ~1), random {rnd:.4f} (baseline {base:.4f})")
    assert pure > 0.99 and abs(rnd - base) < 3 * base, "instrument broken"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    selftest()
    if a.selftest or not a.run_dir:
        return
    ckpts = sorted(Path(a.run_dir).glob("step=*.ckpt"), key=lambda p: int(re.findall(r"\d+", p.name)[0]))
    prev = None
    rows = []
    for p in ckpts:
        fac, step = load_factors(p)
        nB = sum(float(B.pow(2).sum()) for A, B in fac.values()) ** 0.5
        nA = sum(float(A.pow(2).sum()) for A, B in fac.values()) ** 0.5
        nP = sum(float((B @ A).pow(2).sum()) for A, B in fac.values()) ** 0.5
        coup = sorted(float((B @ A).norm() / (B.norm() * A.norm()).clamp_min(1e-30)) for A, B in fac.values())
        row = dict(step=step, normB=nB, normA=nA, normBA=nP, coupling_median=coup[len(coup) // 2])
        if prev is not None:
            pstep, pfac = prev
            G = T = dBsq = dPsq = base_num = base_den = 0.0
            per = []
            for key, (A1, B1) in fac.items():
                A0, B0 = pfac[key]
                dA, dB = A1 - A0, B1 - B0
                g, t = gauge_fraction((A0 + A1) / 2, (B0 + B1) / 2, dA, dB)
                G += g; T += t
                dBsq += float(dB.pow(2).sum()); dPsq += float((B1 @ A1 - B0 @ A0).pow(2).sum())
                r, n = A1.shape; m = B1.shape[0]
                base_num += t * (r * r) / (r * (m + n)); base_den += t
                per.append((g / t if t else 0.0, key))
            per.sort()
            row.update(gauge_frac=G / T, chance_baseline=base_num / base_den,
                       rel_vel_B=dBsq ** 0.5 / nB, rel_vel_BA=dPsq ** 0.5 / nP,
                       dA_share=1 - dBsq / T,
                       top_gauge_modules=[(round(f, 3), k) for f, k in per[-3:]])
        rows.append(row)
        prev = (step, fac)
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items() if k != "top_gauge_modules"}))
        sys.stdout.flush()
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
