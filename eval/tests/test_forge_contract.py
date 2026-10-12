import pytest

import forge_testutil  # noqa: F401
from forge import contract
from forge.contract import ForgeError
from forge.paths import ForgePaths


def test_constants():
    assert contract.FPS == 44100 / 4096
    assert contract.CAP_SEC == 184.0
    assert contract.PRESET_LEVELS == ("prompt", "render", "latch", "film", "lora", "bungee", "master")
    assert contract.AUDIO_EXTS == {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aif", ".aiff"}
    assert contract.MAX_PENDING_JOBS == 4
    assert contract.SPLICE_XFADE_FRAMES == 2


def test_cap():
    assert contract.check_cap(184.0) == 184.0
    with pytest.raises(ForgeError) as e:
        contract.check_cap(184.01)
    assert e.value.status == 400
    assert e.value.message == "forge passes are capped at 184 s locally (T<2048)"
    with pytest.raises(ForgeError):
        contract.check_cap(0)
    with pytest.raises(ForgeError):
        contract.check_cap(float("nan"))


@pytest.mark.parametrize("name", ["a", "Club_mix-v1.2", "x" * 80])
def test_names_ok(name):
    assert contract.check_name(name) == name


@pytest.mark.parametrize("name", ["", ".", "..", "a/b", "x" * 81, "sp ace", None, 3])
def test_names_bad(name):
    with pytest.raises(ForgeError) as e:
        contract.check_name(name)
    assert e.value.status == 400


def test_levels():
    assert contract.check_level("render") == "render"
    with pytest.raises(ForgeError):
        contract.check_level("sampling")


def test_latent_frames():
    assert contract.latent_frames(184.0) == 1982
    assert contract.latent_frames(1.0) == 11


def test_paths(tmp_path):
    p = ForgePaths(tmp_path).ensure()
    assert p.root == tmp_path / "_forge"
    for d in (p.uploads, p.sessions, p.presets, p.cache):
        assert d.is_dir()
    assert p.cache_dir("chroma") == tmp_path / "_forge" / "cache" / "chroma"
    assert p.cache_dir("chroma").is_dir()
    assert p.preset_dir("render") == tmp_path / "_forge" / "presets" / "render"
    with pytest.raises(ForgeError):
        p.preset_dir("nope")
