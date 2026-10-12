import numpy as np
import pytest
import soundfile as sf

import forge_testutil  # noqa: F401
from forge import stretch
from forge.contract import ForgeError


def test_validate_and_identity():
    assert stretch.validate(1.0, 0.0) == (1.0, 0.0)
    for bad in [(0.49, 0), (2.01, 0), (1, 24.5), ("x", 0)]:
        with pytest.raises(ForgeError):
            stretch.validate(*bad)
    assert stretch.is_identity(1.0004, 0.00005)
    assert not stretch.is_identity(1.001, 0)


def test_cache_key_rounding():
    a = stretch.cache_key("f" * 64, 1.0000001, 0.00001)
    b = stretch.cache_key("f" * 64, 1.0000004, 0.00004)
    assert a == b and len(a) == 64
    assert a != stretch.cache_key("f" * 64, 1.1, 0.0)


needs_bungee = pytest.mark.skipif(not stretch.BUNGEE_PY.exists(), reason="mir/.venv not present")


def dominant_hz(y, sr):
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    return np.fft.rfftfreq(len(y), 1 / sr)[int(np.argmax(spec))]


@needs_bungee
def test_speed_and_pitch(tmp_path):
    sr = 44100
    t = np.arange(2 * sr) / sr
    tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    src = tmp_path / "in.wav"
    sf.write(src, np.stack([tone, tone], axis=1), sr, subtype="FLOAT")
    fast = stretch.stretch_file(src, tmp_path / "fast.wav", 2.0, 0.0)
    y, _ = sf.read(fast, always_2d=True)
    assert y.shape[0] / sr == pytest.approx(1.0, rel=0.06)
    up = stretch.stretch_file(src, tmp_path / "up.wav", 1.0, 12.0)
    y2, _ = sf.read(up, always_2d=True)
    mid = y2[len(y2) // 4: 3 * len(y2) // 4, 0]
    assert dominant_hz(mid, sr) == pytest.approx(880.0, rel=0.03)
    assert not list(tmp_path.glob("*.part.wav"))
