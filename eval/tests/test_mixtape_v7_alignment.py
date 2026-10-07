"""Sign convention and map of eval/mixtape_assemble_v7.py: a regression guard for the phase shift (B delayed by +s
lines up with A) and the stretched-source -> output map. No GPU, no madmom, ~1 s."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mixtape_assemble_v7 as v7  # noqa: E402

SR = v7.SR


def kick_train(n, period, offset, width=0.012):
    t = np.arange(n) / SR
    x = np.zeros(n, dtype=np.float32)
    for k in range(int((n / SR - offset) / period) + 1):
        c = offset + k * period
        x += np.exp(-0.5 * ((t - c) / width) ** 2).astype(np.float32) * np.sin(2 * np.pi * 60 * (t - c)).astype(np.float32)
    return np.stack([x, x])


def test_phase_shift_sign_and_size():
    period = 60.0 / 140
    n = int(SR * 12)
    a = kick_train(n, period, 0.50)
    b = kick_train(n, period, 0.47)                 # B's kicks are 30 ms EARLY: delaying B by +30 ms lines them up
    s, ncc_b, ncc_0 = v7.phase_shift(a, b, period * SR)
    assert abs(s / SR - 0.030) < 0.004, s / SR
    assert ncc_b > ncc_0 and ncc_b > 0.8


def test_phase_shift_noise_has_no_alignment():
    rng = np.random.default_rng(0)
    a = rng.standard_normal((2, SR * 8)).astype(np.float32)
    b = rng.standard_normal((2, SR * 8)).astype(np.float32)
    _, ncc_b, _ = v7.phase_shift(a, b, 0.43 * SR)
    assert ncc_b < 0.4                              # the gate that exposed transitions 4 and 21 (ncc ~ 0)


def test_src_to_out_identity_for_constant_chunks():
    chunk = int(0.25 * SR)
    lens = np.full(20, chunk)
    for src in (0, 1000, chunk, 3 * chunk + 7):
        assert v7.src_to_out(src, lens) == src
