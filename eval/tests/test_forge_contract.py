import pytest

import forge_testutil  # noqa: F401
from forge import contract
from forge.contract import ForgeError
from forge.paths import ForgePaths


def test_constants():
    assert contract.FPS == 44100 / 4096
    assert contract.CAP_SEC == 374.43 and contract.CAP_FRAMES == 4096
    # a generate pads 6 s before allocating: the capped request is exactly the 4096-frame latent
    assert contract.latent_frames(contract.CAP_SEC + 6.0) == 4096
    assert contract.PRESET_LEVELS == ("prompt", "render", "latch", "film", "lora", "bungee", "master")
    assert contract.AUDIO_EXTS == {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aif", ".aiff"}
    assert contract.MAX_PENDING_JOBS == 4
    assert contract.SPLICE_XFADE_FRAMES == 2


def test_cap():
    assert contract.check_cap(374.43) == 374.43
    with pytest.raises(ForgeError) as e:
        contract.check_cap(374.44)
    assert e.value.status == 400
    assert e.value.message == "forge passes are capped at 374.43 s (4096 latent frames)"
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
