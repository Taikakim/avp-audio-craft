"""--only-strengths replaces the adapter sweep (so w0.5 can render) but only filters pinned rows."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model_matrix_gen import STRENGTHS, strength_sweep  # noqa: E402


def test_adapter_default_and_replacement():
    assert strength_sweep(False, None) == STRENGTHS
    assert strength_sweep(False, (0.5,)) == (0.5,)
    assert strength_sweep(False, (1.0, 1.5, 2.0)) == (1.0, 1.5, 2.0)


def test_pinned_rows_stay_at_one():
    assert strength_sweep(True, None) == (1.0,)
    assert strength_sweep(True, (0.5,)) == ()
    assert strength_sweep(True, (1.0, 0.5)) == (1.0,)
