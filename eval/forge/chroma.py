"""SAME octave-band chroma for the CHROMA tab (spec §5.4, §6.3): 3 bands x 128 bins = 384-d."""
import base64

import numpy as np

from .contract import FPS


def _same():
    from harmonic.same_chroma import compute_same_chroma, fold_to_12
    return compute_same_chroma, fold_to_12


def _b64(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a).tobytes(order="C")).decode()


def _quant(a: np.ndarray):
    peak = float(a.max()) if a.size else 0.0
    scale = peak if peak > 0 else 1.0
    return np.clip(np.rint(a / scale * 255.0), 0, 255).astype(np.uint8), scale


def chroma_payload(audio, sr, compute=None, fold=None) -> dict:
    if compute is None or fold is None:
        compute, fold = _same()
    bands = np.maximum(np.asarray(compute(np.asarray(audio, dtype=np.float32).T, sr), dtype=np.float32), 0.0)
    T = int(bands.shape[-1])
    qs, scales = zip(*(_quant(bands[b]) for b in range(3)))
    f12 = np.asarray(fold(bands), dtype=np.float32).sum(axis=0)
    mx = f12.max(axis=0, keepdims=True)
    f12n = np.where(mx > 0, f12 / np.maximum(mx, 1e-12), 0.0)
    q12 = np.clip(np.rint(f12n * 255.0), 0, 255).astype(np.uint8)
    return {"frames": T, "fps": FPS,
            "bands": {"shape": [3, 128, T], "scale": [float(s) for s in scales], "data_b64": _b64(np.stack(qs))},
            "fold12": {"shape": [12, T], "scale": 1.0, "data_b64": _b64(q12)}}


def chroma_384(audio, sr, frames: int) -> np.ndarray:
    compute, _ = _same()
    c = np.asarray(compute(np.asarray(audio, dtype=np.float32).T, sr), dtype=np.float32).reshape(384, -1)
    if c.shape[1] >= frames:
        return np.ascontiguousarray(c[:, :frames])
    return np.pad(c, ((0, 0), (0, frames - c.shape[1])), mode="edge")
