#!/usr/bin/env python3
"""test_regression_phase_ceiling.py — empirically PROVE the plan's central pivot on CPU:
a regression net trained to predict phase-carrying complex HF from a phase-incoherent input
collapses its magnitude toward zero (regression-to-the-mean), while the SAME net recovers
magnitude fine when that's the target. => HF phase must be GENERATED, not regressed.

This is the theoretical crux of docs/clarity-recovery-plan-2026-08-02.md (Track A generative,
and the #64 diagnostic). Rather than trust the report's argument, we train the actual nets on
synthetic data with a KNOWN, controllable phase-coherence and watch the collapse happen.

Setup: HF bins have magnitude m (predictable from an input condition) and phase theta_clean
that is INDEPENDENT of everything the net sees (coherence ~0, matching our measured 0.045).
The net sees the degraded complex spectrum (same m, incoherent phase). Optimal MMSE for the
complex target is E[m e^{i theta_clean} | input] = m * E[e^{i theta_clean}] = 0 -> magnitude
collapse. Magnitude-only target has no such problem.

Run: /home/kim/Projects/SAO/.venv/bin/python eval/test_regression_phase_ceiling.py
"""
import numpy as np
import torch
import torch.nn as nn
torch.set_num_threads(8)

torch.manual_seed(0)
np.random.seed(0)
N, K = 3000, 32          # frames, HF bins
DEV = "cpu"


def make_data(coherence=0.0):
    """Degraded input + clean target. `coherence` in [0,1] ties input phase to target phase."""
    cond = np.random.randn(N, K).astype(np.float32)              # the predictable condition
    mag = np.abs(cond) * 0.5 + 0.5                                # magnitude IS a fn of cond
    theta_clean = np.random.uniform(-np.pi, np.pi, (N, K)).astype(np.float32)
    # input phase = coherence-weighted mix of clean phase and independent noise
    theta_noise = np.random.uniform(-np.pi, np.pi, (N, K)).astype(np.float32)
    theta_in = coherence * theta_clean + (1 - coherence) * theta_noise
    x = np.stack([mag * np.cos(theta_in), mag * np.sin(theta_in)], -1).reshape(N, 2 * K)
    tgt_complex = np.stack([mag * np.cos(theta_clean), mag * np.sin(theta_clean)], -1
                           ).reshape(N, 2 * K)
    return (torch.tensor(x), torch.tensor(tgt_complex), torch.tensor(mag))


class MLP(nn.Module):
    def __init__(self, din, dout):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(din, 128), nn.GELU(), nn.Linear(128, dout))

    def forward(self, x):
        return self.net(x)


def train(x, y, dout, epochs=150):
    net = MLP(x.shape[1], dout).to(DEV)
    opt = torch.optim.Adam(net.parameters(), 3e-3)
    lossf = nn.MSELoss()
    for _ in range(epochs):
        opt.zero_grad()
        loss = lossf(net(x), y)
        loss.backward()
        opt.step()
    return net


def mag_retention(pred_complex, tgt_mag):
    pc = pred_complex.reshape(-1, K, 2)
    pm = torch.sqrt((pc ** 2).sum(-1) + 1e-12)
    return float(pm.mean() / (tgt_mag.mean() + 1e-9))


def main():
    print("Regression net: does it recover HF magnitude when the target carries UNPREDICTABLE phase?\n")
    print(f"{'input coherence':>16} | {'complex-target mag retention':>28} | {'mag-only-target retention':>26}")
    print("-" * 78)
    rows = []
    for coh in [0.045, 1.0]:
        x, tgt_c, mag = make_data(coh)
        net_c = train(x, tgt_c, 2 * K)          # predict complex (phase-carrying)
        ret_c = mag_retention(net_c(x).detach(), mag)
        net_m = train(x, mag, K)                # predict magnitude only
        pred_m = net_m(x).detach()
        ret_m = float(pred_m.mean() / (mag.mean() + 1e-9))
        rows.append((coh, ret_c, ret_m))
        print(f"{coh:>16.3f} | {ret_c:>28.3f} | {ret_m:>26.3f}")

    coh0 = [r for r in rows if r[0] == 0.045][0]
    coh1 = [r for r in rows if r[0] == 1.0][0]
    print("\n=== claims under test ===")
    # at our measured 0.045 coherence, complex-regression magnitude COLLAPSES (< 0.5) ...
    c1 = coh0[1] < 0.5
    # ... but magnitude-only regression is fine (> 0.85) — magnitude is recoverable, phase is not
    c2 = coh0[2] > 0.85
    # and full coherence (1.0) lets complex regression recover magnitude (sanity: it's the phase)
    c3 = coh1[1] > 0.85
    print(f"  [{'PASS' if c1 else 'FAIL'}] @0.045 complex-regression magnitude collapses: "
          f"{coh0[1]:.3f} (<0.5 => regression-to-the-mean)")
    print(f"  [{'PASS' if c2 else 'FAIL'}] @0.045 magnitude-only regression is fine    : "
          f"{coh0[2]:.3f} (>0.85 => magnitude IS recoverable)")
    print(f"  [{'PASS' if c3 else 'FAIL'}] @1.000 complex regression recovers magnitude : "
          f"{coh1[1]:.3f} (>0.85 => the collapse was PURELY the unpredictable phase)")
    ok = c1 and c2 and c3
    print(f"\n{'ALL PASS — CONFIRMED: at 0.045 coherence a regression post-net cannot' if ok else 'CHECK'}")
    if ok:
        print("  recover phase-carrying HF (magnitude collapses to the mean); it CAN restore")
        print("  magnitude. => the phase must be generated (adversarial/flow), not regressed.")
        print("  This is the empirical basis for the Track A generative pivot + #64 diagnostic.")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
