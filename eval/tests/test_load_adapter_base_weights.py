"""load_adapter_base_weights must fail LOUD once a real --init_state_ckpt is found, not swallow it.

An arm warm-started from a full-FT checkpoint (goa5k_fullft_avp_dora_3e-3_* — "CRITICAL: invalid on
vanilla medium-base") renders silently WRONG if this step quietly no-ops on a coverage/load failure:
adapter deltas trained against the warm-started base get baked onto stock medium-base instead. Only
the run_meta.json LOOKUP itself (missing/unparseable file, an init_ckpt path absent on this machine)
is meant to be tolerated (2026-09-28, W's review).
"""
import json
import sys
import types
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model_matrix_gen as mmg  # noqa: E402


def _fake_model(dit):
    """model.model.model == dit, matching StableAudioModel.model.model (== .dit) at render time."""
    return types.SimpleNamespace(model=types.SimpleNamespace(model=dit))


def _write_run_meta(run_dir, init_ckpt):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(json.dumps({"args": {"init_state_ckpt": str(init_ckpt)}}))


def test_no_run_meta_is_a_silent_noop(tmp_path):
    ckpt = tmp_path / "run" / "step=10.ckpt"
    ckpt.parent.mkdir(parents=True)
    ckpt.touch()
    assert mmg.load_adapter_base_weights(_fake_model(torch.nn.Linear(4, 4)), ckpt) is False


def test_no_init_state_ckpt_configured_is_a_silent_noop(tmp_path):
    """An arm that never used --init_state_ckpt at all -- nothing to load, nothing to warn about."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "run_meta.json").write_text(json.dumps({"args": {}}))
    ckpt = run_dir / "step=10.ckpt"
    ckpt.touch()
    assert mmg.load_adapter_base_weights(_fake_model(torch.nn.Linear(4, 4)), ckpt) is False


def test_init_ckpt_path_missing_on_this_machine_raises(tmp_path):
    """CONTINUITY's catch (2026-09-28): an arm whose run_meta.json DOES say it was warm-started,
    but whose init_ckpt is absent (e.g. an unmounted drive), must not silently fall through to
    rendering against stock medium-base -- that is indistinguishable from bug 1 in spirit."""
    run_dir = tmp_path / "run"
    _write_run_meta(run_dir, tmp_path / "does_not_exist.ckpt")
    ckpt = run_dir / "step=10.ckpt"
    ckpt.touch()
    with pytest.raises(FileNotFoundError, match="does not exist on this machine"):
        mmg.load_adapter_base_weights(_fake_model(torch.nn.Linear(4, 4)), ckpt)


def test_good_coverage_loads_and_returns_true(tmp_path):
    dit = torch.nn.Linear(4, 4)
    base_ckpt = tmp_path / "fullft.ckpt"
    donor = torch.nn.Linear(4, 4)
    torch.nn.init.constant_(donor.weight, 7.0)
    torch.save({"state_dict": {"diffusion.model.weight": donor.weight.detach(),
                               "diffusion.model.bias": donor.bias.detach()}}, base_ckpt)
    run_dir = tmp_path / "run"
    _write_run_meta(run_dir, base_ckpt)
    ckpt = run_dir / "step=10.ckpt"
    ckpt.touch()

    assert mmg.load_adapter_base_weights(_fake_model(dit), ckpt) is True
    assert torch.allclose(dit.weight, torch.full((4, 4), 7.0))


def test_bad_coverage_raises_instead_of_warning_and_continuing(tmp_path):
    """The regression this test guards: the original code caught this AssertionError in a bare
    `except Exception` and returned from the loop having only printed a warning, so the caller
    (model_matrix_gen's render loop) proceeded to render the adapter against an UNCHANGED, wrong
    base. It must now propagate."""
    dit = torch.nn.Linear(4, 4)
    base_ckpt = tmp_path / "unrelated.ckpt"
    torch.save({"state_dict": {"totally.unrelated.key": torch.zeros(3)}}, base_ckpt)
    run_dir = tmp_path / "run"
    _write_run_meta(run_dir, base_ckpt)
    ckpt = run_dir / "step=10.ckpt"
    ckpt.touch()

    with pytest.raises(AssertionError, match="covers only"):
        mmg.load_adapter_base_weights(_fake_model(dit), ckpt)


def test_malformed_run_meta_json_is_tolerated_not_fatal(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "run_meta.json").write_text("{not json")
    ckpt = run_dir / "step=10.ckpt"
    ckpt.touch()
    assert mmg.load_adapter_base_weights(_fake_model(torch.nn.Linear(4, 4)), ckpt) is False
