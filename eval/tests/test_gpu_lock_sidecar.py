"""Per-instance GPU sidecars: the lock stays EXCLUSIVE, the holder becomes ASKABLE.

Kim 2026-08-27, after GHOST-NOTE waited 10.6 h on a lock it could not tell was a
RESIDENT SERVER (yieldable on request) rather than a batch job that would finish
on its own. The canonical /tmp/gpu.lock format must NOT grow fields -- non-team
instances parse it -- so the metadata lives in a per-handle companion file.
"""
import importlib.util
import sys

import pytest


def _load_filelock():
    """Load Misc/filelock.py BY PATH, never by putting Misc/ on sys.path.

    Misc/ contains a first-party filelock.py that SHADOWS the pip `filelock`
    package huggingface_hub needs; prepending that directory breaks unrelated test
    modules three imports away with `cannot import name 'BaseFileLock'`. Same trap
    as Misc/build_evals.py -- see MASTER.md section 5. sys.path is restored either way.
    """
    spec = importlib.util.spec_from_file_location(
        "_sao_filelock", "/home/kim/Projects/SAO/Misc/filelock.py")
    mod = importlib.util.module_from_spec(spec)
    saved = list(sys.path)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved
    return mod


filelock = _load_filelock()


@pytest.fixture
def mirror(tmp_path, monkeypatch):
    m = tmp_path / "gpu.lock"
    monkeypatch.setattr(filelock, "GPU_MIRROR_PATH", str(m))
    return m


def test_the_sidecar_is_named_for_the_instance(mirror):
    assert filelock._sidecar_path("CONTINUITY").endswith("gpu.lock.continuity")
    assert filelock._sidecar_path("Ghost-Note").endswith("gpu.lock.ghost-note")


def test_a_server_hold_is_marked_yieldable(mirror):
    filelock._sidecar_write("CONTINUITY", 1, kind="server", note="render server")
    d = {x["handle"]: x for x in filelock.gpu_holders()}["CONTINUITY"]
    assert d["kind"] == "server" and d["yieldable"] == "yes"
    assert d["note"] == "render server"


def test_a_batch_hold_is_not_yieldable(mirror):
    filelock._sidecar_write("WINTERMUTE", 1, kind="batch")
    d = {x["handle"]: x for x in filelock.gpu_holders()}["WINTERMUTE"]
    assert d["kind"] == "batch" and d["yieldable"] == "no"


def test_release_clears_only_its_own_sidecar(mirror):
    filelock._sidecar_write("CONTINUITY", 1, kind="server")
    filelock._sidecar_write("GHOSTNOTE", 2, kind="batch")
    filelock._sidecar_clear("CONTINUITY")
    assert [d["handle"] for d in filelock.gpu_holders()] == ["GHOSTNOTE"]


def test_a_stale_sidecar_is_REPORTED_not_hidden(mirror):
    # a dead holder's leftover is itself a finding -- hiding it would recreate the
    # exact confusion this feature exists to remove
    filelock._sidecar_write("CONTINUITY", 999999, kind="server")
    d = filelock.gpu_holders()[0]
    assert d["alive"] is False


def test_no_sidecars_means_nobody_announced_not_nobody_holding(mirror):
    # rocm-smi stays ground truth; the sidecar is only a claim, same as the lockfile
    assert filelock.gpu_holders() == []
