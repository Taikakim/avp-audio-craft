"""Training data from pre-encoded SA3 latents + grid-aligned mir control features.

Each item is a SAME-L latent (256, 4096), control features already at T=4096 (from
the per-crop .TIMESERIES.npz — no resampling), the text prompt, and an audio
reference latent (a different crop of the same track) for the riffer branch.
No audio decode/encode, no on-the-fly feature extraction.
"""

from __future__ import annotations

import glob
import json
import os
from collections import defaultdict

import numpy as np
import torch
from torch.utils.data import Dataset

# Raw control channels pulled straight from the .TIMESERIES.npz (each already T=4096).
CONTROL_FIELDS = {
    "dynamics": ["rms_energy_bass_ts", "rms_energy_body_ts", "rms_energy_mid_ts", "rms_energy_air_ts"],
    "rhythm": ["beat_activation_ts", "downbeat_activation_ts", "onset_envelope_ts"],
    "melody": ["hpcp_ts"],
    "density_ts": ["onset_envelope_ts"],   # 1-ch onset-density curve (time-varying density control)
    "chroma384": ["same_chroma_ts"],       # SAME 384-d chroma (3 bands x 128), stored (T,384); data-gen TODO
    "fp_volatile": ["onset_envelope_ts", "rms_energy_mid_ts"],  # volatile V-B window channels for fingerprint
}
CONTROL_DIMS = {"dynamics": 4, "rhythm": 3, "melody": 12, "density_ts": 1, "chroma384": 384, "audio": 256,
                "fp_volatile": 2}


# ---------------------------------------------------------------------------
# Fingerprint helpers
# ---------------------------------------------------------------------------

def fingerprint_in_dim(variant: str, k: int) -> int:
    """Total fingerprint vector length.

    k = len(genre_vocab); the genre block is k+1 (k raw probs + 'other' bucket).
    Variants:
      "A" -> genre(k+1) + year + bpm + sync          = k+4
      "B" -> genre(k+1) + year + bpm + sync + onset + energy = k+6
      "C" -> genre(k+1) + year                        = k+2
    """
    base = k + 1 + 1            # genre(k) + other(1) + year(1)
    return {"A": base + 2, "B": base + 4, "C": base}[variant]


def window_energy(rms_window) -> float:
    """Mean RMS energy over a timeseries window. Accepts ndarray or Tensor."""
    return float(np.asarray(rms_window, dtype=np.float32).mean())


def window_onset_density(onset_env_window, frame_rate: float = 10.767) -> float:
    """Onset count per second from an onset-envelope window.

    Peaks are local maxima above mean+std threshold (same logic as beat_aligned_start).
    Returns 0.0 if the window is too short to detect peaks.
    """
    a = np.asarray(onset_env_window, dtype=np.float32).reshape(-1)
    if a.size < 3:
        return 0.0
    thr = a.mean() + a.std()
    pk = np.where((a[1:-1] > a[:-2]) & (a[1:-1] >= a[2:]) & (a[1:-1] > thr))[0]
    return float(len(pk)) / (len(a) / frame_rate)


def _to_ct(arr: np.ndarray) -> np.ndarray:
    """(T,) -> (1, T); (T, C) -> (C, T). float32."""
    arr = np.asarray(arr, dtype=np.float32)
    return arr[None, :] if arr.ndim == 1 else arr.T


def track_key(meta: dict, path: str) -> str:
    """Group crops by their source track. All crops of a track share `path`
    (the source full_mix.flac); `relpath`'s number is a GLOBAL crop id, so its
    dirname (`<Artist - Title>`) is the per-track fallback."""
    p = meta.get("path")
    if p:
        return p
    rel = meta.get("relpath")
    if rel:
        return os.path.dirname(rel)
    return path


class LatentControlDataset(Dataset):
    """(latent, controls, prompt, ref_latent) from a latents_sa3 directory."""

    def __init__(self, root, controls=("dynamics", "rhythm", "melody"),
                 audio_ref="same_track", seed=0, subset_tracks=None,
                 scalar_field=None, scalar_norm=(0.0, 1.0), random_crop_frames=None,
                 # style-fingerprint kwargs
                 fingerprint: bool = False,
                 genre_vocab: "list[str] | None" = None,
                 fp_variant: str = "A",
                 year_norm=(1990.0, 30.0),
                 bpm_norm=(140.0, 20.0),
                 sync_norm=(0.5, 0.25),
                 onset_norm=(0.0, 1.0),
                 energy_norm=(0.0, 1.0)):
        self.root = root
        self.controls = [c for c in controls if c in CONTROL_FIELDS]
        self.audio_ref = audio_ref
        self.scalar_field = scalar_field            # e.g. "onset_density" — a per-crop .json scalar control
        self.scalar_mean, self.scalar_std = scalar_norm
        self.random_crop_frames = random_crop_frames   # int N = return a RANDOM beat-aligned N-frame window
        # style-fingerprint mode
        self.fingerprint = bool(fingerprint)
        self.genre_vocab = list(genre_vocab) if genre_vocab else []
        self.fp_variant = fp_variant
        self.year_norm, self.bpm_norm = year_norm, bpm_norm
        self.sync_norm, self.onset_norm, self.energy_norm = sync_norm, onset_norm, energy_norm
        if self.fingerprint and fp_variant == "B" and "fp_volatile" not in self.controls:
            self.controls = list(self.controls) + ["fp_volatile"]  # load onset+energy timeseries
        self.paths = sorted(glob.glob(os.path.join(root, "*.npy")))
        # drop junk crops with no .json companion (e.g. silence.npy) — they lack every
        # sidecar and would crash the timeseries loader in fingerprint/window mode, where
        # the scalar_field filter below (which also excludes them) never runs.
        self.paths = [p for p in self.paths if os.path.exists(p[:-4] + ".json")]
        self.meta = {}
        self.by_track = defaultdict(list)
        for p in self.paths:
            j = p[:-4] + ".json"
            m = json.load(open(j)) if os.path.exists(j) else {}
            self.meta[p] = m
            self.by_track[track_key(m, p)].append(p)
        if subset_tracks is not None:           # keep a random subset of TRACKS (not crops),
            keys = sorted(self.by_track)         # so each kept track keeps all its crops and the
            np.random.default_rng(seed).shuffle(keys)   # audio-reference pairing still works
            n = int(subset_tracks * len(keys)) if subset_tracks <= 1 else int(subset_tracks)
            keep = set(keys[:max(1, n)])
            self.by_track = defaultdict(list, {k: v for k, v in self.by_track.items() if k in keep})
            self.paths = [p for p in self.paths if track_key(self.meta[p], p) in keep]
        if scalar_field is not None:            # drop crops with no scalar label (e.g. junk 'silence.npy')
            before = len(self.paths)
            self.paths = [p for p in self.paths if scalar_field in self.meta.get(p, {})]
            if len(self.paths) < before:
                print(f"[dataset] dropped {before - len(self.paths)} crops missing '{scalar_field}'", flush=True)
        self._rng = np.random.default_rng(seed)

    def __len__(self):
        return len(self.paths)

    def _load_controls(self, stem: str) -> dict:
        if not self.controls:                       # scalar/no-timeseries mode: don't touch the npz
            return {}                               # (some crops, e.g. 'silence', have no .TIMESERIES.npz)
        z = np.load(stem + ".TIMESERIES.npz")
        chroma_z = None                             # lazy: the .CHROMA.npz sidecar (e.g. same_chroma_ts)
        out = {}
        for name in self.controls:
            chans = []
            for f in CONTROL_FIELDS[name]:
                if f in z:
                    chans.append(_to_ct(z[f]))
                else:                               # field lives in the parallel <crop>.CHROMA.npz sidecar
                    if chroma_z is None:
                        chroma_z = np.load(stem + ".CHROMA.npz")
                    chans.append(_to_ct(chroma_z[f]))
            out[name] = torch.from_numpy(np.concatenate(chans, axis=0))  # (C, 4096)
        return out

    def _pick_reference(self, path: str) -> torch.Tensor:
        peers = self.by_track.get(track_key(self.meta[path], path), [path])
        cands = [q for q in peers if q != path] or [path]
        ref = cands[int(self._rng.integers(len(cands)))]
        return torch.from_numpy(np.load(ref).astype(np.float32))  # (256, 4096)

    def _build_fingerprint(self, m: dict, controls: dict) -> torch.Tensor:
        """Assemble the style-fingerprint vector from crop meta + window-sliced controls.

        Layout (in order):
          genre probs (k dims, vocab order) | other bucket (1 dim) | year (1 dim)
          [variant A/B] bpm (1 dim) | syncopation (1 dim)
          [variant B only] window_onset_density (1 dim) | window_energy (1 dim)

        Volatile dims (onset/energy) come from the ALREADY-SLICED controls["fp_volatile"]
        tensor — NOT from any crop-level .json scalar — so they reflect the actual window
        being trained on (the window-scalar alignment fix).
        """
        g = m.get("style_genre", {})
        vec = [float(g.get(name, 0.0)) for name in self.genre_vocab]     # genre block (vocab order)
        vec.append(float(g.get("other", max(0.0, 1.0 - sum(vec)))))      # other bucket
        ym, ys = self.year_norm
        vec.append((float(m.get("release_year", ym)) - ym) / ys)         # normalised year
        if self.fp_variant in ("A", "B"):
            bm, bs = self.bpm_norm
            sm, ss = self.sync_norm
            vec.append((float(m.get("bpm_madmom", bm)) - bm) / bs)      # normalised bpm (track-level stable)
            vec.append((float(m.get("syncopation", sm)) - sm) / ss)      # normalised syncopation
        if self.fp_variant == "B":
            vol = controls["fp_volatile"]                                 # (2, tw) — ALREADY sliced to window
            onset_w = vol[0].numpy()
            energy_w = vol[1].numpy()
            om, os_ = self.onset_norm
            em, es_ = self.energy_norm
            vec.append((window_onset_density(onset_w) - om) / os_)       # window-aggregated (alignment fix)
            vec.append((window_energy(energy_w) - em) / es_)
        return torch.tensor(vec, dtype=torch.float32)

    def _beat_aligned_start(self, stem: str, t_total: int) -> int:
        """Random window start snapped to a beat (peak of beat_activation_ts); plain-random fallback.
        Gives crop variety across epochs so training stops seeing only the first window of each track."""
        tw = self.random_crop_frames
        hi = t_total - tw
        if hi <= 0:
            return 0
        try:
            a = np.asarray(np.load(stem + ".TIMESERIES.npz")["beat_activation_ts"],
                           dtype=np.float32).reshape(-1)[:t_total]
            thr = a.mean() + a.std()
            pk = np.where((a[1:-1] > a[:-2]) & (a[1:-1] >= a[2:]) & (a[1:-1] > thr))[0] + 1
            pk = pk[pk <= hi]
            if len(pk):
                return int(pk[self._rng.integers(len(pk))])
        except Exception:
            pass
        return int(self._rng.integers(hi + 1))

    def __getitem__(self, i: int) -> dict:
        p = self.paths[i]
        stem = p[:-4]
        m = self.meta[p]
        lat = np.load(p).astype(np.float32)
        while lat.ndim > 2 and lat.shape[0] == 1:   # squeeze stray batch dims, e.g. (1,256,4096) -> (256,4096)
            lat = lat[0]
        controls = self._load_controls(stem)
        if self.random_crop_frames and lat.shape[-1] > self.random_crop_frames:  # beat-aligned random window
            s = self._beat_aligned_start(stem, lat.shape[-1]); tw = self.random_crop_frames
            lat = np.ascontiguousarray(lat[:, s:s + tw])
            controls = {k: v[:, s:s + tw].contiguous() for k, v in controls.items()}
        item = {
            "latent": torch.from_numpy(lat),                             # (256, 4096) or (256, crop) if random
            "prompt": m.get("prompt", ""),
            "controls": controls,
            "stem": os.path.basename(stem),
            "seconds_total": float(m.get("seconds_total", 0.0)),
        }
        if self.audio_ref == "same_track":
            item["ref_latent"] = self._pick_reference(p)
        if self.fingerprint:
            item["fingerprint"] = self._build_fingerprint(m, controls)
        if self.scalar_field is not None:           # normalised per-crop scalar control (e.g. onset_density)
            raw = float(m.get(self.scalar_field, self.scalar_mean))
            item["scalar"] = torch.tensor((raw - self.scalar_mean) / (self.scalar_std + 1e-9), dtype=torch.float32)
        pm = m.get("padding_mask")
        if pm is not None:
            item["padding_mask"] = torch.tensor(np.asarray(pm, dtype=np.float32))
        return item

    def track_stats(self) -> dict:
        sizes = [len(v) for v in self.by_track.values()]
        return {"crops": len(self.paths), "tracks": len(self.by_track),
                "crops_per_track_min": min(sizes), "crops_per_track_max": max(sizes),
                "crops_per_track_mean": round(sum(sizes) / len(sizes), 2),
                "singletons": sum(1 for s in sizes if s == 1)}
