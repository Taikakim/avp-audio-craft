"""Statistics view data, first version: xcorr, XY scatter, time series (spec §4.4, §6.5)."""
import base64
import json
from pathlib import Path

import numpy as np

from .contract import HOP, ForgeError

LIBROSA_FEATURES = ("rms", "onset_strength", "spectral_centroid")
ALIASES = {"bpm": ("bpm_madmom", "bpm_essentia"), "rel_pos": ("relative_position_start",)}


def xcorr_payload(latents, max_frames=20000):
    X = np.concatenate([np.asarray(z, dtype=np.float64).T for z in latents], axis=0)
    n = int(X.shape[0])
    if n > max_frames:
        X = X[np.linspace(0, n - 1, int(max_frames)).round().astype(np.int64)]
    with np.errstate(invalid="ignore", divide="ignore"):
        c = np.nan_to_num(np.corrcoef(X, rowvar=False), nan=0.0)
    q = np.clip(np.rint((c + 1.0) / 2.0 * 255.0), 0, 255).astype(np.uint8)
    return n, {"shape": [256, 256], "data_b64": base64.b64encode(q.tobytes()).decode()}


def resample_points(values, max_points):
    v = np.asarray([np.nan if x is None else x for x in values], dtype=np.float64)
    if len(v) > max_points:
        v = np.interp(np.linspace(0, len(v) - 1, int(max_points)), np.arange(len(v)), v)
    return [None if not np.isfinite(x) else round(float(x), 6) for x in v]


def _fit(v, n):
    v = np.asarray(v, dtype=np.float64)
    if len(v) >= n:
        return v[:n]
    return np.pad(v, (0, n - len(v)), mode="edge") if len(v) else np.zeros(n)


def audio_feature(audio, sr, feature, n_frames):
    import librosa
    mono = np.asarray(audio, dtype=np.float32)
    mono = mono.mean(axis=0) if mono.ndim == 2 else mono
    if feature == "rms":
        v = librosa.feature.rms(y=mono, frame_length=2 * HOP, hop_length=HOP)[0]
    elif feature == "spectral_centroid":
        v = librosa.feature.spectral_centroid(y=mono, sr=sr, n_fft=2 * HOP, hop_length=HOP)[0]
    elif feature == "onset_strength":
        env = librosa.onset.onset_strength(y=mono, sr=sr, hop_length=512)
        k = HOP // 512
        m = len(env) // k
        v = env[: m * k].reshape(m, k).mean(axis=1) if m else env
    else:
        raise ForgeError(400, f"unknown audio feature {feature!r} (have {', '.join(LIBROSA_FEATURES)})")
    return _fit(v, int(n_frames))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)


class DatasetIndex:
    def __init__(self, latent_dir):
        self.rows = []
        keys = set()
        base = Path(latent_dir)
        for jp in sorted(base.glob("*.json")):
            if jp.name.endswith(".TIMESERIES.json") or not jp.with_suffix(".npy").exists():
                continue
            try:
                m = json.loads(jp.read_text())
            except (OSError, ValueError):
                continue
            fields = {k: float(v) for k, v in m.items() if _num(v)}
            for alias, sources in ALIASES.items():
                for s in sources:
                    if s in fields:
                        fields[alias] = fields[s]
                        break
            keys.update(fields)
            label = f"{m.get('track_metadata_artist', '')} — {m.get('track_metadata_title', '')}".strip(" —")
            self.rows.append({"crop_id": jp.stem, "fields": fields, "label": label})
        self._fields = sorted(keys)

    def fields(self):
        return list(self._fields)

    def points(self, x, y, limit=6000):
        for f in (x, y):
            if f not in self._fields:
                raise ForgeError(400, f"unknown field {f!r}")
        pts = [{"crop_id": r["crop_id"], "x": r["fields"][x], "y": r["fields"][y], "label": r["label"]}
               for r in self.rows if x in r["fields"] and y in r["fields"]]
        if len(pts) > limit:
            pts = [pts[i] for i in np.linspace(0, len(pts) - 1, int(limit)).round().astype(int)]
        return pts
