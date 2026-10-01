import json

import numpy as np
import pytest

import forge_testutil  # noqa: F401
from forge.contract import ForgeError
from forge.envelope import sample_envelope, validate_envelope


def test_flat():
    v = sample_envelope({"points": [0.4] * 4, "curves": [0, 0, 0]}, 5)
    assert v.dtype == np.float32
    np.testing.assert_allclose(v, [0.4] * 5, atol=1e-6)


def test_linear_points_with_zero_curves_are_linear():
    v = sample_envelope({"points": [0, 1 / 3, 2 / 3, 1], "curves": [0, 0, 0]}, 7)
    np.testing.assert_allclose(v, np.arange(7) / 6, atol=1e-6)


def test_bent_segment_hand_computed():
    v = sample_envelope({"points": [0, 0, 0, 0], "curves": [0.5, 0, 0]}, 7)
    # k=1: x=1/6, segment 0, s=0.5 -> y = .25*90 + .5*(90-30) + .25*90 = 75 -> v = 15/80
    assert v[1] == pytest.approx(0.1875, abs=1e-6)
    assert v[0] == pytest.approx(0.0, abs=1e-6)
    assert v[2] == pytest.approx(0.0, abs=1e-6)


def test_endpoints_and_single():
    env = {"points": [0.2, 0.9, 0.1, 0.6], "curves": [-1, 1, 0.25]}
    v = sample_envelope(env, 13)
    assert v[0] == pytest.approx(0.2, abs=1e-6)
    assert v[-1] == pytest.approx(0.6, abs=1e-6)
    assert sample_envelope(env, 1)[0] == pytest.approx(0.2, abs=1e-6)
    assert sample_envelope(env, 0).shape == (0,)
    assert v.min() >= 0.0 and v.max() <= 1.0


@pytest.mark.parametrize("env", [
    None, {"points": [0, 0, 0], "curves": [0, 0, 0]}, {"points": [0, 0, 0, 1.2], "curves": [0, 0, 0]},
    {"points": [0, 0, 0, 0], "curves": [0, 2, 0]}, {"points": [0, 0, 0, "x"], "curves": [0, 0, 0]},
])
def test_validate_rejects(env):
    with pytest.raises(ForgeError):
        validate_envelope(env)


def test_vectors_file_matches_code():
    from forge.write_vectors import VECTOR_DIR, envelope_vectors
    path = VECTOR_DIR / "envelope.json"
    assert path.exists(), "run: $PY eval/forge/write_vectors.py"
    assert json.loads(path.read_text()) == envelope_vectors()
