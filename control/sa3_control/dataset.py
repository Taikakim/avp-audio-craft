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


def window_onset_density_active(onset_env_window, rms_window,
                                frame_rate: float = 10.767,
                                gate_frac: float = 0.1) -> float:
    """Onset density over ACTIVE time only (the outro-cheat fix, Kim 2026-07-07):
    frames whose RMS falls below gate_frac x the window's 90th-percentile RMS are
    excluded from BOTH the peak count and the duration denominator — an empty
    tail or outro can no longer fake a low density."""
    a = np.asarray(onset_env_window, dtype=np.float32).reshape(-1)
    r = np.asarray(rms_window, dtype=np.float32).reshape(-1)
    n = min(len(a), len(r))
    a, r = a[:n], r[:n]
    if n < 3:
        return 0.0
    gate = gate_frac * (np.percentile(r, 90) + 1e-12)
    active = r > gate
    active_frames = int(active.sum())
    if active_frames < 3:
        return 0.0
    thr = a[active].mean() + a[active].std()
    pk = np.where((a[1:-1] > a[:-2]) & (a[1:-1] >= a[2:]) & (a[1:-1] > thr)
                  & active[1:-1])[0]
    return float(len(pk)) / (active_frames / frame_rate)


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
                 active_density=False,
                 dual_scalar: bool = False,
                 # style-fingerprint kwargs
                 fingerprint: bool = False,
                 genre_vocab: "list[str] | None" = None,
                 fp_variant: str = "A",
                 year_norm=(1990.0, 30.0),
                 bpm_norm=(140.0, 20.0),
                 sync_norm=(0.5, 0.25),
                 onset_norm=(0.0, 1.0),
                 energy_norm=(0.0, 1.0),
                 # melody-contour conditioning (Head B): sidecar dir of per-crop
                 # <stem>.melody8.npy int8 (4096,) class streams (prep_melody_conditioning.py).
                 # Set -> items carry "melody_cls" (T,) int64; crops without a stream are dropped.
                 melody_dir=None,
                 # metrical-position conditioning (E3): sidecar dir of per-crop
                 # <stem>.metrical.npy int8 (5, 4096) tree-position streams (rows =
                 # subdiv/beat/bar/phrase/coverage) + <stem>.metrical_conf.npy float16 (4096,).
                 # Set -> items carry "metrical_cls" (5, T) int64 + "metrical_conf" (T,) float32.
                 # UNLIKE melody_dir, crops WITHOUT a sidecar are KEPT, not dropped — they get the
                 # all-zero null token (coverage=0), the zero-condition dropout design
                 # (docs/superpowers/specs/2026-07-31-metrical-tree-pe-design.md §2).
                 metrical_dir=None):
        self.root = root
        self.melody_dir = melody_dir
        self.metrical_dir = metrical_dir
        self.controls = [c for c in controls if c in CONTROL_FIELDS]
        self.audio_ref = audio_ref
        self.scalar_field = scalar_field            # e.g. "onset_density" — a per-crop .json scalar control
        self.active_density = active_density        # rms-gated density (outro-cheat fix)
        self.scalar_mean, self.scalar_std = scalar_norm
        self.dual_scalar = bool(dual_scalar)        # emit [standardize(feature), standardize(bpm_madmom)] per crop
        self.random_crop_frames = random_crop_frames   # int N = return a RANDOM beat-aligned N-frame window
        # style-fingerprint mode
        self.fingerprint = bool(fingerprint)
        self.genre_vocab = list(genre_vocab) if genre_vocab else []
        self.fp_variant = fp_variant
        self.year_norm, self.bpm_norm = year_norm, bpm_norm
        # dual_scalar's bpm (feature 2) standardization: defaults to bpm_norm, overwritten by the
        # trainer with corpus (mean,std) computed the same way the scalar path computes its stats.
        self.bpm_mean, self.bpm_std = bpm_norm
        self.sync_norm, self.onset_norm, self.energy_norm = sync_norm, onset_norm, energy_norm
        if self.fingerprint and fp_variant == "B" and "fp_volatile" not in self.controls:
            self.controls = list(self.controls) + ["fp_volatile"]  # load onset+energy timeseries
        # multi-root: accept a single dir (str/Path) OR a list of dirs — glob each and
        # concatenate the FULL-PATH lists. Because every item carries its own absolute path,
        # this sidesteps the 000000.* stem COLLISION between corpora (goa + avp). Single-dir
        # behaviour is byte-identical (one sorted glob over the one root).
        _roots = list(root) if isinstance(root, (list, tuple)) else [root]
        self.paths = []
        for _r in _roots:
            self.paths.extend(sorted(glob.glob(os.path.join(str(_r), "*.npy"))))
        # drop junk crops with no .json companion (e.g. silence.npy) — they lack every
        # sidecar and would crash the timeseries loader in fingerprint/window mode, where
        # the scalar_field filter below (which also excludes them) never runs.
        self.paths = [p for p in self.paths if os.path.exists(p[:-4] + ".json")]
        if self.melody_dir is not None:         # melody mode: keep only crops with a class stream
            before = len(self.paths)            # (BEFORE subset_tracks, so a subset fraction is
            self.paths = [p for p in self.paths # relative to melody-covered tracks, not all 5.4k)
                          if os.path.exists(self._melody_path(p))]
            print(f"[dataset] melody_dir: {len(self.paths)}/{before} crops have a "
                  f".melody8.npy stream", flush=True)
        if self.metrical_dir is not None:       # metrical mode: NO filtering — uncovered crops
            n_cov = sum(1 for p in self.paths   # already carry the all-zero null (coverage=0),
                        if os.path.exists(self._metrical_path(p)))  # which IS the training null
            print(f"[dataset] metrical_dir: {n_cov}/{len(self.paths)} crops have a "
                  f".metrical.npy sidecar (rest train as the all-zero null — kept, not dropped)",
                  flush=True)
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
        if self.dual_scalar:                        # feature 2 = bpm_madmom; the avp augmentation crops
            before = len(self.paths)                # deliberately omit it (WORKLOG 2026-07-06) -> skip them
            self.paths = [p for p in self.paths if "bpm_madmom" in self.meta.get(p, {})]
            dropped = before - len(self.paths)
            if dropped:
                print(f"[dataset] dual_scalar: dropped {dropped}/{before} crops missing 'bpm_madmom'", flush=True)
        self._rng = np.random.default_rng(seed)

    def __len__(self):
        return len(self.paths)

    def _melody_path(self, latent_path: str) -> str:
        stem = os.path.basename(latent_path)[:-4]
        return os.path.join(str(self.melody_dir), stem + ".melody8.npy")

    def _metrical_path(self, latent_path: str) -> str:
        stem = os.path.basename(latent_path)[:-4]
        return os.path.join(str(self.metrical_dir), stem + ".metrical.npy")

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
            if getattr(self, "active_density", False):
                # outro-cheat fix: density over ACTIVE frames only (rms-gated),
                # so silent tails can't fake low density (Kim 2026-07-07)
                dens = window_onset_density_active(onset_w, energy_w)
            else:
                dens = window_onset_density(onset_w)
            vec.append((dens - om) / os_)       # window-aggregated (alignment fix)
            vec.append((window_energy(energy_w) - em) / es_)
        return torch.tensor(vec, dtype=torch.float32)

    def _build_dual_scalar(self, m: dict) -> torch.Tensor:
        """Stripped 2-dim sibling of _build_fingerprint: [standardize(feature), standardize(bpm_madmom)].

        Feature 1 = the per-crop .json `scalar_field` (e.g. onset_density); feature 2 = the track-level
        bpm_madmom. Both are pre-standardized with the corpus (mean,std) pairs (`scalar_norm` for the
        feature, `bpm_mean/bpm_std` for bpm) so 0 == corpus mean == the cfg-dropout null. Conditioning on
        BOTH stops the adapter cheating a feature target by shifting tempo. Used only for the json-scalar
        path; the scalar-from-timeseries path assembles the window-mean feature in the training loop and
        combines it with `dual_bpm` (below).
        """
        raw_f = float(m.get(self.scalar_field, self.scalar_mean))
        std_f = (raw_f - self.scalar_mean) / (self.scalar_std + 1e-9)
        std_bpm = (float(m.get("bpm_madmom", self.bpm_mean)) - self.bpm_mean) / (self.bpm_std + 1e-9)
        return torch.tensor([std_f, std_bpm], dtype=torch.float32)

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
        melody_cls = None
        if self.melody_dir is not None:            # (4096,) int8 contour classes, latent-frame grid
            melody_cls = np.load(self._melody_path(p)).astype(np.int64)
        metrical_cls = None
        metrical_conf = None
        if self.metrical_dir is not None:          # (5, 4096) int8 tree classes + (4096,) conf
            mp = self._metrical_path(p)
            if os.path.exists(mp):
                metrical_cls = np.load(mp).astype(np.int64)
                cp = mp[:-len(".metrical.npy")] + ".metrical_conf.npy"
                metrical_conf = (np.load(cp).astype(np.float32) if os.path.exists(cp)
                                 else np.zeros(metrical_cls.shape[-1], dtype=np.float32))
            else:                                  # missing sidecar = uncovered: the all-zero null
                metrical_cls = np.zeros((5, lat.shape[-1]), dtype=np.int64)
                metrical_conf = np.zeros(lat.shape[-1], dtype=np.float32)
        if self.random_crop_frames and lat.shape[-1] > self.random_crop_frames:  # beat-aligned random window
            s = self._beat_aligned_start(stem, lat.shape[-1]); tw = self.random_crop_frames
            lat = np.ascontiguousarray(lat[:, s:s + tw])
            controls = {k: v[:, s:s + tw].contiguous() for k, v in controls.items()}
            if melody_cls is not None:
                melody_cls = np.ascontiguousarray(melody_cls[s:s + tw])
            if metrical_cls is not None:
                metrical_cls = np.ascontiguousarray(metrical_cls[:, s:s + tw])
                metrical_conf = np.ascontiguousarray(metrical_conf[s:s + tw])
        item = {
            "latent": torch.from_numpy(lat),                             # (256, 4096) or (256, crop) if random
            "prompt": m.get("prompt", ""),
            "controls": controls,
            "stem": os.path.basename(stem),
            "seconds_total": float(m.get("seconds_total", 0.0)),
        }
        if melody_cls is not None:
            item["melody_cls"] = torch.from_numpy(melody_cls)            # (T,) int64
        if metrical_cls is not None:
            item["metrical_cls"] = torch.from_numpy(metrical_cls)        # (5, T) int64
            item["metrical_conf"] = torch.from_numpy(metrical_conf)      # (T,) float32
        if self.audio_ref == "same_track":
            item["ref_latent"] = self._pick_reference(p)
        if self.fingerprint:
            item["fingerprint"] = self._build_fingerprint(m, controls)
        if self.scalar_field is not None:           # normalised per-crop scalar control (e.g. onset_density)
            raw = float(m.get(self.scalar_field, self.scalar_mean))
            item["scalar"] = torch.tensor((raw - self.scalar_mean) / (self.scalar_std + 1e-9), dtype=torch.float32)
        if self.dual_scalar:                        # 2-vector {feature, bpm_madmom}, both standardized
            if self.scalar_field is not None:       # json-scalar feature path -> full (2,) vector here
                item["dual_scalar"] = self._build_dual_scalar(m)
            else:                                   # timeseries-window-mean path -> feature assembled in the
                std_bpm = (float(m.get("bpm_madmom", self.bpm_mean)) - self.bpm_mean) / (self.bpm_std + 1e-9)
                item["dual_bpm"] = torch.tensor(std_bpm, dtype=torch.float32)  # loop; provide std bpm only
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
