#!/usr/bin/env python3
"""test_phase_fusion.py — de-risk the pseudo-complex PHASE-FUSION layer for the #62 post-net.

The dual-branch post-net predicts real/imag phase proxies (R, I) that must be fused into a
phase in (-pi, pi]. The clarity report transcribed an APNet-style arctangent-fusion formula;
this test checks (a) the CORRECT fusion (torch.atan2) matches ground-truth phase across all
four quadrants, (b) its gradient is finite AWAY from the origin and identifies the origin
(R=I=0) singularity that must be handled by MAGNITUDE-WEIGHTING the phase loss (which the plan
already does), and (c) whether the report's hand-transcribed formula actually matches atan2
(suspected mis-transcription -> use atan2 directly).

Run: /home/kim/Projects/SAO/.venv/bin/python eval/test_phase_fusion.py
"""
import numpy as np
import torch
torch.set_num_threads(2)


def report_formula(R, I):
    """As transcribed in the clarity report:
    Phi = arctan(I/R) - (pi/2) * Sgn+(I) * (Sgn+(R) - 1),  Sgn+(x)=1 if x>=0 else 0."""
    sgn = lambda x: (x >= 0).float()
    return torch.arctan(I / R) - (np.pi / 2) * sgn(I) * (sgn(R) - 1)


def main():
    ok = True
    # one point in each quadrant + on axes
    R = torch.tensor([1.0, -1.0, -1.0, 1.0, 0.0, 0.0], requires_grad=True)
    I = torch.tensor([1.0, 1.0, -1.0, -1.0, 1.0, -1.0], requires_grad=True)
    truth = torch.atan2(I, R)

    # (1) atan2 is the correct fusion (by definition) — sanity that it spans (-pi,pi]
    span_ok = bool(truth.min() >= -np.pi - 1e-6 and truth.max() <= np.pi + 1e-6)
    ok &= span_ok
    print(f"  [{'PASS' if span_ok else 'FAIL'}] atan2 fusion spans (-pi,pi]: "
          f"[{truth.min():.3f}, {truth.max():.3f}]")

    # (2) gradient finite away from origin; origin singularity flagged
    fused = torch.atan2(I, R)
    fused[:4].pow(2).sum().backward()          # only the off-origin points
    gfin = bool(torch.isfinite(R.grad[:4]).all() and torch.isfinite(I.grad[:4]).all())
    ok &= gfin
    print(f"  [{'PASS' if gfin else 'FAIL'}] atan2 grad finite off-origin: {gfin}")
    # origin singularity: |grad| ~ 1/r as (R,I)->0 (must be magnitude-weighted in the loss)
    Ro = torch.tensor([1e-4], requires_grad=True); Io = torch.tensor([1e-4], requires_grad=True)
    torch.atan2(Io, Ro).backward()
    gmag = float(torch.sqrt(Ro.grad**2 + Io.grad**2))
    print(f"       origin note: |grad| at r=1.4e-4 is {gmag:.0f} (~1/r blowup) "
          f"=> phase loss MUST be magnitude-weighted (plan already does this)")

    # (3) does the report's transcribed formula match atan2? (suspected mis-transcription)
    with torch.no_grad():
        rep = report_formula(R.detach(), I.detach())
        # compare on the 4 finite-R points (formula undefined at R=0)
        diff = (rep[:4] - truth[:4]).abs()
        matches = bool((diff < 1e-5).all())
    print(f"  [{'PASS' if not matches else 'NOTE'}] report's hand-formula vs atan2: "
          f"{'MISMATCH -> use torch.atan2' if not matches else 'matches'}")
    for q, (r, i, d) in enumerate(zip(R.detach()[:4], I.detach()[:4], diff)):
        print(f"       quad R={r:+.0f} I={i:+.0f}: report {report_formula(r, i):+.3f} "
              f"vs atan2 {truth[q]:+.3f}  (diff {d:.3f})")
    # the FINDING we want: report formula is mis-transcribed in >=1 quadrant, so atan2 is the
    # correct choice. Test passes if atan2 is sound (1&2) regardless of the report formula.
    finding = "report formula mis-transcribed (Q2/Q3) -> implement fusion as torch.atan2" \
        if not matches else "report formula matches atan2"
    print(f"\n  DECISION: {finding}")

    print(f"\n{'ALL PASS — fuse phase with torch.atan2 (correct, differentiable off-origin);' if ok else 'CHECK'}")
    if ok:
        print("  magnitude-weight the phase term to tame the origin singularity. Ready for #62.")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
