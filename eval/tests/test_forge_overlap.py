import numpy as np

import forge_testutil  # noqa: F401
from forge.overlap import chroma_target, pad_target, region_frames

LIN = {"points": [0, 1 / 3, 2 / 3, 1], "curves": [0, 0, 0]}


def test_region_frames_clamped():
    assert region_frames(0.25, 0.75, 10.0, 100) == (2, 8)
    assert region_frames(-1.0, 50.0, 10.0, 100) == (0, 100)


def test_chroma_target_ramps():
    A = np.zeros((384, 10), np.float32)
    B = np.ones((384, 10), np.float32)
    t = chroma_target(A, B, 3, 8, LIN)
    np.testing.assert_allclose(t[0], [0, 0, 0, 0, 0.25, 0.5, 0.75, 1, 1, 1], atol=1e-6)


def test_pad_target():
    x = np.arange(6, dtype=np.float32).reshape(2, 3)
    np.testing.assert_allclose(pad_target(x, 5), [[0, 1, 2, 2, 2], [3, 4, 5, 5, 5]])
    np.testing.assert_allclose(pad_target(x, 2), [[0, 1], [3, 4]])
