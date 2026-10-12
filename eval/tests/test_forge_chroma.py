import base64
import sys
from pathlib import Path

import numpy as np
import pytest

import forge_testutil  # noqa: F401

MIRCHROMA = Path("/home/kim/Projects/mir-same-chroma/src")
pytestmark = pytest.mark.skipif(not MIRCHROMA.is_dir(), reason="mir-same-chroma checkout missing")
if MIRCHROMA.is_dir() and str(MIRCHROMA) not in sys.path:
    sys.path.insert(0, str(MIRCHROMA))

from forge.chroma import chroma_384, chroma_payload  # noqa: E402


def tone(hz, seconds=3.0, sr=44100):
    t = np.arange(int(seconds * sr)) / sr
    y = (0.5 * np.sin(2 * np.pi * hz * t)).astype(np.float32)
    return np.stack([y, y])


def test_a440_folds_to_pitch_class_a():
    p = chroma_payload(tone(440.0), 44100)
    T = p["frames"]
    assert p["fps"] == 44100 / 4096
    assert p["bands"]["shape"] == [3, 128, T] and len(p["bands"]["scale"]) == 3
    raw = np.frombuffer(base64.b64decode(p["bands"]["data_b64"]), dtype=np.uint8)
    assert raw.size == 3 * 128 * T
    f12 = np.frombuffer(base64.b64decode(p["fold12"]["data_b64"]), dtype=np.uint8).reshape(12, T)
    assert int(np.argmax(f12.mean(axis=1))) == 9          # C C# D D# E F F# G G# A -> 9
    assert f12.max() == 255


def test_silence_is_all_zero_but_valid():
    p = chroma_payload(np.zeros((2, 44100), dtype=np.float32), 44100)
    f12 = np.frombuffer(base64.b64decode(p["fold12"]["data_b64"]), dtype=np.uint8)
    assert f12.max() == 0 and all(s == 1.0 for s in p["bands"]["scale"])


def test_chroma_384_fits_frames():
    c = chroma_384(tone(220.0, 2.0), 44100, 30)
    assert c.shape == (384, 30) and c.dtype == np.float32
