"""Time-stretch / pitch-shift through Bungee in mir/.venv (spec §6.3 POST /forge/stretch).

speed > 1 = faster (shorter), the Bungee convention; semitones > 0 = up.
"""
import hashlib
import math
import os
import subprocess
from pathlib import Path

from .contract import ForgeError

BUNGEE_PY = Path("/home/kim/Projects/mir/.venv/bin/python")
BUNGEE_TAG = "bungee-0.2.1"

_CODE = r"""
import sys
import numpy as np
import soundfile as sf
from bungee_python import bungee as B
src, dst, speed, semis = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
d, sr = sf.read(src, dtype="float32", always_2d=True)
st = B.Bungee(sample_rate=sr, channels=d.shape[1])
if abs(semis) > 1e-4:
    st.set_pitch(2.0 ** (semis / 12.0))
if abs(speed - 1.0) > 5e-4:
    st.set_speed(speed)
y = np.asarray(st.process(d), dtype=np.float32)
if y.ndim == 1:
    y = y.reshape(-1, d.shape[1])
sf.write(dst, y, sr, subtype="FLOAT")
"""


def validate(speed, semitones):
    try:
        sp, se = float(speed), float(semitones)
    except (TypeError, ValueError):
        raise ForgeError(400, "speed and semitones must be numbers")
    if not (math.isfinite(sp) and 0.5 <= sp <= 2.0):
        raise ForgeError(400, f"speed {speed!r} outside 0.5..2")
    if not (math.isfinite(se) and -24.0 <= se <= 24.0):
        raise ForgeError(400, f"semitones {semitones!r} outside -24..24")
    return sp, se


def is_identity(speed, semitones) -> bool:
    return abs(float(speed) - 1.0) < 5e-4 and abs(float(semitones)) < 1e-4


def cache_key(file_sha, speed, semitones) -> str:
    raw = f"{file_sha}|{round(float(speed), 6):.6f}|{round(float(semitones), 4):.4f}|{BUNGEE_TAG}"
    return hashlib.sha256(raw.encode()).hexdigest()


def stretch_file(src, dst, speed, semitones, python=BUNGEE_PY, timeout=900) -> Path:
    dst = Path(dst)
    tmp = dst.with_name(dst.stem + ".part.wav")
    r = subprocess.run([str(python), "-c", _CODE, str(src), str(tmp), repr(float(speed)), repr(float(semitones))],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 or not tmp.exists():
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"bungee failed (rc={r.returncode}): {r.stderr.strip()[-400:]}")
    os.replace(tmp, dst)
    return dst
