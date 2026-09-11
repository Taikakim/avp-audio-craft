"""The unconverged-EMA warning.

WHY: rendering an under-converged EMA shadow renders the run's STARTING point, not what it
learned -- and for a warm start that starting point is a different model entirely. It cost us
both AVP surgical/regsweep sweeps and the suomi full-FTs, silently, because nothing in the
render path ever looked at how far the shadow had travelled.
"""
import importlib.util, math, sys
from pathlib import Path
import pytest

SRC = Path(__file__).resolve().parents[1] / "model_matrix_gen.py"


def _mod():
    spec = importlib.util.spec_from_file_location("mmg_ema", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["mmg_ema"] = m
    spec.loader.exec_module(m)
    return m


def test_no_ema_key_returns_none():
    """A LoRA/DoRA checkpoint has no shadow at all -- not a warning, just nothing to say."""
    assert _mod().ema_convergence({"diffusion.model.x": 1}) is None


def test_uses_ema_step_not_global_step():
    """THE bug this function exists to prevent. A real suomi full-FT had global_step 3160 and
    ema_step 12600 -- reading the wrong one understates travel by 4x and turns 'nearly usable'
    into 'hopeless' (or the reverse)."""
    m = _mod()
    r = m.ema_convergence({"diffusion_ema.ema_step": 12600})
    assert r["ema_step"] == 12600
    assert r["halflives"] == pytest.approx(12600 * (1 - 0.9999) / math.log(2), rel=1e-6)
    assert r["halflives"] == pytest.approx(1.82, abs=0.01)
    assert r["residual_init"] == pytest.approx(0.28, abs=0.01)
    assert r["converged"] is False


def test_the_warm_suomi_case_is_flagged():
    """632 updates at the default beta: the shadow is 94% the WARM-START, i.e. another model."""
    r = _mod().ema_convergence({"diffusion_ema.ema_step": 632})
    assert r["residual_init"] > 0.9
    assert r["converged"] is False


@pytest.mark.parametrize("updates,expect", [(20000, False), (21000, True), (70000, True)])
def test_band_boundary_is_three_halflives(updates, expect):
    """CONTINUITY's band (2026-09-10): >=3 half-lives usable, below that dominated by the start."""
    assert _mod().ema_convergence({"diffusion_ema.ema_step": updates})["converged"] is expect


def test_beta_shortens_the_horizon():
    """A smaller beta converges in fewer updates -- the whole point of choosing beta per run."""
    m = _mod()
    slow = m.ema_convergence({"diffusion_ema.ema_step": 1500}, beta=0.9999)
    fast = m.ema_convergence({"diffusion_ema.ema_step": 1500}, beta=0.9977)
    assert fast["halflives"] > slow["halflives"] * 20
    assert fast["converged"] and not slow["converged"]


def test_assumed_beta_is_labelled_as_assumed():
    """beta is not in the checkpoint. An assumed value must never be reported as known."""
    r = _mod().ema_convergence({"diffusion_ema.ema_step": 100})
    assert r["beta"] == 0.9999 and "assumed" in r["beta_source"]


def test_the_warning_is_actually_wired_into_the_render_path():
    """A helper nothing calls is worthless -- and the beta table is useless unless it is loaded."""
    src = SRC.read_text()
    assert "ema_convergence(_sd_raw" in src
    assert "UNCONVERGED EMA" in src
    assert "_load_ema_betas()" in src.split("def _load_ema_betas")[-1], "loader never called"
