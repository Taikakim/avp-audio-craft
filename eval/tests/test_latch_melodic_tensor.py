# Owner: GHOST-NOTE (created 2026-10-14)
"""Controls for latch_melodic_tensor (run under the MIR venv): same notes EQ'd -> ~1; shifted / unrelated notes -> ~0; shape is (T, 24 notes + 12 colour) with NO high band.
KNOWN LIMIT, deliberately not asserted: two percussive tracks whose kicks share one pitch score colour ~1 (the kick IS a pitched C#2) -- that is the data, not a bug."""
import os
import sys
import tempfile

import numpy as np
import pytest

pytest.importorskip("basic_pitch")
pytest.importorskip("librosa")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import latch_melodic_tensor as M  # noqa: E402
from test_latch_melody_check import melody, w  # noqa: E402


def test_controls_and_shape():
    from scipy.signal import butter, sosfilt
    from test_latch_melody_check import SR
    A = [60, 64, 67, 72, 64, 60]
    with tempfile.TemporaryDirectory() as td:
        x = melody(A)
        base = M.tensor(w(td, "a", x))
        assert base["notes"].shape[1] == 24 and base["colour"].shape[1] == 12 and len(base["notes"]) == len(base["colour"])
        eq = (sosfilt(butter(2, 2500, "lowpass", fs=SR, output="sos"), x) * 2).astype(np.float32)
        assert M.similarity(base, M.tensor(w(td, "e", eq)))["combined"] > 0.95
        for nm, notes in (("up1", [p + 1 for p in A]), ("fifth", [p + 7 for p in A]), ("other", [71, 66, 62, 59, 66, 71])):
            s = M.similarity(base, M.tensor(w(td, nm, melody(notes))))
            assert s["combined"] < 0.3 and s["notes"] < 0.3, (nm, s)
