"""Unit tests for the fingerprint trainer wiring (Task 5).

Run from /home/kim/Projects/SAO/control/:
    /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_train_wiring.py -v
"""
import sys
import os

# Make sa3_control importable when running from the control/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from sa3_control.train import EMA


def test_ema_tracks_toward_current_weights():
    p = [torch.zeros(4, requires_grad=True)]
    ema = EMA(p, decay=0.9)
    with torch.no_grad():
        p[0].add_(1.0)              # weights move to 1.0
    ema.update()
    assert torch.allclose(ema.shadow[0], torch.full((4,), 0.1), atol=1e-6)  # 0.9*0 + 0.1*1


def test_ema_copy_and_restore_roundtrip():
    p = [torch.ones(3)]
    ema = EMA(p, decay=0.5)
    ema.shadow[0].fill_(9.0)
    ema.copy_to()
    assert torch.allclose(p[0], torch.full((3,), 9.0))
    ema.restore()
    assert torch.allclose(p[0], torch.ones(3))
