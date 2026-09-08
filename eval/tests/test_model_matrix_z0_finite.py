"""The non-finite-latent guard in model_matrix_gen.

WHY: on 2026-09-08 a long render pass emitted NaN latents partway through -- 110 of 216 cells
in one pass, 108 of 110 in the next. A NaN latent decodes to a FULL-SCALE CONSTANT (peak 1.0,
RMS 1.0): maximum-volume noise that is neither short, quiet, nor truncated, so the file count
was right, ffprobe reported the exact requested duration, and the process exited 0. Those
clips reached the listening board. Only score_and_publish's latent-sanity gate caught them,
and that gate inspects the cfg7/w1 subset alone.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

SRC = Path(__file__).resolve().parents[1] / "model_matrix_gen.py"


def _load():
    """Import model_matrix_gen without running it. Loaded fresh per test so NONFINITE_CELLS
    (module-level) does not leak between cases."""
    spec = importlib.util.spec_from_file_location("mmg_under_test", SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mmg_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_finite_latent_passes_and_records_nothing():
    mmg = _load()
    assert mmg.z0_is_finite(torch.randn(1, 256, 280), "arm/ep1 cfg7 w1.0 kl_0 st24") is True
    assert mmg.NONFINITE_CELLS == []


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_any_non_finite_value_fails(bad):
    mmg = _load()
    z0 = torch.randn(1, 256, 280)
    z0[0, 3, 17] = bad          # ONE bad element out of 71,680 must be enough
    assert mmg.z0_is_finite(z0, "arm/ep1 cfg7 w1.0 kl_0 st24") is False
    assert mmg.NONFINITE_CELLS == ["arm/ep1 cfg7 w1.0 kl_0 st24"]


def test_all_nan_latent_fails():
    """The shape actually seen in the incident: the entire latent non-finite."""
    mmg = _load()
    assert mmg.z0_is_finite(torch.full((1, 256, 512), float("nan")), "arm/ep1 NATIVE") is False
    assert len(mmg.NONFINITE_CELLS) == 1


def test_failures_accumulate_across_cells():
    mmg = _load()
    for i in range(3):
        mmg.z0_is_finite(torch.full((1, 4, 4), float("nan")), f"cell{i}")
    assert mmg.NONFINITE_CELLS == ["cell0", "cell1", "cell2"]


def test_message_names_the_cell_and_says_nothing_was_written(capsys):
    mmg = _load()
    mmg.z0_is_finite(torch.full((1, 4, 4), float("nan")), "arm/ep399 NATIVE 47.55s cfg7 w1.0")
    out = capsys.readouterr().out
    assert "arm/ep399 NATIVE 47.55s cfg7 w1.0" in out
    assert "Nothing written" in out
    assert "16/16" in out          # element count, so a partial burst is distinguishable


def test_guard_is_wired_into_both_render_paths():
    """A helper nothing calls is worthless. Both the grid cell and the native cell must
    consult it, and both must `continue` -- writing NO wav, m4a or manifest line, so the
    cell stays missing and a later resume re-renders it rather than skipping it forever."""
    src = SRC.read_text()
    assert src.count("if not z0_is_finite(") == 2, "expected the grid path AND the native path"
    for chunk in src.split("if not z0_is_finite(")[1:]:
        head = chunk[:400]
        assert "continue" in head
        assert head.index("continue") < head.find("append_manifest") % (len(head) + 1)


def test_base_mirror_is_skipped_when_the_base_render_was_dropped():
    """The base model renders ONE strength and mirrors it across the others. If that single
    render is dropped, base_m4a_name stays None and mirroring would write manifest rows
    pointing at a nonexistent file."""
    src = SRC.read_text()
    assert ("if ckpt_path is None and only_strengths is None and base_m4a_name is not None:"
            in src)
