from pathlib import Path

import pytest

import forge_testutil  # noqa: F401
from forge_testutil import EVAL


def test_server_imports_its_own_eval_dir():
    # The server pulls in torch, the SA3 fork and GPU-box paths. Skipped on a CPU-only box (cloud
    # skeleton session, 2026-10-01); run it on the dev machine.
    pytest.importorskip("torch")
    import explorer_render_server as srv
    assert Path(srv.__file__).resolve().parent == EVAL
    # the helper modules must come from the same checkout as the server
    assert Path(srv.cmt.__file__).resolve().parent == EVAL
    assert Path(srv.presets.__file__).resolve().parent == EVAL


def test_forge_package_importable():
    import forge
    assert Path(forge.__file__).resolve().parent == EVAL / "forge"
